# P5.16 — autodisc-select: does direct-delivery select survive removing the seed oracle?

**Pre-registered:** 2026-07-19T14:55Z (Madrid wall clock). Design + patches by Fable; Opus runs
the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE — run 2026-07-19T15:00Z–15:03Z. **OVERALL: YES** (RQ-P5.16a WSEL 4/5,
RQ-P5.16b SWAP 4/5 strengthened; V PASS on all 24 gating frames, no downgrade). The seed oracle
is removable: 1 flip out of 12 cells, and the P5.14 headline survives with VLM-discovered seeds.
**Branch:** `experiment/autodisc-select` off `main` @ `6a26e62`.
**Hardware:** RTX 3090 host (SAM2 carry, bf16) + Jetson Orin Nano 8 GB over `ssh jetson`
(VLM: discovery calls + idle ROI re-anchors + non-gating shadow call), `15W` + `jetson_clocks`.

## Research question

P5.14 delivered the first Part V select YES (WSEL 5/5, SWAP 4/5 strengthened) — but its two
candidate carries were seeded by oracles at f0: the target from `gt[f0]` (UAV123 GT) and the
distractor from a hand-annotated box. The audit of P5.14 (this cycle) flagged that dependency as
the YES's biggest external-validity gap, and P5.15 explicitly named the auto-discovery cycle as
unblocked (the carry itself survives 24 s idle unmaintained, 24/25 — so if discovery seeds a
carry early, the carry will still be alive at the prompt). P5.16 changes exactly ONE factor:
**seed provenance**. Both candidates are found by the deployed VLM itself during the idle
window (anticipatory grounding of the two known operator phrases), with no ground truth
anywhere in the loop. Everything else — idle ROI maintenance, caption binding, direct delivery
(acquire_s = 0), coverage, the strengthened SWAP rule — is the P5.14 path, imported unchanged
from `select_p56.py` (not copied).

Scope note (recorded, not tested here): the caption→candidate *binding* stays string equality
on the two known phrases. Free-phrase binding is a separate factor for a later cycle;
single-factor discipline keeps this run attributable to seed provenance alone.

- **RQ-P5.16a** — With VLM-discovered seeds, does WSEL (select the warm target) still pass on
  >= 4 of the 5 gating scenes? (PASS per cell = P5.14 rule verbatim: correct selection AND
  genuine lock at deliver AND coverage >= 0.5.)
- **RQ-P5.16b** — Does SWAP (select the warm distractor) still pass the STRENGTHENED rule on
  >= 4 of the 5 gating scenes? (PASS per cell = delivered box IoU < 0.25 vs target GT AND
  >= 0.25 vs the hand distractor GT at the prompt — junk cannot pass.)
- **OVERALL = YES iff both AND the visual gate (below) does not downgrade.** car3:200 never
  gates (control).

## Design

### Discovery protocol (the single new mechanism)

- Discovery starts at `ds = f0 - DS_OFFSET`, **DS_OFFSET = 150** frames (5 s pre-roll). A
  design-time frame audit (all six ds frames dumped and looked at, 2026-07-19) confirmed: every
  target is visible with valid GT at ds; 4/6 distractors (car10:615 van, car9:300 black car,
  car7:460 black car, car3:200 white car) enter the FOV only near f0 — which is why the
  schedule fires target first: the distractor call then lands at ~ds+140 ≈ f0-10, where the
  distractor's presence is proven by the existence of P5.14's f0 hand seed.
- Queue starts `[target, distractor]`. The head caption fires as a FULL-FRAME VLM call on the
  current frame `fs`; the measured wall latency advances the stream: `fr = fs + round(lat*fps)`
  (latency-honest — no free lookahead). Existing carries keep stepping at CAND_HZ across
  [fs, fr].
- Accept rule (NO GT anywhere): parseable + `_valid` in frame AND IoU < **IOU_SAME = 0.5** vs
  every already-carried candidate's current box (distinctness guard: rejects the VLM re-finding
  the same object under the second caption). Accepted → SAM2 carry seeded on frame fs (the
  frame the VLM actually saw), caught up fs → fr.
- Rejected/invalid → the caption requeues at the BACK. A call still in flight at the prompt is
  DISCARDED (outcome recorded `in_flight_at_prompt`). A caption never accepted by the prompt is
  an honest per-leg failure: reason `discovery-failed:<candidate>`.
- After discovery, the P5.14 idle maintenance runs unchanged (distractor ROI re-anchor at
  f0+90 / f0+165, P5.5 accept rule verbatim), with one mechanical guard: a boundary that falls
  before the discovery-done frame is SKIPPED and recorded `in-discovery` — the Jetson was busy.

### The discovery budget (pre-registered teeth)

Window = DS_OFFSET + t_p·fps = 390 frames (t_p=8.0 scenes) or 330 (car9:560, t_p=6.0). At the
measured full-frame acquire latency (~4.4–4.6 s ≈ 132–138 frames, P5.14 shadow calls), that is
**exactly 2 completed call slots** — a retry after an invalid/duplicate first answer only fits
if mean latency < ~4.2 s, which the record says it isn't. So in practice each caption gets one
shot; a wasted slot kills that caption's leg honestly. This is deliberate: the alternative
(earlier ds) was rejected because the look showed 4/6 distractors absent before ~f0, so earlier
distractor calls would invite false-positive discoveries. Scenario B of the selfcheck encodes
this budget exactly.

### Pre-registered per-scene hazards (from the design-time look at the ds frames)

- car10:240 — the distractor caption's relation ("the black car in front of the white car")
  INVERTS between ds and f0 (black car is behind at ds, in front by f0). Defused for the
  distractor call by target-first scheduling (fires near f0), but recorded.
- car7:460 — two adjacent silver/grey cars at ds: the target caption "the silver car" is
  ambiguous there; wrong-object WSEL discovery risk.
- car10:615 — the target caption's relatum ("the white van") is absent at ds; the VLM may
  ground a different white car; WSEL risk.
- car9:560 — tightest window (330 frames ≈ 2.4 slots).

### What is inherited byte-identical (imported, not copied)

Delivery contract, `bind_by_caption`, `leg_pass_p56`, `swap_weak_pass`, DIST_FLOOR, coverage
(`coverage_realtime` + `e24_score`), shadow re-ground (non-gating), ROI re-anchor
(`roi_reanchor`, ROI_MARGIN 2.0, ROI_MIN_SIDE 256, ROI_RES 512), carry cadences (CARRY_HZ 6.15,
CAND_HZ 3.075), MAX_SIDE 1024, VLM = Qwen2-VL-2B q8_0 terse (Jetson llama.cpp). Scenes =
`scenes_p516.json`, a byte-identical copy of P5.14's frozen `scenes_p56.json` (the
`distractor_box` field is NOT used for seeding here — only `distractor_gt_prompt` for scoring).

### Rejected competitor (seeds DECISIONS)

Considered and rejected this cycle: (1) a carry-health gate / IoU-floored re-anchor fix for the
P5.15 identity-swap finding — low leverage: P5.15 already measured the mechanism, PLAIN needs
no maintenance at these horizons, and it would optimize a component the select arc doesn't
currently need; (2) sim bank v3 with z-order/displacement gates — third rejection of the sim
fork: two banks in a row tied the contracts (P5.10, P5.13) while real video separated them for
free (P5.14); the mandated bank-v3 gates stay carried forward, unexecuted. The oracle-seed
dependency is the largest remaining unearned assumption in the Part V headline result, and
P5.15 explicitly de-risked it — highest leverage.

## Code (already committed — Opus: do NOT edit these files)

| File | Role |
|---|---|
| `discover_p516.py` | rig: discovery scheduler + leg runner + real-stack matrix + `--selfcheck` (scenarios A–E + upstream P5.6/P5.5/P5.3 suites) |
| `scenes_p516.json` | frozen input, byte-identical copy of P5.14 `scenes_p56.json` |
| `verdict_p516.py` | mechanical verdict, fail classes, oracle-delta vs the hardcoded frozen P5.14 row |
| `make_proof.py` | `proof/p516_pass_grid.png` (P5.14 oracle vs P5.16 discovered) + `proof/p516_discovery.png` (discovery timelines) |

Selfcheck was green at commit time on the design machine. The rig dumps the claim frames
itself (`deliver.png`, `discovery_<cand>.png` per cell) with inline frame-health asserts
(>99%-one-colour → hard fail).

## Run matrix (Opus starts here — exact commands)

Software versions are recorded into every `results.json` at runtime; copy one set into Results.
UAV123 = 1280x720 @ 30 fps. New frozen constants: DS_OFFSET 150, IOU_SAME 0.5. All other
constants inherited (values above).

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-19-autodisc-select
mkdir -p $EXP/raw

# R0. offline selfcheck (no GPU/Jetson; must end "discover_p516 selfcheck OK";
#     any failure -> STOP, record, do not run the matrix, do not fix code)
.venv-ft/bin/python $EXP/discover_p516.py --selfcheck 2>&1 | tee $EXP/raw/selfcheck.log

# R1. Jetson power config (idempotent, NOPASSWD)
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"

# R2. pilot cell (shakes out Jetson boot + discovery path on one cell)
.venv-ft/bin/python $EXP/discover_p516.py \
    --matrix $EXP/scenes_p516.json --only car10:240 --legs WSEL \
    --out runs 2>&1 | tee $EXP/raw/pilot.log

# R3. full matrix: 6 scenes x 2 legs = 12 cells, sequential, resumable
#     (existing runs/DSC_*/results.json are skipped — the pilot cell is not rerun;
#      single-cell rerun after a CRASH only: --only car9:560 --legs SWAP)
.venv-ft/bin/python $EXP/discover_p516.py \
    --matrix $EXP/scenes_p516.json --out runs 2>&1 | tee $EXP/raw/matrix.log

# R4. mechanical verdict (paste FULL output verbatim into Results)
.venv-ft/bin/python $EXP/verdict_p516.py 2>&1 | tee $EXP/raw/verdict.txt

# R5. proof figures (after the verdict)
.venv-ft/bin/python $EXP/make_proof.py
```

Each cell writes `runs/DSC_<LEG>_<clip>_<f0>/results.json` + `deliver.png` +
`discovery_<cand>.png` (per accepted candidate) + `overlay.mp4`. `runs/**` is gitignored;
curated evidence goes to `proof/`.

### Abort criteria (mechanical — do not deliberate)

- R0 selfcheck fails → STOP; record the output; the matrix does not run.
- A cell CRASHES (exception, not a scored FAIL) → snapshot the traceback to `raw/`, retry once
  via `--only <clip>:<f0> --legs <LEG>`; a second crash → STOP and record (infra, not a
  verdict; the campaign is INCOMPLETE).
- A cell's wall time exceeds 20 min → kill, record, retry once; twice → STOP (Jetson hang).
- Jetson unreachable / q8_0 server fails to boot twice in a row → STOP, record, INCOMPLETE.
- Never rerun a scored cell; n=1 deterministic replay, first scored result stands.

## Visual verification (gating — CLAUDE.md "Look at it")

After R3, open with the **Read tool**, for EVERY one of the 12 cells:

1. `runs/DSC_<LEG>_<clip>_<f0>/deliver.png` — the prompt frame, the frame the verdict is about:
   green = delivered box, red = target GT, blue = hand distractor GT.
2. `runs/DSC_<LEG>_<clip>_<f0>/discovery_<selected>.png` — the frame the VLM actually saw when
   it discovered the SELECTED candidate (target for WSEL, distractor for SWAP; tagged
   `<== SELECTED` in the banner), green = VLM box (red = target GT overlaid on target
   discoveries, diagnostic). If the cell failed `discovery-failed:<selected>` this file will
   not exist for the selected candidate — that absence must MATCH the scored reason.

That is up to 24 gating PNGs. **PASS looks like:** a real aerial road scene; in `deliver.png`
the green box sits on the correct vehicle (target vehicle for WSEL, distractor vehicle inside
the blue box for SWAP); in `discovery_*.png` the green box sits on the vehicle the caption
names. **FAIL looks like:** green box on the wrong vehicle or empty road (the fail class says
`off-target`/`off-distractor` — the picture must show exactly that), a missing discovery PNG
matching `discovery-fail`, or a black/one-colour frame (that cell INVALID — never a
log-inferred pass). Record one line per cell in Results ("what I saw"). A scored PASS whose
frames contradict it → **V downgrades OVERALL to NO**; a scored FAIL is never rescued by V; a
FAIL cell's frames must show the failure mode the class claims (negative proof — capture it).

## Verdict rules (frozen — `verdict_p516.py` is the sole authority)

- RQ-P5.16a = WSEL PASS count over the 5 gating scenes >= 4.
- RQ-P5.16b = SWAP PASS count (strengthened rule) over the 5 gating scenes >= 4.
- OVERALL = YES iff both AND V does not downgrade. car3:200 never gates.
- Fail classes assigned mechanically by `classify()` (discovery-fail / lost-track / off-target /
  off-distractor / on-target / coverage / infra); report verbatim.
- Any cell INVALID per the visual gate or missing `results.json` → INCOMPLETE, not a verdict.
- Non-gating diagnostics to report: the oracle-delta table (P5.14 vs P5.16 per cell — the cost
  of removing the oracle, the experiment's headline number either way), per-cell discovery call
  logs, target seed IoU vs GT at the accept frame, weak-vs-strong SWAP, shadow table.

## Estimates (calibrated vs P5.14 actual 21–22 s/cell; marked estimates)

- **Runtime:** ~35–60 s/cell (P5.14's 21–22 s + 2 full-frame discovery calls ≈ 9 s + 150-frame
  pre-roll carry stepping). Matrix ≈ 8–15 min total; whole run incl. verdict/proof < 25 min.
- **Predictions:** discovery completes both candidates in ~4–5 of 6 scenes per leg (car9:560
  tightest). WSEL 3–4/5 gating; SWAP 2–4/5. **OVERALL predicted NO** — the value either way is
  the oracle-delta table (which cells the oracle was carrying) or, if YES, the removal of the
  Part V headline's biggest asterisk. car3:200 control WSEL predicted to FLIP back to FAIL
  under discovery (its P5.14 PASS was oracle-seed-dependent). Hazard cells most likely to fail
  WSEL: car7:460, car10:615 (see hazards above).

## Results

Run 2026-07-19T15:00Z–15:03Z on `experiment/autodisc-select` @ `848da94`. R0 selfcheck green
(`select_p53` / `select_p55` / `select_p56` / `discover_p516` all OK). No aborts, no crashes, no
INVALID cells; 12/12 cells scored, n=1 deterministic.

**Versions / config:** python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6 (`.venv-ft`, RTX
3090). VLM = `phase3-terse100eos-1024-q8_0.gguf` + `mmproj-phase3-terse100eos-1024-f16.gguf`
(llama.cpp on Jetson Orin Nano, `NV Power Mode: 15W` mode 0 + `jetson_clocks`), MAX_SIDE 1024.
Carry = SAM2 `facebook/sam2.1-hiera-tiny`, CARRY_HZ 6.15 / CAND_HZ 3.075. Frozen constants:
DS_OFFSET 150, IOU_SAME 0.5, MATCH_FLOOR 0.1, DIST_FLOOR 0.25, ROI_MARGIN 2.0, ROI_MIN_SIDE 256,
ROI_RES 512, reanchor offsets [90, 165], cover_s 10.0, UAV123 1280x720 @ 30 fps.

| cell | pass | weak | d_iou | d_dist | cov | seed_iou_gt | disc calls (T,D outcome) | done_f | fail class / reason | what I saw (deliver.png + discovery png) |
|---|---|---|---|---|---|---|---|---|---|---|
| DSC_WSEL_car10_240 | PASS | – | 0.6771 | 0.0 | 1.00 | 0.6828 | accepted, accepted | 360 | – | deliver f=480: green on the white car, red GT overlapping, blue distractor GT on the dark car ahead. discovery f=90: green on the white car, red GT overlapping. Correct. |
| DSC_SWAP_car10_240 | PASS | weak-too | 0.0 | 0.7557 | 0.0 | 0.6828 | accepted, accepted | 360 | – | deliver f=480: green on the dark car ahead, red target GT on the white car — cleanly separated. discovery f=225: green on the dark car beside a white car ("the black car in front of the white car"). Correct. |
| DSC_WSEL_car10_615 | PASS | – | 0.8889 | 0.0202 | 1.00 | 0.5209 | accepted, accepted | 736 | – | deliver f=855: green on the small car ahead of the white van (blue GT = the van). discovery f=465: green on the white car, red GT overlapping. Correct — the pre-registered "relatum absent at ds" hazard did not bite. |
| DSC_SWAP_car10_615 | PASS | weak-too | 0.0 | 0.8758 | 0.0 | 0.5209 | accepted, accepted | 736 | – | deliver f=855: green on the white van (blue GT overlapping), red GT on the small car ahead. discovery f=600: green on the white van as it enters the frame bottom-right, partially cut by the frame edge — still the right object, and the carry held it. |
| DSC_WSEL_car9_300 | PASS | – | 0.8402 | 0.0 | 0.9767 | 0.8039 | accepted, accepted | 423 | – | deliver f=540: green on the silver car, red GT overlapping; blue distractor GT far up the road. discovery f=150: green on the silver car. Correct (best seed of the run). |
| DSC_SWAP_car9_300 | PASS | weak-too | 0.0 | 0.7253 | 0.0 | 0.8039 | accepted, accepted | 423 | – | deliver f=540: green far up the road on the distractor, red GT on the silver car mid-frame. discovery f=286: green on the black car at frame bottom-left. Correct. |
| **DSC_WSEL_car7_460** | **FAIL** | – | – | – | 0.0 | **0.0** | accepted, accepted | 580 | lost-track: selected track lost during idle | discovery f=310 "the silver car": green on a **different** silver car (upper, by the parking lot) while the red target GT sits on the silver car below it — the pre-registered two-silver-cars ambiguity. The wrong carry then dies, so deliver f=700 has **no green box** at all (red/blue GTs on the roundabout). Wrong-object *discovery*, surfaced as a lost track. |
| **DSC_SWAP_car7_460** | **FAIL** | weak-too | 0.0 | 0.0 | 0.0 | 0.0 | accepted, accepted | 580 | off-distractor | discovery f=445 "the black car": green on a dark car on the **far right road**, not the blue-GT dark car in the roundabout. deliver f=700: green stranded at the left frame edge, nowhere near the blue GT. Class `off-distractor` matches the pixels exactly. |
| DSC_WSEL_car9_560 | PASS | – | 0.9116 | 0.0 | 0.97 | 0.6274 | accepted, accepted | 681 | – | deliver f=740: green on the silver car, red GT overlapping. discovery f=410: green on the silver car. Correct despite the tightest window. |
| DSC_SWAP_car9_560 | PASS | weak-too | 0.0 | 0.4779 | 0.0 | 0.6274 | accepted, accepted | 681 | – | deliver f=740: green inside the blue distractor GT up the road (0.4779 — the run's tightest pass, box smaller than GT but on the object). discovery f=546: green on the dark red car. Correct. |
| DSC_WSEL_car3_200 (control) | PASS | – | 0.6667 | 0.0 | 0.94 | 0.5376 | accepted, accepted | 320 | – | deliver f=440: green on the red car, red GT overlapping, blue GT on the car ahead. discovery f=50: green on the red car. Correct — **did not flip**, against the pre-registered prediction. |
| DSC_SWAP_car3_200 (control) | PASS | weak-too | 0.0 | 0.8864 | 0.0 | 0.5376 | accepted, accepted | 320 | – | deliver f=440: green on the distractor (blue GT under it), red GT on the red car below. discovery f=185: green on the light-coloured car. Correct. |

- **RQ-P5.16a: 4/5 gating WSEL PASS → YES** (floor 4). **RQ-P5.16b: 4/5 gating SWAP PASS,
  strengthened rule → YES** (floor 4). **V: PASS** — all 24 gating PNGs opened with the Read
  tool; every scored PASS is corroborated by its frames, both FAILs show the failure mode their
  class claims, no black/degenerate frame (max single-colour fraction 0.009 across all 24).
  **OVERALL: YES.**
- **Oracle delta — 1 flip in 12 cells** (verbatim from `raw/verdict.txt`): only
  `DSC_WSEL_car7_460` was LOST to discovery (P5.14 PASS → P5.16 FAIL). `DSC_SWAP_car7_460` was
  already FAIL under the oracle. All ten other cells are unchanged. **This is the headline: the
  P5.14 select YES was not oracle-propped — removing GT seeding costs exactly one cell, and that
  cell is the one whose caption is genuinely ambiguous in the pixels.**
- **Discovery worked in every cell:** 24/24 VLM calls accepted (0 invalid, 0 duplicate-rejected,
  0 in-flight-at-prompt, 0 `discovery-failed` legs), mean full-frame latency **4.51 s**
  (min 4.49, max 4.56, n=24) — dead-on the pre-registered 4.4–4.6 s. Both captions completed in
  exactly 2 slots, finishing 120 frames (4.0 s) before the prompt in 10 cells and 59 frames
  (2.0 s) before it in the two `car9:560` cells. The budget was tight but never binding.
- **Seed quality (target, IoU vs GT at the accept frame):** 0.52–0.80 on the five cells where
  discovery found the right car (median 0.63), and **0.0** on `car7:460` — the numeric
  fingerprint of wrong-object discovery, agreeing with the picture.
- **Both re-anchor boundaries behaved as designed:** in all 12 cells the f0+90 boundary fell
  inside discovery and was skipped-and-recorded (`in-discovery`), and the f0+165 boundary fired
  and was accepted. No re-anchor harmed a cell here (idle is only ~8 s; contrast P5.15, where
  the same rule cost 2 clips over 24 s).
- **Shadow re-ground (non-gating): disagreed with direct delivery on 4/12 cells** — 3x
  `NO_MATCH` (car10:240 SWAP, car10:615 WSEL, car7:460 SWAP/WSEL) and 1x wrong-object
  (car3:200 WSEL picked the distractor). Shadow acquire 4.48–4.53 s vs **acquire_s = 0.00 s**
  for delivery. Same magnitude of separation P5.14 measured (4/12), now with no GT anywhere in
  the loop.
- **Weak-vs-strengthened SWAP:** 6/6 weak, 5/6 strengthened — the strengthened rule is still
  doing work (it is what makes `car7:460` SWAP a FAIL rather than a pass on a junk box).
- **Estimate-vs-actual.** Runtime: estimated 35–60 s/cell and 8–15 min for the matrix; actual
  **mean 29 s/cell, max 30 s**, matrix **5.7 min**, whole run incl. verdict + proof ~7 min. Third
  consecutive over-estimate, but by ~1.5x rather than the ~4x of the previous two — the
  calibration note landed. Predictions: **wrong in the useful direction.** Fable predicted
  OVERALL **NO** (WSEL 3–4/5, SWAP 2–4/5) and a `car3:200` control flip; actual is YES 4/5 + 4/5
  with the control holding. Of the three named hazard cells, only `car7:460` failed —
  `car10:615` (absent relatum) and `car9:560` (tightest window) both passed. Discovery was
  predicted to complete in "~4–5 of 6 scenes per leg"; it completed in **6/6**.

## What broke / what surprised

- **Nothing broke.** No crash, no Jetson boot flake, no hang, no retry — the abort criteria were
  never exercised.
- **The surprise is how cheap the oracle was.** The pre-registered expectation was that GT
  seeding was load-bearing; it is worth one cell out of twelve. The idle window is long enough
  that a 4.5 s full-frame VLM call per caption is affordable *and* the resulting seed (IoU
  0.52–0.80, not 1.0) is good enough for SAM2 to carry — consistent with P5.15's finding that
  the carry is robust.
- **`car7:460` fails for a language reason, not a vision or tracking one.** Two adjacent silver
  cars make "the silver car" genuinely ambiguous at ds; the VLM's answer is defensible, the
  scene's phrasing is not. The mechanical fail class (`lost-track`) understates this — the loss
  is downstream of a wrong-object discovery, which only the frames and `seed_iou_gt = 0.0`
  reveal. **A future pre-registration should classify on seed correctness before track outcome.**
- **The control did not flip**, so the P5.14 `car3:200` PASS is not oracle-dependent either.
  That retires the last piece of the old "resolution-bound" story for this cell.

## Deliverables (proof/, committed)

1. `proof/p516_pass_grid.png` — P5.14 oracle-seeded vs P5.16 discovered, per cell x leg. Shows
   the whole result in one figure: the two rows are identical except `car7:460` WSEL. Opened and
   verified.
2. `proof/p516_discovery.png` — discovery timelines per cell (frames relative to f0). Shows the
   two accepted calls (T then D) landing inside the idle window in all 12 cells, the skipped
   first re-anchor and the accepted second. Opened and verified.
3. `proof/p516_flip_DSC_WSEL_car7_460_discovery.png` — **negative proof, the single flip.**
   Discovery frame f=310 for "the silver car": the green VLM box is on the wrong silver car
   (upper, by the parking lot); the red target GT is on the silver car below. `seed_iou_gt` 0.0.
4. `proof/p516_flip_DSC_WSEL_car7_460_deliver.png` — the consequence at the prompt frame f=700:
   **no green box at all** (the wrong carry was lost during idle), red target GT and blue
   distractor GT alone on the roundabout. This is what the mechanical class `lost-track` looks
   like when its actual cause is upstream, in discovery.

## Ledger updates (Opus, after Results are filled)

- `docs/results/part5-anticipatory.md`: append one row per RQ with the headline counts.
- `docs/questions/part5-anticipatory.md`: RQ-P5.16a/b + one-line verdicts.
- `docs/decisions/part5-anticipatory.md`: the rejected-competitor decision above (what/why/
  what was given up) + any non-trivial call made during the run.
- `SOURCES.md`: nothing new expected (no new external assets).
- Do NOT merge to main; leave that to the orchestrator review.
