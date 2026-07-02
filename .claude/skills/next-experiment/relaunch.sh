#!/usr/bin/env bash
# Relaunch guard for the next-experiment loop. The ONLY sanctioned way to spawn
# the next /next-experiment terminal. Refuses (exit 1, reason on stdout+log)
# unless every check passes. Usage: relaunch.sh [--dry-run|status|cleanup]
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "REFUSED: not in a git repo"; exit 1; }

STATE=.claude
BUDGET=$STATE/loop-budget   # human seeds: echo N > .claude/loop-budget  (authorizes N cycles)
LAST=$STATE/loop-last
LOG=$STATE/loop.log
MIN_INTERVAL=1800  # ponytail: 30-min crash-loop breaker; a real cycle takes far longer

# Windows we spawn carry the NEXTEXP-LOOP-WIN marker in their cmdline. reap
# kills every tagged terminal session except the caller's own (which the NEXT
# cycle reaps) — window closes when its session leader dies.
reap() {
  mysess=$(ps -o sess= -p $$ | tr -d ' ')
  reaped=0
  for w in $(pgrep -f 'NEXTEXP-LOOP-WIN' || true); do
    s=$(ps -o sess= -p "$w" 2>/dev/null | tr -d ' ')
    [ -z "$s" ] || [ "$s" = "$mysess" ] && continue
    pkill -TERM -s "$s" 2>/dev/null
    reaped=$((reaped + 1))
    echo "$(date -Is) REAPED loop window (session $s)" >>"$LOG"
  done
  echo "reaped $reaped stale loop window(s)"
}

if [ "${1:-}" = "cleanup" ]; then reap; exit 0; fi

if [ "${1:-}" = "status" ]; then
  echo "== loop status =="
  echo "branch: $(git branch --show-current)  dirty: $(git status --porcelain | wc -l) files"
  echo "budget: $(cat .claude/loop-budget 2>/dev/null || echo '<none>')"
  echo "open loop windows: $(pgrep -f 'NEXTEXP-LOOP-WIN' | wc -l)  (close all: relaunch.sh cleanup)"
  echo "-- timeline (.claude/loop.log, last 20) --"
  tail -20 .claude/loop.log 2>/dev/null || echo "<no log yet>"
  echo "-- experiment commits since yesterday --"
  git log --oneline --since=yesterday --grep='^E[0-9]\|next-experiment\|Merge experiment' || true
  exit 0
fi

refuse() { echo "REFUSED: $1"; echo "$(date -Is) REFUSED: $1" >>"$LOG"; exit 1; }

branch=$(git branch --show-current)
[ "$branch" = "main" ] || refuse "not on main (on '$branch') — merge must finish first"
[ -z "$(git status --porcelain)" ] || refuse "working tree not clean — closeout incomplete"
[ -f "$BUDGET" ] || refuse "no $BUDGET — human must authorize cycles: echo N > $BUDGET"
n=$(tr -dc 0-9 <"$BUDGET")
{ [ -n "$n" ] && [ "$n" -gt 0 ]; } || refuse "loop budget exhausted ($BUDGET='${n:-}') — human must reseed"
now=$(date +%s)
if [ -f "$LAST" ]; then
  last=$(tr -dc 0-9 <"$LAST")
  gap=$((now - ${last:-0}))
  [ "$gap" -ge "$MIN_INTERVAL" ] || refuse "last relaunch ${gap}s ago (< ${MIN_INTERVAL}s) — crash-loop breaker"
fi
term=""
for t in gnome-terminal xterm konsole kitty alacritty; do
  command -v "$t" >/dev/null && term=$t && break
done
[ -n "$term" ] || refuse "no terminal emulator found"

if [ "${1:-}" = "--dry-run" ]; then
  echo "OK (dry-run): all checks pass; would spawn via $term; budget=$n"
  exit 0
fi

exec 9>"$STATE/loop.lock"
flock -n 9 || refuse "another relaunch already in progress"
reap
echo $((n - 1)) >"$BUDGET"
echo "$now" >"$LAST"
if [ "$term" = "gnome-terminal" ]; then
  DISPLAY=${DISPLAY:-:0} gnome-terminal -- bash -c ": NEXTEXP-LOOP-WIN; cd $PWD && claude --remote-control --dangerously-skip-permissions '/next-experiment'; exec bash" &
else
  DISPLAY=${DISPLAY:-:0} "$term" -e bash -c ": NEXTEXP-LOOP-WIN; cd $PWD && claude --remote-control --dangerously-skip-permissions '/next-experiment'; exec bash" &
fi
echo "$(date -Is) SPAWNED via $term, budget now $((n - 1))" >>"$LOG"
echo "SPAWNED: /next-experiment terminal via $term; budget remaining $((n - 1))"
