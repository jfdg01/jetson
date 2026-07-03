# E9 — retarget-switch: mid-follow NL target switch ("now follow the blue car")

**Pre-registered:** 2026-07-03T11:55Z (Madrid wall-clock). Design + patches by Fable;
the executor runs the matrix and fills Results only — **do NOT re-patch code**.
**Status:** PRE-REGISTERED, not yet run.

## Research question

**RQ-E9:** With all deployed levers on (Fix B, motion loss-gate, pursuit DR, motion
acquire-hold), can the two-tier loop execute a mid-follow natural-language target
switch — CARRY on "the white car", then at t=50 s command "the blue car" — locking
the new target within 15 s and following it to trial end, in 3/3 trials at 0.5 m/s,
without breaking the control leg?

This is the second half of the north star sentence ("follow that white car" /
"**switch to that blue truck**") and has never been exercised: every experiment so
far (E1–E8) holds one caption for the whole trial.

## Context and rationale (audit, 2026-07-03)

- **E8 audit — verdict valid.** Raw CSVs confirm both mechanisms fired and the
  target genuinely left the frame during wrong-lock; RQ-E8 NO is a real ceiling,
  not an artifact. The decoy wrong-lock corner now has two NOs (E7, E8): identity
  is impossible with a pixel-identical twin, and a search behavior is heavier
  machinery. Corner parked.
- **E5 audit — first-acquire lottery confirmed** (mh-1.5b/c logs: consecutive
  size-prior rejects of road-dash boxes while in_fov=1.0). Real, but the 1.5 m/s
  config is already a latency-quality issue on a PASSing leg — lower leverage.
- **Chosen instead:** the retarget path. It is a whole untested verb of the north
  star, it reuses the E3/E7/E8 twin metrics with only a sign flip in the verdict
  (post-switch, "distractor" IS the commanded target), and the state-machine change
  is small (swap the acquire closure, drop the carry, reuse the entire not-CARRY
  acquire path).
- **Rejected alternatives:** (a) 1.5 m/s first-acquire relock-latency fix — quality
  improvement on an already-PASS config; (b) wrong-lock search behavior — third run
  at an adversarial corner that two experiments say needs identity, which the
  synthetic twin cannot provide. Both recorded here as the DECISIONS seed.

## Design

- **Escort twin (new `--twin escort`):** a BLUE car (BGR 230,90,40), 2.5 m behind
  the white rover, +3 m east, same velocity. Co-moving, so it sits at a fixed
  offset inside the ~8.7 m x 11.6 m footprint whichever car the copter centers on.
  Color makes it NL-referable — the E3 identical-twin identity problem does not
  apply by construction.
- **Retarget (`--retarget-t 50`):** at the first CARRY tick at/after t=50 the SM
  swaps its submit closure to caption "the blue car", cancels any stale pending
  draw, drops the carry, and enters state RETARGET. The loop goes blind (pursuit
  DR owns it, moving at the old target's velocity = the escort's velocity, benign)
  until the new caption locks. RETARGET reuses the whole not-CARRY acquire path
  (size prior validates, `relock_walls` records the switch wall) but the E7
  reground motion gate is **not** consulted — that gate is a claim of continuity
  with the OLD target.
- **Why t=50:** bridge occlusion is t in [30,35]; E4 measured ~9.3 s relock at
  0.5 m/s, so the white car is re-locked by ~44 s — the switch fires from steady
  CARRY, and 75-50 = 25 s remain to demonstrate stable follow of the new target.
- **Known quirk (accepted):** an already-running VLM draw cannot be cancelled
  (max_workers=1); the new-caption submit just queues ~2.3 s behind. Bounded,
  visible in the switch wall.
- **Precondition gate (color smoke):** greedy decoding is deterministic per frame,
  so the smoke renders 10 distinct poses and does 1 draw per caption per pose.
  If the VLM cannot color-discriminate on these synthetic frames, the SITL legs
  are meaningless — gate them.

## Code changes (already committed on `experiment/retarget-switch` — executor: do NOT edit)

| File | Change |
|---|---|
| `experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py` | `render()` gains `distractor_color` (default keeps E3/E7/E8 byte-identical); selfcheck renders + asserts the blue escort |
| `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` | `AcquireCarrySM.retarget()`, RETARGET state, caption threading through `submit`/`_acquire`, `--twin escort`, `--retarget-t`, `m["retarget"]` metrics, selfcheck E9 scenario |
| `experiments/2026-07-03-retarget-switch/e9_color_smoke.py` | precondition smoke (10 poses x 2 captions) |
| `experiments/2026-07-03-retarget-switch/run_e9.py` | full matrix runner with per-leg snapshots |

Both selfchecks PASS on 2026-07-03T11:50Z:
`.venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py` and
`... phase3_sitl.py --selfcheck`.

## Run matrix

Rig: host 3090 (SAM2 carry + SITL) + Jetson Orin Nano over `ssh jetson`
(llama-server Qwen2-VL-2B Q8_0, booted by the scripts; power mode as-is from E8 =
MAXN_SUPER + jetson_clocks). One command runs everything, smoke first, snapshots
per leg into `runs/<label>/`:

```bash
cd /home/gara/jetson
.venv-ft/bin/python experiments/2026-07-03-retarget-switch/run_e9.py 2>&1 | tee experiments/2026-07-03-retarget-switch/raw/run_e9.log
```

| Label | Command core (runner adds it) | Purpose |
|---|---|---|
| `color-smoke` | `e9_color_smoke.py` | precondition: VLM color discrimination |
| `ctl` | `--speed 0.5 --twin escort --loss-gate motion --dr pursuit --acquire-hold motion` | escort present, NO retarget — does the blue car alone break follow? |
| `rt-a/b/c` | ctl flags + `--retarget-t 50` | the switch, n=3 |

Gotchas: phase3_sitl clobbers `raw/phase3a-sitl/trial-0.5ms.{csv,mp4}` and
`runs/phase3a-sitl/results.json` every run — the runner snapshots immediately after
each leg (E2–E8 gotcha, already handled; do not reorder legs manually).
`--reground-gate` stays `none` (E7 verdict: not shipped).

## Verdict rules (mechanical — executor does not deliberate)

All fields below are in the leg's snapshotted `results.json` under `trial`.

- **Smoke:** PASS iff `hits_of_10` >= 7 for BOTH captions. If either < 7, the
  runner prints `PRECONDITION-FAIL` and skips the legs; verdict = **RQ-E9
  PRECONDITION-FAIL** (the deployed VLM cannot color-discriminate on the synthetic
  frames); fill Results with the smoke numbers only and close out normally —
  a negative result is content.
- **`ctl` PASS** iff `in_fov_frac >= 0.90` AND `twin.closest_at_end == "true"`.
- **`rt-*` leg PASS** iff ALL of:
  1. `retarget.switch_walls_s` non-empty AND its first entry <= 15.0
  2. last entry of `retarget.switch_on` == `"distractor"`
  3. `twin.closest_at_end == "distractor"`
  4. `twin.final_d_dist_m <= 2.0`
  5. `retarget.frac_box_closer_dist_post >= 0.80`
  6. `retarget.dist_in_fov_frac_post >= 0.90`
  7. `in_fov_frac >= 0.90` (whole-trial; the escort stays near-center post-switch
     so the white car remains in frame too)
- **Ignore `twin.id_switch_s` on rt legs** — post-switch, sitting "closer to the
  distractor" is commanded behavior; the metric is only meaningful pre-switch and
  on `ctl`.
- **RQ-E9 = YES** iff `ctl` PASS AND `rt-a`, `rt-b`, `rt-c` all PASS. Any other
  combination = NO; record which criterion failed per leg in Results.
- **Abort criteria:** a leg hangs > 20 min wall — kill it, snapshot whatever
  exists, mark the leg INVALID, continue. 2 INVALID legs — stop the matrix, verdict
  INVALID-RUN, note it in Status. Missing results.json after a leg — same INVALID
  handling.

## Estimates (estimates, not measurements)

- Smoke: ~5 min (server boot ~2–3 min + 20 draws x ~2.3 s).
- Each SITL leg: ~4 min (SITL boot + 75 s trial + teardown); total ~20–25 min.
- Switch wall: ~2.5–5 s expected (one to two VLM draws; first draw may return the
  white car under the new caption — size prior accepts it, in which case
  `switch_on` catches the wrong lock — that is exactly what criterion 2 tests).
- Smoke: expect white >= 9/10; blue is the open question (training distribution is
  real drone imagery; "blue" on a synthetic top-down car may miss) — if blue
  < 7/10, PRECONDITION-FAIL is the honest outcome and kills the SITL matrix cheaply.
- RQ-E9 YES probability: contingent on smoke; given smoke PASS, moderately likely —
  the switch mechanically reuses the relock path that already works at 0.5 m/s.

## Results (TBD — executor fills)

Smoke (`runs/color-smoke/results.json`):

| Caption | hits / 10 | verdict |
|---|---|---|
| the white car | TBD | TBD |
| the blue car | TBD | TBD |

Legs:

| Leg | in_fov_frac | switch_wall_s (first) | switch_on (last) | closest_at_end | final_d_dist_m | frac_box_closer_dist_post | dist_in_fov_frac_post | PASS? |
|---|---|---|---|---|---|---|---|---|
| ctl | TBD | — | — | TBD | — | — | — | TBD |
| rt-a | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| rt-b | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| rt-c | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

**RQ-E9 verdict:** TBD

Estimate-vs-actual (fill where they diverge): TBD

## Closeout checklist (executor works from this README alone)

0. First action on session start (before running anything):
   `echo "$(date -Is) EXEC-START retarget-switch" >> .claude/loop.log`
1. Run the matrix (one command, above). Fill the Results tables here, set Status
   to COMPLETE + verdict, add the finish timestamp (Madrid wall-clock
   `YYYY-MM-DDThh:mmZ`).
2. Append the ledger rows:
   - `docs/results/part4-end-to-end.md`: one row per leg + the smoke row, each
     with config (0.5 m/s, escort, levers, retarget-t 50, Q8_0, MAXN_SUPER).
   - `docs/questions/part4-end-to-end.md`: `RQ-E9` + one-line verdict (per-Part
     doc, NOT the root QUESTIONS.md).
   - `docs/decisions/part4-end-to-end.md`: the E9 decision (retarget over
     1.5 m/s-latency and search-behavior alternatives — rationale is in Context
     above; copy it, don't re-derive).
3. Commit everything on `experiment/retarget-switch` with message
   `E9 retarget-switch: <verdict>`. `git status` must be clean after.
4. Do NOT merge to main. Do NOT relaunch anything. Return a summary to the parent
   session: verdict, per-leg PASS/FAIL with the failing criterion numbers, smoke
   hits, any INVALID legs, and the commit hash. The parent reviews and merges.
