/* CPS3 video DMA (cps3dma.h). Register writes as Red Earth makes them (scripts/cps3_vlog.sh logs): 16-bit halves.
   Character DMA: records of 3 words at CPS3DMA_LIST in character RAM (command << 21 | (bytes / 8 - 1); dest / 8;
   (src + 0x400000) / 2), bit 24 of a first word ends the list; 0x040c0096 = list word address, 0x040c0098 = 0x0040
   starts it; busy: 0x040c000c bit 1. Palette DMA: 0xa0 source (src + 0x400000) / 2, 0xa4 first colour, 0xa8 fade,
   0xac length, 0xae = 0x0002 | length bit 16 starts it; busy: bit 2. Both: IRQ 10 at the end, acknowledged at
   0x05110000 (crt0.S irq10 does it). */
#include "cps3dma.h"
#include "cps3t.h"

#define W16(a, v) (*(volatile uint16_t *)(a) = (uint16_t)(v))
#define W32(a, v) (*(volatile uint32_t *)(a) = (uint32_t)(v))
#define R16(a)    (*(volatile uint16_t *)((a) | 0x20000000u))
#define PPU       0x040c0000u
#define CHAR_WIN  0x04100000u
#define TIMEOUT   (1u << 22)                    /* ticks: 33.5 M clocks, ~1.3 s */
#define GRACE     (1u << 19)                    /* ticks after IRQ 10 for the bit to clear */

static uint32_t list_n;

void cps3dma_char_record(uint32_t command, uint32_t src, uint32_t dest_byte, uint32_t bytes)
{
    if (list_n >= CPS3DMA_LIST_MAX)
        return;
    uint32_t a = CHAR_WIN + CPS3DMA_LIST + 12 * list_n++;
    W16(PPU + 0x86, 0);                         /* the window on character RAM's first 1 MB */
    W32(a + 0, command << 21 | ((bytes / 8u - 1u) & 0x1fffff));
    W32(a + 4, dest_byte / 8u);
    W32(a + 8, (src + 0x400000u) / 2u);
}

static uint32_t sr_get(void)
{
    uint32_t v;
    __asm__ volatile("stc sr, %0" : "=r"(v));
    return v;
}
static void sr_set(uint32_t v)
{
    __asm__ volatile("ldc %0, sr" : : "r"(v));
}

/* start (a function writing the start register) and wait: IRQ 10 taken and the status bit clear; IRL 10 and above
   unmasked meanwhile (the caller's mask restored after). FRC read once per 2,048 polls (MAME's slow count) */
static uint32_t run(void (*start)(void), uint32_t bit)
{
    uint32_t sr = sr_get();
    W32(0x05110000u, 0);
    irq10_n = 0;
    uint32_t p = cps3t_ticks(), acc = 0, k = 0, irq_at = ~0u;
    start();
    sr_set((sr & ~0xf0u) | 0x90u);
    for (;;) {
        uint32_t st = R16(PPU + 0x0c) & bit;
        if (irq10_n && irq_at == ~0u)
            irq_at = acc;
        if (irq_at != ~0u && !st)
            break;
        if (++k == 2048) {
            k = 0;
            uint32_t q = cps3t_ticks();
            acc += (q - p) & 0xffff;
            p = q;
            if (acc >= TIMEOUT || (irq_at != ~0u && acc - irq_at >= GRACE))
                break;
        }
    }
    sr_set(sr);
    if (irq_at == ~0u)
        return 0;
    acc += (cps3t_ticks() - p) & 0xffff;
    return acc * CPS3T_CLOCKS_PER_TICK;
}

static void char_start(void)
{
    W16(PPU + 0x98, 0x0040);
}

uint32_t cps3dma_char_run(void)
{
    W16(PPU + 0x86, 0);
    W32(CHAR_WIN + CPS3DMA_LIST + 12 * list_n, 0x01000000u);
    list_n = 0;
    W16(PPU + 0x96, CPS3DMA_LIST / 4);
    return run(char_start, 2);
}

static uint32_t pal_len;
static void pal_start(void)
{
    W16(PPU + 0xae, 0x0002 | ((pal_len >> 16) & 1));
}

uint32_t cps3dma_palette(uint32_t src, uint32_t first, uint32_t n, uint32_t fade)
{
    uint32_t s = (src + 0x400000u) / 2u;
    W16(PPU + 0xa0, s >> 16);
    W16(PPU + 0xa2, s);
    W16(PPU + 0xa4, first >> 16);
    W16(PPU + 0xa6, first);
    W16(PPU + 0xa8, fade >> 16);
    W16(PPU + 0xaa, fade);
    W16(PPU + 0xac, n);
    pal_len = n;
    return run(pal_start, 4);
}
