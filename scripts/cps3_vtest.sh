#!/bin/sh
# The CPS3 video test in MAME (make; src/vtest.c): a snapshot in the middle of each phase, compared
# with tools/vtest.py's expected screens. Dumps for tools/cps3render.py go to build/run/.
set -e
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make >/dev/null
O=build/run; rm -rf "$O"; mkdir -p "$O/w"
VLOG_OUT="$O" VLOG_DUMP=300,900,1500,2100,2700,3300 VLOG_END=3310 VLOG_FROM=0 mame redearthn -rompath build/mame -nodrc \
  -skip_gameinfo -nothrottle -sound none -video none -seconds_to_run 100 -cfg_directory "$O/w/cfg" \
  -nvram_directory "$O/w/nvram" -snapshot_directory "$O/snap" -diff_directory "$O/w/diff" -state_directory "$O/w/sta" \
  -inipath "$O/w" -autoboot_script scripts/lua/cps3_vlog.lua 2>&1 | grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|redearth' || true
fail=0; k=0
for s in $(ls "$O"/snap/redearthn/*.png 2>/dev/null); do
  python3 tools/imgdiff.py build/expect_$k.png "$s" --mask "$O/diff_$k.png" || fail=1
  k=$((k + 1))
done
n=$(ls build/expect_*.png | wc -l)
if [ "$k" -ne "$n" ]; then echo "$k of $n snapshots taken (MAME stopped early: see $O/writes.log)"; fail=1; fi
exit $fail
