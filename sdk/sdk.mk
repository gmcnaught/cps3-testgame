# CPS3 SDK make fragment (docs/SDK.md). A program's Makefile sets
#   PROG   name (the MiSTer zip / MRA name)
#   SRCS   its C and assembly files
#   FLASH  optional: the graphics / sample flash image (SIMMs 3-6, 64 MB at most) and the rule that makes it
#   TITLE  optional: the MRA's title
# then includes this file. Targets: all (build/mame/sfiii3na/, a MAME set), mister (build/mister/: zip and MRA, needs
# the jtcps3 beta key as tools/mkmra3.py says), clean. Build in the cps3-dev container (docker/Dockerfile):
#   docker run --rm -v <repo>:/p -w /p/<program dir> cps3-dev:latest make
CPS3_SDK  := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
CPS3_ROOT := $(CPS3_SDK)/..
OUT       ?= build
TITLE     ?= $(PROG)
CPS3_CFLAGS := -m2 -mb -O2 -ffreestanding -fno-builtin -nostdlib -fomit-frame-pointer -Wall -Wextra
CPS3_SDK_SRCS := $(addprefix $(CPS3_SDK)/src/,crt0.S cps3.c cps3v.c cps3dma.c cps3s.c cps3io.c)

all: $(OUT)/mame/sfiii3na

$(OUT)/main.elf: $(SRCS) $(CPS3_SDK_SRCS) $(wildcard $(CPS3_SDK)/include/*.h) $(CPS3_SDK)/link_simm.ld
	@mkdir -p $(OUT)
	sh-elf-gcc $(CPS3_CFLAGS) $(CFLAGS) -I$(CPS3_SDK)/include -I$(OUT) -nostartfiles -T $(CPS3_SDK)/link_simm.ld \
	  -Wl,-Map,$(OUT)/main.map -o $@ $(CPS3_SDK_SRCS) $(SRCS) -lgcc

$(OUT)/mame/sfiii3na: $(OUT)/main.elf $(FLASH)
	sh-elf-objcopy -O binary -j .boot $< $(OUT)/main.bin
	sh-elf-objcopy -O binary -j .text -j .data $< $(OUT)/simm1.bin
	python3 $(CPS3_ROOT)/tools/mkcps3.py $(OUT)/main.bin $(OUT)/mame $(OUT)/simm1.bin $(FLASH)

mister: $(OUT)/mame/sfiii3na
	python3 $(CPS3_ROOT)/tools/mkmra3.py $(OUT)/mame $(OUT)/mister $(PROG) "$(TITLE)"

clean:
	rm -rf $(OUT)

.PHONY: all mister clean $(OUT)/mame/sfiii3na
