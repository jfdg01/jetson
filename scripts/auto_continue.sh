#!/usr/bin/env bash
#
# auto_continue.sh — OS-level auto-continuation for the v2 principled rebuild.
#
# WHY THIS EXISTS
#   On Claude Pro the working session pauses when the 5-hour token window is
#   exhausted. A scheduler that lives *inside* the harness/session (the earlier
#   CronCreate durable:true attempt) dies with the session, so it never re-fires.
#   This script is invoked by the *real* OS crontab, which is independent of any
#   Claude session — so it survives token exhaustion. Each tick it launches a
#   fresh headless `claude -p` that re-reads project state and continues the
#   lowest-unfinished phase. When the window is exhausted the headless run fails
#   fast (rate-limited, ~no token cost); when the window resets the next tick
#   simply succeeds. No window-reset detection needed — bounded retries.
#
# SAFETY GUARDS (in order)
#   1. STOP sentinel  -> operator kill switch; never launches while present.
#   2. DONE sentinel  -> all phases finished; stops launching (no token waste).
#   3. flock          -> atomic mutex; never two headless runs at once.
#   4. pgrep -x claude-> defers to ANY live claude (the interactive session too),
#                        so cron only takes over once the live session is gone.
#   5. timeout        -> bounds a runaway/hung headless run; next tick resumes.
#
# Idempotent by construction: the continuation prompt re-derives state every
# fire, so a partial run is safely picked up by the next.

set -uo pipefail

# --- cron runs with a minimal environment; pin everything we rely on ----------
export HOME="${HOME:-/home/gara}"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

REPO="/home/gara/jetson"
STATE="$REPO/.auto-continue"
PROMPT_FILE="$REPO/scripts/auto_continue_prompt.md"
LOCK="$STATE/run.lock"
LOG="$STATE/auto-continue.log"
SESSION_LOG_DIR="$STATE/sessions"
STOP="$STATE/STOP"
DONE="$STATE/DONE"

# Max wall-clock for one headless run. A productive Phase-4 run can be long; the
# next tick continues idempotently, so this only bounds true hangs.
MAX_RUN_SECONDS="${AUTO_CONTINUE_MAX_RUN_SECONDS:-10800}"   # 3h

mkdir -p "$STATE" "$SESSION_LOG_DIR"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

# 1 + 2: sentinels --------------------------------------------------------------
if [[ -f "$STOP" ]]; then log "skip: STOP sentinel present"; exit 0; fi
if [[ -f "$DONE" ]]; then log "skip: DONE sentinel present (all phases complete)"; exit 0; fi
if [[ ! -f "$PROMPT_FILE" ]]; then log "ERROR: prompt file missing ($PROMPT_FILE)"; exit 1; fi

# 3: flock — acquire non-blocking, hold for the whole wrapper lifetime ----------
exec 9>"$LOCK"
if ! flock -n 9; then log "skip: another auto_continue run holds the lock"; exit 0; fi

# 4: defer to any live claude (interactive session or a prior headless run) -----
if pgrep -x claude >/dev/null 2>&1; then
  log "skip: a claude process is already running (deferring to live session)"
  exit 0
fi

# --- launch the headless continuation -----------------------------------------
ts="$(date -u +%Y%m%dT%H%M%SZ)"
session_log="$SESSION_LOG_DIR/$ts.log"
log "launch: starting headless claude (timeout ${MAX_RUN_SECONDS}s) -> $session_log"

cd "$REPO" || { log "ERROR: cannot cd to $REPO"; exit 1; }

timeout "${MAX_RUN_SECONDS}s" \
  claude -p "$(cat "$PROMPT_FILE")" \
    --dangerously-skip-permissions \
    --add-dir "$REPO" \
    >>"$session_log" 2>&1
rc=$?

if   [[ $rc -eq 0   ]]; then log "done: headless run exited 0"
elif [[ $rc -eq 124 ]]; then log "warn: headless run hit ${MAX_RUN_SECONDS}s timeout (next tick resumes)"
else                         log "warn: headless run exited $rc (likely rate-limited / window exhausted; will retry next tick)"
fi

exit 0
