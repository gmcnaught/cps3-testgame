/* CPS3 wide 6-bit sprite probe (tools/wtest.py has the layout and why): character RAM tiles 0x1000-0x3fff, each
   labelled with its own number, loaded by character DMA from the graphics flash; then 6-bit and 8-bit sprites of
   1-4 tiles a side, some mirrored, every frame. tools/wtest_check.py reads which tile each sprite cell shows. A DMA
   that never ends is reported on text row 27. */
#include "cps3.h"
#include "wtest.h"

int main(void)
{
    cps3_init();
    uint16_t c[4];
    c[0] = W_BACKDROP, c[1] = 0;
    cps3v_colours(0, c, 2);
    c[0] = 0, c[1] = w_col6[0], c[2] = w_col6[1], c[3] = 0;
    cps3v_colours(W_P6 * 64, c, 4);
    c[1] = w_col8[0], c[2] = w_col8[1];
    cps3v_colours(W_P8 * 256, c, 4);
    for (uint32_t k = 0; k < W_TILES / 4096; k++)       /* 1 MB a record */
        cps3dma_char_copy(k << 20, W_TILE0 + 4096 * k, 4096);
    if (!cps3dma_char_run())
        cps3v_text(0, 27, "DMA END NOT SEEN");
    for (;;) {
        cps3v_wait_vblank();
        cps3v_vblank();
        cps3v_begin();
        for (int i = 0; i < W_N; i++) {
            const struct w_spr *s = &w_sprites[i];
            cps3v_sprite(s->x, s->y, s->w, s->h, s->base, s->bpp6 ? W_P6 : W_P8,
                         (s->bpp6 ? CPS3V_BPP6 : 0) | (s->flipx ? CPS3V_FLIPX : 0));
        }
        cps3v_end();
    }
}
