/* CPS3 character RAM load experiments (tools/dmap.py): labelled tiles loaded by the CPU, by uncompressed character
   DMA (command 0) and by compressed character DMA (command 4 table, command 2 6-bit or 3 8-bit data), over the tiles on screen, into
   fresh tiles, and with the display list empty during the load; tilemap 0 shows 24 x 13 tiles from the step's first
   shown tile, whose labels tools/dmap_check.py reads off the screen. The DMA as src/dtest.c starts it (Red Earth's
   writes). After each load the tiles are read back: text row 26 shows "BAD <count>" on a difference. Text row 27:
   the step and the frame. */
#include "cps3v.h"
#include "dmap_scene.h"

volatile uint32_t vbl_count;

#define W16(a, v) (*(volatile uint16_t *)(a) = (uint16_t)(v))
#define W32(a, v) (*(volatile uint32_t *)(a) = (uint32_t)(v))
#define RD16(a)   (*(volatile uint16_t *)((a) | 0x20000000u))
#define RD32(a)   (*(volatile uint32_t *)((a) | 0x20000000u))
#define PPU       0x040c0000u
#define CHAR_WIN  0x04100000u
#define LIST      0x1000u
#define DMA_WAIT  4000000u

static uint16_t pal_shadow[0x20000];

/* tools/dmap.py tile() */
static void make_tile(uint8_t *px, uint32_t label, int origin)
{
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++)
            px[16 * y + x] = m_pens[origin][(label >> (15 - ((y >> 2) * 4 + (x >> 2)))) & 1];
}

static void hexs(char *b, uint32_t v, int n)
{
    for (int i = n - 1; i >= 0; i--, v >>= 4)
        b[i] = "0123456789ABCDEF"[v & 15];
}

static void verify(const struct m_step *s)
{
    static uint8_t px[256];
    uint32_t bad = 0;
    for (uint32_t i = 0; i < M_N; i++) {
        uint32_t a = (s->dest + i) * 256u;
        make_tile(px, s->label + i, s->origin);
        W16(PPU + 0x86, a >> 20);
        for (uint32_t q = 0; q < 256; q += 4) {
            uint32_t w = (uint32_t)px[q] << 24 | (uint32_t)px[q + 1] << 16 | (uint32_t)px[q + 2] << 8 | px[q + 3];
            if (RD32(CHAR_WIN + ((a + q) & 0xfffff)) != w)
                bad++;
        }
    }
    char b[] = "BAD 00000000";
    hexs(b + 4, bad, 8);
    cps3v_text(1, 26, bad ? b : "            ");
}

static uint32_t list_n;
static void rec(uint32_t cmd, uint32_t src, uint32_t dest_byte, uint32_t bytes)
{
    uint32_t a = CHAR_WIN + LIST + 12 * list_n++;
    W32(a + 0, cmd << 21 | ((bytes / 8u - 1u) & 0x1fffff));
    W32(a + 4, dest_byte / 8u);
    W32(a + 8, (src + 0x400000u) / 2u);
}

static uint32_t dma(void)
{
    W32(CHAR_WIN + LIST + 12 * list_n, 0x01000000u);
    list_n = 0;
    W16(PPU + 0x96, LIST / 4);
    W16(PPU + 0x98, 0x0040);
    uint32_t t = 0;
    while ((RD16(PPU + 0x0c) & 2) && ++t < DMA_WAIT)
        ;
    W32(0x05110000u, 0);
    return t;
}

static void load(const struct m_step *s)
{
    static uint8_t px[256];
    uint32_t t = 0;
    switch (s->kind) {
    case 0:
        for (uint32_t i = 0; i < M_N; i++) {
            make_tile(px, s->label + i, s->origin);
            cps3v_tiles(s->dest + i, px, 1);
        }
        break;
    case 1:
        W16(PPU + 0x86, 0);
        rec(0, 256u * s->src, 256u * s->dest, 256u * M_N);
        t = dma();
        break;
    case 2:
    case 3:                                   /* 6-bit (2) or 8-bit (3) compressed, after the table (4) */
        W16(PPU + 0x86, 0);
        rec(4, M_TABLE_AT, 0, 256);
        rec(s->kind, M_RLE_AT + 0x80000u * s->src, 256u * s->dest, 256u * M_N);
        t = dma();
        break;
    }
    if (t >= DMA_WAIT)
        cps3v_text(20, 26, "DMA BUSY");
    verify(s);
}

static void scene_list(int on)
{
    cps3v_begin();
    if (on)
        cps3v_band(0, 0, 16 * M_ROWS);
    cps3v_end();
}

int main(void)
{
    cps3v_init();
    for (int k = 0; k < M_COLOURS_N; k++)      /* colour code 1; entry 0 also the backdrop */
        pal_shadow[256 + (m_colours[k] >> 16)] = (uint16_t)m_colours[k];
    pal_shadow[0] = (uint16_t)m_colours[0];
    cps3v_colours(0, pal_shadow, 0x20000);
    cps3v_text_init();                        /* after the colours: its own at 0x1fe00 */
    load(&m_step[0]);
    __asm__ volatile("ldc %0, sr" : : "r"(0xa0));   /* IRL 12 (VBlank) on; IRL 10 (DMA end) polled */
    uint32_t frame = 0, shown = m_step[0].shown;
    int step_done = 0;
    for (;;) {
        cps3v_wait_vblank();
        int st = (int)(frame / M_STEP_FRAMES);
        if (st >= M_STEPS)
            st = M_STEPS - 1;
        uint32_t t = frame - (uint32_t)st * M_STEP_FRAMES;
        const struct m_step *s = &m_step[st];
        cps3v_vblank();
        int on = 1;
        if (st > step_done && frame < (uint32_t)M_STEPS * M_STEP_FRAMES) {
            if (!s->off || t == M_BLANK_FRAMES / 2) {
                load(s);
                step_done = st;
                shown = s->shown;
            }
        }
        if (s->off && t < M_BLANK_FRAMES)
            on = 0;
        /* the tilemap: cells from the shown tile, rewritten when it changes (unit 0, during VBlank) */
        static uint32_t cells_of = 0xffffffffu;
        if (cells_of != shown) {
            for (int r = 0; r < 64; r++)
                for (int c = 0; c < 64; c++)
                    cps3v_cell(CPS3V_MAP_UNIT(0), c, r, c < M_COLS && r < M_ROWS ? shown + r * M_COLS + c : 0, 1, 0);
            cells_of = shown;
        }
        cps3v_tilemap(0, 0, 0, CPS3V_MAP_UNIT(0), 1);
        for (int k = 1; k < 4; k++)
            cps3v_tilemap(k, 0, 0, CPS3V_MAP_UNIT(0), 0);
        scene_list(on);
        if (frame % 10 == 0) {
            char b[] = "STEP 00 FRAME 00000000";
            hexs(b + 5, (uint32_t)st, 2);
            hexs(b + 14, frame, 8);
            cps3v_text(1, 27, b);
        }
        frame++;
    }
}
