/* CPS3 inputs and EEPROM (MAME cps3.cpp INPUTS / EXTRA ports and eeprom_r / eeprom_w; the EEPROM interface as
   maldita.castilla-cps3 uses it on MAME and jtcps3). Not checked on a real board. */
#ifndef CPS3IO_INCLUDED
#define CPS3IO_INCLUDED
#include <stdint.h>

/* cps3_pad(): a set bit = pressed */
#define CPS3_UP     0x0001u
#define CPS3_DOWN   0x0002u
#define CPS3_LEFT   0x0004u
#define CPS3_RIGHT  0x0008u
#define CPS3_B1     0x0010u
#define CPS3_B2     0x0020u
#define CPS3_B3     0x0040u
#define CPS3_B4     0x0080u
#define CPS3_B5     0x0100u
#define CPS3_B6     0x0200u
#define CPS3_START  0x0400u
#define CPS3_COIN   0x0800u
/* cps3_system() */
#define CPS3_SERVICE 0x1u
#define CPS3_TEST    0x2u

uint32_t cps3_pad(int player);                  /* player 0 or 1 */
uint32_t cps3_system(void);

/* the 93C46: 32 words of 32 bits (128 bytes), kept by MAME in its .nv file and by jtcps3 in the MiSTer's .nvm */
#define CPS3_EE_WORDS 32
uint32_t cps3_ee_read(int word);
void cps3_ee_write(int word, uint32_t v);
#endif
