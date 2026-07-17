# P5.9 — Kerb-safe scene generator: calibrated spawn bands, G4b redefined, first scene bank

**Pre-registered:** 2026-07-17T15:44Z (Madrid wall-clock).
**Status: PRE-REGISTERED, not yet run.**
**Branch:** `experiment/kerbsafe-scenebank`.
**Division of labour:** design + patches by Fable; **Opus runs the matrix and fills
the Results section only — do NOT re-patch code.** All files under "Code changes"
are already committed. If a run crashes on an infra error, follow the abort
criteria below — never silently re-run a completed cell.

## Research question

**RQ-P5.9:** With spawn bands constrained to the *calibrated* kerb-safe corridor
(design-time sweep, this cycle: rendered-car integrity holds for lat ∈ [−5.5, +2.5]
at every station s ∈ [0, 70]; bands clamped to worst-case lat ∈ [−5.0, +1.8],
s ≤ 67.4) and the seed-diversity gate G4b redefined to measure whole-scenario
divergence (ruling below), does the generator (a) pass the full capability gate
including the new rendered-integrity gate G6, and (b) produce a 12-clip
pre-registered scene bank with zero clipping — the dataset the select arc needs?

Meeting ALL of (thresholds as numbers; G1/G2/G3/G5 byte-for-byte from P5.7/P5.8):

- **G0 completion** (per run): results.json present, 240/240 gt.jsonl frames,
  ≤ 12 failed-then-recovered service calls.
- **G1 render-alive** (per run): 0 dead frames (std ≤ 5), 0 byte-identical
  consecutive frames, camera sim-stamps advance exactly 40 ms per frame.
- **G2 GT-on-vehicle** (per run, both cars): median in-box colour purity ≥ 0.30
  AND ≥ 4× the lateral control-box purity.
- **G3 co-visibility** (per run): both cars bbox area ≥ 150 px in ≥ 80% of frames.
- **G5 throughput** (per run): ≥ 0.5 generated frames/s wall.
- **G6 rendered integrity (NEW — the mechanical anti-clipping gate):** per car,
  p10 of per-frame frag (largest-connected-component fraction of car-colour
  pixels in the padded GT box) **≥ 0.95** AND frac(frag < 0.90) **≤ 0.02** AND
  ≥ 200 scored frames. Calibrated on P5.8 data: clean runs p10 ≥ 0.996 /
  frac 0.000; the kerb-clipped P5.8 seed101 blue car p10 0.666 / frac 0.312 —
  wide separation on both sides of the gate. (Median alone would NOT have
  caught P5.8's defect — its median was 0.999; hence p10 + tail fraction.)
- **G4a determinism** (seed101_A vs seed101_D, fresh server session each):
  canonical GT (sim-stamps excluded) byte-identical AND frames mean |diff| ≤ 2.0
  with frac(|diff| > 8) ≤ 1%.
- **G4b seed diversity (REDEFINED — ruling in Context):** min pairwise
  whole-scenario divergence over the 15 pre-registered seeds ≥ **1.0 m**, where
  divergence(a,b) = mean over 240 frames of mean(|Δtarget|, |Δdistractor|,
  |Δcam|); PLUS recorded gt.jsonl f0 positions of every completed run must
  reproduce `author_scenario()` within 1e-3 m.
- **V visual gate** (operator, Read tool — see "Visual verification").

**Overall verdict: YES iff all 4 gate runs pass G0,G1,G2,G3,G5,G6 AND G4a AND
G4b AND ≥ 11/12 bank cells pass G0,G1,G2,G3,G5,G6 (≤ 1 cell lost to infra and
recorded as such; a present-but-gate-failing bank cell is a NO) AND V passes.**
`verdict_p59.py` computes all of this mechanically; V can only downgrade.

## Context & rationale (audit summary)

**P5.8 audit (adversarial, this cycle) — verdict CONFIRMED, diagnosis CONFIRMED,
with the audit's own re-derivations:**

- *Transport FIXED is real.* Independently re-verified from raw artifacts: all
  four `runs/*/results.json` show `retries_pose=0, retries_step=0,
  response_lost=0, proxy_restarts=0, spawn_warns=[]`; 240-line gt.jsonl per run.
- *G4a byte-identity is real and correctly claimed.* Canonical GT of seed101_A
  vs seed101_D: identical md5 (`da06f447…`), and raw frame PNGs at f0000/0060/
  0120/0180/0239 are md5-identical pairwise. (First hash attempt used a wrong
  filename pattern and trivially "passed" on empty strings — redone properly;
  recorded here as a reminder that verification code needs verifying.)
- *G4b birthday diagnosis is sound.* Recomputed independently: gating-triple
  pairwise f0 distances 0.863/0.695/0.215 m (matches); 2000 random 3-seed
  triples over seeds 1–120 pass the old gate only 73.8% of the time (executor:
  74.6%, different RNG — same conclusion), median min-pairwise 1.53 m. A ~25%
  false-failure rate confirms the old gate measured seed luck, not generator
  capability.
- *The kerb defect is real, worse than "caveat" reads, and P5.8's V-frames
  under-sold neither.* Viewed directly: at f0180 the P5.8 seed101 blue car is
  two disconnected blobs with the whole mid-body sunk below the kerb — as a
  grounding target for "the blue car" this frame is unusable. The executor's
  fix-before-use flag was correct.
- *One gap in P5.8's story:* the clean seeds 202/303 were only conditionally
  safe — their distractors rode lat ≤ 2.9 with s ≤ 53. This cycle's sweep shows
  lat 3.0+ starts failing at s = 70 and fully splits by lat 3.5–4.5 at s ≥ 50:
  the old band [1.5, 5.0] was unsafe for roughly half its width. P5.8's 2/3
  clean seeds were luck of the same kind G4b's triple was.

**Design-time calibration (this cycle, disclosed — all on the RTX 3090
workstation, gz 8.14.0, fresh servers, teardown via killserver `remaining: 0`):**

1. **Kerb sweep** (`probe_kerb.py` → `curation/kerb_sweep.json` +
   `kerb_heatmap.png` + `kerb_sample_*.png`): blue probe car over
   s ∈ {0,10,…,70} × lat ∈ [−8, +8] step 0.5, run-like oblique camera; per cell
   pixel-count ratio + largest-connected-component fraction. **Finding: the
   median kerb is NOT parallel to ROAD_HEADING=145°** — it converges from
   lat ≈ 7.5 at s=10 to ≈ 3.5 at s=70 (~4° skew). That is *why* P5.8's seed101
   clipped only late in the clip. Clean corridor: lat ∈ [−5.5, +2.5] at all
   s ≤ 70. A placement check at s≈71, lat +2.0 (`curation/placement_s65_*.png`)
   shows the car on the median paint and marginal — so the fix caps the
   s-envelope too (the old envelope reached s ≈ 76, past the calibrated range).
2. **G6 calibration on P5.8's stored frames** (numbers above): the metric
   separates clipped from clean by ≥ 0.33 in p10 — thresholds are set in the
   middle of a wide gap, not tuned to pass.
3. **Full-length design smoke, seed 101 on the fixed generator**
   (`curation/smoke101_fixed/`, frames trimmed, results + gt + overlays kept):
   240/240 at 8.28 fps, 0 retries, purity 0.824/0.766 (blue was 0.472 in P5.8),
   G6 p10 0.997/1.000, `overlay_f0180.png` viewed — **blue car intact on
   asphalt at the exact seed/frame that was two blobs in P5.8.**

**G4b ruling (the designer's call P5.8 deferred).** The old gate (min pairwise
target-f0 distance ≥ 1.0 m over a 3-seed triple) is **dropped** — it tests one
2-D point of a ~10-D scenario draw, and with 3 pairs its false-failure rate on
an arbitrary triple is ~25% (measured, twice). The *intent* — different seeds
must produce materially different scenes, i.e. the rig is a generator, not a
replayer — is legitimate and stays. The replacement measures that intent
directly: **whole-scenario divergence** (mean over all 240 frames of both cars'
and the camera's pairwise position distance), gated at min-over-pairs ≥ 1.0 m
across **all 15 pre-registered seeds** (105 pairs), plus a faithfulness
cross-check that recorded GT reproduces the authored scenario. Measured on the
new bands over seeds 1–120 (7140 pairs): min 1.15 m, p1 2.11 m, median 6.19 m —
**zero false failures observed in 7140 pairs**, while a degenerate seeding bug
(the failure class the gate exists to catch) would score ≈ 0 and fail loudly.
What is given up: sensitivity to two seeds coinciding at one instant — accepted,
because a single-frame coincidence between otherwise-diverging trajectories is
exactly the birthday noise that made the old gate wrong. **Honesty note: under
the new definition P5.8's triple would have passed (divergences 7.48/11.43/4.15
m ≥ 1.0), so this redefinition retroactively flips P5.8's failing gate.** That
is disclosed, deliberate, and grounded in third-party-checkable measurement —
the alternative (keeping a gate with a known 25% false-failure rate because
changing it looks self-serving) privileges appearance over measurement. The
old statistic is still reported per-run in Results as a non-gating diagnostic.

**Rejected alternative for the cycle:** skip the fix and resume P5.6 on the
P5.8-state generator ("two cycles of infra are enough"). Loser because the
defect is not cosmetic for a *select* experiment: a distractor that renders as
two blobs is precisely the "blue car" the phrase must bind to, seed101-class
spawns hit the old band's unsafe half broadly (lat ≥ 3.0 unsafe at high s), and
any select result on such scenes invites the reviewer's "your sim is broken"
dismissal. The fix cost is one design session (already spent) plus a ~25 min
matrix; the alternative risked a full wasted science cycle.

**P5.6 call (one line):** `experiment/direct-delivery-select` (`df6de31`)
**stays PARKED this cycle and resumes next cycle on this bank if RQ-P5.9 = YES**
— its contract-change hypothesis is still the live select lever, and the bank's
12 clips with per-object phrases/GT are built to be its scene source.

**Seed-selection procedure (pre-registered, mechanical, no cherry-picking):**
gating seeds stay {101, 202, 303} (continuity with P5.7/P5.8; 101 is the
regression seed). Bank seeds = the first 12 integers ≥ 1, ascending, that pass
two offline screens computed from `author_scenario` alone: (a) collision
screen — no frame with |Δs| < 5.0 m AND |Δlat| < 2.3 m between the two cars
(car AABB is 2.14 m wide × 4.0 m long); (b) accumulated divergence — adding the
seed keeps min pairwise divergence ≥ 1.0 m against gating seeds + already-
accepted bank seeds. **Result (computed at design time): seeds 1–12, no seed
skipped; min pairwise divergence over all 15 seeds = 1.36 m.** Same-seed
continuity vs P5.8: v_t/standoff/alt/aim are draw-order-identical (verified:
seed101 v_t 5.831, standoff 17.77, alt 16.31 match P5.8's results.json exactly;
only lat0/amp/s0_d rescale into the new bands and seed101's v_d hits the new
6.0 cap, was 6.5).

## Code changes (already committed — Opus: do NOT edit these files)

| File | Change |
|---|---|
| `runners/scenegen.py` | **kerb-safe bands (calibrated):** target lat0 U(−4.5, −2.2), distractor lat0 U(0.5, 1.3), sway amp U(0.2, 0.5) (was 0.7), distractor s0 U(4, 10) (was 14), v_d cap 6.0 (was 6.5) → worst-case lat ∈ [−5.0, +1.8] ⊂ LAT_SAFE (−5.2, 2.0), s ≤ 67.4 ≤ S_SAFE_MAX 70; `author_scenario` **asserts** the corridor per scenario so a band edit cannot silently regress. **G6 metric:** module-level `frag_metric()` (largest-CC fraction, pad 0.10, ≥ 30 px to score); per-frame `frag` in gt.jsonl; `g6_frag_p10/min/below090_frac/n` in results.json. **selfcheck** extended: frag_metric unit tests (solid blob = 1.0, split blob = 2/3, tiny → None) + 40-seed corridor sweep, all offline. |
| `experiments/2026-07-17-kerbsafe-scenebank/probe_kerb.py` | design-time (s, lat) integrity sweep (kept: reproduces `curation/kerb_sweep.json` + heatmap against a live server) |
| `experiments/2026-07-17-kerbsafe-scenebank/verdict_p59.py` | mechanical verdict: G0–G6 per run, G4a from the A/D pair, redefined G4b + faithfulness cross-check, bank rules, INCOMPLETE handling. Smoke-tested against the design-smoke run (prints a correct row + INCOMPLETE). |
| `experiments/2026-07-17-kerbsafe-scenebank/make_proof.py` | proof figures: before/after kerb fix, calibration heatmap, 12-clip bank grid, G6-has-teeth bars |
| `curation/*` | sweep + placement + smoke provenance (smoke frames/videos trimmed; results/gt/overlays kept) |

Self-check (no gz server, no GPU needed):
`.venv-ft/bin/python runners/scenegen.py selfcheck` → must print `scenegen selfcheck OK`.

## Run matrix (Opus starts here)

Config: **RTX 3090 workstation only — the Jetson is NOT used** (unchanged from
P5.7/P5.8: this campaign makes no on-device claim; the bank's consumers run on
the Jetson in later campaigns). gz sim 8.14.0 (Harmonic), Python 3.12.10 /
numpy 2.4.4 / cv2 4.13.0 via `.venv-ft`. No power-mode knob (desktop GPU,
stock clocks).

**16 runs, one fresh server session each** (session-per-run keeps G4a
cross-session and every bank clip independently reproducible):

| cell | SEED | RUN |
|---|---|---|
| gate | 101 | seed101_A |
| gate | 202 | seed202_B |
| gate | 303 | seed303_C |
| gate | 101 | seed101_D |
| bank | 1–12 | bank01 … bank12 (`bank%02d` = seed) |

Per run (**keep the `nohup gz sim` launch as its own clean background command —
do not fold it into `&&` chains (the sandbox reaper kills gz+python combos); the
recorder is a separate command**):

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-kerbsafe-scenebank
SEED=101 RUN=seed101_A   # <-- change per run, table above
mkdir -p $EXP/raw $EXP/runs

# 0. guarantee no stale server (kills by process group, verifies; exit 0 = clean)
.venv-ft/bin/python runners/scenegen.py killserver

# 1. fresh headless server, nohup'd alone
SITL=$PWD/runners/sitl/external/SITL_Models/Gazebo
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
GZ_SIM_RESOURCE_PATH="$SITL/models:$SITL/worlds" \
nohup gz sim -s runners/sitl/worlds/select_arena.sdf > $EXP/raw/gz_$RUN.log 2>&1 &

# 2. wait for the camera topic (~15-25 s world load)
for i in $(seq 40); do gz topic -l 2>/dev/null | grep -q uav_cam && break; sleep 3; done
gz topic -l | grep uav_cam   # MUST print the image topic; if empty after 120 s see aborts

# 3. record (~1 min at ~8.3 fps + finalize; DONE line + results.json at end)
nohup .venv-ft/bin/python runners/scenegen.py record --seed $SEED --frames 240 \
    --out $EXP/runs/$RUN > $EXP/raw/rec_$RUN.log 2>&1 &
for i in $(seq 60); do test -f $EXP/runs/$RUN/results.json && break; sleep 5; done
tail -5 $EXP/raw/rec_$RUN.log   # expect "[scenegen] DONE ..."
cat $EXP/runs/$RUN/progress.json  # retry counters for the Results table

# 4. kill this session's server (same verified process-group kill as step 0)
.venv-ft/bin/python runners/scenegen.py killserver
```

After all 16 runs:

```bash
# mechanical verdict (paste its full output into Results)
.venv-ft/bin/python experiments/2026-07-17-kerbsafe-scenebank/verdict_p59.py

# proof deliverables
.venv-ft/bin/python experiments/2026-07-17-kerbsafe-scenebank/make_proof.py
```

Gotchas: `killserver` is the only sanctioned kill (a pid-file kill records the
bash wrapper, not the ruby server, and orphans a live server that silently fakes
a "fresh session"); it must print `remaining: 0` — if it exits 1, run it again,
then `ps -ef | grep -i ruby`, kill the pgid by hand, and record that in Results.
`gt.jsonl`, overlays and `progress.json` are written incrementally — a crashed
run stays gradeable up to its crash frame. ~250 MB of frames per run land in
`runs/<RUN>/frames/` (gitignored; results.json + gt.jsonl are tracked). Disk
budget ≈ 4 GB. **Never delete a completed run dir.**

## Visual verification (gating — Opus MUST do this per the CLAUDE.md rule)

Open with the **Read tool**, before writing any verdict (**16 images minimum**):

- **Gate runs (4 × 3 = 12 images):** `runs/<RUN>/overlay_f0060.png`,
  `overlay_f0120.png`, `overlay_f0180.png` for seed101_A, seed202_B, seed303_C,
  seed101_D.
- **Bank runs (12 images):** `runs/bank<NN>/overlay_f0180.png` for all 12 —
  f0180 is the late-clip frame where kerb clipping was worst in P5.8, so it is
  the recurrence-sensitive frame. Additionally open all three overlays for the
  **two bank runs with the lowest per-run min of G6 frag p10** (from the verdict
  table) — the mechanically-selected worst cells get the full look.

**PASS looks like** (reference: `curation/smoke101_fixed/overlay_f0180.png`,
this campaign's fixed code, viewed at design time): grey asphalt with yellow
lane lines, oblique aerial view; **two cars — one white, one blue — each
rendered as ONE connected body sitting ON the asphalt**, wheels not sunk, body
not intersecting the raised kerb and not straddling the median paint; a green
GT box tight on each car (edges within ~10% of the silhouette) labelled
`id0 white` / `id1 blue`; across f0060→f0120→f0180 of one run the scene visibly
advances.

**FAIL looks like:** a car split into two or more disconnected colour blobs
(P5.8's defect — reference for what it looked like:
`../2026-07-17-scenegen-transport/runs/seed101_A/overlay_f0180.png`); a car
body partially sunk below kerb/ground; a car riding ON the median paint or kerb
line; black/single-colour frame; sky instead of ground; one car only or two
same-coloured cars; boxes floating off the vehicles; three identical frames.

Record one line per opened run in Results. **A missing PNG = that run is
INVALID — never a log-inferred pass.** If V fails on any run, the overall
verdict is NO even if `verdict_p59.py` prints YES; describe what the frames
show. If V and G6 disagree in either direction (V sees a split G6 passed, or
G6 fails a run whose frames look clean), that disagreement is a finding —
record it explicitly with the frame path.

## Verdict rules (mechanical — Opus does not deliberate)

- Run `verdict_p59.py`; its table + verdict is the G0–G6/G4a/G4b result. Do V
  yourself as specified. **Overall = YES iff verdict_p59 prints YES AND V
  passed on every opened run.**
- **Partial-run rule (pre-registered):** a run that dies mid-clip → snapshot
  `raw/*_$RUN.log` + `progress.json`, rename the dir
  `runs/<RUN>_attempt<N>_INVALID`, open whatever overlays exist (they are
  written mid-run) and describe them, then re-run that cell **once** with a
  fresh server. Second death of the same cell → **gate cell:** record `infra`
  FAIL; the matrix is INCOMPLETE and the overall verdict is NO [G0] with
  partial evidence documented. **Bank cell:** create `runs/<cell>.INFRA`
  (one-line reason inside), continue; ≤ 1 such cell is tolerated by the YES
  rule, ≥ 2 is NO.
- **Abort criteria:** no camera topic after 120 s → snapshot gz log,
  `killserver`, retry once fresh; twice → that cell INVALID/`infra`. No
  `progress.json` update for > 5 min or no `results.json` after 15 min →
  `killserver`, kill the recorder pid, snapshot logs, apply the partial-run
  rule. Never delete a completed run dir; never edit code.
- `verdict_p59.py` prints INCOMPLETE → the campaign stays INCOMPLETE until
  every cell has results.json or a recorded infra marker.

## Estimates (marked as estimates — one per gate, none treated as a formality)

- Per run ≈ 1.0–1.5 min (design smoke: 28.9 s record loop + ~20 s world load +
  finalize); matrix (16 runs, serial) ≈ 20–30 min; verdict + proof ≈ 5 min
  (G4a reads 480 PNGs, ~1 min).
- **G0:** PASS 16/16, 0 retries (P5.8: 0 in 1920 calls; smoke: 0). Any nonzero
  retry count gets a sentence in Results.
- **G1:** PASS 16/16, 0 dead / 0 identical / stamps exact (smoke: exact).
- **G2:** PASS 16/16; purity ≈ 0.70–0.90 per car (smoke 0.824/0.766; the old
  0.472 outlier was the clipping and should NOT recur — a bank purity < 0.6 on
  the blue car is a yellow flag to mention even if the gate passes).
- **G3:** PASS 16/16, both-visible = 1.000 (smoke 1.0).
- **G5:** PASS 16/16 at 8.0–8.5 fps (smoke 8.28).
- **G6 (new):** PASS 16/16, p10 ≥ 0.99 both cars (smoke 0.997/1.000) — the
  gate margin is ~0.04+; a p10 in [0.95, 0.99) passes but gets a sentence.
- **G4a:** PASS — byte-identical GT and frames mean |diff| = 0.0 (P5.8 measured
  exactly this at full scale; nothing in this patch touches transport or
  rendering). A nonzero diff would be a regression finding, not noise.
- **G4b (redefined):** PASS at 1.36 m ≥ 1.0 (computed offline at design time;
  the run only re-verifies + adds the faithfulness cross-check). A faithfulness
  failure would mean the recorder diverged from the authored scenario — grade
  it a hard NO and investigate, that is not a threshold issue.
- **V:** PASS 16/16 with no split/sunk/median-riding cars. The known residual
  risk: a bank seed placing the distractor near lat +1.8 at s ≈ 65+ sits ~0.5 m
  from the paint — "close to the line" is a PASS if the body is connected and
  on asphalt; note it in the run's V line.
- Disk ≈ 4 GB under `runs/` (gitignored). No new external assets → no SOURCES
  entry expected.

## Results (filled by Opus)

Run date/time: TBD. Versions: TBD (from results.json). Rig: TBD.

| run | seed | G0 (retries/lost/restarts) | G1 | G2 (pur0/pur1) | G3 | G5 fps | G6 (p10 id0/id1) | V (one line) |
|---|---|---|---|---|---|---|---|---|
| seed101_A | 101 | | | | | | | |
| seed202_B | 202 | | | | | | | |
| seed303_C | 303 | | | | | | | |
| seed101_D | 101 | | | | | | | |
| bank01 | 1 | | | | | | | |
| bank02 | 2 | | | | | | | |
| bank03 | 3 | | | | | | | |
| bank04 | 4 | | | | | | | |
| bank05 | 5 | | | | | | | |
| bank06 | 6 | | | | | | | |
| bank07 | 7 | | | | | | | |
| bank08 | 8 | | | | | | | |
| bank09 | 9 | | | | | | | |
| bank10 | 10 | | | | | | | |
| bank11 | 11 | | | | | | | |
| bank12 | 12 | | | | | | | |

- G4a (A vs D): TBD
- G4b (redefined, 15 seeds; + old-statistic diagnostic values): TBD
- `verdict_p59.py` full output (verbatim): TBD
- V notes per run + the two worst-G6 bank cells given the full three-frame look: TBD
- **RQ-P5.9 overall: TBD**
- Estimate-vs-actual table: TBD

## Deliverables (cut by Opus after the matrix — commit all, view all)

1. `proof/p59_beforeafter_kerb.png` — P5.8 seed101 f0180 (two disconnected
   blobs) vs P5.9 seed101 f0180 (intact body, calibrated bands): the fix,
   same seed, same frame index.
2. `proof/p59_kerb_calibration.png` — the (s, lat) integrity sweep with the
   derived corridor: the measurement behind the bands (and the ~4° kerb skew
   that explains P5.8's late-clip failure).
3. `proof/p59_bank_grid.png` — 12 bank clips at f0180 with GT overlays and
   per-run G6: the select arc's scene data, existing and clean.
4. `proof/p59_g6_teeth.png` — G6 frag p10 across all 16 runs vs the P5.8
   clipped reference (0.666): the regression gate has teeth.
5. Ledgers: RESULTS row → `docs/results/part5-anticipatory.md`; QUESTIONS
   (RQ-P5.9) → `docs/questions/part5-anticipatory.md`; DECISIONS (G4b
   redefinition ruling; fix-first-vs-science-now; bands + seed procedure) →
   `docs/decisions/part5-anticipatory.md`. No new SOURCES expected.
6. Committed on this branch; **not merged** (the loop's reviewer merges).
