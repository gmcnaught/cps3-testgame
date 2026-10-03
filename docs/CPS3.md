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
  jtcps3. Video registers: Red Earth's boot values (`cps3v_init` in `sdk/src/cps3v.c`). Since the SDK (2026-10-03)
  `cps3v_init` writes the output port 0x05000008 = 0xc003 (coins accepted; the BIOS writes 0xc000, which MAME treats
  as coins locked out) and builds each frame's sublists in two alternating areas (0x2000 / 0x6000); the MAME checks
  give the same results. jtcps3 (`.rbf` 2026-10-02, .81) re-run on the SDK build: `vtest`, `vtest2`, `vtest3`,
  `dtest` and `dmap` as recorded below (README "Results so far" has the pixel counts).
- SH-2 RTE pops PC and SR before its delay slot runs: no stack pop in the slot.
- VBlank = IRL 12, auto-vector 64-71; cleared by a write to 0x05100000.
- Open: jtcps3 reset the program once after loading the SIMM set (a counter in uncleared RAM ran on past its end); cause unknown. Opening the OSD did not save the EEPROM as `.nvm`, for Red Earth either.

## From herzmx/CPS3-CBIOS and the Capcom BIOS

- The BIOS does all I/O and video access through the uncached mirror: `0x24xxxxxx` (sprite / colour RAM, PPU
  registers), `0x25xxxxxx` (inputs, EEPROM, SS RAM and registers, IRQ acks). Our code uses the cached addresses
  (`0x04` / `0x05`): reads of status or input through them can be stale once the cache is on (Inferred from SH-2
  cache rules; not yet seen).
- Inputs: `0x25000000` system word (START 0x1000, coin, service, test), `0x25000002` P1 pad word (up 0x0001, down
  0x0002, left 0x0004, right 0x0008, shot 1-6 from 0x0010), active low. Corrected 2026-10-03 from MAME's port map
  (cps3.cpp INPUTS / EXTRA; `sdk/src/cps3io.c`): the 32-bit word at 0x05000000 holds P1 up / down / left / right /
  buttons 1-3 in bits 0-6 and P2's in bits 8-14, service 16, test 17, coin 1 / 2 24 / 25, P2 button 6 26, start 1 / 2
  28 / 29; buttons 4-6 are at 0x05000004 (P1 bits 19 / 18 / 17, P2 4 / 5 bits 20 / 21), not in the pad word. Checked
  in MAME for P1 right and button 1 (`examples/hello`); not on jtcps3 or a board.
- Reset order: dispatch stubs from 0x400; cache-as-RAM routine at 0x534 writes `0xFFFFFE80 = 0xBD0F`,
  `0xFFFFFE90` (FMR) `= 2`, the bus controller, CCR; then DMA channel 0 (phase 2), a table of 96 register writes at
  0x61C (phase 3: PPU registers 0x240c0000-0xae, sound `0x240e0200`, `0x25000008 = 0xc000`, `0x25000a20-26`, SS
  registers, `0x25150002`), IRQ acks and `0x25150002 = 0x4642` (phase 4), RAM test, video RAM clears (phases 6-8).
- The FMR / 0xFFFFFE80 writes (added to `sdk/src/crt0.S`) did not change the speed on jtcps3 (a CPU-bound
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

`src/vtest.c` draws `tools/vtest.py`'s scene through `sdk/src/cps3v.c` (helpers a port can build on): colours and
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
main-list records of 511 and 96 entries), the same 600 in three records of 200, 200 and 207 entries, 524 sprites in
records of 10, 511 and 10 entries, column streaming (tilemap 1 scrolled 6 px a frame to x 1500 through a
256-column level, each column written into the 64-column map, unit 5, just before it shows), tilemap 0 switched to
data unit 6 with tilemap 2 disabled (its band still listed), sprites from 300 tiles uploaded in one `cps3v_tiles` call
across the bank 5 / 6 boundary plus black masks (a colour code whose colours are all 0), and last the 120-sprite scene after the program rewrites part of character
RAM and colour RAM while running (and reads both back through the uncached mirror; a difference would show on the text
layer).

| Check | Result |
|---|---|
| MAME 0.289, snapshots in each phase | 12 of 12 phases: 0 of 86,016 pixels differ |
| jtcps3, the three long lists (run of 2026-10-01 17:00): screenshots against the screen composed with only the first K sprites | 511 + 96, 200 / 200 / 207 and 10 / 511 / 10 entries: each best at K = 504 (3-5 px, noise), i.e. the first 511 entries of the frame with the 7 band entries; drawing all sprites: 8,303 / 8,305 / 3,077 px; losing only the record after the full one (10 / 511 / 10): 1,581 px |
| jtcps3 (`jtcps3.rbf` 2026-09-24), 16 shots 5 s apart, `tools/vtest_check.py` | Phases 0-4: shots with 0-9 pixels differing (screenshot noise, below) |
| jtcps3, phases 6-8 (streaming, data unit switch and layer off, one-call upload across banks and black masks; run of 2026-10-01 16:50) | 0-3 pixels differ (screenshot noise). In the same run phases 0-3 had 8-40 differing pixels in every shot, all 256 of them repeating the pixel to their right (the noise below) |
| jtcps3, phase 5 (600 sprites) | 8,329-8,335 pixels differ; the shots equal the screen composed without the second main-list record (6-8 pixels) |
| jtcps3, last phase (reload) | The screen keeps the old tiles of tilemaps 0 and 3 and of the reloaded sprite tile; the new colours show (shots equal phase 3's screen but for the reloaded colours, 456-533 pixels). The read-back found every rewritten tile and colour equal to what was written |

Observed on jtcps3, not explained (the jtcps3 HDL was not read):

- Character RAM written by the CPU after the first frames reads back correctly but is not drawn: the tiles drawn
  stay those written at start-up. Colour RAM writes at the same time are drawn. Later measured (`dmap`, below): with
  the display on, CPU writes lose the last 8 tiles of each 64-tile block; with the display list empty they are all
  drawn; character DMA works.
- In one run (the first, before the read-back was added) some tiles written at start-up drew as partly written (the
  first column of a 4x4 sprite, tiles 20,495-20,498, and tiles 32,764-32,767); the three runs after it drew every
  start-up tile correctly. Unknown cause.
- Only the first 511 display-list entries of a frame are drawn (tilemap bands and sprites alike), however they are
  split into main-list records: the cut falls at entry 511 with no record full (200 / 200 / 207) and inside a full
  record (10 / 511 / 10). MAME draws every entry. Whether the real board has such a limit is Unknown: next, the
  entries per frame real games use (MAME logs of real sets), and the jtcps3 source.
- Screenshot noise: with the program frozen (`CDEFS=-DFREEZE_AT=1500`: no video writes after frame 1,500, only the
  VBlank acknowledge), shots of the still screen still differ from the expected one by 3-97 scattered single pixels,
  different in each shot. 190 of 193 wrong pixels in 7 frozen shots repeat the pixel to their right (3 the one to
  their left). The screenshot is a plain copy of the MiSTer scaler's input frame buffer (Main_MiSTer
  `user_io_screenshot` -> `mister_scaler_read_32`, no filtering), and every frame of a frozen screen should be the
  same, so the frames written to that buffer differ: jtcps3's video output, or the scaler's sampling of it, is one
  pixel early on some frames (Inferred; which of the two is Unknown).

## Character DMA (`make dtest`, `make dmap`; 2026-10-02)

How a program loads tiles while it runs, as the games do: the video chip copies them from the graphics flash
(SIMMs 3-6, MAME's `user5`) into character RAM. Format from MAME 0.289 `cps3.cpp` (`process_character_dma`,
`do_char_dma`, `do_alt_char_dma`), start-up writes from Red Earth (`scripts/cps3_vlog.sh`):

- The list lives in character RAM (Red Earth: byte 0x1000), written by the CPU through the bank window. Records of
  three 32-bit words: (command << 21 | (length / 8 - 1)), destination byte / 8, (source + 0x400000) / 2 with the
  source counted from the start of the graphics flash. Bit 24 of a record's first word ends the list.
- Commands: 0 copies length bytes; 4 sets the decompression table (its source address); 2 decodes 6bpp run-length
  data (a byte under 0x40 is a pixel, 0x40 | n repeats the last pixel n + 1 times, 0x80 | i writes table pair i);
  3 decodes 8bpp run-length data (a control byte for each 8 items, bit 7 first: set = a table pair by index, clear =
  a pixel byte; after two equal bytes in a row the next byte is a count of (count + 1) & 0xff more copies). For 2
  and 3 the length counts bytes written.
- Start: 16-bit writes 0x040c0096 = list word address (byte address / 4), 0x040c0098 = 0x0040 | address bits 16-21
  (MAME: bit 6 starts the list; Red Earth's value 0x0040). Busy: 0x040c000c bit 1 (read through the uncached
  mirror). End: IRQ 10, acknowledged by a write to 0x05110000; these programs mask IRL 10 (SR 0xa0) and poll.
  Found later (`ttest`, 2026-10-03): on jtcps3 the busy bit comes up 120-576 CPU clocks after the start write, so
  `dtest`'s and `dmap`'s poll returns at once there, before the DMA has run. Their results below stand: each is
  judged on screens taken frames later (Inferred: their CPU read-backs, MAME only, would trail a jtcps3 DMA). A DMA
  started while another still runs was not tested; `sdk/src/cps3dma.c` waits for IRQ 10 instead.
- Byte order: DMA source byte a is byte a ^ 1 of the flash image as `tools/mkcps3.py` takes it (the sound chip reads
  byte a): measured in MAME, where a ^ 2 gave each 32-bit word's bytes reversed. Pixels land in character RAM in
  order, left pixel first, as CPU-written tiles. Palette DMA reads the same way: colour i of a source is image bytes
  2i + 1 (bits 8-15) and 2i (bits 0-7) (measured in MAME by `examples/hello`, colour RAM read back; jtcps3 draws
  the same colours). `sdk/tools/cps3asset.py` stores tiles and colours so.

| Test | MAME 0.289 | jtcps3 (`.rbf` 2026-09-24) |
|---|---|---|
| `dtest`: command 0 over 288 tiles on screen (two records), into fresh tiles (0x4000), 16 tiles a frame for 18 frames, 1 MB in one record across the 1 MB bank boundary | 5 of 5 phases exact, read-back equal | 5 of 5 phases exact (12 shots) |
| `dmap`: 312 labelled tiles a step: command 0 twice over the tiles on screen, into fresh tiles, with the display list empty; CPU writes with the display list empty; commands 4 + 2 twice; commands 4 + 3 twice (8-bit pens 0x9a / 0xe5, table pairs on odd tiles) | 10 of 10 steps | 10 of 10 steps |
| `dmap` `cpu_on`: CPU writes over the tiles on screen with the display on | 312 of 312 cells | 280 of 312: in each 64-tile block the last 8 tiles keep their old pixels (cells 56-63, 120-127, ...); the next DMA replaces them all |

A first `dtest` palette repeated every 32 pens (pen i and i + 32 the same colour), so phases 2 and 4 drew like
phase 0 and phase 3 like phase 1, and the shots were read as failures; `dmap` labels each tile instead, and `dtest`
now has one colour per pen.

## Sound (`make stest`, `scripts/cps3_stest.sh`)

16 voices of signed 8-bit PCM read from the sample flash (SIMMs 3-6), no sound CPU (MAME `cps3_a.cpp`). Registers,
32-bit, voice v at 0x040e0000 + 32 v (`sdk/src/cps3s.c` writes them through the cache-through mirror 0x240e0000):

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

### Sample addressing (`make atest`, `scripts/cps3_stest.sh atest`)

| Check | Result |
|---|---|
| MAME 0.289 | The 360 writes equal; every sample equal to the model; `tools/atest_decode.py` reads 40 of 40 codes |
| jtcps3 (.rbf 2026-09-24, by ear, 2026-10-02) | Blocks 0-15 right; 16 -> 0, 17 -> 1, 24 -> 8, 32 -> 0, 48 -> 0, 63 -> 15: the chip reads offset mod 16 MB, voices 0 and 1 alike; register 0x84 = 0x00230000 (written by 3rd Strike and Red Earth at start-up, ignored by MAME) changes nothing |
| Hardware (validated outside this repo, 2026-10-03) | The sound chip addresses only the 16 MB of SIMM 3: jtcps3's result is the hardware behaviour; MAME's 64 MB reach is more permissive than the board |

3rd Strike in MAME (`sfiii3n` attract, 240 s): 3,868 key-ons, every start below 7.6 MB of the sample flash; every
sound register written as two 16-bit halves; register 0 always 0.

## Timing (`make ttest`, `scripts/cps3_ttest.sh`; 2026-10-03)

`src/ttest.c` times everything with the SH7604 free-running timer (FRC, phi / 8, its reset setting; byte reads,
high byte first). Instruction and memory rows: a loop of 32 copies of one operation, timed at n and 2n iterations
(the call and timer reads cancel), minus the empty loop from the same code location, interrupts masked, median of 3.
Character and palette DMA: three times from the start write, from one transfer: the status bit first seen set (SET),
seen clear again (CLR), and IRQ 10 taken (IRQ; `sdk/src/crt0.S` `irq10` reads FRC, IRL 10 unmasked while waiting). Table,
units and the manual's figures: `tools/ttest.py`, `tools/ttest_check.py`.

| Rows | MAME 0.289 | jtcps3 (`.rbf` 2026-10-02) | SH7604 manual |
|---|---|---|---|
| CPU clocks a frame | 419,433 (25 MHz / 59.6 Hz = 419,470) | 419,199 | - |
| Empty loop (DT + BF taken) | 4 | 4 | 4 |
| NOP, ADD, DIV1, BT not taken | 1 | 1 | 1 |
| BRA + NOP, BF taken | 3 | 3 | 3 |
| MUL.L, DMULS.L back to back / MULS.W | 2 / 1 | 6.37 / 1.96 | 2-4 / 1-3 |
| Load + ADD not using it / using it | 2 / 2 | 3 / 3 | 2 / 3 (load-use slot, programming manual 7.5) |
| Load from main RAM through the cache (hit after the first loop) | 1 | 1.50 | 1 |
| Uncached 32-bit load: main RAM, sprite, colour, character, SS RAM, inputs / BIOS ROM / SIMM 1 / 16-bit PPU status | 1 | 7.50 / 8.50 / 4.50 / 4.50 | 1 + bus cycles |
| 32-bit store, every area, cached address or not | 1 | 6.06 | 1 + bus cycles |
| Character DMA 256 B: SET / CLR / IRQ | 72 / 2,616 / 2,512 | 576 / 1,256 / 952 | - |
| Character DMA 4 KB | 56 / 2,560 / 2,512 | 120 / 9,104 / 9,032 | - |
| Character DMA 64 KB | 56 / 2,560 / 2,512 | 128 / 142,648 / 142,584 | - |
| Character DMA 1 MB | 56 / 2,560 / 2,512 | 128 / 2,277 K / 2,277 K (shown in thousands) | - |
| Palette DMA 256 colours | 56 / 2,552 / 2,512 | 152 / 648 / 568 | - |
| Palette DMA 8,192 colours | 56 / 2,552 / 2,512 | 128 / 14,456 / 14,384 | - |
| Sprite-list DMA (empty list) | 120 | 712 | - |
| DMAC 4 KB: burst / cycle steal / 16-byte units / from SIMM 1 | 2,072 / 2,072 / 152 / 2,072 | 13,808 / 13,344 / 3,168 / 10,424 | - |
| Loads during a 1 MB character DMA (main RAM, sprite RAM) | 1 (DMA ended during the measurement) | 7.50, as without (DMA still running at the end) | - |
| DMAs started with their status bit already set | 0 | 0 | - |
| SIMM 1 past the cache: empty loop / NOP | 4 / 1 | 10 / 2.5 | - |
| Cache RAM: empty loop / NOP / load / store | 4 / 1 / 1 / 1 | 4 / 1 / 1.5 / 1.5 | 1 |

MAME: `scripts/cps3_ttest.sh`, passes 1, 2, 3 and 5 identical; its screen read back gives the same values as its
RAM. jtcps3: 192.168.20.62, `scripts/mister_run.sh build/ttest/mame ttest "CPS3 timing test" 5 10`, shots of passes 2,
6, 11 and 15, all 63 rows read; the values above are pass 2's, the others within 8-80 clocks of them (the instruction
and memory rows identical).

Inferred:

- jtcps3's 2.6-3.0x slowdown against MAME (top of this file) is memory access, not the clock: the frame count is
  within 0.06% of MAME's and register-only instructions take the manual's clocks, while every load or store off the
  SH-2 costs 4.5-8.5 clocks and back-to-back 32-bit multiplies 6.4.
- jtcps3 character DMA takes about 2.2 CPU clocks a byte (64 KB: 142,600; 1 MB: 2,277,000, 91 ms, 5.4 frames), with
  a start cost under 1,000 clocks. The status bit comes up 120-576 clocks after the start write, then clears when IRQ
  10 arrives (within 100 clocks). Palette DMA: about 1.75 clocks a colour. The CPU's loads ran at their usual speed
  while a character DMA was running.
- The first `ttest` version polled the status bit from the start write and took "clear" as the end. On jtcps3 the bit
  is still clear for the first 120+ clocks, so it moved on at once and started the next DMA while the last still ran;
  that run's later DMAs never reported done (status bit 1 set past 1.3 s each). The current version waits for IRQ 10
  and saw no stuck bit in 15 passes. Not tested directly: starting a DMA while one runs.
- MAME's DMA times are its constants (below), so for DMA only jtcps3 and the board can be compared.

Observed in MAME's source (the copy in `../maldita.castilla-cps3/refs/cps3/mame/`):

- `cps3.cpp` keeps the character and palette DMA status bits set for 100 us (2,500 clocks; IRQ 10 at the same time)
  and the sprite-list bit for 4 us, "delay time is a hack" / "actual DMA speed is unknown".
- No wait states and no cache (docs above); no load-use stall either (2 clocks where the manual gives 3).
- The FRT: `sh7604.cpp` `sh2_timer_resync` sets the base to the current cycle and drops the clocks short of a full
  tick at every read, so a loop reading FRC every 9 clocks counted 8 / 9 of the time; and `frc_r` serves each byte
  read separately (no latch of the low byte), so a low byte that wraps between the two reads gives a value 256 ticks
  low (seen: one loop timing 12% low in one pass). `ttest` reads FRC once per 2,048 polls in its waits, and reads the
  high byte a second time, re-reading the low byte if it changed.

Bus settings the program runs with (`sdk/src/crt0.S`, the BIOS's values; SH7604 hardware manual 7.2): BCR2 0x00e8 = area 3
(SIMM, 0x06000000) 32-bit, areas 1 (main RAM, 0x02000000) and 2 (video and I/O, 0x04000000-0x05ffffff) 16-bit; WCR
0xaa57 = areas 1-3 one wait state with the external WAIT input on, area 0 (BIOS ROM) long wait, 2 idle cycles
between areas. FMR is written 2 (x4 clock multiplication, hardware manual 3.2.5). So on the board a 32-bit load from
main RAM or video memory is two 16-bit bus cycles of at least 3 clocks each (Inferred from the register values; not
measured; the clock ratio between the CPU and the bus is Unknown).

The board: not run yet. The code-location rows run last because the fetch through 0x26000000 and from cache RAM
depends on how the CPS3 decrypts those addresses; MAME decrypts by the address ANDed with 0xc7ffffff (SIMM) and by
0xc0000000 + offset (cache RAM).

## Inferred, not tested

Sound capacity: the sound chip addresses only SIMM 3's 16 MB (about 8.7 minutes of 8-bit PCM at 32 kHz), on the
hardware and on jtcps3. MAME plays all 64 MB of the `sfiii3na` layout (about 35 minutes); a program that relies on
that runs only in MAME.
