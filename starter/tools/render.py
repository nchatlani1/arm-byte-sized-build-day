"""One renderer for browser previews, embedded samples, and live display frames.
Only Python's standard library is needed. Coordinates are landscape 250 x 122.
"""
from pathlib import Path
import json
import os
import math
import re
import struct
import unicodedata
import zlib
from device_config import load, apply

ROOT = Path(os.environ.get('CROWPANEL_RESOURCE_ROOT', Path(__file__).resolve().parents[1]))
WIDTH, HEIGHT, STRIDE = 250, 122, 16
FRAME_BYTES = WIDTH * STRIDE
FONTS = {}


def stock_symbol(data):
    symbol = data.get('symbol', 'ARM')
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,8}', symbol):
        raise ValueError('Stock symbol must be 1-9 uppercase ticker characters, such as ARM or BRK-B')
    return symbol


def ascii_text(text):
    punctuation = str.maketrans({'–': '-', '—': '-', '−': '-', '‘': "'", '’': "'", '“': '"', '”': '"', '…': '...', '\u00a0': ' '})
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', str(text).translate(punctuation)) if not unicodedata.combining(c))
    return normalized.encode('ascii', 'replace').decode().replace('\n', ' ')


def load_fonts():
    if FONTS:
        return
    source = (ROOT / 'firmware/lib/ElecrowEPD/EPDfont.h').read_text(errors='replace')
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    for height, width in ((12, 6), (16, 8), (24, 12), (32, 16)):
        match = re.search(r'ascii_%02d%02d\s*\[[^;]+?=\s*\{(.*?)\};' % (height, width), source, re.S)
        if not match:
            raise ValueError(f'Missing vendor font {height}')
        values = bytes(int(v, 16) for v in re.findall(r'0[xX]([0-9a-fA-F]+)', match[1]))
        size = height * ((width + 7) // 8)
        if len(values) < 95 * size:
            raise ValueError(f'Incomplete font {height}')
        FONTS[height] = (values, size)


class Canvas:
    def __init__(self):
        self.frame = bytearray(b'\xff' * FRAME_BYTES)

    def pixel(self, x, y, black=True):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            index, mask = x * STRIDE + y // 8, 0x80 >> (y % 8)
            if black:
                self.frame[index] &= ~mask & 255
            else:
                self.frame[index] |= mask

    def line(self, x, y, end_x, end_y):
        dx, dy = abs(end_x - x), -abs(end_y - y)
        sx, sy = (1 if x < end_x else -1), (1 if y < end_y else -1)
        error = dx + dy
        while True:
            self.pixel(x, y)
            if x == end_x and y == end_y:
                return
            twice = 2 * error
            if twice >= dy:
                error += dy
                x += sx
            if twice <= dx:
                error += dx
                y += sy

    def rect(self, x, y, width, height, fill=False):
        for row in range(y, y + height):
            if fill or row in (y, y + height - 1):
                self.line(x, row, x + width - 1, row)
            else:
                self.pixel(x, row)
                self.pixel(x + width - 1, row)

    def circle(self, cx, cy, radius):
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if (radius - 0.75) ** 2 <= x*x + y*y <= (radius + 0.45) ** 2:
                    self.pixel(cx+x, cy+y)

    def text(self, text, x, y, height=16, max_width=234):
        load_fonts()
        text = ascii_text(text)
        width = height // 2
        count = max_width // width
        if len(text) > count:
            text = text[:max(0, count-3)] + ('.' * min(3, count))
        data, size = FONTS[height]
        for i, ch in enumerate(text):
            index = ord(ch) - 32
            if not 0 <= index < 95:
                index = ord('?') - 32
            glyph = data[index*size:(index+1)*size]
            for row in range(height):
                for col in range(width):
                    if glyph[row*((width+7)//8)+col//8] & (1 << (col % 8)):
                        self.pixel(x+i*width+col, y+row)

    def centered(self, text, y, height=16, max_width=230):
        count = max_width // (height // 2)
        clean = ascii_text(text)
        if len(clean) > count:
            clean = clean[:count-3] + '...'
        self.text(clean, (WIDTH-len(clean)*(height//2))//2, y, height, max_width)

    def wrapped(self, text, x, y, width, height=16, lines=2):
        words = ascii_text(text).split()
        rows, current = [], ''
        limit = width // (height // 2)
        for word in words:
            candidate = (current+' '+word).strip()
            if current and len(candidate) > limit:
                rows.append(current)
                current = word
            else:
                current = candidate
        if current:
            rows.append(current)
        for i, row in enumerate(rows[:lines]):
            if i == lines-1 and len(rows) > lines:
                row = row[:max(0, limit-3)] + '...'
            self.text(row, x, y+i*(height+2), height, width)

    def header(self, text, source):
        self.text(text.upper(), 10, 7, 12, 164)
        self.text(source.upper(), 208, 7, 12, 36)
        self.line(10, 23, 239, 23)

    def footer(self, text):
        self.line(10, 101, 239, 101)
        self.centered(text, 106, 12)

    def sun(self, cx, cy):
        self.circle(cx, cy, 9)
        for i in range(8):
            angle = i * math.pi / 4
            self.line(cx+round(12*math.cos(angle)), cy+round(12*math.sin(angle)),
                      cx+round(15*math.cos(angle)), cy+round(15*math.sin(angle)))
        self.pixel(cx-3, cy-1)
        self.pixel(cx+3, cy-1)
        self.line(cx-3, cy+3, cx+3, cy+3)


def content(name):
    if name not in RENDERERS:
        raise ValueError('Unknown screen')
    sample = json.loads((ROOT / 'templates' / name / 'content.json').read_text())
    return apply(name, sample, load(ROOT / 'device.json'))


def draw_morning_briefing(c, d):
    c.header(d.get('title', 'Morning Briefing'), d.get('source', 'demo'))
    c.sun(29, 47)
    c.text(f"{d.get('temperature_f', '--')} {d.get('temperature_unit', 'F')}", 54, 29, 24, 96)
    c.text(d.get('condition', 'Weather unavailable'), 54, 56, 12, 120)
    c.text(d.get('location', 'San Diego'), 10, 77, 12, 114)
    c.line(151, 30, 151, 91)
    c.text(stock_symbol(d), 164, 30, 16, 76)
    price = d.get('price')
    c.text('--' if price is None else f'${float(price):.2f}', 160, 51, 16, 82)
    c.text(d.get('quote_as_of', 'QUOTE'), 160, 76, 12, 80)
    c.footer(d.get('affirmation', 'Build with courage.'))


# Morning Briefing is the only starter template. Advanced projects live separately.
RENDERERS = {'morning_briefing': draw_morning_briefing}
NAMES = ('morning_briefing',)


def render(name, data=None):
    if name not in RENDERERS:
        raise ValueError('Unknown screen')
    data = content(name) if data is None else data
    if not isinstance(data, dict):
        raise ValueError('Screen content must be an object')
    canvas = Canvas()
    RENDERERS[name](canvas, data)
    return bytes(canvas.frame)


def png(frame, scale=1):
    if len(frame) != FRAME_BYTES or not 1 <= scale <= 8:
        raise ValueError('Invalid frame or scale')
    rows = bytearray()
    for y in range(HEIGHT):
        row = bytearray()
        for x in range(WIDTH):
            value = 255 if frame[x*STRIDE+y//8] & (0x80 >> (y%8)) else 0
            row.extend(bytes([value])*scale)
        for _ in range(scale):
            rows.append(0)
            rows.extend(row)
    def chunk(kind, payload):
        return struct.pack('!I', len(payload))+kind+payload+struct.pack('!I', zlib.crc32(kind+payload)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('!IIBBBBB', WIDTH*scale, HEIGHT*scale, 8, 0, 0, 0, 0))+chunk(b'IDAT', zlib.compress(rows))+chunk(b'IEND', b'')



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Optional local PNG previews.')
    parser.add_argument('--output', type=Path, default=ROOT / '.generated/preview')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        (args.output / f'{name}.png').write_bytes(png(render(name), 4))
    print(f'Rendered {len(NAMES)} screen preview(s).')
