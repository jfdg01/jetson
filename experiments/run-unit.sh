#!/usr/bin/env bash
# Run ONE experiment unit in a fresh, isolated Claude session.
#   usage: experiments/run-unit.sh <path-to-runcard.md>
# Env overrides: CLAUDE_MODEL (default: sonnet), CLAUDE_PERM (default: bypassPermissions)
# See experiments/README.md — esp. the permissions/autonomy note before changing CLAUDE_PERM.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CARD="${1:?usage: run-unit.sh <path-to-runcard.md>}"
[ -f "$CARD" ] || { echo "run card not found: $CARD" >&2; exit 1; }
CARD_ABS="$(cd "$(dirname "$CARD")" && pwd)/$(basename "$CARD")"

MODEL="${CLAUDE_MODEL:-sonnet}"
PERM="${CLAUDE_PERM:-bypassPermissions}"

# Build the kickoff prompt from the constant bootstrap, substituting only the card path.
PROMPT="$(sed "s#{{RUNCARD}}#${CARD_ABS}#g" "$REPO_ROOT/experiments/bootstrap-prompt.md")"

echo ">> fresh session  model=$MODEL  perm=$PERM"
echo ">> run card:      $CARD_ABS"
cd "$REPO_ROOT"   # so the session auto-loads project CLAUDE.md / README.md
claude -p "$PROMPT" \
  --model "$MODEL" \
  --permission-mode "$PERM" \
  --output-format text
