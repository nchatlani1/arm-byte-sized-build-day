#!/usr/bin/env python3
"""Build on the target OS. The distribution contains no project credentials."""
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import os
import platform
import importlib.metadata
import json
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/companion'
WORK = ROOT / 'build/companion'
NOTICE_FALLBACKS = {
    ('proxy-tools', '0.1.0'): 'proxy_tools-0.1.0-LICENSE.txt',
    ('pyserial', '3.5'): 'pyserial-3.5-LICENSE.txt',
    ('pyobjc-core', '11.1'): 'pyobjc-core-11.1-License.txt',
    ('pyobjc-framework-libdispatch', '11.1'): 'pyobjc-libdispatch-11.1-License.txt',
}


def notice_fallback(name, version):
    # Match the exact upstream version; a new dependency must bring its own notice.
    filename = NOTICE_FALLBACKS.get((name.lower().replace('_', '-'), version))
    return ROOT / 'licenses' / filename if filename else None


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)

def third_party_notices():
    """Preserve installed distribution license texts alongside the pilot binary."""
    folder=WORK/'third-party-notices'
    if folder.exists():shutil.rmtree(folder)
    folder.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for dist in sorted(importlib.metadata.distributions(),key=lambda d:d.metadata['Name'].lower()):
        name=dist.metadata['Name'];copied=[]
        for item in dist.files or []:
            if not any(word in Path(item).name.lower() for word in ('license','copying','notice','copyright')):
                continue
            source=Path(dist.locate_file(item))
            if not source.is_file():continue
            destination=folder/name/str(len(copied))/Path(item).name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination);copied.append(str(destination.relative_to(folder)))
        if not copied:
            fallback = notice_fallback(name, dist.version)
            if fallback and fallback.is_file():
                destination = folder / name / 'upstream' / fallback.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fallback, destination)
                copied.append(str(destination.relative_to(folder)))
            else:
                raise RuntimeError(f'Missing license text for {name} {dist.version}; add an exact-version notice before distribution.')
        inventory.append(dict(name=name,version=dist.version,license=dist.metadata.get('License-Expression') or dist.metadata.get('License'),files=copied))
    for candidate in (Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt'):
        if candidate.is_file():shutil.copy2(candidate,folder/'Python-LICENSE.txt');break
    else:raise RuntimeError('Python runtime license text was not found; add it before distributing a bundled app.')
    (folder/'distributions.json').write_text(json.dumps(inventory,indent=2)+'\n')
    shutil.copy2(ROOT/'guides/LICENSES.md',folder/'SOURCE-NOTICES.md')
    return folder

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    data = [('companion/ui','companion/ui'),(str(third_party_notices()),'third-party-notices'),('release/release.json','release.json')]
    native = WORK / 'native'
    if sys.platform == 'darwin':
        helper = native / 'CrowPanel Calendar.app'
        exe = helper / 'Contents/MacOS/CrowPanelCalendar'
        exe.parent.mkdir(parents=True, exist_ok=True)
        run('xcrun', 'swiftc', '-target', platform.machine()+'-apple-macosx14.0', ROOT/'tools/mac_calendar_reader.swift', '-o', exe, '-framework','AppKit','-framework','EventKit')
        info = {'CFBundleExecutable':'CrowPanelCalendar','CFBundleIdentifier':'local.crowpanel.calendar','CFBundleName':'CrowPanel Calendar','CFBundlePackageType':'APPL','CFBundleVersion':'1','LSUIElement':True,'NSCalendarsUsageDescription':'Read your selected work calendar for your CrowPanel. Events are never changed.','NSCalendarsFullAccessUsageDescription':'Read your next meeting title and time for your CrowPanel. Events are never changed.'}
        (helper/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        run('codesign','--force','--sign','-',helper)
        data.append((str(helper), 'native/CrowPanel Calendar.app'))
    args = [sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','CrowPanelBackend','--distpath',str(OUT/'service'),'--workpath',str(WORK/'pyinstaller'),'--specpath',str(WORK),'--paths',str(ROOT/'tools'),'--paths',str(ROOT/'companion'),'--collect-submodules','bleak','--collect-submodules','keyring.backends']
    for source,destination in data:
        args += ['--add-data',str(ROOT/source)+os.pathsep+destination]
    if sys.platform == 'win32':
        args += ['--windowed','--collect-all','webview','--hidden-import','win32com.client','--hidden-import','pythoncom']
    args.append(str(ROOT/'companion/desktop.py'))
    run(*args)
    if sys.platform == 'darwin':
        app = OUT / 'CrowPanel Companion.app'
        contents = app/'Contents'
        (contents/'MacOS').mkdir(parents=True,exist_ok=True)
        resources = contents/'Resources'
        resources.mkdir(exist_ok=True)
        backend = resources/'backend'
        if backend.exists():shutil.rmtree(backend)
        shutil.copytree(OUT/'service/CrowPanelBackend',backend,symlinks=True)
        run('xcrun','swiftc','-target',platform.machine()+'-apple-macosx14.0',ROOT/'companion/native/Companion.swift','-o',contents/'MacOS/CrowPanelCompanion','-framework','AppKit','-framework','WebKit','-framework','ServiceManagement')
        info = {'CFBundleExecutable':'CrowPanelCompanion','CFBundleIdentifier':'local.crowpanel.companion','CFBundleName':'CrowPanel Companion','CFBundleDisplayName':'CrowPanel Companion','CFBundlePackageType':'APPL','CFBundleVersion':'5','CFBundleShortVersionString':'0.3.2','LSUIElement':True,'LSMinimumSystemVersion':'14.0','NSHighResolutionCapable':True,'NSBluetoothAlwaysUsageDescription':'Connect to your CrowPanel to send the display content you choose.','NSBluetoothPeripheralUsageDescription':'Connect to your CrowPanel display.','NSCalendarsFullAccessUsageDescription':'Read your next work meeting for your CrowPanel display. Events are never changed.'}
        (contents/'Info.plist').write_bytes(plistlib.dumps(info))
        run('codesign','--force','--deep','--sign','-',app)
        archive = OUT/('CrowPanel-Companion-macOS-'+platform.machine()+'.zip')
        if archive.exists():archive.unlink()
        run('ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive)
        print('Built local Mac pilot:',app)
        print('Ad-hoc signed, not Developer ID signed or notarized. Pilot before workshop distribution.')
    elif sys.platform == 'win32':
        destination = OUT/'CrowPanel Companion Windows'
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(OUT/'service/CrowPanelBackend', destination)
        shutil.make_archive(str(OUT/'CrowPanel-Companion-Windows'), 'zip', OUT, destination.name)
        print('Built Windows app. This build requires target-machine validation and publisher signing.')
    else:
        print('Built service. Native workshop packages require macOS or Windows.')

if __name__=='__main__':main()
