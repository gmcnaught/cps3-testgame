/* CPS3 (SH-2) program run from the BIOS ROM (0x00000000, 512 KB; tools/mkcps3.py encrypts it),
   work RAM is main RAM (0x02000000, 512 KB). src/link_simm.ld runs it from SIMM 1 instead, as the games do. */
OUTPUT_FORMAT("elf32-sh")
ENTRY(start)
MEMORY
{
    rom (rx) : ORIGIN = 0x00000000, LENGTH = 0x80000
    ram (rw) : ORIGIN = 0x02000000, LENGTH = 0x80000
}
__stack_top = 0x02080000;
SECTIONS
{
    .text : {
        KEEP(*(.vectors))
        *(.boot)
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(4);
    } > rom
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
    } > ram AT > rom
    __data_load = LOADADDR(.data);
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.bss .bss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
