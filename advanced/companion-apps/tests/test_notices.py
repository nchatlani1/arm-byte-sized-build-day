"""Prevent version drift from silently dropping packaged dependency notices."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_companion import notice_fallback

class NoticeTests(unittest.TestCase):
    def test_exact_upstream_versions_have_original_notice_texts(self):
        for name, version in [("pyserial", "3.5"), ("pyobjc-core", "11.1"), ("pyobjc-framework-libdispatch", "11.1")]:
            notice = notice_fallback(name, version)
            self.assertIsNotNone(notice)
            self.assertIn("Copyright", notice.read_text())
    def test_new_or_unknown_versions_cannot_reuse_an_old_notice(self):
        self.assertIsNone(notice_fallback("pyserial", "99.0"))
        self.assertIsNone(notice_fallback("unknown", "3.5"))

if __name__ == "__main__":
    unittest.main()
