# E23 tolerant-cell sizing (pre-registered 2026-07-04T16:20Z)

**Status: PRE-REGISTERED, not yet run.** Final Part IV experiment. Self-contained
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

## Results (TBD)

Phase-0 cell sweep (HW -> worst-case containment /6, mean crop area frac): TBD.
HW\*: TBD.

| clip | true hint | fuzzed hint | E18 A best | E20 cell best | tol r1 | tol r2 | tol best PASS? | acquire_s |
|---|---|---|---|---|---|---|---|---|
| car3 | bottom left | TBD | F / 0.976 | F / 0.982 | | | | |
| car7 | top center | TBD | F / 0.285 | F / 0.997 | | | | |
| car9 | bottom center | TBD | F / 0.993 | **P** / 0.996 | | | | |
| car10 | center | TBD | **P** / 1.000 | **P** / 1.000 | | | | |
| car14 | center | TBD | F / 0.903 | **P** / 0.907 | | | | |
| car18 | middle left | TBD | F / 0.711 | F / 0.981 | | | | |

Verdict: TBD. Estimate-vs-actual: TBD. What broke / what surprised: TBD.
