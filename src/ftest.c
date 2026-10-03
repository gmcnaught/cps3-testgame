/* CPS3 flash sound load test (tools/ftest.py's sample flash): the program rewrites part of SIMM 3 while running and
   the sound chip plays it, as a port would load a stage's music into SIMM 3 from SIMMs 4-6 (jtcps3 plays samples only
   from the first 16 MB). Steps, results on the text layer:
     ID     flash autoselect on slot 1's chips (Fujitsu 29F016A: 0404 ADAD)
     SUM    sources A (SIMM 4) and B (SIMM 6) read through the flash window, against tools/ftest.py's sums
     ERASE  slot 1's sector (64 KB of each of the two chips = 128 KB of samples): frames until it reads 0xFFFF, the
            first status read, halfwords not 0xFFFF after
     LOAD   source to slot by program commands: frames, programs that never read back (the copy stops at 64 = FAIL
            00040), halfwords differing after
     RAW    source A to slot 3 by plain 16-bit writes, no commands (does the window act as RAM?)
   and between them each slot played on voice 0 (the plays list on screen: code if the loads work, code in MAME).
   Graphics flash access (MAME cps3.cpp gfxflash_r / gfxflash_w, cram_gfxflash_bank_w; the C-BIOS's GFX flash
   routines, refs herzmx/CPS3-CBIOS src/flash.c): bank register 0x040c0088 (16-bit) = sub-bank + 2, sub-bank n =
   sample-flash bytes n x 2 MB to n x 2 MB + 2 MB (SIMM 3 + n / 8, chip pair (n % 8) / 2, 1 MB half n & 1); window
   0x04200000, 16-bit halfword h = chip address h of both chips (high byte the even chip). Commands go to both chips
   at once (0xAAAA, ...). Chip and write enable: the Capcom BIOS writes 0x01050003 / 0x01050000 to 0x07ff000c and
   1 / 0 to 0x07ff0048 around flash commands (by one-word DMA; written here by the CPU; CDEFS=-DNO_CEWE: not at
   all). MAME's sample copy changes only at the words a window write touches, so in MAME an erased slot still plays
   its old code; MAME's flash model also takes plain data bytes 0x10 / 0x40 / 0x90 ... as Intel commands, so RAW's
   result there says nothing about the hardware (AMD-type chips ignore writes without the unlock sequence). */
#include "cps3v.h"
#include "cps3s.h"
#include "ftest.h"

volatile uint32_t vbl_count;

#define BANKSEL (*(volatile uint16_t *)0x240c0088u)
#define F16     ((volatile uint16_t *)0x24200000u)
#define CE_REG  (*(volatile uint32_t *)0x27ff000cu)
#define WE_REG  (*(volatile uint32_t *)0x27ff0048u)
#define POLLS   20000u                  /* reads of a programmed halfword before giving up */
#define MAX_FAIL 64u                    /* failed programs before a copy stops (FAIL shows 40 = stopped) */
#define ERASE_FRAMES 600u               /* 10 s */
#define CH      2048u                   /* halfwords copied through RAM per bank switch */

static void ce(int on)
{
#ifndef NO_CEWE
    CE_REG = on ? 0x01050003u : 0x01050000u;
#else
    (void)on;
#endif
}

static void we(int on)
{
#ifndef NO_CEWE
    WE_REG = on ? 1u : 0u;
#else
    (void)on;
#endif
}

/* the sub-bank holding sample-flash byte off; returns off's halfword index in the window */
static uint32_t sel(uint32_t off)
{
    BANKSEL = (uint16_t)((off >> 21) + 2);
    return (off & 0x1fffffu) >> 1;
}

static void unlock(void)
{
    F16[0x555] = 0xaaaa;
    F16[0x2aa] = 0x5555;
}

static void reset_cmd(void)
{
    we(1);
    F16[0] = 0xf0f0;
    we(0);
}

/* text layer: results as "<step> <name> <hex> ..." */
static void hexs(char *b, uint32_t v, int n)
{
    for (int i = n - 1; i >= 0; i--, v >>= 4)
        b[i] = "0123456789ABCDEF"[v & 15];
}

static void line(int row, const char *s)
{
    cps3v_text(1, row, "                                              ");
    cps3v_text(1, row, s);
}

static char rs[48];
static int rk;
static void rbegin(const char *what)
{
    rk = 0;
    for (const char *p = what; *p; p++)
        rs[rk++] = *p;
}
static void rfield(const char *name, uint32_t v, int digits)
{
    rs[rk++] = ' ';
    for (const char *p = name; *p; p++)
        rs[rk++] = *p;
    rs[rk++] = ' ';
    hexs(rs + rk, v, digits);
    rk += digits;
}
static void rend(int row)
{
    rs[rk] = 0;
    line(row, rs);
}

static void frames(uint32_t n)
{
    while (n--)
        cps3v_wait_vblank();
}

static int play_k;
static void play(void)
{
    const struct f_play *p = &f_plays[play_k];
    line(14 + play_k, p->text);
    cps3v_text(1, 26, ">");
    cps3s_voice(0, CPS3S_BASE + p->off, CPS3S_BASE + p->off + p->len, CPS3S_BASE + p->off, 0, 4096, 0x4000, 0x4000);
    cps3s_keys(1);
    frames(p->len * 60u / CPS3S_RATE + 10u);
    cps3s_keys(0);
    frames(90);
    cps3v_text(1, 26, " ");
    play_k++;
}

/* autoselect: halfwords 0 and 1 (manufacturer, device of both chips) */
static void flash_id(int row, uint32_t off)
{
    sel(off);
    ce(1);
    we(1);
    unlock();
    F16[0x555] = 0x9090;
    we(0);
    uint32_t m = F16[0], d = F16[1];
    reset_cmd();
    ce(0);
    rbegin("ID");
    rfield("MAN", m, 4);
    rfield("DEV", d, 4);
    rend(row);
}

static void flash_sum(int row, const char *what, uint32_t off, uint32_t len, uint32_t expect)
{
    uint32_t h = sel(off), sum = 0;
    for (uint32_t i = 0; i < len / 2; i++)
        sum += F16[h + i];
    rbegin(what);
    rfield("SUM", sum, 8);
    rfield("EXP", expect, 8);
    rend(row);
}

static void flash_erase(int row, const char *what, uint32_t off)
{
    uint32_t sa = sel(off) & ~0xffffu;
    ce(1);
    we(1);
    unlock();
    F16[0x555] = 0x8080;
    unlock();
    F16[sa] = 0x3030;
    we(0);
    uint32_t st = F16[sa], t0 = vbl_count;
    while (F16[sa] != 0xffff && vbl_count - t0 < ERASE_FRAMES)
        ;
    uint32_t fr = vbl_count - t0;
    reset_cmd();
    ce(0);
    uint32_t bad = 0;
    for (uint32_t i = 0; i < 0x10000u; i++)
        bad += F16[sa + i] != 0xffff;
    rbegin(what);
    rfield("FR", fr, 4);
    rfield("ST", st, 4);
    rfield("NOTFF", bad, 5);
    rend(row);
}

/* len bytes from sample-flash offset src to dst (both 4-byte aligned, neither crossing a 2 MB sub-bank), by program
   commands (cmd) or plain writes; then every halfword compared */
static void flash_copy(int row, const char *what, uint32_t src, uint32_t dst, uint32_t len, int cmd)
{
    static uint16_t buf[CH];
    uint32_t n = len / 2, fail = 0, diff = 0, t0 = vbl_count;
    if (cmd)
        ce(1);
    for (uint32_t i = 0; i < n && fail < MAX_FAIL; i += CH) {
        uint32_t m = n - i < CH ? n - i : CH;
        uint32_t hs = sel(src) + i;
        for (uint32_t j = 0; j < m; j++)
            buf[j] = F16[hs + j];
        uint32_t hd = sel(dst) + i;
        for (uint32_t j = 0; j < m && fail < MAX_FAIL; j++) {
            if (!cmd) {
                F16[hd + j] = buf[j];
                continue;
            }
            we(1);
            unlock();
            F16[0x555] = 0xa0a0;
            F16[hd + j] = buf[j];
            we(0);
            uint32_t t = 0;
            while (F16[hd + j] != buf[j] && ++t < POLLS)
                ;
            if (t == POLLS) {
                fail++;
                reset_cmd();
            }
        }
    }
    uint32_t fr = vbl_count - t0;
    if (cmd)
        ce(0);
    else
        reset_cmd();                    /* in case the data formed a command sequence */
    for (uint32_t i = 0; i < n; i++) {
        uint32_t hs = sel(src + 4 * (i / 2)), v = F16[hs + (i & 1)];
        uint32_t hd = sel(dst + 4 * (i / 2));
        diff += F16[hd + (i & 1)] != v;
    }
    rbegin(what);
    rfield("FR", fr, 4);
    rfield("FAIL", fail, 5);
    rfield("DIFF", diff, 5);
    rend(row);
}

int main(void)
{
    cps3v_init();
    cps3v_text_init();
    cps3v_text(1, 1, "CPS3 FLASH SOUND LOAD TEST");
    cps3v_text(1, 13, "PLAYS: CODE IF LOADS WORK, MAME");
    cps3s_init();
    __asm__ volatile("ldc %0, sr" : : "r"(0));   /* interrupts on: VBlank (IRL 12) counts vbl_count */
    frames(60);
    for (int k = 0; k < 4; k++)
        play();
    flash_id(3, F_SLOT1);
    flash_sum(4, "SRC A", F_SRCA, F_SRCA_LEN, F_SRCA_SUM);
    flash_sum(5, "SRC B", F_SRCB, F_SRCB_LEN, F_SRCB_SUM);
    flash_erase(6, "ERASE 8M", F_SLOT1);
    play();
    flash_copy(7, "A TO 8M", F_SRCA, F_SLOT1, F_SRCA_LEN, 1);
    play();
    play();
    flash_erase(8, "ERASE 8M", F_SLOT1);
    flash_copy(9, "B TO 8M", F_SRCB, F_SLOT1, F_SRCB_LEN, 1);
    play();
    flash_erase(10, "ERASE10M", F_SLOT2);
    flash_copy(11, "A TO 10M", F_SRCA, F_SLOT2, F_SRCA_LEN, 1);
    play();
    flash_copy(12, "RAW A TO 12M", F_SRCA, F_SLOT3, F_SRCA_LEN, 0);
    play();
    line(26, "END");
    for (;;)
        cps3v_wait_vblank();
}
