# CPS3 / jtcps3 hardware notes

Measured on MAME 0.289 (`cps3` driver, stand-in set `redearthn`) and a MiSTer running `jtcps3.rbf` (file date
2026-09-24, beta, release build), unless marked inferred. Written while porting a game to the CPS3; the test game in
this repo (`src/vtest.c`) is the program behind the "Video test" section.

## Booting our own program on jtcps3

- Set: Red Earth (Asia, NO CD) layout and keys (`9e300ab1` / `a175b82c`, in the MRA header); `tools/mkcps3.py`
  encrypts (MAME `cps3_mask`; checked: re-encrypting the decrypted Capcom BIOS gives the original bytes),
  `tools/mkmra3.py` writes the MRA (needs the user's `jtbeta.zip`).
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
| jtcps3 (`jtcps3.rbf` 2026-09-24), 32 screenshots 2 s apart (`scripts/mister_run.sh`, `tools/vtest_check.py`) | Phases 0-4: each has screenshots with 0 pixels differing (12 of 23 shots), after the two corrections below. Phase 5: 6-bit colour sprites 4 tiles wide are drawn 2 tiles wide (3,328 px), with or without word 3 bits 8-9; 1- and 2-tile-wide 6-bit sprites match |

Measured on jtcps3 (Observed):

- Colour: each 5-bit channel shows as `v << 3 | v >> 2` (31 -> 255, 16 -> 132, 4 -> 33). MAME shows `v << 3`
  (31 -> 248). Expected frames for jtcps3 use the first.
- The screenshot is 384x224 and shows MAME's column x at x - 1 (whole picture, tilemaps and sprites alike: best
  offset over the frame 2,044 px off vs 20,279 unshifted; 0 after the other fixes).
- Single pixels at colour edges (0-18 a shot, different places each shot) take the neighbouring pixel's value:
  screenshot capture, not drawing (the same phase has exact shots). A frame check on jtcps3 passes when one
  screenshot of a still frame matches.
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

## Inferred, not tested

Sound: 16 channels of 8-bit PCM read from the SIMM (graphics) flash, no sound CPU (MAME `cps3_a.cpp`); Red Earth's
layout has 0x2C80000 bytes of SIMM, so ~25 MB of 12 kHz 8-bit music fits as PCM.
