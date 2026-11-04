"""Public screen settings. Resolve a new US ZIP once, then cache its coordinates.

92128 is bundled so clean/default builds work offline. Location lookup is a
build-time convenience; the ESP32 needs only coordinates and its own Wi-Fi.
"""
import copy
import json
import math
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_LOCATION = {'zip_code': '92128', 'city': 'San Diego',
                    'latitude': 33.0067, 'longitude': -117.069}


def valid_location(value, zip_code):
    if not isinstance(value, dict) or value.get('zip_code') != zip_code:
        return False
    if not isinstance(value.get('city'), str) or not 1 <= len(value['city']) <= 80:
        return False
    return all(type(value.get(key)) in (int, float) and math.isfinite(value[key])
               and -limit <= value[key] <= limit
               for key, limit in (('latitude', 90), ('longitude', 180)))


def resolve_location(zip_code, cache_dir):
    if not isinstance(zip_code, str) or not re.fullmatch(r'[0-9]{5}', zip_code):
        raise ValueError('weather.zip_code must be a five-digit US ZIP string, such as "02108"')
    if zip_code == DEFAULT_LOCATION['zip_code']:
        return dict(DEFAULT_LOCATION)
    cache = Path(cache_dir) / ('zip-' + zip_code + '.json')
    if cache.exists():
        try:
            saved = json.loads(cache.read_text())
            if valid_location(saved, zip_code):
                return saved
        except (ValueError, OSError):
            pass
    print('Resolving a new US ZIP with Zippopotam.us; later builds use the local cache.')
    request = Request('https://api.zippopotam.us/us/' + zip_code,
                      headers={'Accept': 'application/json', 'User-Agent': 'CrowPanelWorkshop/1.0'})
    try:
        # PlatformIO's bundled Python may not have system roots. certifi is
        # already installed by PlatformIO; keep certificate verification enabled.
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        with urlopen(request, timeout=12, context=context) as response:
            body = response.read(65537)
        if len(body) > 65536:
            raise ValueError('Location response is too large')
        data = json.loads(body)
        if not isinstance(data, dict) or data.get('post code') != zip_code or data.get('country abbreviation') != 'US':
            raise ValueError('Location response did not match the requested US ZIP')
        place = data['places'][0]
        location = dict(zip_code=zip_code, city=place['place name'],
                        latitude=float(place['latitude']), longitude=float(place['longitude']))
        if not valid_location(location, zip_code):
            raise ValueError('Invalid location response')
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError('US ZIP was not found. Check weather.zip_code in device.json.') from None
        raise ValueError('ZIP lookup failed. Check internet access or use bundled ZIP 92128 offline.') from None
    except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
        raise ValueError('ZIP lookup failed. Check the ZIP and internet access, or use bundled ZIP 92128 offline.') from None
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(location, indent=2) + '\n')
    return location


def load(path):
    path = Path(path)
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or set(raw) != {'stock_symbol', 'weather', 'title', 'footer'}:
        raise ValueError('Use only stock_symbol, weather, title and footer in starter/device.json')
    symbol = raw['stock_symbol']
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,8}', symbol):
        raise ValueError('Invalid stock_symbol; use a USD ticker such as ARM or MSFT')
    weather = raw['weather']
    if not isinstance(weather, dict) or set(weather) != {'zip_code', 'temperature_unit'}:
        raise ValueError('weather needs zip_code and temperature_unit')
    if weather['temperature_unit'] not in ('C', 'F'):
        raise ValueError('Choose C or F in device.json')
    for key, limit in (('title', 29), ('footer', 38)):
        if not isinstance(raw[key], str) or len(raw[key]) > limit:
            raise ValueError('Invalid ' + key)
    result = copy.deepcopy(raw)
    result['weather'].update(resolve_location(weather['zip_code'], path.parent / '.generated'))
    return result


def apply(name, base, config):
    data = copy.deepcopy(base)
    if name == 'morning_briefing':
        weather = config['weather']
        data.update(title=config['title'], symbol=config['stock_symbol'], location=weather['city'],
                    temperature_unit=weather['temperature_unit'], affirmation=config['footer'])
        if config['stock_symbol'] != base.get('symbol'):
            data.update(price=None, quote_as_of='SAMPLE ONLY')
        if weather['temperature_unit'] == 'C' and isinstance(base.get('temperature_f'), (int, float)):
            data['temperature_f'] = round((base['temperature_f'] - 32) * 5 / 9)
    return data
