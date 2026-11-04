"""Exercise the release boundary with isolated, credential-free fixtures."""
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release'))
from package_workshop import package,read_manifest

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        self.manifest=self.root/'files.txt'
        self.manifest.write_text('README.md\nfirmware/src/main.cpp\n')
        (self.source/'firmware/src').mkdir(parents=True)
        (self.source/'README.md').write_text('Sample')
        (self.source/'firmware/src/main.cpp').write_text('void setup() {}')
    def build(self):
        return package(self.source,self.root/'out','test-r1',self.manifest)
    def test_exact_members_and_identical_source_bytes_with_local_build_output(self):
        for name in ('.pio/build/firmware.bin','.generated/frames.h','.local/settings.json'):
            p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('local excluded output')
        archive=self.build()
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.namelist(),['CrowPanel-Workshop/README.md','CrowPanel-Workshop/firmware/src/main.cpp'])
            self.assertIsNone(z.testzip())
            for name in read_manifest(self.manifest):
                self.assertEqual(z.read('CrowPanel-Workshop/'+name),(self.source/name).read_bytes())
        before=archive.read_bytes();self.assertEqual(before,self.build().read_bytes())
    def test_missing_required_source_fails(self):
        (self.source/'firmware/src/main.cpp').unlink()
        with self.assertRaises(ValueError):self.build()
    def test_helpers_preview_releases_and_credentials_are_rejected(self):
        for name in ('companion/app_core.py','tools/build_companion.py','preview/example.png','release/package.py','.env','firmware/include/secrets.h'):
            with self.subTest(name=name):
                p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('forbidden extra')
                with self.assertRaises(ValueError):self.build()
                p.unlink()
    def test_traversal_duplicates_and_secret_manifest_entries_fail(self):
        for text in ('../outside\n','README.md\nREADME.md\n','.env\n','firmware/include/secrets.h\n','/absolute\n'):
            self.manifest.write_text(text)
            with self.assertRaises(ValueError):read_manifest(self.manifest)
    def test_symlinked_source_and_ancestor_fail(self):
        outside=self.root/'outside';outside.mkdir();(outside/'link.md').write_text('no')
        (self.source/'linked').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.build()
    def test_output_inside_source_fails(self):
        with self.assertRaises(ValueError):package(self.source,self.source/'dist','test',self.manifest)
    def test_repository_separates_starter_advanced_and_companion_apps(self):
        names=set(read_manifest(ROOT/'release/repository-files.txt'))
        self.assertIn('starter/firmware/src/main.cpp',names)
        self.assertEqual({n for n in names if n.startswith('starter/templates/') and n.endswith('content.json')},
                         {'starter/templates/morning_briefing/content.json'})
        self.assertFalse(any('companion' in n or 'integration_data' in n for n in names if n.startswith('starter/')))
        self.assertIn('advanced/display/firmware/include/companion_link.h',names)
        self.assertIn('advanced/companion-apps/companion/app_transport.py',names)
        self.assertIn('.github/workflows/windows-companion.yml',names)
        with self.assertRaises(ValueError):
            self.manifest.write_text('starter/.vscode/launch.json\n')
            read_manifest(self.manifest)


if __name__=='__main__':unittest.main()
