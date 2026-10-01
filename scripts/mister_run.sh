#!/bin/sh
# Install a CPS3 test set on the MiSTer (jtcps3), load it, take N screenshots STEP s apart (the first after WAIT s)
# into <mame_dir>/../mister/shot_<i>.png, then return to the menu.
#   scripts/mister_run.sh <mame_dir> <name> <title> [shots] [step]
# <mame_dir>: tools/mkcps3.py's output (sfiii3na/), e.g. build/vtest2/mame. MISTER=root@host (required; the MiSTer needs jtcps3.rbf
# and jtbeta.zip). Installs /media/fat/games/mame/<name>.zip and /media/fat/_Arcade/<MRA_DIR, default _CPS3Test>/<title>.mra.
set -e
cd "$(dirname "$0")/.."
SRC=$1; NAME=$2; TITLE=$3; N=${4:-10}; STEP=${5:-2}
DEV=${MISTER:?set MISTER=root@<mister-ip>}
OUT=$(dirname "$SRC")/mister
python3 tools/mkmra3.py "$SRC" "$OUT" "$NAME" "$TITLE" >/dev/null
ssh "$DEV" "mkdir -p /media/fat/_Arcade/${MRA_DIR:-_CPS3Test}; rm -rf /media/fat/screenshots/$NAME"
scp -q "$OUT/$NAME.zip" "$DEV:/media/fat/games/mame/"
scp -q "$OUT/$TITLE.mra" "$DEV:/media/fat/_Arcade/${MRA_DIR:-_CPS3Test}/"
# each command write has a timeout: one write to /dev/MiSTer_cmd once blocked for minutes (2026-09-30)
ssh "$DEV" "timeout 20 sh -c \"echo 'load_core /media/fat/_Arcade/${MRA_DIR:-_CPS3Test}/$TITLE.mra' > /dev/MiSTer_cmd\"
  sleep ${WAIT:-5}; i=0
  while [ \$i -lt $N ]; do timeout 5 sh -c 'echo screenshot > /dev/MiSTer_cmd'; sleep $STEP; i=\$((i+1)); done; sleep 1"
rm -f "$OUT"/shot_*.png; i=0
for f in $(ssh "$DEV" "ls /media/fat/screenshots/$NAME/ 2>/dev/null"); do
  i=$((i+1)); scp -q "$DEV:/media/fat/screenshots/$NAME/$f" "$OUT/shot_$i.png"; echo "$OUT/shot_$i.png"
done
[ "${KEEP:-0}" = 1 ] || ssh "$DEV" 'timeout 20 sh -c "echo load_core /media/fat/menu.rbf > /dev/MiSTer_cmd"'
