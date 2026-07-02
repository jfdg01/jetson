# E6 — first-acquire: motion-hold makes the first VLM lock reliable

**Pre-registered:** 2026-07-03T00:54Z (design, Stage-0 diagnostic, and code patches by Fable;
executor runs the matrix and fills Results only — do NOT re-patch code).
**Status:** PRE-REGISTERED, not yet run.
**Branch:** `experiment/first-acquire`

## Research question

**RQ-E6:** Does a pre-first-lock motion-hold (servoing on the ego-motion-compensated
frame-diff blob so the car stays in FOV across VLM draws) lift the follow ceiling past
0.5 m/s by fixing first-acquire reliability?

**YES iff** mh-0.5 passes its run gate AND >= 2/3 of the 1.0 m/s runs pass their run gate
(run gate: `in_fov_frac >= 0.90` AND `recovered_after_occlusion == true`). Anything else = NO.

## Context and rationale

E5 (`experiments/2026-07-02-pursuit-chase/`) reframed the binding constraint: the pursuit
controller holds 1.5 m/s once seeded (p-1.5b in-FOV 0.927), but at >= 1.0 m/s the trial
almost never gets a first lock (p-1.0: 32 acquire attempts, 31 rejected by the size prior,
never locked). E5 called it an "acquire lottery" but never logged the rejected boxes —
that observability gap is also fixed here.

**Stage-0 diagnostic (already run at design time, 2026-07-03T00:46Z; full data in
`raw/stage0/results.json` + PNGs, script `acquire_bench.py`):** the t=0 frame was
re-rendered over a rover-position grid spanning a full 4 m road-dash period plus an
altitude sweep, and the deployed VLM (Jetson q8_0, greedy) was run on each. Result:
14/19 accepted (IoU vs oracle >= 0.90 on accepts); all 5 rejects are the VLM grounding
"the white car" onto a white road-dash instead of the car (rw ~= 0.203, IoU 0.0), which
happens when the car sits high/clipped in frame or at certain altitudes. Decoding is
greedy (temperature=0), so the per-frame answer is deterministic — the "lottery" is frame
content: cm-scale pose changes flip the greedy output. The size prior is doing its job
(every reject was a genuine dash box); at >= 1.0 m/s the car exits the FOV after ~1-2
draws (~2.3 s wall each) while the copter hovers, so the trial dies waiting for a
repeatable draw on a car-less frame.

**Fix under test — motion-hold acquire (`--acquire-hold motion`):** before the first lock,
when blind, servo the PID on the largest ego-motion-compensated frame-diff blob. The car
is the scene's only mover, so the diff (previous acquire-buffer frame warped onto the
current pose, >= 0.35 s baseline) is the car's swept region; its union bbox is a pixel
target that keeps the car in FOV until a draw accepts. Pose comes free (SITL truth here;
the EKF provides it on real hardware). After the first lock the existing replay + DR +
pursuit machinery owns all blind phases — the hold never re-engages.

**Rejected alternatives** (DECISIONS seed): (a) *retry-only / more attempts* — at >= 1.0 m/s
the car leaves the FOV after <= 2 draws, so retries land on car-less frames; retrying is
what E5's p-1.0 already did 32 times. (b) *Relax the size prior* — Stage 0 shows the prior
correctly rejecting dash boxes (IoU 0.0); relaxing it would admit wrong locks, E2's failure
mode. (c) *2.0 m/s stretch runs* — NadirCam texture covers N in [-20, 140]; a 2.0 m/s car
reaches 150.5 m and runs off the world. Not run.

## Code changes (already committed on `experiment/first-acquire` — executor: do NOT edit)

All in `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`:

- `_ground_affine()` + `motion_blob()` module helpers (warp-compensated frame diff).
- `AcquireCarrySM.acquire_log`: every resolved acquire attempt logged as
  `(t, raw box, accepted)`; exported in `results.json` (E5's blind spot).
- `run_trial(..., acquire_hold=...)` + the pre-first-lock hold injection (guarded:
  `acquire_hold=="motion" and out is None and sm.first_lock_t is None`).
- `--acquire-hold {none,motion}` flag; recorded in the run's `cfg`.
- `selfcheck()` extended (acquire_log contents; motion_blob on two rendered poses; static
  frame yields None). Verified passing 2026-07-03T00:53Z:
  `.venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py --selfcheck`
- Plus `acquire_bench.py` here (Stage-0 tool; nothing to re-run).

## Run matrix

Same rig as E2-E5: local-VLM path (the script boots the Jetson q8_0 llama-server over ssh
itself; do NOT pass `--remote-carry`), local 3090 carry @1024, 75 s per trial. All runs use
the E4/E5 chosen config plus the new flag:
`--loss-gate motion --dr pursuit --acquire-hold motion`. Software versions and environment
are auto-captured per run by the manifest (as E2-E5). Working dir: repo root.

One command drives all seven trials and snapshots each immediately (results/CSV/mp4 are
clobbered between runs — the snapshot is inside the script):

```bash
cd /home/gara/jetson && bash experiments/2026-07-03-first-acquire/run_e6.sh 2>&1 | tee experiments/2026-07-03-first-acquire/run_e6.log
```

| run | speed (m/s) | why | snapshot dir |
|---|---|---|---|
| mh-0.5 | 0.5 | regression: hold must not break the working speed | `runs/mh-0.5/` |
| mh-1.0a/b/c | 1.0 | the RQ: n=3 because E5 showed 1.5 is stochastic run-to-run | `runs/mh-1.0{a,b,c}/` |
| mh-1.5a/b/c | 1.5 | stretch: does the hold also seed 1.5 (E5 p-1.5b held it once seeded) | `runs/mh-1.5{a,b,c}/` |

Gotchas: each trial boots its own SITL + Jetson server (~1-2 min overhead). Run the script
in a way that survives the session (e.g. foreground in this session, or `nohup`); E5 lost a
trial to a torn-down background shell and had to re-run it.

## Verdict rules (mechanical — do not deliberate)

- **Per-run gate:** PASS iff `results.json` has `trial.in_fov_frac >= 0.90` AND
  `trial.recovered_after_occlusion == true` (this is the `gate` field the script prints).
- **Per-speed:** 0.5 passes iff mh-0.5 passes. 1.0 passes iff >= 2 of {a,b,c} pass.
  1.5 passes iff >= 2 of {a,b,c} pass (report regardless; 1.5 does NOT affect RQ-E6).
- **RQ-E6 = YES** iff 0.5 passes AND 1.0 passes; otherwise **NO**. A NO is a valid,
  loop-continuing verdict — record it plainly.
- **Abort criteria:** a run hanging > 10 min past its 75 s trial window, a crash, or a
  missing `results.json` -> snapshot whatever exists into the run dir, mark the run
  INVALID in the Results table, and continue with the next run. An INVALID run may be
  re-run identically ONCE (same command, same snapshot dir, note it); still broken ->
  leave INVALID. If a speed cannot reach 2 valid runs, its verdict is FAIL.
- Also record per run (from `results.json`): `first_lock_s`, `n_acquire_attempts`,
  `n_rejected_acquires`, and the accept fraction derivable from `acquire_log`
  (`n_accepted / len(acquire_log)`). These are diagnosis columns, not gates.

## Estimates (marked as estimates)

- **Runtime:** ~2-2.5 h total (7 trials x ~75 s + ~1-2 min boot each + snapshots). ESTIMATE.
- **mh-0.5:** PASS, ~90% confident — the hold barely engages at 0.5 (E5 p-0.5 locked at
  t=0 draw 1). ESTIMATE.
- **mh-1.0:** PASS 2/3 or 3/3, ~65% confident — Stage 0 gives ~74% accept/draw on
  car-in-frame frames; the hold buys unlimited draws, so lock within ~3 draws (~7 s)
  should be typical; residual risk is blob-servo quality (offset target, PID overshoot).
  ESTIMATE.
- **mh-1.5:** SPLIT or PASS, ~40% confident of >= 2/3 — once seeded, E5 p-1.5b held 0.927;
  the question is whether the hold servo keeps up with 1.5 m/s between draws. ESTIMATE.
- **first_lock_s at 1.0:** ~5-10 s (2-4 draws). ESTIMATE.

## Results (TBD — executor fills; one row per run)

| run | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | accept_frac | notes |
|---|---|---|---|---|---|---|---|---|
| mh-0.5 | | | | | | | | |
| mh-1.0a | | | | | | | | |
| mh-1.0b | | | | | | | | |
| mh-1.0c | | | | | | | | |
| mh-1.5a | | | | | | | | |
| mh-1.5b | | | | | | | | |
| mh-1.5c | | | | | | | | |

**Per-speed verdicts (TBD):** 0.5: — | 1.0: — | 1.5: —
**RQ-E6 verdict (TBD):** —

## Closeout checklist for the executor

0. First action on session start (before running anything):
   `echo "$(date -Is) EXEC-START first-acquire" >> .claude/loop.log`
1. Fill Results here (table, per-speed verdicts, RQ-E6 verdict, estimate-vs-actual notes
   where they diverge; set Status line above to COMPLETE + verdict).
2. Append RESULTS row(s), QUESTIONS verdict (per-Part doc `docs/questions/part4-end-to-end.md`
   and `docs/results/part4-end-to-end.md`, not the root files), DECISIONS entry
   (`docs/decisions/part4-end-to-end.md`: motion-hold chosen over retry-only / relaxed
   prior — rationale is in "Rejected alternatives" above).
3. Commit everything on `experiment/first-acquire` with a one-line
   `E6 first-acquire: <verdict>` message. `git status` must be clean after.
4. `git checkout main && git merge --no-ff experiment/first-acquire`. Any conflict -> STOP:
   abort the merge, note it in the README Status line, do NOT run step 5.
5. Launch the next cycle — ONLY via the guard script, never by hand:
   ```bash
   bash .claude/skills/next-experiment/relaunch.sh
   ```
   If it prints `REFUSED: <reason>`, copy the reason into the README Status line and
   STOP — do not retry, do not spawn a terminal any other way.

Step 5 runs ONLY if 1-4 all succeeded. FAIL verdicts still loop; broken process does not.
