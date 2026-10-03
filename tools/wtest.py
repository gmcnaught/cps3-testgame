#!/usr/bin/env python3
"""CPS3 wide 6-bit sprite probe (src/wtest.c): which tile does the video draw in each cell of a 6-bit colour sprite?
On jtcps3 a 6-bit sprite 4 tiles wide draws tile columns 2-3 wrong (`vtest` phase 5: other pixels, not the
sprite's); 1- and 2-wide 6-bit sprites and 8-bit sprites of every size are exact. Here every tile of character RAM
0x1000-0x3fff carries its own number as a label (tools/dmap.py's: a 4 x 4 grid of 4 x 4-pixel blocks, bit 15
top-left, row by row; pens 1 / 2, so the same tile reads in a 6-bit palette (colour code x 64) and an 8-bit one
(x 256)), loaded by character DMA from the graphics flash (sdk/include/cps3dma.h). tools/wtest_check.py reads the
label in every 16x16 cell of every sprite from a MAME snapshot or a jtcps3 screenshot: the tile drawn there.

    wtest.py <out_dir>     -> <out_dir>/wtest.h, <out_dir>/wtest.bin (the graphics flash)

Sprites on a 16-pixel grid, tiles column by column from the sprite's base (sdk/include/cps3v.h cps3v_sprite), base
0x1400 + 0x40 i for sprite i. Three bands of 4 tile rows (lines 0-63, 80-143, 160-223):
  A  6-bit: 1x1, 1x2, 1x4, 2x1, 2x2, 2x4, 4x2 mirrored, 2x2 mirrored
  B  6-bit: 4x1, 4x2, 4x4, 4x4 mirrored
  C  8-bit (control): 4x1, 4x2, 4x4, 4x4 mirrored
Colours: backdrop dark blue; 6-bit pens 1 / 2 greens (colour code P6), 8-bit pens 1 / 2 reds (colour code P8).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sdk', 'tools'))
from cps3asset import Flash  # noqa: E402

TILE0, TILE_END = 0x1000, 0x4000                 # labelled tiles in character RAM (3 MB)
BASE0, BASE_STEP = 0x1400, 0x40
P6, P8 = 40, 1                                   # colour codes: 6-bit entries 2560-2623, 8-bit 256-511
PENS = (1, 2)
BACKDROP = (2, 2, 6)
COL6 = ((0, 10, 0), (8, 31, 8))
COL8 = ((12, 0, 0), (31, 10, 10))
# (band, grid column, w, h, 6-bit, mirrored)
SPRITES = [('A', 0, 1, 1, 1, 0), ('A', 2, 1, 2, 1, 0), ('A', 4, 1, 4, 1, 0), ('A', 6, 2, 1, 1, 0),
           ('A', 9, 2, 2, 1, 0), ('A', 12, 2, 4, 1, 0), ('A', 15, 4, 2, 1, 1), ('A', 20, 2, 2, 1, 1),
           ('B', 0, 4, 1, 1, 0), ('B', 5, 4, 2, 1, 0), ('B', 10, 4, 4, 1, 0), ('B', 15, 4, 4, 1, 1),
           ('C', 0, 4, 1, 0, 0), ('C', 5, 4, 2, 0, 0), ('C', 10, 4, 4, 0, 0), ('C', 15, 4, 4, 0, 1)]
BAND_ROW = {'A': 0, 'B': 5, 'C': 10}


def layout():
    """[(i, x, y, w, h, base, bpp6, flipx)]"""
    return [(i, 16 * c, 16 * BAND_ROW[b], w, h, BASE0 + BASE_STEP * i, b6, fx)
            for i, (b, c, w, h, b6, fx) in enumerate(SPRITES)]


def expected(s):
    """the tile in each cell, [(cx, cy, tile)] with cx, cy the cell's screen column / row in the sprite"""
    _, _, _, w, h, base, _, fx = s
    return [(cx, cy, base + (w - 1 - cx if fx else cx) * h + cy) for cx in range(w) for cy in range(h)]


def tile(label):
    out = bytearray(256)
    for y in range(16):
        for x in range(16):
            bit = 15 - (y // 4 * 4 + x // 4)
            out[16 * y + x] = PENS[label >> bit & 1]
    return bytes(out)


def bgr(c):
    r, g, b = c
    return b << 10 | g << 5 | r


def main():
    out = sys.argv[1]
    f = Flash()
    f.tiles(0, b''.join(tile(t) for t in range(TILE0, TILE_END)))
    f.write(os.path.join(out, 'wtest.bin'))
    L = ['/* tools/wtest.py */',
         f'#define W_TILE0 0x{TILE0:x}u', f'#define W_TILES 0x{TILE_END - TILE0:x}u',
         f'#define W_P6 {P6}u', f'#define W_P8 {P8}u',
         f'#define W_BACKDROP 0x{bgr(BACKDROP):04x}u',
         f'static const uint16_t w_col6[2] = {{0x{bgr(COL6[0]):04x}, 0x{bgr(COL6[1]):04x}}};',
         f'static const uint16_t w_col8[2] = {{0x{bgr(COL8[0]):04x}, 0x{bgr(COL8[1]):04x}}};',
         'static const struct w_spr { int16_t x, y; uint8_t w, h, bpp6, flipx; uint16_t base; } w_sprites[] = {']
    for _, x, y, w, h, base, b6, fx in layout():
        L.append(f'    {{{x}, {y}, {w}, {h}, {b6}, {fx}, 0x{base:x}}},')
    L.append('};')
    L.append(f'#define W_N {len(SPRITES)}')
    open(os.path.join(out, 'wtest.h'), 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
