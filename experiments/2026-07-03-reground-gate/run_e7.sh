#!/usr/bin/env bash
# E7 reground-gate run matrix. The reground_motion_ok + --reground-gate patches
# are already in phase3_sitl.py (do NOT re-patch). Seven trials, one script.
# phase3_sitl overwrites raw/phase3a-sitl/trial-<v>ms.{csv,mp4} +
# runs/phase3a-sitl/results.json every run -- snapshot immediately after each,
# same gotcha E2-E6 hit.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-03-reground-gate
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1 label(dir)  $2 speed  $3.. extra flags
  local dir="$CAMP/runs/$1"; local v="$2"; shift 2
  echo "=========== E7 $dir  speed=$v  extra: $* ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" \
    --loss-gate motion --dr pursuit --acquire-hold motion "$@" 2>&1
  mkdir -p "$dir"
  cp "$SRC/runs/phase3a-sitl/results.json" "$dir/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$dir/trial.csv" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.mp4" "$dir/trial.mp4" 2>/dev/null
  echo "--- snapshot -> $dir ---"
}

run ctl-decoy   0.25 --twin decoy                          # gate OFF: E3-S2 attribution control
run mg-decoy-a  0.25 --twin decoy --reground-gate motion
run mg-decoy-b  0.25 --twin decoy --reground-gate motion
run mg-decoy-c  0.25 --twin decoy --reground-gate motion
run mg-reg-0.5  0.5  --reground-gate motion                # plain-occlusion regression legs
run mg-reg-1.0  1.0  --reground-gate motion
run mg-reg-1.5  1.5  --reground-gate motion                # stretch: reported, not in the RQ
echo "=========== E7 MATRIX DONE ==========="
