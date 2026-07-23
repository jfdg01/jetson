#!/usr/bin/env python3
"""Watch a herdr pane for the Claude session-limit banner, send `continue` when the window resets.

    python3 scripts/herdr_continue.py rework          # pane id, terminal id or title substring
    python3 scripts/herdr_continue.py --selfcheck

Trigger is the literal banner text, not the status-bar usage percentage:
    You've hit your session limit · resets 9:40am (Europe/Madrid)

Audit trail: .claude/herdr-continue.log (also echoed to stdout).
"""
import json
import logging
import subprocess
import sys
import re
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BANNER = "hit your session limit"
# "resets 9:40am (Europe/Madrid)" / "resets 3pm" / "resets at 9:40 AM"
RESET_RE = re.compile(
    r"resets\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap])m\s*(?:\(([^)]+)\))?", re.I
)
MARGIN_S = 90  # the reset is not exact; wait past it
WORKING_WAIT_MS = 90_000  # a resumed session should start working within this
FALLBACK_ATTEMPTS = 5  # hourly probes; the window is 5h, so this spans it
FALSE_POSITIVE_COOLDOWN_S = 300  # banner text present but session still working
LOG_PATH = Path(__file__).resolve().parent.parent / ".claude" / "herdr-continue.log"

log = logging.getLogger("herdr-continue")


def setup_logging():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    for h in (logging.FileHandler(LOG_PATH), logging.StreamHandler()):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def herdr(*args):
    """Run a herdr CLI command. Returns parsed JSON, or {} on any failure (logged)."""
    p = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if p.returncode != 0 or p.stderr.strip():
        log.error("herdr %s -> rc=%s stderr=%s", " ".join(args), p.returncode, p.stderr.strip()[:300])
    if not p.stdout.strip():
        return {}
    try:
        r = json.loads(p.stdout)
    except json.JSONDecodeError:
        log.error("herdr %s -> unparseable stdout: %s", " ".join(args), p.stdout[:300])
        return {}
    if "error" in r and r["error"].get("code") != "timeout":
        log.error("herdr %s -> api error: %s", " ".join(args), r["error"])
    return r


def resolve(target):
    """Accept a pane id, terminal id or title substring -> the matching agent record."""
    agents = herdr("agent", "list").get("result", {}).get("agents", [])
    hits = [a for a in agents if target in (a["pane_id"], a["terminal_id"])] or [
        a for a in agents if target.lower() in a["terminal_title_stripped"].lower()
    ]
    if len(hits) != 1:
        listing = "\n".join(
            f"  {a['pane_id']}  {a['terminal_id']}  [{a['agent_status']}]  {a['terminal_title_stripped']}"
            for a in agents
        )
        log.error("%s match for %r. panes:\n%s", "no" if not hits else "ambiguous", target, listing)
        return None
    return hits[0]


def current_pane(terminal_id):
    """pane_id for a terminal, re-read every loop: panes move between tabs, ids get reused."""
    a = resolve(terminal_id)
    return a["pane_id"] if a else None


def parse_reset(line, now):
    """-> aware datetime of the next occurrence of the banner's reset time, or None."""
    m = RESET_RE.search(line)
    if not m:
        return None
    hour, minute, ampm, tzname = m.group(1), m.group(2), m.group(3), m.group(4)
    hour = int(hour) % 12 + (12 if ampm.lower() == "p" else 0)
    tz = ZoneInfo(tzname) if tzname else now.tzinfo
    now = now.astimezone(tz)
    when = now.replace(hour=hour, minute=int(minute or 0), second=0, microsecond=0)
    if when <= now:
        when += timedelta(days=1)
    return when


def send_continue(terminal_id):
    """Send `continue`; True if the session actually started working on it."""
    pane = current_pane(terminal_id)  # re-resolve: the pane may have moved while we slept
    if pane is None:
        return False
    # pane run types the text but does not submit it; Enter is a separate key event
    herdr("pane", "run", pane, "continue")
    herdr("pane", "send-keys", pane, "Enter")
    # a still-limited session stays idle; an accepted continue flips it to working
    r = herdr("agent", "wait", terminal_id, "--status", "working", "--timeout", str(WORKING_WAIT_MS))
    ok = "result" in r
    log.log(logging.INFO if ok else logging.WARNING,
            "sent continue to %s (accepted=%s)", pane, ok)
    if not ok:
        tail = (herdr("agent", "read", terminal_id, "--source", "visible", "--lines", "12",
                      "--format", "text").get("result", {}).get("read", {}).get("text", ""))
        log.warning("pane tail after unaccepted send:\n%s", tail[-600:])
    return ok


def resume_by_retry(terminal_id):
    """Fallback when the banner carried no parseable reset time: probe hourly across the window."""
    for attempt in range(1, FALLBACK_ATTEMPTS + 1):
        log.info("fallback: sleeping 1h before attempt %d/%d", attempt, FALLBACK_ATTEMPTS)
        time.sleep(3600)
        if send_continue(terminal_id):
            log.info("fallback: accepted on attempt %d (~%dh after banner)", attempt, attempt)
            return True
        log.warning("fallback: attempt %d not accepted, still limited", attempt)
    log.error("fallback: %d hourly attempts exhausted, giving up on this banner",
              FALLBACK_ATTEMPTS)
    return False


def main(target):
    a = resolve(target)
    if not a:
        sys.exit(1)
    terminal_id = a["terminal_id"]  # stable id; pane ids and titles are not
    log.info("armed: watching %s (%s) %r for %r", a["pane_id"], terminal_id,
             a["terminal_title_stripped"], BANNER)
    ticks = 0
    while True:
        try:
            pane = current_pane(terminal_id)
            if pane is None:
                log.error("terminal %s is gone, waiting 60s", terminal_id)
                time.sleep(60)
                continue
            r = herdr("wait", "output", pane, "--match", BANNER,
                      "--source", "recent", "--lines", "400", "--timeout", "3600000")
            if "result" not in r:
                ticks += 1
                log.info("heartbeat: no banner after %dh of watching %s", ticks, pane)
                continue

            line = r["result"]["matched_line"].strip()
            # the phrase can appear for other reasons (a log, a doc, a session talking about it).
            # a real limit stops the session dead, so anything still working is a false positive.
            status = (herdr("agent", "get", terminal_id)
                      .get("result", {}).get("agent", {}).get("agent_status"))
            if status != "idle":
                log.info("banner text seen but agent_status=%s, ignoring: %s", status, line)
                time.sleep(FALSE_POSITIVE_COOLDOWN_S)  # the line stays in the buffer; don't spin
                continue
            log.warning("BANNER HIT on %s: %s", pane, line)

            when = parse_reset(line, datetime.now().astimezone())
            if when is None:
                log.error("no reset time parsed from %r, falling back to hourly retries", line)
                resume_by_retry(terminal_id)
            else:
                sleep_s = (when - datetime.now().astimezone()).total_seconds() + MARGIN_S
                log.info("resuming at %s (in %.1f min)", when.strftime("%F %T %Z"), sleep_s / 60)
                time.sleep(max(0, sleep_s))
                if not send_continue(terminal_id):
                    log.warning("scheduled resume not accepted, falling back to hourly retries")
                    resume_by_retry(terminal_id)
            time.sleep(60)  # don't re-fire on the stale banner still in scrollback
        except KeyboardInterrupt:
            log.info("disarmed by Ctrl-C")
            return
        except Exception:
            log.error("loop error, retrying in 60s:\n%s", traceback.format_exc())
            time.sleep(60)


def selfcheck():
    now = datetime(2026, 7, 22, 23, 30, tzinfo=ZoneInfo("Europe/Madrid"))
    got = parse_reset("You've hit your session limit · resets 9:40am (Europe/Madrid)", now)
    assert (got.hour, got.minute, got.day) == (9, 40, 23), got
    got = parse_reset("resets 11pm (Europe/Madrid)", now)  # 23:00 today is already past
    assert (got.hour, got.day) == (23, 23), got
    assert parse_reset("no reset here", now) is None
    print("selfcheck ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selfcheck":
        selfcheck()
    elif len(sys.argv) > 1:
        setup_logging()
        main(sys.argv[1])
    else:
        sys.exit(__doc__)
