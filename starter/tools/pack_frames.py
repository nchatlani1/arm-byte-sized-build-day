"""Build the Morning Briefing sample and public settings into firmware."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import ROOT, render
from device_config import load


def pack():
    config = load(ROOT / 'device.json')
    weather = config['weather']
    # This starter owns one screen. No account receiver, Bluetooth or screen registry.
    lines = ['#pragma once', '#include <Arduino.h>',
             'constexpr char kStockSymbol[] = ' + json.dumps(config['stock_symbol']) + ';',
             'constexpr char kWeatherLatitude[] = ' + json.dumps(str(weather['latitude'])) + ';',
             'constexpr char kWeatherLongitude[] = ' + json.dumps(str(weather['longitude'])) + ';',
             'constexpr char kWeatherUnit[] = ' + json.dumps(weather['temperature_unit']) + ';',
             'const uint8_t kMorningBriefingFrame[4000] PROGMEM = {',
             ','.join(str(b) for b in render('morning_briefing')), '};\n']
    folder = ROOT / '.generated'
    folder.mkdir(exist_ok=True)
    target = folder / 'frames.h'
    result = '\n'.join(lines)
    if not target.exists() or target.read_text() != result:
        target.write_text(result)
    print('Packed Morning Briefing; weather location: ' + weather['city'] + '.')


if __name__ == '__main__':
    pack()
