# CPS3 SDK example (docs/SDK.md). From the repository root:
#   docker run --rm -v "$PWD":/p -w /p/examples/hello cps3-dev:latest make
#   mame sfiii3na -rompath examples/hello/build/mame
PROG  := hello
TITLE := CPS3 SDK hello
SRCS  := main.c
FLASH := build/flash.bin
include ../../sdk/sdk.mk

$(FLASH) build/assets.h: assets.py ../../sdk/tools/cps3asset.py
	@mkdir -p build
	python3 assets.py $(FLASH) build/assets.h

build/main.elf: build/assets.h
