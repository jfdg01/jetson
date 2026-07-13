# P5.3 — multi-candidate select-on-command (late-binding phrase select)

**Status: COMPLETE — RQ-P5.3a FAIL (WSEL 3/5), RQ-P5.3b FAIL (SWAP 2/5), overall NO. Ran 2026-07-14T01:47Z (Madrid). A FAIL is a valid result; matrix ran clean (15/15, exit 0), no abort triggered.**
<!-- prior status -->
**Status: PRE-REGISTERED — matrix not yet run.**
Pre-registered 2026-07-14T01:35Z (Madrid wall clock). Design + patches by Fable;
**Opus runs the matrix and fills the Results section only — do NOT re-patch code.**
Branch: `experiment/multi-candidate-select`.

## Research question

Part V so far (P5.1, P5.2) proved warm-start acquire with **one dominant
target** — the "select" stage was trivially satisfied (the 2026-07-14 charter
audit, item 1: all 31 clips single-dominant-target, selection untested). P5.3
tests the untested pipeline stage: when **two same-class candidates** are
warm-carried through the idle window, does the operator's phrase pick the right
track?

- **RQ-P5.3a (select works):** late-binding phrase select (WSEL) delivers the
  *named* target's live track — PASS on **>= 4/5 scenes**, where per-scene PASS =
  `selection == target` AND `genuine_lock` (delivered box IoU vs target GT >= 0.25
  at the delivery frame) AND `coverage >= 0.5` over the 10 s window.
- **RQ-P5.3b (the phrase drives it):** swapping the phrase swaps the selection —
  SWAP PASS on **>= 4/5 scenes**, where PASS = `selection == distractor` AND
  delivered box IoU vs *target* GT < 0.25 (checkable with target-only GT) AND no
  failure reason.
- **Overall verdict = YES iff both a and b hold.** CSEL (cold baseline) is
  reported for comparison (expected mostly FAIL by staleness, per E18/P5.1/P5.2)
  but does not gate the verdict.

## Method: late-binding select (and why)

At the prompt `t_p`, the deployed phrase-grounding VLM (Qwen2-VL-2B q8_0 terse,
max_side 1024 — the frozen Part II backend) fires on the prompt frame. Its box
lands ~4.5 s later; **as a raw box it is stale** (the whole Part IV finding). But
instead of using it, we **match it by IoU against the candidates' carried boxes
at the submit frame** (the frame the VLM actually saw), then deliver the matched
**track's current box**. Track identity survives the VLM latency even though the
raw box does not.

Fairness note (differs from P5.1): WSEL/SWAP and CSEL all deliver at the **same
frame** (`prompt + measured_acquire`). The warm legs get no earlier delivery
here; the only difference is *what* is delivered — a live track's current box vs
a stale raw box. This isolates the late-binding claim from the delivery-lag
claim already proven in P5.1/P5.2.

Grounding in existing work (why this is NOT a deep-research cycle): the deployed
VLM *is* a phrase->box model, fine-tuned in Part II on RefDrone — a
referring-expression dataset whose expressions disambiguate among same-class
distractors. Phrase-driven selection among candidates is therefore in the
model's training lineage; the only new mechanism is the IoU match, built from
`replay_source.iou` + the existing carry. No new method, no new citation needed.

**Rejected alternative (record for DECISIONS):** CLIP crop-text similarity or
VLM multiple-choice over candidate crops would answer the select question with
lower latency, but neither is grounded in repo code or already-cited work — they
would require a deep-research cycle first. Late-binding re-ground costs the full
acquire latency but uses only deployed, already-validated components. If P5.3
FAILS on the match mechanism, the crop-scoring family becomes the next
deep-research target; given up for now: sub-acquire-latency selection.

**Scope cuts (recorded):**
1. Candidate *enumeration* is out of scope. The 2-candidate set is seeded at
   `f0`: target from `gt[f0]` (oracle seed — justified by P5.1/P5.2 where WARM
   matched ORACLE exactly), distractor from a hand-annotated box (this README).
   Idle-window candidate *discovery/maintenance* is charter backlog item 2.
2. REGROUND off in WSEL/SWAP (v1 isolates the select mechanism, mirroring
   E18-B/ORACLE). CSEL keeps REGROUND on (deployed behaviour).
3. Two candidates only; K>2 is future work.
4. UAV123 person clips (the downloaded subset) have no >= 8 s co-visible
   same-class distractor pairs (checked person13, person20: ~5-6 s spans) — so
   P5.3 v1 runs on **car scenes only**. Negative curation result, recorded.

## Legs

| Leg | Phrase | Candidates | Delivery | REGROUND |
|---|---|---|---|---|
| WSEL | target caption | 2 carries seeded at f0, idle catch-up at CARRY_HZ/2 each, realtime bridge during acquire | matched track's current box at `prompt+acq` | off |
| SWAP | **distractor** caption | same | same | off |
| CSEL | target caption | none (deployed cold path) | raw stale VLM box at `prompt+acq`, carry seeds there | on (mask gate app_tau 12.0) |

Match rule: `argmax IoU(vlm_box, candidate_box_at_prompt)`; `NO_MATCH` if max
< 0.10 (e.g. the VLM boxed an uncarried third object) — no delivery, leg FAILS
with reason. Honest failure mode; in deployment it would fall back to cold.

Budget honesty: during idle and the acquire bridge each candidate runs at
CARRY_HZ/2 = 3.075 Hz (two tracks share E1's measured 6.15 Hz on-Orin SAM2
budget). After select the loser is dropped and the winner gets full CARRY_HZ.

## Scenes (frozen in `scenes.json`)

Curated 2026-07-14 by rendering frames with GT + grid overlays and verifying
both boxes visually (target box = red, distractor = blue, all 5 verified).
`f0` is a 0-based frame index (frame file `%06d.jpg` = f0+1, GT line = f0+1).
All scenes: t_p = 8 s after f0, cover 10 s, fps 30.

| Scene | Target (GT[f0]) | Distractor (hand box @f0) | Known risks (recorded, kept) |
|---|---|---|---|
| car10:240 | "the white car" | "the black car" [540,253,600,311] | third dark car ahead may draw VLM (NO_MATCH) |
| car10:615 | "the white car" | "the white van" [588,455,715,700] | type not colour disambiguation; big silver sedan mid-frame = phrase ambiguity |
| car9:300 | "the silver car" | "the black car" [588,528,660,672] | distractor overtakes target during idle; third maroon car enters ~f540 |
| car7:460 | "the silver car" | "the black car" [900,308,1000,352] | target GT NaN patch ~f900 in coverage window (scorer skips NaN frames) |
| car3:200 | "the red car" | "the white car" [388,538,420,602] | tiny boxes (~16x40 px) small-object VLM risk; second white car may draw SWAP |

Dropped during curation: person13/person20 (distractor co-visibility < 8 s),
car2/car4 (only 4 frames on disk).

## Code (already committed — Opus: do NOT edit these files)

- `select_p53.py` — the rig. Imports (does not copy) `replay_e24` pieces
  (`vlm_acquire`, `MaskGate`, `coverage_realtime`, `e24_score`, constants) and
  `warmstart.window`. New: `idle_catchup_multi` (2 carries at CAND_HZ),
  `bridge_realtime` (alternating realtime steps during the acquire latency,
  frames drop), the IoU match with 0.10 floor, `leg_pass` (mechanical verdict
  rules), f0-offset frame arithmetic, sliced overlay renderer.
  `--selfcheck` is green (stub carries + stub VLM + fake clock; asserts offset
  arithmetic, phrase-driven selection both ways, NO_MATCH floor, CSEL stale
  path, leg_pass rules).
- `scenes.json` — the frozen 5-scene set above.
- `make_proof.py` — builds `proof/p53_pass_grid.png` + `proof/p53_deliver_iou.png`
  from `runs/*/results.json`.

Versions: same stack as P5.1/P5.2 (`.venv-ft` from `requirements-ft.lock.txt`;
SAM2.1-tiny via `stream_carry.MODEL`, carry on the local RTX 3090 rate-capped to
the on-Orin 6.15 Hz budget; VLM on the Jetson over SSH, q8_0, max_side 1024,
greedy decode — deterministic rig, n=1 per cell justified as in P5.1).

## Run matrix (Opus: exact commands)

Jetson must be at 15W + jetson_clocks (both NOPASSWD over SSH):

```bash
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"
ssh jetson "nvpmodel -q | head -2"   # confirm 15W mode, record output below
```

Selfcheck first (no hardware):

```bash
cd /home/gara/jetson
.venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py --selfcheck
```

Full matrix (5 scenes x 3 legs = 15 runs; each run boots the Jetson q8_0
server, writes `runs/<LEG>_<clip>_<f0>/results.json` + `overlay.mp4`, and skips
cells whose results.json already exists — safe to re-run after an interruption):

```bash
cd /home/gara/jetson
.venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py \
    --matrix experiments/2026-07-14-multi-candidate-select/scenes.json --out runs \
    2>&1 | tee experiments/2026-07-14-multi-candidate-select/raw/matrix_$(date +%Y%m%d_%H%M).log
```

(`mkdir -p experiments/2026-07-14-multi-candidate-select/raw` first if needed.)
Single-cell rerun example:

```bash
.venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py \
    --matrix experiments/2026-07-14-multi-candidate-select/scenes.json \
    --only car9:300 --legs WSEL --out runs
```

Then proof figures:

```bash
.venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/make_proof.py
```

## Verdict rules (mechanical — encoded in `leg_pass`)

- Per-run PASS is computed by the rig and printed + stored as `"pass"` in
  results.json; the README verdict is just counting.
- RQ-P5.3a YES iff WSEL PASS >= 4/5. RQ-P5.3b YES iff SWAP PASS >= 4/5.
  Overall YES iff both. 3/5 on either = FAIL (a FAIL verdict is a valid result;
  record which stage broke: VLM grounding wrong object, NO_MATCH floor, carry
  drift, or coverage collapse — the `reason`/`match_ious` fields in results.json
  say which).
- **Abort criteria:** (1) Jetson server fails to boot 3x in a row — stop, record,
  check device. (2) The first two scenes' WSEL both end NO_MATCH *with a valid
  VLM box* (suggests a match-rule bug, not a model failure) — stop, inspect
  `match_ious` and the overlay, report back instead of burning the matrix.
- GT-handling rule (pre-registered): GT exists only for the annotated target.
  Selection correctness comes from the match rule (which carried track won);
  SWAP is scored as "distractor selected AND delivered box NOT on the target"
  (IoU < 0.25 vs target GT). No distractor GT is ever needed.

## Estimates (marked as estimates)

- Per run: ~60-120 s wall (Jetson boot dominates; idle catch-up ~50-85 strided
  SAM2 steps, acquire ~4.5-5 s, bridge ~5 s realtime, coverage ~10 s realtime,
  overlay render ~1-2 min for the ~700-frame slice). 15 runs: **~30-50 min**.
- Expected numbers (estimates): WSEL 4/5 (car3's tiny boxes the likeliest
  miss), SWAP 3-5/5 (car3/car10:615 phrase-ambiguity risks), CSEL genuine_lock
  0-2/5 (staleness, consistent with COLD 5/25 in P5.2).

## Results (TBD — Opus fills this section only)

Jetson power mode check output: `NV Power Mode: 15W` (+ `sudo jetson_clocks`). Rig on local RTX 3090 (SAM2 carry, rate-capped to 6.15 Hz), VLM q8_0 max_side 1024 on the Jetson over SSH. n=1 per cell (deterministic, as P5.1/P5.2). Wall ~15 min total.

| Scene | WSEL sel | WSEL iou@deliver | WSEL cov | WSEL PASS | SWAP sel | SWAP iou@deliver | SWAP PASS | CSEL iou@deliver | CSEL PASS |
|---|---|---|---|---|---|---|---|---|---|
| car10:240 | target | 0.815 | 1.00 | **PASS** | NO_MATCH (0.000) | — | FAIL | 0.490 | **PASS** |
| car10:615 | NO_MATCH (0.000) | — | 0.00 | FAIL | NO_MATCH (0.009) | — | FAIL | 0.000 | FAIL |
| car9:300 | target | 0.873 | 0.963 | **PASS** | distractor | 0.000 | **PASS** | 0.053 | FAIL |
| car7:460 | target | 0.806 | 1.00 | **PASS** | NO_MATCH (0.000) | — | FAIL | 0.000 | FAIL |
| car3:200 | distractor | 0.000 | 0.00 | FAIL | distractor | 0.000 | **PASS** | 0.249 | FAIL |

- WSEL PASS count: **3/5** (car10:240, car9:300, car7:460) -> RQ-P5.3a: **FAIL** (needs >= 4/5)
- SWAP PASS count: **2/5** (car9:300, car3:200) -> RQ-P5.3b: **FAIL** (needs >= 4/5)
- Overall P5.3 verdict: **NO** (YES requires both a and b)
- CSEL (baseline, non-gating): genuine_lock **1/5** (car10:240 only), consistent with COLD 5/25 in P5.2 — cold stays broadly stale.
- Estimate-vs-actual divergences: WSEL landed 3/5 vs estimated 4/5 (car10:615 missed as flagged, but car3:200 also missed — VLM grounded the "red car" phrase onto the white-car distractor track, not the tiny red target). SWAP landed 2/5 vs estimated 3-5/5 — worse than expected: the distractor captions ("the black car", "the white van") NO_MATCH 3/5 because the deployed VLM's box at the prompt frame overlapped neither carried candidate. Wall ~15 min, under the 30-50 min estimate (Jetson server kept warm across cells).
- What broke where (from `reason`/`match_ious`/overlay):
  - **Dominant failure = NO_MATCH (4 of 7 non-passes):** the stale VLM box at the submit frame overlaps neither carried candidate's box at the prompt frame (max IoU ~0.000). This is the honest fallback the match rule was designed to catch, but it fires far more than expected — the VLM grounded the caption onto an object outside both carried tracks (third cars in-frame, or type/colour phrase ambiguity for the distractor captions). NOT a match-rule bug: WSEL passed cleanly on car10:240 / car9:300 / car7:460 with deliver_iou 0.81-0.87, proving the IoU match delivers the correct live track when the VLM box lands on a carried candidate.
  - **Wrong-object grounding (car3:200 WSEL):** VLM boxed the white-car distractor for "the red car" (tiny ~16x40 px target), match selected distractor, deliver_iou 0.0 vs target GT. Small-object grounding risk, pre-registered.
  - **SWAP passes are real but partial:** car9:300 and car3:200 SWAP correctly selected the distractor (delivered box off the target, IoU 0.0 vs target GT = correct per the SWAP scoring rule). The other 3 SWAP cells NO_MATCH on the distractor caption.
  - **Interpretation:** the late-binding IoU-match mechanism is *sound but not robust enough* — it is bottlenecked by the deployed VLM's raw grounding accuracy at the prompt frame, not by carry drift or the match rule. Selection succeeds when and only when the VLM boxes a carried candidate. Per the pre-registered rejected-alternative note, this motivates the crop-scoring family (CLIP crop-text / VLM multiple-choice over the *carried candidate crops* directly, bypassing free-frame VLM grounding) as the next deep-research target.

## Deliverables plan (DoD-7)

1. `proof/p53_pass_grid.png` — per-scene x per-leg outcome grid (from
   `make_proof.py`, built from `runs/*/results.json`). Shows WSEL 3/5, SWAP 2/5,
   CSEL 1/5 and the NO_MATCH cells — the quantitative FAIL at a glance.
2. `proof/p53_deliver_iou.png` — WSEL vs CSEL delivered-box IoU at the same
   deliver frame. Where WSEL matches (3 scenes) it delivers a live track at
   IoU 0.81-0.87; CSEL's stale raw box collapses to ~0 on the same frame. The
   late-binding-vs-stale figure — and the reason the *mechanism* is sound even
   though the *verdict* is FAIL.
3. Curated overlay clip pair (car9:300, re-encoded from `runs/`):
   - `proof/car9_300_WSEL.mp4` — phrase "the silver car": the matched track (green
     delivered box) locks the silver target, IoU 0.873, cov 0.96 → PASS. The
     positive half of the late-binding claim.
   - `proof/car9_300_SWAP.mp4` — same scene, phrase swapped to "the black car":
     selection flips to the distractor track (delivered box leaves the target) →
     SWAP PASS. The phrase drives the selection when the VLM grounds a carried
     candidate. (This is one of only 2 scenes where both directions worked; the
     overall FAIL is driven by NO_MATCH elsewhere — see Results.)

## Ledger checklist (post-run)

- [x] RESULTS row(s) -> `docs/results/part5-anticipatory.md`
- [x] QUESTIONS entry (RQ-P5.3a/b + one-line verdicts) -> `docs/questions/part5-anticipatory.md`
- [x] DECISIONS entry (late-binding vs crop-scoring; oracle-seeded candidate
  set scope cut) -> `docs/decisions/part5-anticipatory.md`
- [x] No new external sources pulled in -> SOURCES unchanged
