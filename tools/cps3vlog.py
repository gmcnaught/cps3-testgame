#!/usr/bin/env python3
"""Summarise a scripts/lua/cps3_vlog.lua log (writes.log) over a frame range: what a CPS3 game writes each frame,
when in the frame, and how much (docs/CPS3.md).

    cps3vlog.py <writes.log> [first_frame last_frame]
"""
import collections
import re
import sys


def main():
    path = sys.argv[1]
    f0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    f1 = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 30
    frames = set()
    reg = collections.Counter()           # (kind, address) -> writes
    reg_vals = collections.defaultdict(set)
    late = collections.Counter()          # kind -> writes later than line 20 after the frame callback
    lines = collections.defaultdict(list)  # kind -> line offsets
    chr_frames = collections.Counter()
    chr_cmds = collections.Counter()
    chr_bytes = collections.Counter()      # frame -> decompressed bytes
    chr_dst = [1 << 30, 0]
    pal = []                               # (frame, src, dst, len, fade)
    pal_cur = {}
    counts = []
    cur = None
    for ln in open(path):
        if ln.startswith('  cmd='):
            if cur is None:
                continue
            m = re.match(r'  cmd=(\d) len=(\w+) dst=(\w+) src=(\w+)', ln)
            if int(ln.split('[')[1].split()[0], 16) & 0x01000000:   # the end-of-list record
                continue
            cmd, n, dst = int(m[1]), int(m[2], 16), int(m[3], 16)
            chr_cmds[cmd] += 1
            if cmd != 4:
                chr_bytes[cur] += n
                chr_dst[0] = min(chr_dst[0], dst)
                chr_dst[1] = max(chr_dst[1], dst + n)
            continue
        p = ln.split()
        if len(p) < 3 or not p[0].isdigit():
            continue
        fr, at, kind = int(p[0]), float(p[1]), p[2]
        if not f0 <= fr <= f1:
            cur = None
            continue
        cur = fr
        frames.add(fr)
        if kind == 'COUNT':
            counts.append((int(p[5]), int(p[7]), int(p[11]), int(p[13])))
            continue
        if kind == 'CHRDMA':
            chr_frames[fr] += 1
            continue
        if kind == 'DUMP':
            continue
        addr = int(p[3], 16)
        data, mask = (int(x, 16) for x in p[4].split('/'))
        reg[(kind, addr, mask)] += 1
        reg_vals[(kind, addr, mask)].add(data & mask)
        lines[kind].append(at)
        if at > 20:
            late[kind] += 1
        if kind == 'PPU' and 0x040c00a0 <= addr <= 0x040c00af:
            pal_cur[(addr, mask)] = data & mask
            if addr == 0x040c00ac and mask == 0x0000ffff and data & 2:
                g = lambda a, m: pal_cur.get((a, m), 0)
                src = ((g(0x040c00a0, 0xffff0000) | g(0x040c00a0, 0x0000ffff)) << 1) - 0x400000
                dst = g(0x040c00a4, 0xffff0000) << 0 | g(0x040c00a4, 0x0000ffff)
                fade = g(0x040c00a8, 0xffff0000) | g(0x040c00a8, 0x0000ffff)
                n = (g(0x040c00ac, 0xffff0000) >> 16) | ((data & 1) << 16)
                pal.append((fr, src, dst, n, fade))
    nf = len(frames)
    print(f'{path}: frames {min(frames)}-{max(frames)} ({nf})')
    print('\nRegister writes (kind address mask: writes, distinct values, first values):')
    for (k, a, m), n in sorted(reg.items(), key=lambda x: (x[0][0], x[0][1], -x[0][2])):
        vals = sorted(reg_vals[(k, a, m)])
        print(f'  {k:6s} {a:08x} {m:08x}: {n:6d} ({n / nf:5.2f}/frame), {len(vals):4d} values  '
              + ' '.join(f'{v:x}' for v in vals[:6]) + (' ...' if len(vals) > 6 else ''))
    print('\nLine offsets after the frame callback (min / median / max) and writes after line 20:')
    for k, v in sorted(lines.items()):
        v = sorted(v)
        print(f'  {k:6s} {v[0]:6.1f} {v[len(v) // 2]:6.1f} {v[-1]:6.1f}   late {late[k]}')
    if counts:
        s = [sum(c[i] for c in counts) / len(counts) for i in range(4)]
        mx = [max(c[i] for c in counts) for i in range(4)]
        print(f'\nCPU writes per frame: sprite RAM {s[0]:.0f} writes / {s[1]:.0f} bytes mean, {mx[0]} / {mx[1]} max; '
              f'colour RAM {s[2]:.0f} / {s[3]:.0f} mean, {mx[2]} / {mx[3]} max')
    if chr_frames:
        b = [chr_bytes[f] for f in frames]
        print(f'\nCharacter DMA: started on {len(chr_frames)} of {nf} frames ({max(chr_frames.values())} max a frame); '
              f'commands {dict(chr_cmds)}; decompressed bytes a frame mean {sum(b) / nf:.0f}, max {max(b)}; '
              f'destinations {chr_dst[0]:#x}-{chr_dst[1]:#x}')
    if pal:
        pf = collections.Counter(p[0] for p in pal)
        fades = collections.Counter(p[4] for p in pal)
        print(f'\nPalette DMA: {len(pal)} transfers on {len(pf)} frames ({max(pf.values())} max a frame); '
              f'lengths {sorted(collections.Counter(p[3] for p in pal).items())[:8]}; '
              f'destinations {min(p[2] for p in pal):#x}-{max(p[2] + p[3] for p in pal):#x}; '
              f'fade values {len(fades)}, most used ' + ', '.join(f'{v:08x} x{n}' for v, n in fades.most_common(4)))


if __name__ == '__main__':
    main()
