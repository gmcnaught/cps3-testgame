#!/usr/bin/env python3
"""A MAME stand-in set for a homebrew CPS3 program: the program as Red Earth's BIOS ROM, encrypted with Red Earth's
keys (MAME cps3.cpp cps3_mask; the jtcps3 MRA header carries the same keys), and blank SIMMs.
    mkcps3.py <main.bin> <out_dir> [simm1.bin]      -> <out_dir>/redearthn/*
simm1.bin (the program at 0x06000000) goes to SIMM 1: encrypted for its addresses, byte k of each 32-bit word in
file simm1.k (MAME cps3.cpp copy_from_nvram).
"""
import os
import struct
import sys

KEY1, KEY2 = 0x9e300ab1, 0xa175b82c
SET = 'redearthn'
BIOS = 'redearth_asia_nocd.29f400.u2'
SIMMS = [f'redearth-simm1.{k}' for k in range(4)] + [f'redearth-simm3.{k}' for k in range(8)] + \
        [f'redearth-simm4.{k}' for k in range(8)] + [f'redearth-simm5.{k}' for k in range(2)]


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
    for s in SIMMS:
        p = os.path.join(d, s)
        if simm1 and s.startswith('redearth-simm1.'):
            open(p, 'wb').write(simm1[int(s[-1])])
        else:
            open(p, 'wb').write(b'\xff' * 0x200000)
    print(f'{d}: program {len(open(prog, "rb").read())} bytes')


if __name__ == '__main__':
    main()
