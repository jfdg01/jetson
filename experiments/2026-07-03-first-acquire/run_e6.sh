#!/usr/bin/env bash
# E6 first-acquire run matrix. The motion-hold + acquire-log patches are already
# in phase3_sitl.py (do NOT re-patch). Seven trials, one script, no stages.
# phase3_sitl overwrites raw/phase3a-sitl/trial-<v>ms.{csv,mp4} +
# runs/phase3a-sitl/results.json every run -- snapshot immediately after each,
# same gotcha E2-E5 hit.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-03-first-acquire
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1 label(dir)  $2 speed
  local dir="$CAMP/runs/$1"; local v="$2"
  echo "=========== E6 $dir  speed=$v  --loss-gate motion --dr pursuit --acquire-hold motion ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" --loss-gate motion --dr pursuit --acquire-hold motion 2>&1
  mkdir -p "$dir"
  cp "$SRC/runs/phase3a-sitl/results.json" "$dir/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$dir/trial.csv" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.mp4" "$dir/trial.mp4" 2>/dev/null
  echo "--- snapshot -> $dir ---"
}

run mh-0.5   0.5
run mh-1.0a  1.0
run mh-1.0b  1.0
run mh-1.0c  1.0
run mh-1.5a  1.5
run mh-1.5b  1.5
run mh-1.5c  1.5
echo "=========== E6 MATRIX DONE ==========="
