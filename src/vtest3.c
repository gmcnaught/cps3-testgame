/* CPS3 video test 3 (tools/vtest3.py's scene, through src/cps3v.c): objects as one main-list record each, pointing at
   sublists written once at the start (cps3v_put: as drawn and mirrored, low and high in sprite RAM) with the object's
   position and an optional colour code for all its pieces (cps3v_object); in the per-piece phases the same objects
   as entries of one record at position 0. Each phase's screen is compared with tools/vtest3.py's expect_<phase>.png
   (MAME snapshot, jtcps3 screenshot). */
#include "cps3v.h"
#include "vtest3_scene.h"

volatile uint32_t vbl_count;

static uint16_t pal_shadow[0x20000];

static void scene_upload(void)
{
    for (uint32_t i = 0; i < V3_COLOURS_N; i++)
        pal_shadow[v3_colours[i] >> 15] = (uint16_t)(v3_colours[i] & 0x7fff);
    cps3v_colours(0, pal_shadow, 0x20000);
    for (uint32_t i = 0; i < V3_TILES_N; i++)
        cps3v_tiles(v3_tiles_num[i], v3_tiles + 256 * i, 1);
#ifdef PAD_TILES                              /* jtcps3 check: PAD_TILES unused tiles written after the scene's */
    static const uint8_t pad[256];
    for (uint32_t i = 0; i < PAD_TILES; i++)
        cps3v_tiles(0x7f00 + i, pad, 1);
#endif
    for (int r = 0; r < 64; r++)
        for (int k = 0; k < 64; k++)
            cps3v_cell(CPS3V_MAP_UNIT(0), k, r, V3_CHECK_TILE, V3_CHECK_PAL, 0);
    for (int s = 0; s < V3_SUBS; s++)
        for (int j = 0; j < v3_sub[s].n; j++) {
            const struct v3_piece *p = &v3_piece[v3_sub[s].first + j];
            cps3v_put(v3_sub[s].addr + 16u * j, p->dx, p->dy, p->w, p->h, p->tile, p->pal, p->fx ? CPS3V_FLIPX : 0);
        }
}

static void scene_list(int ph)
{
    const struct v3_obj *o = v3_objs[v3_set[ph]];
    cps3v_begin();
    cps3v_band(0, 0, V3_BAND_LINES);
    for (int i = 0; i < v3_objs_n[v3_set[ph]]; i++, o++) {
        const struct v3_sub *s = &v3_sub[o->sub];
        if (!v3_pieces[ph] && !o->pieces) {
            cps3v_object(s->addr, s->n, o->x, o->y, o->pal);
            continue;
        }
        for (int j = 0; j < s->n; j++) {              /* the open record (a new one after an object record) */
            const struct v3_piece *p = &v3_piece[s->first + j];
            cps3v_sprite(o->x + p->dx, o->y + p->dy, p->w, p->h, p->tile, o->pal >= 0 ? (uint32_t)o->pal : p->pal,
                         p->fx ? CPS3V_FLIPX : 0);
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
    scene_list(0);
    for (;;) {
        cps3v_wait_vblank();
#ifdef FREEZE_AT
        if (frame >= FREEZE_AT)
            continue;                         /* still screen: no more video writes */
#endif
        int ph = (int)(frame / V3_PHASE_FRAMES);
        if (ph >= V3_PHASES)
            ph = V3_PHASES - 1;
        cps3v_vblank();
        cps3v_tilemap(0, 0, 0, CPS3V_MAP_UNIT(0), 1);
        for (int k = 1; k < 4; k++)
            cps3v_tilemap(k, 0, 0, CPS3V_MAP_UNIT(0), 0);
        scene_list(ph);
        frame++;
    }
}
