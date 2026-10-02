#!/usr/bin/env python3
"""CPS3 character RAM load experiments (src/dmap.c), read back from the screen: every tile carries its own 16-bit
label (a 4 x 4 grid of 4 x 4-pixel blocks, bit 15 top-left, row by row) in colours that say where it came from, so one
screenshot shows which tile the video draws in each tilemap cell, whatever the hardware did. tools/dmap_check.py
decodes MAME snapshots and jtcps3 screenshots and compares them with each step's expectation.

    dmap.py <out_dir>    -> <out_dir>/dmap_scene.h, <out_dir>/dmap.bin (graphics flash from SIMM 3), <out_dir>/steps.txt

Label colours (pens: bit 0 / bit 1): written by the CPU 1 / 2 (greens), in the graphics flash as plain tiles 3 / 4
(reds), as 6bpp run-length data 5 / 6 (blues), as 8bpp run-length data 0x9a / 0xe5 (yellows); a cell left at pen 0
shows the backdrop.
Flash: plain tile t at byte 256 t (t = 0 .. FLASH_TILES - 1) labelled t; run-length streams at RLE_AT, labels RLE_LABEL + i:
two 6bpp (command 2, MAME do_char_dma: bytes < 0x40 literal, 0x40 | n = the last literal n + 1 more times; the table
set by command 4 not used, no 0x80 byte), two 8bpp (command 3, rle3() below; table pairs on odd tiles).
Screen: tilemap 0, 24 x 13 cells (lines 0-207) from the step's shown tile; text row 27: the step and frame numbers.
Steps (STEP_FRAMES frames each; the program stays in the last), set by STEPS below:
  (name, kind, source, destination, tiles shown from, expected origin, expected first label)
  kind: 'cpu' (the CPU writes labelled tiles), 'dma0' (uncompressed DMA), 'dma2' / 'dma3' (6bpp / 8bpp run-length DMA); with '_off' the
  display list is empty for BLANK_FRAMES frames and the load happens in the middle of them.
The default order: the uncompressed DMA twice over the tiles on screen, into fresh tiles, the CPU and DMA loads with
the display off, then the 6bpp and the 8bpp run-length DMA twice each. DMAP_STEPS=<name,...> (environment) picks and orders steps by name.
"""
import os
import sys

COLS, ROWS = 24, 13
N = COLS * ROWS                    # 312 tiles shown
STEP_FRAMES = 300
BLANK_FRAMES = 60
FLASH_TILES = 0x4000               # plain labelled tiles: 4 MB
RLE_AT = 0x500000                  # compressed streams
TABLE_AT = 0x4f0000
RLE_LABEL = (0x5000, 0x6000, 0x5800, 0x6800)     # command 2 streams 0-1, command 3 streams 2-3
CPU, PLAIN, RLE, RLE8 = 0, 1, 2, 3
PENS = {CPU: (1, 2), PLAIN: (3, 4), RLE: (5, 6), RLE8: (0x9a, 0xe5)}   # RLE8: 8-bit pens
COLOURS = {0: (2, 2, 6), 1: (0, 10, 0), 2: (8, 31, 8), 3: (12, 0, 0), 4: (31, 10, 10), 5: (0, 0, 14), 6: (10, 16, 31),
           0x9a: (14, 12, 0), 0xe5: (31, 31, 6)}

ALL = {   # name: (kind, source (label / stream), destination tile, shown from, origin, first label)
    'boot':      ('cpu', 0x100, 0x100, 0x100, CPU, 0x100),
    'over1':     ('dma0', 0x0000, 0x100, 0x100, PLAIN, 0x0000),
    'over2':     ('dma0', 0x1000, 0x100, 0x100, PLAIN, 0x1000),
    'fresh':     ('dma0', 0x2000, 0x4000, 0x4000, PLAIN, 0x2000),
    'cpu_off':   ('cpu_off', 0x7000, 0x100, 0x100, CPU, 0x7000),
    'dma0_off':  ('dma0_off', 0x3000, 0x100, 0x100, PLAIN, 0x3000),
    'rle1':      ('dma2', 0, 0x100, 0x100, RLE, RLE_LABEL[0]),
    'rle2':      ('dma2', 1, 0x100, 0x100, RLE, RLE_LABEL[1]),
    'rle8a':     ('dma3', 2, 0x100, 0x100, RLE8, RLE_LABEL[2]),
    'rle8b':     ('dma3', 3, 0x100, 0x100, RLE8, RLE_LABEL[3]),
    'cpu_on':    ('cpu', 0x7400, 0x100, 0x100, CPU, 0x7400),
}
DEFAULT = ['boot', 'over1', 'over2', 'fresh', 'cpu_off', 'dma0_off', 'rle1', 'rle2', 'rle8a', 'rle8b']


def steps():
    names = os.environ.get('DMAP_STEPS', ','.join(DEFAULT)).split(',')
    assert names[0] == 'boot'
    return [(n,) + ALL[n] for n in names]


def tile(label, origin):
    p0, p1 = PENS[origin]
    out = bytearray(256)
    for y in range(16):
        for x in range(16):
            bit = 15 - (y // 4 * 4 + x // 4)
            out[16 * y + x] = p1 if label >> bit & 1 else p0
    return bytes(out)


def rle(px):
    """command 2 data for the bytes px (all < 0x40): runs of 2 or more as a literal and one repeat byte"""
    out, i = bytearray(), 0
    while i < len(px):
        n = 1
        while i + n < len(px) and px[i + n] == px[i] and n < 65:
            n += 1
        out.append(px[i])
        if n > 1:
            out.append(0x40 | (n - 2))
        i += n
    return bytes(out)


# command 3 (MAME do_alt_char_dma, "8bpp"): a control byte for each 8 items, bit 7 first; item with its bit set: byte
# p, the table's pair (2 (p & 0x7f), + 1) as two bytes; clear: the byte itself. Each byte goes through ProcessByte8:
# after two equal bytes in a row the next one is a count, (count + 1) & 0xff more copies of that byte, and the pair
# state is reset. The table (TABLE_AT, set by command 4) holds PAIRS.
PAIRS = [(0x9a, 0xe5), (0xe5, 0x9a), (0xe5, 0xe5), (0x9a, 0x9a)]


def decode3(stream, n):
    """MAME do_alt_char_dma for the first n bytes out"""
    out, lastb, lastb2, i = [], 0xfffe, 0xffff, 0

    def put(b):
        nonlocal lastb, lastb2
        if lastb == lastb2:
            out.extend([lastb] * ((b + 1) & 0xff))
            lastb2 = 0xffff
        else:
            lastb2, lastb = lastb, b
            out.append(b)
    while True:
        ctrl = stream[i]
        i += 1
        for _ in range(8):
            p = stream[i]
            i += 1
            if ctrl & 0x80:
                a, b = PAIRS[p & 0x7f]
                put(a)
                put(b)
            else:
                put(p)
            ctrl = ctrl << 1 & 0xff
            if len(out) >= n:
                return bytes(out[:n])


def rle3(px):
    """command 3 data for px: runs of 3 or more as two bytes and a count, pairs from the table where the next two
    bytes form one, literals otherwise (built item by item against decode3's pair state)"""
    items = []                                  # (is a table item, byte)
    i, lastb, lastb2 = 0, 0xfffe, 0xffff
    while i < len(px):
        v = px[i]
        n = 1
        while i + n < len(px) and px[i + n] == v and n < 257:
            n += 1
        if lastb == lastb2:                     # a count is due (after a pair that ended equal): emit 0 more copies
            items.append((0, 0xff))
            lastb2 = 0xffff
            continue
        pair = i + 1 < len(px) and (v, px[i + 1]) in PAIRS and v != lastb   # else its second byte were a count
        if n >= 3 and v != lastb and not (pair and i // 256 % 2):   # odd tiles: table pairs first
            items += [(0, v), (0, v), (0, n - 3)]
            lastb2, lastb = 0xffff, v
            i += n
            continue
        if pair:
            items.append((1, PAIRS.index((v, px[i + 1]))))
            for b in (v, px[i + 1]):
                lastb2, lastb = lastb, b
            i += 2
            continue
        items.append((0, v))
        lastb2, lastb = lastb, v
        i += 1
    items += [(0, 0)] * (-len(items) % 8)
    out = bytearray()
    for k in range(0, len(items), 8):
        out.append(sum(t << (7 - j) for j, (t, _) in enumerate(items[k:k + 8])))
        out += bytes(b for _, b in items[k:k + 8])
    assert decode3(out, len(px)) == px
    return bytes(out)


def flash():
    """DMA byte a is file byte a ^ 1 of tools/mkcps3.py's user5 (measured in MAME, src/dtest.c)"""
    img = bytearray(RLE_AT + 0x80000 * len(RLE_LABEL))
    for t in range(FLASH_TILES):
        img[256 * t:256 * (t + 1)] = tile(t, PLAIN)
    for k, base in enumerate(RLE_LABEL):
        s = (rle if k < 2 else rle3)(b''.join(tile(base + i, RLE if k < 2 else RLE8) for i in range(N)))
        assert len(s) < 0x80000
        img[RLE_AT + 0x80000 * k:RLE_AT + 0x80000 * k + len(s)] = s
    img[TABLE_AT:TABLE_AT + 2 * len(PAIRS)] = bytes(b for p in PAIRS for b in p)   # command 3's pairs
    out = bytearray(len(img))
    out[0::2], out[1::2] = img[1::2], img[0::2]
    return bytes(out)


def header():
    st = steps()
    kinds = {'cpu': 0, 'dma0': 1, 'dma2': 2, 'dma3': 3}
    o = ['/* generated by tools/dmap.py */', '#include <stdint.h>', f'#define M_COLS {COLS}', f'#define M_ROWS {ROWS}',
         f'#define M_N {N}', f'#define M_STEP_FRAMES {STEP_FRAMES}', f'#define M_BLANK_FRAMES {BLANK_FRAMES}',
         f'#define M_STEPS {len(st)}', f'#define M_RLE_AT {RLE_AT:#x}', f'#define M_TABLE_AT {TABLE_AT:#x}',
         'struct m_step { uint8_t kind, off; uint16_t src, dest, shown, origin, label; };',
         'static const struct m_step m_step[M_STEPS] = {']
    for name, kind, src, dest, shown, origin, label in st:
        o.append(f'    {{{kinds[kind.replace("_off", "")]}, {int(kind.endswith("_off"))}, {src:#x}, {dest:#x}, '
                 f'{shown:#x}, {origin}, {label:#x}}},   /* {name} */')
    o.append('};')
    o.append(f'static const uint8_t m_pens[{len(PENS)}][2] = {{' +
             ', '.join(f'{{{a}, {b}}}' for a, b in PENS.values()) + '};')
    o.append(f'#define M_COLOURS_N {len(COLOURS)}')
    o.append('static const uint32_t m_colours[M_COLOURS_N] = {  /* pen << 16 | BGR555 */' +
             ', '.join(f'{p << 16 | (b << 10) | (g << 5) | r:#x}' for p, (r, g, b) in COLOURS.items()) + '};')
    return '\n'.join(o) + '\n'


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'dmap_scene.h'), 'w').write(header())
    f = flash()
    open(os.path.join(out, 'dmap.bin'), 'wb').write(f)
    with open(os.path.join(out, 'steps.txt'), 'w') as s:
        for name, kind, src, dest, shown, origin, label in steps():
            s.write(f'{name} {kind} {origin} {label}\n')
    print(f'{out}: {len(steps())} steps, graphics flash {len(f)} bytes')


if __name__ == '__main__':
    main()
