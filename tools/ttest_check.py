#!/usr/bin/env python3
"""The timing test's results side by side (src/ttest.c; tests, units and notes in tools/ttest.py).
    ttest_check.py <label>=<source> ...
A source is MAME's dump (scripts/lua/ttest_dump.lua: "<index> <hex>" lines), a screenshot of the test's screen
(.png: MAME snapshot or jtcps3 screenshot, read with tools/dmap_check.py's OCR), or the screen typed in from a board
(.txt: one test a line as the screen shows it, e.g. "LD MRAM    6.00"; tests not listed stay blank). Values the
screen shows in thousands ("12345K") are read as 12345000.
Columns: the SH7604 programming manual's figure (no wait states), then each source. Units: CPU clocks per operation
for the op rows (clocks per loop iteration for ITER), CPU clocks for the frame and the DMA rows (FRT ticks x 8, so
they assume the FRT runs at phi / 8 of the CPU clock).
Exit 1 if a screenshot's rows cannot be read.
"""
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ttest  # noqa: E402
from dmap_check import ocr  # noqa: E402

PER_OP = ('op', 'iter', 'during')
NAMES = [t[0] for t in ttest.TESTS]


def fmt(kind, v):
    if v is None:
        return ''
    if v == 0xffffffff:
        return 'NEVER'
    if kind in PER_OP:
        v = v - (1 << 32) if v >= 1 << 31 else v
        return f'{v / 100:.2f}'
    return str(v)


def parse_screen_value(kind, s):
    s = s.strip()
    if not s:
        return None
    if s in ('NEVER', 'TIMEOUT'):
        return 0xffffffff
    if kind in PER_OP:
        return round(float(s) * 100) & 0xffffffff
    if s.endswith('K'):                      # shown in thousands: the last 3 digits are lost
        return int(s[:-1]) * 1000
    return int(s)


def from_lines(lines):
    """screen lines (OCR or typed): each '<name> <value>', name as in tools/ttest.py"""
    out = {}
    for line in lines:
        line = line.strip()
        for name in sorted(NAMES, key=len, reverse=True):
            if line.startswith(name) and (len(line) == len(name) or line[len(name)] == ' '):
                kind = ttest.TESTS[NAMES.index(name)][1]
                try:
                    out[name] = parse_screen_value(kind, line[len(name):])
                except ValueError:
                    pass
                break
    return out


def from_shot(path):
    px = Image.open(path).convert('RGB').load()
    best = {}
    for dx in (0, -1):                       # jtcps3 draws the picture 1 px left
        lines = []
        for row in range(2, 2 + ttest.ROWS):
            s = ocr(px, row, dx).ljust(48)
            lines += [s[k:k + ttest.CELL] for k in range(0, ttest.COLS * ttest.CELL, ttest.CELL)]
        got = from_lines(lines)
        if len(got) > len(best):
            best = got
    return best


def load(src):
    if src.endswith('.png'):
        return from_shot(src)
    text = open(src).read().splitlines()
    if text and all(re.fullmatch(r'\d+ [0-9a-f]{8}', ln) for ln in text if ln):
        return {NAMES[int(i)]: int(v, 16) for i, v in (ln.split() for ln in text if ln) if int(i) < len(NAMES)}
    return from_lines(text)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cols = []
    for a in sys.argv[1:]:
        label, _, src = a.partition('=')
        if not src:
            label, src = os.path.basename(a), a
        cols.append((label, load(src)))
    bad = 0
    w = [8, 44] + [max(10, len(c[0])) for c in cols]
    print('  '.join(h.ljust(n) for h, n in zip(['test', 'manual'] + [c[0] for c in cols], w)))
    for name, kind, _, _, _, manual in ttest.TESTS:
        row = [name, manual or '']
        for _, vals in cols:
            row.append(fmt(kind, vals.get(name)))
        print('  '.join(v.ljust(n) for v, n in zip(row, w)).rstrip())
    for label, vals in cols:
        if len(vals) < len(NAMES):
            missing = [n for n in NAMES if n not in vals]
            print(f'{label}: {len(missing)} of {len(NAMES)} tests not read: {", ".join(missing)}')
            bad = 1
    sys.exit(bad)


if __name__ == '__main__':
    main()
