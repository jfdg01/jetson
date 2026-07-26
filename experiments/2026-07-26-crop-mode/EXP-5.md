*Stage of the MODE 2 campaign, split out of `README.md` on 2026-07-26 so a session
working one stage does not load the other four. The section number below is unchanged,
so existing "§7" citations still resolve. Campaign context, imagery decision, versions
and proof deliverables stay in `README.md`.*

## 7. EXP-5 — carry-crop mechanism pilot (levers b, c, e)

Kill-cheap. **Exploratory: no test, no PASS claim** — the n>=25 rule binds gating arms, and
this arm gates nothing. Runs on existing UAV123, **no new imagery**.

### The guard, fully specified

Applied **before** the box is committed at `carla_debug_ui.py:1734`, against the **previous
committed** box:

* **Area veto.** Reject if `area(new) / area(prev) not in [0.4, 2.5]`. **Units pinned: area
  ratio, not side length** (2.5x area = 1.58x linear). These are P5.21's own `AREA_LO` /
  `AREA_HI` (`carry_p521.py:96`); the novelty is the **call site** — the tracker's own output
  at accept time — not the constants. The proposal's grow-only variant is discarded because
  `car10` failed by shrinking.
* **Displacement veto (new — the actual `car10` mechanism).** Reject if
  `dist(centre(new), centre(prev)) > D_MAX * max(w, h) of prev`. P5.21's `REINFORCE_DISP=1.5`
  was diagnostic-only at a 90-frame stride; per-step it must be far tighter. **Do not guess
  it.** The CONTROL arm logs the full per-step displacement distribution over the 12 clips
  and `D_MAX` is set to its **99th percentile, rounded to one decimal**, before any treatment
  arm runs. The *rule* is pre-registered here, not the number.
* **On veto:** hold the previous box, do **not** re-centre the window this step, increment
  `veto_run`; at `veto_run >= 5` fall through to the existing lost branch
  (`carla_debug_ui.py:1698-1710`).

### Window policy — one deliberate deviation from the proposal

The proposal says "each step, crop around the current box centre". `_prep` writes every
frame into SAM2's memory bank, so per-step window jitter injects synthetic ego-motion **and**
synthetic zoom into every memory entry — which is exactly the `roi.py:60-65` death spiral.
The crop arms instead use a **dead-band re-centre**: the window moves only when the box
centre leaves the central 50% of the window. The crop is applied to the **init frame too**
(seed box remapped into crop coords) so frame 0's geometry matches the rest.

### Arms

| arm | carry | `image_size` |
|---|---|---|
| **A1 CONTROL (deployed)** | plain, whole frame | 640 |
| **A2 CONTROL-2 (deployed fallback)** | plain, whole frame | **1024** |
| **A3 GUARD-ONLY** | plain, whole frame + guard | 640 |
| A4 CROP-FIXED-NOGUARD | fixed 512-px window, dead-band | 640 |
| **A5 CROP-FIXED-GUARD** | fixed 512-px window, dead-band + guard | 640 |
| A6 CROP-SCALED-GUARD | `roi_window(margin=2.0, min_side=256)` + guard | 640 |

A2 and A3 exist so that a win cannot be misattributed: A2 because every tail clip already
passes at 1024 with zero new code, A3 because the guard alone might be the whole effect.

* **Clips:** 12 UAV123 — the full EXP-1 resolution-gated tail (`bike3, car15, uav3,
  person21, building3, car13, truck2, truck3`) + 4 easy controls (median IoU > 0.8 at 640)
  to catch regression on the trivial case. `car11` is excluded by pre-registered rule (0.000
  at every size except 896 — anomalous, not resolution-gated).
* **Metric:** per-clip median IoU vs GT; `area_ratio` and per-step displacement traces (does
  the spiral reproduce — monotone collapse or not); veto counts by type.
* **n:** 12 clips x 6 arms = 72 runs.
* **Visual:** overlay one spiralling and one held clip at frames 0 / 25% / 50% / 100%, plus
  the crop window drawn on the full frame. Read all of them.
* **Kill gate 1:** if A5 **and** A6 both still spiral (monotone `area_ratio` collapse or
  IoU -> 0) on >= 50% of the tail-8 -> **kill levers b/c/e**, do not build EXP-6.
* **Kill gate 2:** if **A3 ~= A5** on the tail (within 1 clip of PASS-flips), the crop is not
  the lever — **ship the guard alone as a ~10-line patch and kill the crop**.
* **Kill gate 3:** if A5 < A2 on the tail, the config flag wins; kill.
* **Proceed gate:** A5 or A6 recovers >= 4/8 tail clips from median IoU < 0.25 to >= 0.25
  with no easy-clip regression -> earn EXP-6, recording which of FIXED / SCALED won (that
  answers lever c; no separate experiment for it).
* **Code:** host-side crop wrapper around `_send` at `carla_debug_ui.py:1619-1620` and
  `:1649` (crop -> JPEG -> send; remap the returned box by `x0 + b*sx`, modelled 1:1 on
  `select_p55.py:111-113`) + the guard branch before `:1734`. ~60 lines. **Zero bridge
  protocol change** — `carry_ssh_bridge.py:_decode` accepts any resolution and `_prep`
  resizes internally.
* **Reuse:** `carry_ssh_bridge.py`, `StreamCarry`, `run_exp1.py`'s `stage` / `carry` /
  `score` staging, `curate_p518.py` loader, frozen EXP-1 seed boxes.
* **Tracker placement:** SAM2 on the Orin only, via `carry_ssh_bridge.py`. The 3090 runs
  CARLA only. Non-negotiable.
* **Cost estimate.** ~1 day, dev-dominated (72 short on-device runs ~= 50 min + 2 bridge
  spawns).
* **Estimate (pre-registered).** A4 spirals on 6-7/8 tail. **A3 GUARD-ONLY recovers 0-1/8** —
  the tail's 0.000 at 640 reads as "never latched", not "drifted", and a veto cannot conjure
  a latch. A5 recovers **4-6/8**. A6 recovers 2-3/8 (box-scaled windows re-introduce the
  shrink-feedback half). Easy clips: A5 within 0.03 median IoU of A1.

### Results — run 2026-07-26T22:40Z, `runs/exp5/`

Per-clip **median IoU vs GT**, 24 steps at stride 11 (~8.8 s of video per clip), SAM2 on the
Orin over `carry_ssh_bridge.py`. Bold = the arm is at or above 0.25 where A1 is not.

| clip | A1 640 | A2 1024 | A3 guard | A4 crop | A5 crop+guard | A6 scaled |
|---|---|---|---|---|---|---|
| bike3 | 0.000 | **0.649** | 0.000 | **0.753** | 0.000 | **0.749** |
| car15 | 0.000 | **0.717** | 0.000 | **0.653** | **0.653** | **0.764** |
| uav3 | 0.000 | **0.436** | 0.000 | 0.000 | 0.000 | 0.000 |
| person21 | 0.000 | **0.537** | 0.000 | **0.611** | **0.600** | **0.664** |
| building3 | 0.446 | 0.507 | 0.446 | 0.521 | 0.521 | 0.657 |
| car13 | 0.639 | 0.769 | **0.000** | 0.752 | **0.000** | **0.000** |
| truck2 | 0.723 | 0.793 | 0.723 | 0.795 | 0.795 | 0.812 |
| truck3 | 0.800 | 0.852 | 0.800 | 0.868 | 0.868 | 0.797 |
| boat3 | 0.967 | 0.955 | 0.967 | 0.951 | 0.951 | 0.958 |
| car18 | 0.921 | 0.924 | 0.921 | 0.913 | 0.913 | **0.000** |
| person10 | 0.889 | 0.901 | 0.889 | 0.888 | 0.887 | 0.868 |
| wakeboard6 | 0.822 | 0.900 | 0.822 | 0.901 | 0.901 | 0.896 |
| **tail >= 0.25** | **4/8** | **8/8** | **3/8** | **7/8** | **5/8** | **6/8** |
| tail median IoU | 0.223 | 0.683 | 0.000 | 0.703 | 0.560 | 0.707 |
| easy median IoU | 0.905 | 0.913 | 0.905 | 0.907 | 0.907 | 0.882 |
| vetoes fired | 0 | 0 | 44 | 0 | 24 | 5 |
| monotone spirals | 0 | 0 | 0 | 0 | 0 | 1 (`uav3`) |
| **on-device Hz** | **5.75** | **2.34** | 5.73 | **6.30** | 6.29 | 6.50 |

`D_MAX` = **4.2** (rule as pre-registered: 99th pct of A1's per-step displacement, rounded to
1 dp; raw 4.2055 over n=278 steps, p50 0.531, p95 2.087).

**Verdict as pre-registered: KILL.** Kill gate 3 fires — A5 reaches 5/8 on the tail, A2
(plain@1024, a config flag already deployed as the size-gated fallback) reaches 8/8. The
proceed gate also fails, and was **unreachable by construction**: only 4 tail clips sit below
0.25 in A1 (`bike3`, `car15`, `uav3`, `person21`), so "recovers >= 4/8" demanded a perfect
4/4, and `uav3` is recovered by no crop arm at any setting. Kill gates 1 and 2 did **not**
fire (A5 zero spirals, A6 one; A3 3/8 vs A5 5/8 is two PASS-flips apart, so the crop — not the
guard — is what moves the tail).

The six arms decompose *why* the composed treatment lost, and the three mechanisms are each
confirmed on pixels as well as in the traces:

* **Lever b (the crop) works, and it is free.** A4 vs A1: tail 7/8 vs 4/8, tail median 0.703
  vs 0.223, easy clips unchanged (0.907 vs 0.905), and **faster** — 6.30 Hz vs 5.75 Hz. The
  speed-up is transport, not compute: SAM2's cost is fixed by `image_size=640`, and a 512-px
  crop is a smaller JPEG to encode and push over ssh than a 1280x720 frame (median step 159 ms
  vs 174 ms).
* **Lever e (the guard) is harmful as specified — it self-latches.** "Hold the previous box on
  veto" freezes the reference the *next* veto is measured against, so one veto begets all the
  rest. `car13` under A3: 23 displacement vetoes + 1 area veto, 20 lost steps, median 0.000,
  where A1 held the same clip at 0.639. `bike3` under A5: one genuine burst at ratio 3.67 is
  vetoed, and from then on the frozen reference makes the ratio climb monotonically
  3.10 -> 5.95 — 13 area vetoes, 9 lost steps, median 0.000, while A4 absorbed the same burst
  and finished at 0.92. Small boxes make it worse: `disp_norm` divides by `max(w, h)` of the
  previous box, and `car13`'s box is 15x9 px, so even `D_MAX=4.2` is trivially exceeded by
  ordinary jitter. The guard cost A4 two tail clips and bought nothing.
* **Lever c: FIXED beats SCALED.** A6 reaches 6/8 on the tail but regresses an easy control —
  `car18` 0.921 -> 0.000, the tracker dies at step 10 after area ratios 0.72 / 0.69 / 0.37 —
  and owns the only monotone spiral. That is exactly the shrink-feedback half `roi.py:60-65`
  documents: the box shrinks, the window shrinks with it, and once the box is lost the window
  is stranded on empty tarmac with no way back. `min_side=256` slowed that down; it did not
  stop it. A fixed window cannot shrink, so it cannot spiral.

### Deviations from the pre-registration

* **`D_MAX` is contaminated by construction, and was used anyway.** The rule sets it from the
  CONTROL distribution, but CONTROL's distribution *contains the failures the veto exists to
  catch* — the tail's drift events are in the sample that sets the threshold, which inflates
  it. Breakdown: ALL n=278 p99 4.206 (max 4.80); TAIL n=182 p99 4.559; EASY n=96 p99 **1.734**
  (max 2.08). The honest threshold is closer to 1.7. The pre-registered rule was honoured and
  the run went out at 4.2, with the EASY-only p99 recorded here as a labelled diagnostic
  rather than swapped in post hoc. It does not change the verdict — at a *tighter* threshold
  the displacement veto fires more often, and the self-latching failure above gets worse, not
  better.
* **Proceed gate unreachable by construction** (above). Same class of pre-registration error
  as the P5.3 / P5.4 / P5.5 gates: a floor written without checking how many cells could
  physically move.
* **The 4 easy controls** are the best clip per object category (`boat3`, `car18`, `person10`,
  `wakeboard6`) rather than the top 4 outright, so the regression check is not four cars.
* **`uav3` is recovered by nothing** below 1024. It is a UAV-on-UAV clip at 720x480, so its
  fixed window is 480 (`min(CROP_SIDE, w, h)`) — barely a crop at all. Only A2 moves it.

### Estimate vs actual

| pre-registered | actual |
|---|---|
| A4 spirals on 6-7/8 tail | **0/8** — A4 never spiralled and was the best crop arm |
| A3 GUARD-ONLY recovers 0-1/8 | 0 recovered, and it **lost** `car13` (4/8 -> 3/8) |
| A5 recovers 4-6/8 | 2/4 of the recoverable cells (5/8 total) |
| A6 recovers 2-3/8 | 3/4 recoverable (6/8 total), but regressed an easy clip |
| easy: A5 within 0.03 of A1 | 0.907 vs 0.905 — held |

The estimate had the guard as the load-bearing part and the bare crop as the failure mode.
Both were backwards. The single wrong assumption was that an unguarded per-step crop would
spiral; a **fixed-size** window has no shrink term, so there is nothing to spiral.

### What this means for EXP-6

EXP-5 as pre-registered says kill, and the honest continuation is not "run EXP-6 anyway".
A4 was **not** the pre-registered treatment, so carrying it forward is a **post-hoc arm
promotion** and is marked as such: §8 is re-pre-registered below with A4 (fixed crop, **no
guard**) as TREATMENT, A2 as the arm to beat, and the guard dropped as a measured negative.
No p-value from EXP-5 is carried anywhere — this pilot is exploratory and gates nothing.

### Proof

* `proof/exp5-arms.png` — per-clip median IoU across all six arms, tail and easy split, with
  tail recovery and on-device Hz. The quantitative claim: A4 recovers the tail at A2's
  accuracy and 2.7x its rate; A3/A5's zeros are the guard, not the crop.
* `proof/exp5-guard-latches.png` — `bike3`, A4 (top) vs A5 (bottom), steps 0/8/15/23. Same
  crop window (orange), same seed. A4 holds the cyclist to 0.92; A5 has no box at all from
  step 15 on — one vetoed burst, then the frozen reference latches the veto permanently.
* `proof/exp5-scaled-strands.png` — `car18`, A4 (top) vs A6 (bottom). At step 8 A6's box has
  already collapsed onto the car's front half (0.25) and its window with it; by step 15 the
  box is gone and the window sits on empty road while the car drives away. A4's fixed 512
  window follows the car to 0.90. This is the shrink-feedback spiral, on a clip A1 handles at
  0.921.

---

