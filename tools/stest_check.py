#!/usr/bin/env python3
"""Check the CPS3 sound test in MAME (scripts/cps3_stest.sh).
    stest_check.py <build_dir> <writes.log> <mame.wav> [model.wav]
<build_dir>: tools/stest.py's output (stest.bin, stest_writes.txt). <writes.log>: scripts/lua/stest_log.lua's.
<mame.wav>: MAME's -wavwrite output at the chip's rate (-samplerate 37286).
1. Writes: the logged sound-register writes, with the program's frame, equal to stest_writes.txt (after the
   key-off at start-up, before the end frame).
2. Audio: the chip computed from the logged writes and stest.bin as MAME's cps3_a.cpp does (per voice: signed 8-bit
   sample x signed 16-bit volume / 2^23, left from register 7 bits 16-31 and right from bits 0-15 as MAME's
   cps3.cpp routes them, position advanced by step / 4096 a sample, loop / end), left and right,
   against the WAV: every sample within 1 LSB at lag 0. Each write takes effect from output sample ceil(t x rate).
   The model is written to model.wav when given (e.g. to compare with a capture from hardware).
"""
import os
import sys
import wave

import numpy as np

CHIP = 42954545 // 3 // 384      # MAME's stream rate: clock() / 384 in integers, 37,286 Hz
BASE = 0x400000


def swap(v):
    return (v >> 16) | ((v << 16) & 0xffffffff)


def s16(v):
    v &= 0xffff
    return v - 0x10000 if v & 0x8000 else v


def model(writes, img, total):
    out = np.zeros((total, 2))
    regs = [[0] * 8 for _ in range(16)]
    st = [{'on': False, 'tot': 0, 'dead': False} for _ in range(16)]
    keys, prev = 0, 0
    marks = [(min(int(np.ceil(t * CHIP)), total), o, d) for t, _, o, d in writes] + [(total, None, None)]
    for at, off, data in marks:
        if at > prev:
            N = at - prev
            j = np.arange(N, dtype=np.int64)
            for v in range(16):
                s, r = st[v], regs[v]
                if not s['on']:
                    continue
                step = r[3] >> 16
                if not s['dead']:
                    start, end = swap(r[1]) - BASE, swap(r[5]) - BASE
                    loop = ((r[3] & 0xffff) | ((r[4] << 16) & 0xffff0000)) - BASE
                    a = start + ((s['tot'] + j * step) >> 12)
                    keep = N
                    if r[2] & 1:
                        over = a >= end
                        a[over] = loop + (a[over] - end) % (end - loop)
                    else:
                        stop = np.nonzero(a >= end)[0]
                        if len(stop):
                            keep = int(stop[0])
                            s['dead'] = True
                    smp = img[a[:keep]]
                    out[prev:prev + keep, 0] += smp * s16(r[7] >> 16) / 8388608   # left: bits 16-31 (MAME's routing)
                    out[prev:prev + keep, 1] += smp * s16(r[7]) / 8388608
                s['tot'] += N * step
            prev = at
        if off is None:
            break
        if off < 0x80:
            regs[off // 8][off % 8] = data
        elif off == 0x80:
            new = data >> 16
            for v in range(16):
                if new & (1 << v) and not keys & (1 << v):
                    st[v] = {'on': True, 'tot': 0, 'dead': False}
                elif not new & (1 << v):
                    st[v]['on'] = False
            keys = new
    return out


def main():
    bd, logf, wavf = sys.argv[1:4]
    nm = os.path.basename(os.path.normpath(bd))    # stest, atest: tools/<nm>.py's output
    img = np.frombuffer(open(f'{bd}/{nm}.bin', 'rb').read(), np.int8).astype(np.int64)
    exp = [tuple(int(x, 16) if k == 2 else int(x) for k, x in enumerate(l.split())) for l in open(f'{bd}/{nm}_writes.txt')]
    end = int(next(l for l in open(f'{bd}/{nm}.h') if 'ST_END_FRAME' in l).split()[2])
    writes = []
    for line in open(logf):
        t, fr, off, data = line.split()
        writes.append((float(t), int(fr), int(off), int(data, 16)))
    got = [(fr, o, d) for _, fr, o, d in writes if 0 < fr < end]
    boot = [(fr, o, d) for _, fr, o, d in writes if fr == 0]
    ok1 = got == exp and boot == [(0, 0x80, 0)]
    print(f'  writes: {len(got)} logged, {len(exp)} expected: {"equal" if got == exp else "DIFFER"}; '
          f'start-up {boot}')
    if got != exp:
        for k, (a, b) in enumerate(zip(got + [None] * len(exp), exp + [None] * len(got))):
            if a != b:
                print(f'    first difference at write {k}: logged {a}, expected {b}')
                break

    w = wave.open(wavf)
    rate, nch, n = w.getframerate(), w.getnchannels(), w.getnframes()
    pcm = np.frombuffer(w.readframes(n), np.int16).reshape(-1, nch).astype(np.float64) / 32768
    if rate != CHIP or nch != 2:
        print(f'  audio: {wavf} is {rate} Hz, {nch} channels; needs {CHIP} Hz stereo (-samplerate {CHIP})')
        print('FAIL')
        return 1
    out = model(writes, img, n)
    if len(sys.argv) > 4:
        ww = wave.open(sys.argv[4], 'wb')
        ww.setnchannels(2)
        ww.setsampwidth(2)
        ww.setframerate(CHIP)
        ww.writeframes(np.clip(np.round(out * 32768), -32768, 32767).astype('<i2').tobytes())
        ww.close()
    err = np.abs(pcm - out) * 32768
    energy = [float(np.sqrt(np.mean(out[:, c] ** 2))) for c in (0, 1)]
    ok2 = err.max() <= 1.0 and min(energy) > 0
    print(f'  audio: {n / rate:.1f} s at {rate} Hz, model rms L {energy[0]:.4f} R {energy[1]:.4f}, '
          f'max error {err.max():.2f} LSB (L {err[:, 0].max():.2f}, R {err[:, 1].max():.2f})')
    if err.max() > 1.0:
        k = int(np.argmax(err.max(axis=1)))
        print(f'    first sample over 1 LSB at {np.nonzero(err.max(axis=1) > 1.0)[0][0] / rate:.6f} s; '
              f'worst at {k / rate:.6f} s')
    print('PASS' if ok1 and ok2 else 'FAIL')
    return 0 if ok1 and ok2 else 1


if __name__ == '__main__':
    sys.exit(main())
