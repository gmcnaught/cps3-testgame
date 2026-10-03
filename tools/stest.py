#!/usr/bin/env python3
"""CPS3 sound test (src/stest.c, sdk/src/cps3s.c): generated samples and a schedule of voice operations by frame.
    stest.py <out_dir>      -> <out_dir>/stest.h, stest.bin, stest_writes.txt
stest.bin: the sample flash image (byte k = chip address 0x400000 + k; tools/mkcps3.py puts it in SIMMs 3-6).
stest.h: the samples' chip addresses and the schedule for src/stest.c. stest_writes.txt: the sound-register writes
the program must make, "<frame> <word offset> <data hex>" (word offset as MAME's sound_w: voice v register r at
8 v + r, the key register at 0x80), checked by tools/stest_check.py.

Scenes (the text layer names the one playing):
  A  one-shot sine, ends by itself while keyed, then keyed off
  B  intro + loop (loop start after the start), volume to left only while playing, step halved while playing
  C  noise left only, then right only; one sine at volume -0x4000, then two voices keyed in one write with
     volumes +0x4000 and -0x4000 on the same sample (they cancel: silence)
  D  one-period sawtooth loop at steps 4096, 8192, 12288, 1024 (pitch x1, x2, x3, x1/4)
  E  three tones stored in SIMMs 4, 5 and 6 (chip addresses past 16, 32 and 48 MB)
  F  all 16 voices at once (the same loop at 16 steps), keyed on and off in one write each
  G  a short blip restarted by key off -> key on in the same frame, 10 times; a key-on write to a voice already
     on (no restart: the sine plays on)
"""
import math
import os
import sys

RATE = 37286
BASE = 0x400000
MB = 1 << 20


def clip8(v):
    return max(-128, min(127, int(round(v))))


def sine(freq, secs, amp=100):
    return [clip8(amp * math.sin(2 * math.pi * freq * i / RATE)) for i in range(int(secs * RATE))]


def samples():
    """name -> (signed bytes, loop offset or None, image offset or None = next free)"""
    S = {}
    S['sine440'] = (sine(440, 1.0), None, None)
    intro = [clip8(90 * math.sin(2 * math.pi * (200 + 600 * i / (RATE / 4)) * i / RATE)) for i in range(RATE // 4)]
    per = RATE // 220                                         # 169 samples: a whole number of periods loops cleanly
    sq = ([80] * (per // 2) + [-80] * (per - per // 2)) * 110
    S['introloop'] = (intro + sq, len(intro), None)
    x, noise = 1, []
    for _ in range(RATE // 2):
        x = (x * 1103515245 + 12345) & 0x7fffffff
        noise.append(((x >> 16) & 0xff) - 128)
    S['noise'] = ([clip8(v * 0.6) for v in noise], None, None)
    S['saw'] = ([clip8(-100 + 200 * i / 170) for i in range(170)], 0, None)
    S['tone_simm4'] = (sine(330, 0.5), None, 16 * MB + 0x1234 * 4)
    S['tone_simm5'] = (sine(523.25, 0.5), None, 32 * MB + 0x5678 * 4)
    S['tone_simm6'] = (sine(659.25, 0.5), None, 48 * MB + 0x9abc * 4)
    S['blip'] = ([clip8(110 * math.sin(2 * math.pi * 1200 * i / RATE) * (1 - i / 1500)) for i in range(1500)],
                 None, None)
    return S


def layout(S):
    img = bytearray()
    table = {}
    for name, (d, loop, at) in S.items():
        if at is None:
            at = (len(img) + 3) & ~3
        if len(img) < at:
            img += bytes(at - len(img))
        img[at:at + len(d)] = bytes(v & 0xff for v in d)
        start = BASE + at
        table[name] = (start, start + len(d), start + (loop if loop is not None else 0), loop is not None)
    return img, table


def schedule():
    """[(frame, op, args)]: ('scene', text), ('voice', v, sample, step, vol_l, vol_r), ('vol', v, l, r),
    ('step', v, step), ('keys', mask), ('poke', bits, addr, value) (a 16- or 32-bit write; tools/btest.py), in program
    order within a frame"""
    E = []

    def at(f, *op):
        E.append((f, op))

    at(1, 'scene', 'A ONE-SHOT SINE 440 HZ')
    at(30, 'voice', 0, 'sine440', 4096, 0x4000, 0x4000)
    at(30, 'keys', 0x0001)
    at(120, 'keys', 0x0000)
    at(150, 'scene', 'B INTRO + LOOP, PAN, STEP')
    at(150, 'voice', 1, 'introloop', 4096, 0x3000, 0x3000)
    at(150, 'keys', 0x0002)
    at(270, 'vol', 1, 0x3000, 0)
    at(330, 'step', 1, 2048)
    at(390, 'keys', 0x0000)
    at(420, 'scene', 'C LEFT, RIGHT, NEGATIVE VOLUME')
    at(420, 'voice', 2, 'noise', 4096, 0x3000, 0)
    at(420, 'keys', 0x0004)
    at(470, 'voice', 3, 'noise', 4096, 0, 0x3000)
    at(470, 'keys', 0x0008)
    at(520, 'voice', 4, 'sine440', 4096, -0x4000, -0x4000)
    at(520, 'keys', 0x0010)
    at(580, 'keys', 0x0000)
    at(590, 'voice', 4, 'sine440', 4096, -0x4000, -0x4000)
    at(590, 'voice', 5, 'sine440', 4096, 0x4000, 0x4000)
    at(590, 'keys', 0x0030)
    at(630, 'keys', 0x0000)
    at(640, 'scene', 'D PITCH X1 X2 X3 X1/4')
    at(640, 'voice', 6, 'saw', 4096, 0x3000, 0x3000)
    at(640, 'keys', 0x0040)
    at(700, 'step', 6, 8192)
    at(760, 'step', 6, 12288)
    at(820, 'step', 6, 1024)
    at(880, 'keys', 0x0000)
    at(900, 'scene', 'E SAMPLES IN SIMM 4, 5, 6')
    at(900, 'voice', 7, 'tone_simm4', 4096, 0x4000, 0x4000)
    at(900, 'keys', 0x0080)
    at(960, 'voice', 8, 'tone_simm5', 4096, 0x4000, 0x4000)
    at(960, 'keys', 0x0180)
    at(1020, 'voice', 9, 'tone_simm6', 4096, 0x4000, 0x4000)
    at(1020, 'keys', 0x0380)
    at(1080, 'keys', 0x0000)
    at(1100, 'scene', 'F ALL 16 VOICES')
    for v in range(16):
        at(1100, 'voice', v, 'saw', 1024 * (v + 1) // 2, 0x0600, 0x0600)
    at(1100, 'keys', 0xffff)
    at(1220, 'keys', 0x0000)
    at(1260, 'scene', 'G RESTART, KEY ON WHILE ON')
    at(1260, 'voice', 10, 'blip', 4096, 0x4000, 0x4000)
    at(1260, 'keys', 0x0400)
    for k in range(1, 11):
        at(1260 + 6 * k, 'keys', 0x0000)
        at(1260 + 6 * k, 'keys', 0x0400)
    at(1340, 'voice', 11, 'sine440', 4096, 0x3000, 0x3000)
    at(1340, 'keys', 0x0800)
    at(1370, 'keys', 0x0800)
    at(1400, 'keys', 0x0000)
    at(1430, 'scene', 'END')
    return E, 1440


def main():
    out = sys.argv[1]
    E, end = schedule()
    emit(out, 'stest', samples(), E, end)


def emit(out, name, S, E, end):
    """<out>/<name>.bin, .h, _writes.txt from samples S and schedule E (also tools/atest.py)"""
    os.makedirs(out, exist_ok=True)
    img, table = layout(S)
    names = list(S)
    open(os.path.join(out, f'{name}.bin'), 'wb').write(bytes(img))
    scenes = [op[1] for _, op in E if op[0] == 'scene']
    with open(os.path.join(out, f'{name}.h'), 'w') as f:
        f.write(f'/* generated by tools/{name}.py */\n')
        f.write(f'#define ST_END_FRAME {end}\n')
        f.write('static const struct st_sample { uint32_t start, end, loop; uint8_t looped; } st_samples[] = {\n')
        for n in names:
            s, e, lp, on = table[n]
            f.write(f'    {{0x{s:x}, 0x{e:x}, 0x{lp:x}, {int(on)}}},   /* {n} */\n')
        f.write('};\n')
        f.write('static const char *const st_scenes[] = {\n' + ''.join(f'    "{t}",\n' for t in scenes) + '};\n')
        f.write('enum { OP_SCENE, OP_VOICE, OP_VOL, OP_STEP, OP_KEYS, OP_POKE };\n')
        f.write('static const struct st_op { uint16_t frame; uint8_t op, v; int32_t a, b, c, d; } st_ops[] = {\n')
        sc = 0
        for fr, op in E:
            if op[0] == 'scene':
                f.write(f'    {{{fr}, OP_SCENE, 0, {sc}, 0, 0, 0}},\n')
                sc += 1
            elif op[0] == 'voice':
                f.write(f'    {{{fr}, OP_VOICE, {op[1]}, {names.index(op[2])}, {op[3]}, {op[4]}, {op[5]}}},\n')
            elif op[0] == 'vol':
                f.write(f'    {{{fr}, OP_VOL, {op[1]}, {op[2]}, {op[3]}, 0, 0}},\n')
            elif op[0] == 'step':
                f.write(f'    {{{fr}, OP_STEP, {op[1]}, {op[2]}, 0, 0, 0}},\n')
            elif op[0] == 'poke':
                f.write(f'    {{{fr}, OP_POKE, {op[1]}, 0x{op[2]:08x}, 0x{op[3]:08x}, 0, 0}},\n')
            else:
                f.write(f'    {{{fr}, OP_KEYS, 0, {op[1]}, 0, 0, 0}},\n')
        f.write('};\n#define ST_OPS (sizeof st_ops / sizeof st_ops[0])\n')
    # the register writes sdk/src/cps3s.c makes for the schedule
    sw = lambda a: ((a >> 16) | (a << 16)) & 0xffffffff
    loop_lo = [0] * 16
    w = []
    for fr, op in E:
        if op[0] == 'voice':
            v, (s, e, lp, on) = op[1], table[op[2]]
            loop_lo[v] = lp & 0xffff
            w += [(fr, 8 * v + 1, sw(s)), (fr, 8 * v + 2, int(on)), (fr, 8 * v + 3, (op[3] << 16 | loop_lo[v])),
                  (fr, 8 * v + 4, lp >> 16), (fr, 8 * v + 5, sw(e)), (fr, 8 * v + 6, sw(e)),
                  (fr, 8 * v + 7, (op[4] & 0xffff) << 16 | (op[5] & 0xffff))]
        elif op[0] == 'vol':
            w.append((fr, 8 * op[1] + 7, (op[2] & 0xffff) << 16 | (op[3] & 0xffff)))
        elif op[0] == 'step':
            w.append((fr, 8 * op[1] + 3, op[2] << 16 | loop_lo[op[1]]))
        elif op[0] == 'keys':
            w.append((fr, 0x80, op[1] << 16))
        elif op[0] == 'poke' and 0x040e0000 <= op[2] < 0x040e0300:
            w.append((fr, (op[2] - 0x040e0000) // 4, op[3]))
    with open(os.path.join(out, f'{name}_writes.txt'), 'w') as f:
        f.write(''.join(f'{fr} {o} {d:08x}\n' for fr, o, d in w))
    print(f'{out}: {len(names)} samples, {len(img)} bytes of sample flash, {len(E)} operations, {len(w)} writes')


if __name__ == '__main__':
    main()
