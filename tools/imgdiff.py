#!/usr/bin/env python3
"""Compare two images pixel by pixel (top-left 384x224 unless --size): count, area and a mask of differences.
    imgdiff.py <a.png> <b.png> [--mask out.png] [--size WxH]       exit 0 when identical
"""
import argparse
import sys

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--mask')
    ap.add_argument('--size', default='384x224')
    o = ap.parse_args()
    w, h = (int(v) for v in o.size.split('x'))
    a = Image.open(o.a).convert('RGB').crop((0, 0, w, h))
    b = Image.open(o.b).convert('RGB').crop((0, 0, w, h))
    ab, bb = a.tobytes(), b.tobytes()
    d = [ab[i:i + 3] != bb[i:i + 3] for i in range(0, len(ab), 3)]
    n = sum(d)
    msg = f'{o.a} vs {o.b}: {n} of {w * h} pixels differ'
    if n:
        idx = [i for i, v in enumerate(d) if v]
        xs, ys = [i % w for i in idx], [i // w for i in idx]
        msg += f' (x {min(xs)}-{max(xs)}, y {min(ys)}-{max(ys)})'
        if o.mask:
            m = Image.new('L', (w, h))
            m.putdata([255 if v else 0 for v in d])
            m.save(o.mask)
    print(msg)
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
