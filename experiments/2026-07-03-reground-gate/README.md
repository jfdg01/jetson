# E7 — reground-gate: motion-consistency gate on REGROUND acceptance

**Pre-registered:** 2026-07-03T10:28Z (design + patches by Fable; the executor runs the
matrix and fills Results only — do NOT re-patch code).
**Status:** COMPLETE 2026-07-03T11:58Z. RQ-E7 = NO (gate defeated by drive-through
co-location; regression legs held). Ledgers appended, merged to main, next cycle relaunched.
**Branch:** `experiment/reground-gate`. **Part:** IV (end-to-end workflow refinement).

## Research question

**RQ-E7:** Does a motion-consistency gate on REGROUND acceptance — accept a
size-prior-passing VLM box only if it sits on the ego-motion-compensated frame-diff blob
(the scene's mover) — convert E3-S2's decoy wrong-lock (3/3 at 0.25 m/s) into a relock on
the true car, **without** regressing plain-occlusion relock at 0.5 and 1.0 m/s?

Thresholds are in "Verdict rules" below; the RQ is falsifiable per-run with no judgment
calls.

## Context & rationale (audit summary)

- **The open failure:** E3-S2 (`experiments/2026-07-02-twin-distractor/`) planted a parked,
  pixel-identical decoy 2 m past the bridge north edge, same lane. REGROUND wrong-locked the
  decoy **3/3** — the size prior is identity-blind, and the decoy is the only size-plausible
  car visible while the true car is under the bridge. E4/E5/E6 fixed loss detection, blind
  pursuit, and first-acquire; reground *acceptance* is the last unguarded phase.
- **Why now:** E6 closed first-acquire (follow ceiling >= 1.0 m/s, 1.5 also 3/3). The
  north-star workflow ("follow that white car") cannot survive a second white car in frame
  until reground acceptance is identity-aware. This is the highest-leverage open thread.
- **Rejected alternative 1 — CLIP appearance gate** (the "E3b" placeholder named in the E3
  README): the SITL decoy is rendered with the *identical* polygon and color by
  construction, so an appearance embedding cannot separate decoy from target even in
  principle. Rejected on validity, not cost.
- **Rejected alternative 2 — DR-position radius gate** (accept only boxes near the
  dead-reckoned target position): needs a pixel-to-world drift calibration and a radius
  tuned to DR error growth, and E5 showed DR position error compounds during long blind
  phases. More machinery, weaker guarantee. Revisit only if a *moving* same-appearance
  distractor scenario ever matters.
- **Chosen lever — motion consistency:** the true car is the scene's mover; the decoy is
  parked. `motion_blob()` (ego-motion-compensated frame diff) is already committed and
  validated by E6 at all tested speeds. This extends motion consistency to the third and
  last phase: loss gating (E4), acquire hold (E6), reground acceptance (E7).
- **Known limit (record plainly, do not fix here):** a *moving* same-appearance distractor
  defeats this gate too — both cars are movers. That scenario is out of scope for E7.
- **E6 audit note carried forward:** the deterministic stack made E6's three mh-1.0 runs
  byte-identical (n=3 was effectively n=1). The decoy legs here vary through
  wall-clock-dependent VLM submit timing (as E6's 1.5 legs did), but if the three mg-decoy
  results.json files are byte-identical, record that fact in Results — it weakens n=3
  claims and is thesis content.

## Code changes (already committed on `experiment/reground-gate` — executor: do NOT edit)

All in `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`:

1. `reground_motion_ok(box, cur_bgr, base_bgr, M, pad=60.0)` — module function: compute
   `motion_blob(cur, base, M)`; blob None -> reject; else map the box center (base-frame
   pixels — the VLM drew it on the submit frame) through M and accept iff it lands within
   the blob bbox + 60 px pad. Pad rationale: base frame is the `acq_buf` entry nearest the
   submit time (buffer steps 0.5 s -> <= 0.25 s slack -> <= 0.6 m ~= 39 px pose drift at
   the 2.5 m/s cap), decoy offset is >= 2 m ~= 126 px at F/alt ~63 px/m.
2. `AcquireCarrySM`: optional `reground_gate` ctor arg, consulted ONLY on REGROUND resolves
   (first ACQUIRE has no prior mover to confirm against); gate reject -> `box = None`
   (keep drawing), counted in `n_gate_rejected`. `acquire_log` entries gain a 4th field
   `reason` in `{"", "size", "motion"}`.
3. `run_trial(..., reground_gate="none")` + closure wiring `acq_buf`/`_ground_affine`/live
   pose into the gate; metric `n_reground_gate_rejects`; twin metric `relock_on` — per
   relock, whether the first boxed twin frame is closer to `"true"` or `"distractor"`
   (aligned index-for-index with `relock_walls_s`).
4. CLI `--reground-gate {none,motion}` (default none -> all prior behavior byte-identical);
   recorded in the manifest cfg.
5. Selfcheck: prior asserts updated to the 4-field log; new scripted SM run proving the
   gate is consulted only on REGROUND resolves (reject-then-accept timeline); rendered
   accept/reject/no-mover checks for `reground_motion_ok` on the E6 frame pair.

Selfcheck run 2026-07-03: `selfcheck PASS ... + E7 reground gate`.

## Rig & versions

Same rig as E2–E6 (see `experiments/2026-07-03-first-acquire/README.md` for full detail):
host 3090 runs SITL + SAM2 carry at image-size 1024; the script boots the Jetson q8_0
llama-server over ssh itself — do **NOT** pass `--remote-carry`. Jetson power mode is
irrelevant to the verdict (VLM latency is absorbed by the acquire loop) but runs at the
deployed MAXN config. Trials are 75 s; E6 measured ~2.5 min wall per trial including
boot/teardown. Deterministic greedy VLM -> per-frame answers deterministic.

Camera geometry: 640x480, FOCAL_PX ~= 554, alt 8.8 m -> ~63 px/m. Decoy: parked 2 m past
the bridge north edge, same lane (`--twin decoy`, unchanged from E3).

## Run matrix

One command from the repo root (venv `.venv-ft` per repo rules):

```bash
bash experiments/2026-07-03-reground-gate/run_e7.sh 2>&1 | tee experiments/2026-07-03-reground-gate/raw/matrix.log
```

(`mkdir -p experiments/2026-07-03-reground-gate/raw` first if missing.)

All seven trials run with the deployed levers `--loss-gate motion --dr pursuit
--acquire-hold motion`; the script snapshots each run to `runs/<label>/` immediately
(results.json + trial.csv + trial.mp4) because phase3_sitl clobbers its outputs per run.

| label | speed | twin | reground-gate | purpose |
|---|---|---|---|---|
| ctl-decoy | 0.25 | decoy | none | attribution control: reproduce E3-S2 wrong-lock under current levers |
| mg-decoy-a/b/c | 0.25 | decoy | motion | the treatment, n=3 |
| mg-reg-0.5 | 0.5 | — | motion | regression leg (in RQ) |
| mg-reg-1.0 | 1.0 | — | motion | regression leg (in RQ) |
| mg-reg-1.5 | 1.5 | — | motion | stretch speed: reported, NOT in the RQ verdict |

## Verdict rules (mechanical — do not deliberate)

Read each run's snapshot `runs/<label>/results.json` -> `trial` object.

- **Per decoy run PASS** iff ALL of:
  - `twin.relock_on[0] == "true"` (first relock landed on the true car; `relock_on` empty
    or `[0] != "true"` -> FAIL),
  - `twin.final_d_true_m <= 2.0`,
  - `in_fov_frac >= 0.90`,
  - `recovered_after_occlusion == true`.
- **Regression leg PASS** iff `in_fov_frac >= 0.90` AND `recovered_after_occlusion == true`
  (the E6 gate, unchanged).
- **RQ-E7 = YES** iff mg-decoy-a, -b, -c are ALL PASS **and** mg-reg-0.5 and mg-reg-1.0
  are BOTH PASS. Anything else -> **RQ-E7 = NO** (record which legs failed).
- **Control leg:** ctl-decoy is expected to wrong-lock (`twin.closest_at_end ==
  "distractor"`). If it instead follows the true car, the RQ verdict stands as computed
  above but add one line to Results: "attribution confounded — control did not reproduce
  E3-S2 under current levers".
- **Distinct failure mode to record (not a process failure):** gate correctly rejects the
  decoy but the greedy VLM keeps boxing it -> never relocks. Signature: `relock_walls_s`
  empty or first relock very late, many `"motion"` reasons in `acquire_log`,
  `n_reground_gate_rejects` high. Record it plainly as a FAIL with this mechanism named —
  it is thesis content (the gate needs a search behavior, not just a filter).
- **Abort criteria:** a run hangs > 15 min or crashes -> kill it, snapshot whatever exists,
  mark that run INVALID in Results, continue the matrix. Two INVALID runs of the same label
  type -> stop the matrix, record what happened in Status, and do NOT relaunch (process
  failure).
- Byte-identical mg-decoy results (see audit note) -> add the fact to Results; the verdict
  still counts them per the rules above.

## Estimates (all are estimates)

- Runtime: ~20–25 min for 7 trials (E6 measured ~2.5 min/trial + one-time Jetson boot).
- ctl-decoy reproduces the wrong-lock: ~80% (E3-S2 was 3/3, but under older levers).
- mg-decoy 0/3 wrong-lock: ~75%; all three full-PASS: ~60% (risks: VLM decoy-fixation ->
  never-relock mode above; a relock attempt resolving exactly during the true car's
  drive-through past the parked decoy could pass the gate on the wrong car).
- Regression legs both PASS: ~85% (gate only adds rejects; risk is delayed relock pushing
  in_fov below 0.90 at 1.0).

## Results

Ran 2026-07-03T11:58Z, 7/7 trials completed clean (exit 0, none INVALID). Log:
`raw/matrix.log`; snapshots in `runs/<label>/`.

| label | speed | gate | relock_on[0] | final_d_true_m | final_d_dist_m | in_fov_frac | recovered | relock_walls_s | n_gate_rejects | leg verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| ctl-decoy | 0.25 | none | distractor | 7.91 | 1.93 | 0.903 | true | [23.38, 2.32] | 0 | CONTROL (wrong-lock reproduced) |
| mg-decoy-a | 0.25 | motion | distractor | 4.32 | 1.68 | 1.000 | true | [36.91] | 8 | FAIL |
| mg-decoy-b | 0.25 | motion | distractor | 4.05 | 1.94 | 1.000 | true | [37.10] | 7 | FAIL |
| mg-decoy-c | 0.25 | motion | distractor | 4.07 | 1.93 | 1.000 | true | [37.12] | 6 | FAIL |
| mg-reg-0.5 | 0.5 | motion | — | — | — | 1.000 | true | [9.32] | 0 | PASS |
| mg-reg-1.0 | 1.0 | motion | — | — | — | 1.000 | true | [6.92] | 0 | PASS |
| mg-reg-1.5 | 1.5 | motion | — | — | — | 1.000 | true | [6.78] | 0 | PASS |

- Control reproduced E3-S2: `ctl-decoy.closest_at_end == "distractor"` -> attribution
  clean, no confound.
- mg-decoy runs are **not** byte-identical (md5 dd4dcf1 / 3e7cdb2 / ab5eaa4; rejects 8/7/6,
  relock 36.91/37.10/37.12 s) — the wall-clock VLM submit timing varied as expected, so
  n=3 is a real n=3 here, unlike E6's mh-1.0.
- **Failure mechanism (thesis content, not a process failure):** the gate fired hard — 6-8
  REGROUND rejects per decoy run (reason `motion` in `acquire_log`), vs 0 in the control —
  and delayed re-acquisition, but the relock still landed on the decoy 3/3
  (`relock_on[0] == "distractor"`, final lock on decoy: `final_d_true` 4.05-4.32 m > 2.0,
  `final_d_dist` ~1.7-1.9 m). This is **not** the never-relock mode (each run relocked, at
  ~37 s). The gate filters *standalone* parked-decoy boxes but does not prevent wrong-lock:
  the true car drives past the parked decoy, transiently co-locating the decoy with the
  ego-compensated mover blob, so a decoy box eventually passes the gate. Motion consistency
  is **necessary but not sufficient** against a same-appearance parked distractor sitting on
  the target's own path — the "moving same-appearance distractor" limit named up front turns
  out to have a static-but-co-located cousin the gate also misses.

**RQ-E7 verdict: NO.** Gate did not convert the decoy wrong-lock into a true relock:
mg-decoy-a/b/c all FAIL (`relock_on[0] == "distractor"`, `final_d_true > 2.0` on all three).
Regression legs held cleanly (mg-reg-0.5, -1.0, -1.5 all PASS: `in_fov_frac == 1.0`,
`recovered == true`), so the gate does not regress plain-occlusion relock — it is simply
defeated by drive-through co-location on the same-lane parked decoy.

## Ledger rows to append (executor)

- `docs/results/part4-end-to-end.md`: one row per run from the Results table.
- `docs/questions/part4-end-to-end.md`: `RQ-E7` + one-line verdict.
- `docs/decisions/part4-end-to-end.md`: motion-consistency gate chosen over CLIP appearance
  gate (pixel-identical decoy defeats appearance by construction; motion reuses committed
  E6 machinery) and over a DR-position radius gate (needs drift calibration; weaker under
  compounding DR error). Known limit: a moving same-appearance distractor defeats the gate
  — out of scope, recorded plainly.

## Closeout checklist for the executor

0. First action on session start (before running anything):
   `echo "$(date -Is) EXEC-START reground-gate" >> .claude/loop.log`
1. Fill Results here.
2. Append RESULTS row(s), QUESTIONS verdict (per-Part doc, not root), DECISIONS entry if
   drafted here.
3. Commit everything on `experiment/reground-gate` with a one-line
   `E7 reground-gate: <verdict>` message. `git status` must be clean after.
4. `git checkout main && git merge --no-ff experiment/reground-gate`. Any conflict -> STOP:
   abort the merge, note it in the README Status line, do NOT run step 5.
5. Launch the next cycle — ONLY via the guard script, never by hand:
   ```bash
   python3 .claude/skills/next-experiment/relaunch.py
   ```
   If it prints `REFUSED: <reason>`, copy the reason into the README Status line and
   STOP — do not retry, do not spawn a terminal any other way.

Step 5 runs ONLY if 1–4 all succeeded. FAIL verdicts still loop; broken process does not.
