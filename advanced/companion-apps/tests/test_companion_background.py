"""Behavioral regressions for idle, reconnect, startup and interrupted account reads."""
import copy
import json
import os
import subprocess
import time
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch, Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from app_core import Core
from app_profile import DEFAULT, private_json
from app_transport import Transport, SERVICE
from app_windows import startup_command, startup_enabled, set_startup

class Device:
    label = 'Disconnected'
    message = ''
    def connect(self,*args):
        self.label = 'Bluetooth connected'
    def disconnect(self):
        self.label = 'Disconnected'
    def close(self):
        self.disconnect()
    def send_data(self,packet):
        pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.patch = patch('app_core.Transport',Device)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def core(self,**kwargs):
        core = Core(ROOT,self.folder.name,start_loop=False,**kwargs)
        self.addCleanup(core.close)
        return core

    def test_disconnected_enabled_accounts_never_read_or_schedule_polling(self):
        core = self.core()
        core.preferences.save(dict(DEFAULT,calendar_enabled=True,spotify_enabled=True))
        core.calendar.read = Mock(side_effect=AssertionError('calendar read while absent'))
        core.spotify.playback = Mock(side_effect=AssertionError('Spotify read while absent'))
        for _ in range(20):
            core.refresh()
            self.assertIsNone(core._tick())
        self.assertEqual(core.pending,set())
        core.calendar.read.assert_not_called()
        core.spotify.playback.assert_not_called()

    def test_reconnect_backoff_is_capped_and_does_not_scan_until_due(self):
        private_json(Path(self.folder.name)/'device.json',{'kind':'ble','address':'saved'})
        core = self.core()
        with patch('app_core.time.monotonic',return_value=100):
            delays=[]
            for _ in range(7):
                core._retry_later()
                delays.append(core.reconnect_due-100)
            self.assertEqual(delays,[30,60,120,240,300,300,300])
            core.connect = Mock()
            self.assertEqual(core._tick(),300)
            core.connect.assert_not_called()
        with patch('app_core.time.monotonic',return_value=401):
            self.assertIsNone(core._tick())
            core.connect.assert_called_once_with('ble','saved',automatic=True)

    def test_pause_survives_restart_and_resume_explicitly_enables_saved_target(self):
        private_json(Path(self.folder.name)/'device.json',{'kind':'ble','address':'saved'})
        first = self.core()
        first.disconnect()
        second = self.core()
        self.assertFalse(second.want_connection)
        self.assertIsNone(second._tick())
        second.reconnect()
        third = self.core()
        self.assertTrue(third.want_connection)
        self.assertFalse(json.loads(third.device_config.read_text())['paused'])

    def test_invalid_saved_target_does_not_crash_or_reconnect(self):
        Path(self.folder.name,'device.json').write_text('[]')
        core = self.core()
        self.assertIsNone(core.saved_device)
        self.assertIsNone(core._tick())

    def test_completed_account_read_after_disconnect_cannot_restore_live_data(self):
        core = self.core()
        core.device.label='Bluetooth connected'
        p=copy.deepcopy(core.preferences.value)
        entered,finish=threading.Event(),threading.Event()
        def read():
            entered.set()
            finish.wait(2)
            return {'status':'empty'}
        core.calendar.read=read
        task=core.pool.submit(core._fetch,'calendar',p,core.connection_generation)
        self.assertTrue(entered.wait(1))
        core.disconnect()
        finish.set()
        task.result(timeout=2)
        self.assertNotIn('calendar',core.values)
        self.assertNotEqual(core.sources['calendar']['status'],'live')

    def test_queued_account_read_is_skipped_after_disconnect(self):
        core=self.core()
        core.calendar.read=Mock()
        core._fetch('calendar',copy.deepcopy(core.preferences.value),core.connection_generation)
        core.calendar.read.assert_not_called()

    def test_sleep_stops_work_and_wake_preserves_persisted_pause(self):
        private_json(Path(self.folder.name)/'device.json',{'kind':'ble','address':'saved','paused':True})
        core=self.core()
        core.suspend()
        self.assertIsNone(core._tick())
        core.resume_from_sleep()
        self.assertFalse(core.want_connection)
        self.assertTrue(json.loads(core.device_config.read_text())['paused'])

    def test_windows_startup_quotes_spaces_and_rejects_overlong_command(self):
        self.assertEqual(startup_command(r'C:\Users\Workshop User\CrowPanel\CrowPanelBackend.exe'),r'"C:\Users\Workshop User\CrowPanel\CrowPanelBackend.exe" --background')
        with self.assertRaises(ValueError):
            startup_command('x'*260)

    def test_windows_startup_writes_only_current_user_and_can_be_removed(self):
        from contextlib import nullcontext
        registry=types.SimpleNamespace(HKEY_CURRENT_USER=object(),REG_SZ=1,CreateKey=Mock(return_value=nullcontext('key')),SetValueEx=Mock(),DeleteValue=Mock())
        with patch.dict(sys.modules,winreg=registry),patch('app_windows.sys.frozen',True,create=True),patch('app_windows.sys.executable','C:/CrowPanel/CrowPanelBackend.exe'):
            set_startup(True)
            registry.CreateKey.assert_called_with(registry.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run')
            registry.SetValueEx.assert_called_once_with('key','CrowPanel Companion',0,1,'C:/CrowPanel/CrowPanelBackend.exe --background')
            registry.CreateKey.return_value=nullcontext('key')
            set_startup(False)
            registry.DeleteValue.assert_called_once_with('key','CrowPanel Companion')

    @unittest.skipUnless(sys.platform=='darwin','Native Mac process-exit notifications')
    def test_parent_exit_stops_service_without_polling_delay(self):
        parent=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        self._parent_exit_check(parent,False)

    @unittest.skipUnless(sys.platform=='darwin','Native Mac process-exit notifications')
    def test_already_exited_parent_stops_service_immediately(self):
        parent=subprocess.Popen([sys.executable,'-c','pass'])
        parent.wait(timeout=3)
        self._parent_exit_check(parent,True)

    def _parent_exit_check(self,parent,already_exited):
        folder=Path(self.folder.name)/'process-profile'
        process=subprocess.Popen([sys.executable,str(ROOT/'companion/desktop.py'),'--offline','--parent-pid',str(parent.pid)],env=dict(os.environ,CROWPANEL_APP_DATA=str(folder)),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            if not already_exited:
                deadline=time.monotonic()+5
                while not (folder/'runtime.json').exists():
                    if process.poll() is not None or time.monotonic()>deadline:
                        self.fail('Companion did not start')
                    time.sleep(.02)
                parent.terminate()
                parent.wait(timeout=3)
            _,error=process.communicate(timeout=3)
            self.assertEqual(process.returncode,0,error.decode())
            self.assertFalse((folder/'runtime.json').exists())
        finally:
            if parent.poll() is None:
                parent.terminate();parent.wait(timeout=3)
            if process.poll() is None:
                process.terminate();process.communicate(timeout=5)

    def test_absent_bluetooth_target_uses_short_filtered_lookup(self):
        calls=[]
        class Scanner:
            @staticmethod
            async def find_device_by_address(address,**kwargs):
                calls.append((address,kwargs))
                return None
        class Client:
            def __init__(self,*args,**kwargs):
                raise AssertionError('Must not connect if target is absent')
        transport=Transport()
        try:
            with patch.dict(sys.modules,bleak=types.SimpleNamespace(BleakScanner=Scanner,BleakClient=Client)):
                with self.assertRaises(RuntimeError):
                    transport.connect('ble','saved',automatic=True)
            self.assertEqual(calls,[('saved',{'timeout':4,'service_uuids':[SERVICE]})])
            self.assertEqual(transport.label,'Disconnected')
        finally:
            transport.close()

if __name__=='__main__':
    unittest.main()
