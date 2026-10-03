/* CPS3 character DMA test (tools/dtest.py's scene, through sdk/src/cps3v.c): tiles copied from the graphics flash
   (SIMM 3) into character RAM by the character DMA (list command 0, uncompressed) while the display runs, over tiles
   on screen, into tiles never drawn, one small copy a frame, and 1 MB in one record. The DMA list is written into
   character RAM at byte 0x1000 and started as Red Earth does (scripts/cps3_vlog.sh: 16-bit writes, 0x040c0096 = list
   word address, 0x040c0098 = 0x0040); MAME cps3.cpp process_character_dma reads it. After each DMA the copied tiles
   are read back; a difference, or a DMA still busy after the wait, is reported on the text layer. Each phase's screen
   is compared with tools/dtest.py's expect_<phase>.png (MAME snapshot, jtcps3 screenshot). */
#include "cps3v.h"
#include "dtest_scene.h"

/* jtcps3 check: D2_BASE=<tile> puts phase 2's tiles there instead of tools/dtest.py's (the expected screens stay) */
#ifndef D2_BASE
#define D2_BASE 0
#endif
#define BASE(ph) ((ph) == 2 && D2_BASE ? (uint32_t)D2_BASE : (uint32_t)d_base[ph])

volatile uint32_t vbl_count;

#define W16(a, v) (*(volatile uint16_t *)(a) = (uint16_t)(v))
#define W32(a, v) (*(volatile uint32_t *)(a) = (uint32_t)(v))
#define RD16(a)   (*(volatile uint16_t *)((a) | 0x20000000u))
#define RD32(a)   (*(volatile uint32_t *)((a) | 0x20000000u))
#define PPU       0x040c0000u
#define CHAR_WIN  0x04100000u
#define LIST      0x1000u                 /* the DMA list's character RAM byte address (Red Earth's) */
#define DMA_WAIT  4000000u                /* status polls before giving up */

static uint16_t pal_shadow[0x20000];

/* tools/dtest.py pen() */
static uint8_t pen(int k, int j, int x, int y)
{
    if (x == 0 || y == 0)
        return 250;
    return (uint8_t)(1 + 48 * k + (((x >> 2) + (y >> 2) + j) & 1) * 24 + j % 24);
}

static void make_tile(uint8_t *px, int k, int j)
{
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++)
            px[16 * y + x] = pen(k, j, x, y);
}

/* tools/dtest.py big_tile(): phase 4's record, tile i */
static void make_big(uint8_t *px, int i)
{
    int j = D_BIG_DEST + i - BASE(4);
    if (j >= 0 && j < D_N)
        make_tile(px, 4, j);
    else
        make_tile(px, 0, i + 1000);
}

/* text layer reports (MAME: none) */
static int text_on;
static void hexs(char *b, uint32_t v, int n)
{
    for (int i = n - 1; i >= 0; i--, v >>= 4)
        b[i] = "0123456789ABCDEF"[v & 15];
}
static void report(int row, const char *what, uint32_t a, uint32_t b)
{
    char s[] = "P0 ...... 00000000 00000000";
    s[1] = (char)('0' + row);
    for (int i = 0; i < 6 && what[i]; i++)
        s[3 + i] = what[i];
    hexs(s + 10, a, 8);
    hexs(s + 19, b, 8);
    if (!text_on) {
        cps3v_text_init();
        text_on = 1;
    }
    cps3v_text(1, 2 + row, s);
}

/* the n tiles from first equal set k from tile j0 (big: phase 4's record from its tile 0) */
static void verify(int row, uint32_t first, uint32_t n, int k, int j0, int big)
{
    static uint8_t px[256];
    uint32_t bad = 0, at = 0;
#ifdef NO_VERIFY                              /* jtcps3 check: no read-back */
    return;
#endif
    for (uint32_t i = 0; i < n; i++) {
        uint32_t a = (first + i) * 256u;
        if (big)
            make_big(px, (int)i);
        else
            make_tile(px, k, j0 + (int)i);
        W16(PPU + 0x86, a >> 20);
        for (uint32_t q = 0; q < 256; q += 4) {
            uint32_t w = (uint32_t)px[q] << 24 | (uint32_t)px[q + 1] << 16 | (uint32_t)px[q + 2] << 8 | px[q + 3];
            if (RD32(CHAR_WIN + ((a + q) & 0xfffff)) != w && !bad++)
                at = first + i;
        }
    }
    if (bad)
        report(row, "TILES", bad, at);
}

/* list records (MAME process_character_dma): word 0 command << 21 | (length / 8 - 1), bit 24 = end of list;
   word 1 destination / 8; word 2 (source + 0x400000) / 2, the source counted from the graphics flash's start */
static uint32_t list_n;
static void rec(uint32_t src, uint32_t dest_tile, uint32_t tiles)
{
    uint32_t a = CHAR_WIN + LIST + 12 * list_n++;
    W32(a + 0, (tiles * 256u / 8u - 1u) & 0x1fffff);
    W32(a + 4, dest_tile * 256u / 8u);
    W32(a + 8, (src + 0x400000u) / 2u);
}

/* closes the list, starts the DMA and waits for status bit 1 to clear; then acknowledges IRQ 10 */
static void dma(int row)
{
    W32(CHAR_WIN + LIST + 12 * list_n, 0x01000000u);
    list_n = 0;
    W16(PPU + 0x96, LIST / 4);
    W16(PPU + 0x98, 0x0040);
    uint32_t t = 0;
    while ((RD16(PPU + 0x0c) & 2) && ++t < DMA_WAIT)
        ;
    W32(0x05110000u, 0);
    if (t >= DMA_WAIT)
        report(row, "BUSY", t, RD16(PPU + 0x0c));
}

static void scene_list(int ph)
{
    uint32_t b = BASE(ph);
    cps3v_begin();
    cps3v_band(0, 0, D_BAND_LINES);
    for (int s = 0; s < D_NSPR; s++)
        cps3v_sprite(16 * (s % D_COLS), s < D_COLS ? D_SPR_Y0 : D_SPR_Y1, 1, 1, b + D_COLS * D_ROWS + s, D_PAL, 0);
    cps3v_end();
}

/* the phase's DMA, at its first frame t = 0 (phase 3: frames 0 .. D_STREAM_FRAMES - 1) */
static void phase_dma(int ph, uint32_t t)
{
#ifdef SKIP_DMA                               /* jtcps3 check: bit ph set = no DMA in phase ph */
    if (SKIP_DMA & (1 << ph))
        return;
#endif
    switch (ph) {
    case 1:
        W16(PPU + 0x86, 0);                   /* the list's bank */
        rec(D_SRC_B, BASE(1), D_COLS * D_ROWS);
        rec(D_SRC_B + 256u * D_COLS * D_ROWS, BASE(1) + D_COLS * D_ROWS, D_NSPR);
        dma(1);
        verify(1, BASE(1), D_N, 1, 0, 0);
        break;
    case 2:
        W16(PPU + 0x86, 0);
        rec(D_SRC_C, BASE(2), D_N);
        dma(2);
        verify(2, BASE(2), D_N, 2, 0, 0);
        break;
    case 3:
        if (t >= D_STREAM_FRAMES)
            break;
        W16(PPU + 0x86, 0);
        rec(D_SRC_D + 256u * D_STREAM_TILES * t, BASE(3) + D_STREAM_TILES * t, D_STREAM_TILES);
        dma(3);
        if (t == D_STREAM_FRAMES - 1)
            verify(3, BASE(3), D_N, 3, 0, 0);
        break;
    case 4:
        W16(PPU + 0x86, 0);
        rec(D_SRC_BIG, D_BIG_DEST, D_BIG_N);
        dma(4);
        verify(4, D_BIG_DEST, D_BIG_N, 0, 0, 1);
        break;
    }
}

int main(void)
{
    static uint8_t px[256];
    cps3v_init();
    for (uint32_t i = 0; i < D_COLOURS_N; i++)
        pal_shadow[d_colours[i] >> 15] = (uint16_t)(d_colours[i] & 0x7fff);
    cps3v_colours(0, pal_shadow, 0x20000);
    for (int j = 0; j < D_N; j++) {           /* set A by the CPU */
        make_tile(px, 0, j);
        cps3v_tiles(BASE(0) + j, px, 1);
    }
    verify(0, BASE(0), D_N, 0, 0, 0);
    for (int u = 0; u < 3; u++) {             /* map units 0-2: the tilemap from tile 0x100, 0x4000, 0xfa0 */
        static const int ph_of_unit[3] = { 0, 2, 4 };
        for (int r = 0; r < 64; r++)
            for (int c = 0; c < 64; c++)
                cps3v_cell(CPS3V_MAP_UNIT(u), c, r,
                           c < D_COLS && r < D_ROWS ? BASE(ph_of_unit[u]) + r * D_COLS + c : BASE(0),
                           D_PAL, 0);
    }
    /* interrupts above level 10: VBlank (IRL 12) counts vbl_count; IRL 10 (DMA end) stays masked, polled instead */
#ifndef SR_MASK
#define SR_MASK 0xa0
#endif
    __asm__ volatile("ldc %0, sr" : : "r"(SR_MASK));
    uint32_t frame = 0;
    scene_list(0);
    for (;;) {
        cps3v_wait_vblank();
#ifdef FREEZE_AT
        if (frame >= FREEZE_AT)
            continue;                         /* still screen: no more video writes */
#endif
        int ph = (int)(frame / D_PHASE_FRAMES);
        if (ph >= D_PHASES)
            ph = D_PHASES - 1;
        uint32_t t = frame - (uint32_t)ph * D_PHASE_FRAMES;
        cps3v_vblank();
#ifdef NO_SWITCH                              /* jtcps3 check: tilemap 0 stays on map unit 0 */
        cps3v_tilemap(0, 0, 0, CPS3V_MAP_UNIT(0), 1);
#else
        cps3v_tilemap(0, 0, 0, CPS3V_MAP_UNIT(ph == 2 ? 1 : ph == 4 ? 2 : 0), 1);
#endif
        for (int k = 1; k < 4; k++)
            cps3v_tilemap(k, 0, 0, CPS3V_MAP_UNIT(0), 0);
        if (frame < D_PHASES * D_PHASE_FRAMES && (t == 0 || ph == 3))
            phase_dma(ph, t);
        scene_list(ph);
#ifdef SHOW_FRAME                             /* jtcps3 check: the frame number at the bottom right */
        if (frame % 30 == 0) {
            char f[] = "F00000000";
            if (!text_on) {
                cps3v_text_init();
                text_on = 1;
            }
            hexs(f + 1, frame, 8);
            cps3v_text(38, 26, f);
        }
#endif
        frame++;
    }
}
