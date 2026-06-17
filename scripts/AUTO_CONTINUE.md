# Auto-continuation (Pro 5-hour-window self-resume)

Keeps the v2 principled rebuild moving when the Claude **Pro 5-hour token window**
runs out mid-session. The earlier in-harness scheduler died with the session; this
one lives in the **OS crontab**, so it is independent of any Claude session.

## How it works

```
user crontab  ──every 15 min──▶  scripts/auto_continue.sh  ──▶  claude -p (headless)
                                         │                          re-reads project
                                         │                          state, continues the
                                         ▼                          lowest-unfinished phase,
                                  guards (below)                    commits locally, exits
```

- Window exhausted → headless `claude -p` fails fast (rate-limited, ~no token cost) →
  next tick retries. Window reset → next tick just succeeds. No reset-time detection.
- Continuation prompt: `scripts/auto_continue_prompt.md` (self-contained, idempotent —
  re-derives state every fire, never redoes committed work).

## Guards (in order; the wrapper does nothing unless all pass)

1. `.auto-continue/STOP`  — operator kill switch. Present ⇒ never launches.
2. `.auto-continue/DONE`  — all phases complete. Written by the agent when finished ⇒ stops launching.
3. `flock`                — atomic mutex; never two headless runs at once.
4. `pgrep -x claude`      — defers to ANY live claude (incl. the interactive session), so cron is strictly a fallback.
5. `timeout 3h`           — bounds a hung run; the next tick resumes.

## Operate

```bash
# Pause / resume the loop
touch /home/gara/jetson/.auto-continue/STOP      # pause
rm    /home/gara/jetson/.auto-continue/STOP      # resume

# Watch what it's doing
tail -f /home/gara/jetson/.auto-continue/auto-continue.log     # scheduler decisions
ls -t   /home/gara/jetson/.auto-continue/sessions/             # per-run headless transcripts

# Is it installed?
crontab -l | grep auto_continue

# Remove it entirely (e.g. when all phases are done)
crontab -l | grep -v auto_continue.sh | crontab -
```

If a step needs a human, the agent writes `.auto-continue/BLOCKED.md` (what's needed)
and stops instead of forcing it. The runtime-state dir `.auto-continue/` is gitignored;
the mechanism (`scripts/`) is committed. Decision + rationale: `DECISIONS.md`
(2026-06-18T00:45). Never pushes to origin — local commits only.
