#!/usr/bin/env bash
# Unattended ROI-crop accuracy sweep: wait for the terse-output training to free the
# GPU, then run the broad + survivor sweep. Detached (setsid nohup) so it survives the
# Claude session closing. Logs + a DONE/FAIL sentinel land in ./logs.
set -u
cd /home/gara/jetson
LOG_DIR="experiments/2026-06-25-roi-crop-anchor/logs"
mkdir -p "$LOG_DIR"
SENTINEL="$LOG_DIR/sweep.done"
LOG="$LOG_DIR/sweep.log"
TRAIN_PID="${1:-902674}"

{
  echo "[overnight] $(date -u +%FT%TZ) waiting for training PID $TRAIN_PID to exit..."
  while kill -0 "$TRAIN_PID" 2>/dev/null; do sleep 30; done
  echo "[overnight] $(date -u +%FT%TZ) training exited; waiting for GPU to drop <6GB..."
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
    echo "[overnight] GPU used=${used} MiB"
    [ "${used:-99999}" -lt 6000 ] && break
    sleep 15
  done
  echo "[overnight] $(date -u +%FT%TZ) starting sweep"
  .venv-ft/bin/python experiments/2026-06-25-roi-crop-anchor/run_sweep.py
  rc=$?
  echo "[overnight] $(date -u +%FT%TZ) sweep exit code=$rc"
  echo "$rc" > "$SENTINEL"
} >> "$LOG" 2>&1
