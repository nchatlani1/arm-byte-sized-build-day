"""Read-only account-level Spotify PKCE; tokens stay in OS credential storage."""
import base64
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import webbrowser

REDIRECT = 'http://127.0.0.1:8766/callback'
SERVICE = 'CrowPanel Companion Spotify'


class SpotifyError(Exception):
    pass


class Spotify:
    def __init__(self, vault=None):
        if vault is None:
            import keyring
            vault = keyring
        self.vault = vault
        self.pending = None
        self.lock = threading.Lock()
        self.message = 'Connect your Spotify account to read phone, browser or desktop playback.'

    def _read(self, client):
        try:
            raw = self.vault.get_password(SERVICE, client)
            return json.loads(raw) if raw else None
        except Exception:
            raise SpotifyError('OS credential storage is unavailable. Unlock it and retry.') from None

    def connected(self, client):
        if not client:
            return False
        try:
            return bool(self._read(client))
        except SpotifyError:
            return False

    def _save(self, client, token):
        try:
            self.vault.set_password(SERVICE, client, json.dumps(token))
        except Exception:
            raise SpotifyError('Could not save Spotify sign-in in OS credential storage.') from None

    def disconnect(self, client):
        if client:
            try:
                self.vault.delete_password(SERVICE, client)
            except Exception:
                if self._read(client):
                    raise SpotifyError('Could not remove the Spotify credential.') from None
        self.message = 'Spotify disconnected.'

    def begin(self, client):
        if not client:
            raise SpotifyError('Enter your Spotify app Client ID first. No client secret is needed.')
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with self.lock:
            self.pending = {'client': client, 'verifier': verifier, 'state': state,
                            'expires': time.monotonic() + 300}
        self.message = 'Complete Spotify sign-in in your browser.'
        return 'https://accounts.spotify.com/authorize?' + urlencode({
            'client_id': client, 'response_type': 'code', 'redirect_uri': REDIRECT,
            'scope': 'user-read-currently-playing', 'state': state,
            'code_challenge_method': 'S256', 'code_challenge': challenge})

    def callback(self, state, code, error=''):
        with self.lock:
            pending = self.pending
            if not pending or time.monotonic() > pending['expires'] or not secrets.compare_digest(state, pending['state']):
                raise SpotifyError('This sign-in has expired or its state is invalid. Try Connect again.')
            self.pending = None
        if error or not code:
            self.message = 'Spotify sign-in was cancelled or denied.'
            raise SpotifyError(self.message)
        token = self._request('https://accounts.spotify.com/api/token', {
            'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT,
            'client_id': pending['client'], 'code_verifier': pending['verifier']})
        if not token.get('access_token') or not token.get('refresh_token'):
            raise SpotifyError('Spotify did not supply a complete sign-in. Try again.')
        token['expires_at'] = time.time() + token.get('expires_in', 3600)
        self._save(pending['client'], token)
        self.message = 'Spotify connected. Playback can be on your phone, browser or desktop.'

    def _request(self, url, body=None, bearer=None):
        headers = {'Accept': 'application/json', 'User-Agent': 'CrowPanelCompanion/1.0'}
        payload = None
        if body is not None:
            payload = urlencode(body).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if bearer:
            headers['Authorization'] = 'Bearer ' + bearer
        try:
            with urlopen(Request(url, data=payload, headers=headers), timeout=12) as response:
                if response.status == 204:
                    return None
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise SpotifyError('Spotify response was too large.')
                return json.loads(data)
        except HTTPError as exc:
            if exc.code == 429:
                retry = exc.headers.get('Retry-After', '60')
                seconds = int(retry) if retry.isdigit() else 60
                error = SpotifyError(f'Spotify rate limit reached; retry in {seconds} seconds.')
                error.retry_after = max(30, min(seconds, 86400))
                raise error from None
            if exc.code == 403:
                raise SpotifyError('Spotify denied access. Check app eligibility and the app user allowlist.') from None
            if exc.code in (400, 401):
                raise SpotifyError('Spotify sign-in needs attention. Reconnect your account.') from None
            raise SpotifyError(f'Spotify returned HTTP {exc.code}.') from None
        except (URLError, TimeoutError, ValueError):
            raise SpotifyError('Spotify could not be reached. Check connectivity and retry.') from None

    def playback(self, client):
        with self.lock:
            token = self._read(client) if client else None
            if not token:
                raise SpotifyError('Connect Spotify first.')
            if token.get('expires_at', 0) <= time.time() + 60:
                updated = self._request('https://accounts.spotify.com/api/token', {
                    'grant_type': 'refresh_token', 'refresh_token': token['refresh_token'], 'client_id': client})
                if not updated.get('access_token'):
                    raise SpotifyError('Reconnect Spotify; token refresh did not return access.')
                token.update(updated)
                token['expires_at'] = time.time() + updated.get('expires_in', 3600)
                self._save(client, token)
            return self._request('https://api.spotify.com/v1/me/player/currently-playing?additional_types=track,episode', bearer=token['access_token'])
