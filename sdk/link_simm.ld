/* CPS3 (SH-2) program run from SIMM 1 (program flash, 0x06000000, 8 MB) as the games are: the BIOS ROM holds
   the vectors and start-up (.boot), SIMM 1 the code, constants and the data's load image; work RAM is main RAM.
   The Makefile cuts main.elf into bios.bin (.boot) and simm1.bin (the rest); tools/mkcps3.py encrypts both. */
OUTPUT_FORMAT("elf32-sh")
ENTRY(start)
MEMORY
{
    rom (rx) : ORIGIN = 0x00000000, LENGTH = 0x80000
    simm (rx) : ORIGIN = 0x06000000, LENGTH = 0x800000
    ram (rw) : ORIGIN = 0x02000000, LENGTH = 0x80000
}
__stack_top = 0x02080000;
SECTIONS
{
    .boot : {
        KEEP(*(.vectors))
        *(.boot)
        . = ALIGN(4);
    } > rom
    .text : {
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(4);
    } > simm
    /* trace block for the MAME scripts, first in RAM so it sits at 0x02000000 */
    .trace (NOLOAD) : {
        KEEP(*(.trace))
        . = ALIGN(4);
    } > ram
    .data : {
        __data_start = .;
        *(.data .data.*)
        . = ALIGN(4);
        __data_end = .;
    } > ram AT > simm
    __data_load = LOADADDR(.data);
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.bss .bss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
