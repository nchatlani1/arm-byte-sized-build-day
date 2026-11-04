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
            self.assertIn('kMorningBriefingFrame[4000]',frames)
            self.assertNotIn('WORKSHOP_DATA_BRIDGE',frames)
            self.assertNotIn('kQuoteCount',frames)
            self.assertNotIn('kCalendarScreen',frames)
            self.assertFalse((root/'companion').exists())
            self.assertEqual(set(p.name for p in (root/'.generated').iterdir()),{'frames.h'})

if __name__=='__main__':unittest.main()
