# CPS3 test programs, each run from SIMM 1 as the games are:
#   vtest   video: colours, tiles, two tilemaps, sprites of every size and flip (src/vtest.c, tools/vtest.py)
#   vtest2  video as a port uses it: four tilemaps (parallax), vertical scroll, character RAM banks and reloads,
#           over 511 sprites, high colour codes (src/vtest2.c, tools/vtest2.py)
#   vtest3  objects as one main-list record each: prebuilt sublists, record position, colour code override
#           (src/vtest3.c, tools/vtest3.py)
#   dtest   character DMA: tiles copied from SIMM 3 into character RAM while the display runs (src/dtest.c,
#           tools/dtest.py)
#   dmap    character RAM loads read off the screen: labelled tiles by CPU, uncompressed and compressed DMA, display
#           on and off (src/dmap.c, tools/dmap.py; check: scripts/cps3_dmap.sh, tools/dmap_check.py)
#   stest   sound: the 16 PCM voices (src/stest.c, tools/stest.py)
#   atest   sound addressing: a beep code per 1 MB block of the sample flash, played block by block (src/atest.c,
#           tools/atest.py)
#   ftest   flash sound load: part of SIMM 3 erased and reprogrammed from SIMMs 4 and 6 while running, then played
#           (src/ftest.c, tools/ftest.py; tools/ftest_decode.py reads the codes from a recording)
#   btest   sound bank probe: candidate registers written, then the start of the sample flash played: does any move
#           the chip to SIMMs 4-6? (src/btest.c, tools/btest.py; tools/ftest_decode.py <wav> build/btest/btest_plays.txt)
# The library they share is the SDK (sdk/, docs/SDK.md); examples/ builds programs with sdk/sdk.mk.
# Build in the cps3-dev container (docker/Dockerfile):
#   docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make [vtest|vtest2|vtest3|dtest|stest]
# CDEFS=-DFREEZE_AT=<frame> (vtest, vtest2, vtest3, dtest): from that frame the program writes nothing more to the video hardware
# (a still screen without per-frame list rebuilds, register writes or DMA), to tell screenshot-capture noise from
# effects of the per-frame writes.
# Output per program P: build/P/mame/sfiii3na/ (a MAME stand-in set) and what tools/P.py writes (expected screens,
# samples). scripts/cps3_vtest.sh P and scripts/cps3_stest.sh check them in MAME; scripts/mister_run.sh on jtcps3.
PROGS  := vtest vtest2 vtest3 dtest dmap stest atest ftest btest ttest wtest
SDK_SRCS := $(addprefix sdk/src/,crt0.S cps3.c cps3v.c cps3dma.c cps3s.c cps3io.c)
CFLAGS := -m2 -mb -O2 -ffreestanding -fno-builtin -nostdlib -fomit-frame-pointer -Wall -Wextra

all: $(PROGS)

$(PROGS):
	@mkdir -p build/$@
	python3 tools/$@.py build/$@
	sh-elf-gcc $(CFLAGS) $(CDEFS) -Ibuild/$@ -Isrc -Isdk/include -nostartfiles -T sdk/link_simm.ld \
	  -Wl,-Map,build/$@/main.map -o build/$@/main.elf src/$@.c $(wildcard src/$@_k.S) $(SDK_SRCS) -lgcc
	sh-elf-objcopy -O binary -j .boot build/$@/main.elf build/$@/main.bin
	sh-elf-objcopy -O binary -j .text -j .data build/$@/main.elf build/$@/simm1.bin
	python3 tools/mkcps3.py build/$@/main.bin build/$@/mame build/$@/simm1.bin \
	  $$(test -f build/$@/$@.bin && echo build/$@/$@.bin)

clean:
	rm -rf build

.PHONY: all clean $(PROGS)
