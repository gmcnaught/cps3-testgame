# CPS3 test game

A small homebrew program for the Capcom CPS3 (SH-2): it draws a known scene with colour RAM, CPU-written
character RAM, two tilemaps and sprites, and steps through six phases. Each phase has an expected screen composed
on the host, so a MAME snapshot or a MiSTer `jtcps3` screenshot can be compared pixel for pixel.

Use it as:
- a starting point for porting a game to the CPS3 (boot code, linker script, encryption, set/MRA packaging and
  a minimal video library, `src/cps3v.c`), or
- a regression test for the `jtcps3` core (or any CPS3 emulator) against MAME.

## Status

| Check | Result |
|---|---|
| MAME 0.289, `scripts/cps3_vtest.sh` | 6 of 6 phases: 0 of 86,016 pixels differ |
| jtcps3 (`jtcps3.rbf` 2026-09-24 beta), `scripts/mister_run.sh` + `tools/vtest_check.py` | Phases 0-4 exact (after jtcps3's colour expansion and 1-px offset, applied by `vtest_check.py`). Phase 5: 6-bit colour sprites 4 tiles wide are drawn 2 tiles wide |

Details, and what is known about the CPS3 video hardware: [docs/CPS3.md](docs/CPS3.md).

## Phases (600 frames each, the last one stays)

| Phase | Shows |
|---|---|
| 0 | Tilemap 0 (colour swatches, flip markers, row/column markers) under tilemap 1 (sparse markers), sprites 1x1-4x4 tiles with flips, edges, overlap |
| 1 | As 0, tilemap 0 scrolled 440 px (past a 32-column wrap) |
| 2 | As 0, tilemap 0 scrolled to 1000,1000 (past the map edges) |
| 3, 4 | Every sprite size 1/2/4 x 1/2/4 tiles with each flip |
| 5 | Sprites in 6-bit colour mode, with and without word 3 bits 8-9 set |

## Requirements

- Docker, for the SH-2 toolchain: `docker build -t cps3-dev:latest docker` (binutils 2.42, GCC 13.3 for `sh-elf`;
  builds from source, takes a while).
- MAME (tested with 0.289) on the host, for `scripts/cps3_vtest.sh`.
- Python 3 with Pillow on the host.
- For the MiSTer: `jtcps3.rbf` installed, and `jtbeta.zip` (the jtcps3 beta key) in `/media/fat/games/mame/`;
  SSH access as root.

No Capcom ROM, BIOS or code is included or needed. The program runs as a stand-in for the Red Earth (Asia, NO CD)
set (`redearthn`) because MAME and jtcps3 need a known set layout and keys: `tools/mkcps3.py` writes every file of
that set itself (the program as the BIOS ROM's boot code and SIMM 1, the other SIMMs blank).

## Build and check in MAME

```sh
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make   # build/mame/redearthn/, build/expect_<phase>.png
scripts/cps3_vtest.sh                                     # builds, runs MAME, compares one snapshot per phase
mame redearthn -rompath build/mame                        # to watch it
```

## Check on a MiSTer (jtcps3)

```sh
MISTER=root@<mister-ip> scripts/mister_run.sh build/mame cps3test "CPS3 test game" 32 2
python3 tools/vtest_check.py build build/mister/shot_*.png
```

`mister_run.sh` writes the zip and MRA (`tools/mkmra3.py`), installs them (`/media/fat/games/mame/cps3test.zip`,
`/media/fat/_Arcade/_CPS3Test/`, set `MRA_DIR` to change), loads the core, takes N screenshots STEP seconds apart
and copies them back. `vtest_check.py` matches each shot to its best phase and writes a diff mask for shots that
differ. Single scattered pixels at colour edges come from the screenshot capture (other shots of the same phase are
exact): a phase passes when one of its shots matches.

## Layout

| Path | What |
|---|---|
| `src/crt0.S` | Vectors, the BIOS's bus/cache set-up (needed on jtcps3), `.data`/`.bss`, VBlank (IRL 12) handler |
| `src/link_simm.ld` | Boot code in the BIOS ROM, program in SIMM 1 (0x06000000), RAM at 0x02000000 |
| `src/link.ld` | Alternative: everything in the 512 KB BIOS ROM |
| `src/cps3v.c`, `cps3v.h` | Video helpers: CRTC/SS init, colours, tiles, tilemap cells and registers, display list (tilemap bands, sprites), VBlank DMA |
| `src/vtest.c` | The test game |
| `tools/vtest.py` | The scene (as `build/vtest_scene.h`) and the expected screens, composed without the CPS3 register formulas |
| `tools/mkcps3.py` | Encrypts the program into the `redearthn` stand-in set for MAME |
| `tools/mkmra3.py` | jtcps3 zip and MRA from that set |
| `tools/imgdiff.py`, `tools/vtest_check.py` | Screen comparison (MAME; jtcps3 with its colour and offset) |
| `scripts/cps3_vlog.sh`, `scripts/lua/cps3_vlog.lua`, `tools/cps3vlog.py`, `tools/cps3render.py` | Log a real CPS3 game's video writes in MAME, dump video memory, and re-render a frame from a dump (needs your own game set in `roms/`, or `ROMPATH`) |

## License

MIT, see [LICENSE](LICENSE).
