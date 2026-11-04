"""Compile registered samples and public settings into flash-resident frames."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import ROOT, screen_names, render
from device_config import load


def pack():
    config = load(ROOT / 'device.json')
    names = screen_names(config)
    if not 1 <= len(names) <= 8 or not all(re.fullmatch(r'[a-z][a-z0-9_]*', n) for n in names):
        raise ValueError('Register one to eight screens with simple lowercase names')
    if names[0] != 'morning_briefing':
        raise ValueError('Keep morning_briefing first; its direct feed owns screen zero')
    weather = config['weather']
    frames = [render(name) for name in names]
    # Compile account radios only when requested. Named IDs avoid fixed screen positions.
    lines = ['#pragma once', '#include <Arduino.h>',
             f'#define WORKSHOP_CALENDAR {int(config["extensions"]["calendar"])}',
             f'#define WORKSHOP_SPOTIFY {int(config["extensions"]["spotify"])}',
             '#define WORKSHOP_DATA_BRIDGE (WORKSHOP_CALENDAR || WORKSHOP_SPOTIFY)',
             *[f'constexpr int8_t {symbol} = {names.index(name) if name in names else -1};'
               for name, symbol in [('morning_briefing', 'kMorningBriefingScreen'),
                                    ('calendar', 'kCalendarScreen'), ('now_playing', 'kNowPlayingScreen')]],
             f'constexpr uint8_t kScreenCount = {len(names)};',
             'constexpr const char* kNames[] = {' + ','.join(json.dumps(n) for n in names) + '};',
             'constexpr char kStockSymbol[] = ' + json.dumps(config['stock_symbol']) + ';',
             'constexpr char kWeatherLatitude[] = ' + json.dumps(str(weather['latitude'])) + ';',
             'constexpr char kWeatherLongitude[] = ' + json.dumps(str(weather['longitude'])) + ';',
             'constexpr char kWeatherUnit[] = ' + json.dumps(weather['temperature_unit']) + ';',
             'const uint8_t kFrames[][4000] PROGMEM = {']
    for frame in frames:
        lines.append('{' + ','.join(str(b) for b in frame) + '},')
    lines.append('};\n')
    folder = ROOT / '.generated'
    folder.mkdir(exist_ok=True)
    target = folder / 'frames.h'
    result = '\n'.join(lines)
    if not target.exists() or target.read_text() != result:
        target.write_text(result)
    print(f'Packed {len(frames)} screen(s); weather location resolved to {weather["city"]}.')


if __name__ == '__main__':
    pack()
