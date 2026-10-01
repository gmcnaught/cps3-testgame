/* CPS3 video test (tools/vtest.py's scene, through src/cps3v.c): colours, tiles and two tilemaps written by the
   CPU, the tilemaps drawn as bands, then sprites; tilemap 0's scroll changes every VT_PHASE_FRAMES frames. The
   screen of each phase is compared with tools/vtest.py's expect_<phase>.png (MAME snapshot, jtcps3 screenshot). */
#include "cps3v.h"
#include "vtest_scene.h"

volatile uint32_t vbl_count;

static uint16_t pal_shadow[0x600];

static void scene_upload(void)
{
    for (int i = 0; i < VT_COLOURS; i++)
        pal_shadow[vt_colours[i] >> 16] = (uint16_t)vt_colours[i];
    cps3v_colours(0, pal_shadow, 0x600);
    cps3v_tiles(0, vt_tiles, VT_TILES);
    for (int k = 0; k < 2; k++)
        for (int r = 0; r < 64; r++)
            for (int c = 0; c < 64; c++) {
                uint32_t v = vt_maps[k][r * 64 + c];
                cps3v_cell(CPS3V_MAP_UNIT(k), c, r, v & 0xffff, (v >> 16) & 0x1ff,
                           (v & (1u << 25) ? CPS3V_FLIPX : 0) | (v & (1u << 26) ? CPS3V_FLIPY : 0) |
                           (v & (1u << 27) ? CPS3V_BPP6 : 0));
            }
}

static void scene_list(int ph)
{
    cps3v_begin();
    cps3v_band(0, 0, CPS3V_H);
    cps3v_band(1, 0, CPS3V_H);
    for (int i = 0; i < VT_SPRITES; i++) {
        const struct vt_sprite *s = &vt_sprites[i];
        if (s->set != vt_set[ph])
            continue;
        cps3v_sprite(s->x, s->y, s->w, s->h, s->tile, s->pal,
                     (s->fx ? CPS3V_FLIPX : 0) | (s->fy ? CPS3V_FLIPY : 0) | (s->bpp6 ? CPS3V_BPP6 : 0) |
                     (s->w3 ? CPS3V_W3_300 : 0));
    }
    cps3v_end();
}

int main(void)
{
    cps3v_init();
    scene_upload();
    __asm__ volatile("ldc %0, sr" : : "r"(0));   /* interrupts on: VBlank (IRL 12) counts vbl_count */
    uint32_t frame = 0;
    scene_list(0);
    for (;;) {
        cps3v_wait_vblank();
#ifdef FREEZE_AT
        if (frame >= FREEZE_AT)
            continue;                         /* still screen: no more video writes */
#endif
        int ph = (int)(frame / VT_PHASE_FRAMES);
        if (ph >= VT_PHASES)
            ph = VT_PHASES - 1;
        cps3v_vblank();
        for (int k = 0; k < 2; k++)
            cps3v_tilemap(k, vt_scroll[ph][k][0], vt_scroll[ph][k][1], CPS3V_MAP_UNIT(k), 1);
        scene_list(ph);
        frame++;
    }
}
