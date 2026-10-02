# CPS3 test game

Four small homebrew programs for Capcom's CPS3 arcade board. Each one draws a known picture (or plays a known
sequence of sounds) built entirely from generated test data, and comes with the exact result it should produce. You
can run them in MAME or on a MiSTer with the `jtcps3` core and compare, pixel for pixel or sample for sample.

They are useful if you are:
- **porting a game to the CPS3**: the programs show, in small readable C, how to boot your own code, load
  graphics, build the display list and drive the sound chip. `src/cps3v.c` (video) and `src/cps3s.c` (sound) are
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

## Results so far

MAME 0.289 and `jtcps3.rbf` dated 2026-09-24 (beta), on 2026-10-01.

| Test | MAME | jtcps3 |
|---|---|---|
| `vtest` | All 6 phases exact | Phases 0-4 exact. Phase 5: 6-bit colour sprites 4 tiles wide are drawn only 2 tiles wide |
| `vtest2` | All 12 phases exact | Phases 0-4 and 8-10 correct. Phases 5-7: only the first 511 display-list entries of a frame are drawn, however they are grouped (the 7 layer entries count; 504 of the sprites show). Phase 11: the replaced tiles do not appear (the old ones stay on screen), although reading them back gives the new data; the replaced colours do appear |
| `vtest3` | All 5 phases exact | Phases 0-2 correct (records, positions, override, mirrored piece lists, 241 records). Phases 3-4: the last 7 tiles the program writes to character RAM (1,792 bytes) are not drawn as written: some draw nothing, one draws another tile's pixels. With `PAD_TILES=64` (64 more tiles written after them) both phases are exact. The port's wrong column was the same thing (its tile was 7th from the end of its upload). Phase 11 of `vtest2`, a short reload whose tiles never show, may be the same effect |
| `stest` | Exact: every register write and every audio sample | Runs and shows each scene; the audio has not been recorded or compared yet |

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
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make    # builds all four into build/<test>/
scripts/cps3_vtest.sh vtest                                # one snapshot per phase, compared with the expected screens
scripts/cps3_vtest.sh vtest2
scripts/cps3_vtest.sh vtest3
scripts/cps3_stest.sh                                      # register writes and audio, compared with the schedule and chip model
mame sfiii3na -rompath build/vtest2/mame                   # just to watch one
```

Each check prints how many pixels (or samples) differ and exits non-zero on any difference.

### On a MiSTer

```sh
MISTER=root@<mister-ip> scripts/mister_run.sh build/vtest2/mame vtest2 "CPS3 video test 2" 16 5
python3 tools/vtest_check.py build/vtest2 build/vtest2/mister/shot_*.png
```

`mister_run.sh` packages the test as a zip and MRA, copies them to the MiSTer (`/media/fat/games/mame/` and
`/media/fat/_Arcade/_CPS3Test/`; set `MRA_DIR` to change the folder), starts it, takes 16 screenshots 5 seconds apart
and copies them back. `vtest_check.py` says which phase each screenshot shows and how many pixels differ, and saves a
difference mask for each shot that is not exact. For `stest`, listen: the scene playing is named on screen, and
`build/stest/run/model.wav` (written by the MAME check) is what it should sound like.

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
| `src/vtest.c`, `vtest2.c`, `vtest3.c`, `stest.c` | The four test programs |
| `src/cps3v.c`, `cps3v.h` | Video library: screen set-up, colours, tiles, tilemaps, display list (layers, sprites, records pointing at prebuilt piece lists), text layer |
| `src/cps3s.c`, `cps3s.h` | Sound library: voice set-up, volume, pitch, key on/off |
| `src/crt0.S` | Start-up code: the bus and cache set-up the real BIOS does (jtcps3 needs it), VBlank interrupt |
| `src/link_simm.ld`, `link.ld` | Memory layout: program in SIMM 1 (as the games run), or all in the BIOS ROM |
| `tools/vtest.py`, `vtest2.py`, `vtest3.py`, `stest.py` | Generate each test's data, and the expected screens or register writes |
| `tools/mkcps3.py`, `mkmra3.py` | Build the MAME set, and the MiSTer zip and MRA |
| `tools/imgdiff.py`, `vtest_check.py`, `stest_check.py` | Compare results: MAME snapshots, jtcps3 screenshots, sound |
| `scripts/cps3_vtest.sh`, `cps3_stest.sh`, `mister_run.sh` | Run the checks in MAME; run a test on a MiSTer |
| `scripts/cps3_vlog.sh`, `scripts/lua/cps3_vlog.lua`, `tools/cps3vlog.py`, `tools/cps3render.py` | Research tools: log how a real CPS3 game drives the video hardware in MAME, and re-draw a frame from a memory dump (needs your own game set in `roms/`, or `ROMPATH`) |

## License

MIT, see [LICENSE](LICENSE).
