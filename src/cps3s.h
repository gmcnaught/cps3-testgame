/* CPS3 sound helpers (docs/CPS3.md "Sound"): the 16 PCM voices of the sound chip (MAME cps3_a.cpp). Samples are
   signed 8-bit in the sample flash (SIMMs 3-6); chip address = byte offset in that flash + 0x400000. A voice plays
   from start, one sample every 4096 / step output samples (output rate = clock / 384, 37,286 Hz), and at end jumps to
   loop (loop on) or goes silent while still keyed (loop off). Output per voice = sample x volume / 2^23. */
#ifndef CPS3S_INCLUDED
#define CPS3S_INCLUDED
#include <stdint.h>

#define CPS3S_BASE 0x400000u                    /* chip address of the sample flash's first byte */
#define CPS3S_RATE 37286                        /* output samples a second (MAME: clock / 384) */

void cps3s_init(void);                          /* all voices keyed off */
/* voice v's registers (written while keyed: take effect at once); vol_l / vol_r signed, left / right speaker as MAME
   routes them */
void cps3s_voice(int v, uint32_t start, uint32_t end, uint32_t loop, int looped, uint32_t step, int vol_l, int vol_r);
void cps3s_volume(int v, int vol_l, int vol_r);
void cps3s_step(int v, uint32_t step);
/* key bits (bit v = voice v on); a voice going from off to on restarts at its start */
void cps3s_keys(uint16_t keys);
uint16_t cps3s_keys_now(void);
#endif
