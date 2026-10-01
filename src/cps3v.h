/* CPS3 video helpers (docs/CPS3.md "Video"): colour RAM, character RAM, tilemaps and the display list, all in
   screen coordinates (x right, y down, 0,0 = top-left of the 384x224 screen). The CPS3 register formulas live in
   cps3v.c only; tools/vtest.py checks them against an independently composed screen. */
#ifndef CPS3V_INCLUDED
#define CPS3V_INCLUDED
#include <stdint.h>

/* the screen, and sprite RAM layout used here: main list 0x0000-0x1fff, sublists from 0x2000, tilemaps in
   4 KB units (64 x 64 cells of 4 bytes = 4 units each) from unit 0x40 (byte 0x40000) */
#define CPS3V_W 384
#define CPS3V_H 224
#define CPS3V_MAP_UNIT(k) (0x40 + 4 * (k))     /* tilemap data k (0-15) */

/* sprite and tilemap-cell flags */
#define CPS3V_FLIPX 0x1000u
#define CPS3V_FLIPY 0x0800u
#define CPS3V_BPP6  0x0200u                     /* colour code x 64 instead of x 256 */
#define CPS3V_W3_300 0x10000u                   /* sprites: word 3 bits 8-9 set (Red Earth's 6-bit sprites; tests) */

void cps3v_init(void);                          /* CRTC, SS layer cleared, empty display list */
void cps3v_colours(uint32_t first, const uint16_t *bgr, uint32_t n);   /* first and n even: 32-bit writes */
void cps3v_tiles(uint32_t first, const uint8_t *px, uint32_t n);       /* 16x16 8-bit tiles, 256 bytes each */
/* tilemap cell (col, row 0-63) of tilemap data unit */
void cps3v_cell(uint32_t unit, int col, int row, uint32_t tile, uint32_t pal, uint32_t flags);
/* tilemap tm (0-3) registers: the map pixel (0-1023) shown at the screen's top-left, data unit, on/off;
   written to the PPU at once (call during VBlank) */
void cps3v_tilemap(int tm, int map_x, int map_y, uint32_t unit, int enable);

/* display list, drawn in order (later on top); built during the frame, sent by cps3v_vblank() */
void cps3v_begin(void);
void cps3v_band(int tm, int top, int lines);    /* tilemap tm on screen lines top .. top + lines - 1 */
/* w, h in tiles (1, 2 or 4); tiles numbered column by column from tile; (x, y) = top-left pixel */
void cps3v_sprite(int x, int y, int w, int h, uint32_t tile, uint32_t pal, uint32_t flags);
void cps3v_group(void);                         /* later entries in a new main-list record (sublist) */
void cps3v_end(void);
/* at VBlank: global scrolls, the sprite-list DMA of the last finished list */
void cps3v_vblank(void);

/* SS text layer (drawn over everything): 8x8 font for ASCII 32-95 in white, 48 x 28 cells on screen */
void cps3v_text_init(void);
void cps3v_text(int col, int row, const char *s);   /* row 0-27, col 0-47 */

extern volatile uint32_t vbl_count;             /* src/crt0.S's VBlank handler counts here */
void cps3v_wait_vblank(void);
#endif
