#!/usr/bin/env python3
"""Autonomous research burner (2026-07-14 run; generalized 2026-07-20).

One cron tick = at most one `next-experiment` cycle. Cron wraps this in `flock -n`
so only one cycle runs at a time; ticks that land while a cycle is running are
skipped, so cycles run back-to-back, near-continuous, unattended.

Design: charter at experiments/2026-07-14-autoresearch-run/README.md.
Model split: this fires `claude -p --model opus` (the loop driver / workhorse);
the next-experiment skill itself spawns Fable (model:fable) for per-cycle design.

Guards (checked every tick, cheapest first):
  1. .claude/autoresearch.STOP present   -> kill switch, do nothing.
  2. .claude/autoresearch.deadline unset -> fail closed, do nothing (see DEADLINE_FILE).
  3. now >= that deadline                -> remove our crontab line, stop forever.
  4. loop-budget <= 0                    -> runaway cap hit, do nothing until reseeded.
Survives 5h-window token exhaustion for free: a cycle that runs out of tokens just
fails/returns; the next tick after the window resets starts a fresh cycle, and the
prompt tells the driver to run the loop-focus resume protocol before redesigning
anything (that is what stops a rate-limit kill from double-spending the budget).

stdlib only on purpose — no venv needed so cron stays trivial.
"""
import subprocess, time, datetime, pathlib

REPO = pathlib.Path("/home/gara/jetson")
CLAUDE = "/home/gara/.local/bin/claude"
# ponytail: 11h > the 10h per-experiment hard cap in .claude/loop-focus, so a legitimately
# long matrix is never killed mid-run. Trade: a genuinely hung cycle burns up to 11h.
CYCLE_TIMEOUT = 11 * 3600
DOTC = REPO / ".claude"
LOG = DOTC / "autoresearch.log"
STOP = DOTC / "autoresearch.STOP"
BUDGET = DOTC / "loop-budget"
LOGDIR = DOTC / "autoresearch-logs"
# Deadline lives in a file, not a constant: a hardcoded past date silently disables the
# loop (it did, 2026-07-19). Missing/unparseable file = fail closed and say so, so the
# failure mode is a logged skip, never a burn nobody authorized. Extend the run with:
#   date -d '2026-07-21 18:00' -Is > .claude/autoresearch.deadline
DEADLINE_FILE = DOTC / "autoresearch.deadline"

PROMPT = (
    "Run the next-experiment skill now to execute exactly ONE autonomous research "
    "cycle end-to-end: you are the Opus loop driver. Read status, spawn the Fable "
    "design subagent (model:fable) for audit+pick-RQ+design, verify its handoff, run "
    "the matrix, fill Results, append the RESULTS/QUESTIONS/DECISIONS ledgers, cut the "
    "proof deliverables, commit on the experiment branch, merge --no-ff to main, and "
    "decrement .claude/loop-budget. No human is available: never ask a question, make "
    "every mechanical call yourself per the skill's verdict rules. Honor .claude/"
    "loop-focus verbatim (it may tell you to run a deep-research cycle first when a "
    "method gap blocks the RQ). A FAIL verdict is a valid result and still merges. When "
    "this single cycle's merge (or a clean process-failure stop) is done, end your turn. "
    "Run the matrix in the FOREGROUND of your own turn and wait for it: never `nohup ... &` "
    "it and end the turn. Cron holds a `flock` only for as long as you are alive, so "
    "backgrounding the long run releases the lock and the next tick starts a SECOND driver "
    "on your branch (this happened 2026-07-20T03:00Z, two duplicate matrices). "
    "Before spawning Fable, run the RESUME AFTER TOKEN EXHAUSTION protocol at the bottom "
    "of .claude/loop-focus: a previous cycle may have been killed mid-flight by the 5h-"
    "window rate limit. Classify the state from .claude/loop.log + the experiment/* "
    "branches and resume it; do NOT redesign over a surviving pre-registration, and never "
    "decrement the budget twice for one slug."
)


def deadline():
    """Epoch seconds, or None if unset/unreadable (caller fails closed)."""
    try:
        return datetime.datetime.fromisoformat(
            DEADLINE_FILE.read_text().strip()).astimezone().timestamp()
    except Exception:
        return None


def log(msg):
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{ts} {msg}\n")


def disable_cron():
    """Drop our own crontab line — match on __file__ so a renamed copy still disarms."""
    me = pathlib.Path(__file__).name
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    kept = [l for l in cur.splitlines() if me not in l]
    subprocess.run(["crontab", "-"], input="\n".join(kept) + "\n", text=True)


def main():
    if STOP.exists():
        log("STOP file present, skipping tick")
        return
    dl = deadline()
    if dl is None:
        log(f"no usable deadline in {DEADLINE_FILE.name}, skipping tick (write an ISO "
            f"timestamp there to arm the run)")
        return
    if time.time() >= dl:
        log("DEADLINE reached: disabling cron, stopping run")
        disable_cron()
        return
    try:
        budget = int(BUDGET.read_text().strip() or "0")
    except Exception:
        budget = 0
    if budget <= 0:
        log("budget<=0, skipping tick (reseed .claude/loop-budget to resume)")
        return

    LOGDIR.mkdir(exist_ok=True)
    t0 = int(time.time())
    cyclelog = LOGDIR / f"cycle-{t0}.log"
    log(f"CYCLE-START budget={budget} log={cyclelog.name}")
    try:
        with cyclelog.open("w") as out:
            r = subprocess.run(
                [CLAUDE, "-p", PROMPT, "--model", "opus",
                 "--dangerously-skip-permissions"],
                cwd=str(REPO), timeout=CYCLE_TIMEOUT,
                stdout=out, stderr=subprocess.STDOUT)
        log(f"CYCLE-END rc={r.returncode} dur={int(time.time())-t0}s")
    except subprocess.TimeoutExpired:
        log(f"CYCLE-TIMEOUT after {CYCLE_TIMEOUT}s, killed")


if __name__ == "__main__":
    main()
