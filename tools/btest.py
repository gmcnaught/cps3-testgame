#!/usr/bin/env python3
"""CPS3 sound bank probe (src/btest.c = src/stest.c on btest.h): does any register move the sound chip's samples to
another SIMM? jtcps3 reads sample offset mod 16 MB (tools/atest.py); a port could keep its effects at the start of
every SIMM and its stages' music in SIMMs 4-6 if a register chose the SIMM. The sample flash is atest's (every 1 MB
block starts with its beep code: (b // 8) + 1 high beeps, then (b % 8) + 1 low). Each probe writes one candidate
register, plays the start of block 0 on voice 0 and writes the register back to 0: 1 high 1 low = no effect; 3 high
1 low = SIMM 4, 5 high = SIMM 5, 7 high = SIMM 6 (any other code names the block read).
    btest.py <out_dir>      -> <out_dir>/btest.h, btest.bin, btest_writes.txt (as tools/stest.py), btest_plays.txt

Candidates: the graphics flash bank register 0x040c0088 (the CPU's flash window; SIMMs 4-6 as the BIOS selects them),
sound register 0x84 (3rd Strike and Red Earth write 0x00230000 at start-up; MAME ignores it) and the other unused
sound registers 0x81-0x87, and voice register 0 (MAME ignores it; 3rd Strike writes 0). Expected in MAME: block 0
every time (MAME reads only the start register).
"""
import sys

import atest
import stest

BASE, MB = stest.BASE, stest.MB
SND = 0x040e0000
FRAMES = 200


def probes():
    """(label, [(bits, addr, value)], before key-on on the voice: True for voice registers)"""
    P = [('NONE', [])]
    for simm, v in ((4, 0x0a), (5, 0x12), (6, 0x1a)):
        P.append((f'40C0088={v:04X} (SIMM {simm})', [(16, 0x040c0088, v)]))
    for v in (0x00010000, 0x00020000, 0x00030000, 0x00000001, 0x00000002, 0x00000003, 0x01000000):
        P.append((f'SND 84={v:08X}', [(32, SND + 4 * 0x84, v)]))
    for r in (0x81, 0x82, 0x83, 0x85, 0x86, 0x87):
        for v in (0x00010001, 0x00030003):
            P.append((f'SND {r:02X}={v:08X}', [(32, SND + 4 * r, v)]))
    for v in (0x00000001, 0x00000003, 0x00010000, 0x00030000, 0x01000000):
        P.append((f'VOICE REG 0={v:08X}', [(32, SND + 0, v)]))
    return P


def main():
    S = {f'block{b}': (atest.code(b), None, b * MB) for b in range(64)}
    E = []

    def at(f, *op):
        E.append((f, op))

    at(1, 'scene', 'CPS3 SOUND BANK PROBE: 1H 1L = NO EFFECT')
    f = 120
    plays = []
    for k, (label, pokes) in enumerate(probes()):
        at(f, 'scene', f'B{k + 1:02d} {label}')
        at(f, 'voice', 0, 'block0', 4096, 0x4000, 0x4000)
        for bits, a, v in pokes:
            at(f, 'poke', bits, a, v)
        at(f, 'keys', 1)
        at(f + FRAMES - 30, 'keys', 0)
        for bits, a, v in pokes:
            at(f + FRAMES - 30, 'poke', bits, a, 0)
        plays.append(f'B{k + 1:02d} {label}')
        f += FRAMES
    at(f, 'scene', 'END')
    stest.emit(sys.argv[1], 'btest', S, E, f + 10)
    open(f'{sys.argv[1]}/btest_plays.txt', 'w').write('\n'.join(plays) + '\n')


if __name__ == '__main__':
    main()
