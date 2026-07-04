# E20 prompt-scoped acquire (2026-07-04)

**Status: PRE-REGISTERED, ready to run.** Branch `experiment/prompt-scoped-acquire`.
Pre-registered 2026-07-04T11:35Z, before any run.

## Context

E18 (`experiments/2026-07-03-real-video-replay/`) measured the sim-to-real binder: the
~4.85 s blocking full-frame VLM acquire returns a box correct for the frame the model
SAW, but the target moves ~146 frames before arrival, so the lock lands STALE (A-leg
1/6). E19 (`experiments/2026-07-04-motion-comp-acquire/`) showed bolt-on compensation
does not close it: FLOW is catastrophic when wrong, BUF repairs coverage but cannot
flip the arrival-frame lock metric. The remaining honest axis is **raw acquire
latency** — and prefill cost scales with image area (ROI campaign, 2026-06-26:
M=2.0@512 crop = 2.7x cheaper prefill AND +22.6pp IoU). First acquire never got that
win because it has no location prior.

E20's prior is the **operator's own phrase**. The UX contract becomes
"object [place on screen]" — e.g. "the red car in the bottom left". The spatial part
is parsed client-side into a padded 3x3-cell crop; the VLM grounds the frozen caption
inside the crop; the box maps back to full-frame coords. Latency falls with crop area;
the target is also LARGER in the (un-downscaled) crop, which the ROI data says helps.

## RQ-E20

Does prompt-scoped cell-crop acquire cut acquire latency enough to flip E18's stale
locks into genuine arrival-frame locks — under the unchanged E18 metric?

## Arms

| arm | acquire behaviour |
|---|---|
| `cell` | first ACQUIRE attempt on the padded 3x3 cell named by the hint; retries + REGROUND full-frame; `--mc none` |
| `cellbuf` | `cell` + E19 BUF catch-up (submit-frame init, catch-up stride 12 at 6.15 Hz) — the composition leg |
| `wrong` | `cell` with a deliberately wrong hint (car10, "top left") — fallback/robustness probe, observational |

Control = E18 A-leg + E19 `--mc none` ctl runs (byte-equivalent acquire path). **No new
ctl runs** (D6).

## Decisions

- **D1 — hint consumed client-side.** The caption sent to the VLM stays the frozen E18
  caption (e.g. "the red car"); the spatial phrase only selects the crop. Keeps the VLM
  input distribution comparable to E18/E19; the crop already encodes the place.
- **D2 — halves not matrixed.** On 720p under the max_side=1024 cap, a half crop is
  ~553k px vs the 590k px the full frame is resized to — a ~1.1x "saving", no lever.
  The half grammar exists in `scope.py` for completeness; spending 12 runs on a
  pre-registered dead arm is waste. Given up: a direct test of the loosest hint.
- **D3 — pad = 10% of frame W/H per side** (`scope.PAD_FRAC`). A raw 1/3 cell cuts
  boundary-straddling targets (car14's frame-0 box crosses the col boundary by ~4 px).
  The selfcheck asserts every clip's frame-0 GT box is inside its padded cell.
- **D4 — scope applies to the FIRST ACQUIRE attempt only.** The hint is a statement
  about t=0. Any invalid/unparseable scoped result falls back to full-frame on the next
  attempt, and REGROUND is always full-frame — so the floor is exactly E18 behaviour.
- **D5 — wrong-hint probe is observational.** A VLM asked for "the red car" in a crop
  that doesn't contain it may hallucinate a box; there is no client-side defense at
  ACQUIRE (the mask gate has no template yet). The probe quantifies the UX-contract
  risk; we do not engineer around it in E20.
- **D6 — reuse controls.** E19 reproduced E18's ctl exactly on this identical code
  path; re-running 12 ctl legs buys nothing.
- **D7 — max_side cap unchanged (1024), crops sent native (no resize up or down).**
  Single knob (crop area) so the attribution is clean. Given up: a `cell@512` arm that
  would trade precision for more speed — E21 explores the resolution axis if needed.

## Pre-registered geometry + estimates (marked as estimates)

Full-frame path: 1280x720 -> 1024x576 = 590k px, measured ~4.85 s wall (E18).
Fitting the ROI campaign's 2.7x-cheaper ~2.0 s anchor: fixed cost ~0.35 s, prefill
~4.5 s. Padded cells for the six hints: 173k–262k px (2.25–3.4x fewer):

- **Est. scoped acquire wall: ~1.7–2.3 s** -> backlog ~50–70 frames (vs ~146).
- **Est. cell arm: 3/6 clips flip to PASS** (genuine lock needs IoU>=0.25 at the
  arrival frame; slower/larger targets flip, fast small ones may still miss).
- **Est. cellbuf: same genuine_lock as cell, coverage >=0.85 on 6/6** (BUF's repair,
  per E19).
- **Est. wrong probe: hallucinated box in the wrong cell on >=1/2 reps** (E19-FLOW-style
  fragility, now at the UX layer).

## Frozen config

Everything not named above is byte-identical to E19: Qwen2-VL-2B Q8_0 terse on Jetson
(`JetsonBackend`, max_side 1024, 15W + jetson_clocks), SAM2.1-hiera-tiny StreamCarry at
the 6.15 Hz E1 cap, E14/E16 mask gate (app_tau 12.0), LOSS_S 1.0, BUF_K 12, wall-clock
frame-drop replay + E18 scorer (`score_run`, lock_iou 0.25, native 30 fps GT). Clips +
captions frozen from E18: car3/car14/car18/car10 "the red car", car9 "the white car",
car7 "the silver car".

Per-clip hints (derived from frame-0 GT centroid via `scope.hint_for`, asserted in the
selfcheck): car3 "bottom left", car7 "top center", car9 "bottom center", car10
"center", car14 "center", car18 "middle left".

## Matrix (27 runs)

smoke: `cell` car10 x1 (plumbing). Then `cell` 6 clips x n=2, `cellbuf` 6 x n=2,
`wrong` car10 x n=2. Per-run isolation: fresh subprocess, Jetson server self-boot
(E18/E19 convention). Run dirs `runs/{cell,cellbuf,wrong}_<clip>_r<rep>/`.

## Scoring + verdict rules (frozen before any run)

Per clip: PASS = `genuine_lock` (first accepted box IoU>=0.25 vs GT at arrival frame)
AND `coverage` >= 0.50; clip takes the better of its n=2 reps. Primary arm = `cell`.

- **YES**: cell >= 4/6 PASS.
- **PARTIAL**: cell 2–3/6.
- **NO**: cell <= 1/6.
- Suffix **[hint-fragile]** if the wrong probe produces an accepted wrong-cell lock
  (cov < 0.25 on either rep).
- **Regression guard**: no clip's cell-arm coverage may fall > 0.10 below its E18
  A-leg best; a breach marks the arm REGRESSIVE regardless of locks.
- `cellbuf` reported as the composition row (same PASS rule) — it tests whether the
  residual ~60-frame staleness is small enough for BUF to erase within the metric.

Latency is measured per submit in `mc_log` (`acquire_s` = (arrival_i − submit_i)/fps):
report the scoped-acquire mean vs E18's ~4.85 s.

## Code

- `scope.py` (COMMITTED, selfcheck green): `REGIONS` grammar (3x3 cells + halves),
  `crop_rect(hint, w, h)` padded+clamped pixel rect, `hint_for(box, w, h)` honest
  phrase from frame-0 GT, `map_back(box, rect)`.
- `replay_e20.py` (EXECUTOR WRITES): fork of `../2026-07-04-motion-comp-acquire/replay_e19.py`
  with changes LOCALISED to acquire submission:
  - CLI: `--scope-hint <phrase>` (optional; must be a `scope.REGIONS` key), `--mc
    {none,buf}` (drop flow), rest unchanged.
  - `submit(frame_bgr, rect=None)`: with rect, crop `frame[y0:y1, x0:x1]`, write the
    CROP to /dev/shm, call `vlm_acquire(be, path, caption, cw, ch)` with the **crop's**
    w,h, then `scope.map_back` to full-frame coords before returning. Without rect,
    byte-identical to E19.
  - In `replay()`: ACQUIRE state uses `rect = crop_rect(hint, w, h)` on the FIRST
    attempt only; any retry and all REGROUND submits pass `rect=None` (D4). `_valid`
    checks against the full frame shape (box is already mapped back).
  - `mc_log` entries gain `"scoped": bool, "rect": rect|None, "acquire_s":
    round((arrival_i - submit_i)/fps, 2)`.
  - Extend the E19 selfcheck: (a) scoped path — stub submit asserts it received the
    crop dims and the returned box comes back offset by the rect origin; (b) fallback —
    first scoped submit returns None, second attempt arrives with rect=None; (c) buf
    composition path still terminates. Keep the E19 checks passing unchanged.
- `run_matrix.py` (EXECUTOR WRITES): E19 pattern; hints from `scope.hint_for` applied
  to the frozen table above (hardcode the table, assert it matches `hint_for` on the
  frame-0 GT at startup); `wrong` runs pass `--scope-hint "top left"` on car10.
- `summarize.py`, `make_proof.py` (EXECUTOR WRITES): E19 pattern. Proof clips (2–3,
  committed under `proof/`, captioned in Results): at minimum one E18-stale vs
  E20-cell side-by-side on a flipped clip, and the wrong-probe behaviour.

## Execution plan (for the executor)

1. `git log --oneline -3` on branch `experiment/prompt-scoped-acquire`; run
   `scope.py` selfcheck.
2. Write `replay_e20.py`, run `--selfcheck` until green. Commit.
3. Record Jetson power state into `raw/jetson-power.txt` (`ssh jetson "sudo nvpmodel -q; sudo jetson_clocks --show"`).
4. Smoke run (`cell` car10). Sanity: scoped `acquire_s` < 3.5 s and a valid mapped
   box, else STOP and diagnose before the matrix.
5. Full matrix via `run_matrix.py` under `nohup`/background with per-leg logging to
   `raw/matrix.log`. **Do not end your turn to "wait"** — poll the run count in a loop
   from within your session until 27/27 (the E19 executor stalled twice doing this;
   don't repeat it).
6. `summarize.py` -> per-clip table; apply the frozen verdict rules mechanically.
7. Fill this README's Results section (per-clip table, latency table, estimate-vs-
   actual, what broke/surprised, 2–3 captioned proof clips). Append ledger rows:
   `docs/results/part4-end-to-end.md`, `docs/questions/part4-end-to-end.md` (RQ-E20 +
   one-line verdict), `docs/decisions/part4-end-to-end.md` (D1–D7 summary). Timestamps
   in Madrid wall-clock `YYYY-MM-DDThh:mmZ`. No emojis.
8. Commit per convention: results.json COMMITTED, `data/` + `runs/*/overlay.mp4`
   gitignored (copy E19's `.gitignore`), proof clips COMMITTED. Trailers:
   `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` +
   `Claude-Session: https://claude.ai/code/session_012TGniwau8FeL31gVg1BCnC`.
   **Never push. Never merge to main** — the parent session audits and merges.

## Results (TBD)

| clip | hint | E18 A best (gen/cov) | cell r1 | cell r2 | cell best PASS? | cellbuf best PASS? | scoped acquire_s |
|---|---|---|---|---|---|---|---|
| car3 | bottom left | F / 0.976 | | | | | |
| car7 | top center | F / 0.285 | | | | | |
| car9 | bottom center | F / 0.993 | | | | | |
| car10 | center | **P** / 1.000 | | | | | |
| car14 | center | F / 0.903 | | | | | |
| car18 | middle left | F / 0.711 | | | | | |

Wrong probe (car10, "top left"): TBD.
Verdict: TBD. Estimate-vs-actual: TBD. What broke / what surprised: TBD.
