#!/bin/sh
# src/dmap.c in MAME: a snapshot in the middle of each step, read by tools/dmap_check.py.
#   scripts/cps3_dmap.sh            (DMAP_STEPS=<name,...> picks the steps, tools/dmap.py)
set -e
cd "$(dirname "$0")/.."
docker run --rm -e DMAP_STEPS -v "$PWD":/p -w /p cps3-dev:latest make dmap >/dev/null
B=build/dmap; O=$B/run; rm -rf "$O"; mkdir -p "$O/w"
n=$(wc -l < "$B/steps.txt" | tr -d ' ')
D=$(seq 0 $((n - 1)) | while read k; do printf '%d,' $((300 * k + 150)); done)
VLOG_OUT="$O" VLOG_DUMP="$D" VLOG_END=$((300 * n + 10)) VLOG_FROM=999999 mame sfiii3na -rompath "$B/mame" -nodrc \
  -skip_gameinfo -nothrottle -sound none -video none -seconds_to_run 200 -cfg_directory "$O/w/cfg" \
  -nvram_directory "$O/w/nvram" -snapshot_directory "$O/snap" -diff_directory "$O/w/diff" -state_directory "$O/w/sta" \
  -inipath "$O/w" -autoboot_script scripts/lua/cps3_vlog.lua 2>&1 | grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|sfiii3' || true
python3 tools/dmap_check.py "$B" "$O"/snap/sfiii3na/*.png
