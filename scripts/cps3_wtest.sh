#!/bin/sh
# The wide 6-bit sprite probe in MAME (make wtest; src/wtest.c): a snapshot at frame 300, read by tools/wtest_check.py.
#   scripts/cps3_wtest.sh
set -e
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make wtest >/dev/null
O=build/wtest/run; rm -rf "$O"; mkdir -p "$O/w"
SNAP_AT=300 mame sfiii3na -rompath build/wtest/mame -nodrc -skip_gameinfo -nothrottle -sound none -video none \
  -seconds_to_run 60 -cfg_directory "$O/w/cfg" -nvram_directory "$O/w/nvram" -snapshot_directory "$O/snap" \
  -diff_directory "$O/w/diff" -state_directory "$O/w/sta" -inipath "$O/w" -autoboot_script scripts/lua/snap.lua 2>&1 |
  grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|sfiii3' || true
python3 tools/wtest_check.py "$O"/snap/sfiii3na/*.png
