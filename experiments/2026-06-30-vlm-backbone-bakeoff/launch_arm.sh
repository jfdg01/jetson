#!/usr/bin/env bash
# Crash-resistant launcher for a bake-off arm. Auto-restarts on non-zero exit;
# the trainer's epoch-level resume + run_arm's per-lr DONE sentinel mean each
# restart picks up where it died (loses <1 epoch), not from scratch. Capped so a
# deterministic failure (bad config) can't loop forever.
#   bash experiments/2026-06-30-vlm-backbone-bakeoff/launch_arm.sh <arm> [driver.py]
# driver defaults to run_arm.py; arm D (Florence) passes run_florence.py (enc-dec seq2seq).
set -u
ARM="${1:?usage: launch_arm.sh <arm> [driver.py]}"
DRIVER="${2:-run_arm.py}"
cd "$(dirname "$0")/../.." || exit 1            # repo root
export HF_TOKEN="$(cat .hugging-face-token 2>/dev/null)"
export TRANSFORMERS_VERBOSITY=error   # silence per-collate info spam (PaliGemma image-token notice)
LOG="experiments/2026-06-30-vlm-backbone-bakeoff/raw/${ARM}-sweep.log"
mkdir -p "$(dirname "$LOG")"
MAX=8
for try in $(seq 1 $MAX); do
  echo "=== launch attempt $try/$MAX $(date -u +%FT%TZ) ===" >>"$LOG"
  .venv-ft/bin/python "experiments/2026-06-30-vlm-backbone-bakeoff/$DRIVER" \
      --arm "$ARM" --stage all >>"$LOG" 2>&1
  rc=$?
  echo "=== exited rc=$rc (attempt $try) $(date -u +%FT%TZ) ===" >>"$LOG"
  [ $rc -eq 0 ] && { echo "=== arm $ARM COMPLETE ===" >>"$LOG"; exit 0; }
  sleep 15
done
echo "=== arm $ARM gave up after $MAX attempts ===" >>"$LOG"
exit 1
