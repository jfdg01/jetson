# E23 tolerant-cell sizing (pre-registered 2026-07-04T16:20Z)

**Status: COMPLETE (2026-07-04T17:41Z) — RQ-E23 NO (REGRESSIVE) [containment-not-sufficient].
See `## Results` below.** Final Part IV experiment. Self-contained
handoff: a fresh session should run this from this file alone. Arc context:
`experiments/HANDOFF-acquire-arc.md` (acquire arc, now CLOSED). This campaign is a
UX-hardening coda to E20, not part of the acquire-latency arc.

## Motivation (operator, 2026-07-04)

E20's crop grammar (`experiments/2026-07-04-prompt-scoped-acquire/scope.py`) quantises
the operator's phrase to a rigid 3x3 grid of exact thirds: a target centroid at 34%
of frame width is classed "center" (0.34 > 1/3), yet a real operator would call it
"left" -- 34% is reasonably close to the left edge. The grid is **too cagey**: it
demands the operator agree with a geometric third to the pixel. Real coarse spatial
language ("left", "center") spans a generous, overlapping band. E23 asks: **make the
cells bigger than 1/9 of the screen (overlapping) so a casual operator phrase still
crops the target -- and find how big they must be before the latency win erodes.**

## RQ-E23

How large must the acquire crop cells be to absorb realistic operator boundary-fuzz
(a target near a cell edge named one cell over) without regressing E20's acquire
win (its PASS set and its sub-staleness latency)?

## The knob: overlapping cells with a single half-width HW

Replace E20's `third + fixed pad` with one parameter. Cells are centered windows on
each axis at centers `{1/6, 3/6, 5/6}`; a cell spans `[center - HW, center + HW]`
(fraction of axis), clamped to the frame. `HW` is the half-width knob.

- **E20-equivalent HW = 1/6 + 0.10 = 0.2667** (a third's half-width 1/6 plus E20's
  0.10 pad). This makes E23 a clean superset: HW=0.2667 reproduces E20's crop.
- HW = 0.50 -> each cell is a frame-half centered on its third (e.g. left col =
  [0, 0.667]); heavy overlap, big crop.
- Cells OVERLAP for HW > 1/6, which is the point: a boundary target lands inside more
  than one cell, so an operator naming either neighbour still crops it.

`hint_for` (the true cell = centroid's nearest third) is UNCHANGED -- it is the
ground-truth cell. What changes is (a) the crop size for a given hint, and (b) that
we now score against a FUZZED operator, below.

## Fuzzy-operator model (frozen, tau = 0.10)

The load-bearing modelling choice. A real operator uses generous, overlapping edge
terms. Model: on each axis the set of **plausible phrasings** for a centroid is every
term whose third-band, expanded by `tau = 0.10` on each side, contains the centroid:

- col plausible: `left` if cx < 1/3 + tau; `right` if cx > 2/3 - tau; `center` if
  1/3 - tau < cx < 2/3 + tau. (A centroid in an overlap has >= 2 plausible cols.)
- row plausible: same with cy and top/middle/bottom.

`tau = 0.10` = "coarse human spatial terms span ~10% of the axis beyond the geometric
third." Frozen; sensitivity to tau in {0.05, 0.15} reported offline, not swept
on-device. The **worst-case phrasing** for a clip = the plausible (row,col) whose
cell is most edge-ward from the true cell (the hardest for a crop to contain) -- that
is what the on-device leg uses.

Frame-0 centroids (from `scope.py` GT, 1280x720) and their fuzz exposure:

| clip | cx | cy | true cell | plausible cols (tau=0.10) |
|---|---|---|---|---|
| car3 | 0.321 | 0.727 | bottom left | left (near 1/3 boundary) |
| car7 | 0.436 | 0.097 | top center | center |
| car9 | 0.382 | 0.727 | bottom center | left, center (0.382 < 0.433) |
| car10 | 0.515 | 0.412 | center | center |
| car14 | 0.347 | 0.394 | center | left, center (the 34% example) |
| car18 | 0.243 | 0.427 | middle left | left |

car9 and car14 are the fuzz-sensitive clips: true "center" but an operator would
plausibly say "left". car3 sits just left of the 1/3 line. car7/car10/car18 are
unambiguous.

## Design

### Phase 0 -- offline containment/latency sweep (FREE, the primary deliverable)

For each `HW` in a sweep and the frozen fuzzy operator, compute per clip:
- **contained?** does the `HW`-crop for a plausible phrasing contain the WHOLE
  frame-0 GT box? Report the containment rate over all (clip x plausible-phrasing)
  pairs, and separately the worst-case-phrasing containment (6 clips).
- **crop area** as a fraction of the 1024-cap full frame (latency proxy; E18/E20
  established area drives prefill/acquire latency).

Sweep `HW` in `{0.2667 (E20), 0.32, 0.38, 0.44, 0.50}`. Define:
- **HW\*** = the smallest HW with 100% worst-case containment on all 6 clips.
- Report E20's HW (0.2667) worst-case containment -- expected < 100% (this quantifies
  "too cagey"); if it is already 100%, that is itself the result: E20's pad already
  tolerates realistic fuzz and no bigger cell is needed (record and reconfirm on
  device, do not chase a bigger size).

Write the sweep table to `raw/phase0_cell_sweep.txt` and commit it.

### On-device confirmation (gated on Phase 0)

Run **HW\*** (or E20's HW, if it was already 100%) on the 6 clips, n=2, using each
clip's **worst-case fuzzed hint**, exact E20 pipeline otherwise. Measure PASS +
`acquire_s`. Compare to E20's COMMITTED results table (do not re-run E20). 13 legs
(smoke `car10` x1 + 6 clips x n=2), dirs `runs/tol_<clip>_r<rep>/`. This confirms the
chosen cell size (a) still locks under a casual/fuzzed phrase and (b) has NOT
reintroduced staleness.

Fallbacks/floor mirror E20: invalid crop -> full-frame submit; REGROUND full-frame.

## Decisions

- **D1 -- single half-width knob HW (overlapping cells), HW=0.2667 reproduces E20.**
  One variable, clean sweep, E20 is the HW floor. Given up: separate footprint+pad
  knobs (two-dimensional, no cleaner).
- **D2 -- fuzzy operator frozen at tau=0.10**, worst-case phrasing on device. The
  honest test of "casual operator"; tau sensitivity reported offline only. Given up:
  a learned/empirical operator distribution (no data; tau is the documented proxy).
- **D3 -- Phase 0 (offline) picks the size; on-device only confirms it.** Containment
  and crop area are geometric and free; only lock-success + real acquire_s need
  Jetson. Burning legs across the whole HW sweep would re-measure a geometric fact.
  Given up: an on-device size sweep.
- **D4 -- score against E20's COMMITTED table, do not re-run E20.** The rig is
  near-deterministic (greedy decode); E20's numbers stand as the baseline.

## Scoring + verdict rules (frozen before any run)

Per clip: PASS = `genuine_lock` AND coverage >= 0.50, better of n=2. Arm `tol` at HW\*.

- **YES**: at HW\*, fuzzed-hint PASS set is a SUPERSET of E20's {car9, car10, car14}
  AND mean `acquire_s` < 3.0 s (staleness budget: has not collapsed toward E18's
  ~4.85 s). I.e. bigger tolerant cells absorb the fuzz for free.
- **PARTIAL**: PASS set preserves >= 2 of E20's three but drops one, OR mean
  acquire_s in [3.0, 4.0) s (tolerance bought at a real latency cost).
- **NO**: PASS set drops >= 2 of E20's three, OR mean acquire_s >= 4.0 s (bigger
  cells reintroduced E18 staleness -- the tolerance is not free), OR Phase 0 shows no
  HW < 0.50 reaches 100% containment (cells cannot be made both tolerant and small).
- Suffix **[already-tolerant]** if Phase 0 finds E20's HW (0.2667) already 100%
  worst-case containment -- then the deployed grammar needs no change and the
  on-device leg merely reconfirms E20.
- **Regression guard**: no clip's `tol` coverage may fall > 0.10 below its E18 A-leg
  best (car3 0.976, car7 0.285, car9 0.993, car10 1.000, car14 0.903, car18 0.711).

## Pre-registered estimates (marked as estimates)

- E20 HW worst-case containment: est. **4/6** (car9, car14 fuzzed to "left" may
  escape the 0.433 right edge of E20's padded left crop; car3 near-boundary marginal).
  If instead 6/6, verdict carries [already-tolerant] and E23 becomes a confirmation.
- HW\*: est. **~0.38** (100% containment; crop area still ~0.4-0.5 of full frame).
- On-device at HW\*: est. **PASS superset holds** (car9/car10/car14 preserved; the
  size-bound fails car3/car7/car18 stay failed -- E20's residual fails are
  target-size bound, NOT crop-bound, so a bigger cell will not recover them and is
  not expected to), mean acquire_s est. **~2.0-2.6 s** (bigger crop than E20's ~1.85
  but well under staleness) -> **YES**.
- prior: bigger cells are a UX win (operator can be casual) at a modest latency cost;
  the interesting number is the acquire_s vs HW curve -- where casualness starts
  costing staleness.

## Code (executor writes; keep diffs localised)

- `cells.py` (in this dir): the HW-parameterised overlapping grammar. `crop_rect(hint,
  w, h, hw)`, `regions(hw)`, and `plausible_hints(box, w, h, tau)` +
  `worst_hint(box, w, h, tau)` (the fuzzy operator). IMPORT `map_back` and the true
  `hint_for` from E20's `scope.py` (do not copy). Offline selfcheck: (a) HW=0.2667
  crop_rect == E20 scope.crop_rect for all 9 cells (superset check); (b) car14's
  plausible cols == {left, center} at tau=0.10; (c) a known box contained by its
  worst_hint crop at HW=0.44 but NOT at HW=0.2667 (proves the knob does something).
- `phase0.py`: the offline sweep -> `raw/phase0_cell_sweep.txt` + a small
  containment-vs-area plot `proof/cell_sweep.png`. Picks HW\* (or flags
  [already-tolerant]).
- `replay_e23.py`: fork of `experiments/2026-07-04-prompt-scoped-acquire/replay_e20.py`;
  ONLY change in acquire submission: use `cells.crop_rect(worst_hint(...), w, h, HW)`
  in place of E20's `scope.crop_rect(hint, ...)`. CLI `--hw` (default 0.2667 =
  E20-equivalent), `--fuzz/--tau` (default 0.10). `mc_log` gains `"hw", "true_hint",
  "fuzzed_hint", "acquire_s"`. Extend selfcheck (HW=0.2667 path byte-equivalent to
  E20; fuzzed path picks worst_hint). Selfcheck offline.
- `run_matrix.py`, `summarize.py`, `make_proof.py`: E20/E21 pattern.

## Execution plan (for the executor)

1. Branch `experiment/tolerant-cells` off main is ALREADY created + checked out (do
   not re-branch). Confirm E20's `scope.py` selfcheck still green.
2. Write `cells.py` + selfcheck (green offline); commit. Run `phase0.py`; commit
   `raw/phase0_cell_sweep.txt` + the plot; determine HW\* (or [already-tolerant]).
3. Write `replay_e23.py`; `--selfcheck` green; commit. `raw/jetson-power.txt` via
   `ssh jetson "sudo nvpmodel -q; sudo jetson_clocks --show"` (NOPASSWD).
4. Smoke leg (`car10` at HW\*, sanity: valid mapped box AND acquire_s < 3.5 s), then
   the 13-leg matrix at HW\* with worst-case fuzzed hints, log to `raw/matrix.log`.
   **CRITICAL ANTI-STALL RULE: never end your turn to "wait" (five prior executors
   stalled -- E19 x2, E20, E21). Poll `runs/*/results.json` in a FOREGROUND loop until
   13/13, then continue straight through to summarize + Results + ledgers + commits.**
5. Apply the frozen verdict rules mechanically; fill Results below (Phase-0 sweep
   table, per-clip table with E18-A + E20-cell columns + true/fuzzed hint + acquire_s,
   estimate-vs-actual, what broke/surprised, captioned proof).
6. Ledgers under Part 4 ONLY: `docs/results/part4-end-to-end.md`,
   `docs/questions/part4-end-to-end.md` (RQ-E23 + one-line verdict),
   `docs/decisions/part4-end-to-end.md` (D1-D4). If YES, a DECISIONS entry recommending
   the deployed cell grammar change (HW\* replacing E20's 0.2667). Madrid wall-clock
   `YYYY-MM-DDThh:mmZ`; no emojis.
7. Commit per convention (results.json + phase0 sweep + proof committed; data/ +
   overlays gitignored; copy E20's `.gitignore`; trailer block from the orchestrator).
   **Never push, never merge to main, never commit on main.**
8. Final message = completion report: Phase-0 sweep + HW\*, verdict, per-clip table,
   E20-HW-vs-HW\* containment contrast, mean acquire_s vs E20 1.85 / E18 4.85,
   breakages, `git log --oneline main..HEAD`.

## Results (2026-07-04T17:41Z)

**Status: COMPLETE. RQ-E23 = NO (REGRESSIVE) [containment-not-sufficient].**
Run date 2026-07-04. Jetson Orin Nano 8 GB, 15 W + jetson_clocks (`raw/jetson-power.txt`).
Backend Qwen2-VL-2B Q8_0, `max_side=1024`. Phase-0 offline; 13 on-device legs.

### Phase 0 -- offline cell sweep (`raw/phase0_cell_sweep.txt`, `proof/cell_sweep.png`)

Frame-0 GT, 1280x720, fuzzy operator tau=0.10. Worst-case = most edge-ward plausible cell.

| HW | worst-case containment /6 | all-phrasing rate | mean worst-case crop-area frac | note |
|---|---|---|---|---|
| 0.2667 | 2/6 | 11/19 | 0.364 | E20-equivalent |
| 0.3200 | 5/6 | 17/19 | 0.492 | |
| **0.3800** | **6/6** | **19/19** | **0.660** | **HW\*** |
| 0.4400 | 6/6 | 19/19 | 0.745 | |
| 0.5000 | 6/6 | 19/19 | 0.789 | |

Per-clip worst-case containment: car3/car7 contained at every HW; car9/car10/car14/car18
all escape E20's 0.2667 and are only contained at HW>=0.38 (car9 needs 0.38, the rest 0.32).
tau sensitivity: at tau=0.05 even E20's HW is 6/6; at tau>=0.10 E20 collapses to 2/6, HW*=0.38
holds 6/6 through tau=0.15.

**HW\* = 0.38** (smallest HW with 6/6 worst-case containment). **E20's HW (0.2667) worst-case
containment = 2/6** -- NOT [already-tolerant]; E20's grid IS too cagey under tau=0.10 fuzz
(worse than the estimated 4/6).

### On-device -- HW\*=0.38, worst-case fuzzed hints, n=2 (`raw/matrix.log`)

PASS = `genuine_lock` AND coverage >= 0.50, better of n=2. E18-A / E20-cell columns are the
committed baselines (not re-run).

| clip | true hint | fuzzed hint | E18 A best | E20 cell best | tol r1 | tol r2 | tol PASS? | acquire_s |
|---|---|---|---|---|---|---|---|---|
| car3 | bottom left | center | F / 0.976 | F / 0.982 | F / 0.901 | F / 0.898 | **FAIL** | 3.93 |
| car7 | top center | top center | F / 0.285 | F / 0.997 | F / 0.286 | F / 0.283 | **FAIL** | 2.67 |
| car9 | bottom center | middle left | F / 0.993 | **P** / 0.996 | F / 0.988 | F / 0.985 | **FAIL** | 2.83 |
| car10 | center | top center | **P** / 1.000 | **P** / 1.000 | F / 0.000 | F / 0.000 | **FAIL** | 2.67 |
| car14 | center | top left | F / 0.903 | **P** / 0.907 | **P** / 0.916 | **P** / 0.916 | **PASS** | 2.10 |
| car18 | middle left | top center | F / 0.711 | F / 0.981 | F / 0.984 | F / 0.987 | **FAIL** | 2.63 |

- tol PASS set = **{car14}** (1/6). E20 PASS set to preserve {car9, car10, car14}: **kept 1/3**.
- mean scoped `acquire_s` = **2.80 s** (n=12, min 2.10 max 3.93) vs E20 1.85 / E18 4.85.
- Regression guard vs E18-A best coverage: **car10 BREACH** (tol cov 0.000 vs E18-A 1.000);
  others within 0.10 (car3 -0.075, car7 +0.001, car9 -0.005, car14 +0.013, car18 +0.276).

### Verdict

Frozen rules -> superset FALSE (kept 1/3, drops car9 AND car10 = drops >=2) -> **NO**; plus the
car10 regression breach -> **NO (REGRESSIVE)**. mean acquire_s 2.80 s is inside budget (<3.0),
so latency is NOT the binder -- containment is.

### Estimate-vs-actual

| field | estimate | actual | note |
|---|---|---|---|
| E20 HW worst-case containment | 4/6 | **2/6** | E20 more cagey than expected |
| HW\* | ~0.38 | **0.38** | exact |
| tol PASS superset preserved | YES (car9/car10/car14) | **NO, kept only car14** | the core miss |
| mean acquire_s | 2.0-2.6 s | **2.80 s** | slightly over; not the binder |
| verdict | YES | **NO (REGRESSIVE)** | prior wrong: bigger cell != recovers the PASS |

### What broke / what surprised

**Geometric containment is necessary but NOT sufficient for a lock.** Phase-0 guaranteed HW*=0.38
crops geometrically contain the frame-0 GT box for every worst-case phrasing (6/6), yet on device
only car14 locked. Two distinct failure modes, neither visible offline:

1. **Enlarged crop admits a decoy (car10, the regression).** E18's full-frame acquire LOCKED
   car10 (genuine, cov 1.00). The worst-case fuzz pushes "center" -> "top center", whose HW*=0.38
   crop is a wide top band that still contains the target but now also contains a *second red car*.
   The VLM grounds the decoy (mapped box far from GT, cov 0.000, 9-10 REGROUND gate rejects =
   E20-style poisoned template). A bigger tolerant cell trades E20's cageyness for distractor
   exposure. Proof: `proof/car10_E18_vs_E23tol_regression.mp4`.
2. **Staleness binder unchanged (car3/car9/car18).** These reach high coverage (0.90-0.99) --
   the crop DID contain the target and carry tracks it -- but `genuine_lock` is FALSE because the
   ~2.8 s acquire still lands *after* the arrival frame on a moving target. This is exactly E18's
   acquire-latency-vs-motion binder; a fuzz-tolerant crop does nothing to it. Proof:
   `proof/car9_E23tol_stale.mp4`.

car14 (true "center", fuzzed "top left") is the lone survivor: E18-A had it stale (genuine FALSE),
E23's tolerant cell locks it fast (2.10 s, genuine, cov 0.92) -- the mechanism works when the
enlarged crop is distractor-free and the target is slow enough. Proof: `proof/car14_E23tol_survivor.mp4`.

Net: making cells tolerant to operator fuzz is not free. Enlarging the crop to absorb a casual
phrase re-imports the two problems the tight E20 cell was suppressing -- distractors (car10) and,
for moving targets, the acquire-latency staleness that E18 already pinned as the true binder.
E20's tight-cell latency win does NOT survive a realistic worst-case fuzzy operator. Operator
fuzz-tolerance and small distractor-free crops are in tension; closing it needs an appearance
gate on the acquire (not just a geometric one) or a faster acquire, not a bigger cell.

### Proof deliverables (`proof/`)

- `cell_sweep.png` -- Phase-0 containment (bars) vs mean worst-case crop-area frac (line) across
  the HW sweep; HW*=0.38 marked (containment / latency-proxy trade).
- `car10_E18_vs_E23tol_regression.mp4` -- **the negative result**: E18 full-frame locks car10
  (top), E23 HW*=0.38 worst-case 'top center' cell grounds the WRONG red car (bottom).
- `car9_E23tol_stale.mp4` -- HW*=0.38 'middle left' cell tracks (cov 0.99) but genuine_lock FALSE:
  the E18 acquire-staleness binder is untouched by fuzz-tolerance.
- `car14_E23tol_survivor.mp4` -- the lone clip the tolerant cell recovers (locks, genuine, 2.10 s).
