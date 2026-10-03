#!/usr/bin/env python3
"""CPS3 video test scene (src/vtest.c, sdk/src/cps3v.c): writes the scene as a C header and the screen it should
produce, composed here in screen coordinates without the CPS3's register formulas, so a MAME snapshot or a jtcps3
screenshot that matches it checks cps3v.c's position, scroll, tile-order, flip and colour handling.

    vtest.py <out_dir>      -> <out_dir>/vtest_scene.h, <out_dir>/expect_<phase>.png

Scene: colour RAM entry 0 as backdrop; tilemap 0 (opaque: colour swatches R/G/B/grey 0-31, flip markers, column
and row markers) under tilemap 1 (sparse markers), drawn as tilemap bands of at most 128 lines; then sprites of
1x1 to 4x4 tiles, flips, edges, overlap, one in 6-bit colour mode. Phases: the same scene with tilemap 0 scrolled
by PHASES[k] (the program switches every PHASE_FRAMES frames and stays in the last phase); phases 3-4 draw every
sprite size (1, 2, 4 x 1, 2, 4 tiles) with each flip instead (each tile: its own colour and an F), phase 5 sprites in
6-bit colour mode and with word 3 bits 8-9 set (Red Earth sets them on its 6-bit sprites; MAME ignores them).
"""
import os
import sys

from PIL import Image

W, H = 384, 224
PHASE_FRAMES = 600
# (tilemap 0 scroll, tilemap 1 scroll, sprite set): the scrolls are the map pixel shown at the screen's top-left
PHASES = [((8, 12), (37, 11), 0), ((440, 12), (37, 11), 0), ((1000, 1000), (37, 11), 0),
          ((8, 12), (37, 11), 1), ((8, 12), (37, 11), 2), ((8, 12), (37, 11), 3)]


def bgr(r, g, b):
    return (b << 10) | (g << 5) | r


def rgb8(c):
    return ((c & 0x1f) << 3, ((c >> 5) & 0x1f) << 3, ((c >> 10) & 0x1f) << 3)


class Scene:
    def __init__(self):
        self.colours = {}          # colour RAM index -> BGR555
        self.tiles = [bytes(256)]  # tile 0: transparent
        self.maps = [[[0] * 64 for _ in range(64)] for _ in range(2)]
        self.sprites = []          # (set, x, y, w, h, tile, pal, flipx, flipy, bpp6, word 3 bits 8-9)

    def tile(self, pixels):
        """16x16 pixel values (rows); returns the tile number"""
        self.tiles.append(bytes(v for row in pixels for v in row))
        return len(self.tiles) - 1

    def image(self, w, h, f):
        """a w x h tile sprite image from f(x, y), stored column by column as the CPS3 draws it; first tile"""
        first = len(self.tiles)
        for tx in range(w):
            for ty in range(h):
                self.tile([[f(tx * 16 + x, ty * 16 + y) for x in range(16)] for y in range(16)])
        return first


def build():
    s = Scene()
    s.colours[0] = bgr(4, 4, 10)                    # backdrop
    P1, P2, P6 = 1, 2, 20                           # 8-bit palettes 1 and 2 (entries 256-767); 6-bit code 20
    for lv in range(32):
        s.colours[256 + 1 + lv] = bgr(lv, 0, 0)
        s.colours[256 + 33 + lv] = bgr(0, lv, 0)
        s.colours[256 + 65 + lv] = bgr(0, 0, lv)
        s.colours[256 + 97 + lv] = bgr(lv, lv, lv)
    WHITE, BLACK, YELLOW, MAGENTA, CYAN, ORANGE = range(129, 135)
    for i, c in zip(range(129, 135), [bgr(31, 31, 31), bgr(0, 0, 0), bgr(31, 31, 0), bgr(31, 0, 31),
                                       bgr(0, 31, 31), bgr(31, 16, 0)]):
        s.colours[256 + i] = c
    for i in range(1, 256):                         # palette 2: palette 1's colours with red and blue swapped
        if 256 + i in s.colours:
            c = s.colours[256 + i]
            s.colours[512 + i] = ((c & 0x1f) << 10) | (c & 0x3e0) | (c >> 10)
    for i in range(1, 64):                          # 6-bit palette at code 20: entries 1280-1343
        s.colours[P6 * 64 + i] = bgr(i // 2, 31 - i // 2, (i * 5) % 32)

    swatch = [s.tile([[2 * k - 1 + (x >= 8) for x in range(16)] for y in range(16)]) for k in range(1, 65)]

    def glyph_F(fg, edge):
        # an F: top bar and stem in fg; edge colour on the left column and top row (flip and offset check)
        rows = []
        for y in range(16):
            r = []
            for x in range(16):
                v = 0
                if 2 <= x <= 4 and 2 <= y <= 13 or 2 <= y <= 4 and 2 <= x <= 12 or 7 <= y <= 9 and 2 <= x <= 9:
                    v = fg
                if x == 0 or y == 0:
                    v = edge
                r.append(v)
            rows.append(r)
        return s.tile(rows)

    tF = glyph_F(WHITE, YELLOW)
    tF2 = glyph_F(CYAN, MAGENTA)
    checker = s.tile([[97 + (6 if (x // 4 + y // 4) % 2 else 10) for x in range(16)] for y in range(16)])
    checker_hi = s.tile([[33 + (6 if (x // 4 + y // 4) % 2 else 10) for x in range(16)] for y in range(16)])
    digits = [s.tile([[ORANGE if (x in (1, 14) or y in (1, 14)) else (1 + 2 * d if (x - 3) // 2 < d + 1 and
                       4 <= y <= 11 and 3 <= x else 0) for x in range(16)] for y in range(16)]) for d in range(5)]

    # tilemap 0: checker, columns 32-63 in the green checker (shows where a 32-column wrap would fall), swatches,
    # flips, markers on column 0 / 63 and row 0 / 63
    m = s.maps[0]

    def ent(tile, pal, fx=0, fy=0, bpp6=0):
        return (tile, pal, fx, fy, bpp6)
    for r in range(64):
        for c in range(64):
            m[r][c] = ent(checker_hi if c >= 32 else checker, P1)
    for ch in range(4):
        for k in range(16):
            m[2 + ch][1 + k] = ent(swatch[ch * 16 + k], P1)
    for i, (fx, fy) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        m[7][1 + i] = ent(tF, P1, fx, fy)
        m[7][6 + i] = ent(tF, P2, fx, fy)
    for r in range(64):
        m[r][0] = ent(digits[0], P1)
        m[r][63] = ent(digits[1], P1)
        m[r][31] = ent(digits[2], P1)
        m[r][32] = ent(digits[3], P1)
    for c in range(64):
        m[0][c] = ent(digits[4], P1)
        m[63][c] = ent(digits[4], P2)
    # tilemap 1: sparse F markers
    m = s.maps[1]
    for r in range(64):
        for c in range(64):
            m[r][c] = ent(tF2, P1) if r % 4 == 1 and c % 5 == 2 else ent(0, P1)

    # sprites (screen x, y of the top-left pixel); set 0
    grad = lambda w, h: s.image(w, h, lambda x, y: 1 + ((x // 2 + y // 2) % 128))
    big = grad(4, 4)
    S = []
    S.append((300, 20, 4, 4, big, P1, 0, 0, 0))
    S.append((320, 40, 2, 2, s.image(2, 2, lambda x, y: [WHITE, YELLOW, MAGENTA, CYAN][(x // 16) * 2 + y // 16]),
              P1, 0, 0, 0))                                         # overlaps the 4x4: drawn later, on top
    for i, (fx, fy) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        S.append((10 + 20 * i, 150, 1, 1, tF, P1, fx, fy, 0))
    quad = s.image(2, 2, lambda x, y: [1 + 31, 33 + 31, 65 + 31, 97 + 31][(x // 16) * 2 + y // 16])
    S.append((100, 140, 2, 2, quad, P1, 0, 0, 0))
    S.append((140, 140, 2, 2, quad, P1, 1, 0, 0))
    S.append((180, 140, 2, 2, quad, P1, 0, 1, 0))
    tall = s.image(1, 4, lambda x, y: 1 + y // 2)
    S.append((220, 120, 1, 4, tall, P1, 0, 0, 0))
    wide = s.image(4, 1, lambda x, y: 65 + x // 2)
    S.append((240, 120, 4, 1, wide, P1, 0, 0, 0))
    S.append((240, 140, 4, 2, s.image(4, 2, lambda x, y: 97 + (x + y) % 32), P2, 1, 1, 0))
    S.append((-8, 100, 2, 2, quad, P1, 0, 0, 0))                    # left edge
    S.append((376, 100, 2, 2, quad, P1, 0, 0, 0))                   # right edge
    S.append((200, 216, 2, 2, quad, P1, 0, 0, 0))                   # bottom edge
    S.append((10, -8, 2, 2, quad, P1, 0, 0, 0))                     # top edge
    six = s.image(2, 2, lambda x, y: 1 + (x + 2 * y) % 63)
    S.append((320, 150, 2, 2, six, P6, 0, 0, 1))
    s.sprites += [(0,) + t + (0,) for t in S]

    # sets 1, 2: every size, two flips per set (rows at y 24 and 120); tile k of a sprite in colour k with an F
    tcol = [1 + 31, 33 + 31, 65 + 31, 97 + 31, YELLOW, MAGENTA, CYAN, ORANGE, 1 + 15, 33 + 15, 65 + 15, 97 + 10,
            1 + 7, 33 + 7, 65 + 7, 97 + 20]
    F = [[(2 <= x <= 4 and 2 <= y <= 13 or 2 <= y <= 4 and 2 <= x <= 12 or 7 <= y <= 9 and 2 <= x <= 9)
          for x in range(16)] for y in range(16)]
    mats = {}
    for w in (1, 2, 4):
        for h in (1, 2, 4):
            mats[(w, h)] = s.image(w, h, lambda x, y, h=h: WHITE if F[y % 16][x % 16] else
                                   tcol[((x // 16) * h + y // 16) % 16])
    for st, flips in ((1, [(0, 0), (1, 0)]), (2, [(0, 1), (1, 1)])):
        for row, (fx, fy) in enumerate(flips):
            x = 4
            for w in (1, 2, 4):
                for h in (1, 2, 4):
                    s.sprites.append((st, x, 24 + 96 * row, w, h, mats[(w, h)], P1, fx, fy, 0, 0))
                    x += 16 * w + 4
    # set 3: 6-bit colour and word 3 bits 8-9
    six1 = s.image(1, 1, lambda x, y: 1 + (x + 2 * y) % 63)
    six4 = s.image(4, 4, lambda x, y: 1 + (x // 2 + y) % 63)
    for i, (t, w, h, b6, z) in enumerate([(six, 2, 2, 1, 0), (six, 2, 2, 1, 3), (quad, 2, 2, 0, 3), (quad, 2, 2, 0, 0),
                                          (six1, 1, 1, 1, 3), (six4, 4, 4, 1, 3), (six4, 4, 4, 1, 0)]):
        s.sprites.append((3, 8 + 52 * i, 120, w, h, t, P6 if b6 else P1, 0, 0, b6, z))
    return s


def compose(s, phase):
    """the expected screen: backdrop, tilemap 0, tilemap 1, sprites in order, colours as 5-bit << 3"""
    scr = [[s.colours[0]] * W for _ in range(H)]

    def put(x, y, tile, pal, fx, fy, bpp6, tx, ty):
        v = s.tiles[tile][(15 - ty if fy else ty) * 16 + (15 - tx if fx else tx)]
        if v and 0 <= x < W and 0 <= y < H:
            scr[y][x] = s.colours.get((pal * (64 if bpp6 else 256) + v) & 0x1ffff, 0)
    for k, (sx, sy) in enumerate(phase[:2]):
        m = s.maps[k]
        for y in range(H):
            my = (y + sy) % 1024
            for x in range(W):
                mx = (x + sx) % 1024
                tile, pal, fx, fy, b6 = m[my // 16 % 64][mx // 16 % 64]
                put(x, y, tile, pal, fx, fy, b6, mx % 16, my % 16)
    for (st, x0, y0, w, h, tile, pal, fx, fy, b6, z) in s.sprites:
        if st != phase[2]:
            continue
        for c in range(w):
            for r in range(h):
                t = tile + c * h + r
                # a flipped sprite mirrors the whole block
                bx = (w - 1 - c) if fx else c
                by = (h - 1 - r) if fy else r
                for ty in range(16):
                    for tx in range(16):
                        put(x0 + bx * 16 + tx, y0 + by * 16 + ty, t, pal, fx, fy, b6, tx, ty)
    img = Image.new('RGB', (W, H))
    img.putdata([rgb8(c) for row in scr for c in row])
    return img


def header(s):
    o = ['/* generated by tools/vtest.py */', '#include <stdint.h>',
         f'#define VT_PHASE_FRAMES {PHASE_FRAMES}', f'#define VT_PHASES {len(PHASES)}',
         f'#define VT_TILES {len(s.tiles)}', f'#define VT_SPRITES {len(s.sprites)}',
         f'#define VT_COLOURS {len(s.colours)}']
    o.append('static const int16_t vt_scroll[VT_PHASES][2][2] = {'
             + ', '.join('{' + ', '.join(f'{{{x}, {y}}}' for x, y in p[:2]) + '}' for p in PHASES) + '};')
    o.append('static const uint8_t vt_set[VT_PHASES] = {' + ', '.join(str(p[2]) for p in PHASES) + '};')
    o.append('static const uint32_t vt_colours[VT_COLOURS] = {  /* index << 16 | BGR555 */')
    o += [f'    {(i << 16) | c:#x}u,' for i, c in sorted(s.colours.items())]
    o.append('};')
    o.append('static const uint8_t vt_tiles[VT_TILES * 256] = {')
    data = b''.join(s.tiles)
    for i in range(0, len(data), 32):
        o.append('    ' + ', '.join(str(b) for b in data[i:i + 32]) + ',')
    o.append('};')
    o.append('/* tilemap cells: tile | pal << 16 | flipx << 25 | flipy << 26 | bpp6 << 27 */')
    o.append('static const uint32_t vt_maps[2][64 * 64] = {')
    for m in s.maps:
        o.append('  {')
        for r in m:
            o.append('    ' + ', '.join(f'{t | p << 16 | fx << 25 | fy << 26 | b << 27:#x}' for t, p, fx, fy, b in r) + ',')
        o.append('  },')
    o.append('};')
    o.append('struct vt_sprite { uint8_t set; int16_t x, y; uint8_t w, h; uint16_t tile, pal; uint8_t fx, fy, bpp6, '
             'w3; };')
    o.append('static const struct vt_sprite vt_sprites[VT_SPRITES] = {')
    o += [f'    {{{st}, {x}, {y}, {w}, {h}, {t}, {p}, {fx}, {fy}, {b}, {z}}},'
          for st, x, y, w, h, t, p, fx, fy, b, z in s.sprites]
    o.append('};')
    return '\n'.join(o) + '\n'


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    s = build()
    open(os.path.join(out, 'vtest_scene.h'), 'w').write(header(s))
    for k, p in enumerate(PHASES):
        compose(s, p).save(os.path.join(out, f'expect_{k}.png'))
    print(f'{out}: {len(s.tiles)} tiles, {len(s.colours)} colours, {len(s.sprites)} sprites, {len(PHASES)} phases')


if __name__ == '__main__':
    main()
