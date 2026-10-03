#!/usr/bin/env python3
"""Read src/wtest.c's screen: the tile label in every 16x16 cell of every sprite (tools/wtest.py), against the tile
cps3v_sprite asks for there.
    wtest_check.py <shot.png>...
Per sprite: OK, or a grid (rows top to bottom, cells left to right) of the tile read in each cell, with '*' where it
differs from the expected tile; '.' = backdrop only (nothing drawn), '?' = mixed pixels. Works on MAME snapshots
(5-bit colour v << 3) and jtcps3 screenshots (v << 3 | v >> 2, picture 1 px left). Exit 1 if any cell differs.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wtest  # noqa: E402

CLASSES = {'bg': wtest.BACKDROP, '6a': wtest.COL6[0], '6b': wtest.COL6[1], '8a': wtest.COL8[0], '8b': wtest.COL8[1]}


def palette():
    out = []
    for k, (r, g, b) in CLASSES.items():
        for f in (lambda v: v << 3, lambda v: v << 3 | v >> 2):
            out.append((k, (f(r), f(g), f(b))))
    return out


def classify(rgb, pal):
    return min(pal, key=lambda kv: sum((a - b) ** 2 for a, b in zip(kv[1], rgb)))[0]


def cell(px, x0, y0, flip, dx, pal):
    ks = []
    for by in range(4):
        for bx in range(4):
            sx = 3 - bx if flip else bx
            ks.append(classify(px[x0 + 4 * sx + 2 + dx, y0 + 4 * by + 2], pal))
    if all(k == 'bg' for k in ks):
        return '.'
    for d in '68':
        if all(k in (d + 'a', d + 'b') for k in ks):
            v = 0
            for k in ks:
                v = v << 1 | (k[1] == 'b')
            return (d, v)
    return '?'


def read(path):
    im = Image.open(path).convert('RGB')
    px = im.load()
    pal = palette()
    best = None
    for dx in (0, -1):
        res = []
        for s in wtest.layout():
            i, x, y, w, h, base, b6, fx = s
            cells = {(cx, cy): cell(px, x + 16 * cx, y + 16 * cy, fx, dx, pal) for cx in range(w) for cy in range(h)}
            res.append((s, cells))
        score = sum(1 for s, cs in res for (cx, cy, t) in wtest.expected(s) if cs[(cx, cy)] == ('6' if s[6] else '8', t))
        if best is None or score > best[0]:
            best = (score, res)
    return best[1]


def main():
    bad = 0
    for f in sys.argv[1:]:
        print(f'{f}:')
        for s, cells in read(f):
            i, x, y, w, h, base, b6, fx = s
            name = f'  {i:2} {"6-bit" if b6 else "8-bit"} {w}x{h}{" mirrored" if fx else ""} base {base:#x}'
            exp = {(cx, cy): t for cx, cy, t in wtest.expected(s)}
            want = '6' if b6 else '8'
            if all(cells[k] == (want, t) for k, t in exp.items()):
                print(name + ': OK')
                continue
            bad = 1
            print(name + ':')
            for cy in range(h):
                row = []
                for cx in range(w):
                    c = cells[(cx, cy)]
                    if isinstance(c, tuple):
                        txt = f'{c[1]:04x}' + ('' if c[0] == want else f'({c[0]}-bit)')
                    else:
                        txt = c.rjust(4)
                    row.append(txt + ('*' if c != (want, exp[(cx, cy)]) else ' '))
                print('      ' + ' '.join(r.ljust(13) for r in row) + '   expected ' +
                      ' '.join(f'{exp[(cx, cy)]:04x}' for cx in range(w)))
    return bad


if __name__ == '__main__':
    sys.exit(main())
