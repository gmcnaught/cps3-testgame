#!/bin/sh
# A CPS3 video test in MAME (make <prog>; src/<prog>.c): a snapshot in the middle of each 600-frame phase, compared
# with tools/<prog>.py's expected screens. Dumps for tools/cps3render.py go to build/<prog>/run/.
#   scripts/cps3_vtest.sh [vtest|vtest2]
set -e
cd "$(dirname "$0")/.."
P=${1:-vtest}
docker run --rm -v "$PWD":/p -w /p cps3-dev:latest make "$P" >/dev/null
B=build/$P; O=$B/run; rm -rf "$O"; mkdir -p "$O/w"
n=$(ls "$B"/expect_*.png | wc -l | tr -d ' ')
D=$(seq 0 $((n - 1)) | while read k; do printf '%d,' $((600 * k + 300)); done)
VLOG_OUT="$O" VLOG_DUMP="$D" VLOG_END=$((600 * n - 290)) VLOG_FROM=999999 mame sfiii3na -rompath "$B/mame" -nodrc \
  -skip_gameinfo -nothrottle -sound none -video none -seconds_to_run 200 -cfg_directory "$O/w/cfg" \
  -nvram_directory "$O/w/nvram" -snapshot_directory "$O/snap" -diff_directory "$O/w/diff" -state_directory "$O/w/sta" \
  -inipath "$O/w" -autoboot_script scripts/lua/cps3_vlog.lua 2>&1 | grep -v -E '^$|WRONG|EXPECTED|FOUND|NO GOOD|might not|sfiii3' || true
fail=0; k=0
for s in $(ls "$O"/snap/sfiii3na/*.png 2>/dev/null); do
  python3 tools/imgdiff.py "$B/expect_$k.png" "$s" --mask "$O/diff_$k.png" || fail=1
  k=$((k + 1))
done
if [ "$k" -ne "$n" ]; then echo "$k of $n snapshots taken (MAME stopped early: see $O/writes.log)"; fail=1; fi
exit $fail
