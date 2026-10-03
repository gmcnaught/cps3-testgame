/* CPS3 video DMA: character DMA (graphics flash -> character RAM, plain or run-length decoded) and palette DMA
   (graphics flash -> colour RAM). Both end with IRQ 10; the wait here takes IRQ 10 (sdk/src/crt0.S irq10) and the
   status bit clear, as src/ttest.c measures them: on jtcps3 the busy bit comes up 120-576 CPU clocks after the start
   write, so a wait on the bit alone returns before the DMA has run (docs/CPS3.md "Timing").
   Flash addresses count from the start of the graphics flash (SIMM 3; MAME's user5). The character DMA reads flash
   byte a as byte a ^ 1 of the image tools/mkcps3.py takes (tools/cps3asset.py flash_tiles stores tiles so). */
#ifndef CPS3DMA_INCLUDED
#define CPS3DMA_INCLUDED
#include <stdint.h>

/* list commands (herzmx/CPS3-CBIOS, MAME process_character_dma; checked by src/dmap.c on MAME and jtcps3) */
#define CPS3DMA_COPY  0u                        /* bytes copied */
#define CPS3DMA_RLE6  2u                        /* 6bpp run-length data decoded (bytes = bytes written) */
#define CPS3DMA_RLE8  3u                        /* 8bpp run-length data decoded (bytes = bytes written) */
#define CPS3DMA_TABLE 4u                        /* the decoders' pair table read from src (dest unused) */
/* the list lives in character RAM bytes 0x1000-0x1fff (tiles 16-31: not usable as tiles): 341 records at most */
#define CPS3DMA_LIST       0x1000u
#define CPS3DMA_LIST_MAX   341

/* one list record; dest_byte and bytes multiples of 8 */
void cps3dma_char_record(uint32_t command, uint32_t src, uint32_t dest_byte, uint32_t bytes);
/* n 16x16 8-bit tiles from flash byte src to character RAM tile first */
static inline void cps3dma_char_copy(uint32_t src, uint32_t first, uint32_t n)
{
    cps3dma_char_record(CPS3DMA_COPY, src, first * 256u, n * 256u);
}
/* runs the list built so far and waits for its end; CPU clocks taken, 0 if no end was seen within ~1.3 s */
uint32_t cps3dma_char_run(void);

/* n colours (BGR555 words) from flash byte src to colour RAM entry first; fade as Red Earth writes it (0: none; MAME
   applies a fade only when fade & 0x40400040); waits for the end as cps3dma_char_run */
uint32_t cps3dma_palette(uint32_t src, uint32_t first, uint32_t n, uint32_t fade);

extern volatile uint32_t irq10_n, irq10_frc;    /* sdk/src/crt0.S: IRQ 10s taken, FRC at the last */
#endif
