# E8 — reground-selfcorrect: does the E4 motion loss-gate recover from an E7 decoy wrong-lock, given time?

**Pre-registered:** 2026-07-03T11:00Z (design + patches by Fable; the executor runs the
matrix and fills Results only — do NOT re-patch code).
**Status:** COMPLETE (RQ-E8 NO). Ran 2026-07-03T11:20Z, 4/4 clean; see Results.
**Branch:** `experiment/reground-selfcorrect`. **Part:** IV (end-to-end workflow refinement).

## Research question

**RQ-E8:** E7's decoy legs ran 75 s and all ended wrong-locked on the parked decoy. Given
enough trial duration for the *already-deployed* E4 motion loss-gate (`--loss-gate motion`,
active in every E7 leg including the control) to complete a full stillness-detect (2.0 s) +
`LOSS_S` wait (3.0 s) + VLM reacquire cycle **after** that wrong-lock, does the combined
loop (E4 loss-gate + E7 reground motion-gate) self-correct onto the true car — **without**
a new mechanism, just clock time?

Falsifiable per leg, thresholds in "Verdict rules" below.

## Context & rationale (audit finding)

- **What the audit found:** re-reading E7's raw `results.json` (not just its Results
  table), all three decoy legs (mg-decoy-a/b/c) show the SAME shape: `acquire_log`'s final
  accepted entry (`reason == ""`) lands at **t = 69.31 / 69.46 / 69.47 s**, against a fixed
  `DURATION_S = 75.0` — i.e. **5.5-5.7 s of runway remained** after the wrong-lock that
  decided the verdict. `phase3_sitl.py`'s E4 motion loss-gate (`loss_gate == "motion" and
  sm.state == "CARRY"`, lines ~415-427) already demotes a CARRY box once its world-frame
  velocity (`hist_vel()`, via `box_to_world`) sits under 0.1 m/s for > 2.0 s continuously
  (`motion_stale[0] = True`) — exactly the situation a lock onto a *parked* decoy produces.
  Once demoted, `LOSS_S = 3.0` more seconds without a box forces the state machine back to
  REGROUND. **Minimum time for one correction cycle: ~5.0 s** (2.0 stillness + 3.0 loss),
  before a fresh VLM reacquire attempt (E7 measured ~2.3 s/attempt, and the *first*
  reacquisition in these same runs took **34.5 s and 8 rejects** — attempts 34.77 to 69.31
  s in mg-decoy-a). **75 s was not long enough for this already-active mechanism to even
  attempt, let alone complete, a second correction.** RQ-E7's "NO" is correctly attributed
  (the gate really was defeated by co-location, once) but the experiment never observed
  whether the system recovers afterward — that's a gap in E7, not a re-run of an invalid
  result, so this is a genuine follow-on question, not a validation re-run.
- **Why this is the highest-leverage next step:** it costs zero new code beyond a duration
  knob (no new gate, no new heuristic) and directly tests the E7 DECISIONS entry's own
  named next lever — "identity (impossible here) or a track-continuity/search behavior, not
  a filter" — against a mechanism (E4's stillness loss-gate) that already exists and was
  already running in every E7 leg. If it works, E7's "NO" gets a durability caveat, not a
  reversal, and the north-star gap narrows for free. If it doesn't (the loop cycles
  reject/reground and never lands on the true car, e.g. because the true car has driven out
  of frame/salience by the time the decoy is finally rejected), that is equally strong
  thesis content: geometry-only correction has a ceiling and search/identity is required
  after all.
- **Rejected alternative — design a new post-lock "track-continuity" confirmation gate**
  (a fresh ~2 s confirmation window applied specifically after REGROUND acceptance, reusing
  `motion_blob`/`_ground_affine`). Rejected for now: it would duplicate the E4 loss-gate's
  existing stillness check almost exactly (same primitives, same threshold shape), and we
  don't yet know whether the existing mechanism already does the job given time. Building a
  second copy of the same idea before checking if the first one just needed more clock time
  would be premature machinery. Revisit only if E8 shows the existing loss-gate reaches
  REGROUND again but *still* can't discriminate (e.g. repeatedly re-locks the same static
  decoy because it re-enters the motion blob some other way) — that would motivate a
  purpose-built confirmation window instead of reusing the generic stillness check.
- **Scope note:** this only extends *time*, not scenario. The "moving same-appearance
  distractor" limit named in E7 (both cars are movers, motion consistency can't separate
  them at all) is still explicitly out of scope here.

## Code changes (already committed on `experiment/reground-selfcorrect` — executor: do NOT edit)

All in `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`, one knob, no new
gates or heuristics:

1. `run_trial(..., duration_s: float = DURATION_S)` — new keyword, default unchanged
   (75.0, byte-identical behavior for every prior experiment's script). The trial loop
   (`while time.monotonic() - t_start < duration_s`) and `achieved_hz` now read the
   parameter instead of the module constant; `duration_s` is also written into the `trial`
   results dict for the record.
2. CLI `--duration-s` (default `DURATION_S`), threaded into `run_trial(...)` and into the
   manifest `cfg` dict (was previously hardcoded to the `DURATION_S` constant there).
3. No changes to `AcquireCarrySM`, `gate_box`, `reground_motion_ok`, or any gate logic —
   this experiment tests the existing E4+E7 machinery under more time, nothing else.

Compiles clean (`python3 -m py_compile`); `--selfcheck` path untouched (does not call
`run_trial`, unaffected by the new parameter's default).

## Rig & versions

Same rig as E2-E7 (see `experiments/2026-07-03-first-acquire/README.md` for full detail):
host 3090 runs SITL + SAM2 carry at image-size 1024; the script boots the Jetson q8_0
llama-server over ssh itself — do **NOT** pass `--remote-carry`. Jetson power mode
irrelevant to the verdict, runs at the deployed 15 W + jetson_clocks config (this board
has no MAXN_SUPER — only 15W/7W; see `docs/decisions/part2-rebuild.md`). Deterministic greedy VLM.

Camera geometry unchanged: 640x480, FOCAL_PX ~= 554, alt 8.8 m -> ~63 px/m. Decoy: parked
2 m past the bridge north edge, same lane (`--twin decoy`, unchanged from E3/E7). Trials
are **150 s** here (double E7's 75 s) — see Estimates for why.

## Run matrix

One command from the repo root (venv `.venv-ft` per repo rules):

```bash
bash experiments/2026-07-03-reground-selfcorrect/run_e8.sh 2>&1 | tee experiments/2026-07-03-reground-selfcorrect/raw/matrix.log
```

(`mkdir -p experiments/2026-07-03-reground-selfcorrect/raw` first if missing — it already
exists in this pre-registration but confirm before running.)

All four trials run with the deployed levers `--loss-gate motion --dr pursuit
--acquire-hold motion --duration-s 150`; the script snapshots each run to `runs/<label>/`
immediately (results.json + trial.csv + trial.mp4) because phase3_sitl clobbers its
outputs per run.

| label | speed | twin | reground-gate | duration | purpose |
|---|---|---|---|---|---|
| ctl-decoy-long | 0.25 | decoy | none | 150 s | does the E4 loss-gate alone (no E7 reground gate) also eventually self-correct? descriptive only, not in the RQ verdict |
| mg-decoy-a/b/c-long | 0.25 | decoy | motion | 150 s | the treatment, n=3 |

**Not rerun:** the plain-occlusion regression legs (mg-reg-0.5/1.0/1.5). They already
relocked at 6.8-9.3 s into a 75 s trial in E7 (PASS with wide margin) — a duration
extension appended after they already finished cannot change an outcome decided in the
first 10 s, so rerunning them would burn GPU time for a structurally foregone result. If
this reasoning is wrong (e.g. a code change here somehow altered early-trial behavior),
that would show up as a compile/selfcheck failure, not a silent regression — none occurred.

## Verdict rules (mechanical — do not deliberate)

Read each run's snapshot `runs/<label>/results.json` -> `trial` object.

- **Per gated decoy run (mg-decoy-a/b/c-long) PASS** iff ALL of:
  - `twin.relock_on` is non-empty AND its **last** entry `== "true"` (final identity, not
    first — self-correction may take more than one relock cycle),
  - `twin.closest_at_end == "true"`,
  - `twin.final_d_true_m <= 2.0`,
  - `in_fov_frac >= 0.90`.
- **RQ-E8 = YES** iff mg-decoy-a-long, -b-long, -c-long are ALL PASS.
- **RQ-E8 = NO** iff any of the three is not PASS. Record which condition failed per run:
  - `relock_on` last entry still `"distractor"` (or `closest_at_end == "distractor"`) after
    150 s -> genuine failure to self-correct even with time; name it plainly.
  - `n_regrounds == 1` for the whole 150 s (never even got kicked back to REGROUND) ->
    the E4 stillness check itself did not fire; report `hist_vel()`-adjacent evidence if
    visible in the CSV (target world-position column) rather than guessing why.
  - `relock_on` gained a 2nd+ entry but it's still `"distractor"` -> the loop cycles
    reject/reground without ever landing on the true car; this is the "geometry-only
    correction has a ceiling" outcome named in Context above — record it as that, not as a
    process failure.
- **Control leg (ctl-decoy-long, no reground-gate) is descriptive, not gated into the RQ
  verdict.** Report its `relock_on` (all entries), `n_regrounds`, and final twin metrics
  regardless of outcome. If it ALSO ends `closest_at_end == "true"`, say so explicitly in
  Results — it would mean the E4 loss-gate alone (not the E7 reground gate) does the
  correcting, which changes the attribution story for the DECISIONS entry (credit the
  loss-gate + reacquisition loop, not the motion reground-gate specifically) without
  changing the RQ-E8 YES/NO verdict on the gated legs.
- **Abort criteria:** a run hangs > 20 min (150 s trials + boot/teardown; generous margin
  over the ~5-6 min/trial estimate below) or crashes -> kill it, snapshot whatever exists,
  mark that run INVALID in Results, continue the matrix. Two INVALID runs -> stop the
  matrix, record what happened in Status, and do NOT relaunch (process failure).
- If the three mg-decoy-*-long `results.json` files are byte-identical to each other, record
  that fact in Results (same caveat E7 flagged for its own legs) — it weakens the n=3 claim
  but does not by itself change the verdict.

## Estimates (all are estimates)

- Runtime: ~6-7 min/trial (150 s trial + ~1 min boot/teardown overhead, doubling E7's
  ~2.5 min/trial estimate proportionally) x 4 trials = **~25-30 min** total.
- RQ-E8 = YES (all 3 gated legs self-correct): **~45%**. The 80 s of post-wrong-lock runway
  (150 - 69.3) comfortably covers the ~40 s worst-case single correction cycle (5 s
  detect+wait + up to 35 s reacquire, per mg-decoy-a's own first-acquisition timing) with
  margin for a second attempt if the first reground also lands wrong — but nothing in the
  gate stack guarantees the VLM eventually proposes the true car's box at all if it has
  driven far downstream/out of frame by then, which is the main risk.
- Per-leg PASS with exactly one extra relock cycle (`n_regrounds == 2`, second entry
  `"true"`): most likely path if it works, **~35%**.
- Never-regrounds-again (`n_regrounds` stays 1, stillness check never fires): **~15%** —
  would indicate `hist_vel()` on a parked-decoy box does not actually read as near-zero
  velocity (e.g. noise from the box's rear-edge measurement), worth flagging as a
  loss-gate bug if seen.
- ctl-decoy-long also self-corrects (loss-gate alone, no reground gate): **~30%** — if the
  reacquire VLM draw happens to land back on the true car by chance, `reground_gate=none`
  will accept it same as the decoy; this is a real possible outcome, not a bug.

## Results

Ran 2026-07-03T11:20Z, 4/4 trials completed clean (exit 0, 0 INVALID). Log:
`raw/matrix.log`; snapshots in `runs/<label>/`.

| label | speed | gate | n_regrounds | relock_on (all) | final_d_true_m | final_d_dist_m | closest_at_end | in_fov_frac | leg verdict |
|---|---|---|---|---|---|---|---|---|---|
| ctl-decoy-long | 0.25 | none | 5 | distractor, distractor, distractor, distractor | 26.67 | 1.96 | distractor | 0.4376 | descriptive |
| mg-decoy-a-long | 0.25 | motion | 2 | distractor | 26.51 | 1.93 | distractor | 0.4954 | FAIL |
| mg-decoy-b-long | 0.25 | motion | 2 | distractor | 26.61 | 1.93 | distractor | 0.4814 | FAIL |
| mg-decoy-c-long | 0.25 | motion | 2 | distractor | 26.51 | 1.93 | distractor | 0.4927 | FAIL |

**Narrative.** All three gated legs fail every PASS condition: last (only) `relock_on`
entry is `"distractor"`, `closest_at_end == "distractor"`, `final_d_true_m` ~= 26.5 m
(true car ended ~26.5 m downstream, far out of the ~2 m PASS band), and `in_fov_frac`
~= 0.49 (< 0.90). The three `results.json` are **not** byte-identical (distinct md5s;
distinct `relock_walls_s` 37.13 / 34.98 / 37.0 s and `id_switch_s` 4.37 / 4.53 / 4.48 s),
so the n=3 claim holds.

The failure is **not** the loss-gate-inert mode (`n_regrounds == 1`) flagged as a 15%
risk in Estimates — the E4 stillness loss-gate clearly fired: gated legs regrounded once
more after the wrong-lock (`n_regrounds == 2`) and the control regrounded four more times
(`n_regrounds == 5`). Nor is the E7 motion reground-gate inert: it actively rejected the
still-decoy proposals (`n_reground_gate_rejects` = 29 / 32 / 29 on the gated legs vs 0 on
the ungated control). Both mechanisms worked as designed.

The binding constraint is **upstream of both gates**: by the time the loss-gate demotes
the wrong-lock and forces a reground (~67-69.5 s, the second accepted acquire in each
gated leg), the true car has driven ~26.5 m downstream and mostly out of frame
(`in_fov_frac` ~= 0.49), so the only near-camera salient car the VLM can propose is the
parked decoy. Extra clock time cannot help because there is no true-car box left to
reacquire — the reground-gate then correctly rejects everything for the remaining ~80 s
but never sees a true-car proposal to accept. This is exactly the risk named in Context
("the true car has driven out of frame/salience by the time the decoy is finally
rejected") and is the **"geometry-only correction has a ceiling; search/identity is
required after all"** outcome, not a process/gate failure.

**Control attribution.** ctl-decoy-long (loss-gate on, no reground gate) also ends
`closest_at_end == "distractor"` (`final_d_true_m` 26.67 m): the E4 loss-gate **alone
does not self-correct** either — it re-locks the parked decoy on all four of its extra
regrounds (`relock_on` = distractor x4), because with no reground gate every VLM proposal
of the only salient (decoy) car is accepted. So the control does **not** shift credit to
"loss-gate alone corrects" — neither mechanism corrects, and the attribution story from
E7 is unchanged. Per the Ledger rules, this means **no new DECISIONS entry is required**
(E8 is a duration/measurement extension of E7's existing decision, and the control did
not change the loss-gate-vs-reground-gate attribution).

**RQ-E8 verdict: NO.** A duration extension to 150 s (2x E7's 75 s) does not let the
already-deployed E4 + E7 machinery self-correct off an E7 decoy wrong-lock. E7's "NO"
gains a durability caveat, not a reversal: the gates fire and reject as designed, but
geometry-only correction has a ceiling — once the true car has left the frame during the
wrong-lock, more clock time alone cannot reacquire it, confirming search/identity (E7's
own named next lever) is required.

## Ledger rows to append (executor)

- `docs/results/part4-end-to-end.md`: one row per run from the Results table.
- `docs/questions/part4-end-to-end.md`: `RQ-E8` + one-line verdict.
- `docs/decisions/part4-end-to-end.md`: only if the control leg outcome changes the
  attribution story (loss-gate-alone vs. reground-gate-specific credit) — otherwise this
  experiment doesn't need a new DECISIONS entry (it's a duration/measurement extension of
  E7's existing decision, not a new choice).

## Closeout checklist for the executor

0. First action on session start (before running anything):
   `echo "$(date -Is) EXEC-START reground-selfcorrect" >> .claude/loop.log`
1. Fill Results here.
2. Append RESULTS row(s), QUESTIONS verdict (per-Part doc, not root), DECISIONS entry if
   drafted here.
3. Commit everything on `experiment/reground-selfcorrect` with a one-line
   `E8 reground-selfcorrect: <verdict>` message. `git status` must be clean after.
4. `git checkout main && git merge --no-ff experiment/reground-selfcorrect`. Any conflict ->
   STOP: abort the merge, note it in the README Status line, do NOT run step 5.
5. Launch the next cycle — ONLY via the guard script, never by hand:
   ```bash
   python3 .claude/skills/next-experiment/relaunch.py
   ```
   If it prints `REFUSED: <reason>`, copy the reason into the README Status line and
   STOP — do not retry, do not spawn a terminal any other way.

Step 5 runs ONLY if 1-4 all succeeded. FAIL verdicts still loop; broken process does not.
