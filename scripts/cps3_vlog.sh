#!/bin/sh
# Log a real CPS3 game's video set-up in MAME (scripts/lua/cps3_vlog.lua; PLAN.md C0).
#   scripts/cps3_vlog.sh <out_dir> [mame args...]
# Set: redearthn from $ROMPATH (your own set; default roms/). VLOG_DUMP, VLOG_END, VLOG_INPUT,
# VLOG_FROM as in the Lua script. -nodrc: the DRC bypasses Lua write taps.
set -e
cd "$(dirname "$0")/.."
O=$1; shift
mkdir -p "$O/w"
VLOG_OUT="$O" mame redearthn -rompath "${ROMPATH:-roms}" -nodrc -skip_gameinfo -nothrottle -sound none -video none \
  -cfg_directory "$O/w/cfg" -nvram_directory "$O/w/nvram" -snapshot_directory "$O/snap" -diff_directory "$O/w/diff" \
  -state_directory "$O/w/sta" -inipath "$O/w" -autoboot_script scripts/lua/cps3_vlog.lua "$@" 2>&1 |
  grep -v -E '^$' || true
