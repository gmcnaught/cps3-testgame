#!/usr/bin/env python3
"""CPS3 video test 2 (src/vtest2.c, src/cps3v.c): the video features a game port uses, as a scene written as a C
header and the screens it should produce, composed here in screen coordinates without the CPS3's register formulas.

    vtest2.py <out_dir>      -> <out_dir>/vtest2_scene.h, <out_dir>/expect_<phase>.png

Scene: four 64x64 tilemaps (a port's background layers), drawn as bands back to front: tilemap 0 opaque (rows in
graded colours, column / row markers), 1 and 2 sparse, 3 the front layer on screen lines 96-223 only. Tiles come from
all 8 character RAM banks (1 MB = 4,096 tiles each; tilemap 1 from bank 1, 2 from bank 2, 3 from bank 3, sprites from
banks 5 and 7, up to tile 32,767) and colour codes up to 0x1ff (colour RAM entries up to 0x1ffff).
Phases (PHASE_FRAMES frames each; the program stays in the last):
  0  parallax: each tilemap at its own scroll
  1  parallax further on: tilemap 3 past the 1024-pixel map wrap
  2  vertical scroll: tilemaps at y 500, 1000 and 1010 (across the wrap) and -30
  3  120 sprites (1x1 to 4x4, flips, partly off every edge) interleaved with the bands in depth order: some behind
     tilemap 2, some between 2 and 3, some in front of 3
  4  as 3, the display list split into four main-list records (a new sublist after each band); same screen as 3
  5  600 sprites (1x1, overlapping, list order = depth), more than one sublist holds (511: the 505th sprite starts a
     second main-list record); per-line load well above a game's
  6  column streaming: tilemap 1 scrolls 6 px a frame for 250 frames (to x 1500, past the 1024-pixel map wrap)
     through a 256-column level, the program writing each column into a 64-column map just before it comes into
     view, as a port streams a room wider than the map; then it holds
  7  tilemap 0 switched to another map in memory (data unit 6; a port's alternative layer), tilemap 2 switched off
     (its band still in the list: draws nothing)
  8  sprites from 300 tiles uploaded in one call across a bank boundary (tiles 24,426-24,725, banks 5-6), and black
     masks over the top and bottom 16 lines: sprites in a colour code whose colours are all 0 (black, not
     transparent)
  9  as 3, after the program reloads part of character RAM (tilemap 0's and 3's tiles, some sprite tiles) and some
     colours while running, as a port does between rooms (last: on jtcps3 the reloaded tiles do not show)
"""
import os
import sys

import numpy as np
from PIL import Image

W, H = 384, 224
PHASE_FRAMES = 600
BANK = 4096                                        # tiles per 1 MB character RAM bank
# per phase: the four tilemaps' scrolls (map pixel at the screen's top-left; for the streamed tilemap the level
# pixel, unwrapped, where the stream stops), the sprite set, the tile set (0 / 1), options: groups (a new main-list
# record after each band), units (each tilemap's data unit, default k), enable (default all on), stream (tilemap 1
# streamed from the level into unit 5)
S0 = [(10, 0), (40, 8), (120, 16), (300, 24)]
PHASES = [(S0, 0, 0, {}),
          ([(20, 0), (80, 8), (240, 16), (900, 24)], 0, 0, {}),
          ([(10, 500), (40, 1000), (120, 1010), (300, -30)], 0, 0, {}),
          (S0, 1, 0, {}),
          (S0, 1, 0, {'groups': 1}),
          (S0, 2, 0, {}),
          ([(10, 0), (1500, 8), (120, 16), (300, 24)], 0, 0, {'stream': 1, 'units': [0, 5, 2, 3]}),
          (S0, 0, 0, {'units': [6, 1, 2, 3], 'enable': [1, 1, 0, 1]}),
          (S0, 3, 0, {}),
          (S0, 1, 1, {})]
UNITS = 7                                          # tilemap data units 0-6 (unit 5: the stream)
LEVEL_W = 256                                      # streamed level columns
STREAM_PX, STREAM_FRAMES = 6, 250
TILES_C = 6 * BANK - 150                           # the one-call upload: 300 tiles across the bank 5 / 6 boundary
MASK_PAL = 0x0f                                    # colour code with every colour 0
BANDS = [(0, 0, 224), (1, 0, 224), (2, 0, 224), (3, 96, 128)]   # (tilemap, first line, lines), back to front
PAL = [1, 2, 0x80, 0x1c0]                          # colour code of each tilemap's tiles
SPAL = list(range(0x1f0, 0x200))                   # sprite colour codes


def bgr(r, g, b):
    return (b << 10) | (g << 5) | r


class Scene:
    def __init__(self):
        self.colours = {0: bgr(2, 2, 6)}           # colour RAM index -> BGR555; entry 0: backdrop
        self.colours_b = {}                        # changed by the reload
        self.tiles = {}                            # tile number -> 256 pixel values, tile set 0
        self.tiles_b = {}                          # tile set 1: replaced tiles
        self.maps = [[[(0, 0, 0, 0)] * 64 for _ in range(64)] for _ in range(UNITS)]   # (tile, pal, fx, fy)
        self.level = [[(0, 0, 0, 0)] * LEVEL_W for _ in range(64)]                     # streamed into unit 5
        self.tiles_c = []                          # pixels of tiles TILES_C.., uploaded in one call
        self.sprites = []                          # (set, slot, x, y, w, h, tile, pal, fx, fy); slot: drawn after band slot

    def put_tile(self, n, f, b=False):
        px = bytes(f(x, y) for y in range(16) for x in range(16))
        (self.tiles_b if b else self.tiles)[n] = px
        return n


def build():
    s = Scene()
    # colours: code 1 graded rows (tilemap 0), 2 tilemap 1, 0x80 tilemap 2, 0x1c0 tilemap 3, 0x1f0-0x1ff sprites
    for i in range(1, 256):
        s.colours[0x100 + i] = bgr((i * 3) % 32, (i // 8) % 32, 31 - (i // 8) % 32)
        s.colours[0x200 + i] = bgr(31 - i % 32, (i * 5) % 32, 8)
        s.colours[0x8000 + i] = bgr(8, 31 - i % 32, (i * 7) % 32)
        s.colours[0x1c000 + i] = bgr((i * 11) % 32, 16, (i * 3) % 32)
    for c in SPAL:
        for i in range(1, 256):
            s.colours[c * 256 + i] = bgr((c * 7 + i) % 32, (c * 3 + i * 2) % 32, (c + i * 5) % 32)
    for i in range(1, 256, 3):                     # the reload changes tilemap 1's colours
        s.colours_b[0x200 + i] = bgr(i % 32, 31, 31 - i % 32)

    # tilemap 0 (bank 0): a graded row band per map row (8 tiles), a column marker every 8 columns (the column
    # number in 1-8 bars), a row marker in column 0
    grad = [s.put_tile(1 + k, lambda x, y, k=k: 1 + 32 * (k % 8) + (y + x // 4) % 32) for k in range(8)]
    bars = [s.put_tile(16 + n, lambda x, y, n=n: 250 if (x % 2 == 1 and x // 2 < n + 1 and 2 <= y <= 13) or
                       x == 0 or y == 0 else 0x30 + n) for n in range(8)]
    rowm = [s.put_tile(32 + n, lambda x, y, n=n: 251 if (y % 2 == 1 and y // 2 < n + 1 and 2 <= x <= 13) or
                       y == 15 else 0x60 + n) for n in range(8)]
    for r in range(64):
        for c in range(64):
            t = grad[r % 8]
            if c % 8 == 4:
                t = bars[(c // 8) % 8]
            if c == 0:
                t = rowm[r % 8]
            s.maps[0][r][c] = (t, PAL[0], 0, 0)
    # tile set 1: tilemap 0's graded tiles redrawn as checks
    for k in range(8):
        s.put_tile(1 + k, lambda x, y, k=k: 1 + 32 * ((k + 3) % 8) + (8 if (x // 4 + y // 4) % 2 else 20), b=True)

    # tilemap 1 (bank 1): sparse diamonds; tilemap 2 (bank 2): broken strips; flips on some cells
    dia = s.put_tile(BANK + 7, lambda x, y: (1 + (x + y) % 200) if abs(x - 7.5) + abs(y - 7.5) <= 7 else 0)
    arrow = s.put_tile(BANK + 4095, lambda x, y: 40 + y * 8 if x <= y // 2 + 4 and 4 <= y <= 13 else 0)
    for r in range(64):
        for c in range(64):
            if (r * 7 + c * 3) % 11 == 0:
                s.maps[1][r][c] = (dia, PAL[1], 0, 0)
            elif (r * 5 + c) % 23 == 0:
                s.maps[1][r][c] = (arrow, PAL[1], c % 2, r % 2)
    strip = s.put_tile(2 * BANK + 100, lambda x, y: 1 + x * 4 + y if 4 <= y <= 11 else 0)
    for r in range(64):
        for c in range(64):
            if r % 6 == 3 and c % 4 != 0:
                s.maps[2][r][c] = (strip, PAL[2], (c // 4) % 2, 0)
    # tilemap 3 (bank 3): bricks on map rows 0-7 and 56-63 (in view at y scroll 24 and -30), platforms elsewhere
    brick = s.put_tile(3 * BANK, lambda x, y: 0xc0 if y % 8 == 7 or (x + (y // 8) * 8) % 16 == 0 else 1 + (x + y) % 60)
    plat = s.put_tile(3 * BANK + 4095, lambda x, y: 70 + x if y < 6 else 0)
    for r in range(64):
        for c in range(64):
            if r < 8 or r >= 56:
                s.maps[3][r][c] = (brick, PAL[3], c % 3 == 0, 0)
            elif r % 4 == 0 and (c // 5) % 3 == 0:
                s.maps[3][r][c] = (plat, PAL[3], 0, 0)
    s.put_tile(3 * BANK, lambda x, y: 0xc8 if y % 8 == 7 or (x + (y // 8) * 8) % 16 == 0 else 100 + (x * y) % 60,
               b=True)

    # the streamed level (tilemap 1, phase 6): diamonds, and on map row 2 a column marker (bars = column mod 8,
    # flipped by column / 8 mod 2): a column written to the wrong place shows
    for r in range(64):
        for c in range(LEVEL_W):
            if r % 8 == 2:
                s.level[r][c] = (bars[c % 8], PAL[1], (c // 8) % 2, 0)
            elif (r * 3 + c * 5) % 7 == 0:
                s.level[r][c] = (dia, PAL[1], 0, c % 2)
    # unit 6 (phase 7): tilemap 0's other map, the graded tiles in diagonal stripes
    for r in range(64):
        for c in range(64):
            s.maps[6][r][c] = (grad[(r + c) % 8], PAL[0], c % 2, 0)

    # sprite images (tiles column by column, as the CPS3 draws them): banks 5 and 7
    def image(first, w, h, f, b=False):
        for tx in range(w):
            for ty in range(h):
                s.put_tile(first + tx * h + ty, lambda x, y, tx=tx, ty=ty: f(tx * 16 + x, ty * 16 + y), b=b)
        return first

    def man(x, y, w, h):                           # a figure with an outline: flips and order show
        cx, cy = w * 8, h * 8
        if x in (0, 16 * w - 1) or y in (0, 16 * h - 1):
            return 255
        if (x - cx) ** 2 / (cx * cx) + (y - cy * 0.6) ** 2 / (cy * cy * 0.25) < 1:
            return 1 + (x * 3 + y) % 200
        if x < cx // 2 and y > cy:
            return 220
        return 0
    imgs = {}
    nxt = 5 * BANK
    for w, h in ((1, 1), (1, 2), (2, 2), (2, 4), (4, 4)):
        imgs[(w, h)] = image(nxt, w, h, lambda x, y, w=w, h=h: man(x, y, w, h))
        nxt += w * h
    top = image(8 * BANK - 4, 2, 2, lambda x, y: 255 if x in (0, 31) or y in (0, 31) else 1 + (x // 4 + y // 4) * 9)
    image(5 * BANK, 1, 1, lambda x, y: 255 if x in (0, 15) or y in (0, 15) else 30 + x * 9, b=True)   # reloaded
    # set 0 (phases 0-2): a few sprites over the parallax, in front of everything
    for i, (w, h) in enumerate(((1, 1), (2, 2), (2, 4), (4, 4))):
        s.sprites.append((0, 4, 20 + 80 * i, 40, w, h, imgs[(w, h)], SPAL[i], i % 2, 0))
    s.sprites.append((0, 4, 340, 160, 2, 2, top, SPAL[5], 0, 0))
    # set 1 (phases 3, 4 and 6): 120 sprites in three depth slots (after band 1, after band 2, after band 3)
    sizes = [(1, 1), (1, 2), (2, 2), (2, 4), (4, 4)]
    for i in range(120):
        w, h = sizes[(i * 7) % 5]
        x = (i * 37) % 420 - 24
        y = (i * 53) % 260 - 24
        slot = 2 if i < 40 else 3 if i < 80 else 4
        s.sprites.append((1, slot, x, y, w, h, imgs[(w, h)] if i % 9 else top if (w, h) == (2, 2) else imgs[(w, h)],
                          SPAL[i % 16], (i // 2) % 2, (i // 3) % 2))
    # set 2 (phase 5): 600 1x1 sprites, list order = depth
    for i in range(600):
        s.sprites.append((2, 4, (i * 29) % 400 - 8, (i * 17) % 236 - 8, 1, 1, imgs[(1, 1)] if i % 5 else top + (i % 4),
                          SPAL[(i * 5) % 16], i % 2, (i // 2) % 2))
    # set 3 (phase 8): tiles from the one-call upload (each shows its number's low bits), black masks
    for k in range(300):
        s.tiles_c.append(bytes((255 if x in (0, 15) or y in (0, 15) else
                                1 + ((k >> (x // 4)) & 1) * 100 + (y // 4) * 30) if k < 296 else 1
                               for y in range(16) for x in range(16)))
    solid = TILES_C + 296                          # 4 solid tiles: the 4x1 masks
    for i in range(12):
        s.sprites.append((3, 4, 16 + 30 * i, 40 + (i % 3) * 50, 4, 4, TILES_C + 140 + i, SPAL[i], i % 2, 0))
    for x in range(0, W, 64):
        s.sprites.append((3, 4, x, 0, 4, 1, solid, MASK_PAL, 0, 0))
        s.sprites.append((3, 4, x, H - 16, 4, 1, solid, MASK_PAL, 0, 0))
    return s


def compose(s, phase):
    scrolls, sset, tset, opt = phase
    units = opt.get('units', [0, 1, 2, 3])
    enable = opt.get('enable', [1, 1, 1, 1])
    tiles = dict(s.tiles)
    tiles.update({TILES_C + k: p for k, p in enumerate(s.tiles_c)})
    colours = dict(s.colours)
    if tset:
        tiles.update(s.tiles_b)
        colours.update(s.colours_b)
    T = {n: np.frombuffer(p, np.uint8).reshape(16, 16) for n, p in tiles.items()}
    scr = np.zeros((H, W), np.int64)

    def draw_tile(px, pal, fx, fy, x0, y0, rows=None):
        t = px[:, ::-1] if fx else px
        t = t[::-1, :] if fy else t
        ys, xs = np.nonzero(t)
        X, Y = xs + x0, ys + y0
        ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
        if rows is not None:
            ok &= (Y >= rows[0]) & (Y < rows[1])
        scr[Y[ok], X[ok]] = pal * 256 + t[ys[ok], xs[ok]]

    def band(tm, first, lines):
        if not enable[tm]:
            return
        sx, sy = scrolls[tm]
        m = s.maps[units[tm]]
        # every map cell that reaches the screen, drawn at its screen position (the map repeats every 1024 px; the
        # streamed level is read at its own, unwrapped column)
        for cy in range(-1, H // 16 + 2):
            for cx in range(-1, W // 16 + 2):
                mx0 = (sx // 16 + cx) * 16
                my0 = (sy // 16 + cy) * 16
                if units[tm] == 5:
                    tile, pal, fx, fy = s.level[(my0 // 16) % 64][(mx0 // 16) % LEVEL_W]
                else:
                    tile, pal, fx, fy = m[(my0 // 16) % 64][(mx0 // 16) % 64]
                if tile:
                    draw_tile(T[tile], pal, fx, fy, mx0 - sx, my0 - sy, (first, first + lines))

    def sprite(x0, y0, w, h, tile, pal, fx, fy):
        for c in range(w):
            for r in range(h):
                bx = (w - 1 - c) if fx else c
                by = (h - 1 - r) if fy else r
                draw_tile(T[tile + c * h + r], pal, fx, fy, x0 + bx * 16, y0 + by * 16)

    for k, b in enumerate(BANDS):
        band(*b)
        for (st, slot, x, y, w, h, t, p, fx, fy) in s.sprites:
            if st == sset and slot == k + 1:
                sprite(x, y, w, h, t, p, fx, fy)
    lut = np.zeros(0x20000, np.uint32)
    for i, c in colours.items():
        lut[i] = ((c & 0x1f) << 3) << 16 | (((c >> 5) & 0x1f) << 3) << 8 | ((c >> 10) & 0x1f) << 3
    rgb = lut[scr]
    a = np.stack([(rgb >> 16) & 0xff, (rgb >> 8) & 0xff, rgb & 0xff], axis=-1).astype(np.uint8)
    return Image.fromarray(a, 'RGB')


def header(s):
    o = ['/* generated by tools/vtest2.py */', '#include <stdint.h>',
         f'#define V2_PHASE_FRAMES {PHASE_FRAMES}', f'#define V2_PHASES {len(PHASES)}',
         f'#define V2_SPRITES {len(s.sprites)}', f'#define V2_BANDS {len(BANDS)}', f'#define V2_UNITS {UNITS}',
         f'#define V2_LEVEL_W {LEVEL_W}', f'#define V2_STREAM_PX {STREAM_PX}', f'#define V2_STREAM_FRAMES {STREAM_FRAMES}',
         f'#define V2_TILES_C {TILES_C}', f'#define V2_TILES_C_N {len(s.tiles_c)}']
    o.append('static const int16_t v2_scroll[V2_PHASES][4][2] = {'
             + ', '.join('{' + ', '.join(f'{{{x}, {y}}}' for x, y in p[0]) + '}' for p in PHASES) + '};')
    o.append('static const uint8_t v2_set[V2_PHASES] = {' + ', '.join(str(p[1]) for p in PHASES) + '};')
    o.append('static const uint8_t v2_tileset[V2_PHASES] = {' + ', '.join(str(p[2]) for p in PHASES) + '};')
    o.append('static const uint8_t v2_groups[V2_PHASES] = {' + ', '.join(str(p[3].get('groups', 0)) for p in PHASES)
             + '};')
    o.append('static const uint8_t v2_stream[V2_PHASES] = {' + ', '.join(str(p[3].get('stream', 0)) for p in PHASES)
             + '};')
    o.append('static const uint8_t v2_units[V2_PHASES][4] = {' + ', '.join(
        '{' + ', '.join(str(u) for u in p[3].get('units', [0, 1, 2, 3])) + '}' for p in PHASES) + '};')
    o.append('static const uint8_t v2_enable[V2_PHASES][4] = {' + ', '.join(
        '{' + ', '.join(str(u) for u in p[3].get('enable', [1, 1, 1, 1])) + '}' for p in PHASES) + '};')
    o.append('static const uint16_t v2_bands[V2_BANDS][3] = {' + ', '.join(f'{{{a}, {b}, {c}}}' for a, b, c in BANDS)
             + '};')

    def colours(name, d):
        o.append(f'#define {name.upper()}_N {len(d)}')
        o.append(f'static const uint32_t {name}[{len(d)}] = {{  /* index << 15 | BGR555 */')
        o.extend(f'    {(i << 15) | c:#x}u,' for i, c in sorted(d.items()))
        o.append('};')

    def tiles(name, d):
        o.append(f'#define {name.upper()}_N {len(d)}')
        o.append(f'static const uint16_t {name}_num[{len(d)}] = {{' + ', '.join(str(n) for n in sorted(d)) + '};')
        o.append(f'static const uint8_t {name}[{len(d)} * 256] = {{')
        for n in sorted(d):
            p = d[n]
            for i in range(0, 256, 64):
                o.append('    ' + ', '.join(str(b) for b in p[i:i + 64]) + ',')
        o.append('};')
    colours('v2_colours', s.colours)
    colours('v2_colours_b', s.colours_b)
    tiles('v2_tiles', s.tiles)
    tiles('v2_tiles_b', s.tiles_b)
    o.append('/* tilemap cells: tile | pal << 16 | flipx << 25 | flipy << 26 */')
    cell = lambda t, p, fx, fy: f'{t | p << 16 | fx << 25 | fy << 26:#x}'
    o.append('static const uint32_t v2_maps[V2_UNITS][64 * 64] = {  /* unit 5: filled by the stream */')
    for m in s.maps:
        o.append('  {')
        for r in m:
            o.append('    ' + ', '.join(cell(*e) for e in r) + ',')
        o.append('  },')
    o.append('};')
    o.append('static const uint32_t v2_level[64][V2_LEVEL_W] = {')
    for r in s.level:
        o.append('  {' + ', '.join(cell(*e) for e in r) + '},')
    o.append('};')
    o.append('static const uint8_t v2_tiles_c[V2_TILES_C_N * 256] = {')
    for p in s.tiles_c:
        for i in range(0, 256, 64):
            o.append('    ' + ', '.join(str(b) for b in p[i:i + 64]) + ',')
    o.append('};')
    o.append('struct v2_sprite { uint8_t set, slot; int16_t x, y; uint8_t w, h; uint16_t tile, pal; uint8_t fx, fy; };')
    o.append('static const struct v2_sprite v2_sprites[V2_SPRITES] = {')
    o += [f'    {{{st}, {sl}, {x}, {y}, {w}, {h}, {t}, {p}, {fx}, {fy}}},' for st, sl, x, y, w, h, t, p, fx, fy in s.sprites]
    o.append('};')
    return '\n'.join(o) + '\n'


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    s = build()
    open(os.path.join(out, 'vtest2_scene.h'), 'w').write(header(s))
    for k, p in enumerate(PHASES):
        compose(s, p).save(os.path.join(out, f'expect_{k}.png'))
    print(f'{out}: {len(s.tiles)} tiles (+{len(s.tiles_b)} reloaded), {len(s.colours)} colours '
          f'(+{len(s.colours_b)}), {len(s.sprites)} sprites, {len(PHASES)} phases')


if __name__ == '__main__':
    main()
