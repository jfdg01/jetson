# P5.19 — late-entry-rescue: aligned discovery dedup + bounded grace delivery at n=26

**Pre-registered:** 2026-07-20T05:40Z (Madrid wall clock). Design + patches by Fable; Opus runs
the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE 2026-07-20T06:20Z — **branch 1, YES [late-entry-rescued]**
(WSEL 22/26, strengthened SWAP 20/26 vs bar 20/26, baseline 17, delta +3).
**Branch:** `experiment/late-entry-rescue`.
**Rig:** RTX 3090 workstation (`.venv-ft`: python 3.12.10, torch 2.6.0+cu124, transformers
4.57.6) + Jetson Orin Nano 8 GB over `ssh jetson` (llama.cpp q8_0, `NV Power Mode: 15W` mode 0 +
`jetson_clocks` — record `nvpmodel -q` output in Results). VLM =
`phase3-terse100eos-1024-q8_0.gguf` + `mmproj-phase3-terse100eos-1024-f16.gguf`, MAX_SIDE 1024.
Carry = SAM2 `facebook/sam2.1-hiera-tiny` bf16. Data = UAV123 @ 1280x720, 30 fps
(`experiments/2026-07-03-real-video-replay/data/UAV123`). Identical to the P5.18 rig — the
paired comparison requires it.

## RQ-P5.19

**Does fixing the frame-misaligned discovery distinctness guard (dedup at the frame the VLM
saw), plus a bounded grace delivery for the in-flight discovery call (acquire_s <= 2.0 s),
lift strengthened SWAP to the pre-registered bar at n=26 on the frozen P5.18 scene set —
without regressing WSEL?**

P5.18 (NO [SWAP-bound]: WSEL 22/26, strengthened SWAP 17/26 vs bar 20/26) named late-entry
discovery wrong-seeding as failure mechanism (a). This cycle's audit found its root cause is a
**bug, not a model limitation**: the P5.16 distinctness guard compares frame-misaligned boxes
and therefore never fired once in the whole P5.18 matrix (see audit trail). This experiment
patches exactly that mechanism and re-runs the identical matrix, paired cell-for-cell against
the committed P5.18 baseline.

**Pre-registered thresholds (counts of real n, frozen in `verdict_p519.py`):**

- **Scene set:** `../2026-07-20-n25-select/scenes_p518.json` VERBATIM (referenced, not copied):
  26 gating scenes per leg + car3:200 control (non-gating). n = 26 per leg.
- **Bar = 20 of 26 per leg** (unchanged from P5.18 — the bar SWAP missed).
- **Baseline (frozen):** P5.18 committed runs recompute to WSEL 22 / SWAP 17; `verdict_p519.py`
  re-derives this from `../2026-07-20-n25-select/runs/*/results.json` and REFUSES to verdict on
  drift.
- **MIN_SEP = +2 SWAP cells vs baseline 17** — the pre-registered minimum arm-to-arm difference
  that counts as a real rescue effect. Rationale: 2 of the failing SWAP cells are visually
  confirmed recoverable late-entry cells (see per-cell table); +1 is within single-cell timing
  noise (real Jetson latency variance re-rolls every schedule).
- **N_MIN = 25** valid cells per leg else INFRA; a missing/INVALID cell counts FAIL
  (conservative, no bar rescaling).
- Two arms: P5.19 patched run vs frozen P5.18 baseline. Same scenes, same harness
  (`discover_p516.py` imported, not copied), same rig; **single factor = the two coupled
  patches** (aligned dedup + grace, one mechanism: discovery integrity under late entry).

**Legs (unchanged from P5.6/P5.14/P5.16/P5.18):** WSEL = phrase names the idle-tracked target;
pass = correct selection + genuine lock + coverage >= 0.5 (`leg_pass_p56`). SWAP = phrase names
the distractor; strengthened pass = distractor selected, delivered box off the target GT
(IoU < 0.25) AND on the hand `distractor_gt_prompt` (IoU >= 0.25), no failure reason. For a
GRACED delivery the distractor-GT check uses the carry's **box_at_prompt** (SAM2 catch-up box
at the prompt frame) so the hand GT — annotated at the prompt frame — stays frame-aligned;
`deliver_iou` vs target GT is computed at the actual deliver frame `fr` (per-frame GT, no
staleness). Weak SWAP reported non-gating.

## Context and rationale (audit trail)

### P5.18 audit — what was verified

- `runs/verdict.json` cross-checked: branch 2, WSEL 22 / SWAP 17, 26/26 valid both legs, no
  visual downgrades. Recomputing pass counts from the 54 committed `results.json` reproduces
  22/17 exactly (this recomputation is now frozen into `verdict_p519.py` as the drift guard).
- **Proof PNGs opened with the Read tool** (LOOK AT IT): `proof/pass_matrix.png` — the car
  family carries the damage (car WSEL 6/10, SWAP 5/10; non-car WSEL 16/16); `proof/
  deliver_iou.png` — delivery quality is bimodal exactly as claimed: passes land 0.40–0.97,
  fails at 0.00/no-delivery, nothing near the 0.25 floors, so no threshold retune recovers
  anything.
- **The root-cause find (new, beyond the P5.18 README):** `discover()` in
  `experiments/2026-07-19-autodisc-select/discover_p516.py` HAS a distinctness guard
  (IOU_SAME = 0.5) — but it compares the VLM box from frame `fs` (what the VLM saw) against
  carried boxes already stepped through the ~4.6 s call window to `fr` (lines 111–124: the
  `idle_catchup_multi` step mutates `boxes` BEFORE the `iou(vbox, b)` check). Under motion an
  object no longer overlaps itself across ~138 frames, so the guard is structurally dead.
  Census over all 108 P5.18 discovery calls: **106 accepted, 0 duplicate_reject, 2
  in-flight** — the guard never fired once.
- Raw-log evidence, recomputed offline from the committed runs: car18:150 SWAP "the black SUV"
  box vs the carried target box IoU **0.854 at fs** but 0.087 at fr -> accepted (distractor
  track born ON the red Mustang); bike1:450 **0.727 at fs** vs 0.000 at fr -> accepted.
  `runs/DSC_SWAP_car18_150/discovery_distractor.png` opened: the "black SUV" box sits on the
  red Mustang — the only car in frame.
- **Regression census (why the fix is near-free):** across all 52 accepted distractor calls in
  P5.18, a proxy aligned guard (IoU >= 0.5 vs target GT at fs) fires on 8 — including 4
  FAILING SWAP cells (car18:150 0.854, bike1:450 0.727, car9:950 0.770, person10:450 0.836)
  and on NO currently-passing gating cell (closest: the car3:200 control at 0.387). Recovery
  ceiling SWAP 17 -> 21; regression floor ~0.
- **Schedule arithmetic (why the fix ALONE recovers zero cells):** idle window = ds (f0-150)
  to prompt (f0+240) = 390 frames = 13 s; at ~4.6 s per call only 2 completed slots fit. A
  post-reject retry returns ~13+ frames past the prompt, and P5.16 discards in-flight results
  (`in_flight_at_prompt`). So aligned dedup alone converts wrong-seed deliveries into honest
  `discovery-failed` — same FAIL count, honest buckets. The completing mechanism is **grace**:
  the harness is synchronous, the in-flight result is already in hand at the prompt; if the
  phrase names that candidate and the result is valid + aligned-distinct + lands within
  GRACE_MAX_S = 2.0 s of the prompt, deliver it at `fr` with acquire_s = (fr-prompt)/fps.
  Observed in-flight returns in P5.18 land 0.23–0.8 s late — ~6x under the 4.68 s cold
  re-ground this contract replaced.
- **Scene frames opened with the Read tool** (per-cell recovery grounding):
  - `car18/000269.jpg` (mid-window): red Mustang dominant, a tiny dark vehicle far up the road
    top-right — the retry either finds it (grace pass) or re-boxes the Mustang (aligned dup ->
    honest fail). Coin flip.
  - `bike1/000570.jpg`: ONLY the blue-shirt rider is in frame — "the cyclist in the yellow
    shirt" is genuinely absent; bike1:450 is UNRECOVERABLE and should convert to an honest
    discovery-failed (pre-registered as a bucket conversion, NOT a flip).
  - `bike1/002358.jpg`: BOTH riders in frame — and the P5.18 failure here is
    `discovery-failed:distractor` with the distractor call `in_flight_at_prompt`: the pure
    grace cell. Flip probability high.
  - `car9/001071.jpg`: two cars well separated — a fresh retry seed dodges the P5.18 drift
    (its delivered box landed 0.32 on the target, 0.00 on the distractor). Medium-high.
  - `person10/000571.jpg`: the second person is barely entering at the bottom edge; P5.18
    stacked two failures here (wrong seed AND "selected track lost during idle"). Medium-low.

### Per-cell failing-SWAP mechanism table (from the committed P5.18 runs)

| cell | P5.18 failure | patch's expected effect |
|---|---|---|
| bike1:2250 | discovery-failed: distractor in-flight at prompt, result discarded | grace delivers it — flip HIGH |
| car9:950 | wrong seed (0.770@fs) -> drift (iou_t 0.32, iou_d 0.00) | dedup rejects, retry re-seeds or graces — flip medium-high |
| car18:150 | wrong seed (0.854@fs): "black SUV" track born on the Mustang | dedup rejects; retry finds SUV (grace) or re-boxes Mustang (honest fail) — coin flip |
| person10:450 | wrong seed (0.836@fs) + carry lost during idle | dedup rejects; two stacked causes — flip medium-low |
| bike1:450 | wrong seed (0.727@fs); named distractor NOT in frame | converts to honest discovery-failed — bucket conversion, NO flip |
| car7:460, car9:1150, car3:1050, wakeboard3:150 | delivered box on NEITHER GT (iou_t 0.0–0.05, iou_d 0.0): carry drift, not late entry | out of this patch's reach — remain FAIL |

Expected (estimates, marked as such): SWAP 17 + 2..4 = **19–21, median ~20** — a genuine coin
flip at the bar, which is what makes this falsifiable rather than a demo. WSEL expected ~22
(the aligned guard cannot fire on the first discovery call, which is the target's — `boxes` is
empty then; and in P5.18 every first call was accepted, so the target path is untouched up to
timing noise). The 4 failing WSEL cells are carry-drift cells this patch does not address.

### The pick, and the rejected alternative (DECISIONS material)

- **Picked:** fix the named mechanism (a) of P5.18 — it is a provable harness bug with a
  visually confirmed recovery ceiling (+4) and near-zero regression risk, testable at n=26 in
  ~35 min on the frozen scene set with a clean paired design.
- **Rejected: car-family carry hardening** (mechanism (b), the bimodal drift cells — 8 of the
  13 leg-failures). Bigger family, but no clean lever identified: P5.15 already showed the
  deployed idle re-anchor is net-negative via same-class identity swap (net -2 clips), and the
  drift cells fail with the box on NEITHER GT, which is a SAM2-carry-quality problem the loop
  has no new lever for this cycle. Fixing discovery integrity first also cleans the
  measurement of (b): wrong-seed cells currently contaminate the drift bucket.
- **Rejected: dedup-only (no grace).** Predetermined NO by schedule arithmetic (2 slots per
  window, retry always in-flight): it converts wrong deliveries to honest fails and recovers
  zero cells. Bundling grace is what makes the RQ live; both patches are one mechanism
  (late-entry discovery integrity) so the A/B stays single-factor.
- Dead levers (loop-focus): nothing here re-proposes E19–E23 acquire speedups, VLM swap,
  re-anchor variants, or a bank v4. Grace is not an acquire speedup: it changes WHEN an
  already-made discovery is honored, not how fast the VLM answers.

## Code changes (already committed — Opus: do NOT edit these files)

All in `experiments/2026-07-20-late-entry-rescue/`, committed on this branch by Fable:

- **`rescue_p519.py`** — the harness. `discover_aligned` = `p516.discover` with the carried
  boxes SNAPSHOTTED at `fs` before the catch-up step and the dedup evaluated against the
  snapshot (PATCH 1); returns a 5th element `pending` describing the in-flight call.
  `run_leg_p519` = `p516.run_leg_p516` with the grace block (PATCH 2) replacing the bare
  `discovery-failed` return: fires iff the selected candidate has no carry AND the pending
  call is for it AND `_valid` AND aligned-distinct AND (fr-prompt)/fps <= GRACE_MAX_S = 2.0;
  seeds SAM2 at fs, catches up fs->prompt (box_at_prompt, used for the strengthened-SWAP
  check), prompt->fr, delivers at fr with acquire_s = (fr-prompt)/fps; every refusal is
  recorded (`meta.grace.refused` = no-pending | invalid | duplicate | cap | past-clip-end |
  carry-lost) followed by the honest fail. The matrix runner monkeypatches
  `p516.run_leg_p516 = run_leg_p519` and calls the UNCHANGED `p516.run_matrix_scene`
  (module-global resolution), then stamps each results.json with a `p519` marker and dumps
  `grace_deliver.png` for graced cells. Selfcheck S1–S6 includes an A/B bug repro (moving
  carry: original guard accepts the target's own box as a "distractor", aligned guard rejects
  at IoU 1.0) and a static-equivalence run of the ENTIRE upstream p516 selfcheck with the
  aligned guard patched in. **Run green at design time 2026-07-20T05:20Z.**
- **`verdict_p519.py`** — sole verdict authority. Recomputes + asserts the frozen baseline,
  builds the paired flip table with mechanism attribution (aligned-dedup / grace /
  grace-refused / timing-noise), enforces the visual audit set (P5.18 rules PLUS every flipped
  cell and every graced cell), applies the downgrade-only visual gate, writes
  `runs/verdict.json`. Refuses on: baseline drift, missing `p519` patch markers (guards a
  stale-harness rerun), incomplete audit. **Selfcheck green at design time 2026-07-20T05:30Z.**
- **`make_proof.py`** — 3 figures from runs/*/results.json: `proof/paired_flip.png` (per-scene
  4-column P5.18-vs-P5.19 grid, flips outlined, G = graced), `proof/dedup_census.png`
  (discovery-outcome bars per arm — the dead guard vs the live one), `proof/
  discovery_headline.png` (car18:150 wrong-seed frame vs what P5.19 did). Smoke-tested
  self-vs-self at design time (renders correctly, 0 flips, census 106/0/0/2).

Upstream files are IMPORTED, never modified: `discover_p516.py` and everything below it are
byte-identical to what P5.18 ran.

## Run matrix (Opus: copy-paste; run from repo root `/home/gara/jetson`)

R0 — gates (all must pass before R1; abort INFRA if not):

```bash
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/rescue_p519.py --selfcheck
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/verdict_p519.py --selfcheck
ssh jetson "sudo nvpmodel -q; sudo jetson_clocks"   # expect 'NV Power Mode: 15W' mode 0
```

R1 — the matrix (54 cells = 27 scenes x 2 legs, resumable: re-invoking skips any cell whose
results.json exists):

```bash
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/rescue_p519.py \
    --matrix /home/gara/jetson/experiments/2026-07-20-n25-select/scenes_p518.json \
    --out /home/gara/jetson/experiments/2026-07-20-late-entry-rescue/runs
```

R2 — verdict + proof (only after R1 completes and the visual audit below is written):

```bash
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/verdict_p519.py
.venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/make_proof.py
```

**Abort / INVALID rules (P5.18 verbatim):** if a cell hangs > 20 min wall, kill it, DELETE the
partial `runs/DSC_*/` dir, retry that cell ONCE via
`... --only <clip>:<f0> --legs <LEG> --out .../runs`; a second hang = that cell INVALID
(= FAIL for the count; leave no results.json). 3 consecutive SSH/backend boot failures = stop,
verdict INFRA. NEVER rerun a cell that already has a results.json. Do not edit thresholds,
constants, or any committed .py — if something looks wrong, record it in Results and let the
verdict script speak.

## Visual verification (LOOK AT IT — mandatory, gates the verdict)

`verdict_p519.py` computes the required audit set mechanically and REFUSES to verdict until
`visual_downgrades.json` (in this dir) lists every required cell as audited. Opus MUST open
each required cell's PNGs with the Read tool and write one line per cell in Results (what was
seen, not what the log says). Required set = every failing gating cell (cap 12, lowest metric
first) + 5 rank-sampled passing cells + person20:1050 both legs + **every flipped cell** +
**every graced cell**.

- Per cell open `runs/<cell>/deliver.png`; for graced cells ALSO `grace_deliver.png` (the
  claim frame at fr: green delivered box ON the phrase's object, red = target GT at fr, blue =
  hand distractor GT from the prompt frame, labelled stale); for discovery buckets and flips
  ALSO `discovery_distractor.png` / `discovery_target.png` (green VLM box on the NAMED object,
  not its same-class neighbor — P5.18's car18:150 failure mode).
- PASS looks like: SWAP — green box on the distractor object, clearly off the red target GT
  box. WSEL — green box on the target, overlapping the red GT. FAILURE looks like: green box
  on the wrong same-class object, on background, or a stale box the object has left.
- Cheap asserts already in the harness (`_frame_health`): a frame > 99% one colour aborts the
  cell. No PNG for a scored cell = that cell INVALID.
- Write `visual_downgrades.json` as
  `{"audited": ["DSC_SWAP_car18_150", ...], "downgrades": [{"cell": "...", "seen": "..."}]}` —
  a pass whose PNG contradicts the numbers gets DOWNGRADED (fail); nothing can be upgraded.

## Mechanical verdict (verdict_p519.py is the sole authority)

Branches (exhaustive):

- **INFRA [n-underflow]** — valid < 25 in either leg after the retry rule.
- **1 YES [late-entry-rescued]** — WSEL >= 20/26 AND strengthened SWAP >= 20/26. The P5.18 NO
  was harness-bound (the misaligned guard), not capability-bound; Part V select claim stands
  at real n with the fix.
- **2 NO [wsel-regressed]** — WSEL < 20/26. The patch broke the passing leg; revert and
  re-diagnose (grace/dedup touched a WSEL path it should not have).
- **3 NO [rescue-real-but-short]** — WSEL >= 20, SWAP <= 19, and SWAP-17 >= +2. The mechanism
  is real (recovered cells with rescue attribution) but late entry was not the binding share
  of the SWAP misses; the remaining fails' buckets (expected: carry-drift) name the next
  constraint.
- **4 NO [rescue-dead]** — WSEL >= 20, SWAP <= 19, SWAP-17 <= +1 (including regressions).
  Aligned dedup + grace do not move SWAP beyond noise: the retry re-boxes the same wrong
  object (referring-expression limit, P5.16's known loss mode) — the lever moves to
  discovery-time abstention, not scheduling.

Non-gating diagnostics recorded in verdict.json: paired flip table with mechanism attribution
(timing-noise flips reported separately from rescue flips), dedup-fire census, grace census
with acquire_s values, grace refusals, watch cells (DSC_SWAP_car9_950, DSC_SWAP_person10_450 —
the two proxy-guard cells whose recovery is least certain), weak-SWAP count, control cell.

## Estimates (marked as estimates)

- Matrix: 54 cells x ~30–32 s (P5.18 measured shape) + ~5–15 s extra on cells where the guard
  fires (a third VLM call) ~= **28–40 min**. Whole run incl. audit + ledgers < 1.5 h.
- Predicted branch: **1 (YES) at SWAP 20–21 / WSEL 22**, with branch 3 (SWAP 19) the live
  alternative — the design is a genuine coin flip at the bar.
- Grace fires on ~2–4 SWAP cells with acquire_s 0.23–0.8 s; dedup fires on ~4–8 cells;
  bike1:450 converts bucket (off-distractor -> discovery) without flipping.

## Results (filled 2026-07-20T06:20Z)

> **Statistical correction, 2026-07-21 (R-4) — the YES is downgraded to
> "indistinguishable".** `n_effective` 26 -> **13**: the 26 cells come from 13 distinct
> clips, and this run's own scene set is P5.18's. Precisely what changes: the p-value does
> **not** fall from significant to non-significant, because `b=3, c=0` is `p = 0.25` at the
> full n and was never significant. What deflation removes is the bar-exact margin — the
> pre-registered gate of 20/26 cells becomes **10/13 over a baseline 8/13**. Corrected
> statement: **we could not distinguish the arms; the gate cleared at a margin that does not
> survive the clip clustering.** Everything mechanical below stands and is what this run
> actually established: the guard fired 0/108 before and 8 after, grace delivers in
> 0.37-0.60 s against a 4.68 s cold re-ground, and P5.20 reproduced arm T cell-for-cell.
> Method: `thesis/01-metodo-estadistico.md`; registry: `thesis/claims.json`.

**VERDICT: branch 1 — YES [late-entry-rescued].** `verdict_p519.py` is the sole authority; it
re-derived the frozen P5.18 baseline (WSEL 22 / SWAP 17) without drift, confirmed all 54 cells
carry the `p519` patch marker, and enforced the 21-cell visual audit before speaking.

| leg | pass | bar | baseline (P5.18) | delta | verdict branch |
|---|---|---|---|---|---|
| WSEL | **22/26** | 20/26 | 22/26 | +0 | clears, no regression |
| SWAP (strengthened) | **20/26** | 20/26 | 17/26 | **+3** (MIN_SEP +2) | clears |

26/26 valid cells per leg, 0 INVALID, 0 retries. The result lands exactly on the bar — the
pre-registered "genuine coin flip" — and clears MIN_SEP by one cell.

### Per-cell flip table (3 recovered, 0 regressed among gating cells)

| cell | P5.18 | P5.19 | mechanism | pre-registered prediction |
|---|---|---|---|---|
| DSC_SWAP_car18_150 | FAIL (wrong seed, 0.854@fs) | **PASS** | grace, acquire_s 0.367 | "coin flip" — won |
| DSC_SWAP_person10_450 | FAIL (wrong seed + carry lost) | **PASS** | grace, acquire_s 0.600 | "flip medium-low" — won |
| DSC_SWAP_bike1_2250 | FAIL (in-flight discarded) | **PASS** | aligned dedup + retry re-seed | "flip HIGH" — won |
| DSC_SWAP_car9_950 | FAIL (wrong seed 0.770@fs) | FAIL (iou_t 0.317, bit-identical) | dedup did not fire | "flip medium-high" — lost |
| DSC_SWAP_bike1_450 | FAIL (wrong seed 0.727@fs) | FAIL (graced onto target, iou_t 0.865) | grace mis-fired | "bucket conversion, NO flip" — no flip, but see caveat |
| car7:460, car9:1150, car3:1050, wakeboard3:150 (SWAP) | FAIL | FAIL | carry drift, out of reach | correctly predicted to remain FAIL |

WSEL is untouched cell-for-cell (22 → 22, zero flips either direction), confirming the
pre-registered claim that the aligned guard cannot fire on the first (target) discovery call.

### Grace census — 4 fired, 0 refused, and only half of them were right

| cell | acquire_s | delivered on | pass |
|---|---|---|---|
| DSC_SWAP_car18_150 | 0.367 | the black SUV (correct) | **PASS** |
| DSC_SWAP_person10_450 | 0.600 | the white-shirted man (correct) | **PASS** |
| DSC_SWAP_bike1_450 | 0.433 | **the target** (iou_t 0.865) | FAIL |
| DSC_SWAP_car3_200 (control) | 0.500 | **the target** (iou_t 0.679) | FAIL (was PASS in P5.18) |

Grace delivers at **0.367–0.600 s**, ~8–12x faster than the 4.68 s cold re-ground it replaces —
the latency claim holds and beat the pre-registered 0.23–0.8 s estimate's midpoint.

**But grace precision in this matrix is 2/4.** When it is wrong it does not abstain: it delivers
a *tight, confident* box on the wrong object (0.865 and 0.679 IoU on the target). Neither wrong
grace inflated the pass count — both scored FAIL under the strengthened rule — so the verdict is
uncontaminated. The mechanism is nonetheless a **silent-failure risk in deployment**, where no GT
exists to catch it: the operator gets a crisp lock on the wrong vehicle.

### Dedup census — the dead guard is now live

Aligned dedup fired in **8 cells** (P5.18: 0 in 108 calls). Discovery outcomes across 54 cells:
accepted 106 → 100, duplicate-reject 0 → 8, in-flight 2 → 4, graced 0 → 4, grace-refused 0.
Recovery ceiling was +4; realised +3.

### The regression the pre-registration did not predict

`DSC_SWAP_car3_200` is the **non-gating control** and it went PASS → FAIL. Grace fired and put a
tight box on the target instead of the distractor. It does not touch the verdict (non-gating),
but it falsifies the pre-registered "regression floor ~0": grace has a real, if small, downside
tail. Recorded here rather than buried because a control cell regressing is exactly the kind of
result that is tempting to omit.

### The aligned dedup's own limitation (found by looking)

`bike1:450` was expected to convert to an honest `discovery-failed`. It did not: the guard let it
through and grace delivered onto the target. Reason: the guard compares the VLM box against the
**carried** boxes, not against GT. The pre-registration's +4 ceiling was computed with a *GT*
proxy (IoU 0.727 vs target GT at fs). When the carry itself has drifted off the target, an
aligned guard still sees no overlap and admits the duplicate. **Aligned dedup is only as good as
the carry it compares against** — which is the same carry-quality constraint that owns the
remaining failures.

### Watch cells

- `DSC_SWAP_car9_950` — did **not** recover; dedup never fired, delivery bit-identical to P5.18
  (iou_t 0.317). The GT-proxy census predicted a fire here; the real carry-referenced guard did
  not agree.
- `DSC_SWAP_person10_450` — recovered via grace, as hoped despite the stacked double failure.

### Visual audit (21 cells opened with the Read tool — full notes in `visual_downgrades.json`)

**0 downgrades.** Every passing cell audited showed the green delivered box on the correct
object. Highlights of what was actually seen:

- `DSC_SWAP_car18_150` discovery f=268: green VLM box on a genuinely small dark SUV far up the
  road — **not** the red Mustang, which was P5.18's exact failure. Grace deliver f=401: green
  squarely on the black SUV, red target GT on the Mustang, well separated. The headline rescue.
- `DSC_SWAP_person10_450` discovery f=572: green on the light-shirted man (the named distractor);
  deliver f=708 green on him, red GT on the dark-blue-shirted person. Clean.
- `DSC_SWAP_bike1_450` discovery f=569: the phrase names "the cyclist in the yellow shirt" but
  the **only** rider in frame is the blue-shirt one, and the VLM boxed him — the distractor is
  genuinely absent, as pre-registered. Grace then delivered onto him anyway.
- `DSC_SWAP_car9_950` deliver f=1190: green box sits *inside* the red target GT on the same white
  car; the dark distractor below untouched.
- `DSC_SWAP_car7_460` deliver f=700: green box on kerb/background, on no object at all.
- `DSC_SWAP_wakeboard3_150` deliver f=390: green box at the extreme frame edge on open water.
- `DSC_WSEL_car7_460` / `DSC_WSEL_car9_950` deliver: **no green box at all** — track lost during
  idle, honest non-delivery.
- `DSC_SWAP_person20_1050` deliver f=1290: box is on the named distractor and off the target
  (clears the rule) but **loose** — it merges two adjacent pedestrians rather than isolating the
  annotated one. Noted, not downgraded.

### Rig, versions, wall-clock

- Jetson `sudo nvpmodel -q` → `NV Power Mode: 15W`, mode `0` (+ `jetson_clocks`).
- `.venv-ft`: Python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6. VLM
  `phase3-terse100eos-1024-q8_0.gguf` + `mmproj-...-f16.gguf`, MAX_SIDE 1024. SAM2
  `facebook/sam2.1-hiera-tiny` bf16. UAV123 @ 1280x720, 30 fps.
- Matrix compute: **26.4 min** summed over 54 cells (mean 29.3 s/cell). Elapsed span was longer:
  the run was interrupted and resumed across several driver cycles by the 5 h rate-limit window
  (see `.claude/loop.log`); per-cell snapshot dirs made this a no-op resume, and the final driver
  found 54/54 `results.json` already written.

### Estimate-vs-actual

| quantity | estimate | actual | note |
|---|---|---|---|
| matrix runtime | 28–40 min | **26.4 min** compute | slightly under; the extra VLM call was cheaper than budgeted |
| verdict branch | 1 (YES) at SWAP 20–21 | **branch 1, SWAP 20** | landed at the bottom of the predicted band, exactly on the bar |
| WSEL | ~22 | **22** | exact |
| dedup fires | ~4–8 cells | **8 cells** | top of band |
| grace fires | ~2–4 SWAP cells | **4** | top of band |
| grace acquire_s | 0.23–0.8 s | **0.367–0.600 s** | inside band |
| recovery | +2..4, median ~20 | **+3** | exact median |
| regression floor | ~0 | **1 (the non-gating control)** | **estimate wrong** — see above |
| bike1:450 | bucket conversion, no flip | no flip, but via a *graced wrong delivery*, not an honest discovery-failed | **mechanism wrong**, count right |

### What broke / what to carry forward

Nothing broke operationally: R0 gates green, 54/54 cells scored, 0 INVALID, 0 retries, 0 hangs.
The substantive negatives are the two above (control regression; aligned dedup inherits carry
drift). The remaining 6 SWAP and 4 WSEL failures are now a **clean** carry-quality bucket —
which was one of the stated reasons to fix discovery integrity first: wrong-seed cells no longer
contaminate the drift measurement. Every remaining failure is either carry drift onto background
or a third object (6 cells), or an honest carry loss during idle (2 cells), or a genuinely absent
referent (bike1:450).

## Proof deliverables (`proof/`, all committed)

All four are reproducible from `runs/*/results.json` via the committed `make_proof.py` (the
grace frame is copied straight out of `runs/`). All four were opened with the Read tool before
being committed.

1. **`discovery_headline.png`** — the before/after that names the whole result. LEFT: P5.18
   `DSC_SWAP_car18_150` discovery f=134, phrase "the black SUV", green VLM box on **the red
   Mustang** — the misaligned guard accepted a distractor track born on the target. RIGHT: P5.19
   same cell, f=268, green box on the actual black SUV far up the road. Config: DSC arm, SWAP
   leg, aligned dedup + grace.
2. **`paired_flip.png`** — per-scene 4-column grid (P5.18 WSEL / P5.19 WSEL / P5.18 SWAP / P5.19
   SWAP) over all 27 scenes; green=pass, red=fail, black outline=flip, G=grace delivery. Shows
   the 3 SWAP recoveries, the untouched WSEL columns, and the one outlined red G in the
   car3:200 control row — the regression. Built from both campaigns' `results.json`.
3. **`dedup_census.png`** — discovery-call outcomes, P5.18 vs P5.19 over 54 cells: the
   distinctness guard going from **0 fires in 108 calls** (frame-misaligned, structurally dead)
   to 8 duplicate-rejects, plus 4 graced deliveries and 0 grace refusals.
4. **`grace_deliver_car18_150.png`** — the single best graced delivery (`DSC_SWAP_car18_150`,
   f=401, acquire_s=0.367): green delivered box on the black SUV, red target GT on the Mustang,
   blue stale prompt-frame distractor GT labelled as stale. This is what a 0.367 s bounded-grace
   delivery looks like against the 4.68 s cold re-ground it replaces.

## Definition of done (Opus)

1. R0 gates green; R1 matrix complete (54 results.json or documented INVALIDs); visual audit
   written to `visual_downgrades.json`; R2 verdict + proof figures.
2. This README's Results filled (tables above + estimate-vs-actual + what broke).
3. RESULTS row appended to `docs/results/part5-anticipatory.md` (P5.19, both legs + delta vs
   baseline + branch).
4. QUESTIONS entry appended to `docs/questions/part5-anticipatory.md` (RQ-P5.19 + one-line
   verdict).
5. DECISIONS entry appended to `docs/decisions/part5-anticipatory.md`: the aligned-dedup +
   grace bundle vs the rejected carry-hardening lever and the rejected dedup-only design (what
   / why / what was given up — material in "The pick" above).
6. Proof deliverables committed under `proof/` (the 3 make_proof.py figures) and captioned
   here: what each shows, which runs/config produced it. If grace fired anywhere, also copy
   the single best `grace_deliver.png` into `proof/` with a caption naming the cell.
7. Commit on this branch; the loop driver merges. Do NOT touch CLAUDE.md, `.claude/`, or any
   file outside this experiment dir + the three per-Part ledger docs.

### Shadow re-ground (RG), analysed under R-5 (2026-07-21)

The shadow arm was recorded here and never analysed. It is now analysed by
`thesis/analyse_shadow_rg.py`, and the analysis is **one-directional on purpose**.

- **RG selection-correct: 42/50** of the gating cells that have a shadow record,
  8 of the failures by abstention (`selected: null`, no candidate matched
  above the floor). This is a **ceiling**, not a pass rate: the shadow never carries
  a track after its re-ground, so it is never charged coverage or delivered IoU.
- **It is not paired against DD, and the obvious pairing is vacuous.** DD's
  selection is string equality against the stored caption
  (`select_p56.bind_by_caption`, with an assert that exactly one matches), so DD
  scores 50/50 by construction and cannot mis-select. Pairing DD `pass` against RG
  `selected` instead — one criterion folding in coverage, IoU and carry survival,
  the other selection only — is the shape R-21 catalogues as MISLEADING, and the
  paired p it produces is not reported.
- **The dropped cells are not missing at random.** `meta.shadow` is written after
  the early `fail()` returns, so every cell without one is a DD failure. Dropping
  them conditions the number on DD surviving to the prompt.
- **RG is not an independent contract.** It matches its VLM box against
  `cand_at_prompt` — DD's own maintained tracks — so a drifted carry costs RG a
  match. Its failures are re-ground failures plus inherited carry drift.
- **One coincidence not to over-read:** RG's SWAP ceiling is 20/26, the same
  count as DD's realized strengthened-SWAP pass rate. A ceiling on selection and a
  realized pass rate are different quantities; their equality is not a tie.
