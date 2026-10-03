/* CPS3 sound helpers (cps3s.h). Registers (MAME cps3_a.cpp), 32-bit, voice v at 0x040e0000 + 32 v: 1 start (16-bit
   halves swapped), 2 bit 0 loop on, 3 step << 16 | loop bits 0-15, 4 loop bits 16-31, 5 and 6 end (halves swapped;
   always written equal, as the games do: which one is the loop end is unknown), 7 volume: bits 16-31 the left
   speaker, 0-15 the right (MAME cps3.cpp routes chip output 1, computed from bits 16-31, to the left speaker, though
   cps3_a.cpp names bits 16-31 "volume right"; not checked on hardware).
   0x040e0200 bits 16-31: key on per voice. Written through the cache-through mirror 0x240e0000. */
#include "cps3s.h"

#define SNDR ((volatile uint32_t *)0x240e0000u)

static uint16_t keys;
static uint32_t loop_lo[16];                    /* register 3's low half, kept for step changes */

static inline uint32_t swap16(uint32_t a) { return a >> 16 | a << 16; }

void cps3s_init(void)
{
    cps3s_keys(0);
}

void cps3s_voice(int v, uint32_t start, uint32_t end, uint32_t loop, int looped, uint32_t step, int vol_l, int vol_r)
{
    volatile uint32_t *r = SNDR + 8 * v;
    loop_lo[v] = loop & 0xffff;
    r[1] = swap16(start);
    r[2] = looped ? 1 : 0;
    r[3] = step << 16 | loop_lo[v];
    r[4] = loop >> 16;
    r[5] = swap16(end);
    r[6] = swap16(end);
    r[7] = (uint32_t)(uint16_t)vol_l << 16 | (uint16_t)vol_r;
}

void cps3s_volume(int v, int vol_l, int vol_r)
{
    SNDR[8 * v + 7] = (uint32_t)(uint16_t)vol_l << 16 | (uint16_t)vol_r;
}

void cps3s_step(int v, uint32_t step)
{
    SNDR[8 * v + 3] = step << 16 | loop_lo[v];
}

void cps3s_keys(uint16_t k)
{
    keys = k;
    SNDR[0x80] = (uint32_t)k << 16;
}

uint16_t cps3s_keys_now(void) { return keys; }
