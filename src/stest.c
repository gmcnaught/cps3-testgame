/* CPS3 sound test (tools/stest.py's samples and schedule, through src/cps3s.c): at each VBlank the operations of
   that frame, in order; the text layer names the scene playing. st_frame sits first in RAM (0x02000000, the .trace
   section) for scripts/lua/stest_log.lua, which logs every sound-register write with it. */
#include "cps3v.h"
#include "cps3s.h"
#include "stest.h"

volatile uint32_t vbl_count;
volatile uint32_t st_frame __attribute__((section(".trace")));

static void op_run(const struct st_op *o)
{
    switch (o->op) {
    case OP_SCENE:
        cps3v_text(2, 2, "                                            ");
        cps3v_text(2, 2, st_scenes[o->a]);
        break;
    case OP_VOICE: {
        const struct st_sample *s = &st_samples[o->a];
        cps3s_voice(o->v, s->start, s->end, s->loop, s->looped, (uint32_t)o->b, o->c, o->d);
        break;
    }
    case OP_VOL:
        cps3s_volume(o->v, o->a, o->b);
        break;
    case OP_STEP:
        cps3s_step(o->v, (uint32_t)o->a);
        break;
    case OP_KEYS:
        cps3s_keys((uint16_t)o->a);
        break;
    }
}

int main(void)
{
    st_frame = 0;
    cps3v_init();
    cps3v_text_init();
    cps3v_text(2, 1, "CPS3 SOUND TEST");
    cps3s_init();
    __asm__ volatile("ldc %0, sr" : : "r"(0));   /* interrupts on: VBlank (IRL 12) counts vbl_count */
    uint32_t i = 0;
    for (;;) {
        cps3v_wait_vblank();
        uint32_t f = ++st_frame;
        while (i < ST_OPS && st_ops[i].frame == f)
            op_run(&st_ops[i++]);
        if (f == ST_END_FRAME)
            cps3s_keys(0);
    }
}
