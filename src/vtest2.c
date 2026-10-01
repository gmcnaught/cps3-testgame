/* CPS3 video test 2 (tools/vtest2.py's scene, through src/cps3v.c): four tilemaps as bands back to front with
   sprites between them in depth order, tiles in all 8 character RAM banks, colour codes up to 0x1ff; per phase the
   tilemaps' scrolls and a sprite set; at the start of the last phase part of character RAM and colour RAM is rewritten
   while the program runs (a port's room change), at the start of the last phase; the tiles and colours are read back
   after each upload. Each phase's screen is compared with tools/vtest2.py's
   expect_<phase>.png (MAME snapshot, jtcps3 screenshot). */
#include "cps3v.h"
#include "vtest2_scene.h"

volatile uint32_t vbl_count;

static uint16_t pal_shadow[0x20000];

static void colours(const uint32_t *c, uint32_t n, int all)
{
    for (uint32_t i = 0; i < n; i++)
        pal_shadow[c[i] >> 15] = (uint16_t)(c[i] & 0x7fff);
    if (all) {
        cps3v_colours(0, pal_shadow, 0x20000);
        return;
    }
    for (uint32_t i = 0; i < n; i++) {
        uint32_t e = (c[i] >> 15) & ~1u;
        cps3v_colours(e, &pal_shadow[e], 2);
    }
}

static void tiles(const uint16_t *num, const uint8_t *px, uint32_t n)
{
    for (uint32_t i = 0; i < n; i++)
        cps3v_tiles(num[i], px + 256 * i, 1);
}

/* read-back: character RAM (through the bank window) and colour RAM read through the uncached mirror and compared
   with what was written; on a difference the text layer shows the count and the first tile / colour (MAME: none,
   so the expected screens have no text) */
#define RD32(a) (*(volatile uint32_t *)((a) | 0x20000000u))
#define RD16(a) (*(volatile uint16_t *)((a) | 0x20000000u))
static int text_on;
static void hexs(char *b, uint32_t v, int n)
{
    for (int i = n - 1; i >= 0; i--, v >>= 4)
        b[i] = "0123456789ABCDEF"[v & 15];
}
static void report(int row, const char *what, uint32_t bad, uint32_t first)
{
    char b[] = "TILES  BAD 00000000 FIRST 00000000";
    for (int i = 0; i < 6 && what[i]; i++)
        b[i] = what[i];
    hexs(b + 11, bad, 8);
    hexs(b + 26, first, 8);
    if (!text_on) {
        cps3v_text_init();
        text_on = 1;
    }
    cps3v_text(1, row, b);
}
static void verify(int row, const uint16_t *num, const uint8_t *px, uint32_t n, const uint32_t *c, uint32_t nc)
{
    uint32_t bad = 0, first = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t a = num[i] * 256u;
        *(volatile uint16_t *)(0x040c0086u) = (uint16_t)(a >> 20);
        for (uint32_t k = 0; k < 256; k += 4) {
            const uint8_t *q = px + 256 * i + k;
            uint32_t w = (uint32_t)q[0] << 24 | (uint32_t)q[1] << 16 | (uint32_t)q[2] << 8 | q[3];
            if (RD32(0x04100000u + ((a + k) & 0xfffff)) != w && !bad++)
                first = num[i];
        }
    }
    if (bad)
        report(row, "TILES", bad, first);
    bad = 0;
    for (uint32_t i = 0; i < nc; i++)
        if ((RD16(0x04080000u + 2 * (c[i] >> 15)) & 0x7fff) != (c[i] & 0x7fff) && !bad++)
            first = c[i] >> 15;
    if (bad)
        report(row + 1, "COLOUR", bad, first);
}

static void cell(uint32_t unit, int c, int r, uint32_t v)
{
    cps3v_cell(unit, c, r, v & 0xffff, (v >> 16) & 0x1ff,
               (v & (1u << 25) ? CPS3V_FLIPX : 0) | (v & (1u << 26) ? CPS3V_FLIPY : 0));
}

/* column streaming (phases with v2_stream): tilemap 1 shows the 256-column level through unit 5's 64 columns; every
   level column that the next frame shows (and one beyond) is written into map column (column mod 64) if that map
   column holds another one */
static int16_t streamed[64];

static void stream_reset(void)
{
    for (int c = 0; c < 64; c++)
        streamed[c] = -1;
}

static void stream_to(int x)
{
    for (int c = x / 16; c <= (x + CPS3V_W) / 16 + 1 && c < V2_LEVEL_W; c++)
        if (streamed[c & 63] != c) {
            for (int r = 0; r < 64; r++)
                cell(CPS3V_MAP_UNIT(5), c & 63, r, v2_level[r][c]);
            streamed[c & 63] = (int16_t)c;
        }
}

static int stream_x(uint32_t t)
{
    return V2_STREAM_PX * (int)(t < V2_STREAM_FRAMES ? t : V2_STREAM_FRAMES);
}

static void scene_upload(void)
{
    colours(v2_colours, V2_COLOURS_N, 1);
    tiles(v2_tiles_num, v2_tiles, V2_TILES_N);
    cps3v_tiles(V2_TILES_C, v2_tiles_c, V2_TILES_C_N);     /* one call across a bank boundary */
    for (int k = 0; k < V2_UNITS; k++)
        for (int r = 0; r < 64; r++)
            for (int c = 0; c < 64; c++)
                cell(CPS3V_MAP_UNIT(k), c, r, v2_maps[k][r * 64 + c]);
    verify(22, v2_tiles_num, v2_tiles, V2_TILES_N, v2_colours, V2_COLOURS_N);
}

static void scene_list(int ph)
{
    cps3v_begin();
    for (int k = 0; k < V2_BANDS; k++) {
        cps3v_band(v2_bands[k][0], v2_bands[k][1], v2_bands[k][2]);
        for (int i = 0; i < V2_SPRITES; i++) {
            const struct v2_sprite *s = &v2_sprites[i];
            if (s->set == v2_set[ph] && s->slot == k + 1)
                cps3v_sprite(s->x, s->y, s->w, s->h, s->tile, s->pal,
                             (s->fx ? CPS3V_FLIPX : 0) | (s->fy ? CPS3V_FLIPY : 0));
        }
        if (v2_groups[ph])
            cps3v_group();
    }
    cps3v_end();
}

int main(void)
{
    cps3v_init();
    scene_upload();
    __asm__ volatile("ldc %0, sr" : : "r"(0));   /* interrupts on: VBlank (IRL 12) counts vbl_count */
    uint32_t frame = 0;
    int loaded = 0;
    scene_list(0);
    for (;;) {
        cps3v_wait_vblank();
#ifdef FREEZE_AT
        if (frame >= FREEZE_AT)
            continue;                         /* still screen: no more video writes */
#endif
        int ph = (int)(frame / V2_PHASE_FRAMES);
        if (ph >= V2_PHASES)
            ph = V2_PHASES - 1;
        cps3v_vblank();
        uint32_t t = frame - (uint32_t)ph * V2_PHASE_FRAMES;  /* frame within the phase */
        for (int k = 0; k < 4; k++) {
            int x = v2_scroll[ph][k][0];
            if (v2_stream[ph] && k == 1)
                x = stream_x(t);
            cps3v_tilemap(k, x, v2_scroll[ph][k][1], CPS3V_MAP_UNIT(v2_units[ph][k]), v2_enable[ph][k]);
        }
        if (v2_stream[ph]) {                  /* the columns the next frame shows, written during this one */
            if (t == 0)
                stream_reset();
            stream_to(stream_x(t + 1));
        }
        if (v2_tileset[ph] && !loaded) {      /* the reload, while the display runs */
            tiles(v2_tiles_b_num, v2_tiles_b, V2_TILES_B_N);
            colours(v2_colours_b, V2_COLOURS_B_N, 0);
            verify(25, v2_tiles_b_num, v2_tiles_b, V2_TILES_B_N, v2_colours_b, V2_COLOURS_B_N);
            loaded = 1;
        }
        scene_list(ph);
        frame++;
    }
}
