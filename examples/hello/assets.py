#!/usr/bin/env python3
"""examples/hello's flash: a 32x32 ball (four 16x16 tiles, pens 1-15), its 16 colours, and a 0.2 s beep.
    assets.py <out.bin> <out.h>"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sdk', 'tools'))
from cps3asset import Flash  # noqa: E402

TILES_AT, COLOURS_AT, BEEP_AT = 0x10000, 0x20000, 0x30000
BEEP_RATE = 8000


def ball():
    """four tiles, column by column (cps3v_sprite's order): (0,0), (0,1), (1,0), (1,1)"""
    px = [[0] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            d = math.hypot(x - 15.5, y - 15.5)
            if d < 15:
                px[y][x] = 1 + min(14, int(d))
    out = []
    for tx in range(2):
        for ty in range(2):
            for y in range(16):
                out += px[16 * ty + y][16 * tx:16 * tx + 16]
    return out


def main():
    f = Flash()
    f.tiles(TILES_AT, ball())
    cols = [0] + [((31 - 2 * k) << 10) | ((10 + k) << 5) | 31 for k in range(15)]    # pen 0 transparent
    f.colours(COLOURS_AT, cols)
    n = BEEP_RATE // 5
    f.sample(BEEP_AT, [int(90 * math.sin(2 * math.pi * 660 * i / BEEP_RATE) * (1 - i / n)) for i in range(n)])
    f.write(sys.argv[1])
    open(sys.argv[2], 'w').write(
        f'#define TILES_AT 0x{TILES_AT:x}u\n#define COLOURS_AT 0x{COLOURS_AT:x}u\n#define BEEP_AT 0x{BEEP_AT:x}u\n'
        f'#define BEEP_LEN {n}u\n#define BEEP_RATE {BEEP_RATE}u\n')


if __name__ == '__main__':
    main()
