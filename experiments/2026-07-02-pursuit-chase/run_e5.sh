#!/usr/bin/env bash
# E5 pursuit-chase run matrix. The pursuit DR is already in phase3_sitl.py (do NOT
# re-patch). Four trials, one script, no stages. phase3_sitl overwrites
# raw/phase3a-sitl/trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/results.json every
# run -- snapshot immediately after each, same gotcha E2/E3/E4 hit.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-02-pursuit-chase
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1 label(dir)  $2 speed
  local dir="$CAMP/runs/$1"; local v="$2"
  echo "=========== E5 $dir  speed=$v  --loss-gate motion --dr pursuit ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" --loss-gate motion --dr pursuit 2>&1
  mkdir -p "$dir"
  cp "$SRC/runs/phase3a-sitl/results.json" "$dir/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$dir/trial.csv" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.mp4" "$dir/trial.mp4" 2>/dev/null
  echo "--- snapshot -> $dir ---"
}

run p-0.5  0.5
run p-1.0  1.0
run p-1.5  1.5
run p-1.5b 1.5
echo "=========== E5 MATRIX DONE ==========="
