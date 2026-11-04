#!/usr/bin/env python3
"""Desktop companion service. Local assets; authenticated loopback-only API."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import selectors
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit, urlencode
import webbrowser

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
os.environ['CROWPANEL_RESOURCE_ROOT'] = str(ROOT)
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'companion'))
from app_core import Core
from app_profile import private_json
from app_spotify import REDIRECT


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, core, port=0):
        self.core, self.token = core, secrets.token_urlsafe(32)
        self.oauth_server = None
        self.halt, self.done = threading.Event(), threading.Event()
        self.wake_read, self.wake_write = socket.socketpair()
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)

    def serve_forever(self, poll_interval=None):
        # The desktop server sleeps until an HTTP request or shutdown signal.
        # BaseServer's default half-second shutdown polling would wake an idle app.
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self,selectors.EVENT_READ)
                selector.register(self.wake_read,selectors.EVENT_READ)
                while not self.halt.is_set():
                    for key,_ in selector.select():
                        if key.fileobj is self.wake_read:
                            return
                        if not self.halt.is_set():
                            self._handle_request_noblock()
        finally:
            self.done.set()

    def shutdown(self):
        self.halt.set()
        self.wake_write.send(b'!')
        self.done.wait()

    def server_close(self):
        super().server_close()
        self.wake_read.close()
        self.wake_write.close()

    def spotify_connect(self):
        if self.oauth_server:
            raise ValueError('A Spotify sign-in is already open. Finish it or wait five minutes and retry.')
        core = self.core
        outer = self
        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path != '/callback' or self.headers.get('Host') != '127.0.0.1:8766':
                    self.send_error(404)
                    return
                query = parse_qs(parsed.query)
                try:
                    core.spotify.callback(query.get('state', [''])[0], query.get('code', [''])[0], query.get('error', [''])[0])
                    core.refresh()
                    message = 'Spotify connected. You can return to CrowPanel Companion.'
                    code = 200
                except Exception as exc:
                    # Provider error strings are deliberately credential-free.
                    message, code = str(exc), 400
                body = message.encode()
                self.send_response(code)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                if code == 200 or core.spotify.pending is None:
                    threading.Thread(target=outer.stop_oauth, daemon=True).start()
        try:
            callback = ThreadingHTTPServer(('127.0.0.1', 8766), Callback)
        except OSError:
            raise ValueError('Spotify callback port 8766 is busy. Close the other sign-in helper and retry.') from None
        try:
            url = core.spotify.begin(core.preferences.value['spotify_client_id'])
        except Exception:
            callback.server_close()
            raise
        self.oauth_server = callback
        threading.Thread(target=callback.serve_forever, daemon=True).start()
        timer = threading.Timer(300, lambda: self.stop_oauth() if self.oauth_server is callback else None)
        timer.daemon = True
        timer.start()
        webbrowser.open(url)

    def stop_oauth(self):
        server, self.oauth_server = self.oauth_server, None
        if server:
            server.shutdown()
            server.server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, mime='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        expected = '127.0.0.1:' + str(self.server.server_port)
        if self.headers.get('Host') != expected:
            self.reply(403, {'error': 'Invalid host.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            self.reply(403, {'error': 'Invalid origin.'})
            return False
        token = self.headers.get('X-CrowPanel-Token', '')
        if not secrets.compare_digest(token, self.server.token):
            self.reply(401, {'error': 'Open the companion app to start an authenticated session.'})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'application/javascript'), '/app.css': ('app.css', 'text/css')}
        if path in assets:
            if self.headers.get('Host') != '127.0.0.1:' + str(self.server.server_port):
                self.reply(403, {'error': 'Invalid host.'})
                return
            file, mime = assets[path]
            self.reply(200, (ROOT / 'companion/ui' / file).read_bytes(), mime)
            return
        if not self.allowed():
            return
        core = self.server.core
        if path == '/api/state':
            self.reply(200, core.state())
        elif path == '/api/ports':
            self.reply(200, core.device.ports())
        else:
            self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.allowed():
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 65536 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Use a bounded JSON request.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
            core = self.server.core
            path = urlsplit(self.path).path
            result = {'ok': True}
            if path == '/api/preferences':
                result = core.save(body)
            elif path == '/api/refresh':
                core.refresh()
            elif path == '/api/connect':
                core.connect(body.get('kind'), body.get('address'))
            elif path == '/api/disconnect':
                core.disconnect()
            elif path == '/api/reconnect':
                core.reconnect()
            elif path == '/api/suspend':
                core.suspend()
            elif path == '/api/wake':
                core.resume_from_sleep()
            elif path == '/api/scan':
                result = core.device.scan()
            elif path == '/api/spotify/connect':
                self.server.spotify_connect()
            elif path == '/api/spotify/disconnect':
                core.spotify.disconnect(core.preferences.value['spotify_client_id'])
                core.refresh()
            elif path == '/api/calendar/select':
                core.calendar.choose(body.get('ids'))
                core.refresh()
            else:
                self.reply(404, {'error': 'Not found.'})
                return
            self.reply(200, result)
        except Exception as exc:
            # Never return provider payloads, URLs or token cache contents.
            safe = isinstance(exc, (ValueError, RuntimeError)) or exc.__class__.__name__ in ('SpotifyError', 'ProviderError')
            self.reply(400, {'error': str(exc) if safe else 'The action could not complete. Check the connection and retry.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--boot-file')
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--parent-pid', type=int)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--background', action='store_true')
    args = parser.parse_args()
    instance = None
    if sys.platform == 'win32' and not args.browser:
        from app_windows import Instance
        instance = Instance()
        if not instance.acquired:
            instance.show_existing()
            return
    core = Core(ROOT, network=not args.offline)
    server = LocalServer(core)
    url = server.origin + '/#' + server.token
    private_json(core.preferences.folder / 'runtime.json', {'url': url, 'pid': os.getpid()})
    if args.boot_file:
        private_json(args.boot_file, {'url': url, 'pid': os.getpid()})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def terminate(*_):
        server.stop_oauth()
        server.shutdown()
        (core.preferences.folder / 'runtime.json').unlink(missing_ok=True)
        core.close()
        os._exit(0)
    if args.parent_pid:
        def watch_parent():
            if sys.platform == 'darwin':
                import select
                try:
                    queue = select.kqueue()
                    try:
                        event = select.kevent(args.parent_pid,filter=select.KQ_FILTER_PROC,flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,fflags=select.KQ_NOTE_EXIT)
                        queue.control([event],1,None)
                    finally:
                        queue.close()
                    terminate()
                    return
                except (OSError,ValueError):
                    pass
            while not core.stop.is_set():
                try:
                    os.kill(args.parent_pid, 0)
                except OSError:
                    terminate()
                    return
                core.stop.wait(60)
        threading.Thread(target=watch_parent, daemon=True).start()
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    if sys.platform == 'win32' and not args.browser:
        from app_windows import run
        run(url,core,args.background,instance)
        terminate()
    elif args.browser:
        webbrowser.open(url)
    # Keep the main thread alive until terminate finishes cleanup and exits.
    # Joining the HTTP daemon can end the interpreter before a parent watcher
    # removes runtime state and closes the transport.
    threading.Event().wait()

if __name__ == '__main__':
    main()
