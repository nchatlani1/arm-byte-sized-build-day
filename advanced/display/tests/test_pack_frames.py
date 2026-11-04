"""Frame generation must work in a clean source copy without computer helpers."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class PackingTests(unittest.TestCase):
    def test_extension_matrix_uses_named_ids_without_empty_screens(self):
        for calendar, spotify in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(calendar=calendar,spotify=spotify), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                for name in ('templates','tools','firmware/lib/ElecrowEPD'):
                    shutil.copytree(ROOT/name,root/name)
                config=json.loads((ROOT/'device.json').read_text())
                config['extensions']={'calendar':calendar,'spotify':spotify}
                (root/'device.json').write_text(json.dumps(config))
                result=subprocess.run([sys.executable,'-I','-B',str(root/'tools/pack_frames.py')],cwd=root,env=dict(os.environ,CROWPANEL_RESOURCE_ROOT=str(root)),capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                frames=(root/'.generated/frames.h').read_text()
                names=['morning_briefing']+(['now_playing'] if spotify else [])+(['calendar'] if calendar else [])
                self.assertIn('kScreenCount = '+str(len(names))+';',frames)
                self.assertIn('kNames[] = {'+','.join(json.dumps(n) for n in names)+'};',frames)
                self.assertIn('kCalendarScreen = '+str(names.index('calendar') if calendar else -1)+';',frames)
                self.assertIn('kNowPlayingScreen = '+str(names.index('now_playing') if spotify else -1)+';',frames)
                self.assertEqual(len(list((root/'.generated').iterdir())),1)

    def test_clean_inputs_regenerate_frames_without_server_or_helper_packages(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copytree(ROOT/'templates',root/'templates')
            shutil.copytree(ROOT/'firmware/lib/ElecrowEPD',root/'firmware/lib/ElecrowEPD')
            shutil.copytree(ROOT/'tools',root/'tools')
            shutil.copy2(ROOT/'device.json',root/'device.json')
            environment=dict(os.environ,CROWPANEL_RESOURCE_ROOT=str(root))
            result=subprocess.run([sys.executable,'-I','-B',str(root/'tools/pack_frames.py')],cwd=root,env=environment,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            frames=(root/'.generated/frames.h').read_text()
            self.assertIn('kScreenCount = 3;',frames)
            self.assertNotIn('kQuoteCount',frames)
            self.assertIn('kFrames[][4000]',frames)
            self.assertFalse((root/'companion').exists())
            self.assertEqual(set(p.name for p in (root/'.generated').iterdir()),{'frames.h'})

if __name__=='__main__':unittest.main()
