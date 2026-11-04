Import('env')
import runpy
from pathlib import Path
root = Path(env['PROJECT_DIR'])
if env['PIOENV'] != 'workshop_demo' and (root / '.env').exists():
    exporter = runpy.run_path(str(root / 'tools/export_config.py'))
    try:
        live = exporter['export_config'](root)
    except (ValueError, OSError):
        raise RuntimeError('Local Wi-Fi configuration is invalid; check .env. Values are not printed.') from None
    print('Applied local .env configuration (credentials hidden); live mode: ' + ('on' if live else 'off'))
# Morning Briefing uses direct Wi-Fi only. Do not compile the Bluetooth library.
env.GetProjectConfig().set('env:' + env['PIOENV'], 'lib_ignore',
                          '\n'.join(env.GetProjectOption('lib_ignore', []) + ['ESP32 BLE Arduino']))
runpy.run_path(str(root / 'tools/pack_frames.py'), run_name='__main__')
env.Append(CPPPATH=[str(root / '.generated')])
runpy.run_path(str(root / 'tools/make_ca_bundle.py'), run_name='__main__')
# Close browser serial and monitors before uploading this Morning Briefing firmware.
