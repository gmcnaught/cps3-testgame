/* CPS3 SDK set-up (cps3.h) */
#include "cps3.h"

void cps3_irq_mask(int level)
{
    uint32_t sr;
    __asm__ volatile("stc sr, %0" : "=r"(sr));
    sr = (sr & ~0xf0u) | ((uint32_t)(level & 15) << 4);
    __asm__ volatile("ldc %0, sr" : : "r"(sr));
}

void cps3_init(void)
{
    cps3v_init();
    cps3v_text_init();
    cps3s_init();
    cps3_irq_mask(10);                          /* VBlank on; IRQ 10 taken only inside the DMA waits */
}
