#!/usr/bin/env python3
"""A MAME stand-in set for a homebrew CPS3 program: Street Fighter III 3rd Strike (Asia, NO CD), the CPS3 set with the
most flash (SIMMs 1-2 program, 3-6 graphics and samples, 64 MB). The program as its BIOS ROM, encrypted with its keys
(MAME cps3.cpp cps3_mask, init_sfiii3; the jtcps3 MRA header carries the same keys); blank SIMMs otherwise.
    mkcps3.py <main.bin> <out_dir> [simm1.bin [user5.bin]]      -> <out_dir>/sfiii3na/*
simm1.bin (the program at 0x06000000) goes to SIMM 1: encrypted for its addresses, byte k of each 32-bit word in
file simm1.k (MAME cps3.cpp copy_from_nvram). user5.bin (sound samples, e.g. tools/stest.py's) goes to SIMM 3 onward, as MAME
builds its user5 region from them: per pair of chips (2j, 2j + 1), 4 MB of it, byte 4w + 0 / 1 / 2 / 3 =
chip 2j + 1 byte 2w, chip 2j byte 2w, chip 2j + 1 byte 2w + 1, chip 2j byte 2w + 1.
"""
import os
import struct
import sys

KEY1, KEY2 = 0xa55432b4, 0x0c129981
SET = 'sfiii3na'
BIOS = 'sfiii3_asia_nocd.29f400.u2'
SIMMS = [f'sfiii3-simm{n}.{k}' for n in (1, 2) for k in range(4)] + \
        [f'sfiii3-simm{n}.{k}' for n in (3, 4, 5, 6) for k in range(8)]
USER5 = [f'sfiii3-simm{n}.{k}' for n in (3, 4, 5, 6) for k in range(8)]   # MAME's order


def rol16(v, n):
    return ((v << n) | (v >> (16 - n))) & 0xffff


def rotxor(val, xorval):
    res = (val + rol16(val, 2)) & 0xffff
    return rol16(res, 4) ^ (res & (val ^ xorval))


def mask(addr, key1=KEY1, key2=KEY2):
    addr ^= key1
    val = (addr & 0xffff) ^ 0xffff
    val = rotxor(val, key2 & 0xffff)
    val ^= ((addr >> 16) ^ 0xffff) & 0xffff
    val = rotxor(val, key2 >> 16)
    val ^= (addr & 0xffff) ^ (key2 & 0xffff)
    return val | (val << 16)


def encrypt(data, base=0):
    """data (big-endian 32-bit words at address base) -> the stored words"""
    n = len(data) // 4
    w = struct.unpack(f'>{n}I', data)
    return struct.pack(f'>{n}I', *(x ^ mask(base + 4 * i) for i, x in enumerate(w)))


def main():
    prog, out = sys.argv[1], sys.argv[2]
    data = open(prog, 'rb').read()
    if len(data) > 0x80000:
        sys.exit(f'{prog}: {len(data)} bytes, the BIOS ROM holds 524288')
    data = data.ljust(0x80000, b'\xff')
    d = os.path.join(out, SET)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, BIOS), 'wb').write(encrypt(data))
    simm1 = None
    if len(sys.argv) > 3:
        img = open(sys.argv[3], 'rb').read()
        img = encrypt(img.ljust(0x800000, b'\xff')[:0x800000], 0x6000000)
        simm1 = [img[k::4] for k in range(4)]
    chips = {}
    if simm1:
        chips.update({f'sfiii3-simm1.{k}': simm1[k] for k in range(4)})
    if len(sys.argv) > 4:
        u5 = open(sys.argv[4], 'rb').read()
        if len(u5) > 0x200000 * len(USER5):
            sys.exit(f'{sys.argv[4]}: {len(u5)} bytes, SIMMs 3-6 hold {0x200000 * len(USER5)}')
        for j in range(0, (len(u5) + 0x3fffff) // 0x400000):
            seg = u5[j * 0x400000:(j + 1) * 0x400000].ljust(0x400000, b'\xff')
            chips[USER5[2 * j]] = seg[1::2]
            chips[USER5[2 * j + 1]] = seg[0::2]
    for s in SIMMS:
        open(os.path.join(d, s), 'wb').write(chips.get(s, b'\xff' * 0x200000))
    print(f'{d}: program {len(open(prog, "rb").read())} bytes' +
          (f', samples {len(u5)} bytes' if len(sys.argv) > 4 else ''))


if __name__ == '__main__':
    main()
