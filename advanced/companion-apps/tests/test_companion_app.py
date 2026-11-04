"""Account-only app boundaries, OAuth and a constrained local delivery API."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'companion'),str(ROOT/'tools')]
from app_profile import DEFAULT,Preferences,validate
from app_spotify import Spotify,SpotifyError,SERVICE
from app_core import messages,display_text,Core
from desktop import LocalServer
class Vault:
    def __init__(self):self.items={}
    def get_password(self,service,client):return self.items.get((service,client))
    def set_password(self,service,client,value):self.items[service,client]=value
    def delete_password(self,service,client):self.items.pop((service,client),None)
class Tests(unittest.TestCase):
    def test_companion_cannot_store_device_personalization(self):
        result=validate(dict(DEFAULT,stock_symbol='MSFT',weather={'city':'London'},quotes=['no'],titles={'music':'no'},access_token='secret'))
        self.assertEqual(set(result),{'version','calendar_enabled','spotify_enabled','spotify_client_id'})
        for value in (None,0,False,{},'not-id'):
            with self.assertRaises(ValueError):validate(dict(DEFAULT,spotify_client_id=value))
    def test_migration_only_keeps_account_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'profile.json').write_text(json.dumps({'calendar_enabled':True,'music_source':'sample','stock_symbol':'MSFT'}))
            pref=Preferences(folder)
            self.assertTrue(pref.value['calendar_enabled']);self.assertNotIn('stock_symbol',pref.value)
    def test_pkce_state_and_readonly_scope(self):
        spotify=Spotify(Vault());query=parse_qs(urlsplit(spotify.begin('a'*32)).query)
        self.assertEqual(query['scope'],['user-read-currently-playing'])
        expected=base64.urlsafe_b64encode(hashlib.sha256(spotify.pending['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'],[expected])
        with self.assertRaises(SpotifyError):spotify.callback('wrong','code')
        spotify._request=lambda *args,**kwargs:{'access_token':'access','refresh_token':'refresh','expires_in':3600}
        spotify.callback(query['state'][0],'code')
        self.assertTrue(spotify.connected('a'*32))
        with self.assertRaises(SpotifyError):spotify.callback(query['state'][0],'code')
    def test_refresh_keeps_refresh_token_and_uses_account_endpoint(self):
        vault=Vault();spotify=Spotify(vault);spotify._save('a'*32,{'access_token':'old','refresh_token':'retained','expires_at':0})
        calls=[]
        def response(url,body=None,bearer=None):
            calls.append(url);return {'access_token':'new','expires_in':3600} if body else {'item':None}
        spotify._request=response;spotify.playback('a'*32)
        self.assertEqual(json.loads(vault.get_password(SERVICE,'a'*32))['refresh_token'],'retained')
        self.assertIn('/me/player/currently-playing',calls[-1])
    def test_delivery_contains_data_not_pixels_or_preferences(self):
        pref=dict(DEFAULT,calendar_enabled=True,spotify_enabled=True)
        values={'calendar':{'status':'ok','title':'CS601 – Seminar','start':2000},'spotify':{'item':{'name':'Track','artists':[{'name':'Artist'}]},'is_playing':True}}
        sources={k:{'status':'live'} for k in ('calendar','spotify')}
        packets=messages(pref,values,sources,now=1900)
        self.assertEqual(packets[0]['title'],'CS601 - Seminar');self.assertEqual(packets[0]['lease'],100)
        self.assertEqual(packets[1]['track'],'Track')
        for packet in packets:
            self.assertLessEqual(len(json.dumps(dict(packet,id=123)).encode())+1,383)
            self.assertTrue(set(packet).isdisjoint({'pixels','frame','project','quotes','stock_symbol','location'}))
        expired=messages(pref,values,sources,now=2001)
        self.assertEqual(expired[0]['status'],'unavailable')
        sources['spotify']['status']='error'
        self.assertEqual(messages(pref,values,sources,1900)[1]['status'],'unavailable')
    def test_ascii_bounds_keep_unicode_data_packet_under_wire_limit(self):
        self.assertEqual(display_text('CS601 – Café',120),'CS601 - Cafe')
        pref=dict(DEFAULT,spotify_enabled=True)
        values={'spotify':{'item':{'name':'🎵'*400,'artists':[{'name':'é'*400}]},'is_playing':False}}
        sources={'calendar':{'status':'off'},'spotify':{'status':'live'}}
        self.assertLessEqual(len(json.dumps(dict(messages(pref,values,sources)[1],id=1)).encode())+1,383)
    def test_controls_and_json_escaping_stay_within_device_command_limit(self):
        self.assertEqual(display_text('A\0B\x7fC\nD',120),'A B C D')
        pref=dict(DEFAULT,spotify_enabled=True,calendar_enabled=True)
        values={'calendar':{'status':'ok','title':'"'*120,'start':2000},'spotify':{'item':{'name':'"'*120,'artists':[{'name':'"'*64}]},'is_playing':True}}
        sources={key:{'status':'live'} for key in ('calendar','spotify')}
        for packet in messages(pref,values,sources,now=1900):
            wire=json.dumps(dict(packet,id=2147483647),separators=(',',':')).encode()+b'\n'
            self.assertLessEqual(len(wire),383)
    def test_local_api_auth_and_removed_personalization_endpoints(self):
        class Fake:
            def state(self):return {'sources':{}}
        server=LocalServer(Fake());threading.Thread(target=server.serve_forever,daemon=True).start()
        def get(path,headers):return urlopen(Request(server.origin+'/api/'+path,headers=headers),timeout=3)
        try:
            with self.assertRaises(HTTPError) as e:get('state',{})
            self.assertEqual(e.exception.code,401)
            for header in ({'Origin':'https://unrelated.example'},{'Host':'unrelated.example'}):
                with self.assertRaises(HTTPError) as e:get('state',dict(header,**{'X-CrowPanel-Token':server.token}))
                self.assertEqual(e.exception.code,403)
            with get('state',{'X-CrowPanel-Token':server.token}) as response:self.assertEqual(json.load(response),{'sources':{}})
            for path in ('export','preview/morning_briefing'):
                with self.assertRaises(HTTPError) as e:get(path,{'X-CrowPanel-Token':server.token})
                self.assertEqual(e.exception.code,404)
        finally:server.shutdown();server.server_close()
    def test_pause_cancels_inflight_connect_before_upload(self):
        started,finish=threading.Event(),threading.Event()
        class Device:
            label='Disconnected';message=''
            def connect(self,*args):
                started.set();finish.wait(3);self.label='USB connected'
            def disconnect(self):self.label='Disconnected'
            def close(self):self.disconnect()
        with tempfile.TemporaryDirectory() as folder, patch('app_core.Transport',Device):
            core=Core(ROOT,folder,network=False)
            try:
                core.connect('usb','test-port');self.assertTrue(started.wait(1))
                core.disconnect();finish.set()
                core.pool.shutdown(wait=True)
                self.assertFalse(core.want_connection);self.assertEqual(core.device.label,'Disconnected')
                self.assertIsNone(core.saved_device)
            finally:finish.set();core.close()
    def test_missing_firmware_extension_does_not_read_account(self):
        with tempfile.TemporaryDirectory() as folder:
            core=Core(ROOT,folder,network=True,start_loop=False)
            try:
                core.preferences.value['spotify_enabled']=True
                core.device.capabilities=frozenset({'calendar'})
                core.device.label='USB connected'
                core.last_send=__import__('time').monotonic()
                with patch.object(core.pool,'submit') as submit:
                    core._tick()
                    submit.assert_not_called()
                self.assertIn('extensions.spotify',core.sources['spotify']['message'])
            finally:core.close()

    def test_protocol_two_accepts_new_capabilities_and_legacy_hello(self):
        from app_transport import Transport
        for hello,expected in [({'protocol':2,'mode':'data','capabilities':['calendar']},frozenset({'calendar'})),({'protocol':2,'mode':'data'},None)]:
            device=Transport()
            try:
                with patch.object(device,'ports',return_value=[{'id':'test'}]), patch('serial.Serial'), patch.object(device,'command',return_value=hello):
                    device.connect('usb','test')
                    self.assertEqual(device.capabilities,expected)
            finally:device.close()

    def test_failed_music_does_not_discard_calendar(self):
        with tempfile.TemporaryDirectory() as folder:
            core=Core(ROOT,folder,network=False)
            try:
                p=copy.deepcopy(core.preferences.value)
                core.calendar.read=lambda:{'status':'empty'}
                core._fetch('calendar',p)
                def fail(*args):raise SpotifyError('Sign-in required')
                core.spotify.playback=fail;core._fetch('spotify',p)
                self.assertEqual(core.sources['calendar']['status'],'live')
                self.assertEqual(core.sources['spotify']['status'],'error')
            finally:core.close()
if __name__=='__main__':unittest.main()
