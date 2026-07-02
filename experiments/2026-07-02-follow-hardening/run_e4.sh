#!/usr/bin/env bash
# E4 follow-hardening run matrix. Fixes are already in phase3_sitl.py + stream_carry.py
# (do NOT re-patch). Stage 1 selects a loss gate @0.5 m/s; Stage 2 runs the ladder with it.
# phase3_sitl overwrites raw/phase3a-sitl/trial-<v>ms.{csv,mp4} + runs/phase3a-sitl/results.json
# every run -- snapshot immediately after each, same gotcha E2/E3 hit.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-02-follow-hardening
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

run() {  # $1 label(dir)  $2 speed  $3..: extra args
  local dir="$CAMP/runs/$1"; local v="$2"; shift 2
  echo "=========== E4 $dir  speed=$v  $* ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" "$@" 2>&1
  mkdir -p "$dir"
  cp "$SRC/runs/phase3a-sitl/results.json" "$dir/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$dir/trial.csv" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.mp4" "$dir/trial.mp4" 2>/dev/null
  echo "--- snapshot -> $dir ---"
}

# Stage 1: gate selection @ 0.5
run s1-none   0.5 --loss-gate none
run s1-score  0.5 --loss-gate score --score-tau 0
run s1-motion 0.5 --loss-gate motion

echo
echo ">>> STAGE 1 DONE. Read runs/s1-*/results.json, apply the chosen-gate rule in README.md,"
echo ">>> then set GATE below and run Stage 2 (or re-invoke with: GATE=motion bash run_e4.sh --stage2)."
echo

# Stage 2: ladder with the chosen gate. Default motion (the backstop); override with GATE=score.
if [ "${1:-}" = "--stage2" ]; then
  GATE="${GATE:-motion}"
  echo "=========== E4 STAGE 2  gate=$GATE ==========="
  EXTRA="--loss-gate $GATE"; [ "$GATE" = "score" ] && EXTRA="$EXTRA --score-tau 0"
  run ladder-1.0 1.0 $EXTRA
  run ladder-1.5 1.5 $EXTRA
  echo "=========== E4 LADDER DONE ==========="
fi
