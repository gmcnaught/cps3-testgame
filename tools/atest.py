#!/usr/bin/env python3
"""CPS3 sound addressing test (src/atest.c = src/stest.c on atest.h): which sample-flash byte a voice reads for a
given start address. Every 1 MB block of the sample flash (SIMMs 3-6, 64 blocks) starts with its own beep code;
each test plays one block's start address, on voice 0 and then voice 1. Where the chip reads another block than the
address names (high address bits dropped or latched elsewhere), the code heard is that other block's.
    atest.py <out_dir>      -> <out_dir>/atest.h, atest.bin, atest_writes.txt (as tools/stest.py)

Beep code of block b: (b // 8) + 1 high beeps (1,200 Hz), a pause, then (b % 8) + 1 low beeps (400 Hz). Block 0:
1 high, 1 low; block 17 (17 MB): 3 high, 2 low; block 44: 6 high, 5 low. The screen names the test, voice, chip
address and the code expected. Blocks tested: 0-7 (the SFX region in a game is the first MB or two), then 8, 12,
16, 17, 20, 24, 32, 33, 40, 44, 48, 63.
"""
import math
import sys

import stest

RATE, BASE, MB = stest.RATE, stest.BASE, stest.MB
BLOCKS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 17, 20, 24, 32, 33, 40, 44, 48, 63]
FRAMES = 330                    # frames a test (5.5 s: the longest code, 8 + 8 beeps, takes 4.6 s)


def beeps(n, freq):
    on, off = int(0.13 * RATE), int(0.13 * RATE)
    one = [stest.clip8(100 * math.sin(2 * math.pi * freq * i / RATE)) for i in range(on)] + [0] * off
    return one * n


def code(b):
    return beeps(b // 8 + 1, 1200) + [0] * int(0.35 * RATE) + beeps(b % 8 + 1, 400)


def main():
    S = {f'block{b}': (code(b), None, b * MB) for b in range(64)}
    E = []

    def at(f, *op):
        E.append((f, op))

    f = 1
    at(f, 'scene', 'CPS3 SOUND ADDRESS TEST: BEEPS = HIGH, THEN LOW')
    f = 120
    k = 0
    for v in (0, 1):
        for b in BLOCKS:
            k += 1
            at(f, 'scene', f'T{k:02d} V{v} {BASE + b * MB:07X} {b:2d}MB: {b // 8 + 1} HIGH {b % 8 + 1} LOW')
            at(f, 'voice', v, f'block{b}', 4096, 0x4000, 0x4000)
            at(f, 'keys', 1 << v)
            at(f + FRAMES - 30, 'keys', 0)
            f += FRAMES
    at(f, 'scene', 'END')
    stest.emit(sys.argv[1], 'atest', S, E, f + 10)


if __name__ == '__main__':
    main()
