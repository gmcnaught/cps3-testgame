#!/usr/bin/env python3
"""Read src/dmap.c's screen: per tilemap cell the label and origin of the tile drawn there, and the step and frame from
text row 27; compared with the step's expectation (tools/dmap.py steps.txt).
    dmap_check.py <build_dir> <shot.png>...
Per shot: step, frame, the number of cells as expected, and the cells as runs of (origin, label - cell index), e.g.
"0-311 plain +0x1000" (cells 0-311 draw plain flash tiles labelled 0x1000 + cell). Exit 1 if any shot differs.
Works on MAME snapshots (5-bit colour v << 3) and jtcps3 screenshots (v << 3 | v >> 2, picture 1 px left).
"""
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmap  # noqa: E402

NAMES = {dmap.CPU: 'cpu', dmap.PLAIN: 'plain', dmap.RLE: 'rle', dmap.RLE8: 'rle8'}


def palette():
    out = []
    for k, (r, g, b) in dmap.COLOURS.items():
        for f in (lambda v: v << 3, lambda v: v << 3 | v >> 2):
            out.append((k, (f(r), f(g), f(b))))
    return out


def classify(rgb, pal):
    return min(pal, key=lambda kv: sum((a - b) ** 2 for a, b in zip(kv[1], rgb)))[0]


def glyphs():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'font.h')).read()
    rows = re.findall(r'\{((?:0x[0-9a-f]{2},? ?){8})\}', src)
    return {chr(32 + k): [int(v, 16) for v in r.replace(' ', '').split(',') if v] for k, r in enumerate(rows)}


def ocr(px, row, dx):
    G = {c: g for c, g in glyphs().items() if any(g) or c == ' '}
    s = ''
    for c in range(48):
        bits = []
        for y in range(8):
            v = 0
            for x in range(8):
                xx = 8 * c + x + dx
                p = px[xx, 8 * row + y] if 0 <= xx < 384 else (0, 0, 0)
                v = v << 1 | (min(p) > 200)
            bits.append(v)
        s += min(G, key=lambda ch: sum(bin(a ^ b).count('1') for a, b in zip(G[ch], bits)))
    return s.rstrip()


def cells(px, pal):
    out = []
    for r in range(dmap.ROWS):
        for c in range(dmap.COLS):
            pens = [classify(px[16 * c + 4 * bx + 2, 16 * r + 4 * by + 2], pal) for by in range(4) for bx in range(4)]
            origin = None
            for o, (p0, p1) in dmap.PENS.items():
                if all(p in (p0, p1) for p in pens):
                    origin = o
            if origin is None:
                out.append(('?' + ''.join(str(p) for p in pens), None))
                continue
            label = 0
            for p in pens:
                label = label << 1 | (p == dmap.PENS[origin][1])
            out.append((origin, label))
    return out


def runs(cs):
    res, i = [], 0
    while i < len(cs):
        o, lab = cs[i]
        j = i + 1
        if lab is None:
            while j < len(cs) and cs[j] == cs[i]:
                j += 1
            res.append(f'{i}-{j - 1} {o}')
        else:
            while j < len(cs) and cs[j][0] == o and cs[j][1] is not None and cs[j][1] - j == lab - i:
                j += 1
            res.append(f'{i}-{j - 1} {NAMES[o]} {"+" if lab - i >= 0 else "-"}{abs(lab - i):#x}')
        i = j
    return res


def main():
    d = sys.argv[1]
    steps = [l.split() for l in open(os.path.join(d, 'steps.txt'))]
    pal = palette()
    bad = 0
    for f in sys.argv[2:]:
        im = Image.open(f).convert('RGB')
        px = im.load()
        text = max((ocr(px, 27, dx) for dx in (0, -1)), key=lambda s: s.count('STEP'))
        bad_line = max((ocr(px, 26, dx) for dx in (0, -1)), key=len)
        m = re.search(r'STEP ([0-9A-F]{2}) FRAME ([0-9A-F]{8})', text)
        st = int(m.group(1), 16) if m else None
        cs = cells(px, pal)
        msg = f'{os.path.basename(f)}: '
        if st is None or st >= len(steps):
            msg += f'text "{text}"'
            bad = 1
        else:
            name, kind, origin, label = steps[st]
            want = [(int(origin), int(label) + i) for i in range(dmap.N)]
            ok = sum(a == b for a, b in zip(cs, want))
            msg += f'step {st} {name} frame {int(m.group(2), 16)}: {ok} of {dmap.N} as expected'
            if ok != dmap.N:
                bad = 1
        msg += f' | {", ".join(runs(cs))}'
        if bad_line.strip():
            msg += f' | row 26 "{bad_line.strip()}"'
        print(msg)
    return bad


if __name__ == '__main__':
    sys.exit(main())
