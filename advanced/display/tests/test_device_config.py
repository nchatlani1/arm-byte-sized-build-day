"""Public edits and ZIP resolution must be correct before firmware is built."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from device_config import load, apply, resolve_location
from render import content, render, ascii_text


class DeviceConfigTests(unittest.TestCase):
    def config(self):
        value = json.loads((ROOT / 'device.json').read_text())
        value.pop('extensions', None)
        return value

    def read(self, value):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'device.json'
            path.write_text(json.dumps(value))
            return load(path)

    def test_default_and_units_build_without_network(self):
        value = self.config()
        value['weather']['temperature_unit'] = 'C'
        with patch('device_config.urlopen', side_effect=AssertionError('Offline build used network')):
            config = self.read(value)
            base = content('morning_briefing')
            data = apply('morning_briefing', base, config)
            self.assertEqual(config['weather']['city'], 'San Diego')
            self.assertEqual(config['weather']['zip_code'], '92128')
            self.assertEqual(config['weather']['latitude'], 33.0067)
            self.assertEqual(config['weather']['longitude'], -117.069)
            self.assertEqual(data['temperature_f'], 22)

    def test_ticker_change_hides_unrelated_sample_price_and_changes_pixels(self):
        value = self.config()
        value.update(stock_symbol='MSFT', footer='My team')
        original = content('morning_briefing')
        before = copy.deepcopy(original)
        data = apply('morning_briefing', original, self.read(value))
        self.assertIsNone(data['price'])
        self.assertEqual(data['symbol'], 'MSFT')
        self.assertNotEqual(render('morning_briefing', data), render('morning_briefing', original))
        self.assertEqual(original, before)

    def test_zip_lookup_preserves_leading_zero_and_cache_works_offline(self):
        response = {'post code': '02108', 'country abbreviation': 'US', 'places': [
            {'place name': 'Boston', 'latitude': '42.3571', 'longitude': '-71.0655'}]}
        with tempfile.TemporaryDirectory() as folder:
            with patch('device_config.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as lookup:
                location = resolve_location('02108', folder)
                self.assertEqual(lookup.call_args[0][0].full_url, 'https://api.zippopotam.us/us/02108')
                self.assertEqual(location['city'], 'Boston')
            with patch('device_config.urlopen', side_effect=URLError('offline')):
                self.assertEqual(resolve_location('02108', folder), location)

    def test_wrong_zip_response_and_poisoned_cache_never_select_wrong_city(self):
        response = {'post code': '90210', 'country abbreviation': 'US', 'places': [
            {'place name': 'Wrong city', 'latitude': '34', 'longitude': '-118'}]}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'zip-02108.json').write_text(json.dumps(
                {'zip_code': '90210', 'city': 'Wrong city', 'latitude': 34, 'longitude': -118}))
            with patch('device_config.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(ValueError):
                    resolve_location('02108', folder)
            with patch('device_config.urlopen', side_effect=URLError('offline')):
                with self.assertRaises(ValueError):
                    resolve_location('02108', folder)

    def test_not_found_and_bad_config_fail_before_build(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('device_config.urlopen', side_effect=HTTPError('https://example.invalid', 404, '', {}, None)):
                with self.assertRaisesRegex(ValueError, 'not found'):
                    resolve_location('00000', folder)
        for zip_code in ('9210', '123456', '../ab', 2108, True):
            value = self.config()
            value['weather']['zip_code'] = zip_code
            with self.assertRaises(ValueError):
                self.read(value)
        for key, value in [('stock_symbol', '../ARM'), ('title', 'x' * 30), ('footer', 'x' * 39)]:
            config = self.config()
            config[key] = value
            with self.assertRaises(ValueError):
                self.read(config)

    def test_optional_extensions_are_strict_and_default_off(self):
        self.assertEqual(self.read(self.config())['extensions'], {'calendar': False, 'spotify': False})
        for value in (None, [], {'calendar': 1}, {'spotify': 'true'}, {'unknown': True}):
            config = self.config()
            config['extensions'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read(config)
        config = self.config()
        config['extensions'] = {'calendar': True}
        self.assertEqual(self.read(config)['extensions'], {'calendar': True, 'spotify': False})

    def test_display_normalizes_supported_punctuation_and_latin_accents(self):
        self.assertEqual(ascii_text('Café — build…'), 'Cafe - build...')


if __name__ == '__main__':
    unittest.main()
