#!/bin/sh
# The CPS3 sound test in MAME (make stest; src/stest.c): MAME's mix at the chip's rate (-wavwrite, 37,286 Hz) and
# every sound-register write (scripts/lua/stest_log.lua), checked by tools/stest_check.py against the schedule and
# against the chip computed from the writes. Output in build/stest/run/ (mame.wav, model.wav, writes.log).
set -e
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make stest >/dev/null
O=build/stest/run; rm -rf "$O"; mkdir -p "$O/w"
END=$(sed -n 's/^#define ST_END_FRAME //p' build/stest/stest.h)
STEST_LOG="$O/writes.log" STEST_END=$END mame sfiii3na -rompath build/stest/mame -nodrc -skip_gameinfo -nothrottle \
  -sound none -samplerate 37286 -wavwrite "$O/mame.wav" -video none -seconds_to_run 100 -cfg_directory "$O/w/cfg" \
  -nvram_directory "$O/w/nvram" -snapshot_directory "$O/w/snap" -diff_directory "$O/w/diff" \
  -state_directory "$O/w/sta" -inipath "$O/w" -autoboot_script scripts/lua/stest_log.lua 2>&1 |
  grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|sfiii3' || true
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest python3 tools/stest_check.py build/stest "$O/writes.log" \
  "$O/mame.wav" "$O/model.wav"
