*Stage of the MODE 2 campaign, split out of `README.md` on 2026-07-26 so a session
working one stage does not load the other four. The section number below is unchanged,
so existing "§6" citations still resolve. Campaign context, imagery decision, versions
and proof deliverables stay in `README.md`.*

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

