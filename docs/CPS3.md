# CPS3 / jtcps3 hardware notes

Measured on MAME 0.289 (`cps3` driver) and a MiSTer running `jtcps3.rbf` (file date 2026-09-24, beta, release build),
unless marked inferred. Written while porting a game to the CPS3; the programs in this repo (`src/vtest.c`,
`vtest2.c`, `stest.c`) are behind the "Video test", "Video test 2" and "Sound" sections.

## Booting our own program on jtcps3

- Set: Street Fighter III 3rd Strike (Asia 990608, NO CD, `sfiii3na`) layout and keys (`a55432b4` / `0c129981`),
  chosen for its flash: SIMMs 1-2 program, 3-6 graphics and samples (64 MB). `tools/mkcps3.py` encrypts (MAME
  `cps3_mask`; checked: re-encrypting the decrypted Capcom BIOS gives the original bytes) and writes every file of
  the set; `tools/mkmra3.py` writes the MRA (needs the user's `jtbeta.zip`). The jtcps3 MRA header's first 12 bytes
  are region starts in 0x10000 units: SIMM 1 0x0008, 3 0x0088, 4 0x0188, 5 0x0288, 2 0x0388, 6 0x0408 (0x02C8 marks an
  absent SIMM); bytes 0x10-0x17 the keys. The first measurements below (until "Video test") used Red Earth (Asia, NO
  CD, `redearthn`, keys `9e300ab1` / `a175b82c`, 36 MB of flash).
- CPU speed: the same CPU-bound C program (SH-2 at 25 MHz, 419,470 cycles a frame, timed with the free-running
  timer) ran 2.6-3.0x slower per frame on jtcps3 than in MAME. Budget against jtcps3, not MAME.
- MAME fetches opcodes only from the BIOS ROM, SIMM 1/2 (0x06000000) and cache RAM (0xC0000000), not main RAM.
- SIMM 1 files: byte k of each 32-bit word in `simm1.k`, each word encrypted for its address 0x06000000 + offset.
- Reset must program the bus state controller as the BIOS does (BCR1 `0xa55a0020`, BCR2 `0xa55a00e8`, WCR
  `0xa55aaa57`; cache purged off, then on: CCR 0x10 / 0x11). Without it jtcps3 shows nothing; MAME runs anyway.
- Text layer: SS RAM and colour RAM written as 32-bit words (the BIOS's widths); byte writes showed nothing on
  jtcps3. Video registers: Red Earth's boot values (`cps3v_init` in `src/cps3v.c`).
- SH-2 RTE pops PC and SR before its delay slot runs: no stack pop in the slot.
- VBlank = IRL 12, auto-vector 64-71; cleared by a write to 0x05100000.
- Open: jtcps3 reset the program once after loading the SIMM set (a counter in uncleared RAM ran on past its end); cause unknown. Opening the OSD did not save the EEPROM as `.nvm`, for Red Earth either.

## From herzmx/CPS3-CBIOS and the Capcom BIOS

- The BIOS does all I/O and video access through the uncached mirror: `0x24xxxxxx` (sprite / colour RAM, PPU
  registers), `0x25xxxxxx` (inputs, EEPROM, SS RAM and registers, IRQ acks). Our code uses the cached addresses
  (`0x04` / `0x05`): reads of status or input through them can be stale once the cache is on (Inferred from SH-2
  cache rules; not yet seen).
- Inputs: `0x25000000` system word (START 0x1000, coin, service, test), `0x25000002` P1 pad word (up 0x0001, down
  0x0002, left 0x0004, right 0x0008, shot 1-6 from 0x0010), active low.
- Reset order: dispatch stubs from 0x400; cache-as-RAM routine at 0x534 writes `0xFFFFFE80 = 0xBD0F`,
  `0xFFFFFE90` (FMR) `= 2`, the bus controller, CCR; then DMA channel 0 (phase 2), a table of 96 register writes at
  0x61C (phase 3: PPU registers 0x240c0000-0xae, sound `0x240e0200`, `0x25000008 = 0xc000`, `0x25000a20-26`, SS
  registers, `0x25150002`), IRQ acks and `0x25150002 = 0x4642` (phase 4), RAM test, video RAM clears (phases 6-8).
- The FMR / 0xFFFFFE80 writes (added to `src/crt0.S`) did not change the speed on jtcps3 (a CPU-bound
  program from SIMM 1 took the same cycles and frames with and without them). That run did not repeat itself after loading (the
  earlier SIMM run did once); one run, so the cause of the repeat is still open.
- C-BIOS claims (not checked here): colour RAM entry 0 is the backdrop colour on hardware; colour format BGR555.

## Video, from a real game (`scripts/cps3_vlog.sh`, `tools/cps3vlog.py`, `tools/cps3render.py`)

Recorded in MAME 0.289 from `redearthn` (your own set; not included), attract-mode demo fight
on the burning-village stage, frames 4300-5150, camera scrolling and zooming. `cps3_vlog.lua` logs every write to
the PPU registers (0x040c0000-0xaf), SS registers and IRQ acknowledges with the PC and the scan line, reads each
character DMA list, counts CPU writes to sprite and colour RAM, and dumps sprite RAM, the sprite list as the
sprite-list DMA copied it, colour RAM, character RAM (8 MB, through the bank window), SS RAM and registers.

**Check:** `tools/cps3render.py` re-draws a frame from a dump following MAME's `screen_update`; frames 4500, 4800,
4900 (full-screen zoom 0x42) and 5100 match MAME's snapshots exactly (0 of 86,016 pixels differ). The model below is
therefore MAME's, confirmed against MAME's own output; it is not yet checked against jtcps3.

Model (MAME `cps3.cpp`, confirmed by the re-render):

- There are no fixed background layers. One display list in sprite RAM (main list at 0x0000-0x1fff, 4 words a
  record, end marker bit 31) points to sublists; the PPU draws everything in list order, later entries on top.
  A sublist entry with x size 0 draws a band of lines of tilemap 0-3 (`(v3 >> 4) & 3`, up to 128 lines an entry);
  otherwise it is a sprite of 1/2/4/8 x 1/2/4/8 16x16 tiles with consecutive tile numbers, column first, with zoom
  (draw size up to 128 px). Main-list record word 0 bits 28-30 pick one of 8 global scroll registers (0x00-0x1f).
- Tilemaps: 64x64 entries of 32 bits in sprite RAM at `(reg2 >> 16 & 0x7f) << 10` words; the line-scroll table also
  in sprite RAM. Registers per tilemap: scroll X/Y, width, enable (0x8000), line-scroll enable (0x4000), bases.
- Tiles: 16x16, 8 bits a pixel, 256 bytes a tile, only from character RAM (8 MB = 32,768 tiles); pixel 0
  transparent. Colour = pixel | colour code x 256 (8-bit) or x 64 (the "6 bpp" flag, bit 9). The PPU writes
  colour indices (17 bits) to a line buffer; colour RAM (0x04080000, 128 K entries, BGR555, R in bits 0-4) is
  looked up at the end. Index 0 shows where nothing is drawn.
- Full-screen zoom (0x6e / 0x7e, 0x40 = 1:1) scales the whole composed frame; the SS text layer is drawn after it.
- SS text layer: 64x32 8x8 4-bit tiles in SS RAM (tile data at 0x4000), only bits 16-23 and 0-7 of each 32-bit
  word are wired (`umask32 0x00ff00ff`); palette base register 0x12; drawn last, over everything.

What Red Earth does each frame (850 frames, `cps3vlog.py build/vlog/demo/writes.log 4300 5150`):

| Step | Registers | When (scan lines after MAME's frame-done callback) |
|---|---|---|
| Global scrolls 0-7 | 0x00-0x1f, 16-bit halves | 0.1-0.4 |
| Sprite-list DMA: 8, 9, 8, 9, 8, 9, 8, 9 to 0x82; 0 later | 0x80 (low half = 0x82) | 0.5; the 0 at ~2.5 |
| Tilemaps 0-3: scroll, width 0x1f (32 tiles), enable / line scroll, bases | 0x20-0x5f | 0.5-1.4 |
| SS scroll registers | 0x05050000 area | 1.4 |
| Full-screen zoom (11% of frames: special moves) | 0x68-0x7e | 1.5 |
| Character DMA start (62% of frames, one list a frame at character RAM 0x1000) | 0x94, 0x98 | ~5 |
| IRQ 12 acknowledge (VBlank), IRQ 10 acknowledge (character DMA end, same count as DMA starts) | 0x05100000, 0x05110000 | 8-12 |

- Every register write falls within 6 lines of the frame start (VBlank); none later.
- CPU writes to sprite RAM: 623 a frame on average (1,357 bytes), 4,649 at most. Colour RAM: none. All colours
  arrive by palette DMA from the graphics SIMMs (127 transfers on 42 of 850 frames, up to 6,400 colours each,
  34 different fade values; destinations up to colour 0x1e000).
- Character DMA: list records of (command, length, destination, source in the graphics SIMMs); commands seen 4 (set
  the decompression table), 2 (6-bit RLE, 8,434 records) and 0 (uncompressed, 1). 15 KB of tiles a frame on
  average, 950 KB at most (stage start). The game streams animation frames into character RAM as they are needed;
  at frame 4900 the list had 32 main records and ~350 sublist entries, 123 of them in 6-bit colour mode.

For a port (Inferred): a game can load a whole room's tiles into character RAM once (by CPU writes through the
0x04100000 bank window, or by character DMA from SIMM 3+), keep palettes in colour RAM, write one display list a
frame (tilemap bands for the background layers in back-to-front order, then the instances as sprites), and do all
register writes at the start of VBlank as Red Earth does.

## Video test: our own display list on MAME and jtcps3 (`make`, `scripts/cps3_vtest.sh`)

`src/vtest.c` draws `tools/vtest.py`'s scene through `src/cps3v.c` (helpers a port can build on): colours and
16x16 8-bit tiles written by the CPU (colour RAM as 32-bit pairs, character RAM through the 0x04100000 bank window),
two 64x64 tilemaps in sprite RAM drawn as bands of up to 128 lines, then sprites; six phases of 600 frames: three
tilemap scrolls (including 440 px, past a 32-column wrap, and 1000/1000, past the map edges), every sprite size
1/2/4 x 1/2/4 tiles with each flip, and 6-bit colour sprites. `tools/vtest.py` composes the expected screens in
screen coordinates without the CPS3 formulas.

| Check | Result |
|---|---|
| MAME 0.289, snapshots in each phase | 6 of 6 phases: 0 of 86,016 pixels differ |
| jtcps3 (`jtcps3.rbf` 2026-09-24), Red Earth set, 32 screenshots 2 s apart (`scripts/mister_run.sh`, `tools/vtest_check.py`) | Phases 0-4: each has screenshots with 0 pixels differing (12 of 23 shots), after the two corrections below. Phase 5: 6-bit colour sprites 4 tiles wide are drawn 2 tiles wide (3,328 px), with or without word 3 bits 8-9; 1- and 2-tile-wide 6-bit sprites match |
| jtcps3, `sfiii3na` set (2026-10-01), 16 shots 4 s apart | Phases 0-4: shots with 0-15 pixels differing; phase 5: 3,291-3,301 pixels (the same 6-bit sprite difference) |

Measured on jtcps3 (Observed):

- Colour: each 5-bit channel shows as `v << 3 | v >> 2` (31 -> 255, 16 -> 132, 4 -> 33). MAME shows `v << 3`
  (31 -> 248). Expected frames for jtcps3 use the first.
- The screenshot is 384x224 and shows MAME's column x at x - 1 (whole picture, tilemaps and sprites alike: best
  offset over the frame 2,044 px off vs 20,279 unshifted; 0 after the other fixes).
- Single pixels at colour edges (0-18 a shot, different places each shot) take the neighbouring pixel's value:
  the same phase has exact shots, so they vary from frame to frame (see "Screenshot noise" under "Video test 2").
  A frame check on jtcps3 passes when one screenshot of a still frame matches.
- The tilemap width field (0x1f, as Red Earth writes it) does not wrap the map at 32 columns: the 440 px scroll
  shows columns 27-51 as in MAME.
- No reset after loading in this run (the phases advanced in order from the first shot).
- One earlier run (taken after a `/dev/MiSTer_cmd` write blocked for minutes) showed a 6-bit 2x2 sprite missing
  and a flipped 4x2 sprite cut short; the repeat run with the same program matched. Unknown cause; `mister_run3.sh`
  now times out each command write.

For a port: 8-bit colour only (6-bit sprites wider than 2 tiles differ on jtcps3); sprites up to 4x4 tiles (64x64;
x or y size 8 is not usable without zoom: x size 0 is the tilemap command, y size 0 draws nothing); pick each
colour's 5-bit value against jtcps3's expansion.

## Review of the findings above (2026-09-30)

| Finding (above) | State now |
|---|---|
| MAME fetches opcodes only from BIOS ROM, SIMM 1/2, cache RAM | Confirmed in the source: `decrypted_opcodes_map` maps only those three (cps3.cpp:2173) |
| VBlank = IRL 12, cleared at 0x05100000 | Confirmed: map and `vbl_interrupt`; Red Earth acknowledges it once a frame at 0x05100000. Also IRL 10 = character / palette DMA end, cleared at 0x05110000 |
| jtcps3 2.9x slower than MAME, cause no wait states / cache | MAME side confirmed: `sh2.cpp` reads and writes go straight to the address space (no cache, no bus wait model). jtcps3 side still Unknown |
| Hot code in cache RAM (0xC0000000) for speed | Caution: MAME maps only 1 KB there (0xc0000000-0xc00003ff); the SH7604 manual gives 2 KB in two-way mode (CCR TW, PDF p. 231 / 244) and 4 KB with the cache off (p. 240). Code over 1 KB there would run on hardware but not in MAME |
| SS RAM written as 32-bit words; byte writes showed nothing on jtcps3 | Consistent with MAME: SS RAM and registers are on lanes 16-23 and 0-7 only (`umask32 0x00ff00ff`) |
| C-BIOS: colour format BGR555 | Confirmed in MAME (`set_mame_colours`) and by the pixel-exact re-render; not on jtcps3 |
| C-BIOS: colour RAM entry 0 is the backdrop | Confirmed in MAME: the line buffer is cleared to index 0 |
| C-BIOS: cached reads of status/input can be stale | Not testable in MAME (no cache model); still Inferred |
| jtcps3 reset once after loading; `.nvm` not saved | Unchanged, open |

## herzmx/CPS3-CBIOS: what it corroborates (HEAD 1968a3b, 2026-07-17)

The C-BIOS covers boot, the SIMM flash protocols, inputs and a text menu; for the text and PPU set-up it calls the
Capcom BIOS's own routines (`BIOS_MASTER_INIT` at 0x25BC). It contains nothing on the sprite list, tilemaps,
character DMA or palette DMA, so the video model above rests on MAME (and its re-render), not on the C-BIOS.

| C-BIOS statement | Against MAME / our logs |
|---|---|
| Sprite RAM 0x04000000, colour RAM 0x04080000, PPU registers 0x040C0000 | Agrees |
| Colour RAM "~8 KB = 4096 entries" | Disagrees: MAME maps 256 KB (128 K entries) and Red Earth's palette DMA writes up to entry 0x1e000 |
| Colour bit 0 "always 1, valid-colour marker" | Not supported: in MAME bit 0 is the low bit of red; their `0x7C01` is blue 31, red 1 |
| Inputs at 0x25000000 (system word) / 0x25000002 (P1) | Agrees with MAME's 32-bit `INPUTS` port read as two 16-bit halves |
| Uncached mirror 0x2xxxxxxx for I/O | Agrees with `sh2.cpp` (0x2 area masked to the same devices); the cache effect is not modelled by MAME |
| sh7604.h DMAOR address wrong (their own note) | Not used by us |

## Video test 2: the features a port uses (`make vtest2`, `scripts/cps3_vtest.sh vtest2`)

`src/vtest2.c` draws `tools/vtest2.py`'s scene: four 64x64 tilemaps as bands back to front (tilemap 3 on lines
96-223 only), tiles from all 8 character RAM banks (tile numbers up to 32,767 through the bank window), colour codes
up to 0x1ff (colour RAM entries up to 0x1ffff); six phases: parallax scrolls, tilemap 3 past the 1024-pixel wrap,
vertical scrolls of 500, 1000, 1010 and -30, 120 sprites interleaved between the bands (sprites partly off every
edge), the same split into four main-list records, 600 sprites (more than the 511 entries a sublist holds: two
main-list records of 511 and 96 entries), and last the 120-sprite scene after the program rewrites part of character
RAM and colour RAM while running (and reads both back through the uncached mirror; a difference would show on the text
layer).

| Check | Result |
|---|---|
| MAME 0.289, snapshots in each phase | 7 of 7 phases: 0 of 86,016 pixels differ |
| jtcps3 (`jtcps3.rbf` 2026-09-24), 16 shots 5 s apart, `tools/vtest_check.py` | Phases 0-4: shots with 0-9 pixels differing (screenshot noise, below) |
| jtcps3, phase 5 (600 sprites) | 8,329-8,335 pixels differ; the shots equal the screen composed without the second main-list record (6-8 pixels) |
| jtcps3, phase 6 (reload) | The screen keeps the old tiles of tilemaps 0 and 3 and of the reloaded sprite tile; the new colours show (shots equal phase 3's screen but for the reloaded colours, 456-533 pixels). The read-back found every rewritten tile and colour equal to what was written |

Observed on jtcps3, not explained (the jtcps3 HDL was not read):

- Character RAM written by the CPU after the first frames reads back correctly but is not drawn: the tiles drawn
  stay those written at start-up. Colour RAM writes at the same time are drawn. Not tried: character DMA, writing
  with the display off or with the tiles not in use.
- In one run (the first, before the read-back was added) some tiles written at start-up drew as partly written (the
  first column of a 4x4 sprite, tiles 20,495-20,498, and tiles 32,764-32,767); the three runs after it drew every
  start-up tile correctly. Unknown cause.
- A display list of two main-list records with 511 and 96 entries draws only the first; four records of about 32
  entries each draw correctly. Either about 511 entries a frame is a limit, or a record after a full 511-entry
  sublist is lost: not yet told apart.
- Screenshot noise: with the program frozen (`CDEFS=-DFREEZE_AT=1500`: no video writes after frame 1,500, only the
  VBlank acknowledge), shots of the still screen still differ from the expected one by 3-97 scattered single pixels,
  different in each shot. 190 of 193 wrong pixels in 7 frozen shots repeat the pixel to their right (3 the one to
  their left). The screenshot is a plain copy of the MiSTer scaler's input frame buffer (Main_MiSTer
  `user_io_screenshot` -> `mister_scaler_read_32`, no filtering), and every frame of a frozen screen should be the
  same, so the frames written to that buffer differ: jtcps3's video output, or the scaler's sampling of it, is one
  pixel early on some frames (Inferred; which of the two is Unknown).

## Sound (`make stest`, `scripts/cps3_stest.sh`)

16 voices of signed 8-bit PCM read from the sample flash (SIMMs 3-6), no sound CPU (MAME `cps3_a.cpp`). Registers,
32-bit, voice v at 0x040e0000 + 32 v (`src/cps3s.c` writes them through the cache-through mirror 0x240e0000):

| Register | Bits |
|---|---|
| 1 | start address, 16-bit halves swapped |
| 2 | bit 0: loop on |
| 3 | bits 16-31 step (1/4096 sample per output sample), 0-15 loop address bits 0-15 |
| 4 | loop address bits 16-31 |
| 5, 6 | end address, halves swapped; games write both equal (which one is a loop end is unknown) |
| 7 | volume, signed 16-bit: bits 16-31 heard on the left speaker in MAME, 0-15 on the right (see below) |
| 0x040e0200 | bits 16-31: key on per voice; off -> on restarts the voice at its start |

- Chip address = sample flash byte offset + 0x400000. MAME's sample region (user5) holds, per pair of flash chips
  (2j, 2j + 1) covering 4 MB, byte 4w + 0 / 1 / 2 / 3 = chip 2j + 1 byte 2w, chip 2j byte 2w, chip 2j + 1 byte
  2w + 1, chip 2j byte 2w + 1 (`tools/mkcps3.py` writes the chips from a flat image).
- Output rate clock / 384 = 37,286 Hz; per voice sample x volume / 2^23. The position advances by step / 4096 a
  sample; at end it jumps to loop (loop on) or the voice goes silent and stays keyed (loop off).
- Left / right (Observed in MAME): `cps3.cpp` routes chip output 1, computed from register 7 bits 16-31 (which
  `cps3_a.cpp` names "volume right"), to the left speaker, and output 0 (bits 0-15) to the right. A voice with only
  bits 0-15 set is silent on the left of MAME's WAV. Not checked on hardware.
- Register writes while a voice plays (volume, step) take effect at once.

`src/stest.c` plays `tools/stest.py`'s schedule (scenes A-G: one-shot, intro + loop, pan, step change, left / right,
negative volume, two voices cancelling, pitch x1 / x2 / x3 / x1/4, samples in SIMMs 4, 5 and 6, all 16 voices,
restart by key off -> on, key-on while on); the text layer names the scene.

| Check | Result |
|---|---|
| MAME 0.289: the 250 register writes, with their frame, against the schedule | Equal |
| MAME 0.289: `-wavwrite` at 37,286 Hz, both channels, against the chip computed from the logged writes (`tools/stest_check.py`) | Every sample equal (max error 0 LSB), 24.2 s |
| jtcps3 | Runs: the text layer names each scene in turn (screenshots); audio not captured or compared yet |

## Inferred, not tested

Sound capacity: the 64 MB of sample flash in the `sfiii3na` layout hold about 35 minutes of 8-bit PCM at 32 kHz
(less space if graphics share the flash).
