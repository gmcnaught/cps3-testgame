/* CPS3 timing test (tools/ttest.py has the table and the units): CPU instruction timing per code location, memory
   access per region, character / palette / sprite-list DMA and SH-2 DMAC transfer times, counted with the SH7604
   free-running timer (FRC at phi / 8, its reset setting: one tick = 8 CPU clocks). Interrupts are masked during each
   measurement except the frame count. Each result is shown on the text layer as it ends and stored at 0x02000000
   (tt_res, read by scripts/lua/ttest_dump.lua); the whole table runs again every pass. */
#include "cps3v.h"

struct tt {
    const char *name;
    uint8_t kind, loc;
    const char *k, *kend;     /* kernel (src/ttest_k.S) */
    uint32_t a, v;            /* kernel address / DMA length / DMAC source; DMAC CHCR0 */
};
#include "ttest.h"

volatile uint32_t vbl_count;

/* first in RAM (0x02000000, the .trace block): magic 'TTST', passes done, tests, then one value per test */
volatile struct {
    uint32_t magic, pass, n, val[TT_N];
} tt_res __attribute__((section(".trace")));

typedef void (*kfn)(uint32_t n, uint32_t a, uint32_t v);

#define W16(a, v) (*(volatile uint16_t *)(a) = (uint16_t)(v))
#define W32(a, v) (*(volatile uint32_t *)(a) = (uint32_t)(v))
#define R16(a)    (*(volatile uint16_t *)((a) | 0x20000000u))
#define REG8(a)   (*(volatile uint8_t *)(a))
#define REG32(a)  (*(volatile uint32_t *)(a))
#define PPU       0x040c0000u
#define CHAR_WIN  0x04100000u
#define LIST      0x1000u                 /* character DMA list: character RAM byte 0x1000 (Red Earth's) */
#define CDMA_DEST 0x200000u               /* character RAM byte 2 MB: no tile the text layer uses */
#define PDMA_DEST 0x10000u                /* colour 0x10000-0x11fff (text colours from 0x1fe00) */
#define CCR       0xfffffe92u
#define SAR0      0xffffff80u
#define DAR0      0xffffff84u
#define TCR0      0xffffff88u
#define CHCR0     0xffffff8cu
#define DMAOR     0xffffffb0u
#define CRAM      0xc0000000u
#define TIMEOUT   (1u << 22)              /* ticks */

static void sr(uint32_t v)
{
    __asm__ volatile("ldc %0, sr" : : "r"(v));
}

/* FRC: byte accesses, the high byte first (on the chip that latches the low byte; SH7604 manual 11.3). MAME has no
   latch (sh7604.cpp frc_r: each byte read resyncs), so a low byte that wraps between the two reads gives a value 256
   ticks low: the high byte is read again, and the low byte again if it changed */
static inline uint32_t frc(void)
{
    uint32_t h = REG8(0xfffffe12), l = REG8(0xfffffe13), h2 = REG8(0xfffffe12);
    if (h2 != h) {
        l = REG8(0xfffffe13);
        h = h2;
    }
    return h << 8 | l;
}

/* -------- text -------- */
static void dec(char *b, int w, uint32_t v)           /* right-aligned in w cells */
{
    for (int i = w - 1; i >= 0; i--) {
        b[i] = (char)('0' + v % 10);
        v /= 10;
        if (!v) {
            while (--i >= 0)
                b[i] = ' ';
            return;
        }
    }
}

/* one cell of TT_CELL: name (8), space, value (6): x 100 values as ddd.dd, clocks of a million or more in thousands
   (12345K), ~0 (not seen) as NEVER */
static void show(int i, uint32_t v, int kind)
{
    char s[TT_CELL];
    for (int k = 0; k < TT_CELL - 1; k++)
        s[k] = ' ';
    s[TT_CELL - 1] = 0;
    for (int k = 0; k < 8 && tt_tests[i].name[k]; k++)
        s[k] = tt_tests[i].name[k];
    char *f = s + 9;
    if (v == ~0u) {
        f[1] = 'N', f[2] = 'E', f[3] = 'V', f[4] = 'E', f[5] = 'R';
    } else if (kind == TT_OP || kind == TT_ITER || kind == TT_DURING) {   /* x 100, signed */
        int32_t x = (int32_t)v;
        uint32_t m = (uint32_t)(x < 0 ? -x : x);
        if (m < 100000) {
            dec(f, 3, m / 100);
            f[3] = '.';
            f[4] = (char)('0' + m / 10 % 10);
            f[5] = (char)('0' + m % 10);
        } else {
            dec(f, 6, m / 100);
        }
        if (x < 0) {
            int k = 5;
            while (k > 0 && f[k] != ' ')
                k--;
            f[k] = '-';
        }
    } else if (v < 1000000) {
        dec(f, 6, v);
    } else {
        dec(f, 5, v / 1000);
        f[5] = 'K';
    }
    cps3v_text((i / TT_ROWS) * TT_CELL, 2 + i % TT_ROWS, s);
}

static void title(void)
{
    char s[] = "TTEST PASS 00000  CPU CLOCKS (OP: PER OP)";
    dec(s + 11, 5, tt_res.pass);
    cps3v_text(1, 0, s);
}

/* -------- CPU kernels -------- */
static uint32_t ticks(kfn k, uint32_t n, uint32_t a, uint32_t v)
{
    uint32_t t0 = frc();
    k(n, a, v);
    return (frc() - t0) & 0xffff;
}

/* CPU clocks x 100 per loop iteration: the difference between n and 2n iterations (the call and timer reads cancel);
   n doubled until n iterations take 4096 ticks, so 2n stay under the 16-bit counter's wrap; median of 3 (one run hit
   by an interrupt or a bus stall, in either direction, does not count) */
static uint32_t per_iter100(kfn k, uint32_t a, uint32_t v)
{
    uint32_t n = 1, d[3];
    k(1, a, v);
    while (n < 4096 && ticks(k, n, a, v) < 4096)
        n *= 2;
    for (int r = 0; r < 3; r++) {
        uint32_t t2 = ticks(k, 2 * n, a, v), t1 = ticks(k, n, a, v);
        d[r] = t2 > t1 ? t2 - t1 : 0;
    }
    uint32_t lo = d[0] < d[1] ? d[0] : d[1], hi = d[0] < d[1] ? d[1] : d[0];
    uint32_t best = d[2] < lo ? lo : d[2] > hi ? hi : d[2];
    return best * 800u / n;
}

/* the CPS3's SH-2 decrypts every opcode fetch, cache RAM included (MAME cps3.cpp sh2cache_ram_w, cps3_mask) */
static uint32_t rol16(uint32_t v, int n)
{
    return ((v << n) | (v >> (16 - n))) & 0xffff;
}
static uint32_t rotxor(uint32_t val, uint32_t x)
{
    uint32_t res = (val + rol16(val, 2)) & 0xffff;
    return rol16(res, 4) ^ (res & (val ^ x));
}
static uint32_t cps3_mask(uint32_t addr)
{
    addr ^= KEY1;
    uint32_t val = (addr & 0xffff) ^ 0xffff;
    val = rotxor(val, KEY2 & 0xffff);
    val ^= ((addr >> 16) ^ 0xffff) & 0xffff;
    val = rotxor(val, KEY2 >> 16);
    val ^= (addr & 0xffff) ^ (KEY2 & 0xffff);
    return val | val << 16;
}

static int cram_on;
static kfn locate(const struct tt *t)
{
    switch (t->loc) {
    case LOC_SU:
        return (kfn)((uint32_t)t->k | 0x20000000u);
    case LOC_CR: {
        if (!cram_on) {
            REG8(CCR) = 0x19;                 /* purge, two-way mode (ways 0-1 = RAM at 0xc0000000), cache on */
            cram_on = 1;
        }
        const uint32_t *src = (const uint32_t *)t->k;
        for (uint32_t i = 0; i < (uint32_t)(t->kend - t->k + 3) / 4; i++)
            REG32(CRAM + 4 * i) = src[i] ^ cps3_mask(CRAM + 4 * i);
        return (kfn)CRAM;
    }
    default:
        return (kfn)t->k;
    }
}

/* -------- DMA -------- */
extern volatile uint32_t irq10_n, irq10_frc;  /* src/crt0.S irq10: IRQ 10s taken, FRC at the last */

/* CPU clocks from p (an FRC reading) until cond is false. FRC is read once every 2048 polls (well inside its 16-bit
   wrap) and the ticks summed: MAME's FRC (sh7604.cpp sh2_timer_resync) drops the clocks short of a tick at every read,
   so a loop reading it every few clocks counts slow there (a read every 9 clocks: 8 / 9 of the time) */
#define WAIT_WHILE(cond, p)                                                       \
    ({                                                                            \
        uint32_t acc_ = 0, p_ = (p), q_, k_ = 0;                                  \
        while ((cond) && acc_ < TIMEOUT) {                                        \
            if (++k_ == 2048) {                                                   \
                k_ = 0;                                                           \
                q_ = frc();                                                       \
                acc_ += (q_ - p_) & 0xffff;                                       \
                p_ = q_;                                                          \
            }                                                                     \
        }                                                                         \
        acc_ += (frc() - p_) & 0xffff;                                            \
        acc_ >= TIMEOUT ? ~0u : acc_ * 8;                                         \
    })

/* the end of a video DMA, three ways (CPU clocks from p, ~0 = not seen): status bit first seen set, then seen clear,
   IRQ 10 taken. IRL 10 (and VBlank) unmasked while waiting. Ends when IRQ 10 has come and the bit reads clear;
   GRACE ticks after the first of those two if the other never comes; TIMEOUT ticks at most. */
#define GRACE (1u << 19)
struct dmaw { uint32_t set, clr, irq; };
static struct dmaw last_dma;
static uint32_t stuck;

static void dma_wait(uint32_t bit, uint32_t p, struct dmaw *r)
{
    uint32_t acc = 0, k = 0, first = ~0u;
    r->set = r->clr = r->irq = ~0u;
    sr(0x90);
    for (;;) {
        uint32_t st = R16(PPU + 0x0c) & bit;
        uint32_t now = ~0u;
        if (st && r->set == ~0u)
            r->set = now = acc + ((frc() - p) & 0xffff);
        else if (!st && r->set != ~0u && r->clr == ~0u)
            r->clr = now = acc + ((frc() - p) & 0xffff);
        if (irq10_n && r->irq == ~0u) {
            int32_t d = (int16_t)(uint16_t)(irq10_frc - p);   /* the IRQ may have come just before p was taken */
            r->irq = (uint32_t)((int32_t)acc + d);
            if (now == ~0u)
                now = acc + ((frc() - p) & 0xffff);
        }
        if (now != ~0u && first == ~0u && (r->irq != ~0u || r->clr != ~0u))
            first = now;
        if (r->irq != ~0u && !st)
            break;
        if (++k == 2048) {
            k = 0;
            uint32_t q = frc();
            acc += (q - p) & 0xffff;
            p = q;
            if (acc >= TIMEOUT || (first != ~0u && acc - first >= GRACE))
                break;
        }
    }
    sr(0xf0);
    r->set = r->set == ~0u ? ~0u : r->set * 8;
    r->clr = r->clr == ~0u ? ~0u : r->clr * 8;
    r->irq = r->irq == ~0u ? ~0u : r->irq * 8;
    W32(0x05110000u, 0);
}

/* before a start write: IRQ 10 acknowledged and its count cleared; a status bit already set is counted (STUCK) */
static void dma_prepare(uint32_t bit)
{
    W32(0x05110000u, 0);
    irq10_n = 0;
    if (R16(PPU + 0x0c) & bit)
        stuck++;
}

/* one list record, command 0: bytes from the graphics flash's start to character RAM CDMA_DEST; returns the FRC
   reading taken just before the start write */
static uint32_t cdma_start(uint32_t bytes)
{
    W16(PPU + 0x86, 0);                       /* the list's bank */
    W32(CHAR_WIN + LIST + 0, (bytes / 8 - 1) & 0x1fffff);
    W32(CHAR_WIN + LIST + 4, CDMA_DEST / 8);
    W32(CHAR_WIN + LIST + 8, 0x400000u / 2);
    W32(CHAR_WIN + LIST + 12, 0x01000000u);
    W16(PPU + 0x96, LIST / 4);
    dma_prepare(2);
    uint32_t p = frc();
    W16(PPU + 0x98, 0x0040);
    return p;
}

static void cdma(uint32_t bytes)
{
    uint32_t p = cdma_start(bytes);
    dma_wait(2, p, &last_dma);
}

/* Red Earth's writes (16-bit halves): source (flash + 0x400000) / 2, destination colour, fade 0 (none), length,
   then 0x0002 (start; bit 0 = length bit 16) */
static void pdma(uint32_t n)
{
    uint32_t src = 0x400000u / 2;
    W16(PPU + 0xa0, src >> 16);
    W16(PPU + 0xa2, src);
    W16(PPU + 0xa4, PDMA_DEST >> 16);
    W16(PPU + 0xa6, PDMA_DEST);
    W16(PPU + 0xa8, 0);
    W16(PPU + 0xaa, 0);
    W16(PPU + 0xac, n);
    dma_prepare(4);
    uint32_t p = frc();
    W16(PPU + 0xae, 0x0002 | ((n >> 16) & 1));
    dma_wait(4, p, &last_dma);
}

/* src/cps3v.c cps3v_vblank's sequence without the scroll writes; the display list stays empty */
static uint32_t sdma(void)
{
    uint32_t p = frc();
    for (int k = 0; k < 4; k++) {
        W16(PPU + 0x82, 8);
        W16(PPU + 0x82, 9);
    }
    uint32_t r = WAIT_WHILE(R16(PPU + 0x0c) & 1, p);
    W16(PPU + 0x82, 0);
    return r;
}

/* channel 0, auto request: TT_DMAC_BYTES from src to main RAM 0x02050000 */
static uint32_t dmac(uint32_t src, uint32_t chcr)
{
    (void)REG32(CHCR0);
    REG32(CHCR0) = 0;                         /* DE off; TE cleared (read, then write 0) */
    (void)REG32(DMAOR);
    REG32(DMAOR) = 0;
    REG32(DMAOR) = 1;                         /* DME */
    REG32(SAR0) = src;
    REG32(DAR0) = 0x02050000u;
    REG32(TCR0) = TT_DMAC_BYTES / ((chcr & 0x0c00) == 0x0c00 ? 16 : 4);
    uint32_t p = frc();
    REG32(CHCR0) = chcr;
    uint32_t r = WAIT_WHILE(!(REG32(CHCR0) & 2), p);
    (void)REG32(CHCR0);
    REG32(CHCR0) = 0;
    return r;
}

/* -------- the table -------- */
static uint32_t frame_clocks(void)
{
    sr(0xa0);                                 /* VBlank (IRL 12) on */
    cps3v_wait_vblank();
    uint32_t v = vbl_count, p = frc();
    uint32_t acc = WAIT_WHILE(vbl_count - v < 16, p);
    sr(0xf0);
    return acc / 16;
}

static uint32_t empty100[3], busy_after, irq_during;

static uint32_t run(const struct tt *t)
{
    switch (t->kind) {
    case TT_FRAME:
        return frame_clocks();
    case TT_ITER:
        return empty100[t->loc] = per_iter100(locate(t), t->a, 0);
    case TT_OP:
        return (uint32_t)(((int32_t)per_iter100(locate(t), t->a, 0) - (int32_t)empty100[t->loc]) / 32);
    case TT_DURING: {
        /* a 1 MB character DMA under the measurement; IRL 10 and VBlank taken during it (best of 3 drops a run hit by
           VBlank); then its end as cdma's, from the start */
        uint32_t p = cdma_start(1u << 20);
        sr(0x90);
        int32_t c = (int32_t)per_iter100(locate(t), t->a, 0);
        sr(0xf0);
        busy_after = (R16(PPU + 0x0c) & 2) ? 1 : 0;
        irq_during = irq10_n ? 1 : 0;
        struct dmaw w;
        dma_wait(2, frc(), &w);
        (void)p;
        return (uint32_t)((c - (int32_t)empty100[t->loc]) / 32);
    }
    case TT_BUSY:
        return busy_after;
    case TT_IRQDUR:
        return irq_during;
    case TT_STUCK:
        return stuck;
    case TT_CDMA:
    case TT_PDMA:
        if (t->v == 0) {
            if (t->kind == TT_CDMA)
                cdma(t->a);
            else
                pdma(t->a);
            return last_dma.set;
        }
        return t->v == 1 ? last_dma.clr : last_dma.irq;
    case TT_SDMA:
        return sdma();
    case TT_DMAC:
        return dmac(t->a, t->v);
    }
    return 0;
}

int main(void)
{
    cps3v_init();
    cps3v_text_init();
    tt_res.magic = 0x54545354u;               /* 'TTST' */
    tt_res.pass = 0;
    tt_res.n = TT_N;
    title();
    for (;;) {
        sr(0xf0);
        stuck = 0;
        for (int i = 0; i < TT_N; i++) {
            uint32_t v = run(&tt_tests[i]);
            tt_res.val[i] = v;
            show(i, v, tt_tests[i].kind);
        }
        if (cram_on) {
            REG8(CCR) = 0x11;                 /* purge, four-way mode, cache on (src/crt0.S) */
            cram_on = 0;
        }
        tt_res.pass++;
        title();
        sr(0xa0);
        for (int f = 0; f < 60; f++)
            cps3v_wait_vblank();
    }
}
