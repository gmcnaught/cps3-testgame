#!/bin/sh
# The CPS3 timing test in MAME (make ttest; src/ttest.c): the results of the second pass (scripts/lua/ttest_dump.lua)
# to build/ttest/run/mame.txt and a snapshot of the screen, then the table (tools/ttest_check.py).
#   scripts/cps3_ttest.sh
set -e
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make ttest >/dev/null
O=build/ttest/run; rm -rf "$O"; mkdir -p "$O/w"
TTEST_OUT="$O/mame.txt" TTEST_PASSES=2 mame sfiii3na -rompath build/ttest/mame -nodrc -skip_gameinfo -nothrottle \
  -sound none -video none -seconds_to_run 120 -cfg_directory "$O/w/cfg" -nvram_directory "$O/w/nvram" \
  -snapshot_directory "$O/snap" -diff_directory "$O/w/diff" -state_directory "$O/w/sta" -inipath "$O/w" \
  -autoboot_script scripts/lua/ttest_dump.lua 2>&1 | grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|sfiii3' || true
test -s "$O/mame.txt" || { echo "no results (MAME stopped before 2 passes)"; exit 1; }
python3 tools/ttest_check.py mame="$O/mame.txt" mame_screen="$(ls "$O"/snap/sfiii3na/*.png | head -1)"
