# CPS3 SDK

A C library, start-up code and build files for writing your own programs for the Capcom CPS3 (SH-2), run in MAME
(`cps3` driver, as the `sfiii3na` set) and on the MiSTer's jtcps3 core. Everything here was measured on MAME 0.289
and jtcps3 (`.rbf` 2026-09-24 / 2026-10-02) by this repository's test programs; nothing has run on a real board yet.

Status: first iteration (2026-10-03). `examples/hello` runs in MAME (ball drawn from DMA'd tiles and colours, stick
and button 1 work, the beep plays, the EEPROM boot count goes 1, 2 over two runs) and on jtcps3 (`.rbf` 2026-10-02:
ball and colours right; palette DMA 504 clocks, 1 KB character DMA 2,496; inputs and EEPROM persistence not checked
there). The test programs (`src/`) build on the SDK and pass their MAME checks. maldita.castilla-cps3 still has its
own copies of these files and has not moved to the SDK.

## Layout

| Path | What |
|---|---|
| `sdk/include/cps3.h` | One include: everything below, `cps3_init`, `cps3_irq_mask` |
| `sdk/include/cps3v.h`, `sdk/src/cps3v.c` | Video: screen set-up, colours, tiles by CPU, tilemaps, display list (tilemap bands, sprites, prebuilt sublists), text layer |
| `sdk/include/cps3dma.h`, `sdk/src/cps3dma.c` | Character DMA (copy, 6- and 8-bit run-length) and palette DMA, from the graphics flash, waited for by IRQ 10 |
| `sdk/include/cps3s.h`, `sdk/src/cps3s.c` | Sound: the 16 PCM voices |
| `sdk/include/cps3io.h`, `sdk/src/cps3io.c` | Inputs (both players, 6 buttons, start, coin, service, test) and the EEPROM |
| `sdk/include/cps3t.h` | The CPU's free-running timer (8 CPU clocks a tick) |
| `sdk/src/crt0.S` | Vectors, the BIOS's bus and cache set-up, VBlank (IRQ 12) and DMA-end (IRQ 10) handlers |
| `sdk/link_simm.ld`, `sdk/link.ld` | Program in SIMM 1 (as the games run; the default) or all in the BIOS ROM |
| `sdk/sdk.mk` | Make fragment: compile, then build the MAME set (`tools/mkcps3.py`) and the MiSTer zip / MRA (`tools/mkmra3.py`) |
| `sdk/tools/cps3asset.py` | Writes the graphics / sample flash image: tiles, colours and samples in the byte orders the DMA and sound chip read |
| `examples/hello/` | A ball moved by the stick, a beep on button 1, inputs, an EEPROM boot counter, the DMA times |

## Building a program

You need Docker (the SH-2 compiler: `docker build -t cps3-dev:latest docker`), MAME, and Python 3 with Pillow.

A program's Makefile names the program, its sources and, optionally, its flash image, then includes `sdk/sdk.mk`
(`examples/hello/Makefile`):

```make
PROG  := hello
TITLE := CPS3 SDK hello
SRCS  := main.c
FLASH := build/flash.bin                 # optional: graphics and samples (sdk/tools/cps3asset.py)
include ../../sdk/sdk.mk

$(FLASH) build/assets.h: assets.py
	python3 assets.py $(FLASH) build/assets.h
build/main.elf: build/assets.h
```

```sh
docker run --rm -v "$PWD":/p -w /p/examples/hello cps3-dev:latest make     # from the repository root
mame sfiii3na -rompath examples/hello/build/mame
MISTER=root@<mister-ip> scripts/mister_run.sh examples/hello/build/mame hello "CPS3 SDK hello" 3 5
```

The set is a stand-in for Street Fighter III 3rd Strike (Asia, NO CD): your program in the BIOS ROM file (start-up
code) and SIMM 1 (the rest), encrypted with that game's keys; your flash image in SIMMs 3-6; nothing from the real
game. See the README, "How it runs without Capcom files".

## A program

```c
#include "cps3.h"

int main(void)
{
    cps3_init();                                   /* screen, text layer, sound off, VBlank on */
    cps3dma_palette(COLOURS_AT, 256, 16, 0);       /* 16 colours from the flash to colour code 1 */
    cps3dma_char_copy(TILES_AT, 0x100, 4);         /* 4 tiles from the flash to tiles 0x100-0x103 */
    cps3dma_char_run();
    cps3v_text(2, 1, "HELLO");
    for (;;) {
        cps3v_wait_vblank();
        cps3v_vblank();                            /* sends the list built last frame */
        cps3v_begin();
        cps3v_sprite(176, 96, 2, 2, 0x100, 1, 0);  /* 32x32 sprite of tiles 0x100-0x103, colour code 1 */
        cps3v_end();
    }
}
```

Each frame: wait for VBlank, send the last list (`cps3v_vblank`), set tilemap registers if they change
(`cps3v_tilemap`), then build the next list. Register writes all fall in the first lines of the frame, as Red Earth
makes them.

## What the SDK reserves

| Resource | Use |
|---|---|
| Main RAM 0x02000000-0x0207ffff (512 KB) | `.trace` (first, for MAME scripts), `.data`, `.bss`; the stack from the top down |
| Sprite RAM | Main list 0x0000-0x1fff (510 records a frame); the frame's sublists 0x2000-0x9fff (two 16 KB areas used in turn: 1,024 entries a frame); prebuilt sublists `CPS3V_PRE_A` (0xa000-0x3ffff) and `CPS3V_PRE_B` (0x54000-0x7ffff); tilemaps in 4 KB units from 0x40000 (unit 0x40) |
| Character RAM | Bytes 0x1000-0x1fff (tiles 16-31): the character DMA list (341 records) |
| Colour RAM | Entries 0x1fe00-0x1fe0f: the text layer (colour 1 white) |
| Interrupts | IRQ 12 (VBlank) counts `vbl_count`; IRQ 10 (DMA end) is taken only inside the DMA waits |
| EEPROM | None. The MiSTer MRA fills words 0-23 with 3rd Strike's defaults; `examples/hello` uses words 30-31 |

## Rules from the measurements

Each is measured by a test in this repository (README "Results so far", `docs/CPS3.md`):

- **Load tiles by character DMA, not by CPU writes**, while the display runs: jtcps3 loses CPU writes to character
  RAM with the display on (the last 8 tiles of each 64-tile block, `dmap`), and the last 7 tiles a program writes
  can draw wrong until more are written after them (`vtest3`). DMA tiles are always right (`dtest`, `dmap`).
- **Wait for a DMA by IRQ 10, not by the busy bit**: on jtcps3 the bit comes up 120-576 CPU clocks after the start
  write (`ttest`). `cps3dma_char_run` and `cps3dma_palette` do this. Character DMA takes about 2.2 CPU clocks a byte
  on jtcps3 (1 MB: 91 ms, 5.4 frames); MAME takes a fixed 100 us whatever the size.
- **jtcps3 draws at most 511 display-list entries a frame**, however they are grouped (`vtest2`); MAME draws more.
- **6-bit colour sprites wider than 2 tiles** are drawn only 2 tiles wide on jtcps3 (`vtest`). Use 8-bit colour.
- **Sprites up to 4x4 tiles** (64x64) without zoom: size 8 is not usable (x size 0 is the tilemap command, y size 0
  draws nothing).
- **Colours**: BGR555; jtcps3 expands 5 bits to 8 as `v << 3 | v >> 2`, MAME as `v << 3`. Colour 0 of the screen is
  the backdrop.
- **Read status and inputs through the cache-through mirror** (0x2xxxxxxx); the SDK does. Write the text layer (SS
  RAM) and colour RAM as 32-bit words: jtcps3 shows nothing for byte writes to SS RAM.
- **Memory is slow on jtcps3**: register-only instructions take the SH7604 manual's clocks, but every load or store
  off the CPU takes 4.5-8.5 clocks (MAME: 1) and back-to-back 32-bit multiplies 6.4 (MAME: 2). jtcps3 runs CPU-bound
  code 2.6-3x slower than MAME: budget against jtcps3 (`ttest`, `docs/CPS3.md` "Timing").
- **Sound reaches 16 MB only** (SIMM 3): the hardware and jtcps3 read sample offsets mod 16 MB; MAME plays all 64 MB
  (`atest`). `cps3asset.Flash.sample` refuses data past 16 MB.
- **The flash cannot be rewritten at run time on jtcps3** (erase and program commands are ignored, `ftest`).
- **Code runs from SIMM 1 or cache RAM**: MAME fetches opcodes only from the BIOS ROM, SIMMs 1-2 and cache RAM, not
  main RAM; it maps 1 KB of cache RAM (the chip has 2 KB in two-way mode), and opcodes there are decrypted by address
  (`ttest`'s cache-RAM rows encrypt the copied code).

## API

### `cps3.h`

| Call | What |
|---|---|
| `cps3_init()` | `cps3v_init`, `cps3v_text_init`, `cps3s_init`, interrupt mask 10 (VBlank taken) |
| `cps3_irq_mask(level)` | SR interrupt mask: levels above it are taken |

### Video (`cps3v.h`)

| Call | What |
|---|---|
| `cps3v_init()` | CRTC for 384x224 (Red Earth's values), SS layer cleared, colour RAM cleared, tilemaps off, empty list; output port with coins accepted |
| `cps3v_colours(first, bgr, n)` | Colours by CPU (first and n even) |
| `cps3v_tiles(first, px, n)` | 16x16 8-bit tiles by CPU (see the rules: prefer DMA) |
| `cps3v_cell(unit, col, row, tile, pal, flags)` | One cell of a 64x64 tilemap in sprite RAM unit `unit` |
| `cps3v_tilemap(tm, map_x, map_y, unit, enable)` | Tilemap 0-3: the map pixel shown at the screen's top-left |
| `cps3v_begin()` / `cps3v_end()` | Start / close the frame's display list |
| `cps3v_band(tm, top, lines)` | Tilemap `tm` on screen lines `top`.. (drawn in list order) |
| `cps3v_sprite(x, y, w, h, tile, pal, flags)` | A sprite of w x h tiles (1, 2, 4), tiles column by column from `tile` |
| `cps3v_group()` | Later entries in a new main-list record |
| `cps3v_put(addr, ...)`, `cps3v_object(addr, n, x, y, pal)` | Prebuilt sublists: written once, drawn by one record at an offset, optionally recoloured |
| `cps3v_vblank()` | At VBlank: global scrolls, the sprite-list copy of the last finished list |
| `cps3v_text_init()`, `cps3v_text(col, row, s)` | Text layer: 48x28 cells, ASCII 32-95 |
| `cps3v_wait_vblank()`, `vbl_count` | Frame sync |

Flags: `CPS3V_FLIPX`, `CPS3V_FLIPY`, `CPS3V_BPP6` (6-bit colour: colour code x 64). Colour code `pal` selects 256
colours (8-bit) from entry `pal * 256`.

### Video DMA (`cps3dma.h`)

| Call | What |
|---|---|
| `cps3dma_char_copy(src, first, n)` | Queue n tiles from flash byte `src` to tile `first` |
| `cps3dma_char_record(cmd, src, dest_byte, bytes)` | Queue any record: `CPS3DMA_COPY`, `CPS3DMA_TABLE` (pair table for the decoders), `CPS3DMA_RLE6`, `CPS3DMA_RLE8` (encoders: `tools/dmap.py`) |
| `cps3dma_char_run()` | Run the queue; returns CPU clocks taken, 0 if no end within ~1.3 s |
| `cps3dma_palette(src, first, n, fade)` | n colours from flash byte `src` to colour entry `first`; returns CPU clocks |

### Sound (`cps3s.h`)

| Call | What |
|---|---|
| `cps3s_voice(v, start, end, loop, looped, step, vol_l, vol_r)` | Voice 0-15: chip addresses (`CPS3S_BASE` + flash offset), loop, step (4096 = one sample per output sample at 37,286 Hz), volumes (signed; 0x4000 is moderate) |
| `cps3s_volume`, `cps3s_step` | Change while playing |
| `cps3s_keys(bits)` | Key bits: a voice going off -> on restarts at its start |

### Inputs and EEPROM (`cps3io.h`)

| Call | What |
|---|---|
| `cps3_pad(player)` | `CPS3_UP` .. `CPS3_RIGHT`, `CPS3_B1` .. `CPS3_B6`, `CPS3_START`, `CPS3_COIN`; set = pressed |
| `cps3_system()` | `CPS3_SERVICE`, `CPS3_TEST` |
| `cps3_ee_read(k)`, `cps3_ee_write(k, v)` | EEPROM word 0-31 (32 bits). MAME keeps it in its nvram directory, jtcps3 in the MiSTer's `.nvm` (not seen saved from the OSD: `docs/CPS3.md`) |

Inputs follow MAME's port map (buttons 4-6 in a second register); checked in MAME by `examples/hello`, not yet on
jtcps3 or a board.

### Timer (`cps3t.h`)

`cps3t_ticks()` reads the timer (8 CPU clocks a tick, wraps every 21 ms); `cps3t_clocks_since(t0)` gives CPU clocks
since a reading, for intervals under 524,288 clocks.

### Flash image (`sdk/tools/cps3asset.py`)

`Flash().tiles(at, pixels)`, `.colours(at, words)`, `.sample(at, values)`, `.write(path)`. Byte orders measured in
MAME: the sound chip reads byte a; the character DMA and the palette DMA read the byte pairs swapped (a ^ 1), so
`tiles` and `colours` store them so.

## Not in the SDK yet

- A real-board run of anything.
- Graphics conversion from images (palette reduction, tiling), a tilemap / level format, run-length encoding as a
  library call (the encoder is in `tools/dmap.py`), sample conversion from WAV.
- Sprite zoom, line scroll, the full-screen zoom registers, fades by palette DMA (the fade format is MAME's guess).
- Timer and profiling interrupts (maldita.castilla-cps3 has an FRT output-compare profiler and a trap hook in its
  own `crt0.S`).
