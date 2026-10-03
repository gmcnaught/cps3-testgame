/* CPS3 timing: the SH7604 free-running timer (FRC, 16 bits, phi / 8 since reset: one tick = 8 CPU clocks; 25 MHz
   CPU: 52,429 ticks a frame, wrapping every 21 ms). Measured with it: docs/CPS3.md "Timing" (src/ttest.c). */
#ifndef CPS3T_INCLUDED
#define CPS3T_INCLUDED
#include <stdint.h>

#define CPS3T_CLOCKS_PER_TICK 8

/* FRC now. Byte reads, high byte first (on the chip that latches the low byte; SH7604 manual 11.3). MAME has no latch
   (each byte read resyncs), so the high byte is read again and the low byte again if it changed. MAME also drops the
   clocks short of a tick at every read: a loop reading it every few clocks counts slow there. */
static inline uint32_t cps3t_ticks(void)
{
    volatile uint8_t *f = (volatile uint8_t *)0xfffffe12u;
    uint32_t h = f[0], l = f[1], h2 = f[0];
    if (h2 != h) {
        l = f[1];
        h = h2;
    }
    return h << 8 | l;
}

/* CPU clocks since t0 (a cps3t_ticks() reading), valid for intervals under 65,536 ticks (524,288 clocks) */
static inline uint32_t cps3t_clocks_since(uint32_t t0)
{
    return ((cps3t_ticks() - t0) & 0xffff) * CPS3T_CLOCKS_PER_TICK;
}
#endif
