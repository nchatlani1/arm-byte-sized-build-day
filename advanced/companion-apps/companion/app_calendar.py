"""Local, read-only calendars. Calendar contents never enter a cloud service."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from app_profile import private_json


class Calendar:
    def __init__(self, resources, folder):
        self.resources, self.folder = Path(resources), Path(folder)
        self.config = self.folder / 'calendar.json'
        self.choices = []

    def choose(self, identifiers):
        if not isinstance(identifiers, list) or not identifiers or not all(isinstance(x, str) for x in identifiers):
            raise ValueError('Select at least one calendar.')
        available = {c['id'] for c in self.choices}
        if not set(identifiers) <= available:
            raise ValueError('Choose a calendar returned by this reader.')
        private_json(self.config, {'calendar_ids': identifiers})

    def read(self):
        if sys.platform == 'darwin':
            return self._mac()
        if sys.platform == 'win32':
            return self._windows()
        raise RuntimeError('Live calendars require macOS Calendar or Windows classic Outlook.')

    def _mac(self):
        app = self.resources / 'native/CrowPanel Calendar.app'
        if not app.exists():
            app = self.resources / '.local/CrowPanel Calendar.app'
        if not app.exists():
            raise RuntimeError('Calendar helper is missing. Rebuild the Mac app.')
        with tempfile.TemporaryDirectory(prefix='crowpanel-calendar-') as folder:
            output = Path(folder) / 'event.json'
            process = subprocess.Popen(['open', '-n', '-W', str(app), '--args', '--config', str(self.config), '--output', str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 115
                while not output.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Calendar reader timed out. Check the Calendar permission prompt.')
                    time.sleep(.2)
                result = json.loads(output.read_text())
                self.choices = result.get('calendars', self.choices)
                if result.get('calendar_ids') and not self.config.exists():
                    private_json(self.config, {'calendar_ids': result['calendar_ids']})
                return result
            finally:
                if process.poll() is None:
                    process.terminate()

    def _windows(self):
        # Outlook Object Model requires an interactive desktop and classic Outlook.
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch('Outlook.Application')
            namespace = outlook.GetNamespace('MAPI')
            items = namespace.GetDefaultFolder(9).Items
            items.Sort('[Start]')
            items.IncludeRecurrences = True
            now = datetime.now()
            end = now + timedelta(days=7)
            query = "[Start] >= '{}' AND [Start] <= '{}'".format(now.strftime('%m/%d/%Y %I:%M %p'), end.strftime('%m/%d/%Y %I:%M %p'))
            upcoming = items.Restrict(query)
            for i, event in enumerate(upcoming):
                if i >= 1000:
                    break
                if event.AllDayEvent or event.BusyStatus == 0 or event.MeetingStatus in (5, 7) or event.ResponseStatus == 4:
                    continue
                start = event.Start.timestamp()
                if start <= time.time():
                    continue
                return {'status': 'ok', 'title': 'Private meeting' if event.Sensitivity == 2 else str(event.Subject or 'Meeting'), 'start': start, 'end': event.End.timestamp()}
            return {'status': 'empty'}
        except Exception:
            raise RuntimeError('Open classic Outlook with a synced calendar. New Outlook does not expose this calendar interface.') from None
        finally:
            pythoncom.CoUninitialize()
