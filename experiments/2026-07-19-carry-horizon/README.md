# P5.15 — carry-horizon: how long does a warm carry survive on real video, and does the deployed re-anchor lever extend it?

**Pre-registered:** 2026-07-19T14:10Z (Madrid wall clock)
**Status:** COMPLETE — run 2026-07-19T14:15Z–14:28Z. **OVERALL: YES** (RQ-P5.15a PLAIN alive@16s = 24/25 vs floor 18; RQ-P5.15b N/A by ceiling). Visual gate PASS on all 25 h16 frames + 5 death frames + 4 MAINT/PLAIN h24 disagreement frames.
**Roles:** design + patches by Fable; Opus runs the matrix and fills Results only — do NOT re-patch code.
**Branch:** `experiment/carry-horizon` (off `main` @ `7685c0e`, the P5.14 merge)

---

## 1. Research question

**RQ-P5.15a (gating):** On real UAV123 video, does an unmaintained warm SAM2 carry
(seeded at GT[0], stepped at the deployed 6.15 Hz budget — the exact P5.1/P5.2 idle
convention) stay on-target (IoU >= 0.25 vs GT) at a **16 s** idle horizon — twice the
longest idle any Part V result has used — on at least **18 of 25** clips?

**RQ-P5.15b (gating, conditional):** At the **24 s** horizon, does adding the deployed
idle ROI re-anchor lever (P5.5 `roi_reanchor`, every 165 frames, Jetson q8_0 terse VLM
with the clip's P5.2 caption) keep **at least 3 more** clips alive than the unmaintained
carry? N/A by ceiling if PLAIN alive@24s >= 22/25 (no headroom to show value).

**Overall verdict: YES iff RQ-P5.15a is YES.** RQ-b is reported either way and shapes
the follow-up, not this verdict.

### Why this experiment (audit-derived rationale)

P5.14 (direct-delivery select, YES) was audited before this pre-registration
(verdict.txt + all `runs/DD_*/results.json` spot-checked, all four committed proof PNGs
opened and corroborated). The YES is internally valid but **narrow**: n=5 gating scenes,
all UAV123 `car*`, a single 8 s idle length, oracle-seeded candidates, hand captions with
string-equality binding (selection is correct by construction — the experiment's real
content is the carry + delivery). Its one FAIL (car7:460 SWAP) was **carry-off-object**,
its one marginal PASS (car9:560, IoU 0.2843 vs the 0.25 floor) was carry-drift, and its
README names **carry quality on real video** the next binding constraint. Under the DD
contract there is no prompt-time VLM to catch a bad carry: *the carry is the product*.
Every Part V number so far sits on carries <= ~8 s old; a real operator's prompt can
arrive much later. Whether warm carries survive 2-3x the tested idle is the single
assumption everything downstream (P5.14's contract, any future auto-discovery cycle)
stands on — and it has never been measured. RQ-b simultaneously gives the deployed
maintenance lever (P5.5: accepted 16/16 rounds, fixed 2 cells, never harmed one) its
first controlled survival-value test.

### Rejected competitor (for DECISIONS)

**Long-idle DD-select sweep on the P5.14 scenes** (re-run WSEL+SWAP at t_p = 16/24 s):
rejected **by looking** at the actual prompt frames (dumped with GT overlays, viewed).
Clip lengths kill car7:460 (needs frame 1240 of 1033) and car10:615@24s (1635 of 1405),
and in car9:300, car9:560, car3:200 and car10:240 the hand-annotated distractor has left
the FOV or cannot be re-identified by 16-24 s — the strengthened-SWAP hand annotation
would be dishonest. Finding worth recording: **UAV123's two-candidate geometry dissolves
within ~16 s**; long-idle *select* cannot be tested on this dataset, but long-idle
*carry* can — every clip has per-frame GT for its single target for free. A second
competitor, the auto-caption/candidate-discovery cycle (removing P5.14's oracle seeds),
is deferred, not rejected: discovery needs a long idle window to be worth anything, so
carry survival over long idle is its prerequisite — this experiment.

---

## 2. Design

- **Clip set (frozen):** the 25-clip P5.2 set verbatim, `clips_p515.json` (copied from
  `experiments/2026-07-04-warm-start-generalization/clips.json`): 9 car, 2 boat,
  8 person, 1 bike, 5 wakeboard; captions as in P5.2 ("the car", "the boat", ...).
  f0 = 0 everywhere; seed = GT[0] (verified valid for all 25). All clips are long
  enough for the 24 s horizon (min: wakeboard2, 733 frames > 721).
- **Arms (2 x 25 = 50 cells, n=1 deterministic):**
  - `PLAIN` — single SAM2 carry (`sam2.1-hiera-tiny`, bf16 autocast on the 3090, the
    P5.3-P5.14 convention), stepped non-realtime at stride round(30/CARRY_HZ) = 5 frames (the deployed
    6.15 Hz budget convention), no maintenance. No Jetson involvement.
  - `MAINT` — PLAIN + `select_p55.roi_reanchor` (margin 2.0, min_side 256, crop long
    edge 512, LANCZOS; accept = parseable + in-frame valid, **no IoU floor** — the
    P5.5 accept rule verbatim) at frames 165, 330, 495, 660, VLM = Jetson q8_0 terse
    over SSH, caption = the clip's caption. An accepted answer reseeds the carry there.
- **Scoring (per cell, per horizon h in {8, 16, 24} s):** the carried box at the scoring
  frame vs UAV123 GT; **alive = IoU >= 0.25** (the Part-V-wide floor). Scoring frame =
  h*30, or the nearest valid-GT frame within +-30 frames if GT is absent there (tie ->
  earlier). Known fallbacks (occlusion spans, measured before freezing): car7 h8 scores
  at f228, person10 h8 at f270; all other 73 horizon points sit on valid GT at h*30
  exactly. No valid GT in the window -> that horizon is N/A for that cell and leaves the
  denominator (none expected). The step schedule is forced to land on every scoring
  frame; re-anchor frames never coincide with scoring frames (asserted in the rig).
- **Non-gating diagnostics** (logged per cell, for the follow-up carry-health-gate
  question): full per-step IoU trace, first-death frame (first valid-GT step with box
  lost or IoU < 0.10), HSV-histogram correlation of the carried crop vs the seed crop
  at each horizon, box-area ratio vs seed, per-category breakdown.

**Thresholds, frozen now.** RQ-a floor 18/25 (72%): P5.2's WARM arm delivered 21/25 at
~8 s; 18 allows three additional deaths over the second 8 s — worse than that and the
"carry until the prompt comes" premise of Part V needs a maintenance or health-gate
answer before any deployment claim. RQ-b margin +3: below 3 flips the P5.5 lever's
value is within single-cell noise on n=25. Ceiling 22: if PLAIN already matches P5.2's
8 s number at 24 s there is no headroom for maintenance to demonstrate anything.

**Estimates (marked as estimates).** P5.14's runtime estimate was 10x over (45-75 min
estimated, 4.4 min measured); calibrating on its measured ~21-22 s/cell (which covered
~8 s idle x 2 candidates + 10 s realtime cover) and scaling to 720 frames / stride 5 =
145 SAM2 steps/cell, single candidate, no realtime segment: **PLAIN ~30-60 s/cell,
~15-25 min for the arm; MAINT + one Jetson boot (~60-90 s once) + 100 VLM crop calls
(~2-3 s each) ~20-35 min; whole matrix ~35-60 min wall.** Expected numbers (estimates,
from the P5.2 WARM 21/25 at ~8 s and P5.14's carry behaviour): PLAIN alive@8s ~21-23,
@16s ~17-20 (the RQ-a floor sits inside this band — genuinely falsifiable), @24s
~14-18; MAINT @24s +2-5 over PLAIN. Prediction to check against: RQ-a marginal-YES,
RQ-b YES.

---

## 3. Code (already committed — Opus: do NOT edit these files)

| File | What |
|---|---|
| `carry_horizon_p515.py` | the rig: injectable `run_cell` core, real-stack `run_matrix` (SAM2 local, Jetson backend booted once per MAINT arm), per-cell `runs/<ARM>_<clip>/results.json` + horizon overlay PNGs + `death.png`, resumable (skips cells whose results.json exists), per-cell crash -> INVALID results.json and the matrix continues. Frame-health asserts built in (>99%-one-colour and byte-identical-frame checks). `--selfcheck` = full stub suite (schedule, alive/dead/death-frame, MAINT rescue + reject, GT-absent fallback + tie + N/A, overlay health) — **green at commit time**. |
| `clips_p515.json` | frozen 25-clip set + captions + horizons |
| `verdict_p515.py` | mechanical verdict (gates above), writes `raw/verdict.txt` |
| `make_proof.py` | proof figures from `runs/*/results.json` (decay curves, alive grid, arm bars) |

Rig constants (all imported from the deployed stack, not redefined): CARRY_HZ 6.15
(`replay_e24`), ROI_MARGIN 2.0 / ROI_MIN_SIDE 256 / ROI_RES 512 (`select_p55`), VLM =
`phase3-terse100eos-1024-q8_0.gguf` via `JetsonBackend` (max_side 1024), SAM2 =
`facebook/sam2.1-hiera-tiny` (`stream_carry.MODEL`). New constants (this rig, frozen):
HORIZONS_S (8, 16, 24), ALIVE_IOU 0.25, GT_TOL 30, DEATH_IOU 0.10, REANCHOR_EVERY 165.

## 4. Run matrix (Opus: copy-paste, in order)

Rig: RTX 3090 host (this repo, `.venv-ft`) + Jetson Orin Nano 8 GB for MAINT only.
Versions: python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6 (the pinned
`.venv-ft`); Jetson llama.cpp q8_0 as deployed (unchanged since Part III).
Record actual versions (`.venv-ft/bin/python -c "import torch,transformers;
print(torch.__version__, transformers.__version__)"`) and the run date in Results.

```bash
cd /home/gara/jetson

# R0 — selfcheck must be green before anything else (offline, ~10 s)
.venv-ft/bin/python experiments/2026-07-19-carry-horizon/carry_horizon_p515.py --selfcheck

# R1 — Jetson power mode (NOPASSWD; needed for MAINT only, do it up front)
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"
ssh jetson "nvpmodel -q"   # record the mode line in Results (15W, this board has no MAXN)

# R2 — PLAIN arm (25 cells, no Jetson; est 15-25 min)
.venv-ft/bin/python experiments/2026-07-19-carry-horizon/carry_horizon_p515.py \
    --matrix experiments/2026-07-19-carry-horizon/clips_p515.json --arm PLAIN --out runs \
    2>&1 | tee experiments/2026-07-19-carry-horizon/raw/plain.log

# R3 — MAINT arm (25 cells, Jetson boots once; est 20-35 min)
.venv-ft/bin/python experiments/2026-07-19-carry-horizon/carry_horizon_p515.py \
    --matrix experiments/2026-07-19-carry-horizon/clips_p515.json --arm MAINT --out runs \
    2>&1 | tee experiments/2026-07-19-carry-horizon/raw/maint.log

# R4 — mechanical verdict (writes raw/verdict.txt)
.venv-ft/bin/python experiments/2026-07-19-carry-horizon/verdict_p515.py

# R5 — proof figures
.venv-ft/bin/python experiments/2026-07-19-carry-horizon/make_proof.py
```

`mkdir -p experiments/2026-07-19-carry-horizon/raw` first if tee complains. The matrix
is resumable: a re-launch skips every cell whose `results.json` exists — **never delete
a scored cell to rerun it**. A crashed cell self-records as INVALID and the matrix
continues; INVALID in any gating count makes the whole run INVALID (verdict script
enforces this).

**Abort criteria (mechanical):** any single cell wall > 10 min (PLAIN) or > 15 min
(MAINT) -> kill the process, the cell self-records INVALID on the next launch attempt or
is marked INVALID by hand-writing `{"arm":..,"clip":..,"INVALID":"hung >Nmin"}` to its
results.json — do not wait it out. Whole-arm wall > 2 h -> abort the arm, run the
verdict on what exists, report INCOMPLETE. Jetson boot failure after 2 retries ->
MAINT arm INVALID, PLAIN still gates RQ-a. Missing `results.json` after a cell printed
its summary line -> INVALID.

**Gotchas:** (1) the Jetson backend is booted ONCE for the whole MAINT arm — if the SSH
session drops mid-arm, just relaunch R3 (resumable). (2) `frame_health` asserts fire
inside overlay writing; if one fires, that cell is INVALID — do not weaken the assert.
(3) car7 and person10 score h8 on fallback frames (228 / 270; occlusion spans
229-269 / 202-269 in the UAV123 anno) — this is pre-registered, not a bug.

## 5. Visual verification (gating; CLAUDE.md "look at it")

The claim frames here are the **horizon scoring frames** — the rig dumps exactly those
(plus first-death frames), so the PNG opened IS the frame the alive/dead claim is about
(the P5.14 viz_late lesson: never gate on a frame seconds away from the claim).

Opus MUST, before writing any verdict into this README:

1. Open with the Read tool **all 25 `runs/PLAIN_<clip>/h16.png`** (the RQ-a claim
   frames). PASS looks like: green carry box substantially overlapping the red GT box
   on the target. Dead looks like: green box elsewhere / on background / absent.
   The verdict for each cell must match what the PNG shows; any mismatch -> stop,
   record the cell INVALID, re-run verdict.
2. Open **every `death.png`** that exists (both arms): confirm the green box is
   genuinely off-object at the recorded death frame.
3. Open **`runs/MAINT_<clip>/h24.png` for every clip where MAINT@24s and PLAIN@24s
   disagree** (the RQ-b claim frames), same PASS/FAIL reading.
4. Open the three `proof/*.png` after R5 and confirm they match `raw/verdict.txt`
   numbers.
5. No frame for a scored cell -> that cell is INVALID ("cannot verify, no frame").

## 6. Results

Run date/time (Madrid): 2026-07-19T14:15Z–14:28Z. Versions actual: python 3.12.10,
torch 2.6.0+cu124, transformers 4.57.6 (`.venv-ft`); SAM2 `facebook/sam2.1-hiera-tiny`
on the RTX 3090; VLM `phase3-terse100eos-1024-q8_0.gguf` on the Jetson via llama.cpp.
Jetson mode line: `NV Power Mode: 15W` (`nvpmodel -q` -> mode 0; this board has no MAXN)
+ `jetson_clocks`. n=1 deterministic, 50/50 cells scored, 0 INVALID, 0 N/A horizons.

Wall clock actual vs estimate: **PLAIN 209 s total (8.4 s/cell)** vs est. 15–25 min;
**MAINT 412 s total (16.5 s/cell, incl. 100 Jetson VLM crop calls)** vs est. 20–35 min;
whole matrix **~10 min** vs est. 35–60 min. Second cycle running ~4x under estimate.

Per-cell numbers: `raw/verdict.txt` (verbatim, both arms, IoU + scoring frame + death
frame). Summary:

| | h8 | h16 | h24 |
|---|---|---|---|
| **PLAIN** alive | 25/25 | **24/25** | 24/25 |
| **MAINT** alive | 24/25 | 22/25 | 22/25 |

- **RQ-P5.15a:** PLAIN alive@16s **24/25** vs floor 18/25 -> **YES**. The single death is
  `car7` (dies at f270, never recovers; a roundabout occlusion behind palms). Every other
  clip is still on-target at 24 s, most at IoU 0.6–0.97.
- **RQ-P5.15b:** **N/A by the pre-registered ceiling** (PLAIN@24s 24 >= 22). Non-gating but
  the striking number: MAINT is **worse** than PLAIN at every horizon (24/22/22 vs
  25/24/24). Re-anchor accepted **100/100** rounds (the P5.5 accept rule has no IoU
  floor) and **cost 3 net clips**: `car10`, `car3`, `person10` were alive under PLAIN and
  dead under MAINT because an accepted re-anchor moved the carry onto a *different
  same-class object* (verified by looking — see below). It rescued exactly one clip,
  `car7` (PLAIN dead@16s/24s, MAINT alive 0.609/0.873). Fable pre-registered this exact
  risk ("MAINT may anchor onto a different same-class object — that is data, not a bug").
- Per-category PLAIN survival @16s: bike 1/1, boat 2/2, car 9/10, person 8/8,
  wakeboard 4/4. Only the car category loses a clip.
- Health-signal separation (all 150 horizon points): `area_ratio` separates cleanly —
  median 1.039 alive (n=141) vs 0.163 dead (n=9); `hist_corr` does not (mean 0.742 both,
  and it is None on 2 dead points where no box exists). A cheap carry-health gate should
  use box-area collapse, not colour histogram.
- Estimate-vs-actual on numbers: Fable predicted PLAIN @16s 17–20 (a "marginal YES") and
  RQ-b YES. **Both predictions were wrong in the same direction**: the unmaintained carry
  is far more durable than the Part V record implied (24/25, not 17–20), and the deployed
  maintenance lever *hurts* rather than helps at long idle.

### Visual verification log (all gating frames opened with the Read tool)

1. **All 25 `runs/PLAIN_<clip>/h16.png`** — each shows the green carry box on the target
   overlapping the red GT box, matching the recorded IoU/alive flag. `PLAIN_car7/h16.png`
   shows the GT red box on a white car at a roundabout with **no green box** — the death
   is real. No mismatch between any PNG and its cell verdict.
2. **All 5 `death.png`** (PLAIN `car7` f270, `car18` f270, `car1_s` f570, `person1_s`
   f170, `person20` f75) — every one shows a genuinely off-object carry: `car7` green box
   drifted onto empty road; the other four show the mask leaking into a large background
   region around the target. The four non-`car7` clips recover afterwards (alive at all
   horizons), so "death" here is a transient-loss diagnostic, not a terminal state.
3. **All 4 MAINT/PLAIN h24 disagreement frames** — `MAINT_car10/h24.png`: green box on a
   *different car* two vehicles ahead of the red GT car. `MAINT_car3/h24.png`: green box
   on a different car up-road. `MAINT_person10/h24.png`: green box on a *different person*
   below the red GT person. `MAINT_car7/h24.png`: green box correctly on the GT car (the
   one rescue). The identity-swap mechanism is visible, not inferred.
4. **The three `proof/*.png`** — the alive grid, the arm bars and the decay curves all
   reproduce `raw/verdict.txt` cell-for-cell (25/24/24 vs 24/22/22, floor line at 18).

### What broke / what surprised

- Nothing crashed; the resumable path was never exercised. Selfcheck green, 0 INVALID.
- **The surprise is the size of the margin.** Part V's whole framing assumed the carry is
  the fragile part over a long idle window; at 24 s of unmaintained carry it is not
  (24/25). The P5.2 WARM 21/25 at ~8 s was therefore *not* carry-bound — those four
  failures were in the select/delivery stage, not the tracker.
- **The deployed idle re-anchor lever is now a measured liability at long idle.** P5.5
  accepted 16/16 rounds and "never harmed one" over an 8 s window; over 24 s the same
  no-IoU-floor accept rule nets -2 clips. It is generic-caption re-grounding with no
  identity constraint, so given enough rounds it will find some object of the class.

### Proof deliverables (committed)

| File | What it shows | Run/config |
|---|---|---|
| `proof/p515_arms.png` | the headline: clips alive vs horizon, both arms, RQ-a floor line at 18 — PLAIN 25/24/24, MAINT 24/22/22 | both arms, all 25 clips, 15W + jetson_clocks |
| `proof/p515_alive_grid.png` | per-clip x per-horizon IoU grid, green=alive/red=dead — every gating number in one figure | both arms |
| `proof/p515_decay.png` | PLAIN per-step IoU traces by category over the full 24 s — shows the transient dips (the recorded "deaths") that recover, and `car7` falling to 0 and staying there | PLAIN arm |
| `proof/p515_maint_car10_h24_IDENTITY_SWAP.png` | **proof of the negative:** MAINT re-anchor moved the carry onto a different car; green box two vehicles ahead of the red GT car at 24 s | MAINT `car10`, re-anchors accepted at f165/330/495/660 |
| `proof/p515_plain_car7_h16_DEAD.png` | the one RQ-a failure, verified visually: red GT on the white car, no green carry box | PLAIN `car7` h16 (f480) |

## 7. Ledger updates on completion (Opus)

RESULTS row(s) + QUESTIONS entry (RQ-P5.15a/b one-liners) + DECISIONS entry (the
rejected long-idle select sweep and why, incl. the "UAV123 two-candidate geometry
dissolves by ~16 s" finding) under Part V; 2-3 proof deliverables committed and
captioned here. No new SOURCES expected (no new external asset).
