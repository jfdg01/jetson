#!/usr/bin/env bash
# Smoke test for the Jetson experiment pipeline.
# Run from repo root: bash .claude/skills/run-jetson/smoke.sh
set -e

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

echo "=== activating venv ==="
source .venv/bin/activate

echo ""
echo "=== parsers unit tests ==="
python experiments/parsers.py

echo ""
echo "=== capability sweep dry-run (first 2 units) ==="
python experiments/run_campaign.py --dry-run --only 01,02

echo ""
echo "=== gemma sweep dry-run (first unit) ==="
python experiments/run_gemma_sweep.py --dry-run --only G1

echo ""
echo "=== vlm campaign dry-run (first unit) ==="
python experiments/run_vlm_campaign.py --dry-run --only V1

echo ""
echo "=== smoke PASSED ==="
