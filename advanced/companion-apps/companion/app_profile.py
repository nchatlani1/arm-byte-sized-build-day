"""Private local companion preferences. Device personalization lives in VS Code."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile

DEFAULT = {'version': 2, 'calendar_enabled': False, 'spotify_enabled': False, 'spotify_client_id': ''}


def data_dir():
    if os.environ.get('CROWPANEL_APP_DATA'):
        return Path(os.environ['CROWPANEL_APP_DATA'])
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/CrowPanel Companion'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CrowPanel Companion'
    return Path.home() / '.local/share/crowpanel-companion'


def private_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.crowpanel-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate(raw):
    if not isinstance(raw, dict):
        raise ValueError('Companion settings must be an object.')
    result = copy.deepcopy(DEFAULT)
    for key in ('calendar_enabled', 'spotify_enabled'):
        value = raw.get(key, False)
        if type(value) is not bool:
            raise ValueError('Source switches must be true or false.')
        result[key] = value
    client = raw.get('spotify_client_id', '')
    if not isinstance(client, str) or (client and not re.fullmatch(r'[a-fA-F0-9]{32}', client)):
        raise ValueError('Enter the public 32-character Spotify Client ID, never a client secret.')
    result['spotify_client_id'] = client
    return result


class Preferences:
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else data_dir()
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.folder / 'connections.json'
        self.value = validate(json.loads(self.path.read_text())) if self.path.exists() else copy.deepcopy(DEFAULT)
        # Migrate only account toggles from the earlier local GUI pilot.
        previous = self.folder / 'profile.json'
        if not self.path.exists() and previous.exists():
            old = json.loads(previous.read_text())
            self.value = validate(dict(old, spotify_enabled=old.get('music_source') == 'spotify'))
            private_json(self.path, self.value)

    def save(self, raw):
        value = validate(raw)
        private_json(self.path, value)
        self.value = value
        return copy.deepcopy(value)
