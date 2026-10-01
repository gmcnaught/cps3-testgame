# CPS3 test game (src/vtest.c, src/cps3v.c; scene and expected screens from tools/vtest.py), run from SIMM 1 as
# the games are. Builds in the cps3-dev container (docker/Dockerfile):
#   docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make
# Output: $(B)/mame/redearthn/ (a MAME stand-in set), $(B)/expect_<phase>.png (the screens it should show).
# scripts/cps3_vtest.sh checks it in MAME, scripts/mister_run.sh + tools/vtest_check.py on jtcps3.
B ?= build
CFLAGS := -m2 -mb -O2 -ffreestanding -fno-builtin -nostdlib -fomit-frame-pointer -Wall -Wextra

all:
	@mkdir -p $(B)
	python3 tools/vtest.py $(B)
	sh-elf-gcc $(CFLAGS) -I$(B) -Isrc -nostartfiles -T src/link_simm.ld -Wl,-Map,$(B)/main.map -o $(B)/main.elf \
	  src/crt0.S src/vtest.c src/cps3v.c -lgcc
	sh-elf-objcopy -O binary -j .boot $(B)/main.elf $(B)/main.bin
	sh-elf-objcopy -O binary -j .text -j .data $(B)/main.elf $(B)/simm1.bin
	python3 tools/mkcps3.py $(B)/main.bin $(B)/mame $(B)/simm1.bin

clean:
	rm -rf $(B)

.PHONY: all clean
