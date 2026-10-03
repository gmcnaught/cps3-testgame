#!/usr/bin/env python3
"""CPS3 SDK asset helper: the graphics / sample flash image (SIMMs 3-6, 64 MB at most) that tools/mkcps3.py writes
to the set (its user5.bin argument; sdk/sdk.mk's FLASH). Offsets count from the start of the flash, as the SDK's DMA
calls (cps3dma.h) and sound calls (cps3s.h: chip address = offset + CPS3S_BASE) take them.

    flash = Flash()
    flash.tiles(0x10000, pixels)        # 16x16 8-bit tiles, 256 bytes each, for cps3dma_char_copy(0x10000, ...)
    flash.colours(0x20000, [0x7fff])    # BGR555 words for cps3dma_palette(0x20000, ...)
    flash.sample(0x30000, s8_values)    # signed 8-bit PCM for cps3s_voice(..., CPS3S_BASE + 0x30000, ...)
    flash.write('build/flash.bin')

Byte orders, measured in MAME 0.289 (src/dtest.c, src/stest.c, examples/hello): the sound chip reads byte a of the
image; the character DMA reads byte a as byte a ^ 1 (tiles are stored with each byte pair swapped); the palette DMA
reads colour i of a source as image bytes 2i + 1 (bits 8-15) and 2i (bits 0-7), the same pair swap (colours are
stored little-endian).
"""
import struct

FLASH_MAX = 64 << 20
SAMPLE_MAX = 16 << 20       # the sound chip addresses SIMM 3 only (hardware and jtcps3; MAME reaches all 64 MB)


class Flash:
    def __init__(self):
        self.img = bytearray()

    def _put(self, at, data):
        end = at + len(data)
        if end > FLASH_MAX:
            raise ValueError(f'flash: {end:#x} past 64 MB')
        if len(self.img) < end:
            self.img += bytes(end - len(self.img))
        self.img[at:end] = data

    def tiles(self, at, pixels):
        """8-bit pixels, 256 per 16x16 tile, row by row; at even"""
        if at & 1 or len(pixels) % 256:
            raise ValueError('tiles: even offset, whole tiles')
        d = bytes(pixels)
        self._put(at, bytes(d[i ^ 1] for i in range(len(d))))

    def colours(self, at, words):
        """BGR555 colours (bit 15 kept as given); at a multiple of 4"""
        if at & 3:
            raise ValueError('colours: offset a multiple of 4')
        self._put(at, palette_bytes(words))

    def sample(self, at, values):
        """signed 8-bit PCM (-128..127)"""
        if at + len(values) > SAMPLE_MAX:
            raise ValueError('sample: past the 16 MB the sound chip addresses')
        self._put(at, bytes(v & 0xff for v in values))

    def write(self, path):
        open(path, 'wb').write(bytes(self.img))


def palette_bytes(words):
    w = list(words) + [0] * (-len(words) % 2)
    return b''.join(struct.pack('<H', w[i]) for i in range(len(w)))
