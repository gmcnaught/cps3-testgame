/* CPS3 SDK: one include for a program (docs/SDK.md). Video (cps3v.h), video DMA (cps3dma.h), sound (cps3s.h),
   inputs and EEPROM (cps3io.h), the CPU's timer (cps3t.h). */
#ifndef CPS3_INCLUDED
#define CPS3_INCLUDED
#include <stdint.h>
#include "cps3v.h"
#include "cps3dma.h"
#include "cps3s.h"
#include "cps3io.h"
#include "cps3t.h"

/* screen set-up (cps3v_init), the text layer's font (cps3v_text_init), sound voices off (cps3s_init), then VBlank
   (IRL 12) unmasked: vbl_count counts frames and cps3v_wait_vblank works */
void cps3_init(void);
/* the SH-2's interrupt mask (SR bits 4-7): levels above it are taken. CPS3: VBlank 12, video DMA end 10 */
void cps3_irq_mask(int level);
#endif
