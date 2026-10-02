/* CPS3 video helpers (cps3v.h). Register layout and formulas: MAME 0.289 cps3.cpp (screen_update,
   draw_tilemapsprite_line, spritedma_w), checked by the Red Earth re-render (tools/cps3render.py) and by
   src/vtest.c against tools/vtest.py. Write widths follow Red Earth's (scripts/cps3_vlog.sh logs): PPU registers
   as 16-bit halves, colour RAM, SS RAM and sprite RAM as 32-bit words. */
#include "cps3v.h"

/* reads through the uncached mirror (0x2xxxxxxx), as the BIOS does: a cached read of a status register returns the
   cache line's old value (on jtcps3 the sprite-list wait in cps3v_vblank ran to its limit every frame) */
#define R16(a)    (*(volatile uint16_t *)((a) | 0x20000000u))
#define W16(a, v) (*(volatile uint16_t *)(a) = (uint16_t)(v))
#define W32(a, v) (*(volatile uint32_t *)(a) = (uint32_t)(v))
#define W8(a, v)  (*(volatile uint8_t *)(a) = (uint8_t)(v))
#define PPU       0x040c0000u
#define SPR       0x04000000u
#define COLOUR    0x04080000u
#define CHAR_WIN  0x04100000u
#define SSRAM     0x05040000u

static uint32_t main_n;           /* main-list records written */
static uint32_t sub_at;           /* next free sublist byte (256-aligned per group) */
static uint32_t grp_at, grp_n;    /* the open group's sublist start and entries */

void cps3v_wait_vblank(void)
{
    uint32_t v = vbl_count;
    while (vbl_count == v)
        ;
}

void cps3v_init(void)
{
    /* CRTC: 384 x 224, Red Earth's in-game values (boot values differ in 0x74 and the zoom size words) */
    static const uint16_t crtc[16] = { 0x002a, 0x006f, 0x01ef, 0x01c6, 0x0000, 0x0000, 0x03ff, 0x0040,
                                       0x0003, 0x0015, 0x00f5, 0x0106, 0x0000, 0x0000, 0x03ff, 0x0040 };
    for (int k = 0; k < 16; k++)
        W16(PPU + 0x60 + 2 * k, crtc[k]);
    W16(PPU + 0x80, 0x0063);          /* pixel clock / mode: Red Earth after its mode selection */
    W16(PPU + 0x84, 0x0800);
    W16(PPU + 0x88, 0x0000);
    W16(PPU + 0x8e, 0x00a0);
    W16(0x05000008, 0xc000);
    /* SS layer registers 0x00-0x14 (Red Earth's boot values), palette base 0xff: text colours from 0x1fe00 */
    static const uint8_t ss[] = { 0x2a, 0x3e, 0x00, 0x16, 0x02, 0xc6, 0x01, 0x00, 0x00, 0x03, 0x15, 0x00, 0xf6, 0x00,
                                  0x07, 0x01, 0x00, 0x00, 0xff, 0x03, 0x00 };
    for (unsigned k = 0; k < sizeof ss; k++)
        W8(0x05050001 + 2 * k, ss[k]);
    for (uint32_t n = 0; n < 0x4000; n++)   /* SS RAM: map, row scroll and tiles cleared (all transparent) */
        W32(SSRAM + 4 * n, 0);
    for (uint32_t a = 0; a < 0x40000; a += 4)  /* colour RAM: 128 K entries */
        W32(COLOUR + a, 0);
    for (int k = 0; k < 4; k++)
        W16(PPU + 0x26 + 0x10 * k, 0);   /* tilemaps off */
    cps3v_begin();
    cps3v_end();
    cps3v_vblank();
}

void cps3v_colours(uint32_t first, const uint16_t *bgr, uint32_t n)
{
    for (uint32_t i = 0; i < n; i += 2)
        W32(COLOUR + 2 * (first + i), ((uint32_t)bgr[i] << 16) | bgr[i + 1]);
}

/* character RAM: 8 MB, 1 MB a bank through the 0x04100000 window (bank in PPU 0x86); a tile is 256 bytes, pixels
   row by row, the left pixel of each word in bits 24-31 */
void cps3v_tiles(uint32_t first, const uint8_t *px, uint32_t n)
{
    uint32_t a = first * 256, end = a + n * 256, bank = ~0u;
    for (; a < end; a += 4, px += 4) {
        if (a >> 20 != bank) {
            bank = a >> 20;
            W16(PPU + 0x86, bank);
        }
        W32(CHAR_WIN + (a & 0xfffff), ((uint32_t)px[0] << 24) | ((uint32_t)px[1] << 16) | ((uint32_t)px[2] << 8) | px[3]);
    }
}

/* tilemap cell and sprite word 0: tile in bits 17-31, flips 12 / 11, 6-bit colour 9, colour code 0-8 */
static uint32_t word0(uint32_t tile, uint32_t pal, uint32_t flags)
{
    return (tile << 17) | (flags & (CPS3V_FLIPX | CPS3V_FLIPY | CPS3V_BPP6)) | (pal & 0x1ff);
}

void cps3v_cell(uint32_t unit, int col, int row, uint32_t tile, uint32_t pal, uint32_t flags)
{
    W32(SPR + unit * 0x1000 + ((row & 63) * 64 + (col & 63)) * 4, word0(tile, pal, flags));
}

/* MAME draw_tilemapsprite_line: screen line d shows map pixel row d + scroll_y + 4 + 16 (the "+ 1" tile row);
   screen column x shows map pixel column x + scroll_x. Width field 0x1f as Red Earth writes it (MAME ignores it). */
void cps3v_tilemap(int tm, int map_x, int map_y, uint32_t unit, int enable)
{
    uint32_t r = PPU + 0x20 + 0x10 * tm;
    W16(r + 0, map_x & 0x3ff);
    W16(r + 2, (map_y - 20) & 0x3ff);
    W16(r + 4, 0x001f);
    W16(r + 6, enable ? 0x8000 : 0);
    W16(r + 8, unit & 0x7f);          /* line-scroll base (high byte) unused: line scroll off */
}

void cps3v_begin(void)
{
    main_n = 0;
    sub_at = 0x2000;
    grp_n = 0;
    grp_at = sub_at;
}

/* closes the open group: a main-list record (global scroll 0, position 0, per-entry colour and depth) */
static void group_close(void)
{
    if (!grp_n)
        return;
    uint32_t m = SPR + main_n * 16;
    W32(m + 0, (grp_n << 16) | (grp_at >> 4));
    W32(m + 4, 0);
    W32(m + 8, 0);
    W32(m + 12, 0);
    main_n++;
    sub_at = (grp_at + grp_n * 16 + 255) & ~255u;
    grp_at = sub_at;
    grp_n = 0;
}

static void entry(uint32_t v1, uint32_t v2, uint32_t v3)
{
    if (grp_n == 511)                   /* a sublist holds at most 511 entries */
        group_close();
    uint32_t e = SPR + grp_at + grp_n * 16;
    W32(e + 0, v1);
    W32(e + 4, v2);
    W32(e + 8, v3);
    W32(e + 12, 0);
    grp_n++;
}

/* MAME screen_update, x size 0: the band's first screen line is ~(y + gscroll_y) - 18 = -y - 19 (global scroll 0);
   at most 128 lines an entry */
void cps3v_band(int tm, int top, int lines)
{
    while (lines > 0) {
        int n = lines > 128 ? 128 : lines;
        entry(0, (uint32_t)(-top - 19) & 0x3ff, ((uint32_t)(n - 1) << 24) | ((uint32_t)tm << 4) | (3 << 2));
        top += n;
        lines -= n;
    }
}

/* MAME screen_update, sprites (no zoom: draw size = 16 x tiles): left = x field - 8 w + 1, top = 1006 - y field
   - 8 h (global scroll 0, main-list position 0); size codes 1, 2, 3 = 1, 2, 4 tiles (0 = 8 tiles, not usable:
   x size 0 is a tilemap band, y size 0 draws nothing) */
static uint32_t word1(int x, int y, int w, int h)
{
    return ((uint32_t)(x + 8 * w - 1) & 0x3ff) << 16 | ((uint32_t)(1006 - y - 8 * h) & 0x3ff);
}
static uint32_t word2(int w, int h, uint32_t flags)
{
    static const uint8_t code[5] = { 0, 1, 2, 0, 3 };
    return ((uint32_t)(16 * h - 1) << 24) | ((uint32_t)(16 * w - 1) << 16) | (flags & CPS3V_W3_300 ? 0x300 : 0) |
           (code[h] << 2) | code[w];
}

void cps3v_sprite(int x, int y, int w, int h, uint32_t tile, uint32_t pal, uint32_t flags)
{
    entry(word0(tile, pal, flags), word1(x, y, w, h), word2(w, h, flags));
}

/* a prebuilt sublist's entry at byte addr of sprite RAM: the sprite as cps3v_sprite places it at (x, y) when its
   record's position is 0 */
void cps3v_put(uint32_t addr, int x, int y, int w, int h, uint32_t tile, uint32_t pal, uint32_t flags)
{
    uint32_t e = SPR + addr;
    W32(e + 0, word0(tile, pal, flags));
    W32(e + 4, word1(x, y, w, h));
    W32(e + 8, word2(w, h, flags));
    W32(e + 12, 0);
}

/* MAME screen_update: a record's position adds to its sprites' x and y fields (10 bits, wrapping) and y counts up;
   whichpal (word 2 bit 29) gives every sprite the record's colour code (bits 16-24) */
void cps3v_object(uint32_t addr, uint32_t n, int x, int y, int pal)
{
    group_close();
    uint32_t m = SPR + main_n * 16;
    W32(m + 0, (n << 16) | (addr >> 4));
    W32(m + 4, ((uint32_t)x & 0x3ff) << 16 | ((uint32_t)-y & 0x3ff));
    W32(m + 8, pal >= 0 ? 0x20000000u | ((uint32_t)pal & 0x1ff) << 16 : 0);
    W32(m + 12, 0);
    main_n++;
}

void cps3v_group(void)
{
    group_close();
}

void cps3v_end(void)
{
    group_close();
    W32(SPR + main_n * 16, 0x80000000u);
}

/* Red Earth's sequence: the 8 global scrolls, 8 / 9 four times to 0x82 (MAME copies the list on 8 after 9), wait for
   the copy (status 0x0c bit 0), then 0 */
void cps3v_vblank(void)
{
    for (int k = 0; k < 16; k++)
        W16(PPU + 2 * k, 0);
    for (int k = 0; k < 4; k++) {
        W16(PPU + 0x82, 8);
        W16(PPU + 0x82, 9);
    }
    for (int t = 0; t < 10000 && (R16(PPU + 0x0c) & 1); t++)
        ;
    W16(PPU + 0x82, 0);
}

/* text layer: SS RAM bytes 2n and 2n + 1 are bits 16-23 and 0-7 of the word at 0x05040000 + 4n (written as whole
   words, as the BIOS does); map cells (row * 64 + col) * 2, little-endian, tile in bits 0-8; 8x8 4-bit tiles from
   byte 0x4000, 32 bytes each, the left pixel of a byte in its low nibble; colours from 0x1fe00 (SS register 0x12) */
#include "font.h"
#define SSW(n, a, b) W32(SSRAM + 4 * (n), ((uint32_t)(a) << 16) | (b))

static uint8_t glyph_byte(int c, int y, int x)
{
    uint8_t r = font[c][y];
    return ((r >> (7 - x)) & 1) | (((r >> (6 - x)) & 1) << 4);
}

void cps3v_text_init(void)
{
    for (int c = 0; c < 64; c++)
        for (int y = 0; y < 8; y++)
            for (int x = 0; x < 8; x += 4)
                SSW((0x4000 + (32 + c) * 32 + y * 4 + x / 2) / 2, glyph_byte(c, y, x), glyph_byte(c, y, x + 2));
    W32(COLOUR + 2 * 0x1fe00, 0x00007fffu);    /* colour 0 transparent, 1 white */
}

void cps3v_text(int col, int row, const char *s)
{
    for (; *s; s++, col++)
        SSW(row * 64 + col, (uint8_t)*s, 0);
}
