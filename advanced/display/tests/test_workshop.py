"""The single sample and drawing primitives must fit the physical frame."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from render import NAMES, FRAME_BYTES, Canvas, content, render, png


class RenderTests(unittest.TestCase):
    def test_registered_screen_fits_frame_and_padding_stays_white(self):
        self.assertEqual(NAMES, ('morning_briefing', 'now_playing', 'calendar'))
        frame = render('morning_briefing')
        self.assertEqual(len(frame), FRAME_BYTES)
        self.assertNotEqual(frame, b'\xff' * FRAME_BYTES)
        for x in range(250):
            self.assertEqual(frame[x * 16 + 15] & 0x3f, 0x3f)
        self.assertTrue(png(frame).startswith(b'\x89PNG\r\n\x1a\n'))

    def test_clipped_text_and_long_unicode_do_not_overflow(self):
        canvas = Canvas()
        canvas.text('x' * 1000, -20, 118, 16)
        self.assertEqual(len(canvas.frame), FRAME_BYTES)
        data = content('morning_briefing')
        data['affirmation'] = 'A long title ' + ('🎵' * 100)
        self.assertEqual(len(render('morning_briefing', data)), FRAME_BYTES)

    def test_unknown_screen_and_nonobject_data_rejected(self):
        with self.assertRaises(ValueError):
            render('../settings')
        with self.assertRaises(ValueError):
            render('morning_briefing', [])


if __name__ == '__main__':
    unittest.main()
