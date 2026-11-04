import contextlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from export_config import export_config, read_wifi_env


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for folder in ('.local','firmware/include'):
            (self.root/folder).mkdir(parents=True)
    def save_env(self, text):
        (self.root/'.env').write_text(text)
    def config(self):
        return (self.root/'firmware/include/secrets.h').read_text()
    def macro(self, name):
        return json.loads(re.search(r'^#define '+name+r' (.+)$',self.config(),re.M)[1])
    def test_env_only_requires_no_setup_json_and_keeps_password_literal(self):
        password=r'p a$$#word\with"quotes'
        self.save_env('HOME_WIFI_SSID="My home"\nHOME_WIFI_PASSWORD="'+password+'"\n')
        output=io.StringIO()
        with contextlib.redirect_stdout(output):self.assertTrue(export_config(self.root))
        self.assertEqual(self.macro('HOME_WIFI_SSID'),'My home')
        self.assertEqual(self.macro('HOME_WIFI_PASSWORD'),password)
        self.assertNotIn(password,output.getvalue())
        self.assertFalse((self.root/'.local/settings.json').exists())
    def test_office_password_is_exported_literally_without_logging(self):
        self.save_env('OFFICE_WIFI_SSID="Office"\nOFFICE_WIFI_PASSWORD="office $ # password"\n')
        output=io.StringIO()
        with contextlib.redirect_stdout(output):export_config(self.root)
        self.assertEqual(self.macro('OFFICE_WIFI_SSID'),'Office')
        self.assertEqual(self.macro('OFFICE_WIFI_PASSWORD'),'office $ # password')
        self.assertNotIn('office $ # password',output.getvalue())

    def test_old_account_state_is_ignored_and_not_exported(self):
        (self.root/'.local/settings.json').write_text(json.dumps({'spotify_client_id':'test-client'}))
        (self.root/'.local/spotify-token.json').write_text(json.dumps({'refresh_token':'test-token'}))
        self.save_env('HOME_WIFI_SSID="Home"\n')
        export_config(self.root)
        self.assertNotIn('SPOTIFY',self.config())
        self.assertNotIn('test-token',self.config())
        self.assertNotIn('test-client',self.config())
    def test_invalid_env_stops_export_without_overwriting_header_or_echoing_values(self):
        self.save_env('HOME_WIFI_SSID="Home"\n');export_config(self.root);before=self.config()
        for text in ('HOME_WIFI_PASSWORD="secret\n','HOME_WIFI_USERNAME=secret\n','WORKSHOP_LIVE=secret\n',
                     'HOME_WIFI_SSID=one\nHOME_WIFI_SSID=secret\n'):
            with self.subTest(text=text):
                self.save_env(text)
                with self.assertRaises(ValueError) as error:export_config(self.root)
                self.assertNotIn('secret',str(error.exception))
                self.assertEqual(self.config(),before)
    def test_offline_flag_manual_override_and_stable_header(self):
        self.save_env('WORKSHOP_LIVE=0\n')
        self.assertFalse(export_config(self.root))
        self.assertEqual(self.macro('WORKSHOP_LIVE'),0)
        stamp=(self.root/'firmware/include/secrets.h').stat().st_mtime_ns
        export_config(self.root)
        self.assertEqual((self.root/'firmware/include/secrets.h').stat().st_mtime_ns,stamp)
        self.assertTrue(export_config(self.root,live=True))
        self.assertEqual(self.macro('WORKSHOP_LIVE'),1)


if __name__=='__main__':unittest.main()
