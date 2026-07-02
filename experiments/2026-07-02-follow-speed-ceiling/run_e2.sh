#!/usr/bin/env bash
# E2 speed-ceiling sweep: 0.5 (re-run), 1.0, 1.5 m/s, levers ON, local 3090 carry.
# phase3_sitl writes raw/phase3a-sitl/trial-<v>ms.csv + runs/phase3a-sitl/results.json
# (overwritten each run); we snapshot per speed into this campaign's runs/speed-<v>/.
set -u
REPO=/home/gara/jetson
CAMP=$REPO/experiments/2026-07-02-follow-speed-ceiling
SRC=$REPO/experiments/2026-07-01-temporal-acquire-carry
PY=$REPO/.venv-ft/bin/python

# preserve trial-1's 0.5 FAIL before the re-run overwrites it
[ -f "$SRC/raw/phase3a-sitl/trial-0.5ms.csv" ] && \
  cp -n "$SRC/raw/phase3a-sitl/trial-0.5ms.csv" "$SRC/raw/phase3a-sitl/trial-0.5ms-run1.csv"

for v in 0.5 1.0 1.5; do
  echo "=========== E2 speed=$v ==========="
  cd "$REPO" && "$PY" "$SRC/phase3_sitl.py" --speed "$v" 2>&1
  d="$CAMP/runs/speed-$v"; mkdir -p "$d"
  cp "$SRC/runs/phase3a-sitl/results.json" "$d/results.json" 2>/dev/null
  cp "$SRC/raw/phase3a-sitl/trial-${v}ms.csv" "$d/trial.csv" 2>/dev/null
  echo "--- snapshot -> $d ---"
done
echo "=========== E2 SWEEP DONE ==========="
