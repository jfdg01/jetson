You are resuming the Jetson master's-thesis v2 "principled rebuild" (Part II)
autonomously, launched by the OS-level auto-continuation cron (scripts/auto_continue.sh).
This is a headless, unattended run — there is no human watching. Work, document,
commit locally, and exit cleanly.

## First, orient (do this every fire — never assume state)
1. Read `/home/gara/.claude/projects/-home-gara-jetson/memory/MEMORY.md` and
   `/home/gara/.claude/projects/-home-gara-jetson/memory/project-v2-rebuild.md` —
   the authoritative live-state record of which phases are done.
2. Read `CLAUDE.md` (working conventions) and the latest entries of `DECISIONS.md`
   and `RESULTS.md`.
3. `git branch --show-current` must be `v2/principled-rebuild`. If not, switch to it.
   Run `git status` and `git log --oneline -5` to see exactly where work stands.
4. Determine the **lowest-unfinished phase** from the memory file and the git log.
   Continue from there. NEVER redo completed/committed work.

## The goal
Drive the gated phases to completion: Phase 0 → 1 → 2 → 3 are DONE and committed.
**Phase 4 (export & deploy) is the current frontier** unless the memory file says
otherwise. Phase 4 = fill `grounding/export/to_gguf.py` (HF→GGUF with the
F16-vs-Q8 disambiguation gate), `grounding/deploy/serve.py`, and implement the
`JetsonBackend` (currently a NotImplementedError stub in `grounding/eval/backends.py`).
Gate: deployed IoU within the Phase-0 fidelity budget of the HF full-val 59.5%.
Jetson is reached via `ssh jetson` (user jfdg; sudo needs a password there except
nvpmodel/jetson_clocks). The merged Phase-3 checkpoint is `runs/v2/phase3-refdrone-1024/`.

## Non-negotiable conventions (from CLAUDE.md)
- GPU/eval/training/export work uses the `.venv-ft` venv. Device-benchmark tooling
  under `experiments/` is stdlib-only. NEVER pip install globally.
- `GROUNDING_PROMPT` and the parser/metric come verbatim from `grounding/contract.py`;
  never re-type them. Run `pytest tests/` (or `make test`) as the regression gate.
- Document EVERY finding (success or failure) in `results/<dated-dir>/` + a row in
  `RESULTS.md` + a `DECISIONS.md` entry (Decision/Alternatives/Reasoning/Tradeoff/
  Revisit-when) **in the same turn** as the finding. Negative results are thesis content.
- Each phase is gated: do not start the next until the prior gate is green AND
  documented same-turn. Write per-run manifests under `runs/`.
- Commit locally on `v2/principled-rebuild` when a unit of work is done. Branch-first
  off main; **NEVER push to origin**. Commit trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- After meaningful progress, UPDATE the memory file
  `/home/gara/.claude/projects/-home-gara-jetson/memory/project-v2-rebuild.md`
  so the next fire resumes correctly.

## Stop conditions (important — this controls the cron loop)
- If a step genuinely needs a human (e.g. an irreversible/destructive action, a
  remote firmware flash, a strategy fork with no data-driven answer, or required
  sudo-with-password on the Jetson that cannot proceed unattended): write a short
  note to `.auto-continue/BLOCKED.md` explaining what is needed, do NOT force it,
  commit what is safely done, and exit.
- When **ALL phases (through Phase 4 gate) are complete and documented**, create the
  sentinel `.auto-continue/DONE` with a one-line summary. This tells cron to stop
  launching. Do this only when the work is truly finished.
- Do not run `git push`. Do not delete others' work. Do not act outside this repo
  except `ssh jetson` for deployment as described.

Work in focused, committed increments. If the token window is short, make whatever
safe progress you can, commit it, update memory, and exit — the next cron tick
continues where you left off.
