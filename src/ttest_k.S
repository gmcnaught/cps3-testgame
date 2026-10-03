/* Timing kernels for src/ttest.c: void k(uint32_t iterations r4, uint32_t address r5, uint32_t value r6).
   Each runs r4 loop iterations of 32 copies of one operation (k_empty: none) closed by DT r4 / BF. Position
   independent (only branches inside the kernel), so ttest.c can copy one into cache RAM; _end marks the copy's end.
   Inside the loop T = 0 (DT leaves it clear until the last iteration): k_bft's BF is always taken, k_btn's BT never. */
    .text

    .macro  kernel name
    .balign 16
    .global _\name
_\name:
    clrt
1:
    .endm

    .macro  kend name
    dt      r4
    bf      1b
    rts
    nop
    .global _\name\()_end
_\name\()_end:
    .endm

    kernel  k_empty
    kend    k_empty

    kernel  k_nop
    .rept   32
    nop
    .endr
    kend    k_nop

    kernel  k_add
    .rept   32
    add     r6, r7
    .endr
    kend    k_add

    kernel  k_div1
    .rept   32
    div1    r6, r7
    .endr
    kend    k_div1

    kernel  k_mull
    .rept   32
    mul.l   r6, r7
    .endr
    kend    k_mull

    kernel  k_dmuls
    .rept   32
    dmuls.l r6, r7
    .endr
    kend    k_dmuls

    kernel  k_mulsw
    .rept   32
    muls.w  r6, r7
    .endr
    kend    k_mulsw

    /* a load and an ADD that does not use it, then one that does (the load-use slot) */
    kernel  k_ldnouse
    .rept   32
    mov.l   @r5, r1
    add     r6, r2
    .endr
    kend    k_ldnouse

    kernel  k_lduse
    .rept   32
    mov.l   @r5, r1
    add     r1, r2
    .endr
    kend    k_lduse

    kernel  k_bra
    .rept   32
    bra     2f
    nop
2:
    .endr
    kend    k_bra

    kernel  k_bft
    .rept   32
    bf      2f
2:
    .endr
    kend    k_bft

    kernel  k_btn
    .rept   32
    bt      9f
    .endr
    kend    k_btn
9:  bra     9b                  /* never reached */
    nop

    kernel  k_ldl
    .rept   32
    mov.l   @r5, r0
    .endr
    kend    k_ldl

    kernel  k_ldw
    .rept   32
    mov.w   @r5, r0
    .endr
    kend    k_ldw

    kernel  k_stl
    .rept   32
    mov.l   r6, @r5
    .endr
    kend    k_stl
