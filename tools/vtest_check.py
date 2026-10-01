#!/usr/bin/env python3
"""Match jtcps3 screenshots of the CPS3 video test against tools/vtest.py's expected screens, with jtcps3's measured
colour conversion (5-bit channel v -> v << 3 | v >> 2) and picture offset (DX: the screenshot shows MAME's
column x at x + DX).
    vtest_check.py <expect_dir> <shot.png>...    -> per shot: best phase and the pixels that differ there
"""
import glob
import os
import sys

from PIL import Image

DX = -1
W, H = 384, 224


def load_expect(d):
    out = []
    for k in range(len(glob.glob(os.path.join(d, 'expect_[0-9].png')))):
        im = Image.open(os.path.join(d, f'expect_{k}.png')).convert('RGB')
        out.append(Image.eval(im, lambda v: v | (v >> 5)).tobytes())
    return out


def diff(e, s):
    """pixels of the expected screen (columns that stay on screen after the offset) differing in the shot"""
    n, pts = 0, []
    for y in range(H):
        for x in range(max(0, -DX), min(W, W - DX)):
            i, j = (y * W + x) * 3, (y * W + x + DX) * 3
            if e[i:i + 3] != s[j:j + 3]:
                n += 1
                pts.append((x, y))
    return n, pts


def main():
    ex = load_expect(sys.argv[1])
    bad = 0
    for f in sys.argv[2:]:
        s = Image.open(f).convert('RGB').crop((0, 0, W, H)).tobytes()
        res = sorted((diff(e, s)[0], k) for k, e in enumerate(ex))
        n, k = res[0]
        msg = f'{f}: phase {k}, {n} pixels differ'
        if n:
            _, pts = diff(ex[k], s)
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            msg += f' (x {min(xs)}-{max(xs)}, y {min(ys)}-{max(ys)})'
            m = Image.new('L', (W, H))
            ps = set(pts)
            m.putdata([255 if (i % W, i // W) in ps else 0 for i in range(W * H)])
            m.save(os.path.splitext(f)[0] + f'_diff{k}.png')
            bad = 1
        print(msg)
    return bad


if __name__ == '__main__':
    sys.exit(main())
