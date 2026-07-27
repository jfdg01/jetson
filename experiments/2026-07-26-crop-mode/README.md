# MODE 2 "click crop" — native-resolution crop around the target (EXP-4 … EXP-7)

**Campaign dir:** `experiments/2026-07-26-crop-mode/` **Opened:** 2026-07-26T12:09Z (Madrid wall-clock) **Part:** VI residual thread. IDs **S0** (gate, no ID) then **EXP-4 … EXP-7**, contiguous after the stopped EXP-3. No collisions with EXP-1 (`2026-07-24-resolution-decoupled-carry`) or EXP-2 (same dir, grounding sweep). **Status:** S0 run and PASSED (2026-07-26T12:17Z, §5). EXP-4 unblocked, not yet started.

This file is the self-contained handoff. A fresh session with no prior context should be able to open it and start, continue, document or complete the campaign.

---

## 1. The proposal, as the repo owner stated it

> The live panel renders a 1920x1920 square viewport. Split the pipeline into two modes. **MODE 1 "normal"** (current deployed control): the VLM grounds the whole square frame downscaled to 1024/960; SAM2 then carries the same whole square frame downscaled to 640. **MODE 2 "click crop"**: the operator's click reveals where the target is, so crop a _native-resolution_ window around it — 960x960 or 540x540 out of the 1920 frame — so the target is 2x+ bigger with no upscale/resample loss. Apply the same trick to SAM2 by cropping around the _current box centre_ each step. Guard against degenerate boxes by ignoring a box that grows more than 2.5x in one frame (starting heuristic).

Four levers are named or implied: (a) crop-for-VLM-ground, (a') cut that crop from the **native 1920** frame rather than the 960 downscale, (b) crop-for-SAM2-carry, (c) window policy (fixed vs box-scaled), (d) re-centre cadence, (e) the degenerate-box guard.

## 2. Verdict on the proposal before any run

**Partly settled, partly live, and one framing is technically wrong.**

**Settled — do not re-run.** Lever (a) is deployed and measured. `roi_reanchor` (`experiments/2026-07-14-select-generalization/select_p55.py:92-117`) is live in `follow_click` (`runners/carla_debug_ui.py:1901-1902`), and EXP-2's `ground_sweep` already measured the point-crop beating the whole frame at every resolution — PT@256 hit@0.5 = 0.769 vs NL@1024 = 0.654. Cropping for the VLM is not an open question.

**Technically wrong framing.** "Native pixels, no upscale, no resample loss" does not describe what SAM2 receives. `StreamCarry._prep` (`experiments/2026-07-01-temporal-acquire-carry/stream_carry.py:95-99`) resizes **whatever it is handed** to `image_size`^2 — 640 today — and the ssh bridge does no resizing at all (`carry_ssh_bridge.py:60-63`). There is no path by which native pixels reach the model. The mechanism under test is **magnification on a fixed model grid**, not resample avoidance.

That reframing is what makes the carry half cheap: because SAM2 resizes everything anyway, the crop's effect is _target pixels on a fixed grid_, and that is source-resolution independent. A 512-px window from a 1280x720 UAV123 frame fed to a 640 grid puts a 20-px target at 25 px vs 10 px whole-frame — **2.5x magnification, the same mechanism at the same strength as the live 1920 rig**. EXP-5 and EXP-6 therefore need **no new imagery**.

**Live and genuinely untested.** (a') cutting the crop from the native 1920 sensor frame instead of the 960 `cv2.resize(..., INTER_AREA)` output at `carla_debug_ui.py:2467` — never done, and no offline bank in this repo has the headroom to try it (UAV123 is 1280x720, the CARLA GT bank is 640x480, both **below** the 512/640 feed sizes). And (b) feeding SAM2's own per-step propagation a crop — `_prep` resized the whole frame in **both** P5.21 arms, so this configuration has never existed.

**Near-dead by prior art, and the guard as stated does not save it.** P5.21 killed crop-fed _re-grounding_ of a running carry (plain 28/34 vs ROI 26/34, b=1/c=3, p=0.625, direction against ROI). Its one documented failure, `car10`, was a **displacement** error at frame 88 that `REINFORCE_DISP` measured and never vetoed, after which the box **shrank** (`area_ratio` 0.36 → 0.16 → 0.10 → 0.05 → 0.03 → 0.02). The proposal's guard is _grow-only_ and _area-only_, so it catches neither half of the only failure we have on record. It is replaced below by a bidirectional area veto plus a displacement veto.

## 3. Geometry the program rests on (derived, not measured)

Live rig: 1920^2 sensor (`LIVE_CAM_SIDE = 1920`), FOV 90, `COPTER_ALT = 45.0` m nadir. f = 960 / tan(45 deg) = **960 px**, so **21.3 px/m** at ground. A `vehicle.ford.mustang` (4.8 x 1.9 m) is **102 x 40 px** in the native frame.

| stage | today (MODE 1) | MODE 2 | target px on the model grid |
| --- | --- | --- | --- |
| VLM ground | 1920 -> 960 -> fed @512 | 540-px native crop -> fed @512 | 27 px -> **97 px (3.6x)** |
| SAM2 carry | 1920 -> 960 -> grid 640 | 960-px native crop -> grid 640 | 34 px -> **68 px (2.0x)** |

## 4. Open questions, ranked

1. Does magnifying the target on SAM2's fixed input grid rescue the resolution-gated tail at 640's throughput? The tail (`bike3, car15, uav3, person21`) is median IoU **0.000** at `image_size=640` and 0.44-0.72 at 1024 — that is "never latched", not "drifted", and magnification is the matching medicine. But **plain@1024 already fixes all eight tail clips** at 2.34 Hz vs 640's 5.76 Hz, so the only claim worth anything is **throughput-matched parity-or-better**, not raw accuracy.
2. Does per-step crop-recentring spiral? The self-referential geometry is documented independently of P5.21 in `grounding/roi.py:60-65` ("box 21px -> crop 86px -> garbage box"). Untested for SAM2 propagation.
3. Is the guard the lever, or is the crop? Never separated. A bidirectional area + displacement veto on _plain_ carry costs ~10 lines and might capture the whole effect.
4. Does CARLA at 1920 actually contain detail its own 960 downscale does not, at a ~100-px vehicle footprint? Mip/LOD streaming can cap useful detail well below sensor resolution. Unmeasured, and it gates everything about lever (a').
5. At matched zoom, does native source beat upscaled-from-960? The only question lever (a') really asks; it needs an FOV-matched control to be answerable at all.
6. Does composed MODE 2 survive the closed loop? Contingent, last.

---

## 5-9. The five stages, one file each

Each stage keeps its own pre-registration, results, deviations and estimate-vs-actual.

- **§5 — [S0 — detail-headroom probe (gate only, no ID, no claim)](S0.md)** — **PASS.** Detail-headroom probe; gate only, no ID and no claim.
- **§6 — [EXP-4 — native source vs zoom, disentangled (lever a')](EXP-4.md)** — **Primary missed.** Magnification is the lever; the "cut from the native 1920 frame" sub-claim does not survive, so `on_image` is never touched and the crop keeps coming off the 960 frame.
- **§7 — [EXP-5 — carry-crop mechanism pilot (levers b, c, e)](EXP-5.md)** — **Exploratory, treatment lost.** The degenerate-box guard is not safe — a box-scaled window re-enters the `roi.py` shrink spiral and killed an easy control. A4 (fixed 512 crop, dead-band re-centre, no guard) is carried forward as a declared post-hoc promotion.
- **§8 — [EXP-6 — gated carry-crop test](EXP-6.md)** — **Bounded null on the primary**, plus an engineering parity gate. Not registered in `thesis/claims.json`.
- **§9 — [EXP-7 — composed MODE 2, closed loop](EXP-7.md)** — **NOT RUN, pre-registered non-run.** Its gate ("EXP-4 and EXP-6 both pass") did not fire, and the two upstream results emptied the contrast — it would have measured the deployed system against itself. Reopening requires re-pre-registration.

## 10. Imagery decision

**One new bank, 25 single frames, ~50 MB. Nothing else.**

- **EXP-5 and EXP-6 run on existing UAV123** (1280x720, 38 clips, frozen seed boxes, GT present, directly comparable to EXP-1). The intuition that UAV123 is too small to test cropping is wrong for the reason in §2: SAM2 resizes everything to `image_size` anyway, so what a crop buys is target-px on a fixed grid. Zero imagery cost.
- **EXP-4 needs Bank-1920-single:** 25 single CARLA captures at `image_size_x/y = 1920, 1920`, FOV 90, nadir 45 m, `Town10HD_Opt`, vehicles placed to hit the footprint strata, per-target pixel footprint in the manifest. This is the **only** asset in the repo with headroom above the 960/512 feed sizes — UAV123 (1280x720) and the CARLA GT bank (640x480, `cam_wh_fov: [640,480,90]`) are both below them. Cost: camera-attr change to `runners/carla_gt_bank.py` (`W, H = 640, 480` -> 1920) plus a single-frame mode; ~2-3 hr, ~50 MB.
- **EXP-7 needs no bank at all.** A 25-clip 1920 video bank would be ~13.8 GB (12x the existing bank's 188 MB/clip) and hours of capture. It is unnecessary: P6.2-DELIVERY's n=25 came from **live CARLA seeds through the flight harness**, not a frozen bank, and the live sensor is already 1920^2 (`LIVE_CAM_SIDE = 1920`, `:105`). EXP-7 reuses that. **13.8 GB and a day of capture saved.**

## 11. What is deliberately not being done

| Cut | Killed by |
| --- | --- |
| Re-test crop-for-VLM-grounding at all | Deployed (`roi_reanchor` live at `carla_debug_ui.py:1901`); EXP-2 `ground_sweep`: PT@256 0.769 > NL@1024 0.654 |
| The proposal's guard as literally stated ("reject growth > 2.5x") | `car10` failed by **shrinking** (`area_ratio` 0.36 -> 0.02) after a **displacement** jump; a grow-only area check catches neither |
| Area-only guard | Same: `runs/p521/roi_car10/results.json` shows `"reinforced": true` at frame 88 with `drifted: false` — a position error a `[0.4, 2.5]` area band cannot see |
| A single 960-vs-1920 comparison for EXP-4 | Confounds source resolution with 2x FOV loss. Replaced by the 2x2 with arm D |
| Carry arms without a `plain@1024` control | Every EXP-1 tail clip already passes at 1024 (bike3 0.649, car15 0.717, uav3 0.436, person21 0.537, building3 0.507, car13 0.769, truck2 0.793, truck3 0.852) with zero new code |
| Carry arms without a guard-alone control | Otherwise a guard win is misattributed to the crop |
| "Each step, re-centre on the current box" as specified | `_prep` writes every frame into SAM2's memory bank; per-step window jitter is synthetic ego-motion + zoom in every entry, i.e. the `roi.py:60-65` spiral. Replaced by dead-band re-centring |
| Box-scaled windows as the primary policy | `grounding/roi.py:60-65`: shrinking box -> shrinking window -> shrinking box. Kept only as EXP-5's A6 comparison arm |
| A standalone cadence (lever d) experiment | Held constant at dead-band re-centre; only worth isolating if EXP-5's guard arms survive _and_ per-step cost bites |
| Bank-1920-video (25 clips x 300 frames) | ~13.8 GB / hours of capture for a question EXP-7 answers live through P6.2's own harness on an already-1920 sensor |
| Any SAM2 run on the 3090 | Standing rule; the tracker is on-device only |

## 12. Software versions and machine config

| item | value |
| --- | --- |
| CARLA | 0.9.16, `/home/gara/carla/CARLA_0.9.16/CarlaUE4.sh`, `Town10HD_Opt` |
| Renderer machine | RTX 3090, power limit **200 W** (`carla_gt_bank.POWER_W`, re-asserted per run by `reassert_power`) |
| Tracker machine | Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`, via `ssh jetson` |
| SAM2 bridge | `~/sam2-bench/carry_ssh_bridge.py --image-size {size}` |
| VLM | `phase3-terse100eos-1024-q8_0.gguf` + mmproj, on the Orin |
| venv | `.venv-ft` |
| Deployed UI defaults at campaign open | `ORIN_GROUND_RES = 512`, `ORIN_CARRY_SIZE = 640`, `LIVE_CAM_SIDE = 1920`, `CAM_W/CAM_H = 960`, `COPTER_ALT = 45.0` |

Deviations from the pre-registration, recorded as run:

- **S0 altitudes are solved at runtime**, not hardcoded — `alt = f·L/target_px` from the reference's own measured extent, floored at 20 m. Same intent, one less number to get wrong.
- **The 3090 sat at 220 W before this campaign; `reassert_power` pulled it to 200 W** and every run from here is at 200 W, matching the GT-bank config. Prior 220 W numbers are a different config and must not be rate-compared against these.
- **S0 disk was 36 MB, not <20 MB** — the six full 1920² frames are ~6 MB each as PNG. Kept as PNG deliberately: a JPEG of the native frame would add compression artifacts to the exact thing under test.

## 13. Status / next step

- 2026-07-26T12:09Z — campaign pre-registered.
- 2026-07-26T12:17Z — **S0 = PASS** (6/6 above the 1.30 gate, both smallest included, difference confirmed by eye on all six pairs). Lever (a') stays alive; the "native 1920" framing is not empty. Estimate was wrong in both magnitude and direction — see §5. **Next: EXP-4** — build the single 1920² imagery bank, then run the 2x2 (A 960/512, B 1920/1024, C 1920/512, D 960/256-upscaled), primary contrast C vs D.
- 2026-07-26T20:05Z — **EXP-4 = MISS on the primary (lever (a') retired), MODE 2 upheld on the secondaries.** C vs D b=1/c=0 (b+c below the 6-pair floor) so the native-1920 plumbing is dead; A vs D b=1/c=8 p=0.039 and C vs A b=8/c=0 p=0.0078 say the win is magnification, which the 960 frame already supplies. See §6. **Next: EXP-5**, the carry-crop mechanism pilot on UAV123 — exploratory, no new imagery, no claim.
- 2026-07-26T22:40Z — **EXP-5 = KILL as pre-registered** (kill gate 3: A5 5/8 tail vs A2 8/8; proceed gate failed and was unreachable by construction). The six-arm decomposition localizes the kill: **lever e (the guard) is dead** — it self-latches by freezing its own reference, and cost the crop two tail clips for nothing; **lever c is answered** — FIXED beats SCALED, because a box-scaled window re-enters the `roi.py` shrink spiral and killed an easy clip. **Lever b (the fixed crop) survives and is free**: A4 tail 7/8 vs A1's 4/8, easy clips unchanged, and _faster_ (6.30 vs 5.75 Hz; A2 is 2.34 Hz). See §7. **Next: EXP-6**, re-pre-registered in §8 with A4 promoted post-hoc, the guard dropped, and a held-out-26 primary stratum to keep the promotion from grading its own homework.
- 2026-07-26T23:40Z — **EXP-6 = PARTIAL PASS.** Parity/shipping gate PASS (crop512@640 vs plain@1024: d_IoU -0.002, d_PASS -1, **2.7x** the on-device rate); accuracy gate FAIL vs plain@640 on the held-out 26 (+0.0085, deflated **p=0.0918**) — a bounded null on ceiling clips. The win is confined to the resolution-gated tail (0.703 vs 0.223, PASS 7/4, n=8, descriptive). See §8. Landed exactly on the pre-registered most-likely verdict.
- 2026-07-26T23:55Z — **EXP-7 = NOT RUN**, gate not met (EXP-4 missed its primary, EXP-6 is partial) _and_ the composed contrast is empty: EXP-4 retired the 1920 source so MODE 2's ground half collapses onto the already-deployed `roi_reanchor`, and EXP-6's carry half is a null except on the size-gated path. See §9. **Campaign closes here.** The one shipping action it authorizes is a config change, not a run: swap the size-gated **1024 carry fallback for crop512@640**.

## 14. Proof deliverables

Committed under `proof/`. Curated out of `runs/` (which is gitignored except `results.json`).

| file | what it shows | run / config |
| --- | --- | --- |
| `s0-detail-headroom-40px.png` | S0, worst case for the downscale. Left = 96² window cut from the native 1920 frame; right = the same physical region taken from the 960 `INTER_AREA` downscale and LANCZOS-upscaled back. Native separates roof from windshield and holds the pavement tiling; the 960-sourced arm is a pink blob with a smeared lane line. Laplacian variance 992.7 vs 131.8 (7.53x). | S0, alt 113.2 m, footprint 40.5 px, `Town10HD_Opt`, 3090 @ 200 W |
| `s0-detail-headroom-103px.png` | Same comparison at the **deployed** nadir altitude (`COPTER_ALT = 45.0` m). 154² window, footprint 103 px, lapvar 416.6 vs 86.3 (4.83x). The regime the campaign is actually about — the gap is clear but no longer decisive, which is why EXP-4 has to convert it into a grounding number rather than assume it. | S0, alt 45.3 m |
| `exp4-arms.png` | EXP-4, both halves of the result in one figure. Left: per-target IoU for C (MODE 2 native crop) and A (deployed 960 crop), sorted by footprint — C clears the 0.5 line on 23 of 25 while A clears it on 15, and where A leads (4 targets) it leads by 0.08-0.17 while C's leads run to 1.0. Right: hit@0.5 and mean IoU for all four arms, all fed at 512. Reproduced by `make_proof.py` from `runs/exp4/results.json`. | EXP-4, n=25, `q8_0` on the Jetson, `Town10HD_Opt`, 3090 @ 200 W |
| `exp4-C-win-t06-yellow-taxi.png` | A C win the upscale arm cannot buy: 62 px target, caption "the yellow car", C at IoU 1.00 against D's 0.33. Prediction green, GT red, drawn on the real 512 feed. An orange distractor sits two car-lengths ahead — at 2x LANCZOS the two are the same smear. | EXP-4, arm C, `t06_small` |
| `exp4-C-loss-t03-grey-ambiguity.png` | The honest failure. Caption "the grey car", four grey cars in the crop; C grounds a different one (green) than GT (red), IoU 0.00, and D scores 0.00 too. Detail is not the binding constraint at C's remaining 8% — the referring expression is. | EXP-4, arm C, `t03_small` |
| `exp5-arms.png` | EXP-5, the whole pilot in one figure. Left: per-clip median IoU for all six arms, resolution-gated tail and easy controls split, 0.25 delivered-PASS line marked. Right: tail recovery and on-device Hz per arm. The quantitative claim — A4 (fixed crop, no guard) recovers 7/8 of the tail at A2's accuracy and 2.7x its rate, while A3/A5's zeros on `car13`/`bike3` are the guard, not the crop. Reproduced by `make_proof5.py` from `runs/exp5/results.json`. | EXP-5, n=12 UAV123 clips x 6 arms, SAM2 on the Orin, `D_MAX=4.2`, stride 11, 24 steps |
| `exp5-guard-latches.png` | The guard's failure mode, on pixels. `bike3`, A4 (top) vs A5 (bottom), steps 0/8/15/23 — identical seed, identical crop window (orange), GT green, carried box yellow. Both hold to step 8; then one genuine burst is vetoed in A5 and the frozen reference latches every subsequent step, so A5 has **no box at all** from step 15 while A4 rides the same burst out to 0.92. This is why lever e is shipped as a negative rather than retuned. | EXP-5, arm A4 vs A5, `bike3` |
| `exp5-scaled-strands.png` | The box-scaled window's failure mode. `car18` (an _easy_ control A1 handles at 0.921), A4 (top) vs A6 (bottom). By step 8 A6's box has collapsed onto the car's front half (IoU 0.25) and dragged the window down with it; by step 15 the box is gone and the window sits on empty road while the car drives away up-frame. A4's fixed 512 window cannot shrink and tracks to 0.90. `roi.py:60-65`'s shrink spiral, reproduced. | EXP-5, arm A4 vs A6, `car18` |
| `exp6-arms.png` | EXP-6 at gate scale: per-clip median IoU for all 38 UAV123 clips, three arms, sorted by the deployed CONTROL so the resolution-gated tail collects on the left; `*` marks the 12 contaminated EXP-5 pilot clips excluded from the primary stratum. The shape _is_ the verdict — CONTROL's grey bars collapse on the left while TREATMENT and CONTROL-2 stand, and the right two-thirds are three indistinguishable arms at ceiling. Right panel: the throughput-matched parity gate, PASS at 2.7x. Reproduced by `make_proof6.py` from `runs/exp6/results.json`. | EXP-6, n=38 x 3 arms, SAM2 on the Orin, stride 11, 24 steps |
| `exp6-win.png` | The largest TREATMENT win, `bike3` (+0.753). CONTROL (top) holds the cyclist at 0.71 on step 0 then reads **0.00 at steps 8, 15 and 23** — the target is gone. TREATMENT (bottom) has its orange 512 crop window riding the rider: 0.68, 0.50, 0.84, 0.92. The tail effect in pixels, and the reason the crop stays as the size-gated path. | EXP-6, CONTROL vs TREATMENT, `bike3` |
| `exp6-loss.png` | The largest TREATMENT loss, `car1_s` (-0.102) — and the reason the loss is cheap. **Both arms hold the jeep for the whole window** (CONTROL 0.87/0.84/0.86/0.87, TREATMENT 0.86/0.78/0.75/0.76); the deficit is mask tightness against the GT box convention, not a dropped track. The crop's worst case is a slightly worse box. | EXP-6, CONTROL vs TREATMENT, `car1_s` |
| `s0-scene-nadir-45m.jpg` | The full 1920² nadir frame the 103 px pair was cut from, downscaled to 960 for size. Establishes that the camera is genuinely nadir over a real Town10 street with the reference Mustang at frame centre — i.e. the geometry the numbers assume. `dominant_frac = 0.014`, so not a blank render. | S0, alt 45.3 m |

Both `pair_*.png` proof copies are NEAREST-magnified for legibility (x3 and x2); the magnification is identical on both arms and adds no information. Unmagnified originals and all six pairs are in `runs/s0/`.
