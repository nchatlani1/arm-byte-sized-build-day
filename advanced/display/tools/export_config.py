"""Export only local Wi-Fi settings. Public screen settings live in device.json."""
import argparse
import json
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
WIFI_KEYS={'HOME_WIFI_SSID':'home_wifi_ssid','HOME_WIFI_PASSWORD':'home_wifi_password',
           'OFFICE_WIFI_SSID':'office_wifi_ssid','OFFICE_WIFI_PASSWORD':'office_wifi_password'}


def read_wifi_env(path):
    """Read literal values: no shell execution, expansion, or escape processing."""
    values={}
    if not path.exists():return values
    for number,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'(?:export\s+)?([A-Z_]+)\s*=(.*)',line)
        if not match or match[1] not in {*WIFI_KEYS,'WORKSHOP_LIVE'}:
            raise ValueError(f'.env line {number}: use a supported NAME=value setting')
        name,value=match[1],match[2].strip()
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:
                raise ValueError(f'.env line {number}: missing closing quote')
            value=value[1:-1]
        if '\x00' in value:raise ValueError(f'.env line {number}: invalid character')
        if name in values:raise ValueError(f'.env line {number}: duplicate setting')
        values[name]=value
    if values.get('WORKSHOP_LIVE','1') not in ('0','1'):
        raise ValueError('.env WORKSHOP_LIVE must be 0 or 1')
    return values



def export_config(root=ROOT, live=None):
    root = Path(root)
    if not (root / '.env').exists():
        raise ValueError('Missing .env; restore the supplied .env from the repository or source ZIP')
    values = read_wifi_env(root / '.env')
    if live is None:
        live = values.get('WORKSHOP_LIVE', '1') == '1'
    lines = ['#pragma once', '// Generated locally; contains Wi-Fi credentials. Never share.',
             f'#define WORKSHOP_LIVE {int(live)}']
    for name in WIFI_KEYS:
        lines.append('#define ' + name + ' ' + json.dumps(values.get(name, ''), ensure_ascii=False))
    out = root / 'firmware/include/secrets.h'
    result = '\n'.join(lines) + '\n'
    if not out.exists() or out.read_text() != result:
        out.touch(mode=0o600, exist_ok=True)
        out.chmod(0o600)
        out.write_text(result)
    return bool(live)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', default=None,
                        help='Enable direct Wi-Fi after upload; otherwise respect .env')
    args = parser.parse_args()
    try:
        live = export_config(live=args.live)
    except ValueError as error:
        raise SystemExit(f'Configuration export failed: {error}. Values are not printed.') from None
    except OSError:
        raise SystemExit('Configuration export failed. Check .env and header permissions; values are not printed.') from None
    print('Exported private Wi-Fi header. Live mode: ' + ('on' if live else 'off'))
