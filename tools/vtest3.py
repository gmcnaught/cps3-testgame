#!/usr/bin/env python3
"""CPS3 video test 3 (src/vtest3.c, src/cps3v.c): objects drawn as one main-list record each, as a port draws its
instances: the object's pieces are written once into sprite RAM as a sublist (prebuilt, mirrored copies too), and each
frame a record points at that sublist with the object's position and, for some, a colour code that replaces the
pieces' own (main-list word 2 bit 29, bits 16-24). The scene is written as a C header and the screens it should
produce are composed here in screen coordinates, without the CPS3's register formulas.

    vtest3.py <out_dir>      -> <out_dir>/vtest3_scene.h, <out_dir>/expect_<phase>.png
    vtest3.py --cells <diff.png>...   -> which phase 3 cells have differing pixels (vtest_check.py's _diff masks)

Screen: tilemap 0 (a grey check) on lines 0-111 only, the backdrop (colour 0, dark blue) below, so a pixel the
hardware leaves undrawn (backdrop or check) shows apart from one drawn black.
Phases (PHASE_FRAMES frames each; the program stays in the last):
  0  24 objects of 2-4 pieces (sizes 1x1 to 4x4) as one record each: prebuilt sublists low (from 0x20000) and high
     (to 0x7ffff) in sprite RAM, mirrored copies (pieces mirrored in the frame, flip x), positions partly off every
     edge (a record x of -20 is 1004 in the 10-bit field), overlaps (later records on top), the colour override on
     some: another colour code of the same colours in red, and a code whose colours are all 0 (black)
  1  as 0, every piece its own entry in one record at position 0 with the colour code resolved: same screen as 0
  2  240 objects of two 1x1 pieces, one record each: 241 records, 481 entries (under jtcps3's 511 a frame)
  3  cells (5 columns x 4 rows, 64 x 44 px) around one configuration from a port (Maldita Castilla's level 1, held
     frame): record A, override red, two pieces mirrored (a 2x2, and left of it a 1x2 whose only opaque column on
     its lower tile is source column 0, so on screen its right edge), and record B after it, overlapping A, with
     transparent pixels over that column. On jtcps3 (rbf 2026-09-24) that column is black where MAME draws red, at
     screen x 176. The cells repeat the configuration (one at the port's exact place) and change one thing each:
     no override, no B, no 2x2, the 1x2 alone (flipped or not, 1x1, at other x), per-piece entries, order swapped
  4  as 3 with every object drawn per piece (the port's other path, which showed the same column): same screen as 3
"""
import os
import sys

import numpy as np
from PIL import Image

W, H = 384, 224
PHASE_FRAMES = 600
BAND_LINES = 112                                   # tilemap 0 on lines 0-111
PRE_LO, PRE_HI = 0x20000, 0x7c000                  # prebuilt sublists: after the per-frame ones; before the end
CHECK_PAL, BLACK_PAL = 1, 0x0f
# phases: (object set, per piece)
PHASES = [(0, 0), (0, 1), (1, 0), (2, 0), (2, 1)]
CELL_W, CELL_H = 64, 44
CELL_X0, CELL_Y0 = 25, 24                          # cell (2, 3) at (153, 156): the port's place


def bgr(r, g, b):
    return (b << 10) | (g << 5) | r


class Scene:
    def __init__(self):
        self.colours = {0: bgr(2, 2, 10)}          # colour RAM index -> BGR555; entry 0: backdrop
        self.tiles = {}                            # tile number -> 256 pixel values
        self.subs = []                             # prebuilt sublists: (addr, [(dx, dy, w, h, tile, pal, fx)])
        self.objs = [[], [], []]                   # per set: (sub, X, Y, pal override or -1, per piece)
        self.cells = []                            # set 2: (column, row, what)
        self._at = [PRE_LO, PRE_HI]

    def put_tile(self, n, f):
        self.tiles[n] = bytes(f(x, y) for y in range(16) for x in range(16))
        return n

    def image(self, first, w, h, f):
        """w x h tiles from first, column by column (as the CPS3 numbers a sprite's tiles), f over the image"""
        for tx in range(w):
            for ty in range(h):
                self.put_tile(first + tx * h + ty, lambda x, y, tx=tx, ty=ty: f(tx * 16 + x, ty * 16 + y))
        return first

    def sub(self, pieces, hi=False):
        """a prebuilt sublist (256-aligned), low or high in sprite RAM"""
        a = self._at[hi]
        self._at[hi] = a + ((len(pieces) * 16 + 255) & ~255)
        assert self._at[0] <= 0x40000 and self._at[1] <= 0x80000
        self.subs.append((a, pieces))
        return len(self.subs) - 1


def mirrored(pieces, sw):
    """a frame of width sw mirrored as a port mirrors it: each piece at sw - dx - its width, flip x toggled"""
    return [(sw - dx - 16 * w, dy, w, h, t, p, 1 - fx) for dx, dy, w, h, t, p, fx in pieces]


def blob(w, h, k):
    def f(x, y):
        cx, cy = w * 8 - 0.5, h * 8 - 0.5
        if x in (0, 16 * w - 1) or y in (0, 16 * h - 1):
            return 250 if (x + y) % 4 < 2 else 0       # dashed outline: placement and flips show
        if ((x - cx) / (cx - 1)) ** 2 + ((y - cy) / (cy - 1)) ** 2 < 1:
            return 1 + (x * 3 + y * 5 + k * 17) % 200
        return 0
    return f


def build():
    s = Scene()
    # colours: tilemap 0's check (code 1); object codes 0x20-0x2f (own) with code + 0x10 the same pens in red, the
    # cells' codes as the port's (A 0x110, its red 0x111, B 0x10c); BLACK_PAL all 0
    for i in range(1, 256):
        s.colours[CHECK_PAL * 256 + i] = bgr(10 + i % 4, 10 + i % 4, 11 + i % 4)
    for c in list(range(0x20, 0x30)) + [0x110, 0x10c]:
        for i in range(1, 256):
            s.colours[c * 256 + i] = bgr((c * 7 + i) % 32, (c * 3 + i * 2) % 32, (c + i * 5) % 32)
    for c in list(range(0x20, 0x30)) + [0x110]:
        red = 0x111 if c == 0x110 else c + 0x10
        for i in range(1, 256):
            s.colours[red * 256 + i] = bgr(8 + (i * 5) % 24, 0, 0)
    check = s.put_tile(1, lambda x, y: 1 + ((x // 4 + y // 4) % 2) * 2 + (x == 0 or y == 0))

    # phase 0 / 1 objects: frames of 2-4 pieces (dx, dy in the frame), each prebuilt as drawn and mirrored
    t = 0x1000
    frames = []
    shapes = [  # (frame width, [(dx, dy, w, h)])
        (48, [(0, 0, 2, 2), (32, 8, 1, 2), (8, 32, 2, 1)]),
        (64, [(0, 0, 4, 4), (16, 64, 2, 1)]),
        (40, [(4, 0, 2, 4), (0, 64, 1, 1), (24, 64, 1, 1), (20, 16, 1, 2)]),
        (32, [(0, 0, 2, 1), (0, 16, 2, 2)]),
        (36, [(10, 0, 1, 1), (0, 16, 2, 2), (20, 4, 1, 1)]),
    ]
    for k, (sw, ps) in enumerate(shapes):
        pieces = []
        for j, (dx, dy, w, h) in enumerate(ps):
            s.image(t, w, h, blob(w, h, k * 4 + j))
            pieces.append((dx, dy, w, h, t, 0x20 + 3 * k + j % 3, 0))
            t += w * h
        frames.append((s.sub(pieces, hi=k % 2 == 1), s.sub(mirrored(pieces, sw), hi=k % 2 == 0)))
    for i in range(24):
        fr = frames[i % 5]
        x = (i * 53) % 404 - 20
        y = (i * 37) % 236 - 16
        if i in (3, 11):
            x = -20                                # record x 1004: off the left edge by wrapping
        if i == 7:
            x = 360
        ov = -1 if i % 3 == 0 else (s.subs[fr[0]][1][0][5] + 0x10) if i % 3 == 1 else BLACK_PAL
        s.objs[0].append((fr[(i // 2) % 2], x, y, ov, 0))

    # phase 2: 240 objects of two 1x1 pieces
    a = s.image(0x1800, 1, 1, blob(1, 1, 3))
    b = s.image(0x1801, 1, 1, blob(1, 1, 9))
    pair = s.sub([(0, 0, 1, 1, a, 0x24, 0), (8, 6, 1, 1, b, 0x25, 0)])
    pair_m = s.sub(mirrored([(0, 0, 1, 1, a, 0x24, 0), (8, 6, 1, 1, b, 0x25, 0)], 24), hi=True)
    for i in range(240):
        s.objs[1].append((pair_m if i % 4 == 3 else pair, (i % 20) * 19 + (i // 20) % 3, (i // 20) * 18 + i % 5,
                          0x35 if i % 7 == 0 else -1, 0))

    # phase 3 / 4 cells. Pieces as the port's sublists hold them (x fields 26 and 2 for A, 15 and 39 for B; record
    # A at x + 13, B at x): A = a mirrored 2x2 (tiles A2) then a mirrored 1x2 (tiles A1: upper a column-0 bar, lower
    # pens only in source column 0, rows 2-6); B = a 2x2 (its right tiles opaque in columns 0-6 only) and a 1x2
    A2 = s.image(0x2059, 2, 2, blob(2, 2, 5))
    A1 = 0x205d
    s.put_tile(A1, lambda x, y: (3 if x == 0 else 4 if x == 1 and 4 <= y <= 11 else 0))
    s.put_tile(A1 + 1, lambda x, y: (4 if y < 5 else 3) if x == 0 and 2 <= y <= 6 else 0)
    A1F = 0x2064                                   # A1 drawn mirrored in the tiles (column 15), for an unflipped piece
    s.put_tile(A1F, lambda x, y: (3 if x == 15 else 4 if x == 14 and 4 <= y <= 11 else 0))
    s.put_tile(A1F + 1, lambda x, y: (4 if y < 5 else 3) if x == 15 and 2 <= y <= 6 else 0)
    B2 = 0x2039
    s.put_tile(B2, lambda x, y: 1 + (x + y) % 5)
    s.put_tile(B2 + 1, lambda x, y: 1 + (x * y) % 5 if y < 12 else 0)
    s.put_tile(B2 + 2, lambda x, y: 5 if x < 7 else 0)
    s.put_tile(B2 + 3, lambda x, y: [0, 5, 5, 5, 4, 3][min(5, y // 3)] if x < 7 and y >= 3 else 0)
    B1 = s.image(0x203d, 1, 2, blob(1, 2, 2))
    PA, PB = 0x110, 0x10c
    a2 = (11, 0, 2, 2, A2, PA, 1)
    a1 = (-5, 0, 1, 2, A1, PA, 1)
    sub_a = s.sub([a2, a1])
    sub_a1 = s.sub([a1])
    sub_a1u = s.sub([(-5, 0, 1, 2, A1F, PA, 0)])
    sub_a1s = s.sub([(-5, 16, 1, 1, A1 + 1, PA, 1)])
    sub_b = s.sub([(0, 0, 2, 2, B2, PB, 0), (32, 0, 1, 2, B1, PB, 0)], hi=True)
    sub_a22 = s.sub([(11, 0, 2, 2, A1, PA, 1)])   # a mirrored 2x2 of A1's columns: bars at its right edge and middle
    s.put_tile(A1 + 2, lambda x, y: 3 if x == 0 else 0)
    s.put_tile(A1 + 3, lambda x, y: 4 if x == 0 and 2 <= y <= 6 else 0)
    RED = 0x111
    cells = [  # (column, row, what, objects as (sub, dx, ov, per piece)) with dx from the cell's x
        (2, 3, 'replica at the port\'s place', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (0, 3, 'replica 128 px left', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (4, 3, 'replica 128 px right', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (2, 0, 'replica over the tilemap', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (2, 2, 'replica on line 112 (band edge)', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (1, 3, 'A without override', [(sub_a, 13, -1, 0), (sub_b, 0, -1, 0)]),
        (3, 3, 'A alone (no B)', [(sub_a, 13, RED, 0)]),
        (0, 2, 'A\'s 1x2 alone, then B', [(sub_a1, 13, RED, 0), (sub_b, 0, -1, 0)]),
        (1, 2, 'A\'s 1x2 alone', [(sub_a1, 13, RED, 0)]),
        (3, 2, 'A\'s 1x2 alone, own colours', [(sub_a1, 13, -1, 0)]),
        (4, 2, 'A\'s 1x2 unflipped (tiles mirrored)', [(sub_a1u, 13, RED, 0)]),
        (0, 1, 'A\'s lower tile alone (1x1)', [(sub_a1s, 13, RED, 0)]),
        (1, 1, 'A\'s 1x2 alone, 1 px right', [(sub_a1, 14, RED, 0)]),
        (2, 1, 'A\'s 1x2 alone, 2 px right', [(sub_a1, 15, RED, 0)]),
        (3, 1, 'A\'s 1x2 alone, 3 px right', [(sub_a1, 16, RED, 0)]),
        (4, 1, 'A\'s 1x2 alone, 1 px left', [(sub_a1, 12, RED, 0)]),
        (0, 0, 'replica, A per piece', [(sub_a, 13, RED, 1), (sub_b, 0, -1, 0)]),
        (1, 0, 'B before A', [(sub_b, 0, -1, 0), (sub_a, 13, RED, 0)]),
        (3, 0, 'mirrored 2x2 of column-0 bars', [(sub_a22, 13, RED, 0)]),
        (4, 0, 'replica, B per piece', [(sub_a, 13, RED, 0), (sub_b, 0, -1, 1)]),
    ]
    for col, row, what, objs in cells:
        x, y = CELL_X0 + col * CELL_W, CELL_Y0 + row * CELL_H
        if what.startswith('replica on line 112'):
            y = BAND_LINES - 12
        s.cells.append((col, row, what, x, y))
        for sub, dx, ov, pp in objs:
            s.objs[2].append((sub, x + dx, y, ov, pp))
    s.maps0 = check
    return s


def compose(s, phase):
    sset, _ = phase
    T = {n: np.frombuffer(p, np.uint8).reshape(16, 16).astype(np.int64) for n, p in s.tiles.items()}
    scr = np.zeros((H, W), np.int64)
    ck = T[s.maps0]
    for y in range(BAND_LINES):
        for x in range(W):
            if ck[y % 16, x % 16]:
                scr[y, x] = CHECK_PAL * 256 + ck[y % 16, x % 16]

    def draw_tile(px, pal, fx, x0, y0):
        t = px[:, ::-1] if fx else px
        ys, xs = np.nonzero(t)
        X, Y = xs + x0, ys + y0
        ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
        scr[Y[ok], X[ok]] = pal * 256 + t[ys[ok], xs[ok]]

    for sub, X, Y, ov, _ in s.objs[sset]:
        for dx, dy, w, h, tile, pal, fx in s.subs[sub][1]:
            for c in range(w):
                for r in range(h):
                    bx = (w - 1 - c) if fx else c
                    draw_tile(T[tile + c * h + r], ov if ov >= 0 else pal, fx, X + dx + bx * 16, Y + dy + r * 16)
    lut = np.zeros(0x20000, np.uint32)
    for i, c in s.colours.items():
        lut[i] = ((c & 0x1f) << 3) << 16 | (((c >> 5) & 0x1f) << 3) << 8 | ((c >> 10) & 0x1f) << 3
    rgb = lut[scr]
    a = np.stack([(rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff], axis=-1).astype(np.uint8)
    return Image.fromarray(a, 'RGB')


def header(s):
    o = ['/* generated by tools/vtest3.py */', '#include <stdint.h>',
         f'#define V3_PHASE_FRAMES {PHASE_FRAMES}', f'#define V3_PHASES {len(PHASES)}',
         f'#define V3_SUBS {len(s.subs)}', f'#define V3_BAND_LINES {BAND_LINES}', f'#define V3_CHECK_TILE {s.maps0}',
         f'#define V3_CHECK_PAL {CHECK_PAL}']
    o.append('static const uint8_t v3_set[V3_PHASES] = {' + ', '.join(str(p[0]) for p in PHASES) + '};')
    o.append('static const uint8_t v3_pieces[V3_PHASES] = {' + ', '.join(str(p[1]) for p in PHASES) + '};')
    o.append(f'#define V3_COLOURS_N {len(s.colours)}')
    o.append(f'static const uint32_t v3_colours[{len(s.colours)}] = {{  /* index << 15 | BGR555 */')
    o.extend(f'    {(i << 15) | c:#x}u,' for i, c in sorted(s.colours.items()))
    o.append('};')
    o.append(f'#define V3_TILES_N {len(s.tiles)}')
    o.append(f'static const uint16_t v3_tiles_num[{len(s.tiles)}] = {{' + ', '.join(str(n) for n in sorted(s.tiles))
             + '};')
    o.append(f'static const uint8_t v3_tiles[{len(s.tiles)} * 256] = {{')
    for n in sorted(s.tiles):
        p = s.tiles[n]
        for i in range(0, 256, 64):
            o.append('    ' + ', '.join(str(b) for b in p[i:i + 64]) + ',')
    o.append('};')
    o.append('struct v3_piece { int16_t dx, dy; uint8_t w, h; uint16_t tile, pal; uint8_t fx; };')
    o.append('struct v3_sub { uint32_t addr; uint16_t first, n; };')
    ps, subs = [], []
    for addr, pieces in s.subs:
        subs.append(f'    {{{addr:#x}, {len(ps)}, {len(pieces)}}},')
        ps += [f'    {{{", ".join(str(v) for v in p)}}},' for p in pieces]
    o.append(f'static const struct v3_piece v3_piece[{len(ps)}] = {{')
    o += ps
    o.append('};')
    o.append('static const struct v3_sub v3_sub[V3_SUBS] = {')
    o += subs
    o.append('};')
    o.append('struct v3_obj { uint16_t sub; int16_t x, y, pal; uint8_t pieces; };')
    for k, objs in enumerate(s.objs):
        o.append(f'#define V3_OBJS{k} {len(objs)}')
        o.append(f'static const struct v3_obj v3_objs{k}[V3_OBJS{k}] = {{')
        o += [f'    {{{", ".join(str(v) for v in ob)}}},' for ob in objs]
        o.append('};')
    o.append('static const struct v3_obj *const v3_objs[3] = {v3_objs0, v3_objs1, v3_objs2};')
    o.append('static const uint16_t v3_objs_n[3] = {V3_OBJS0, V3_OBJS1, V3_OBJS2};')
    return '\n'.join(o) + '\n'


def cells(paths):
    """per vtest_check.py diff mask: the phase 3 cells holding differing pixels"""
    s = build()
    for f in paths:
        m = np.array(Image.open(f).convert('L')) > 0
        print(f)
        for col, row, what, x, y in s.cells:
            box = m[max(0, y):y + CELL_H - 4, max(0, x):x + CELL_W]
            if box.any():
                ys, xs = np.nonzero(box)
                print(f'  cell ({col},{row}) {what}: {len(xs)} px, x {x + xs.min()}-{x + xs.max()}, '
                      f'y {y + ys.min()}-{y + ys.max()}')


def main():
    if sys.argv[1] == '--cells':
        return cells(sys.argv[2:])
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    s = build()
    open(os.path.join(out, 'vtest3_scene.h'), 'w').write(header(s))
    for k, p in enumerate(PHASES):
        compose(s, p).save(os.path.join(out, f'expect_{k}.png'))
    print(f'{out}: {len(s.tiles)} tiles, {len(s.colours)} colours, {len(s.subs)} prebuilt sublists, '
          f'objects {", ".join(str(len(o)) for o in s.objs)}, {len(PHASES)} phases')


if __name__ == '__main__':
    main()
