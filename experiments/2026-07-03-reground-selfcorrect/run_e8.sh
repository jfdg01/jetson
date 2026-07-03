#!/usr/bin/env bash
# E8 reground-selfcorrect run matrix. The --duration-s patch to phase3_sitl.py
# is already committed (do NOT re-patch). Four trials, one script.
# phase3_sitl overwrites raw/phase3a-sitl/trial-<v>ms.{csv,mp4} +
# runs/phase3a-sitl/results.json every run -- snapshot immediately after each,
# same gotcha E2-E7 hit.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-03-reground-selfcorrect
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1 label(dir)  $2 speed  $3.. extra flags
  local dir="$CAMP/runs/$1"; local v="$2"; shift 2
  echo "=========== E8 $dir  speed=$v  extra: $* ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" --duration-s 150 \
    --loss-gate motion --dr pursuit --acquire-hold motion "$@" 2>&1
  mkdir -p "$dir"
  cp "$SRC/runs/phase3a-sitl/results.json" "$dir/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$dir/trial.csv" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.mp4" "$dir/trial.mp4" 2>/dev/null
  echo "--- snapshot -> $dir ---"
}

run ctl-decoy-long   0.25 --twin decoy                          # gate OFF: does the loss-gate alone self-correct?
run mg-decoy-a-long  0.25 --twin decoy --reground-gate motion
run mg-decoy-b-long  0.25 --twin decoy --reground-gate motion
run mg-decoy-c-long  0.25 --twin decoy --reground-gate motion
echo "=========== E8 MATRIX DONE ==========="
