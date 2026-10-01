/* CPS3 video test 2 (tools/vtest2.py's scene, through src/cps3v.c): four tilemaps as bands back to front with
   sprites between them in depth order, tiles in all 8 character RAM banks, colour codes up to 0x1ff; per phase the
   tilemaps' scrolls and a sprite set; at the start of phase 4 part of character RAM and colour RAM is rewritten
   while the program runs (a port's room change). Each phase's screen is compared with tools/vtest2.py's
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

static void scene_upload(void)
{
    colours(v2_colours, V2_COLOURS_N, 1);
    tiles(v2_tiles_num, v2_tiles, V2_TILES_N);
    for (int k = 0; k < 4; k++)
        for (int r = 0; r < 64; r++)
            for (int c = 0; c < 64; c++) {
                uint32_t v = v2_maps[k][r * 64 + c];
                cps3v_cell(CPS3V_MAP_UNIT(k), c, r, v & 0xffff, (v >> 16) & 0x1ff,
                           (v & (1u << 25) ? CPS3V_FLIPX : 0) | (v & (1u << 26) ? CPS3V_FLIPY : 0));
            }
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
        int ph = (int)(frame / V2_PHASE_FRAMES);
        if (ph >= V2_PHASES)
            ph = V2_PHASES - 1;
        cps3v_vblank();
        for (int k = 0; k < 4; k++)
            cps3v_tilemap(k, v2_scroll[ph][k][0], v2_scroll[ph][k][1], CPS3V_MAP_UNIT(k), 1);
        if (v2_tileset[ph] && !loaded) {      /* the reload, while the display runs */
            tiles(v2_tiles_b_num, v2_tiles_b, V2_TILES_B_N);
            colours(v2_colours_b, V2_COLOURS_B_N, 0);
            loaded = 1;
        }
        scene_list(ph);
        frame++;
    }
}
