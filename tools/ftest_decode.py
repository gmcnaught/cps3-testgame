#!/usr/bin/env python3
"""Decode the beep codes of tools/ftest.py's (or tools/btest.py's) plays from a recording of src/ftest.c (MAME -wavwrite or a capture
from hardware, from the program's start): beeps grouped into codes by silences over 1 s (a code's longest pause is
0.48 s; plays are 1.5 s apart, an erased slot plays silence and so no code), listed against ftest_plays.txt (btest: its btest_plays.txt).
    ftest_decode.py <wav> [build/ftest/ftest_plays.txt]       (numpy: run in the cps3-dev image)"""
import sys
import wave

import numpy as np

w = wave.open(sys.argv[1])
R, ch = w.getframerate(), w.getnchannels()
a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch)[:, 0].astype(float)
win = int(0.01 * R)
e = np.sqrt(np.convolve(a * a, np.ones(win) / win, 'same'))
on = e > 0.25 * e.max()
idx = np.flatnonzero(np.diff(on.astype(int))) + 1
edges = np.r_[0, idx, len(on)]
codes, last = [], -9.0
for s, t in zip(edges[:-1], edges[1:]):
    if on[s] and t - s > 0.05 * R:
        zc = np.sum(np.diff(np.sign(a[s:t])) != 0) / 2 / ((t - s) / R)
        if s / R - last > 1.0:
            codes.append([s / R, 0, 0])
        codes[-1][1 if zc > 800 else 2] += 1
        last = t / R
plays = open(sys.argv[2] if len(sys.argv) > 2 else 'build/ftest/ftest_plays.txt').read().splitlines()
print(f'{len(codes)} codes heard, {len(plays)} plays (an erased slot heard as silence drops out of the list)')
for i, (t, h, l) in enumerate(codes):
    print(f'{t:7.1f}s heard {h}H {l}L    ' + (plays[i] if i < len(plays) else ''))
