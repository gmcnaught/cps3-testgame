# CPS3 test game

Six small homebrew programs for Capcom's CPS3 arcade board. Each one draws a known picture (or plays a known
sequence of sounds) built entirely from generated test data, and comes with the exact result it should produce. You
can run them in MAME or on a MiSTer with the `jtcps3` core and compare, pixel for pixel or sample for sample.

They are useful if you are:
- **porting a game to the CPS3**: the programs show, in small readable C, how to boot your own code, load
  graphics (including by character DMA from the graphics flash, plain or run-length encoded), build the display list
  and drive the sound chip. `src/cps3v.c` (video) and `src/cps3s.c` (sound) are
  small libraries you can start from.
- **working on a CPS3 emulator or FPGA core**: each test isolates one hardware feature, so a difference points at a
  specific feature rather than at "the game looks wrong".

No Capcom ROM, BIOS or code is included or needed (see "How it runs without Capcom files" below).

## What the tests check

Each video test runs through **phases** of 10 seconds (600 frames). Every phase shows a still screen, and the tools
compute what that screen must look like, independently of the CPS3's register formulas.

### `vtest`: the basics

| Phase | What is on screen | What it checks |
|---|---|---|
| 0 | Two tilemap layers (colour swatches, flip markers, row/column numbers) and assorted sprites | Colours, tiles written by the CPU, tilemaps, transparency, sprite order and screen edges |
| 1 | The same, back layer scrolled 440 pixels | Horizontal scroll past column 32 |
| 2 | The same, back layer scrolled 1000 x 1000 | Scroll past the map's edges (wrap-around) |
| 3, 4 | Every sprite size (1, 2, 4 tiles wide x 1, 2, 4 tall), each with every flip | Sprite sizes, tile order, horizontal and vertical flip |
| 5 | Sprites in 6-bit colour mode | The 64-colour palette mode |

### `vtest2`: what a game port uses

| Phase | What is on screen | What it checks |
|---|---|---|
| 0 | Four tilemap layers at different scrolls (the front one only on the lower part of the screen) | Parallax, partial-screen layers, tiles from all 8 MB of character RAM, colour codes up to the top of colour RAM |
| 1 | The layers scrolled further; the front layer past the map's 1024-pixel wrap | Horizontal wrap |
| 2 | The layers scrolled vertically (500, 1000, 1010 and -30 pixels) | Vertical scroll and vertical wrap |
| 3 | 120 sprites placed between the layers (some behind layer 2, some between 2 and 3, some in front) | Sprites interleaved with background layers in depth order, sprites cut by every screen edge |
| 4 | The same picture as phase 3, with the display list split into four pieces | Several main-list records (display-list groups) in one frame |
| 5 | 600 overlapping sprites | A display list longer than one group can hold (511 entries) |
| 6 | The same 600 sprites, split into three groups of about 200 | Whether a per-frame limit on display-list entries exists, as opposed to a limit per group |
| 7 | 524 sprites in groups of 10, 511 (full) and 10 | Whether a group following a full one is lost, as opposed to a per-frame limit |
| 8 | A layer scrolling 6 pixels a frame through a level 4 times wider than the tilemap, then stopping | Streaming: the program writes each column of the level into the tilemap just before it scrolls into view, as a game does for a long room |
| 9 | The back layer switched to a different map in memory; layer 2 switched off | Pointing a layer at another map; turning a layer off |
| 10 | Large sprites made from tiles uploaded in one go across a 1 MB bank boundary; black bars at the top and bottom | Bulk tile upload across banks; sprites drawn in colours that are all black (a game's screen mask) |
| 11 | Phase 3's picture after the program replaces some tiles and colours while running | Reloading graphics between levels. The program also reads the tiles and colours back and prints any mismatch on screen |

### `vtest3`: objects as one display-list group each

A game port can write each animation frame's sprite pieces into sprite RAM once, at start-up (as drawn, and a
mirrored copy), then draw every object on screen with one main-list record that points at those pieces and gives the
object's position. The record can also replace the colour code of all its pieces (main-list word 2 bit 29, colour
code in bits 16-24), which is how a port draws an object flashing red or as a black silhouette. A grey check layer
covers the top half of the screen and the backdrop (dark blue) the bottom half, so a pixel left undrawn shows apart
from one drawn black.

| Phase | What is on screen | What it checks |
|---|---|---|
| 0 | 24 objects of 2-4 pieces, some mirrored, some red, some black, overlapping, partly off every edge | Records pointing at prebuilt piece lists (low and high in sprite RAM), record position (including negative x, which wraps in the 10-bit field), the colour-code override |
| 1 | The same picture, every piece its own entry in one group | The same objects drawn the usual way: the screen must equal phase 0's |
| 2 | 240 objects of two pieces | 241 main-list records in one frame (481 entries, under jtcps3's 511) |
| 3 | 20 cells, each a variation on one arrangement taken from a port (two overlapping objects, the first red and mirrored) | The port showed one wrong column on jtcps3; each cell changes one thing (override off, second object removed, single piece, unflipped, other x positions, drawn per piece, order swapped). The cells' tiles are the last ones the program uploads, which is what matters on jtcps3 (below) |
| 4 | The same cells, every object drawn per piece | Same screen as phase 3 |

`python3 tools/vtest3.py --cells <diff mask>...` names the phase 3 cells in which a jtcps3 screenshot differs.
`make vtest3 CDEFS=-DPAD_TILES=64` uploads 64 unused tiles after the scene's.

### `dtest`: character DMA

A CPS3 game does not write its tiles with the CPU while it runs: the video chip copies them from the graphics flash
(SIMMs 3-6) into character RAM by **character DMA**. The program writes a list into character RAM (at byte 0x1000, as
Red Earth does), each record a command, a length, a destination and a source; two register writes start it. This test
uses the uncompressed command (0). 288 tiles are on screen (a 24 x 10 tilemap and 48 one-tile sprites); each phase
shows them in another set of colours. After each DMA the program reads the tiles back and prints any difference.

| Phase | What happens | What it checks |
|---|---|---|
| 0 | Set A, written by the CPU at start | The starting picture |
| 1 | Set B copied over the tiles on screen, one list of two records | A DMA over tiles being drawn |
| 2 | Set C copied into tiles never used (0x4000 on), the screen switched to them | A DMA into fresh tiles |
| 3 | Set D copied over the tiles on screen, 16 tiles a frame for 18 frames | Streaming, one small DMA a frame |
| 4 | 1 MB in one record (4,096 tiles across the 1 MB bank boundary), set E shown from it | A level-sized load |

Build options for jtcps3 checks: `SHOW_FRAME` (frame number at the bottom right), `SKIP_DMA=<mask>` (no DMA in the
phases whose bit is set), `NO_VERIFY`, `NO_SWITCH` (the tilemap stays on its first map), `D2_BASE=<tile>`,
`SR_MASK=<sr>`.

### `dmap`: which tile is drawn where

Each tile carries its own 16-bit number as a 4 x 4 grid of blocks, in colours that say how it got into character RAM
(written by the CPU, copied plain from the flash, decoded from 6bpp or 8bpp run-length data in the flash), so `tools/dmap_check.py` can read
from a screenshot which tile the video draws in each of 312 tilemap cells, whatever went wrong. Steps of 5 seconds:
the CPU's tiles at start; an uncompressed DMA over them, a second one, one into fresh tiles; a CPU load and a DMA with
the display list empty for a second; two 6bpp run-length DMAs (command 2: 6-bit pixels, a byte 0x40 | n repeats the
last pixel) and two 8bpp ones (command 3: 8-bit pixels, a control byte per 8 items, items from a table of byte pairs,
a count after two equal bytes); command 4 sets the table. `DMAP_STEPS=<name,...>` picks the steps (`tools/dmap.py`), e.g. `cpu_on`: CPU writes
with the display on. In MAME: `scripts/cps3_dmap.sh`; on a MiSTer: `mister_run.sh build/dmap/mame dmap ...`, then
`python3 tools/dmap_check.py build/dmap build/dmap/mister/shot_*.png`.

### `stest`: sound

A 24-second sequence of seven scenes on the 16 sound voices. The scene playing is named on screen.

| Scene | What you hear | What it checks |
|---|---|---|
| A | A 440 Hz beep that ends by itself | A one-shot sample stopping at its end |
| B | A rising chirp, then a looping tone that moves to the left speaker and drops an octave | Loop points after an intro; changing volume and pitch while a sound plays |
| C | Noise on the left only, then the right only; a beep at negative volume; then silence | Left/right volume; signed volume (two voices at +volume and -volume cancel out exactly) |
| D | A buzz at 1x, 2x, 3x and 1/4x pitch | The pitch (step) register |
| E | Three tones | Samples stored in each part of the sample memory (SIMMs 4, 5 and 6) |
| F | A chord of 16 notes | All 16 voices at once |
| G | A blip retriggered 10 times; a beep that keeps playing when told to start again | Restarting a voice (key off, then on); "key on" for a voice that is already on does not restart it |

The MAME check compares every sound-register write the program makes against the schedule, then compares MAME's
recorded audio, sample by sample on both channels, against a model of the sound chip.

### `atest`: sound addressing

Which part of the sample memory the sound chip actually reads. Every 1 MB block of the 64 MB sample memory starts
with its own beep code: (block / 8) + 1 high beeps, a pause, then (block mod 8) + 1 low beeps. Forty tests of 5.5 s
play one block each (blocks 0-8, 12, 16, 17, 20, 24, 32, 33, 40, 44, 48, 63), first on voice 0, then on voice 1; the
screen shows the address and the code to expect. `make atest CDEFS=-DREG84=0x00230000u` also writes sound register
0x84 at start-up, as the games do. `tools/atest_decode.py <wav>` reads the codes back from a recording.

Result on jtcps3 (`.rbf` 2026-09-24, heard on a MiSTer): the low beeps always right, the high beeps only 1 or 2:
the chip reads offset mod 16 MB (SIMM 3 only), on both voices, with or without register 0x84. MAME reads all 64 MB.
The CPS3 hardware has the same 16 MB limit (validated outside this repo, 2026-10-03): jtcps3 is correct here and
MAME is more permissive than the board. Commercial games keep their samples low (3rd Strike: below 7.6 MB).

### `ftest`: loading sounds into the sample memory while running

Whether a program can rewrite part of SIMM 3 while it runs and have the sound chip play the new bytes: the way a
game whose music does not fit in the 16 MB the sound chip can address would keep its effects resident and copy each
stage's music into SIMM 3 from SIMMs 4-6. The program reads the flash chips' ID, sums two sources (SIMM 4 and SIMM
6) read through the flash window, erases one 128 KB sector of SIMM 3 and copies a source into it with flash program
commands (twice into the same slot, once into a slot in the second half of a chip pair), and finally copies one with
plain writes. Between the steps it plays the slots and the resident sample as `atest`'s beep codes; the screen lists
each step's result (frames taken, failed programs, halfwords that differ) and each play with the code expected if
the loads work and the code MAME plays. `make ftest CDEFS=-DNO_CEWE` leaves out the BIOS's chip and write enable
writes (0x07ff000c / 0x07ff0048). `tools/ftest_decode.py <wav>` reads the codes back from a recording.

MAME: ID 0404 / ADAD (Fujitsu 29F016A), both sums right, each erase 59 frames with every halfword 0xFFFF after,
each load 1-3 frames with no failures or differences, the slots play the loaded codes and the resident sample is
unchanged. Two results are MAME's model rather than hardware: an erased slot still plays its old code (MAME's sample
copy is refreshed only where the program writes), and the plain writes change some bytes (MAME's flash model takes
data bytes such as 0x10 / 0x40 / 0x90 as Intel commands).

### `btest`: sound bank probe

Whether any register moves the sound chip to SIMMs 4-6. On `atest`'s sample flash, each of 28 probes writes one
candidate register, plays the start of block 0 and writes the register back to 0: the flash bank register 0x040c0088
set to SIMM 4, 5 and 6, sound register 0x84 at 7 values, sound registers 0x81-0x83 and 0x85-0x87 at 2 values each,
and voice register 0 at 5 values. 1 high 1 low = no effect.

### `ttest`: timing

How long things take, counted with the SH-2's own free-running timer (8 CPU clocks a tick), for comparison
between MAME, jtcps3 and a real board. Results are shown on screen as each test finishes and the whole table runs
again every pass:

- CPU clocks a frame (does the CPU clock / frame rate ratio match?).
- Clocks per instruction: NOP, ADD, DIV1, MUL.L, DMULS.L, MULS.W, a load with and without its result used next,
  BRA, a taken and an untaken conditional branch. Each runs 32 times in a loop; the empty loop is subtracted.
- Clocks per 32-bit load or store in each memory area: main RAM (through the cache and not), BIOS ROM, SIMM 1,
  sprite RAM, colour RAM, character RAM, SS RAM, the video status register, the inputs.
- Character DMA (256 B to 1 MB) and palette DMA (256 and 8,192 colours): clocks until the status bit is first seen
  set, until it is seen clear again, and until the DMA-end interrupt (IRQ 10) arrives. Clocks until the sprite-list
  copy reports done, and for 4 KB through the SH-2's own DMA controller (burst, cycle steal, 16-byte units, from SIMM 1).
- Loads while a 1 MB character DMA runs (does the DMA slow the CPU?).
- Last, code fetched past the cache from SIMM 1 and run from the SH-2's cache RAM. These can stop a board that
  decrypts those fetches differently from MAME, so they come after everything else.

The SH7604 manual's figures (no wait states) are listed next to the instruction rows by `tools/ttest_check.py`.
Nothing here has been checked against a real board yet.

## Results so far

MAME 0.289 and `jtcps3.rbf` dated 2026-09-24 (beta), on 2026-10-01 (`dtest` and `dmap` on 2026-10-02).

| Test | MAME | jtcps3 |
|---|---|---|
| `vtest` | All 6 phases exact | Phases 0-4 exact. Phase 5: 6-bit colour sprites 4 tiles wide are drawn only 2 tiles wide |
| `vtest2` | All 12 phases exact | Phases 0-4 and 8-10 correct. Phases 5-7: only the first 511 display-list entries of a frame are drawn, however they are grouped (the 7 layer entries count; 504 of the sprites show). Phase 11: the replaced tiles do not appear (the old ones stay on screen), although reading them back gives the new data; the replaced colours do appear. To change tiles while the game runs, use character DMA (`dtest`, `dmap`): it works |
| `vtest3` | All 5 phases exact | Phases 0-2 correct (records, positions, override, mirrored piece lists, 241 records). Phases 3-4: the last 7 tiles the program writes to character RAM (1,792 bytes) are not drawn as written: some draw nothing, one draws another tile's pixels. With `PAD_TILES=64` (64 more tiles written after them) both phases are exact. The port's wrong column was the same thing (its tile was 7th from the end of its upload). Phase 11 of `vtest2`, a short reload whose tiles never show, may be the same effect |
| `dtest` | All 5 phases exact | All 5 phases exact: DMA over the tiles on screen, into fresh tiles, 16 tiles a frame, and 1 MB in one record across the bank boundary, all while the display runs. (A first version's colours repeated every 32 pens, so some phases' screens were identical and looked like failures) |
| `dmap` | All 10 steps as expected | All 10 steps as expected: uncompressed DMA twice over the tiles on screen and into fresh tiles, run-length DMA twice in 6bpp (command 2) and twice in 8bpp (command 3, pens 0x9a / 0xe5, table pairs), CPU writes and a DMA with the display list empty. With the display on, CPU writes are partly lost: in each 64-tile block the last 8 tiles keep their old pixels (`DMAP_STEPS=boot,cpu_on,over1`: 280 of 312 cells); the next DMA replaces them all |
| `stest` | Exact: every register write and every audio sample | Runs and shows each scene; the audio has not been recorded or compared yet |
| `atest` | Every register write and audio sample equal to MAME's model; 40 of 40 codes decoded. Plays blocks 16-63, which the hardware cannot address | Samples past 16 MB are read from 16 MB lower (by ear), as on the hardware; MAME's 64 MB is not |
| `ftest` | ID, sums, erases and loads all as expected; 10 of 10 codes decoded as MAME's model predicts | `.rbf` 2026-10-02 (.62, screen only): sources in SIMMs 4 and 6 read right through the flash window; erase, program and plain writes all ignored (each sector still the original data after 10 s; every DIFF equals the difference between the untouched slot and its source). ID: 0404 / ADAD on the first run, the slot's data on the second |
| `btest` | 28 of 28 probes play block 0 (MAME reads only the start register); writes and audio exact | 28 of 28 probes play block 0 (by ear, 2026-10-02): none of the candidate registers moves the samples to SIMMs 4-6 |
| `ttest` | Runs every test; MAME has no wait states, no load-use stall, and fixed DMA times (see docs/CPS3.md) | Runs every test, the same values in passes 2-15. Same clocks a frame as MAME; register instructions as the manual; loads and stores off the CPU 4.5-8.5 clocks (MAME 1); character DMA about 2.2 clocks a byte (1 MB: 2.28 M clocks), the status bit set 120-576 clocks after the start, clear and IRQ 10 together at the end |

"Correct" on jtcps3 allows for two known, consistent differences that `tools/vtest_check.py` corrects for: jtcps3
expands 5-bit colours to 8 bits as `v << 3 | v >> 2` (MAME uses `v << 3`), and its picture sits one pixel to the left
of MAME's.

jtcps3 screenshots also show a few scattered wrong pixels (usually under 20, up to about 100), in different places
in each shot. Nearly all of them repeat the pixel to their right, and they appear even when the program is frozen
and writes nothing, so they come from jtcps3's video output or the MiSTer scaler's sampling of it on some frames (not
yet known which), not from the test program. A phase therefore counts as passing on jtcps3 when at least one of its
screenshots matches exactly; in runs where the shift affects every shot, a phase also counts as correct when every
differing pixel is such a one-pixel shift.

More detail, and everything measured about the CPS3 video and sound hardware so far: [docs/CPS3.md](docs/CPS3.md).

## Running the tests

### What you need

- Docker, for the SH-2 compiler: `docker build -t cps3-dev:latest docker` (builds GCC from source; takes a while).
- MAME (tested with 0.289) and Python 3 with Pillow, on your computer.
- For the MiSTer: the `jtcps3` core installed, `jtbeta.zip` (the jtcps3 beta key) in `/media/fat/games/mame/`, and
  SSH access as root.

### In MAME

```sh
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make    # builds them all into build/<test>/
scripts/cps3_vtest.sh vtest                                # one snapshot per phase, compared with the expected screens
scripts/cps3_vtest.sh vtest2
scripts/cps3_vtest.sh vtest3
scripts/cps3_vtest.sh dtest
scripts/cps3_dmap.sh                                       # one snapshot per step, the tiles drawn read off the screen
scripts/cps3_stest.sh                                      # register writes and audio, compared with the schedule and chip model
scripts/cps3_ttest.sh                                      # timing table: MAME's values and its screen read back
mame sfiii3na -rompath build/vtest2/mame                   # just to watch one
```

Each check prints how many pixels (or samples) differ and exits non-zero on any difference.

`dmap` is checked by reading the screen instead: `scripts/cps3_dmap.sh` (one snapshot per step, read by
`tools/dmap_check.py`; `DMAP_STEPS=<name,...>` picks the steps, see `tools/dmap.py`).

### On a MiSTer

```sh
MISTER=root@<mister-ip> scripts/mister_run.sh build/vtest2/mame vtest2 "CPS3 video test 2" 16 5
python3 tools/vtest_check.py build/vtest2 build/vtest2/mister/shot_*.png
MISTER=root@<mister-ip> scripts/mister_run.sh build/dmap/mame dmap "CPS3 DMA map" 27 2
python3 tools/dmap_check.py build/dmap build/dmap/mister/shot_*.png
```

`mister_run.sh` packages the test as a zip and MRA, copies them to the MiSTer (`/media/fat/games/mame/` and
`/media/fat/_Arcade/_CPS3Test/`; set `MRA_DIR` to change the folder), starts it, takes 16 screenshots 5 seconds apart
and copies them back. `vtest_check.py` says which phase each screenshot shows and how many pixels differ, and saves a
difference mask for each shot that is not exact. For `stest`, listen: the scene playing is named on screen, and
`build/stest/run/model.wav` (written by the MAME check) is what it should sound like.

For `ttest` on jtcps3: `scripts/mister_run.sh build/ttest/mame ttest "CPS3 timing test" 3 10`, then
`python3 tools/ttest_check.py mame=build/ttest/run/mame.txt jtcps3=build/ttest/mister/shot_3.png` (the shot must show
PASS 1 or more).

### On a real board

`build/ttest/mame/sfiii3na/` holds the BIOS ROM file (the program's start-up code, encrypted with 3rd Strike Asia
NO CD's keys `a55432b4` / `0c129981`) and the SIMM 1 files (the program); the other SIMMs are blank. Run it on a
board set up for that game, wait until the title line shows PASS 2 or more, and photograph the screen. Type the
three columns into a text file one test a line, as shown (`LD MRAM    6.00`), and compare:
`python3 tools/ttest_check.py mame=build/ttest/run/mame.txt board=board.txt`. A test that never finishes shows
`NEVER`; if the board stops during the first pass, the first blank row is the test that stopped it.

To check whether some effect comes from the program's per-frame updates, build with
`make vtest2 CDEFS=-DFREEZE_AT=<frame>`: from that frame on the program stops writing to the video hardware.

## How it runs without Capcom files

MAME and jtcps3 only run CPS3 software laid out like a known game set, encrypted with that game's keys. These
programs use the layout and keys of Street Fighter III 3rd Strike (Asia, NO CD), `sfiii3na`, the CPS3 set with the most
memory. `tools/mkcps3.py` writes every file of that set itself: the boot code in the BIOS file, the program in
SIMM 1, the sound samples in SIMMs 3-6, the rest blank. Nothing from the real game is used.

## Files

| Path | What |
|---|---|
| `src/vtest.c`, `vtest2.c`, `vtest3.c`, `dtest.c`, `dmap.c`, `stest.c` | The six test programs |
| `src/ttest.c`, `ttest_k.S`, `tools/ttest.py`, `ttest_check.py`, `scripts/cps3_ttest.sh` | Timing test: program, timed loops, the test table, the comparison, the MAME run |
| `src/cps3v.c`, `cps3v.h` | Video library: screen set-up, colours, tiles, tilemaps, display list (layers, sprites, records pointing at prebuilt piece lists), text layer |
| `src/cps3s.c`, `cps3s.h` | Sound library: voice set-up, volume, pitch, key on/off |
| `src/crt0.S` | Start-up code: the bus and cache set-up the real BIOS does (jtcps3 needs it), VBlank interrupt |
| `src/link_simm.ld`, `link.ld` | Memory layout: program in SIMM 1 (as the games run), or all in the BIOS ROM |
| `tools/vtest.py`, `vtest2.py`, `vtest3.py`, `dtest.py`, `dmap.py`, `stest.py` | Generate each test's data, and the expected screens or register writes |
| `tools/mkcps3.py`, `mkmra3.py` | Build the MAME set, and the MiSTer zip and MRA |
| `tools/imgdiff.py`, `vtest_check.py`, `dmap_check.py`, `stest_check.py` | Compare results: MAME snapshots, jtcps3 screenshots, sound |
| `scripts/cps3_vtest.sh`, `cps3_dmap.sh`, `cps3_stest.sh`, `mister_run.sh` | Run the checks in MAME; run a test on a MiSTer |
| `scripts/cps3_vlog.sh`, `scripts/lua/cps3_vlog.lua`, `tools/cps3vlog.py`, `tools/cps3render.py` | Research tools: log how a real CPS3 game drives the video hardware in MAME, and re-draw a frame from a memory dump (needs your own game set in `roms/`, or `ROMPATH`) |

## License

MIT, see [LICENSE](LICENSE).
