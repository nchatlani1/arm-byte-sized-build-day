#!/usr/bin/env python3
"""Check a real Windows portable ZIP without accounts, devices, or startup changes."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        parser.error('Run this smoke check on Windows x64 with Python x64.')
    archive = args.archive.resolve()
    checks = []
    process = None
    with tempfile.TemporaryDirectory(prefix='crowpanel-windows-smoke-') as folder:
        work = Path(folder)
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip():
                raise RuntimeError('Archive integrity check failed')
            for member in zipped.namelist():
                destination = (work / member).resolve()
                if work.resolve() not in destination.parents:
                    raise RuntimeError('Archive contains an unsafe path')
            zipped.extractall(work)
        exe = work / 'CrowPanel Companion Windows/CrowPanelBackend.exe'
        data = exe.read_bytes()
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        assert data[:2] == b'MZ' and data[pe:pe+4] == b'PE\0\0'
        assert struct.unpack_from('<H', data, pe+4)[0] == 0x8664, 'Expected AMD64 executable'
        checks.append('Portable ZIP integrity and real AMD64 PE executable')
        profile = work / 'isolated-profile'
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.FindWindowW.restype = ctypes.c_void_p
        try:
            process = subprocess.Popen([str(exe), '--offline', '--background'],
                cwd=exe.parent, env=dict(os.environ, CROWPANEL_APP_DATA=str(profile)))
            deadline = time.monotonic() + 90
            runtime = profile / 'runtime.json'
            while not runtime.exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Packaged service did not become ready')
                time.sleep(.2)
            metadata = json.loads(runtime.read_text())
            assert metadata['pid'] == process.pid
            parsed = urlsplit(metadata['url'])
            assert parsed.hostname == '127.0.0.1'
            origin = 'http://127.0.0.1:' + str(parsed.port)
            headers = {'X-CrowPanel-Token': parsed.fragment}
            for path in ('/', '/app.js', '/app.css'):
                with urlopen(origin + path, timeout=10) as response:
                    assert response.status == 200 and response.read()
            checks.append('Packaged HTML, JavaScript, and CSS served locally')
            try:
                urlopen(origin + '/api/state', timeout=10)
            except HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError('Unauthenticated API was accepted')
            with urlopen(Request(origin + '/api/state', headers=headers), timeout=10) as response:
                state = json.load(response)
            assert state['device']['label'] == 'Disconnected'
            assert not state['preferences']['calendar_enabled']
            assert not state['preferences']['spotify_enabled']
            checks.append('Authenticated loopback API; disconnected accounts remain disabled')
            while True:
                hwnd = user32.FindWindowW('CrowPanelCompanionTray', 'CrowPanelCompanionTray')
                if hwnd:
                    owner = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(owner))
                    assert owner.value == process.pid, 'A different companion owns the tray'
                    break
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Native notification-area host did not start; check WebView2')
                time.sleep(.2)
            checks.append('Native Windows notification-area host belongs to the packaged process')
        finally:
            if process is not None and process.poll() is None:
                # CI cleanup only: native menu Quit, sleep/resume, and startup need a real pilot.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                process.wait(timeout=15)
    report = {'status': 'CI smoke passed', 'platform': sys.platform, 'architecture': 'x64',
        'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'checks': checks, 'pending': ['WebView2 visual rendering', 'tray controls and clean Quit',
            'real USB and Bluetooth', 'classic Outlook and Spotify sign-in',
            'Start at sign-in and sleep/wake', 'disconnected energy measurements',
            'publisher signing and target-device acceptance']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
