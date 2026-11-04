Import('env')
import runpy
from pathlib import Path
root = Path(env['PROJECT_DIR'])
if env['PIOENV'] != 'workshop_demo':
    exporter = runpy.run_path(str(root / 'tools/export_config.py'))
    try:
        live = exporter['export_config'](root)
    except ValueError as error:
        raise RuntimeError(f'Wi-Fi configuration failed: {error}. Values are not printed.') from None
    except OSError:
        raise RuntimeError('Cannot read .env or write the local Wi-Fi header; check permissions. Values are not printed.') from None
    print('Applied local .env configuration (credentials hidden); live mode: ' + ('on' if live else 'off'))
# Exclude the optional radio library before dependency discovery, not just linking.
settings = runpy.run_path(str(root / 'tools/device_config.py'))['load'](root / 'device.json')
if not any(settings['extensions'].values()):
    env.GetProjectConfig().set('env:' + env['PIOENV'], 'lib_ignore',
                              '\n'.join(env.GetProjectOption('lib_ignore', []) + ['ESP32 BLE Arduino']))
runpy.run_path(str(root / 'tools/pack_frames.py'), run_name='__main__')
env.Append(CPPPATH=[str(root / '.generated')])
runpy.run_path(str(root / 'tools/make_ca_bundle.py'), run_name='__main__')
# Before uploading, close browser serial, monitors and optional companion links.
# The default starter runs independently. Explicitly enabled calendar/music
# extensions receive account data from the optional companion.
