/* CPS3 inputs and EEPROM (cps3io.h). Reads through the cache-through mirror (0x25xxxxxx): a cached read could return
   a stale line. Inputs (active low): 0x05000000, 32 bits: P1 up / down / left / right / B1-B3 in bits 0-6, P2 the
   same in bits 8-14, service 16, test 17, coin 1 / 2 24 / 25, P2 B6 26, start 1 / 2 28 / 29; 0x05000004: P1 B6 / B5 /
   B4 in bits 17 / 18 / 19, P2 B4 / B5 in 20 / 21.
   EEPROM: word k written at 0x05001080 + 4k after a 0 at 0x05001180 + 4k (MAME's note: the board erases first); read
   by a 16-bit read at 0x05001100 + 4k (bits 16-31) or + 2 (bits 0-15), which latches the half, then a 16-bit read of
   0x05001202. */
#include "cps3io.h"

#define IN0 (*(volatile uint32_t *)0x25000000u)
#define IN1 (*(volatile uint32_t *)0x25000004u)

uint32_t cps3_pad(int player)
{
    uint32_t a = ~IN0, b = ~IN1, p;
    if (player == 0) {
        p = a & 0x7f;
        p |= (b >> 19 & 1) ? CPS3_B4 : 0;
        p |= (b >> 18 & 1) ? CPS3_B5 : 0;
        p |= (b >> 17 & 1) ? CPS3_B6 : 0;
        p |= (a >> 28 & 1) ? CPS3_START : 0;
        p |= (a >> 24 & 1) ? CPS3_COIN : 0;
    } else {
        p = a >> 8 & 0x7f;
        p |= (b >> 20 & 1) ? CPS3_B4 : 0;
        p |= (b >> 21 & 1) ? CPS3_B5 : 0;
        p |= (a >> 26 & 1) ? CPS3_B6 : 0;
        p |= (a >> 29 & 1) ? CPS3_START : 0;
        p |= (a >> 25 & 1) ? CPS3_COIN : 0;
    }
    return p;
}

uint32_t cps3_system(void)
{
    uint32_t a = ~IN0;
    return (a >> 16 & 1 ? CPS3_SERVICE : 0) | (a >> 17 & 1 ? CPS3_TEST : 0);
}

#define EE_W(k)  (*(volatile uint32_t *)(0x05001080u + 4 * (k)))
#define EE_E(k)  (*(volatile uint32_t *)(0x05001180u + 4 * (k)))
#define EE_RL(a) (*(volatile uint16_t *)(0x25001100u + (a)))
#define EE_RD    (*(volatile uint16_t *)0x25001202u)

uint32_t cps3_ee_read(int k)
{
    uint32_t hi, lo;
    (void)EE_RL(4 * k);
    hi = EE_RD;
    (void)EE_RL(4 * k + 2);
    lo = EE_RD;
    return hi << 16 | lo;
}

void cps3_ee_write(int k, uint32_t v)
{
    EE_E(k) = 0;
    EE_W(k) = v;
}
