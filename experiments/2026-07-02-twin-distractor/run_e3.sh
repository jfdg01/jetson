#!/usr/bin/env bash
# E3 twin-distractor: S1 crossing x1, S2 decoy x3. Speed 0.25 (default), levers on,
# local 3090 carry. phase3_sitl writes raw/phase3a-sitl/trial-0.25ms.csv +
# runs/phase3a-sitl/results.json (overwritten each run); snapshot per run here.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-02-twin-distractor
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1=twin mode  $2=dest subdir
  echo "=========== E3 twin=$1 -> $2 ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --twin "$1" 2>&1
  d="$CAMP/runs/$2"; mkdir -p "$d"
  cp "$SRC/runs/phase3a-sitl/results.json" "$d/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-0.25ms.csv" "$d/trial.csv" 2>/dev/null
  echo "--- snapshot -> $d ---"
}

run crossing s1-crossing
run decoy    s2-decoy-run1
run decoy    s2-decoy-run2
run decoy    s2-decoy-run3
echo "=========== E3 DONE ==========="
