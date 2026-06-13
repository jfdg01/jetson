#!/usr/bin/env bash
# Run every pending unit of a campaign, each in its OWN fresh session, sequentially.
#   usage: experiments/run-campaign.sh <campaign-dir>
# Resumable: skips DONE units, halts on FAILED or BLOCKED so a human can intervene.
# Sequential by design — the Jetson is a single device; units cannot run concurrently.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAMP="${1:?usage: run-campaign.sh <campaign-dir>}"
CARDS_DIR="$CAMP/runcards"
[ -d "$CARDS_DIR" ] || CARDS_DIR="$CAMP"
[ -d "$CARDS_DIR" ] || { echo "no run cards under $CAMP" >&2; exit 1; }

card_status() { grep -m1 '^status:' "$1" | awk '{print $2}'; }

shopt -s nullglob
mapfile -t CARDS < <(ls "$CARDS_DIR"/*.md | sort)
[ "${#CARDS[@]}" -gt 0 ] || { echo "no *.md run cards in $CARDS_DIR" >&2; exit 1; }

for card in "${CARDS[@]}"; do
  st="$(card_status "$card")"
  case "$st" in
    DONE)    echo "skip  [DONE]    $(basename "$card")"; continue ;;
    BLOCKED) echo "stop  [BLOCKED] $(basename "$card") — resolve precondition, then rerun"; exit 2 ;;
  esac

  echo "=== run   [$st] $(basename "$card") ==="
  "$REPO_ROOT/experiments/run-unit.sh" "$card"

  new="$(card_status "$card")"           # status the session wrote back
  echo "=== done  [$new] $(basename "$card") ==="
  case "$new" in
    FAILED)  echo "unit FAILED — halting campaign (negative result is recorded; review before continuing)"; exit 1 ;;
    RUNNING|TODO) echo "WARNING: unit left status=$new (session may not have finished cleanly) — halting"; exit 3 ;;
    BLOCKED) echo "unit BLOCKED — halting"; exit 2 ;;
  esac
done

echo "campaign complete: all units DONE."
