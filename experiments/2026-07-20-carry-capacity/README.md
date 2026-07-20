# P5.20 carry-capacity — does a bigger SAM2 recover the carry-owned select failures, and does P5.19's bar-exact YES replicate?

**Pre-registered:** 2026-07-20T10:05Z (Madrid wall clock). Design + patches by
Fable; Opus runs the matrix and fills Results only — do **NOT** re-patch code.
**Status:** PRE-REGISTERED, not yet run.
**Branch:** `experiment/carry-capacity` off `main` @ `4678f98` (P5.19 merge).
**Machines:** RTX 3090 workstation (SAM2 carry + orchestration, local repo) +
Jetson Orin Nano over `ssh jetson` (VLM discovery / ROI re-anchor / shadow
calls; llama.cpp q8_0 `phase3-terse100eos-1024`, booted per cell by the
harness). Jetson power: 15W + jetson_clocks (verify in R0; there is no MAXN on
this board). Arms must run **sequentially, never in parallel** — they contend
for the single Jetson VLM server.
**Env:** `.venv-ft` per `requirements-ft.lock.txt`, unchanged since P5.19.
One new artifact: the `facebook/sam2.1-hiera-small` checkpoint (HF hub
download, cached in R0 — a model file, not a package install).

## RQ-P5.20

Two pre-registered gates on one paired A/B over the frozen P5.18 scene set
(`../2026-07-20-n25-select/scenes_p518.json`, 26 gating scenes per leg +
car3:200 non-gating control; legs WSEL and strengthened SWAP, definitions
P5.18-verbatim):

- **Arm T** — the P5.19 harness verbatim (`rescue_p519.py` unmodified:
  aligned dedup + bounded grace), SAM2 carry = `facebook/sam2.1-hiera-tiny`.
  A fresh schedule re-roll of the exact P5.19 config = the replication
  control.
- **Arm S** — identical in every respect except the SAM2 checkpoint:
  `facebook/sam2.1-hiera-small`, equal stride (the same 6.15 Hz carry-budget
  emulation; the harness clock is driven by measured Jetson VLM latencies
  mapped onto the frame index — local carry compute never consumes clip time,
  see `discover_p516.discover`: `cur = fr = fs + round(lat*fps)` — so the
  checkpoint is the **single factor**).

**RQ-P5.20a (capacity):** does carry-model capacity recover the carry-drift
cells that own 8 of P5.19's 10 residual failures?
PASS iff **paired_delta >= +3**, where paired_delta = sum over the 52 gating
leg-cells valid in both arms of (S pass − T pass). MIN_SEP = +3 is the
smallest count above the observed schedule-noise band: between the P5.18 and
P5.19 runs (same scenes; patch effects machine-attributed per cell) exactly
**1** SWAP cell flipped on pure timing noise and the WSEL pass-map was
bit-identical, so ±2 is the honest noise band for a two-fresh-runs
comparison.

**RQ-P5.20b (replication):** does P5.19's bar-exact YES survive a schedule
re-roll? PASS iff arm T lands **WSEL >= 20/26 AND strengthened SWAP >=
20/26** (the P5.18/P5.19 bar, unchanged).

n = 26 gating cells per leg per arm (52 leg-cells per arm, 104 gating cells
total + 4 control cells). Budget target <= 1 h matrix wall (est. below), hard
cap 10 h.

## Context and rationale

### Audit of P5.19 (why the replication arm is mandatory)

P5.19 merged as YES [late-entry-rescued]: WSEL 22/26, SWAP 20/26 — **exactly
on the bar** — delta +3 over P5.18's SWAP 17, vs pre-registered MIN_SEP +2.
This audit found the +3 is softer than the record claims:

1. **Flip-table misattribution (new finding, raw-data level).** The P5.19
   README's per-cell flip table credits `DSC_SWAP_bike1_2250` to "aligned
   dedup + retry re-seed". The machine attribution in its `runs/verdict.json`
   says `"mechanism": "timing-noise"`, and the raw
   `runs/DSC_SWAP_bike1_2250/results.json` confirms the machine is right:
   distractor discovery `call_frame 2235, return_frame 2369, latency_s 4.47,
   outcome "accepted", aligned_iou_max 0.0622` — the call returned 121 frames
   *before* the prompt (2490), the dedup guard never fired (IoU 0.06 << 0.5),
   no grace in meta, `acquire_s 0.0`. Neither patch touched the cell; it
   flipped on a favourable Jetson-latency draw. So the **patch-attributable
   recovery is +2 — exactly at P5.19's pre-registered noise floor** — and the
   headline +3 contains one luck cell.
2. **Bar-exact + fragile mechanisms.** SWAP 20/26 clears by zero margin;
   grace in-sample precision is 2/4 (car18:150 0.367 s PASS, person10:450
   0.600 s PASS, bike1:450 0.433 s FAIL, control car3:200 0.5 s FAIL); the
   non-gating control **regressed** pass→fail via a wrong grace — a
   confident box on the wrong object, not an abstain.
3. **Proof-frame observations (Read-tool, this audit).**
   `proof/dedup_census.png`: 108 discovery calls over 54 cells — P5.18:
   106 accepted / 0 duplicate_reject / 2 in-flight; P5.19: 100 accepted /
   8 duplicate_reject / 4 in-flight / 4 graced / 0 grace-refused. Corroborates
   "misaligned guard fired 0x, aligned guard is alive".
   `proof/paired_flip.png`: WSEL columns are pass-map-identical across
   P5.18/P5.19 (same 4 fails: car7:460, car9:950, car9:1150, car3:1050); the
   SWAP flips are exactly car18:150 (G), person10:450 (G), bike1:2250 (no G —
   the luck cell) fail→pass, and control car3:200 pass→fail (G); bike1:450
   shows G but stays red. Honest rendering incl. the control regression.
   `proof/grace_deliver_car18_150.png`: green delivered box tight on the
   distractor at the grace frame (acquire_s 0.367), red target GT on the
   other vehicle, blue stale distractor GT overlapping green — a genuine
   grace save. `proof/discovery_headline.png`: P5.18's accepted "black SUV"
   discovery box sitting ON the target next to P5.19's handling of the same
   call — the bug the patch fixed, corroborated.
4. **Verdict on the audit:** P5.19's mechanisms are real (dedup alignment is
   a proven bug-fix; 2 grace saves are visually genuine) but the *bar-exact
   YES as a scene-set claim* is not established robust. It must replicate
   under a fresh schedule re-roll before anything is built on it. Rather
   than spend a cycle on a bare re-run, arm T of this A/B **is** that
   re-run, at zero extra cost.

### Why carry capacity is the one lever to probe

- P5.19's residual failures: 10 cells, **8 owned by carry drift/loss**, all
  in the car family (small, low-contrast sedans at altitude): car7:460
  (WSEL+SWAP), car9:950 (WSEL+SWAP), car9:1150 (WSEL+SWAP), car3:1050
  (WSEL+SWAP); plus bike1:450 SWAP (wrong grace) and wakeboard3:150 SWAP.
  That 8-cell block is the recovery ceiling for any carry-side lever — and
  it is untouched by every select-arc lever tried so far (delivery contract
  P5.14, dedup/grace P5.19, re-anchor P5.5/P5.15 which is net *negative*).
- P5.15 showed plain carry *survival* is not the problem (24/25 alive at
  24 s idle); the failures are box-quality-at-delivery — drifted or bloated
  masks on small targets. That is a mask-capacity signature, the thing a
  bigger image encoder is for.
- `sam2.1-hiera-small` (46 M params vs tiny's 38.9 M; both reported figures
  from the SAM2 model zoo) is the smallest capacity step in the same family
  — same API, same `StreamCarry` code path, checkpoint-string swap only.
- Not a dead lever: the dead-levers list kills EdgeTAM (a *different*
  tracker; E1 kept SAM2), not a SAM2 size variant; loop-focus explicitly
  names "tracker swaps" as live stack-level questions.

**Deployment caveat (pre-registered so a YES cannot be over-claimed):** equal
stride isolates capacity as the factor, but the deployed Jetson budget
(6.15 Hz co-resident, E1 TensorRT fp16) was measured for *tiny*. A YES on
RQ-P5.20a licenses only "the failure mode is capacity-bound"; deploying
hiera-small requires a follow-up E1-style TensorRT export + co-resident FPS
gate on the Jetson before any deployed-stack claim. That follow-up is NOT
part of this experiment.

### Rejected alternatives (recorded for DECISIONS)

1. **Replication-only P5.19 re-run** — strictly dominated: arm T is that
   re-run; arm S answers the capacity question for ~30 extra minutes.
2. **ROI-zoom carry** (run SAM2 on a crop around the track) — plausible but
   needs unvalidated coordinate/memory-bank engineering inside StreamCarry;
   too much new code for one cycle. Fallback lever if capacity comes back
   flat.
3. **Higher carry rate** (stride < 5) — violates the deployed 6.15 Hz
   co-resident budget; answers a question the thesis can't use.
4. **area_ratio abstain gate** (P5.15's health signal) — converts
   confident-wrong into honest-abstain but cannot flip FAIL→PASS on either
   leg's pass rule; wrong tool for a pass-rate question.
5. **hiera-base-plus / large** (80.8 M / 224.4 M) — no plausible Jetson
   co-residency; small is the largest defensible step.

## Code changes (written + committed by Fable at design time)

All three files live in this dir; **Opus does not modify them.**

- `capacity_p520.py` — the two-arm runner. Imports `rescue_p519` (which
  imports `discover_p516` — the entire P5.19 harness verbatim) and overrides
  exactly one thing: `stream_carry.MODEL`, read at call time by
  `discover_p516.run_matrix_scene`'s function-level import. Per-arm snapshot
  roots `runs/T/`, `runs/S/` with the P5.16/P5.19 resume rule (a cell whose
  `results.json` exists is skipped). Every cell is stamped
  `p520 = {arm, sam2_model, equal_stride}` the moment it finishes (the p519
  stamp lands on top and preserves it); the runner refuses to start an arm
  into a dir containing another arm's stamped cells (ARM MIX guard).
  Selfcheck S1–S5: arm-knob visibility via the exact import form the harness
  uses, stamping, byte-identical resume skip, ARM MIX refusal, restoration.
- `verdict_p520.py` — the **sole verdict authority** (rules in the next
  section, frozen in its docstring). Recomputes the committed P5.19
  reference counts and asserts == {WSEL: 22, SWAP: 20} (drift → refuse);
  enforces p519 + p520 markers per cell; enforces the mandatory visual-audit
  set via `visual_downgrades.json` (downgrade-only, refuses until covered);
  computes paired_delta on both-arms-valid cells only; writes
  `runs/verdict.json`. Reuses `classify`/`_metric` from `verdict_p519`
  (import, not copy). Selfcheck covers all branches, INFRA underflows,
  marker/ref-drift/audit refusals, downgrade demotion, carry attribution.
- `make_proof.py` — proof figures from `runs/*/results.json` +
  `runs/verdict.json`: `proof/ab_counts.png`, `proof/paired_grid_ts.png`,
  `proof/flip_evidence.png` (side-by-side T|S claim frames for up to 4
  flipped cells).

Selfcheck status at design time (2026-07-20, this machine, `.venv-ft`):
`rescue_p519 --selfcheck` OK (incl. upstream `discover_p516` suite),
`capacity_p520 --selfcheck` OK, `verdict_p520 --selfcheck` OK.

## Run matrix (Opus: run top to bottom from `/home/gara/jetson`)

**R0 — gates (~5 min).** All must pass before any GPU work:

```bash
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/rescue_p519.py --selfcheck
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/capacity_p520.py --selfcheck
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/verdict_p520.py --selfcheck
.venv-ft/bin/python -c "from sam2.sam2_video_predictor import SAM2VideoPredictor as P; P.from_pretrained('facebook/sam2.1-hiera-small'); print('hiera-small cached')"
ssh jetson "sudo nvpmodel -q && sudo jetson_clocks && echo jetson-ok"
```

Record the `nvpmodel -q` output (expect the 15W mode) in Results. If the
hiera-small download fails (network), retry once; still failing → stop,
Results = INFRA [checkpoint-unavailable].

**R1 — arm T (replication control, est. ~27 min):**

```bash
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/capacity_p520.py \
    --arm T --matrix experiments/2026-07-20-n25-select/scenes_p518.json
```

**R2 — arm S (capacity arm, est. ~28–35 min), only after R1 finishes:**

```bash
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/capacity_p520.py \
    --arm S --matrix experiments/2026-07-20-n25-select/scenes_p518.json
```

Both write per-cell snapshots `runs/<arm>/DSC_<LEG>_<clip>_<f0>/`
(results.json, deliver.png, discovery_*.png, grace_deliver.png when grace
fired, overlay.mp4). **Resume after any interruption = re-run the same
command**; completed cells are skipped. A cell that crashed mid-run (dir
exists, results.json missing or missing its p519/p520 stamps) → delete that
cell dir, re-run the arm command.

**R3 — verdict (it will REFUSE until the visual audit is done):**

```bash
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/verdict_p520.py
```

**R4 — mandatory visual audit loop.** The refusal message lists the required
`<arm>/<cid>` cells. For each: open its claim PNGs with the **Read tool**
(see next section), then write
`experiments/2026-07-20-carry-capacity/visual_downgrades.json`:
`{"audited": ["T/DSC_...", "S/DSC_...", ...], "downgrades": [{"cell":
"<arm>/<cid>", "seen": "<what you saw>"}]}` (downgrades may be empty;
audited may not). Re-run R3 until it verdicts. Never list a cell you did not
actually open.

**R5 — proof figures, then LOOK at them:**

```bash
.venv-ft/bin/python experiments/2026-07-20-carry-capacity/make_proof.py
```

Open all three `proof/*.png` with the Read tool; check `ab_counts.png`
numbers equal `runs/verdict.json` counts, `paired_grid_ts.png` has 27 rows ×
4 columns with black outlines exactly on the verdict's flip cells, and
`flip_evidence.png` rows show boxes on objects (not background). Any
mismatch → do not commit the figure, investigate.

## Visual verification (LOOK AT IT)

Every dumped PNG already passes `_frame_health` (asserts the frame is not
>99% one colour). What to look for, per file:

- `deliver.png` (every audited cell): green = delivered box drawn at the
  prompt frame, red = target GT, blue = hand distractor GT (SWAP cells).
  PASS looks like: WSEL — green tight on the *target* (green≈red); SWAP —
  green tight on the *distractor* (green≈blue, clearly off red). Failure
  looks like: green on background, green straddling both objects, green on
  the wrong object, or a grossly bloated box.
- `grace_deliver.png` (grace-fired cells; this is the claim frame there):
  green box at the grace frame `fr`; red = target GT at `fr`; blue =
  distractor GT annotated at the prompt (up to 2 s stale, labelled). PASS:
  green on the distractor. The known failure mode (P5.19 control): green
  confidently on the *target* or background.
- `discovery_target.png` / `discovery_distractor.png` (cells failing in the
  `discovery` bucket, and any flip you audit): green = VLM box at the call
  frame, caption in the banner. Failure: the "distractor" box sitting on
  the target (the P5.18 wrong-seed mode) or on background.
- S-vs-T flipped cells: open **both arms'** claim PNGs side by side — the
  flip is only real if the S frame shows a correct box where the T frame
  shows a wrong/absent one (or vice versa for regressions).

`verdict_p520.py` computes the exact required set (all failing gating cells
capped at 12/arm lowest-metric-first, 5 rank-sampled passes/arm, person20:1050
and car3:200 both legs both arms, both arms of every flip, every grace cell)
and refuses to verdict until `visual_downgrades.json` covers it. Downgrades
are demotion-only; nothing can be upgraded visually.

## Mechanical verdict rules (frozen; `verdict_p520.py` is the sole authority)

- Gate a (capacity): paired_delta >= +3 over the 52 paired gating leg-cells
  (both-arms-valid pairs only; each invalid cell still counts FAIL for its
  own arm's leg count).
- Gate b (replication): T WSEL >= 20/26 AND T SWAP >= 20/26.
- Branches (exhaustive):

| branch | condition | verdict |
|---|---|---|
| INFRA | any arm×leg valid < 25, or paired cells < 50/52 | INFRA [n-underflow / pair-underflow] |
| 1 | a AND b | **YES [capacity-lifts, p519-replicates]** |
| 2 | a AND NOT b | **YES [capacity-lifts, replication-failed]** — capacity is real; P5.19's bar-exact YES was luck-assisted |
| 3 | NOT a AND b | **NO [capacity-flat, p519-replicates]** — carry drift is not capacity-bound at this step; the select claim itself stands |
| 4 | NOT a AND NOT b | **NO [capacity-flat, replication-failed]** — the P5.18→P5.19 arc must be re-opened before any new lever |

  Sub-tag `[capacity-hurts]` appended to 3/4 when paired_delta <= −3.
- Missing/INVALID cell = FAIL for the count. Marker guards (p519 patch
  marker + p520 arm/model stamp) and the P5.19-reference assert
  ({WSEL: 22, SWAP: 20}) make the script refuse rather than mis-verdict.
- Non-gating diagnostics reported, never gating: carry-attribution of
  recovered cells (T-side failure bucket — if a >= +3 but recoveries are
  mostly `discovery`-bucket, the Results MUST say the lift is not
  carry-attributable), T-vs-P5.19 flip census (replication noise measure),
  per-arm grace/dedup census, control cells, weak-SWAP, per-arm wall time.
- Abort rules: Jetson unreachable / VLM boot failure → retry the arm command
  once (resume skips done cells); still failing → stop, Results = INFRA
  [jetson-down], never fake cells. ARM MIX refusal → fix `--arm`/`--out`,
  never delete the other arm's cells to silence it. If total matrix wall
  exceeds 10 h → stop and verdict on what exists (INFRA branches handle
  underflow). If a genuine harness bug blocks a cell, do NOT patch code:
  record the traceback here, mark the cell INVALID, and let the INFRA/count
  rules speak.

## Estimates (marked as estimates)

- Wall: arm T ~27 min (measured P5.19: 54 cells, mean 29.3 s, max 32 s);
  arm S ~28–35 min (same schedule cost + heavier checkpoint load/step);
  matrix total **~55–65 min**, inside the 1 h target; R0 ~5 min;
  audit + verdict + proof are agent time, not GPU time.
- Arm T (replication): WSEL 22 ± 1 (WSEL was pass-map-identical across two
  prior re-rolls); SWAP 19 ± 2 — genuinely uncertain, that is the point:
  P5.19's 20 was bar-exact with only +2 patch-attributable. P(gate b) ~ 0.5.
- Arm S vs T: if the car-family drift is capacity-bound, the ceiling is the
  8 carry-owned cells; realistic paired_delta +2..+5 (P ~ 0.4 of clearing
  +3). If drift is appearance/scale-bound rather than capacity-bound,
  0 ± 2. Regressions from the swap are possible (different masks re-roll
  SWAP schedules); the paired design charges them symmetrically.
- Most likely single outcome (honest guess, not a hope): branch 3 or 4 —
  capacity-flat, with the replication answer deciding which. Either is
  thesis content: it would close "just use a bigger tracker" with data.

## Results (TBD — Opus fills; every number carries its config)

Run date/time: TBD. Jetson `nvpmodel -q`: TBD. R0 gates: TBD.

| arm | SAM2 checkpoint | WSEL /26 | SWAP /26 | total /52 | valid WSEL/SWAP | wall (min) |
|---|---|---|---|---|---|---|
| T | sam2.1-hiera-tiny | TBD | TBD | TBD | TBD | TBD |
| S | sam2.1-hiera-small | TBD | TBD | TBD | TBD | TBD |

- paired_delta (S−T, both-valid pairs): TBD (min_sep +3) → **gate a: TBD**
- T vs bar 20/26 both legs → **gate b: TBD**
- **Branch: TBD — verdict: TBD**
- Recovered cells (cid, T-bucket, carry-attributed?): TBD
- Regressed cells: TBD
- T-vs-P5.19 flip census (replication noise): TBD
- Grace census (per arm: fired/refused, precision): TBD; control car3:200
  both arms: TBD
- Visual audit: N cells opened, downgrades: TBD
- Estimate-vs-actual divergences: TBD

## Deliverables (DoD 7)

`proof/ab_counts.png`, `proof/paired_grid_ts.png`, `proof/flip_evidence.png`
(from `make_proof.py`; commit + caption each here with what it shows and
which runs). If there are zero S-vs-T flips, `flip_evidence.png` is skipped
— commit the two figures plus one curated per-cell claim PNG (`git add -f`)
of the most informative residual failure, captioned.

## Executor definition of done

1. Results section above filled (incl. estimate-vs-actual); README status
   line updated to the verdict.
2. `git add experiments/2026-07-20-carry-capacity/runs/` (gitignore keeps
   only `results.json` files — verdict.json content is transcribed into
   Results, matching the P5.19 pattern), plus `visual_downgrades.json`,
   `proof/*.png`, and this README.
3. Ledger rows appended (per-Part docs, never the root): RESULTS row(s) and
   QUESTIONS entries for RQ-P5.20a/RQ-P5.20b in
   `docs/{results,questions}/part5-anticipatory.md`; DECISIONS entry
   (capacity probe chosen over ROI-zoom carry / rate increase / abstain
   gate; equal-stride deployment caveat) in
   `docs/decisions/part5-anticipatory.md`; SOURCES entry for
   `facebook/sam2.1-hiera-small`.
4. Do not merge; the loop driver reviews and merges.
