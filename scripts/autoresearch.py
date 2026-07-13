#!/usr/bin/env python3
"""Autonomous research burner (2026-07-14 run).

One cron tick = at most one `next-experiment` cycle. Cron wraps this in `flock -n`
so only one cycle runs at a time; ticks that land while a cycle is running are
skipped, so cycles run back-to-back, near-continuous, unattended.

Design: charter at experiments/2026-07-14-autoresearch-run/README.md.
Model split: this fires `claude -p --model opus` (the loop driver / workhorse);
the next-experiment skill itself spawns Fable (model:fable) for per-cycle design.

Guards (checked every tick, cheapest first):
  1. .claude/autoresearch.STOP present  -> kill switch, do nothing.
  2. now >= DEADLINE                     -> remove our crontab line, stop forever.
  3. loop-budget <= 0                    -> runaway cap hit, do nothing until reseeded.
Survives 5h-window token exhaustion for free: a cycle that runs out of tokens just
fails/returns; the next tick after the window resets starts a fresh cycle.

stdlib only on purpose — no venv needed so cron stays trivial.
"""
import subprocess, time, datetime, pathlib

REPO = pathlib.Path("/home/gara/jetson")
DEADLINE = 1784131200          # 2026-07-15 18:00 CEST (Wed), Madrid wall-clock
CLAUDE = "/home/gara/.local/bin/claude"
CYCLE_TIMEOUT = 4 * 3600       # ponytail: 4h hard cap on a stuck cycle; kill + retry next tick
DOTC = REPO / ".claude"
LOG = DOTC / "autoresearch.log"
STOP = DOTC / "autoresearch.STOP"
BUDGET = DOTC / "loop-budget"
LOGDIR = DOTC / "autoresearch-logs"

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
    "this single cycle's merge (or a clean process-failure stop) is done, end your turn."
)


def log(msg):
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{ts} {msg}\n")


def disable_cron():
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    kept = [l for l in cur.splitlines() if "autoresearch.py" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(kept) + "\n", text=True)


def main():
    if STOP.exists():
        log("STOP file present, skipping tick")
        return
    if time.time() >= DEADLINE:
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
