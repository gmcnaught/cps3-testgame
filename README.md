# CPS3 test game

Small homebrew programs for the Capcom CPS3 (SH-2) that exercise its video and sound with generated data, each with a
known answer composed on the host: a MAME snapshot (or WAV) and a MiSTer `jtcps3` screenshot can be compared exactly.

| Program | Tests |
|---|---|
| `vtest` | Colours, CPU-written tiles, two tilemaps, sprites of every size and flip, 6-bit colour |
| `vtest2` | What a game port uses: four tilemaps with parallax and vertical scroll, sprites between the layers in depth order, all 8 character RAM banks, colour codes up to 0x1ff, reloading tiles and colours while running, over 511 sprites (in two main-list records) |
| `stest` | The 16 PCM voices: one-shot, loops, pitch, pan, negative volume, restart, samples in every sample SIMM |

Use them as:
- a starting point for porting a game to the CPS3 (boot code, linker script, encryption, set/MRA packaging, small
  video and sound libraries: `src/cps3v.c`, `src/cps3s.c`), or
- regression tests for the `jtcps3` core (or any CPS3 emulator) against MAME.

## Status

| Program | MAME 0.289 | jtcps3 (`jtcps3.rbf` 2026-09-24 beta) |
|---|---|---|
| `vtest` | 6 of 6 phases: 0 pixels differ | Phases 0-4 exact (after jtcps3's colour expansion and 1-px offset, applied by `vtest_check.py`); phase 5: 6-bit colour sprites 4 tiles wide drawn 2 tiles wide |
| `vtest2` | 7 of 7 phases: 0 pixels differ | Phases 0-4 exact (four tilemaps, parallax, vertical scroll, all 8 character RAM banks, colour codes to 0x1ff, 120 sprites between the layers, four main-list records). Phase 5: with 511 + 96 entries in two main-list records, the second record is not drawn. Phase 6: tiles rewritten by the CPU while running are not shown (they read back correctly; rewritten colours do show) |
| `stest` | 250 register writes as scheduled; WAV equal to the chip model on every sample, both channels | Runs (scenes shown on the text layer); audio not captured yet |

Details, and what is known about the CPS3 video and sound hardware: [docs/CPS3.md](docs/CPS3.md).

## Requirements

- Docker, for the SH-2 toolchain: `docker build -t cps3-dev:latest docker` (binutils 2.42, GCC 13.3 for `sh-elf`,
  Python with Pillow and numpy; builds GCC from source, takes a while).
- MAME (tested with 0.289) on the host, and Python 3 with Pillow.
- For the MiSTer: `jtcps3.rbf` installed, and `jtbeta.zip` (the jtcps3 beta key) in `/media/fat/games/mame/`;
  SSH access as root.

No Capcom ROM, BIOS or code is included or needed. The programs run as a stand-in for the Street Fighter III 3rd
Strike (Asia, NO CD) set (`sfiii3na`, the CPS3 layout with the most flash) because MAME and jtcps3 need a known set
layout and keys: `tools/mkcps3.py` writes every file of that set itself (the program as the BIOS ROM's boot code and
SIMM 1, samples in SIMMs 3-6, the rest blank).

## Build and check in MAME

```sh
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make    # all three: build/<prog>/mame/sfiii3na/, ...
scripts/cps3_vtest.sh vtest                                # snapshot per phase against build/vtest/expect_<k>.png
scripts/cps3_vtest.sh vtest2
scripts/cps3_stest.sh                                      # writes and WAV against the schedule and the chip model
mame sfiii3na -rompath build/vtest2/mame                   # to watch one
```

## Check on a MiSTer (jtcps3)

```sh
MISTER=root@<mister-ip> scripts/mister_run.sh build/vtest2/mame vtest2 "CPS3 video test 2" 32 2
python3 tools/vtest_check.py build/vtest2 build/vtest2/mister/shot_*.png
```

`mister_run.sh` writes the zip and MRA (`tools/mkmra3.py`), installs them (`/media/fat/games/mame/<name>.zip`,
`/media/fat/_Arcade/_CPS3Test/`, set `MRA_DIR` to change), loads the core, takes N screenshots STEP seconds apart
and copies them back. `vtest_check.py` matches each shot to its best phase and writes a diff mask for shots that
differ. Single scattered pixels at colour edges come from the screenshot capture (other shots of the same phase are
exact, and the noise stays with the program frozen: `make vtest2 CDEFS=-DFREEZE_AT=<frame>` stops all video writes
from that frame): a phase passes when one of its shots matches. `stest` on jtcps3 is checked by ear for now (the text layer
names the scene playing); `build/stest/run/model.wav` is what MAME plays, for comparison with a capture.

## Layout

| Path | What |
|---|---|
| `src/crt0.S` | Vectors, the BIOS's bus/cache set-up (needed on jtcps3), `.data`/`.bss`, VBlank (IRL 12) handler |
| `src/link_simm.ld` | Boot code in the BIOS ROM, program in SIMM 1 (0x06000000), RAM at 0x02000000 |
| `src/link.ld` | Alternative: everything in the 512 KB BIOS ROM |
| `src/cps3v.c`, `cps3v.h` | Video helpers: CRTC/SS init, colours, tiles, tilemap cells and registers, display list (tilemap bands, sprites), VBlank DMA, text layer |
| `src/cps3s.c`, `cps3s.h` | Sound helpers: voice registers, volume, step, key on/off |
| `src/vtest.c`, `vtest2.c`, `stest.c` | The test programs |
| `tools/vtest.py`, `vtest2.py`, `stest.py` | Each program's data (as `build/<prog>/*.h`) and expected screens / register writes, composed without the CPS3 register formulas |
| `tools/mkcps3.py` | Encrypts a program (and samples) into the `sfiii3na` stand-in set for MAME |
| `tools/mkmra3.py` | jtcps3 zip and MRA from that set |
| `tools/imgdiff.py`, `tools/vtest_check.py`, `tools/stest_check.py` | Checks: screens (MAME; jtcps3 with its colour and offset), sound (writes and WAV) |
| `scripts/cps3_vtest.sh`, `scripts/cps3_stest.sh`, `scripts/mister_run.sh` | Run the checks in MAME, run a program on a MiSTer |
| `scripts/cps3_vlog.sh`, `scripts/lua/cps3_vlog.lua`, `tools/cps3vlog.py`, `tools/cps3render.py` | Log a real CPS3 game's video writes in MAME, dump video memory, and re-render a frame from a dump (needs your own game set in `roms/`, or `ROMPATH`) |

## License

MIT, see [LICENSE](LICENSE).
