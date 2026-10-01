/* SH-2 vector table and reset entry (CPS3 BIOS ROM at 0). C symbols carry a leading underscore on sh-elf. */
    .section .vectors,"ax"
    .long   start               /* 0: power-on PC */
    .long   __stack_top         /* 1: power-on SP */
    .long   start               /* 2: manual reset PC */
    .long   __stack_top         /* 3: manual reset SP */
    .rept   60
    .long   trap                /* 4-63: exceptions */
    .endr
    .rept   8
    .long   irq                 /* 64-71: IRL auto-vectors (CPS3 VBlank = IRL 12); enabled by HW builds only */
    .endr

    .section .boot,"ax"
    .global start
start:
    mov.l   k_stack, r15
    /* the BIOS's set-up (Red Earth's, at 0x534): cache purged and off, the bus state controller (BCR1, BCR2, WCR;
       0xa55a = the write key), then the cache purged and on. jtcps3 does not run a program without it; MAME
       ignores these registers. */
    mov.l   k_ccr, r1
    mov     #0x10, r0
    mov.b   r0, @r1
    /* the BIOS's two writes before the bus controller (refs: herzmx/CPS3-CBIOS crt0.s): 0xBD0F to 0xFFFFFE80
       (watchdog area) and 2 to 0xFFFFFE90 (FMR, the SH7604's clock ratio) */
    mov.l   k_fe80, r2
    mov.l   v_fe80, r0
    mov.w   r0, @r2
    mov.l   k_fmr, r2
    mov     #2, r0
    mov.w   r0, @r2
    mov.l   k_bcr1, r2
    mov.l   v_bcr1, r0
    mov.l   r0, @r2
    mov.l   k_bcr2, r2
    mov.l   v_bcr2, r0
    mov.l   r0, @r2
    mov.l   k_wcr, r2
    mov.l   v_wcr, r0
    mov.l   r0, @r2
    mov     #0x11, r0
    mov.b   r0, @r1
    /* copy .data from ROM, clear .bss */
    mov.l   k_dload, r1
    mov.l   k_dstart, r2
    mov.l   k_dend, r3
1:  cmp/hs  r3, r2
    bt      2f
    mov.l   @r1+, r0
    mov.l   r0, @r2
    bra     1b
    add     #4, r2
2:  mov.l   k_bstart, r2
    mov.l   k_bend, r3
    mov     #0, r0
3:  cmp/hs  r3, r2
    bt      4f
    mov.l   r0, @r2
    bra     3b
    add     #4, r2
4:  mov.l   k_main, r0
    jsr     @r0
    nop
5:  bra     5b
    nop

trap:
    bra     trap
    nop

/* VBlank: count it (_vbl_count, src/cps3v.h) and clear IRL 12 (any write to 0x05100000) */
irq:
    mov.l   r0, @-r15
    mov.l   r1, @-r15
    mov.l   k_vbl, r0
    mov.l   @r0, r1
    add     #1, r1
    mov.l   r1, @r0
    mov.l   k_ack12, r0
    mov.l   r1, @r0
    mov.l   @r15+, r1
    mov.l   @r15+, r0
    rte                         /* pops PC and SR before its delay slot runs: nothing to pop in the slot */
    nop

    .align  2
k_stack:  .long __stack_top
k_ccr:    .long 0xfffffe92
k_fe80:   .long 0xfffffe80
v_fe80:   .long 0x0000bd0f
k_fmr:    .long 0xfffffe90
k_bcr1:   .long 0xffffffe0
v_bcr1:   .long 0xa55a0020
k_bcr2:   .long 0xffffffe4
v_bcr2:   .long 0xa55a00e8
k_wcr:    .long 0xffffffe8
v_wcr:    .long 0xa55aaa57
k_dload:  .long __data_load
k_dstart: .long __data_start
k_dend:   .long __data_end
k_bstart: .long __bss_start
k_bend:   .long __bss_end
k_main:   .long _main
k_vbl:    .long _vbl_count
k_ack12:  .long 0x05100000
