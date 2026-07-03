#!/usr/bin/env python3
"""Relaunch guard for the next-experiment loop. The ONLY sanctioned way to spawn
the next /next-experiment terminal. Refuses (exit 1, reason on stdout+log)
unless every check passes. Usage: relaunch.py [--dry-run|status|cleanup]

Linux-only (reads /proc). Stdlib-only — run with plain python3.
"""
import fcntl
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

MARKER = "NEXTEXP-LOOP-WIN"
MIN_INTERVAL = 1800  # ponytail: 30-min crash-loop breaker; a real cycle takes far longer
TERMINALS = ["gnome-terminal", "xterm", "konsole", "kitty", "alacritty"]

top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                     capture_output=True, text=True)
if top.returncode != 0:
    print("REFUSED: not in a git repo")
    sys.exit(1)
REPO = Path(top.stdout.strip())
os.chdir(REPO)
STATE = REPO / ".claude"
BUDGET = STATE / "loop-budget"  # human seeds: echo N > .claude/loop-budget
LAST = STATE / "loop-last"
LOG = STATE / "loop.log"


def log(line: str) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with LOG.open("a") as f:
        f.write(f"{stamp} {line}\n")


def refuse(reason: str) -> None:
    print(f"REFUSED: {reason}")
    log(f"REFUSED: {reason}")
    sys.exit(1)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def tagged_windows() -> list[int]:
    """PIDs whose cmdline carries the loop-window marker (excluding ourselves)."""
    pids = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            cmdline = (p / "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if MARKER.encode() in cmdline:
            pids.append(int(p.name))
    return pids


def ancestors() -> set[int]:
    """PID chain from us up to init."""
    chain, pid = set(), os.getpid()
    while pid > 1:
        chain.add(pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])  # field 4: ppid
        except (OSError, ValueError, IndexError):
            break
    return chain


def reap() -> None:
    """Kill every tagged window session except our own — window closes when its
    session leader dies. "Own" is detected by ancestry, not by our session:
    Claude Code's Bash tool setsids each command, so our session is never the
    terminal window's session — but the window's bash (= its session leader =
    the session id) IS one of our ancestors. Comparing sessions killed the
    caller's own window (2026-07-03 01:17 stall)."""
    anc = ancestors()
    reaped = set()
    for w in tagged_windows():
        try:
            sess = os.getsid(w)
        except OSError:
            continue
        if sess in anc or sess in reaped:
            continue
        subprocess.run(["pkill", "-TERM", "-s", str(sess)])
        reaped.add(sess)
        log(f"REAPED loop window (session {sess})")
    print(f"reaped {len(reaped)} stale loop window(s)")


def status() -> None:
    print("== loop status ==")
    dirty = len(git("status", "--porcelain").splitlines())
    print(f"branch: {git('branch', '--show-current')}  dirty: {dirty} files")
    print(f"budget: {BUDGET.read_text().strip() if BUDGET.exists() else '<none>'}")
    print(f"open loop windows: {len(tagged_windows())}  (close all: relaunch.py cleanup)")
    print("-- timeline (.claude/loop.log, last 20) --")
    print("\n".join(LOG.read_text().splitlines()[-20:]) if LOG.exists() else "<no log yet>")
    print("-- experiment commits since yesterday --", flush=True)
    subprocess.run(["git", "log", "--oneline", "--since=yesterday",
                    r"--grep=^E[0-9]\|next-experiment\|Merge experiment"])


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "cleanup":
        reap()
        return
    if arg == "status":
        status()
        return

    if (branch := git("branch", "--show-current")) != "main":
        refuse(f"not on main (on '{branch}') — merge must finish first")
    if git("status", "--porcelain"):
        refuse("working tree not clean — closeout incomplete")
    if not BUDGET.exists():
        refuse(f"no {BUDGET} — human must authorize cycles: echo N > {BUDGET}")
    digits = "".join(c for c in BUDGET.read_text() if c.isdigit())
    budget = int(digits) if digits else 0
    if budget <= 0:
        refuse(f"loop budget exhausted ({BUDGET}='{digits}') — human must reseed")
    now = int(time.time())
    if LAST.exists():
        last = "".join(c for c in LAST.read_text() if c.isdigit())
        gap = now - int(last or 0)
        if gap < MIN_INTERVAL:
            refuse(f"last relaunch {gap}s ago (< {MIN_INTERVAL}s) — crash-loop breaker")
    term = next((t for t in TERMINALS if shutil.which(t)), None)
    if term is None:
        refuse("no terminal emulator found")

    if arg == "--dry-run":
        print(f"OK (dry-run): all checks pass; would spawn via {term}; budget={budget}")
        return

    lock = (STATE / "loop.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        refuse("another relaunch already in progress")
    reap()
    BUDGET.write_text(f"{budget - 1}\n")
    LAST.write_text(f"{now}\n")

    # CLAUDE-EXIT stamp = evidence if the spawned claude dies before its
    # CYCLE-START (the 2026-07-03 01:17 stall left no trace at all).
    wincmd = (
        f": {MARKER}; cd {REPO} && "
        "claude --remote-control --dangerously-skip-permissions --model fable '/next-experiment'; "
        f'echo "$(date -Is) CLAUDE-EXIT rc=$? (spawned window)" >> {LOG}; exec bash'
    )
    if term == "gnome-terminal":
        cmd = ["gnome-terminal", "--", "bash", "-c", wincmd]
    else:
        cmd = [term, "-e", f"bash -c {wincmd!r}"]
    env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
    n_before = len(tagged_windows())
    # start_new_session: detach the terminal client from the caller so it
    # survives even if the caller's claude dies mid-spawn.
    with LOG.open("a") as logf:
        subprocess.Popen(cmd, env=env, start_new_session=True,
                         stdout=logf, stderr=logf)
    log(f"SPAWNED via {term}, budget now {budget - 1}")
    time.sleep(3)
    if len(tagged_windows()) > n_before:
        log("SPAWN-VERIFIED window is up")
    else:
        log("SPAWN-DIED window not found 3s after spawn")
    print(f"SPAWNED: /next-experiment terminal via {term}; budget remaining {budget - 1}")


if __name__ == "__main__":
    main()
