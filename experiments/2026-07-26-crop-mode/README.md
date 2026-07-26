# MODE 2 "click crop" — native-resolution crop around the target (EXP-4 … EXP-7)

**Campaign dir:** `experiments/2026-07-26-crop-mode/`
**Opened:** 2026-07-26T12:09Z (Madrid wall-clock)
**Part:** VI residual thread. IDs **S0** (gate, no ID) then **EXP-4 … EXP-7**, contiguous
after the stopped EXP-3. No collisions with EXP-1 (`2026-07-24-resolution-decoupled-carry`)
or EXP-2 (same dir, grounding sweep).
**Status:** S0 run and PASSED (2026-07-26T12:17Z, §5). EXP-4 unblocked, not yet started.

This file is the self-contained handoff. A fresh session with no prior context should be
able to open it and start, continue, document or complete the campaign.

---

## 1. The proposal, as the repo owner stated it

> The live panel renders a 1920x1920 square viewport. Split the pipeline into two modes.
> **MODE 1 "normal"** (current deployed control): the VLM grounds the whole square frame
> downscaled to 1024/960; SAM2 then carries the same whole square frame downscaled to 640.
> **MODE 2 "click crop"**: the operator's click reveals where the target is, so crop a
> *native-resolution* window around it — 960x960 or 540x540 out of the 1920 frame — so the
> target is 2x+ bigger with no upscale/resample loss. Apply the same trick to SAM2 by
> cropping around the *current box centre* each step. Guard against degenerate boxes by
> ignoring a box that grows more than 2.5x in one frame (starting heuristic).

Four levers are named or implied: (a) crop-for-VLM-ground, (a') cut that crop from the
**native 1920** frame rather than the 960 downscale, (b) crop-for-SAM2-carry, (c) window
policy (fixed vs box-scaled), (d) re-centre cadence, (e) the degenerate-box guard.

## 2. Verdict on the proposal before any run

**Partly settled, partly live, and one framing is technically wrong.**

**Settled — do not re-run.** Lever (a) is deployed and measured. `roi_reanchor`
(`experiments/2026-07-14-select-generalization/select_p55.py:92-117`) is live in
`follow_click` (`runners/carla_debug_ui.py:1901-1902`), and EXP-2's `ground_sweep` already
measured the point-crop beating the whole frame at every resolution — PT@256 hit@0.5 =
0.769 vs NL@1024 = 0.654. Cropping for the VLM is not an open question.

**Technically wrong framing.** "Native pixels, no upscale, no resample loss" does not
describe what SAM2 receives. `StreamCarry._prep`
(`experiments/2026-07-01-temporal-acquire-carry/stream_carry.py:95-99`) resizes **whatever
it is handed** to `image_size`^2 — 640 today — and the ssh bridge does no resizing at all
(`carry_ssh_bridge.py:60-63`). There is no path by which native pixels reach the model. The
mechanism under test is **magnification on a fixed model grid**, not resample avoidance.

That reframing is what makes the carry half cheap: because SAM2 resizes everything anyway,
the crop's effect is *target pixels on a fixed grid*, and that is source-resolution
independent. A 512-px window from a 1280x720 UAV123 frame fed to a 640 grid puts a 20-px
target at 25 px vs 10 px whole-frame — **2.5x magnification, the same mechanism at the same
strength as the live 1920 rig**. EXP-5 and EXP-6 therefore need **no new imagery**.

**Live and genuinely untested.** (a') cutting the crop from the native 1920 sensor frame
instead of the 960 `cv2.resize(..., INTER_AREA)` output at `carla_debug_ui.py:2467` — never
done, and no offline bank in this repo has the headroom to try it (UAV123 is 1280x720, the
CARLA GT bank is 640x480, both **below** the 512/640 feed sizes). And (b) feeding SAM2's own
per-step propagation a crop — `_prep` resized the whole frame in **both** P5.21 arms, so
this configuration has never existed.

**Near-dead by prior art, and the guard as stated does not save it.** P5.21 killed crop-fed
*re-grounding* of a running carry (plain 28/34 vs ROI 26/34, b=1/c=3, p=0.625, direction
against ROI). Its one documented failure, `car10`, was a **displacement** error at frame 88
that `REINFORCE_DISP` measured and never vetoed, after which the box **shrank**
(`area_ratio` 0.36 → 0.16 → 0.10 → 0.05 → 0.03 → 0.02). The proposal's guard is *grow-only*
and *area-only*, so it catches neither half of the only failure we have on record. It is
replaced below by a bidirectional area veto plus a displacement veto.

## 3. Geometry the program rests on (derived, not measured)

Live rig: 1920^2 sensor (`LIVE_CAM_SIDE = 1920`), FOV 90, `COPTER_ALT = 45.0` m nadir.
f = 960 / tan(45 deg) = **960 px**, so **21.3 px/m** at ground. A `vehicle.ford.mustang`
(4.8 x 1.9 m) is **102 x 40 px** in the native frame.

| stage | today (MODE 1) | MODE 2 | target px on the model grid |
|---|---|---|---|
| VLM ground | 1920 -> 960 -> fed @512 | 540-px native crop -> fed @512 | 27 px -> **97 px (3.6x)** |
| SAM2 carry | 1920 -> 960 -> grid 640 | 960-px native crop -> grid 640 | 34 px -> **68 px (2.0x)** |

## 4. Open questions, ranked

1. Does magnifying the target on SAM2's fixed input grid rescue the resolution-gated tail
   at 640's throughput? The tail (`bike3, car15, uav3, person21`) is median IoU **0.000** at
   `image_size=640` and 0.44-0.72 at 1024 — that is "never latched", not "drifted", and
   magnification is the matching medicine. But **plain@1024 already fixes all eight tail
   clips** at 2.34 Hz vs 640's 5.76 Hz, so the only claim worth anything is
   **throughput-matched parity-or-better**, not raw accuracy.
2. Does per-step crop-recentring spiral? The self-referential geometry is documented
   independently of P5.21 in `grounding/roi.py:60-65` ("box 21px -> crop 86px -> garbage
   box"). Untested for SAM2 propagation.
3. Is the guard the lever, or is the crop? Never separated. A bidirectional area +
   displacement veto on *plain* carry costs ~10 lines and might capture the whole effect.
4. Does CARLA at 1920 actually contain detail its own 960 downscale does not, at a ~100-px
   vehicle footprint? Mip/LOD streaming can cap useful detail well below sensor resolution.
   Unmeasured, and it gates everything about lever (a').
5. At matched zoom, does native source beat upscaled-from-960? The only question lever (a')
   really asks; it needs an FOV-matched control to be answerable at all.
6. Does composed MODE 2 survive the closed loop? Contingent, last.

---

## 5. S0 — detail-headroom probe (gate only, no ID, no claim)

**RQ:** does a CARLA 1920^2 render carry real high-frequency detail over its own 960
`INTER_AREA` downscale, at the small-target footprint this program is about?

**Method.** One CARLA spawn on the 3090, `Town10HD_Opt`, synchronous, one RGB camera at
1920^2 FOV 90, nadir over a **static parked car** (deterministic, stationary — the same
reference `gate_a` in `runners/carla_gt_bank.py` uses). The footprint knob is **altitude,
not ground offset**: at nadir, footprint_px = f x L / z, so a lateral offset barely changes
it. Sweep six altitudes chosen to land the target at ~40 / 60 / 100 / 140 / 200 / 230 px:

| nominal footprint px | 40 | 60 | 100 | 140 | 200 | 230 |
|---|---|---|---|---|---|---|
| altitude m | 115.2 | 76.8 | 46.1 | 32.9 | 23.0 | 20.0 |

(20 m is a floor — `gate_a` has flown 25 m without clipping into geometry; the measured
footprint from the GT box is what gets recorded, not the nominal.)

Per altitude, with S = 1.5 x the target's max side in native px (floored at 96):

* **A native** — SxS window from the 1920 frame, no resize.
* **B downscaled** — the 1920 frame resized to 960 with `INTER_AREA` (byte-for-byte what
  `carla_debug_ui.py:2467` does), the *same physical region* cut as an (S/2)x(S/2) window,
  then LANCZOS-upscaled back to SxS.

Both are SxS, so the comparison is at native scale and the upscale is the thing under test.

**Metric.** Laplacian variance ratio A/B per target, plus a side-by-side PNG per target.

**Mandatory visual step.** Read every `pair_*.png`. The ratio in `results.json` is not the
verdict; the pixels are. Mechanical asserts in the script: `dominant_frac < 0.99` on the
full frame, and A/B not byte-identical.

**Gate.** Proceed to EXP-4 only if the ratio is **>= 1.30 for at least 4 of the 6 targets,
including both of the two smallest**, and the difference is visible. Otherwise **lever (a')
is dead** — record it, build no bank, and the "native 1920" framing collapses to "crop from
the 960 frame", which EXP-5/EXP-6 still test in full.

**Code.** `probe_s0.py` (~140 lines). Reuse: `carla_gt_bank.py` (`ensure_carla`, `nadir`,
`setup_world`, `env_car_cache`, `verts_to_box`, `analytic_area`, `dominant_frac`,
`reassert_power`).

**Cost estimate.** ~1 hr wall-clock (dominated by CARLA start-up + world load). Disk <20 MB.

**Estimate (pre-registered).** Ratio ~1.6-2.2 at >=140 px, ~1.1-1.4 at 40-60 px. Confidence
~55% that it clears the gate at the small end. That asymmetry is exactly the risk, which is
why the two smallest targets are gating.

### Command

```bash
# 3090. The script spawns CARLA itself if :2100 is not already up.
.venv-ft/bin/python experiments/2026-07-26-crop-mode/probe_s0.py \
  --port 2100 --out experiments/2026-07-26-crop-mode/runs/s0
```

Writes `runs/s0/full_<alt>.png`, `runs/s0/pair_<footprint>px.png` (native | 960-sourced
upscaled, side by side), `runs/s0/results.json`.

### Results — run 2026-07-26T12:16Z, `runs/s0/`

Reference: `SM_Mustang_prop4_SM_0` at (-11.8, 9.9, -0.0), length 4.72 m, f = 960 px.
Altitudes are the ones the script solved from the *measured* extent (`alt = f·L/target_px`,
floored at 20 m), so they differ slightly from the pre-registered table above.

| nominal px | alt m | measured px | crop S | lapvar native | lapvar down | ratio | mean absdiff | visible? |
|---|---|---|---|---|---|---|---|---|
| 40 | 113.2 | 40.5 | 96 | 992.7 | 131.8 | **7.53** | 5.18 | yes — decisive |
| 60 | 75.5 | 61.1 | 96 | 651.2 | 126.3 | **5.16** | 4.11 | yes — decisive |
| 100 | 45.3 | 103.0 | 154 | 416.6 | 86.3 | **4.83** | 3.16 | yes — clear |
| 140 | 32.3 | 145.9 | 218 | 365.1 | 76.7 | **4.76** | 2.56 | yes — moderate |
| 200 | 22.6 | 212.2 | 318 | 279.7 | 50.8 | **5.50** | 2.23 | yes — subtle |
| 230 | 20.0 | 242.2 | 362 | 251.3 | 47.5 | **5.29** | 2.16 | yes — subtle |

`dominant_frac` 0.004-0.026 on every frame (assert < 0.99); `veh_fill` 0.89-0.94 against the
segmentation mask, so the GT box really is on the car; `box_area_px` tracks `analytic_px_area`
to within 3% at the small end and 14% at 20 m (perspective on a 1.3 m-tall body — expected,
`analytic_area` is a flat-footprint model).

**Visual step done.** All six `pair_*.png` opened, plus `full_alt045.png` (real nadir Town10
street scene, Mustang at frame centre — the geometry is what it claims). `view_*.png` are
NEAREST-magnified viewing copies of the two smallest pairs; identical magnification on both
arms, no information added. At 40 px the native crop separates roof from windshield and holds
the pavement tiling; the 960-sourced arm is a pink blob with a smeared lane line. At 242 px
the gap is real but modest — wing mirrors and crosswalk edges, not object identity.

**Verdict: PASS — 6/6 above the 1.30 gate, both smallest included, difference visible.**

**Estimate vs actual: the estimate was wrong in magnitude and in shape.** Pre-registered
~1.1-1.4 at the small end rising to ~1.6-2.2 at large; measured 4.8-7.5 throughout, *highest*
at the small end. Two corrections fall out of that:

1. The direction was backwards. Laplacian variance is high-frequency energy per pixel, and a
   2x downscale removes a fixed top octave — at 40 px that octave *is* the car's structure,
   at 242 px it is trim detail on a body that survives either way. Small targets lose more,
   not less.
2. The absolute ratio is inflated as a perceptual claim. Some of the native arm's Laplacian
   energy is render noise and aliasing that the `INTER_AREA` downscale legitimately removes,
   which is why the 242 px pair looks far closer than 5.29x suggests. **Read the ratio as a
   gate, not as a quality metric** — it says headroom exists, not how much grounding gain it
   buys. That is EXP-4's job, and EXP-4 is now unblocked.

Live-rig relevance: the deployed nadir altitude is `COPTER_ALT = 45.0` m, which is the
103 px row almost exactly — the regime the campaign is about is the one where the gap is clear.

---

## 6. EXP-4 — native source vs zoom, disentangled (lever a')

Runs **only if S0 passes**.

**RQ:** at matched magnification, does a crop cut from the native 1920 frame ground better
than the same-FOV crop cut from the 960 downscale — and how much of any crop gain is
magnification alone?

A single 960-vs-1920 comparison confounds source resolution with a 2x FOV loss. The 2x2
below separates them; **all four arms are fed at 512**, so feed size is held constant.

| arm | source | window | FOV of frame | feed | note |
|---|---|---|---|---|---|
| **A (CONTROL, deployed)** | 960 | 512 px | 53.3% | 512, 1:1 | today's `roi_reanchor` |
| B | 1920 | 1024 px | 53.3% | 512, 2:1 down | double- vs single-downscale; expected null |
| **C (MODE 2)** | 1920 | 512 px | 26.7% | 512, 1:1 native | 2x zoom, native |
| **D (FOV-matched zoom control)** | 960 | 256 px | 26.7% | 512, 2x LANCZOS up | 2x zoom, **no new detail** |

* **Primary contrast: C vs D** — native detail at matched zoom, i.e. the actual lever-(a')
  question. Secondary A vs D = zoom alone. Secondary A vs B = downscale-chain loss (a
  sanity null; a non-null here means the chain itself is lossy).
* **Metric:** grounding hit@0.5 (binary, primary), IoU (continuous, secondary). No carry.
* **n / unit:** **25 designated targets**, one per capture, on Bank-1920-single (§9),
  stratified by native footprint: 10 at 40-80 px, 8 at 80-160 px, 7 at >160 px. The
  footprint goes in the manifest per target — EXP-1's tail was only ever qualitative and
  that is not repeated here.
* **Deflation:** all 25 come from `Town10HD_Opt`. Pre-registered rule: two targets are
  non-independent if their camera positions are within 30 m **or** they share a spawn point;
  collapse each cluster to one unit, report raw and deflated n, **cite the deflated p**
  (HANDOFF I2, P5.2 precedent).
* **Test:** exact McNemar on hit@0.5; Wilcoxon signed-rank on IoU.
* **PASS gate:** C > D, b > c, **b+c >= 6**, p < 0.05 -> plumb the native 1920 frame through
  to the crop path.
* **Kill gate:** b+c < 6 or b <= c -> **lever (a') dead**; keep cropping from the 960 frame
  and never touch `on_image`. This outcome is cheap and useful — it retires a plumbing
  change permanently.
* **Visual:** overlay predicted and GT boxes on the real crop for one C-win and one C-loss
  target; Read both.
* **Code:** `bank1920.py` (camera-attr change to `carla_gt_bank.py`: `W, H = 1920, 1920`,
  single-frame mode) + `run_exp4.py` (~150 lines, four `crop_resize` call sites). Reuse
  `roi_window`, `crop_resize(..., upscale=False)` for arm C, `map_to_full`, the R-14
  single-frame harness shape (`2026-07-21-roi-ondevice/run_r14.py`), `JetsonBackend`.
* **Cost estimate.** Bank ~2-3 hr, eval ~20 min (100 on-device VLM calls). Half a day.
* **Estimate (pre-registered).** A ~0.60, B ~0.60, C ~0.80, D ~0.76 hit@0.5. Zoom is the big
  lever (consistent with EXP-2: PT@256 0.769 > NL@1024 0.654); native detail adds ~4 pp, so
  b+c is likely 3-5 and **the primary is expected to MISS the reachable floor**. Stated up
  front so a MISS reads as "the 960 crop is good enough", not as a surprise.

### Results — run 2026-07-26T20:05Z, `runs/exp4/`

Bank built by `bank1920.py` (25 targets, 2 rejected, footprint 61-221 px), evaluated by
`run_exp4.py` against `q8_0` on the Jetson over `JetsonBackend`. n = 25, **deflated n = 25**
(see the deflation note below). The deployed model is greedy, so the run is deterministic:
two identical invocations gave byte-identical numbers.

| arm | hit@0.5 | mean IoU | median IoU | median wall_s | n |
|---|---|---|---|---|---|
| **A 960/512 (CONTROL, deployed)** | 0.60 | 0.4629 | 0.5455 | 2.04 | 25 |
| B 1920/1024 | 0.52 | 0.4249 | 0.5000 | 2.04 | 25 |
| **C 1920/512 (MODE 2)** | **0.92** | **0.7651** | **0.8571** | 2.03 | 25 |
| D 960/256 upscaled | 0.88 | 0.6350 | 0.6667 | 2.04 | 25 |

| contrast | b | c | p (McNemar, exact) | p (Wilcoxon, IoU) | median IoU diff |
|---|---|---|---|---|---|
| **C vs D** (primary, native detail at matched zoom) | 1 | 0 | 1.0 | 0.00285 | 0.0000 |
| A vs D (zoom alone) | 1 | 8 | 0.0391 | 0.0400 | 0.0000 |
| A vs B (downscale-chain sanity null) | 4 | 2 | 0.6875 | 0.6832 | 0.0000 |
| C vs A (MODE 2 vs deployed) | 8 | 0 | 0.0078 | 0.00059 | +0.3308 |

**Verdict: MISS on the primary, as pre-registered — and that is the useful answer.** C vs D
has b+c = 1, far under the 6-pair floor, so the binary gate cannot fire and **lever (a')
is retired**: at hit@0.5 a 2x LANCZOS upscale of the 960 frame is worth as much as real
1920 pixels. The crop keeps coming off the 960 display frame and `on_image` is never
touched. What *does* move is **magnification**: A vs D (b=1, c=8, p=0.039) isolates zoom
with no new detail and it wins on its own, and C vs A — MODE 2 against the deployed
control — is b=8, c=0, p=0.0078 with a +0.33 median IoU gap. **MODE 2's premise survives;
its 1920-plumbing sub-claim does not.**

Two caveats, both stated rather than buried. First, the wins are one-sided but small in
count because the arms agree on most targets — C never loses a discordant pair to either
D or A, which is why the continuous secondary (Wilcoxon p=0.0029 vs D, p=0.00059 vs A) is
far stronger than the binary one. Second, C's remaining 8% of misses are **not** detail
failures: the C-loss proof frame shows the model grounding a different, genuinely grey car
when the caption is "the grey car" and the crop holds four of them. That is
referring-expression ambiguity, arm-invariant, and it is the same residual Part VI's R-38
already located downstream of grounding.

**Estimate vs actual.** Estimated A ~0.60 / B ~0.60 / C ~0.80 / D ~0.76; measured 0.60 /
0.52 / 0.92 / 0.88. A was called exactly. C and D both came in ~12 pp high, so the C-D gap
(estimated ~4 pp, measured 4 pp) was right while the absolute level was pessimistic. The
pre-registered prediction that the primary would MISS the b+c floor held — b+c came in at
1, even lower than the estimated 3-5.

### Deviations from the pre-registration

Recorded because each one changes how a number should be read.

1. **Strata are realized by altitude, not by a fixed 45 m.** At 45 m nadir the footprint is
   fixed by vehicle length (21.3 px/m) and Town10's fleet cannot put 7 targets over 160 px.
   Altitude is solved per target from `alt = f*L/target_px`, clamped to [20, 120] m.
2. **One "large" target measures 115.6 px** (`t24_large`) because it hit the 20 m altitude
   floor. Measured bands are 10 small / 9 mid / 6 large, not the planned 10/8/7. Read the
   figure's footprint axis, not the label.
3. **`veh_fill` floor is 0.30, not 0.5.** An axis-aligned box around a car at 45 deg fills
   only ~0.41 of its own AABB even fully unoccluded (a 4.7x1.9 m body rotated 45 deg spans a
   4.67 m square = 21.8 m² against 8.9 m² of car), so a 0.5 floor silently selects for
   axis-aligned traffic. 0.30 still rejects the real failure, a target occluded to
   `veh_fill` 0.0.
4. **The 30 m separation rule is enforced at selection time,** with a 4-pass re-scan and 120
   ticks of driving between passes rather than a widened pool. Minimum realized pairwise
   camera separation is 31.1 m, so **raw n = deflated n = 25** by construction and there is
   no post-hoc collapse to argue about. Minimum target-centre-to-edge distance is 848 px, so
   even the 1024 window never clamps non-square.
5. **The caption is derived from rendered pixels, not the blueprint `color` attribute.**
   Vans and trucks carry a fixed livery and ignore that attribute; the first bank captioned a
   van the renderer drew **white** as "the dark red van". Found only by opening the C-loss
   overlay — the log was clean. The estimator now takes the median hue of the body pixels
   (vehicle-tagged, inside the GT box) when the body's **median** saturation clears 60, and
   median lightness otherwise. Medians, not percentiles: a 90th-percentile rule called a
   black car white off its UBER lettering and a white car blue off a racing stripe. The
   caption is identical in all four arms, so its quality is a constant of the experiment, not
   a confound — but it does cap the absolute rates, and Town10's fleet really is mostly grey
   and white (9 grey / 9 white / 6 red / 1 yellow across the bank).
6. **The bank is ~160 MB of PNG,** not the estimated ~50 MB. PNG is deliberate: JPEG would
   compress away exactly the high-frequency detail under test. Gitignored; `results.json`
   plus the body masks make it rebuildable.

### Proof

* `proof/exp4-arms.png` — per-target IoU C vs A sorted by footprint, plus the four-arm
  hit@0.5 / mean IoU bars. Built by `make_proof.py` from `runs/exp4/results.json`.
* `proof/exp4-C-win-t06-yellow-taxi.png` — C at IoU 1.00 where D scores 0.33 (62 px target,
  "the yellow car", an orange distractor two car-lengths away).
* `proof/exp4-C-loss-t03-grey-ambiguity.png` — C at IoU 0.00 on "the grey car": prediction
  green on a different grey car, GT red. The failure is the phrase, not the pixels.

---

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

## 8. EXP-6 — gated carry-crop test

**Re-pre-registered 2026-07-26T23:05Z, after EXP-5 and before any EXP-6 run.** The original
§8 (TREATMENT = "the EXP-5 winner", implicitly a crop+guard arm) is superseded, because
EXP-5's pre-registered treatment lost and the arm being carried forward is one EXP-5 was not
designed to promote. Both changes are declared, not smoothed over:

1. **TREATMENT is A4 — fixed 512 crop, dead-band re-centre, NO guard.** This is a **post-hoc
   arm promotion** off an exploratory pilot. It is why EXP-6 exists as a properly-powered
   confirmation rather than a formality, and it is why the §7 pilot carries no p-value.
2. **The guard (lever e) is dropped entirely** and shipped as a measured negative, not
   retried with a tuned `D_MAX`. EXP-5 showed the failure is structural — the veto freezes
   its own reference — so any threshold that fires at all latches. Re-tuning `D_MAX` would be
   fitting the pilot.

**RQ (EXP-6):** does a fixed native-resolution crop around the carried box beat plain
carry@640, and does it reach plain@1024's accuracy at >= 2x its throughput?

* **Arms:** CONTROL = plain@640 (deployed); **TREATMENT** = fixed 512-px crop, dead-band
  re-centre, no guard, @640; **CONTROL-2** = plain@1024 (the deployed size-gated fallback).
  Three arms, no guard arm — the guard's verdict is already recorded.
* **Primary metric: per-clip median IoU, Wilcoxon signed-rank, paired.** Not binary PASS —
  CONTROL already passes 32/38, so a PASS gate is ceiling-limited and would burn the run on
  an unreachable floor (the mistake §7's proceed gate made). Secondary: delivered-PASS
  (median IoU >= 0.25), exact McNemar.
* **n / unit:** **all 38 EXP-1 UAV123 clips**, unit = clip, same frozen seed boxes. No
  subsampling, so no selection-bias objection; 38 > the n>=25 floor.
* **Contamination stratum (new, forced by the promotion).** 12 of the 38 clips are the ones
  A4 was selected on in EXP-5, and they are the *hardest* 8 plus 4 easy — a biased subset in
  both directions. Pre-registered stratification is therefore **held-out 26 vs pilot 12**, and
  the **held-out 26 is the primary stratum**; it alone still clears n>=25. The pilot-12 is
  reported for completeness and is *not* what the verdict rests on. The tail-8 vs non-tail-30
  split is reported as a secondary descriptive cut.
* **Deflation:** UAV123 clips sharing a base sequence (`car1`/`car1_s`, `person1`/`person1_s`
  …) are one independent unit. Report raw n and deflated n; **cite the deflated p**.
* **Test:** Wilcoxon (primary, on the held-out 26); exact McNemar with `min_discordant = 6`
  (secondary); Holm within the Part VI family.
* **PASS gate (accuracy):** TREATMENT > CONTROL on the held-out 26, Wilcoxon p < 0.05
  deflated, effect not reversing on the pilot-12.
* **PASS gate (the one that decides shipping): throughput-matched parity vs CONTROL-2** —
  TREATMENT@640 within 0.03 median-of-median IoU of plain@1024, |PASS difference| <= 1 clip,
  at a measured on-device rate >= 2x (target >= 4.7 Hz vs 2.34 Hz). Report measured Hz for
  all three arms; a crop arm below ~4 Hz has spent the entire reason it exists. EXP-5 measured
  6.30 vs 2.34 Hz (2.7x) on 12 clips, so this gate is expected to hold — it is in the
  pre-registration to catch the case where it does not at scale.
* **Kill gate:** TIE or wrong direction vs CONTROL on the held-out 26 (P5.21's exact
  pattern), **or** TREATMENT loses to CONTROL-2 on accuracy without a >= 2x rate advantage ->
  kill. MODE 2 carry does not ship; plain carry + the size-gated 1024 fallback stays the only
  path, and the crop stays acquire-prefill-only exactly as P5.21 left it.
* **Small-frame caveat, pre-declared.** On 720x480 clips the window is `min(512, w, h) = 480`,
  which is barely a crop. `uav3` is such a clip and no crop arm moved it. Report the
  720x480 clips as a labelled subgroup rather than discovering them afterwards.
* **Visual:** per-clip IoU figure from `runs/exp6/results.json` via a committed
  `make_proof6.py`; overlays for the two largest wins and the largest loss, Read.
* **Code:** none beyond `run_exp5.py`'s crop wrapper with `guard: False`, run at gate scale.
  Reuse `run_exp1.py` staging.
* **Cost estimate.** ~1 day (114 clip-runs on-device ~= 3-4 hr; rest is scoring, proof,
  ledgers).
* **Estimate (pre-registered).** Median-of-median IoU: CONTROL 0.811, TREATMENT 0.845,
  CONTROL-2 0.816. PASS 32 / 35 / 36 of 38. Tail-8: 2 / 7 / 8. On the held-out 26 the effect
  should be **much smaller** than the pilot's — those clips are mostly at ceiling, where a
  crop has nothing to add — so Wilcoxon p ~ 0.05-0.30 and a real risk the primary stratum
  comes back a TIE while the tail cut is a clear win. Most likely honest verdict:
  **"throughput-matched parity with the 1024 fallback, tail-scoped win, not a blanket carry
  replacement."**

### Results (run 2026-07-26T23:40Z, `runs/exp6/`)

Ran as pre-registered: 3 arms x 38 clips = 114 clip-runs, same frozen `plan.json` staging as
EXP-1/EXP-5 (STRIDE=11, N_STEPS=24, ~264-frame window), SAM2 on the Orin over the ssh-stdio
bridge, `nvpmodel` 15W + `jetson_clocks`. CONTROL and TREATMENT share one `image_size=640`
bridge process; CONTROL-2 gets its own at 1024. Deterministic — a re-run reproduces the file.

| arm | median-of-median IoU | delivered PASS | tail-8 PASS | on-device Hz | lost steps |
|---|---|---|---|---|---|
| CONTROL plain@640 | 0.811 | 32/38 | 4/8 | 5.76 | 24 |
| **TREATMENT crop512@640** | **0.815** | **35/38** | **7/8** | **6.31** | 38 |
| CONTROL-2 plain@1024 | 0.817 | 36/38 | 8/8 | 2.34 | 31 |

**Strata, TREATMENT vs CONTROL** (Wilcoxon primary, deflated by base sequence; McNemar on
delivered-PASS secondary):

| stratum | n / n_eff | TRT | CTL | PASS | median diff | p raw | **p deflated** | McNemar |
|---|---|---|---|---|---|---|---|---|
| **held-out 26 (PRIMARY)** | 26 / 24 | 0.831 | 0.833 | 24 / 24 | **+0.0085** | 0.1208 | **0.0918** | b=0 c=0 |
| pilot 12 (contaminated) | 12 / 12 | 0.774 | 0.681 | 11 / 8 | +0.0735 | 0.01367 | 0.01367 | b=3 c=0, p=0.25 |
| all 38 (descriptive) | 38 / 36 | 0.815 | 0.811 | 35 / 32 | +0.0190 | 0.003965 | 0.002947 | b=3 c=0, p=0.25 |
| tail 8 | 8 / 8 | 0.703 | 0.223 | 7 / 4 | +0.0940 | 0.01562 | 0.01562 | b=3 c=0, p=0.25 |
| non-tail 30 | 30 / 28 | 0.853 | 0.834 | 28 / 28 | +0.0060 | 0.1128 | 0.0875 | b=0 c=0 |

**TREATMENT vs CONTROL-2** (the parity comparison): held-out 26 +0.0050 deflated p=0.566;
all 38 +0.0015 deflated p=0.6745; tail-8 +0.0080 p=0.945. Statistically indistinguishable
everywhere, at 2.7x the rate. That is the parity claim, and it is the one that ships.

**Gates, evaluated in code** (`runs/exp6/results.json` -> `gates`):

* **Accuracy gate: FAIL.** Held-out 26 is directionally right (+0.0085, 16 wins / 7 losses /
  3 ties, bootstrap CI [+0.0015, +0.024] excluding zero) and the pilot does not reverse it,
  but deflated p=0.0918 > 0.05. Not significant, so it is not claimed. The effect is real but
  tiny where it was measured: the held-out 26 sit at ceiling (both arms PASS 24/24, both at
  ~0.83), and a crop cannot improve a target the plain arm already holds at 0.83.
* **Throughput-matched parity gate: PASS** — d_IoU **-0.002**, d_PASS **-1** clip, rate
  **2.7x** (6.31 vs 2.34 Hz). Inside all three pre-registered bounds.
* **Kill gate: did not fire** — direction is not reversed and the rate advantage is present.

**The pre-registered estimate was almost exactly right.** PASS 32 / 35 / 36 predicted, 32 / 35
/ 36 measured. CONTROL 0.811 predicted, 0.811 measured; CONTROL-2 0.816 vs 0.817. Two misses:
TREATMENT's median-of-median came in 0.815, not the predicted 0.845 (the pilot's margin did
not survive contact with 26 ceiling clips — which the estimate itself warned about), and the
tail-8 CONTROL PASS was 4, not 2. The predicted p-range (0.05-0.30) and the predicted "TIE on
the primary while the tail is a clear win" both landed.

**`n_lost` is not a crop cost.** TREATMENT loses more steps (38 vs 24), but every one is
confined to `car11` / `uav3` / `uav8` — the three clips that score 0.000 in *all three* arms.
CONTROL {car11:2, uav3:10, uav8:12}, TREATMENT {car11:8, uav3:15, uav8:15}, CONTROL-2 {car11:8,
person21:1, uav3:7, uav8:15}. The crop never loses a target the plain arm holds; it loses
already-lost targets more completely.

**720x480 subgroup, as pre-declared:** `uav3` and `uav8`, the only two clips at that frame
size (the other 36 are 1280x720). The window is `min(512, 480) = 480`, i.e. barely a crop —
and both are 0.000 in both arms, so the subgroup is uninformative rather than negative.
`uav3` reaches 0.436 under CONTROL-2, so it is resolution-gated; a 480-px crop of a 480-px
frame cannot deliver that, only the 1024 fallback can. This is the size-gated-fallback
argument, measured.

**Cost, estimate vs actual.** Estimated ~3-4 hr of on-device time; actual **~12 min** total
(CONTROL ~180 s, TREATMENT 153 s, CONTROL-2 404 s). The estimate assumed 1024-arm timings
across all three arms; two of the three run at 640.

**Verdict: PARTIAL PASS — throughput-matched parity with the 1024 fallback, tail-scoped win,
not a blanket carry replacement.** Verbatim the pre-registered most-likely honest outcome.
The shipping gate passes: crop512@640 matches plain@1024's accuracy (d_IoU -0.002, d_PASS -1)
at 2.7x the on-device rate, so it is a strictly cheaper way to buy the fallback's accuracy.
The accuracy gate fails: against plain@640 on the held-out 26 the gain is +0.0085 at deflated
p=0.0918, a **bounded null on the ceiling clips**, not a win. Where the crop earns its keep is
the resolution-gated tail — 0.703 vs 0.223, PASS 7/4 — which is a descriptive secondary cut,
not a powered claim (n=8). Ship it as the size-gated path (crop512@640 replacing the 1024
fallback), not as the default carry.

### Proof

* `proof/exp6-arms.png` — all 38 clips sorted by CONTROL median IoU, three arms, `*` marking
  the 12 contaminated pilot clips. The resolution-gated tail collects on the left, where
  CONTROL's grey bars collapse and both TREATMENT and CONTROL-2 stand; the right two-thirds
  are the ceiling clips where all three arms are indistinguishable. Right panel: the parity
  gate, PASS.
* `proof/exp6-win.png` — `bike3` (delta +0.753), the largest TREATMENT win. CONTROL holds the
  cyclist at 0.71 on step 0 and is at **0.00 for steps 8, 15 and 23** — gone. TREATMENT's
  orange crop window follows the rider: 0.68, 0.50, 0.84, 0.92. The tail effect, in pixels.
* `proof/exp6-loss.png` — `car1_s` (delta -0.102), the largest TREATMENT loss, and the honest
  half. **Both arms hold the jeep for the whole window** (CONTROL 0.87/0.84/0.86/0.87,
  TREATMENT 0.86/0.78/0.75/0.76). The loss is mask tightness against the GT box convention,
  not a track loss — the crop's failure mode is a slightly worse box, never a dropped target.

---

## 9. EXP-7 — composed MODE 2, closed loop

Runs **only if EXP-4 and EXP-6 both pass**.

**RQ:** does MODE 2 (crop-ground + crop-carry) beat MODE 1 on delivered-PASS with the copter
flying its own control output?

* **Arms:** CONTROL = MODE 1 (`follow_click` + plain `orin_carry`, current deployed) vs
  TREATMENT = MODE 2 composed from EXP-4's and EXP-6's winners.
* **Metric:** delivered-PASS, identical definition to P6.2-DELIVERY. Secondary: acquire
  latency, on-device carry Hz.
* **n / unit:** **25 CARLA seeds**, unit = seed, paired, run live through the existing P6.2
  harness — **not a bank** (§10). Stratified to include >= 10 designations with native
  footprint < 80 px.
* **Deflation:** 25 independent CARLA seeds -> `n_effective = n_rows = 25`, same standing as
  P6.2-DELIVERY (explicitly not deflated).
* **Test:** exact McNemar; Holm per-Part and globally.
* **PASS / kill:** b >> c surviving Holm in both families, or record a bounded null in the
  P6.2-COUPLING style.
* **Scope caveat, carried forward verbatim:** grounding is held constant via **ORACLE
  designation** where required (G6: q8_0 is non-discriminative at 45 m nadir). Any claim is
  conditional on correct designation.
* **Code:** raise the crop source in `on_image` (`carla_debug_ui.py:2460-2470`) so
  `live["bgr"]` at 1920 reaches the crop path — **only if EXP-4 passed**; otherwise the crop
  stays on the 960 frame and `on_image` is untouched. Plus one `seg(...)` widget
  `normal | click-crop` in the `w3_src` designate row (~`:2090`), orthogonal to
  `designate` / `acquire`. MODE 2 composes only with `follow_click`; the caption-only
  `follow` button has no coordinate and stays MODE 1.
* **Cost estimate.** ~1-2 days.
* **Estimate (pre-registered).** TREATMENT 19/25 vs CONTROL 12/25 — high uncertainty, fully
  contingent on two upstream gates priced at roughly coin-flip each, so P(reaching EXP-7)
  ~ 0.25.

### Results — NOT RUN (2026-07-26T23:55Z)

**The entry gate did not fire, and the pre-registered response to that is not to run.** Both
upstream results are on record:

* **EXP-4 = MISS on its primary** (§6). C vs D b=1/c=0, below the 6-pair floor: lever (a'),
  the native-1920 plumbing, is retired. What survived is C vs A (b=8, c=0, p=0.0078) — the
  win is *magnification*, which the deployed 960 frame already supplies.
* **EXP-6 = PARTIAL PASS** (§8). The shipping/parity gate passes; the accuracy gate against
  plain@640 fails at deflated p=0.0918 on the held-out 26.

Neither is a pass in the sense §9 requires, and the composition makes that concrete rather
than merely procedural. **EXP-7's TREATMENT would be nearly identical to its CONTROL:**

| MODE 2 half | what EXP-4/EXP-6 leave of it | delta vs deployed CONTROL |
|---|---|---|
| crop-ground | EXP-4 retired the 1920 source; the crop stays on the 960 frame — which is `roi_reanchor`, **already live** at `carla_debug_ui.py:1901` | none |
| crop-carry | EXP-6: bounded null vs plain@640; a parity-and-2.7x replacement for the **1024 size-gated fallback** | fires only on the size-gated path |

So the pre-registered contrast has been emptied by its own upstream results: 25 live CARLA
seeds and ~1-2 days would be spent measuring the deployed system against itself plus a lever
that is a measured null on 24 of 26 held-out clips. The estimate priced P(reaching EXP-7)
~ 0.25 for exactly this reason.

**Verdict: NOT RUN — gate not met, and the composed contrast is empty by construction.**
Recorded as a pre-registered non-run, not a silent drop. What EXP-6 does authorize is a
**deploy change, not a campaign**: swap the size-gated 1024 carry fallback for crop512@640
(same accuracy, 2.7x the on-device rate). That is a UI/config edit backed by an n=38 parity
gate, and it needs no new imagery, no flight seeds and no new claim.

**What would reopen it.** A result that puts real magnification back on the table where the
deployed 960 path cannot reach — e.g. a designation task at a footprint the 960 frame
genuinely cannot resolve (S0's 40-px case, `s0-detail-headroom-40px.png`, is that regime).
EXP-7 as written is not that experiment; it would have to be re-pre-registered against a
contrast that is not already deployed.

---

## 10. Imagery decision

**One new bank, 25 single frames, ~50 MB. Nothing else.**

* **EXP-5 and EXP-6 run on existing UAV123** (1280x720, 38 clips, frozen seed boxes, GT
  present, directly comparable to EXP-1). The intuition that UAV123 is too small to test
  cropping is wrong for the reason in §2: SAM2 resizes everything to `image_size` anyway, so
  what a crop buys is target-px on a fixed grid. Zero imagery cost.
* **EXP-4 needs Bank-1920-single:** 25 single CARLA captures at `image_size_x/y = 1920,
  1920`, FOV 90, nadir 45 m, `Town10HD_Opt`, vehicles placed to hit the footprint strata,
  per-target pixel footprint in the manifest. This is the **only** asset in the repo with
  headroom above the 960/512 feed sizes — UAV123 (1280x720) and the CARLA GT bank (640x480,
  `cam_wh_fov: [640,480,90]`) are both below them. Cost: camera-attr change to
  `runners/carla_gt_bank.py` (`W, H = 640, 480` -> 1920) plus a single-frame mode; ~2-3 hr,
  ~50 MB.
* **EXP-7 needs no bank at all.** A 25-clip 1920 video bank would be ~13.8 GB (12x the
  existing bank's 188 MB/clip) and hours of capture. It is unnecessary: P6.2-DELIVERY's
  n=25 came from **live CARLA seeds through the flight harness**, not a frozen bank, and
  the live sensor is already 1920^2 (`LIVE_CAM_SIDE = 1920`, `:105`). EXP-7 reuses that.
  **13.8 GB and a day of capture saved.**

## 11. What is deliberately not being done

| Cut | Killed by |
|---|---|
| Re-test crop-for-VLM-grounding at all | Deployed (`roi_reanchor` live at `carla_debug_ui.py:1901`); EXP-2 `ground_sweep`: PT@256 0.769 > NL@1024 0.654 |
| The proposal's guard as literally stated ("reject growth > 2.5x") | `car10` failed by **shrinking** (`area_ratio` 0.36 -> 0.02) after a **displacement** jump; a grow-only area check catches neither |
| Area-only guard | Same: `runs/p521/roi_car10/results.json` shows `"reinforced": true` at frame 88 with `drifted: false` — a position error a `[0.4, 2.5]` area band cannot see |
| A single 960-vs-1920 comparison for EXP-4 | Confounds source resolution with 2x FOV loss. Replaced by the 2x2 with arm D |
| Carry arms without a `plain@1024` control | Every EXP-1 tail clip already passes at 1024 (bike3 0.649, car15 0.717, uav3 0.436, person21 0.537, building3 0.507, car13 0.769, truck2 0.793, truck3 0.852) with zero new code |
| Carry arms without a guard-alone control | Otherwise a guard win is misattributed to the crop |
| "Each step, re-centre on the current box" as specified | `_prep` writes every frame into SAM2's memory bank; per-step window jitter is synthetic ego-motion + zoom in every entry, i.e. the `roi.py:60-65` spiral. Replaced by dead-band re-centring |
| Box-scaled windows as the primary policy | `grounding/roi.py:60-65`: shrinking box -> shrinking window -> shrinking box. Kept only as EXP-5's A6 comparison arm |
| A standalone cadence (lever d) experiment | Held constant at dead-band re-centre; only worth isolating if EXP-5's guard arms survive *and* per-step cost bites |
| Bank-1920-video (25 clips x 300 frames) | ~13.8 GB / hours of capture for a question EXP-7 answers live through P6.2's own harness on an already-1920 sensor |
| Any SAM2 run on the 3090 | Standing rule; the tracker is on-device only |

## 12. Software versions and machine config

| item | value |
|---|---|
| CARLA | 0.9.16, `/home/gara/carla/CARLA_0.9.16/CarlaUE4.sh`, `Town10HD_Opt` |
| Renderer machine | RTX 3090, power limit **200 W** (`carla_gt_bank.POWER_W`, re-asserted per run by `reassert_power`) |
| Tracker machine | Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`, via `ssh jetson` |
| SAM2 bridge | `~/sam2-bench/carry_ssh_bridge.py --image-size {size}` |
| VLM | `phase3-terse100eos-1024-q8_0.gguf` + mmproj, on the Orin |
| venv | `.venv-ft` |
| Deployed UI defaults at campaign open | `ORIN_GROUND_RES = 512`, `ORIN_CARRY_SIZE = 640`, `LIVE_CAM_SIDE = 1920`, `CAM_W/CAM_H = 960`, `COPTER_ALT = 45.0` |

Deviations from the pre-registration, recorded as run:

* **S0 altitudes are solved at runtime**, not hardcoded — `alt = f·L/target_px` from the
  reference's own measured extent, floored at 20 m. Same intent, one less number to get wrong.
* **The 3090 sat at 220 W before this campaign; `reassert_power` pulled it to 200 W** and
  every run from here is at 200 W, matching the GT-bank config. Prior 220 W numbers are a
  different config and must not be rate-compared against these.
* **S0 disk was 36 MB, not <20 MB** — the six full 1920² frames are ~6 MB each as PNG. Kept
  as PNG deliberately: a JPEG of the native frame would add compression artifacts to the
  exact thing under test.

## 13. Status / next step

* 2026-07-26T12:09Z — campaign pre-registered.
* 2026-07-26T12:17Z — **S0 = PASS** (6/6 above the 1.30 gate, both smallest included,
  difference confirmed by eye on all six pairs). Lever (a') stays alive; the "native 1920"
  framing is not empty. Estimate was wrong in both magnitude and direction — see §5.
  **Next: EXP-4** — build the single 1920² imagery bank, then run the 2x2 (A 960/512,
  B 1920/1024, C 1920/512, D 960/256-upscaled), primary contrast C vs D.
* 2026-07-26T20:05Z — **EXP-4 = MISS on the primary (lever (a') retired), MODE 2 upheld on
  the secondaries.** C vs D b=1/c=0 (b+c below the 6-pair floor) so the native-1920 plumbing
  is dead; A vs D b=1/c=8 p=0.039 and C vs A b=8/c=0 p=0.0078 say the win is magnification,
  which the 960 frame already supplies. See §6. **Next: EXP-5**, the carry-crop mechanism
  pilot on UAV123 — exploratory, no new imagery, no claim.
* 2026-07-26T22:40Z — **EXP-5 = KILL as pre-registered** (kill gate 3: A5 5/8 tail vs A2
  8/8; proceed gate failed and was unreachable by construction). The six-arm decomposition
  localizes the kill: **lever e (the guard) is dead** — it self-latches by freezing its own
  reference, and cost the crop two tail clips for nothing; **lever c is answered** — FIXED
  beats SCALED, because a box-scaled window re-enters the `roi.py` shrink spiral and killed
  an easy clip. **Lever b (the fixed crop) survives and is free**: A4 tail 7/8 vs A1's 4/8,
  easy clips unchanged, and *faster* (6.30 vs 5.75 Hz; A2 is 2.34 Hz). See §7.
  **Next: EXP-6**, re-pre-registered in §8 with A4 promoted post-hoc, the guard dropped, and
  a held-out-26 primary stratum to keep the promotion from grading its own homework.
* 2026-07-26T23:40Z — **EXP-6 = PARTIAL PASS.** Parity/shipping gate PASS (crop512@640 vs
  plain@1024: d_IoU -0.002, d_PASS -1, **2.7x** the on-device rate); accuracy gate FAIL vs
  plain@640 on the held-out 26 (+0.0085, deflated **p=0.0918**) — a bounded null on ceiling
  clips. The win is confined to the resolution-gated tail (0.703 vs 0.223, PASS 7/4, n=8,
  descriptive). See §8. Landed exactly on the pre-registered most-likely verdict.
* 2026-07-26T23:55Z — **EXP-7 = NOT RUN**, gate not met (EXP-4 missed its primary, EXP-6 is
  partial) *and* the composed contrast is empty: EXP-4 retired the 1920 source so MODE 2's
  ground half collapses onto the already-deployed `roi_reanchor`, and EXP-6's carry half is a
  null except on the size-gated path. See §9. **Campaign closes here.** The one shipping
  action it authorizes is a config change, not a run: swap the size-gated **1024 carry
  fallback for crop512@640**.

## 14. Proof deliverables

Committed under `proof/`. Curated out of `runs/` (which is gitignored except `results.json`).

| file | what it shows | run / config |
|---|---|---|
| `s0-detail-headroom-40px.png` | S0, worst case for the downscale. Left = 96² window cut from the native 1920 frame; right = the same physical region taken from the 960 `INTER_AREA` downscale and LANCZOS-upscaled back. Native separates roof from windshield and holds the pavement tiling; the 960-sourced arm is a pink blob with a smeared lane line. Laplacian variance 992.7 vs 131.8 (7.53x). | S0, alt 113.2 m, footprint 40.5 px, `Town10HD_Opt`, 3090 @ 200 W |
| `s0-detail-headroom-103px.png` | Same comparison at the **deployed** nadir altitude (`COPTER_ALT = 45.0` m). 154² window, footprint 103 px, lapvar 416.6 vs 86.3 (4.83x). The regime the campaign is actually about — the gap is clear but no longer decisive, which is why EXP-4 has to convert it into a grounding number rather than assume it. | S0, alt 45.3 m |
| `exp4-arms.png` | EXP-4, both halves of the result in one figure. Left: per-target IoU for C (MODE 2 native crop) and A (deployed 960 crop), sorted by footprint — C clears the 0.5 line on 23 of 25 while A clears it on 15, and where A leads (4 targets) it leads by 0.08-0.17 while C's leads run to 1.0. Right: hit@0.5 and mean IoU for all four arms, all fed at 512. Reproduced by `make_proof.py` from `runs/exp4/results.json`. | EXP-4, n=25, `q8_0` on the Jetson, `Town10HD_Opt`, 3090 @ 200 W |
| `exp4-C-win-t06-yellow-taxi.png` | A C win the upscale arm cannot buy: 62 px target, caption "the yellow car", C at IoU 1.00 against D's 0.33. Prediction green, GT red, drawn on the real 512 feed. An orange distractor sits two car-lengths ahead — at 2x LANCZOS the two are the same smear. | EXP-4, arm C, `t06_small` |
| `exp4-C-loss-t03-grey-ambiguity.png` | The honest failure. Caption "the grey car", four grey cars in the crop; C grounds a different one (green) than GT (red), IoU 0.00, and D scores 0.00 too. Detail is not the binding constraint at C's remaining 8% — the referring expression is. | EXP-4, arm C, `t03_small` |
| `exp5-arms.png` | EXP-5, the whole pilot in one figure. Left: per-clip median IoU for all six arms, resolution-gated tail and easy controls split, 0.25 delivered-PASS line marked. Right: tail recovery and on-device Hz per arm. The quantitative claim — A4 (fixed crop, no guard) recovers 7/8 of the tail at A2's accuracy and 2.7x its rate, while A3/A5's zeros on `car13`/`bike3` are the guard, not the crop. Reproduced by `make_proof5.py` from `runs/exp5/results.json`. | EXP-5, n=12 UAV123 clips x 6 arms, SAM2 on the Orin, `D_MAX=4.2`, stride 11, 24 steps |
| `exp5-guard-latches.png` | The guard's failure mode, on pixels. `bike3`, A4 (top) vs A5 (bottom), steps 0/8/15/23 — identical seed, identical crop window (orange), GT green, carried box yellow. Both hold to step 8; then one genuine burst is vetoed in A5 and the frozen reference latches every subsequent step, so A5 has **no box at all** from step 15 while A4 rides the same burst out to 0.92. This is why lever e is shipped as a negative rather than retuned. | EXP-5, arm A4 vs A5, `bike3` |
| `exp5-scaled-strands.png` | The box-scaled window's failure mode. `car18` (an *easy* control A1 handles at 0.921), A4 (top) vs A6 (bottom). By step 8 A6's box has collapsed onto the car's front half (IoU 0.25) and dragged the window down with it; by step 15 the box is gone and the window sits on empty road while the car drives away up-frame. A4's fixed 512 window cannot shrink and tracks to 0.90. `roi.py:60-65`'s shrink spiral, reproduced. | EXP-5, arm A4 vs A6, `car18` |
| `exp6-arms.png` | EXP-6 at gate scale: per-clip median IoU for all 38 UAV123 clips, three arms, sorted by the deployed CONTROL so the resolution-gated tail collects on the left; `*` marks the 12 contaminated EXP-5 pilot clips excluded from the primary stratum. The shape *is* the verdict — CONTROL's grey bars collapse on the left while TREATMENT and CONTROL-2 stand, and the right two-thirds are three indistinguishable arms at ceiling. Right panel: the throughput-matched parity gate, PASS at 2.7x. Reproduced by `make_proof6.py` from `runs/exp6/results.json`. | EXP-6, n=38 x 3 arms, SAM2 on the Orin, stride 11, 24 steps |
| `exp6-win.png` | The largest TREATMENT win, `bike3` (+0.753). CONTROL (top) holds the cyclist at 0.71 on step 0 then reads **0.00 at steps 8, 15 and 23** — the target is gone. TREATMENT (bottom) has its orange 512 crop window riding the rider: 0.68, 0.50, 0.84, 0.92. The tail effect in pixels, and the reason the crop stays as the size-gated path. | EXP-6, CONTROL vs TREATMENT, `bike3` |
| `exp6-loss.png` | The largest TREATMENT loss, `car1_s` (-0.102) — and the reason the loss is cheap. **Both arms hold the jeep for the whole window** (CONTROL 0.87/0.84/0.86/0.87, TREATMENT 0.86/0.78/0.75/0.76); the deficit is mask tightness against the GT box convention, not a dropped track. The crop's worst case is a slightly worse box. | EXP-6, CONTROL vs TREATMENT, `car1_s` |
| `s0-scene-nadir-45m.jpg` | The full 1920² nadir frame the 103 px pair was cut from, downscaled to 960 for size. Establishes that the camera is genuinely nadir over a real Town10 street with the reference Mustang at frame centre — i.e. the geometry the numbers assume. `dominant_frac = 0.014`, so not a blank render. | S0, alt 45.3 m |

Both `pair_*.png` proof copies are NEAREST-magnified for legibility (x3 and x2); the
magnification is identical on both arms and adds no information. Unmagnified originals and
all six pairs are in `runs/s0/`.
