"""Account-data bridge only. Layout, personalization and public feeds run on ESP32."""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime
import json
from pathlib import Path
import threading
import time
import unicodedata
from app_profile import Preferences, private_json
from app_spotify import Spotify
from app_calendar import Calendar
from app_transport import Transport


def display_text(value, limit):
    punctuation = str.maketrans({'–':'-', '—':'-', '−':'-', '‘':"'", '’':"'", '“':'"', '”':'"', '…':'...'})
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(value).translate(punctuation)) if not unicodedata.combining(c)).encode('ascii','replace').decode()
    value = ''.join(c if 32 <= ord(c) <= 126 else ' ' for c in value)
    return ' '.join(value.split())[:limit]


def messages(preferences, values, sources, now=None):
    now = time.time() if now is None else now
    calendar = {'op':'calendar','status':'off','lease':180}
    music = {'op':'spotify','status':'off','lease':180}
    if preferences['calendar_enabled']:
        result = values.get('calendar', {})
        calendar['status'] = 'unavailable'
        if sources['calendar']['status'] == 'live':
            if result.get('status') == 'empty':
                calendar['status'] = 'empty'
            elif result.get('start', 0) > now:
                start = result['start']
                calendar.update(status='ok',title=display_text(result.get('title','Meeting'),120),time=datetime.fromtimestamp(start).astimezone().strftime('%a %I:%M %p').replace(' 0',' '),lease=max(1,min(180,int(start-now))))
    if preferences['spotify_enabled']:
        result = values.get('spotify')
        music['status'] = 'unavailable'
        if sources['spotify']['status'] == 'live':
            item = (result or {}).get('item')
            if not item:
                music['status'] = 'empty'
            else:
                episode = result.get('currently_playing_type') == 'episode'
                artist = item.get('show',{}).get('name','Podcast') if episode else ', '.join(a.get('name','') for a in item.get('artists',[]))
                music.update(status='ok',track=display_text(item.get('name','Unknown audio'),120),artist=display_text(artist,64),playing=bool(result.get('is_playing')))
    for packet in (calendar,music):
        # JSON escaping can double ASCII quotes/backslashes. Bound the actual
        # wire command, including the largest transport ID, not just text length.
        fields=[key for key in ('title','track','artist') if key in packet]
        while len(json.dumps(dict(packet,id=2147483647),separators=(',',':')).encode())+1 > 383:
            key=max(fields,key=lambda field:len(json.dumps(packet[field])))
            packet[key]=packet[key][:-1]
    return [calendar, music]


class Core:
    def __init__(self, resources, folder=None, network=True, start_loop=True):
        self.preferences = Preferences(folder)
        self.spotify = Spotify()
        self.calendar = Calendar(resources,self.preferences.folder)
        self.lock = threading.RLock()
        self.wake, self.stop = threading.Event(), threading.Event()
        self.device = Transport()
        # Transport callbacks only signal; never wait for the core lock on the BLE loop.
        self.device.on_disconnect = self.wake.set
        self.pool = ThreadPoolExecutor(max_workers=3,thread_name_prefix='account-bridge')
        self.network = network
        self.values = {}
        self.sources = {k:{'status':'idle' if self.preferences.value[k+'_enabled'] else 'off','message':'Waiting for a connected display' if self.preferences.value[k+'_enabled'] else 'Not enabled','updated':None} for k in ('calendar','spotify')}
        self.pending, self.due = set(), {}
        self.device_busy = False
        self.connection_generation = 0
        self.device_error = ''
        self.last_send = 0
        self.connected = False
        self.suspended = False
        self.retry_count = 0
        self.device_config = self.preferences.folder/'device.json'
        try:
            saved = json.loads(self.device_config.read_text())
            self.saved_device = saved if saved.get('kind') in ('usb','ble') and isinstance(saved.get('address'),str) and saved['address'] else None
        except (OSError,ValueError,AttributeError):
            self.saved_device = None
        self.want_connection = bool(self.saved_device and not self.saved_device.get('paused',False))
        self.reconnect_due = 0
        self.thread = threading.Thread(target=self._loop,daemon=True)
        if start_loop:
            self.thread.start()

    def _idle(self):
        self.values.clear()
        for key in self.sources:
            enabled = self.preferences.value[key+'_enabled']
            self.sources[key].update(status='idle' if enabled else 'off',message='Waiting for a connected display' if enabled else 'Not enabled',updated=None)

    def save(self, raw):
        with self.lock:
            previous = self.preferences.value
            current = self.preferences.save(raw)
            for key in self.sources:
                changed = previous[key+'_enabled'] != current[key+'_enabled'] or (key == 'spotify' and previous['spotify_client_id'] != current['spotify_client_id'])
                if changed:
                    self.values.pop(key,None)
                    self.due[key] = 0
                    self.sources[key] = {'status':'waiting' if current[key+'_enabled'] else 'off','message':'Checking account access…' if current[key+'_enabled'] else 'Not enabled','updated':None}
            if self.device.label == 'Disconnected':
                self._idle()
            self.last_send = 0
        self.wake.set()
        return self.state()

    def _fetch(self, key, preferences, generation=None):
        with self.lock:
            if generation is not None and (generation != self.connection_generation or self.device.label == 'Disconnected' or self.suspended or self.stop.is_set()):
                self.pending.discard(key)
                self.wake.set()
                return
        value, error, retry = None, None, 60
        try:
            if key == 'calendar':
                value = self.calendar.read()
                if value.get('status') not in ('ok','empty'):
                    errors = {'permission_denied':'Allow CrowPanel Companion or CrowPanel Calendar in macOS Privacy & Security → Calendars.','no_exchange_calendar':'Sync your permitted Exchange account in macOS Calendar first.','choose_calendar':'Choose your work calendar below.','calendar_missing':'Select your work calendar again.'}
                    raise RuntimeError(errors.get(value.get('status'),'Calendar access timed out. Allow CrowPanel Companion or CrowPanel Calendar in macOS Privacy & Security → Calendars, then refresh.'))
            else:
                value = self.spotify.playback(preferences['spotify_client_id'])
        except Exception as exc:
            error = str(exc) if isinstance(exc,RuntimeError) or exc.__class__.__name__ == 'SpotifyError' else 'Account data is unavailable. Check access and retry.'
            retry = getattr(exc,'retry_after',60)
        with self.lock:
            self.pending.discard(key)
            stale = generation is not None and (generation != self.connection_generation or self.device.label == 'Disconnected' or self.suspended)
            if preferences != self.preferences.value or stale:
                self.due[key] = 0
            else:
                self.due[key] = time.monotonic() + (max(30,retry) if error else 30)
                if error:
                    self.sources[key].update(status='error',message=error)
                else:
                    self.values[key] = value
                    self.sources[key].update(status='live',message='Reading local work calendar' if key == 'calendar' else 'Reading account playback · phone, browser or desktop',updated=time.time())
                self.last_send = 0
        self.wake.set()

    def _retry_later(self):
        delay = min(300,30 * 2 ** min(self.retry_count,4))
        self.retry_count += 1
        self.reconnect_due = time.monotonic() + delay

    def connect(self, kind, address, automatic=False):
        if kind not in ('usb','ble') or not isinstance(address,str) or not address or len(address)>512:
            raise ValueError('Choose an available USB or Bluetooth display.')
        with self.lock:
            if self.device_busy:
                raise ValueError('A connection is still running. Please wait a moment.')
            self.device_busy = True
            self.connection_generation += 1
            generation = self.connection_generation
            self.want_connection = False
            self.connected = False
            self._idle()
        def run():
            try:
                # Manual pairing may need longer OS prompts; saved targets use a short scan.
                self.device.connect(kind,address,automatic)
                with self.lock:
                    if generation != self.connection_generation or self.stop.is_set():
                        self.device.disconnect()
                        return
                    self.saved_device = {'kind':kind,'address':address,'paused':False}
                    private_json(self.device_config,self.saved_device)
                    self.want_connection = True
                    self.connected = True
                    self.device_error = ''
                    self.retry_count = 0
                    self.due.clear()
                    self.last_send = 0
            except Exception as exc:
                with self.lock:
                    if generation == self.connection_generation:
                        self.device_error = str(exc)
                        self.device.message = self.device_error
                        self.want_connection = bool(self.saved_device and not self.saved_device.get('paused',False) and self.saved_device['kind'] == kind and self.saved_device['address'] == address)
                        self._retry_later()
            finally:
                with self.lock:
                    self.device_busy = False
                self.wake.set()
        self.pool.submit(run)
        self.wake.set()

    def _send(self, packets, generation):
        try:
            for packet in packets:
                with self.lock:
                    if generation != self.connection_generation or self.suspended or self.stop.is_set():
                        return
                capabilities = getattr(self.device, 'capabilities', None)
                if capabilities is None or packet['op'] in capabilities:
                    self.device.send_data(packet)
            self.device_error = ''
        except Exception as exc:
            self.device.disconnect()
            with self.lock:
                if generation == self.connection_generation:
                    self.device_error = str(exc)
                    self.device.message = self.device_error
                    self._retry_later()
        finally:
            with self.lock:
                self.device_busy = False
            self.wake.set()

    def _tick(self):
        with self.lock:
            if self.suspended or self.stop.is_set():
                return None
            now = time.monotonic()
            if self.device.label == 'Disconnected':
                if self.connected:
                    self.connected = False
                    self.connection_generation += 1
                    self._idle()
                    if now >= self.reconnect_due:
                        self._retry_later()
                if self.want_connection and self.saved_device and not self.device_busy:
                    if now >= self.reconnect_due:
                        self.connect(self.saved_device['kind'],self.saved_device['address'],automatic=True)
                        return None
                    return max(.1,self.reconnect_due-now)
                # No periodic account reads, broad scans or half-second wakeups while idle.
                return None
            p = copy.deepcopy(self.preferences.value)
            # A connected display advertises which optional projects were compiled.
            # Do not read an account whose screen is absent from this firmware.
            capabilities = getattr(self.device, 'capabilities', None)
            for key in self.sources:
                if capabilities is not None and key not in capabilities and p[key+'_enabled']:
                    p[key+'_enabled'] = False
                    self.values.pop(key, None)
                    self.sources[key].update(status='error', message='Enable extensions.'+key+' in device.json, then build/upload your Morning Briefing project.', updated=None)
            deadlines = []
            for key in self.sources:
                if self.network and p[key+'_enabled'] and key not in self.pending:
                    due = self.due.get(key,0)
                    if now >= due:
                        self.pending.add(key)
                        self.pool.submit(self._fetch,key,p,self.connection_generation)
                    else:
                        deadlines.append(due)
            if not self.device_busy:
                if now-self.last_send >= 30:
                    self.last_send = now
                    self.device_busy = True
                    self.pool.submit(self._send,messages(p,self.values,self.sources),self.connection_generation)
                else:
                    deadlines.append(self.last_send+30)
            return max(.1,min(deadlines)-now) if deadlines else None

    def _loop(self):
        while not self.stop.is_set():
            self.wake.clear()
            timeout = self._tick()
            self.wake.wait(timeout)

    def state(self):
        with self.lock:
            return {'preferences':copy.deepcopy(self.preferences.value),'sources':copy.deepcopy(self.sources),'spotify_connected':self.spotify.connected(self.preferences.value['spotify_client_id']),'spotify_message':self.spotify.message,'calendar_choices':list(self.calendar.choices),'device':{'label':self.device.label,'message':self.device.message,'busy':self.device_busy,'error':self.device_error,'paused':not self.want_connection and not self.device_busy},'saved_device':copy.deepcopy(self.saved_device)}

    def refresh(self):
        with self.lock:
            self.due.clear()
            self.last_send = 0
        self.wake.set()

    def reconnect(self):
        with self.lock:
            if not self.saved_device:
                raise ValueError('Choose and connect a device first.')
            self.saved_device['paused'] = False
            private_json(self.device_config,self.saved_device)
            self.want_connection = True
            self.retry_count = 0
            self.reconnect_due = 0
        self.wake.set()

    def disconnect(self):
        with self.lock:
            self.want_connection = False
            self.connection_generation += 1
            self.connected = False
            self._idle()
            if self.saved_device:
                self.saved_device['paused'] = True
                private_json(self.device_config,self.saved_device)
        self.device.disconnect()
        self.device.message = 'Paused. USB is available to PlatformIO. Resume when ready.'
        self.wake.set()

    def suspend(self):
        with self.lock:
            self.suspended = True
            self.connection_generation += 1
            self.connected = False
            self._idle()
        # Sleeping must not change the user's persisted Pause/Resume choice.
        self.device.disconnect()
        self.wake.set()

    def resume_from_sleep(self):
        with self.lock:
            self.suspended = False
            self.reconnect_due = 0
            self.retry_count = 0
            self.due.clear()
        self.wake.set()

    def close(self):
        self.stop.set()
        self.connection_generation += 1
        self.wake.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)
        self.device.close()
        self.pool.shutdown(wait=False,cancel_futures=True)
