# E22 CV-proposal acquire (drafted 2026-07-04)

**Status: DRAFT — BLOCKED ON E21 (or orchestrator re-order) + PHASE-0 GATE.** Not yet
run. Drafted 2026-07-04T12:10Z by the orchestrator session as a complete handoff: a
fresh conversation should be able to run this campaign from this file alone. Arc-level
loop: `experiments/HANDOFF-acquire-arc.md`.

## Launch gate

Intended order is E20 -> E21 -> E22, each informed by the last. But E22's Phase-0
prior audit is OFFLINE AND FREE (no Jetson, no VLM) — the orchestrator may run
Phase 0 any time after E20 merges, and may run E22 before E21 if budget is tight,
because E22's ~ms prior preserves E20's measured 1.6-2.0 s acquire latency while
E21's extra coarse VLM pass (~+1 s) is pre-registered as likely to re-open the
staleness gap. Record the chosen order and why in DECISIONS.

Skip E22 (pre-registered decline in the ledgers) only if E20's cell arm had been NO,
or if E21 already achieved YES (>= 4/6) with a fully automated prior — then E22 adds
only an ablation and should be scoped down to Phase 0 alone.

## Context (self-contained chain)

- **E18** (`experiments/2026-07-03-real-video-replay/`): real-video wall-clock replay;
  the ~4.85 s full-frame VLM acquire lands STALE (~146 frames of target motion);
  A-leg 1/6 PASS; carry itself is real-video-ready (oracle B-leg 6/6).
- **E19** (`experiments/2026-07-04-motion-comp-acquire/`): bolt-on compensation fails
  (FLOW catastrophic-when-wrong; BUF repairs coverage, cannot flip the arrival-frame
  lock metric).
- **E20** (`experiments/2026-07-04-prompt-scoped-acquire/`): operator-phrase 3x3-cell
  crop cuts acquire to 1.57-2.07 s; 3/6 flip to PASS (car9/car10/car14), coverage up
  on all six; BUT verdict PARTIAL **[hint-fragile]**: a wrong hint makes the VLM
  hallucinate a box in the empty cell (cov 0.000) and the garbage lock poisons the
  mask-gate template. `cellbuf` added nothing over `cell` (why E22 has no buf legs).
- **E21** (`experiments/2026-07-04-coarse-to-fine-acquire/`, may or may not have run
  yet): automates the hint with a ~1 s coarse VLM pass; pre-registered expectation is
  that the added latency costs PASSes vs E20.

**E22's question: can a ~zero-cost CPU prior (camera-motion-compensated frame
differencing + caption colour) supply the cell hint** — E20's latency, no operator,
no coarse-pass second VLM call?

## RQ-E22

Does a CPU proposal prior (motion + colour -> 3x3 cell) preserve E20's cell-arm wins
with no operator hint and no added VLM latency?

## Design

### The prior (`proposals.py`, ~ms on CPU)

`propose(prev_bgr, cur_bgr, color_kw) -> hint | None`, all at a working width of 320:

1. **Camera-motion compensation**: UAV123 has a MOVING camera — raw frame differencing
   is swamped by global motion. Estimate the global shift with
   `cv2.phaseCorrelate` on float32 grayscale (downscaled); shift `prev` by it
   (`cv2.warpAffine`). This is translation-only by design (ponytail: full homography
   via ORB+RANSAC is the upgrade path if Phase 0 shows rotation/zoom clips failing).
2. **Motion mask**: `cv2.absdiff` -> threshold (pre-registered T=25) -> 3x3
   morphological open.
3. **Colour mask**: from the frozen caption keyword. `red`: HSV hue in [0,10]|[170,180],
   S>=90, V>=60. `white`: S<=40, V>=170. `silver`: S<=40, V in [90,170]. Red is a
   strong cue; white/silver are pre-registered as WEAK (sky, road glare) — expected
   fallback clips.
4. **Combine**: motion AND colour if both non-empty, else motion alone, else colour
   alone. Largest connected component with area >= 30 px (at width 320) -> centroid ->
   `scope.hint_for` (import from E20; do not copy). No component -> None.
5. `prev` = the replay frame ~0.5 s before the submit frame (15 frames at 30 fps);
   in `replay_e22.py` grab it via the E19 `frame_at` accessor at `submit_i - 15`
   (clamp to 0; if submit_i == 0 use submit_i + 15 as `prev` — differencing is
   symmetric for cell purposes).

Runtime fallback (floor = E18): prior None -> plain full-frame submit on this attempt;
fine pass invalid -> next attempt full-frame; REGROUND always full-frame.

Caption -> keyword map (frozen): car3/car10/car14/car18 -> `red`; car9 -> `white`;
car7 -> `silver`.

### Phase 0 — offline prior audit (MANDATORY GATE, no Jetson)

Before any on-device leg: for each of the 6 clips, run the prior at the frames a real
run would submit at (t=0 and, to sample a later REGROUND-era submit, t=10 s) and
compare the proposed cell to the GT cell (`hint_for` on the GT box at that frame,
from `experiments/2026-07-03-real-video-replay/data/UAV123/anno/UAV123/<clip>.txt`).
Write the 6x2 hit table to `raw/phase0_prior_audit.txt` and commit it.

- **GATE: proceed to the matrix only if the t=0 top-1 cell hit rate >= 4/6.**
  Below that, STOP: the campaign result is the (cheap, documented) negative
  "CPU prior insufficient on this footage", filled into Results with the hit table —
  that is a complete E22, do not burn Jetson legs.

### The runs

`replay_e22.py`: fork of E20's `replay_e20.py`; first ACQUIRE attempt computes the
prior and, if it yields a hint, uses E20's exact scoped-submit path
(`scope.crop_rect` + `map_back`). `mc_log` gains `"prior_hint", "prior_ms",
"prior_source"` (`"motion+color"|"motion"|"color"|None`) plus E20's `acquire_s`.
CLI `--cv` flag (default off = byte-equivalent E20/E18 path). Selfcheck offline:
synthetic pair with a translating background + an independently moving coloured
patch -> correct cell; prior None on a static pair -> full-frame fallback.

## Decisions

- **D1 — cell vote, not a box** (same rationale as E21 D1): the prior only picks the
  cell; the audited E20 crop path does the rest. One-variable comparison vs E20/E21:
  who supplies the hint.
- **D2 — no buf legs** (E20 measured cellbuf ≈ cell).
- **D3 — translation-only camera compensation** (phaseCorrelate). Given up: homography
  compensation; the Phase-0 gate is exactly where its absence shows up, cheaply.
- **D4 — Phase-0 gate before Jetson legs.** The prior is auditable against GT offline;
  burning 13 on-device legs on a prior that points at the wrong cell would rediscover
  E20's wrong-probe result at 13x the price.
- **D5 — thresholds frozen** (T=25, area>=30@320w, the HSV ranges above). If Phase 0
  fails, record which stage emptied (motion vs colour vs combine) — that diagnosis is
  the deliverable; do NOT tune thresholds per-clip to pass the gate. One documented
  global adjustment is allowed if a plain bug (not a tuning) is found.

## Frozen config

Identical to E20 (Qwen2-VL-2B Q8_0 terse via JetsonBackend max_side 1024, 15W +
jetson_clocks recorded to `raw/jetson-power.txt`, SAM2.1 tiny StreamCarry 6.15 Hz,
E14/E16 mask gate app_tau 12.0, wall-clock replay + E18 scorer, 6 UAV123 clips +
frozen captions). Matrix: smoke (`cv` car10 x1; sanity: prior_ms < 100 AND acquire_s
< 3.0 AND valid mapped box) + `cv` 6 clips x n=2 = **13 legs**, dirs
`runs/cv_<clip>_r<rep>/`.

## Scoring + verdict rules (frozen before any run)

Per clip: PASS = `genuine_lock` AND coverage >= 0.50, better of n=2. Primary arm `cv`.

- **YES**: cv >= 4/6 PASS, OR cv >= 3/6 matching E20's cell PASSes exactly (car9,
  car10, car14) — automation that fully preserves the operator result is a win even
  at 3/6.
- **PARTIAL**: 2-3/6 not matching E20's PASS set.
- **NO**: <= 1/6, or Phase-0 gate failure (report as NO [prior-insufficient] with the
  hit table).
- Suffix **[prior-wrong]** if a wrong prior cell produces an accepted garbage lock on
  any clip (the E20 wrong-probe failure mode, now automated).
- **Regression guard**: no clip's cv coverage may fall > 0.10 below its E18 A-leg best
  (car3 0.976, car7 0.285, car9 0.993, car10 1.000, car14 0.903, car18 0.711).

## Pre-registered estimates (marked as estimates)

- Phase-0 t=0 hit rate: **4/6** (red clips hit via motion+colour; car7 silver and
  car9 white lean on motion alone — car9's large target likely survives, car7's
  small-high target is the likely miss).
- If the gate passes: **cv ~3/6 PASS** (preserving E20's set where the prior is
  right, full-frame fallback elsewhere), mean acquire_s ~1.6-2.1 s on prior-hit
  clips, ~4.9 s on fallback clips.
- prior_ms: < 30 ms at width 320.

## Execution plan (for the executor)

1. Branch `experiment/cv-proposal-acquire` off main (E20 — and E21 if run first —
   already merged). Confirm the launch gate. `scope.py` selfcheck green.
2. Write `proposals.py` + offline selfcheck; commit. Run **Phase 0**; commit the hit
   table; apply the gate. If the gate fails: skip to step 6 with the negative result.
3. Write `replay_e22.py` (fork E20's replay_e20.py, localised diff); `--selfcheck`
   green; commit. Record `raw/jetson-power.txt`.
4. Smoke leg + sanity; then the 13-leg matrix, logging to `raw/matrix.log`.
   **CRITICAL ANTI-STALL RULE: never end your turn to "wait" (three executors have
   stalled doing this — E19 twice, E20 once). Poll `runs/*/results.json` in a
   foreground loop until 13/13 and continue straight through.**
5. `summarize.py` (per-clip table + prior hit/source table + latency), proof clips
   (2-3, committed, captioned; at minimum: a prior-hit clip side-by-side vs E18-A,
   and the most instructive prior failure or fallback).
6. Fill Results below; apply verdict rules mechanically; append ledgers
   (`docs/{results,questions,decisions}/part4-end-to-end.md`, RQ-E22, D1-D5). Madrid
   wall-clock timestamps `YYYY-MM-DDThh:mmZ`; no emojis.
7. Commit per convention (results.json + phase0 audit + proof committed; data/ +
   overlays gitignored; trailer block from your orchestrator). **Never push, never
   merge to main, never commit on main.**
8. Final message = completion report: Phase-0 table, verdict, per-clip table, prior
   hit/source stats, latencies, breakages, `git log --oneline main..HEAD`.

## Results (TBD)

Phase-0 prior audit (t=0 / t=10s cell vs GT): TBD (6x2 table).

| clip | kw | E18 A best | E20 cell best | prior hint ok? | prior source | cv r1 | cv r2 | cv best PASS? | acquire_s |
|---|---|---|---|---|---|---|---|---|---|
| car3 | red | F / 0.976 | F / 0.982 | | | | | | |
| car7 | silver | F / 0.285 | F / 0.997 | | | | | | |
| car9 | white | F / 0.993 | **P** / 0.996 | | | | | | |
| car10 | red | **P** / 1.000 | **P** / 1.000 | | | | | | |
| car14 | red | F / 0.903 | **P** / 0.907 | | | | | | |
| car18 | red | F / 0.711 | F / 0.981 | | | | | | |

Verdict: TBD. Estimate-vs-actual: TBD. What broke / what surprised: TBD.
