/* CPS3 SDK example (docs/SDK.md): a ball moved by player 1's stick, a beep on button 1, the inputs, a boot counter in
   the EEPROM and the start-up DMA times on the text layer. The ball's tiles and colours come from the graphics flash
   by character and palette DMA, the beep from the sample flash (assets.py writes both). */
#include "cps3.h"
#include "assets.h"

#define BALL_TILE 0x100u                        /* tiles 0x100-0x103 (tiles 16-31 hold the DMA list) */
#define BALL_PAL  1u                            /* colour code 1: colours 256-511 */
#define EE_AT     30                            /* words 30-31: magic, boots (the MRA's EEPROM defaults fill 0-23) */
#define EE_MAGIC  0x48454c4fu                   /* 'HELO' */

static void hex(char *b, uint32_t v, int n)
{
    for (int i = n - 1; i >= 0; i--, v >>= 4)
        b[i] = "0123456789ABCDEF"[v & 15];
    b[n] = 0;
}

static void line(int row, const char *label, uint32_t v, int digits)
{
    char b[9];
    hex(b, v, digits);
    cps3v_text(2, row, label);
    cps3v_text(16, row, b);
}

int main(void)
{
    cps3_init();
    uint32_t pal_clocks = cps3dma_palette(COLOURS_AT, BALL_PAL * 256, 16, 0);
    cps3dma_char_copy(TILES_AT, BALL_TILE, 4);
    uint32_t chr_clocks = cps3dma_char_run();

    uint32_t boots = 0;
    if (cps3_ee_read(EE_AT) == EE_MAGIC)
        boots = cps3_ee_read(EE_AT + 1);
    cps3_ee_write(EE_AT, EE_MAGIC);
    cps3_ee_write(EE_AT + 1, ++boots);

    cps3v_text(2, 1, "CPS3 SDK HELLO");
    cps3v_text(2, 3, "STICK: MOVE   B1: BEEP");
    line(5, "BOOTS", boots, 8);
    line(6, "PAL DMA", pal_clocks, 8);
    line(7, "CHAR DMA", chr_clocks, 8);

    int x = CPS3V_W / 2 - 16, y = CPS3V_H / 2 - 16;
    uint32_t prev = 0, frame = 0;
    for (;;) {
        cps3v_wait_vblank();
        cps3v_vblank();                         /* sends the list built last frame */
        uint32_t p1 = cps3_pad(0), p2 = cps3_pad(1), sys = cps3_system();
        x += (p1 & CPS3_RIGHT ? 2 : 0) - (p1 & CPS3_LEFT ? 2 : 0);
        y += (p1 & CPS3_DOWN ? 2 : 0) - (p1 & CPS3_UP ? 2 : 0);
        x = x < 0 ? 0 : x > CPS3V_W - 32 ? CPS3V_W - 32 : x;
        y = y < 0 ? 0 : y > CPS3V_H - 32 ? CPS3V_H - 32 : y;
        if (p1 & ~prev & CPS3_B1) {
            uint32_t s = CPS3S_BASE + BEEP_AT;
            cps3s_keys(0);
            cps3s_voice(0, s, s + BEEP_LEN, s, 0, 4096u * BEEP_RATE / CPS3S_RATE, 0x4000, 0x4000);
            cps3s_keys(1);
        }
        prev = p1;
        cps3v_begin();
        cps3v_sprite(x, y, 2, 2, BALL_TILE, BALL_PAL, 0);
        cps3v_end();
        line(9, "FRAME", frame++, 8);
        line(10, "P1", p1, 4);
        line(11, "P2", p2, 4);
        line(12, "SYSTEM", sys, 1);
    }
}
