#!/usr/bin/env python3
"""CPS3 timing test (src/ttest.c, src/ttest_k.S): CPU instruction timing, memory access per region, and the
character, palette, sprite-list and SH-2 DMAC transfer times, all counted with the SH7604 free-running timer (FRT,
on-chip, phi / 8: one tick = 8 CPU clocks). Written for comparison between MAME, jtcps3 and a real board; nothing
here is checked against hardware yet.

    ttest.py <out_dir>      -> <out_dir>/ttest.h (the test table, in display order)

Results go to the text layer (three columns of 16 cells, one test a line, updated as each test ends, so a test that
hangs the board leaves the earlier ones on screen) and to RAM at 0x02000000 (scripts/lua/ttest_dump.lua reads them in
MAME). A clock count of a million or more is shown in thousands ("12345K"); a value never seen, NEVER.
  frame   CPU clocks a frame (FRT ticks x 8 between VBlanks, 16 frames averaged), interrupts on
  iter    CPU clocks per loop iteration of the empty kernel (DT + BF, from this code location), x 100
  op      CPU clocks per operation (32 in each loop iteration), the location's empty-loop cost subtracted, x 100
  cdma    character DMA (list command 0, length bytes, from the graphics flash), three rows from one transfer: CPU clocks
          from the start write (0x040c0098) until status 0x040c000c bit 1 is first seen set (SET), then seen clear
          again (CLR), and until IRQ 10 is taken (IRQ: src/crt0.S irq10 reads FRC; IRL 10 unmasked during the wait)
  pdma    palette DMA (length colours), as cdma with status bit 2 and the start write 0x040c00ae
  sdma    sprite-list DMA (empty list): CPU clocks from the first 8 / 9 write to 0x040c0082 until status bit 0 reads 0
  dmac    SH-2 DMAC channel 0 (auto request, bytes): CPU clocks from CHCR0 DE = 1 until TE = 1
  during  as op, measured while a 1 MB character DMA runs, IRL 10 and VBlank unmasked; BUSYAFT: 1 = status bit 1 still
          set at the end; IRQDUR: 1 = IRQ 10 came during the measurement
  stuck   DMAs of this pass (cdma, pdma, during) whose status bit was already set before the start write
A DMA wait ends when IRQ 10 has come and the bit reads clear, 2^19 ticks (4.2 M clocks at phi / 8) after the first of
the two if the other never comes, or after 2^22 ticks.

Code locations: S = SIMM 1 through the cache (0x06000000), SU = SIMM 1 cache-through (0x26000000), CR = SH-2 cache
RAM (0xc0000000; the cache in two-way mode: CCR 0x19). MAME decrypts opcodes fetched from cache RAM (cps3.cpp
sh2cache_ram_w), so the kernel copied there is encrypted for its address first. Memory regions are read through
their cache-through mirrors (0x2xxxxxxx) unless the name ends in C.

MAME 0.289 (refs/cps3/mame/cps3.cpp): character and palette DMA keep their status bit set for a fixed 100 us and the
sprite-list DMA for 4 us ("delay time is a hack"), whatever the length. MAME's SH-2 has no bus wait states and no
cache (docs/CPS3.md).
"""
import sys

import mkcps3

# SH7604 programming manual (refs: SH1_SH2_Programming_Manual_1995.pdf), table 5.x / section 7: execution states with
# no wait states and no contention; None: depends on the board (bus widths, wait states, external WAIT)
TESTS = [
    # name (<= 8 chars), kind, kernel / DMA event / DMAC mode, location, address / length, manual
    ('FRAME', 'frame', None, None, 0, None),
    ('ITER S', 'iter', 'k_empty', 'S', 0, '4 (DT 1 + BF taken 3)'),
    ('NOP', 'op', 'k_nop', 'S', 0, '1'),
    ('ADD', 'op', 'k_add', 'S', 0, '1'),
    ('DIV1', 'op', 'k_div1', 'S', 0, '1'),
    ('MUL.L', 'op', 'k_mull', 'S', 0, '2-4 (back to back: multiplier contention)'),
    ('DMULS.L', 'op', 'k_dmuls', 'S', 0, '2-4 (back to back: multiplier contention)'),
    ('MULS.W', 'op', 'k_mulsw', 'S', 0, '1-3 (back to back: multiplier contention)'),
    ('LD+NOUSE', 'op', 'k_ldnouse', 'S', 0x02040000, '2 (cache hit; MOV.L + ADD)'),
    ('LD+USE', 'op', 'k_lduse', 'S', 0x02040000, '3 (cache hit; load-use slot, 7.5)'),
    ('BRA+NOP', 'op', 'k_bra', 'S', 0, '3 (BRA 2 + delay slot 1)'),
    ('BF TAKEN', 'op', 'k_bft', 'S', 0, '3'),
    ('BT NOTTK', 'op', 'k_btn', 'S', 0, '1'),
    ('LD MRAMC', 'op', 'k_ldl', 'S', 0x02040000, '1 (cache hit)'),
    ('LD MRAM', 'op', 'k_ldl', 'S', 0x22040000, None),
    ('ST MRAM', 'op', 'k_stl', 'S', 0x22040000, None),
    ('ST MRAMC', 'op', 'k_stl', 'S', 0x02040000, None),
    ('LD BIOS', 'op', 'k_ldl', 'S', 0x20000000, None),
    ('LD SIMM1', 'op', 'k_ldl', 'S', 0x26000000, None),
    ('LD SPR', 'op', 'k_ldl', 'S', 0x24030000, None),
    ('ST SPR', 'op', 'k_stl', 'S', 0x24030000, None),
    ('LD COL', 'op', 'k_ldl', 'S', 0x240a0000, None),
    ('ST COL', 'op', 'k_stl', 'S', 0x240a0000, None),
    ('LD CHR', 'op', 'k_ldl', 'S', 0x24180000, None),
    ('ST CHR', 'op', 'k_stl', 'S', 0x24180000, None),
    ('LD SS', 'op', 'k_ldl', 'S', 0x2504e000, None),
    ('ST SS', 'op', 'k_stl', 'S', 0x2504e000, None),
    ('LDW PPUS', 'op', 'k_ldw', 'S', 0x240c000c, None),
    ('LD INPUT', 'op', 'k_ldl', 'S', 0x25000000, None),
] + [(f'C{n} {e}', 'cdma', e.lower(), None, b, None)
     for n, b in (('256', 256), ('4K', 4096), ('64K', 65536), ('1M', 1 << 20)) for e in ('SET', 'CLR', 'IRQ')] + [
    (f'P{n} {e}', 'pdma', e.lower(), None, b, None) for n, b in (('256', 256), ('8K', 8192)) for e in ('SET', 'CLR', 'IRQ')
] + [
    ('SDMA', 'sdma', None, None, 0, None),
    ('DMAC B', 'dmac', 'burst', None, 0x02040000, None),
    ('DMAC C', 'dmac', 'steal', None, 0x02040000, None),
    ('DMAC 16', 'dmac', 'burst16', None, 0x02040000, None),
    ('DMAC SIM', 'dmac', 'burst', None, 0x06000000, None),
    ('LD M DMA', 'during', 'k_ldl', 'S', 0x22040000, None),
    ('LD S DMA', 'during', 'k_ldl', 'S', 0x24030000, None),
    ('BUSYAFT', 'busy', None, None, 0, None),
    ('IRQDUR', 'irqdur', None, None, 0, None),
    ('STUCK', 'stuck', None, None, 0, None),
    # code locations last: a fetch the board cannot decrypt stops the program here
    ('ITER SU', 'iter', 'k_empty', 'SU', 0, '4 (+ fetch wait states)'),
    ('NOP SU', 'op', 'k_nop', 'SU', 0, None),
    ('ITER CR', 'iter', 'k_empty', 'CR', 0, '4'),
    ('NOP CR', 'op', 'k_nop', 'CR', 0, '1'),
    ('LD CR', 'op', 'k_ldl', 'CR', 0xc0000300, '1'),
    ('ST CR', 'op', 'k_stl', 'CR', 0xc0000300, '1'),
]
EVENTS = {'set': 0, 'clr': 1, 'irq': 2}
DMAC_CHCR = {'burst': 0x5a11, 'steal': 0x5a01, 'burst16': 0x5e11}   # DM inc, SM inc, TS long / 16-byte, AR, TB, DE
DMAC_BYTES = 4096
ROWS = 26          # text rows per column (rows 2-27)
COLS, CELL = 3, 16 # columns of 16 cells: name (8), space, value (6), space
KINDS = ['frame', 'iter', 'op', 'cdma', 'pdma', 'sdma', 'dmac', 'during', 'busy', 'irqdur', 'stuck']
LOCS = ['S', 'SU', 'CR']
KERNELS = ['k_empty', 'k_nop', 'k_add', 'k_div1', 'k_mull', 'k_dmuls', 'k_mulsw', 'k_ldnouse', 'k_lduse', 'k_bra',
           'k_bft', 'k_btn', 'k_ldl', 'k_ldw', 'k_stl']


def main():
    out = sys.argv[1]
    assert len(TESTS) <= COLS * ROWS
    for t in TESTS:
        assert len(t[0]) <= 8 and all(32 <= ord(c) < 96 for c in t[0]), t[0]
    L = ['/* tools/ttest.py: the test table */']
    L += [f'#define TT_{k.upper()} {i}' for i, k in enumerate(KINDS)]
    L += [f'#define LOC_{k} {i}' for i, k in enumerate(LOCS)]
    L.append(f'#define TT_N {len(TESTS)}')
    L.append(f'#define TT_ROWS {ROWS}')
    L.append(f'#define TT_CELL {CELL}')
    L.append(f'#define KEY1 0x{mkcps3.KEY1:08x}u    /* tools/mkcps3.py: opcodes fetched from cache RAM are decrypted */')
    L.append(f'#define KEY2 0x{mkcps3.KEY2:08x}u')
    L.append(f'#define TT_DMAC_BYTES {DMAC_BYTES}')
    L.append('extern const char ' + ', '.join(f'{k}[], {k}_end[]' for k in KERNELS) + ';')
    L.append('static const struct tt tt_tests[TT_N] = {')
    for name, kind, kern, loc, addr, _ in TESTS:
        if kind == 'dmac':
            k, v = '0, 0', DMAC_CHCR[kern]
        elif kind in ('cdma', 'pdma'):
            k, v = '0, 0', EVENTS[kern]
        else:
            k, v = (f'{kern}, {kern}_end' if kern else '0, 0'), 0
        L.append(f'    {{ "{name}", TT_{kind.upper()}, LOC_{loc or "S"}, {k}, 0x{addr:08x}u, 0x{v:04x}u }},')
    L.append('};')
    open(f'{out}/ttest.h', 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
