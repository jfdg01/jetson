# RESULTS — Part III · Persistent tracking / object permanence (v3, T0–T4 + levers)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part III — Persistent tracking / object permanence (v3)

Branch `v3/object-permanence`. Problem: keep a lock on a moving target across occlusion/scale change. Headline metrics: temporal (SOT success-precision, ID switches, re-acq time, oracle coverage). Single-frame IoU@0.25 retained as per-anchor sanity check.  
Charter: [`experiments/2026-06-18-part3-charter/README.md`](../../experiments/2026-06-18-part3-charter/README.md)

---

### T0 — Cadence & dynamics harness (2026-06-18) ✅
Full writeup: [`experiments/2026-06-18-t0-cadence/`](../../experiments/2026-06-18-t0-cadence/README.md)  
On-Orin anchor-cadence sweep + tracker cost + dynamics analysis. Anchor = Qwen2-VL-2B Q8_0 `phase3-refdrone-1024-q8_0`.

| Probe | Metric | Value |
|---|---|---|
| **T0a anchor cadence** | wall Hz @512/768/1024 (N=8) | **0.44 / 0.27 / 0.16 Hz** |
| | prefill @512/768/1024 | 1113 / 2431 / 5111 ms (dominant, ∝ pixels) |
| | decode (resolution-independent) | ~1.1 s / 24 tok ≈ 21.6 tok/s |
| | power/thermal/mem | idle 5.2W, mean 10.9W, peak 11.7W; 62.7°C; 4849 MB; no swap |
| **T0b tracker cost** | `ByteTracker.update()` median (1180 fr) | **0.051 ms** → ~1000× headroom under 50 ms |
| | coast horizon (`MAX_LOST_FRAMES=30`) | **1.5 s** @ 20 Hz |
| **T0c dynamics** | target px velocity (nadir, 1–10 m/s, 10–30 m) | 18.5–554 px/s (≤27.7 px/frame) |
| **T0d re-ID geometry** | target crop @10/20/30 m | 111×222 / 55×111 / 37×74 px |

**Key verdicts:** anchor_period (2.26 s @512, median wall 2264.6 ms) > coast_horizon (1.5 s, a configured `MAX_LOST_FRAMES = 30` at 20 Hz, not a measurement) → re-acq must be event-triggered on loss. Tracker holds lock between anchors with ~1000× headroom. **Spine confirmed: Q8_0 @512** — no fidelity benefit is *possible* at a 640×480 source because `_resize_keep_aspect` is downscale-only, so 768/1024 only add latency. **Argued, not measured (corrected 2026-07-21T20:20Z, R-21):** T0 fed a synthetic 640×480 frame of rectangles and never scored fidelity; the earlier wording "no fidelity gain" read as a measurement. On higher-resolution sources the resolution choice is *not* free — the 2026-06-30 whole-frame sweep below measures 512 = 31.4% vs 1024 = 63.1% on real RefDrone imagery.

---

### T1 — Data & temporal contract (2026-06-18) ✅
Full writeup: [`experiments/2026-06-18-t1-temporal-contract/`](../../experiments/2026-06-18-t1-temporal-contract/README.md)  
Temporal-metric suite added to `grounding/contract.py` (SOT success/precision, ID switches, purity, reacq time, oracle coverage, following error). Memoryless-ByteTrack baseline established.

| Clip | SOT succ | coverage | ID sw | purity | reacq fail | follow px |
|---|---|---|---|---|---|---|
| `clean_follow` (control) | 1.000 | 1.000 | 0 | 1.000 | 0/1 | 0.03 |
| `crossing_occlusion` | 0.827 | 0.575 | **1** | **0.725** | **1/2** | 67.7 |

**Finding:** memoryless tracker re-locks wrong same-class object after occlusion — purity 0.725, 1 ID-switch, 1/2 reacqs failed. Constraint #2 (object permanence) made numeric.

---

### T2 — Permanence mechanism (2026-06-24) ✅
Full writeup: [`experiments/2026-06-24-t2-permanence/`](../../experiments/2026-06-24-t2-permanence/README.md)  
Appearance memory: store target descriptor at acquisition, re-acquire by min descriptor distance + refuse-to-lock gate. EMA refinement while locked. Pixels not rendered (T1 decision); appearance = per-instance scalar with noise scaling by crop size.

| Policy | ID sw | purity | reacq fail | coverage | SOT succ | follow px |
|---|---|---|---|---|---|---|
| memoryless baseline (T1) | 1 | 0.725 | 1 | 0.575 | 0.827 | 67.7 |
| **re-ID, snr ≳ 1** | **0** | **1.000** | **0** | **0.695** | **1.000** | **0.13** |
| re-ID, snr ≤ 0.8 (below knee) | 1 | 0.751 | 1 | 0.575 | 0.827 | 67.7 |

**✅ Gate PASS (snr ≳ 1):** appearance gate fully resolves wrong-object re-lock above the knee; degrades to baseline below it. Coverage 0.695 = visible-frame ceiling (139/200). Control unchanged.

**n and provenance caveat (added 2026-07-21T20:20Z, R-21):** this block is **one scripted clip, n_effective = 1** — the PASS rests on a single Bernoulli draw in which one ID switch either happens or does not, so there is no interval and no test behind the 1 → 0. The numbers above reproduce `experiments/2026-06-24-t2-permanence/README.md` verbatim, but **the scored output was never written to disk** — that campaign dir holds only `README.md` and `permanence.gif`, so the figures survive only in prose and this ledger; treat the block as counts-only. The same applies to the 139/200 decomposition (200 − 44 occluded − 17 out-of-frame = 139; the clip length of 200 frames is checkable in T1's `baseline_scores.json`, the 44/17 split is not). Regenerable in principle via `runners/sitl/reid_policy.py --score <clip_dir> --snr <S>`; note the rerun command recorded in `thesis/claims.json` (`grounding.eval.score_clips`) points at a module that does not exist.

---

### T3 — Closed-loop integration in SITL (2026-06-24) ✅
Full writeup: [`experiments/2026-06-24-t3-closed-loop/`](../../experiments/2026-06-24-t3-closed-loop/README.md)  
Lock drives the camera (cascade-PID → body velocity → copter → re-projection). 20 Hz control / 1 Hz detect, 10 m alt. Distractor crosses + briefly occludes at t=29–31 s.

| Policy | Kinematic A/B coverage | Live ArduCopter SITL coverage | Occlusion frames |
|---|---|---|---|
| memoryless baseline | 49.2% | 53.7% | 40 |
| **re-ID (snr 8)** | **97.6%** | **71.5%** | 40 |

**✅ Gate PASS:** 97.6% kinematic / 71.5% live SITL. ~~Phase-C ≈0% →~~ **comparator withdrawn 2026-07-21 (R-7):** Phase C recorded 39% oracle / 21% track coverage, not ~0% (the ~0% traces only to the T3 charter's expectation text), and every Phase-C Branch-2 perception number was retracted on 2026-07-20 when P6.0 found the camera pitched at the sky. There is no valid Phase-C baseline to improve on; the kinematic-vs-live pair below is what this campaign measured. Live margin smaller due to PID-lag + inertia lowering both policies' absolute coverage; direction + mechanism hold.

**n and provenance caveat (added 2026-07-21T20:20Z, R-21):** every cell above is **one independent fresh flight** (campaign README: "One independent fresh flight per policy"), so n = 1 per cell and the third significant figure is frame-count arithmetic *within* one flight, not precision — read the pair as ~49% → ~98% kinematic and ~54% → ~72% live. In a closed loop the controller's output at *t* determines the pixels at *t+1*, so a single early divergence propagates through every later frame and the frame fractions are not independent draws. The perception input is the T2 **synthetic per-instance scalar descriptor, not rendered pixels**. **No results file was retained** — `experiments/2026-06-24-t3-closed-loop/` holds only `README.md` and `closedloop.gif` — so the numbers survive in prose and this ledger only. Saying anything about a *rate* here needs n ≥ 10 flights per arm.

---

### T4 — On-Orin deployment + sim-to-device (2026-06-24) ✅
Full writeup: [`experiments/2026-06-24-t4-deployment/`](../../experiments/2026-06-24-t4-deployment/README.md)  
Integrated two-tier loop on actual Orin Nano 8 GB (15 W). One file (`bytetrack.py`) pushed to device.

| Tier | T0 reference (T0a: Orin · T0b: RTX 3090) | Orin (T4) | Sim-to-device |
|---|---|---|---|
| fast: `ByteTracker.update` median (p99) | 0.051 ms (0.103) — **T0b, RTX 3090** | **0.143 ms (0.291)** | 2.8× slower, **99.7% of 50 ms budget free** |
| slow: VLM anchor @512 wall | 2265 ms (0.44 Hz) — **T0a, Orin** | **2264 ms (0.44 Hz), 100% parse** | **−0.03% — same device, reproducibility check, not a sim-to-device gap** |

**Header + column correction (2026-07-21T20:20Z, R-21):** the reference column was headed "Dev box / T0a", but only the *tracker* row's reference ran on the dev box — T0a ran on the Orin (`t0-results-combined-authoritative.json`: `T0a.device = "Orin Nano 8GB, nvpmodel -m 0 (15 W)"`; `T0b.host = "3090 (x86_64)"`). The tracker row is therefore a genuine dev-box → device transfer; the anchor row is not. Its −0.03% (2265 → 2264 ms) is the same Orin through the same llama.cpp server on both sides — a quantity that cannot fail by construction, and the T4 campaign README words it correctly as "~0 % (same device path)". The qualifier was dropped on the way into this ledger and is restored above.

**✅ Gate PASS:** fast tracker holds 20 Hz with ~350× headroom; anchor reproduces T0a cadence. `deploys_within_t0_budget = True`. **T0–T4 all GATE PASS. Part III COMPLETE.**

---

### 2026-06-26 — Terse output re-LoRA
Full writeup: [`experiments/2026-06-25-terse-output-retrain/`](../../experiments/2026-06-25-terse-output-retrain/README.md)

Retrain anchor to emit 4 space-separated integers instead of `{"bbox": [...]}`. One variable changed; base/data/resolution/LoRA/quant identical to 62.6% deploy.

**Iter-1** (bare ints 0–1000): model reverted to bracketed prior `[x1, x2, x3, x4]` — shed only the `{"bbox": …}` wrapper. Root cause: Qwen tokenizes digits 1-per-token, so digit count dominates, not JSON syntax.

| Metric | JSON deploy | iter-1 | iter-2b (deploy) |
|---|---|---|---|
| RefDrone IoU@0.25 (Orin Q8_0, n=439) | 62.6% | 61.0% (−1.6pp noise) | **63.1%** (+0.5pp) |
| parse_rate (Orin) | 100% | 99.3% | **100%** |
| decode tokens | ~24 (synthetic frame) · **21 (real imgs)** | 21 (synthetic frame) | **12** (−43% vs the 21-tok JSON median on the same 20 real images) |
| decode ms | 967 | — | **531** (−45%) |
| anchor wall @512 | 1807 ms (real imgs, n=20) | 2114 ms (synthetic frame, n=8 — **−6.7% vs its own 2265 ms JSON baseline**, not +17% vs 1807) | **1372 ms** (−24% vs 1807) |

**Two latency harnesses in one table (annotated 2026-07-21T20:20Z, R-21):** the JSON and iter-2b latency/token cells come from the **n=20 real-image** harness (`decode_real.json`: JSON `wall_ms_median` 1807.5 / `decode_tok_median` 21; iter-2b 1371.9 / 12), while the iter-1 cells come from the **n=8 synthetic-anchor-frame** harness whose own JSON baseline was 2265 ms / ~24 tok. The campaign README flags that synthetic frame as OOD ("both models fall back to the 0–1000 tuple prior, so it under-reports — real images are the valid measurement"). Reading 1807 → 2114 as a +17% iter-1 regression, or ~24 → 12 as the quoted −43%, crosses the two series; both cells now carry their own baseline. The published −43% and −24% are unchanged and correct against the real-image JSON medians (21 tok, 1807 ms).

**Iter-2b win** (bare ints 0–100 + EOS-supervision fix): halve the digits + supervise `<|im_end|>` on the target (iter-2 without fix collapsed to 5% parse — outputs never learned to stop). Clean bare `28 44 36 59`, 100% parse. **Strict upgrade: better accuracy AND ~half decode.** Replaces the deploy artifact.

---

### 2026-06-26 — ROI-crop anchor (GATE PASS)
Full writeup: [`experiments/2026-06-25-roi-crop-anchor/`](../../experiments/2026-06-25-roi-crop-anchor/README.md)  
Inference-time only — no retraining. Feed anchor a crop around tracker's box (GT box × margin M) instead of full frame.

| Config (M=2.0) | Prefill ms (Orin Q8_0, 15W) | Decode ms | IoU@0.25, n=439 — **machine/quant per cell** | vs full-frame |
|---|---|---|---|---|
| full-frame @1024 (baseline) | 3691 | 966 | 62.6% **(Orin, GGUF Q8_0)** · 59.5% **(RTX 3090, HF bf16)** | — |
| **ROI crop @512 ← deploy** | **1374** | 964 | **85.2%** **(RTX 3090, HF bf16)** | **2.7× prefill · +25.7 pp (HF→HF)** |
| ROI crop @384 (max-speed) | 885 | 964 | 82.5% **(RTX 3090, HF bf16)** | 4.2× prefill · +23.0 pp (HF→HF) |
| full-frame @512 (downscaled) | — | — | 15.9% **(RTX 3090, HF bf16)** | resolution ceiling laid bare |

**Cross-machine correction (2026-07-21T20:20Z, R-7/R-21).** The accuracy column was headed "IoU@0.25 (HF n=439)" but was a **cross-machine, cross-quantisation composite**: every ROI arm is HF bf16 on the RTX 3090 (`sweep_summary.json`), while the 62.6% it was subtracted from is GGUF Q8_0 on the Orin (the Part II deploy figure). The previously published deltas **+22.6 pp** and **+19.9 pp** were that subtraction and are **superseded, not withdrawn** — the effect is real and enormous either way. They are replaced above by HF→HF deltas against the HF bf16 @1024 full-val (**59.5%**, n=439, `runners/runs/20260617T212559Z/results.json`, `full_val.iou_gate_pass_rate`). The sweep's own in-session HF full-frame-*native* control is **64.0%** (`sweep_summary.json`, key `[inf, native]`, 281/439), which gives +21.2 pp — so the sign and scale of the lever do not depend on which HF baseline is chosen. Latency remains Orin Q8_0 on both sides and is unaffected. **Selection caveat:** M=2.0 @512 (374/439) over M=1.5 @512 (368/439) is a 6-item difference on shared items, and all 15 grid cells were scored on one sample draw — read the peak as a plateau on which we took a point, not a single optimum. **Still open:** an **on-device Q8_0 ROI accuracy** number, the one follow-up the original campaign named before the deploy default was flipped. It is being measured now under [`experiments/2026-07-21-roi-ondevice/`](../../experiments/2026-07-21-roi-ondevice/README.md) (REMEDIATION R-14, paired, both arms on the Orin at Q8_0 on the deployed terse checkpoint). **No number from that campaign is published here yet — it has not finished.**

Drift (RQ4): flat **82.5–83.6%** up to 0.5·box prior drift (vs 85.2% undrifted), and **74.3–79.7%** even at full-box drift — all above baseline. *(Corrected 2026-07-21T20:20Z, R-21: the previously published upper bound "82–85%" is not attained by any drifted arm — 85.2% is the zero-drift point; measured drifted range across shift levels 0.25–1.0 is 326–367/439. Same phrasing appears in the campaign README. There is no pre-registered bar on this probe and the drift direction is a **single seeded draw** per sample per level, so these levels carry sampling error in the perturbation as well as in the items.)* Tight upscaled crop is *both* faster *and* more accurate (super-resolution beats resolution constraint #2). Decode unchanged — orthogonal to terse decode lever; two stack toward sub-1s anchor.

---

### 2026-06-26 — ROI re-anchor demo tab + live on-device confirm
Full writeup: [`experiments/2026-06-26-roi-demo-tab/`](../../experiments/2026-06-26-roi-demo-tab/README.md)  
ROI lever wired into deploy GUI ("Re-anchor speedup" tab). Live on deployed terse Q8_0 model.

| Upload | Full-frame prefill | ROI re-anchor prefill | Speedup |
|---|---|---|---|
| "the white car" | 4034 ms | 1388 ms | 2.91× |
| "the red car" | 3042 ms | 1375 ms | 2.21× |
| "the bus" | 3696 ms | 1373 ms | 2.69× |

ROI prefill pinned at ~1375 ms (fixed 512×512, matches offline 1374 ms). Boxes preserved/tightened. On-device IoU@0.25 via GGUF still open.

---

### 2026-06-27 — ROI re-anchor shrink-and-drift death spiral (negative + fix)
Full writeup: [`experiments/2026-06-27-roi-shrink-spiral/`](../../experiments/2026-06-27-roi-shrink-spiral/README.md)  
Fast re-anchor cadence on "Live tracking" tab collapsed lock: re-anchor crops 4·box natively → shrinking box → smaller crop → fewer pixels → smaller box (unbounded positive feedback). Fix: floor crop side (`roi_window` gains `min_side`; deploy `ROI_MIN_CROP=384 px`). Eval sweep unchanged (`min_side=0` default). On-Orin replay re-confirm open.

---

### 2026-06-30 — ROI super-resolution: learned SR (Swin2SR) buys no measurable accuracy for +1.3 s/crop (negative)
Full writeup: [`experiments/2026-06-30-roi-sr-upscale/`](../../experiments/2026-06-30-roi-sr-upscale/README.md)  
Does a learned upscaler beat LANCZOS/bicubic on the ROI lever? Oracle 400² crops upscaled to a 1024 feed (Qwen `max_pixels` confound defused), n=429, RTX 3090 HF bf16, spine `phase3-terse100eos-1024`.

| method | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |
|---|---|---|---|---|---|
| native | 100.0% | 78.8% | 0.651 | 0 | 306 |
| bicubic | 100.0% | **80.9%** | **0.695** | 0 | 635 |
| lanczos | 100.0% | 80.2% | 0.690 | 0 | 634 |
| swin2sr | 100.0% | 78.6% | 0.682 | **1331** | 635 |

Swin2SR buys **no measurable accuracy** for **+1331 ms per crop**. **Decision: reject SR on latency, keep deployed LANCZOS.** Mean IoU is ~0.04 higher under upscaling (bicubic 0.695 vs native 0.651) but the *method* doesn't matter; learned high-freq detail buys nothing a 2B VLM can use for localization.

*(Corrected 2026-07-21T20:20Z, R-21 — section retitled and both accuracy readings withdrawn as orderings.)* The previously published sentences — "Swin2SR is the worst upscaler (below native on IoU@0.25)" and "upscaling helps box tightness" — assert directional differences this probe cannot support. Paired McNemar over the discordant pairs, recomputed from `sr_probe_out/sr_per_sample.csv` (n=429 samples over 312 unique images): lanczos vs swin2sr **b=21, c=14, p=0.31**; bicubic vs swin2sr b=22, c=12, p=0.12; **swin2sr vs native b=28, c=27, p=1.00** — 337 vs 338 gate passes, a one-item difference; bicubic vs native b=21, c=30, **p=0.26**. **No accuracy difference in this probe is significant**, in either direction. The rejection stands and is correct, but it rests entirely on the **latency** column, which is deterministic and enormous (+1331 ms vs 0 ms for the free interpolators). The percentages in the table above are unchanged and exact.

---

### 2026-06-30 — Whole-frame resolution sweep: 1024 is the on-device knee, 1536/1920 are duplicates
Full writeup: [`experiments/2026-06-30-whole-frame-resolution/`](../../experiments/2026-06-30-whole-frame-resolution/README.md)  
Does feeding the *whole frame* at higher resolution beat the deployed 512 baseline, and at what latency? Jetson Orin Nano 15 W, Q8_0 terse spine, RefDrone well-posed val n=439, parse 100% all arms.

| max_side | IoU@0.25 | mean IoU | prefill | wall |
|---|---|---|---|---|
| 512 | 31.4% | 0.187 | 241 tok / 816 ms | 1424 ms |
| **1024** | **63.1%** | 0.477 | 837 tok / 3712 ms | 4400 ms |
| 1536 | 65.4% | 0.519 | 1383 tok / 7929 ms | 8686 ms |
| 1920 | 65.1% | 0.514 | 1383 tok / 7938 ms | 8689 ms |

512→1024 doubles IoU@0.25 (+31.7pp); 1024→1536 buys only +2.3pp for ~2× wall; 1536≈1920 is a literal duplicate (downscale-only clamp to native ~1360px for ~70% of val). Decode flat (~545 ms) — cost is all prefill. **Whole-frame 1024 @ 4.4 s is too slow for the ~2 s anchor budget; this is the baseline that justifies the ROI-crop lever.** Caveat: the run's per-sample CSV was lost when the results→experiments rename landed mid-run (aggregates intact in `run.log`).

**ROI headline re-measured on-device, paired (2026-07-21T20:21Z, R-14):** the cross-machine
composite above is now retired. Both arms ran in one Orin Q8_0 llama-server session on the
deployed `phase3-terse100eos-1024` checkpoint, same 439 RefDrone val samples, same order.

| arm | IoU@0.25 | mean IoU | prefill ms (med) | decode ms (med) | wall ms (med) | prompt tok (med) |
|---|---|---|---|---|---|---|
| A — full frame @1024 (control) | **63.10%** (277/439) | 0.477 | 3680 | 536 | 4319 | 837 |
| B — ROI M=2.0 @512 (treatment) | **85.19%** (374/439) | 0.681 | 1371 | 533 | 1939 | 385 |

Paired: b=112 (ROI right, full wrong), c=15 (full right, ROI wrong); deflated to n_effective=316
b=81, c=11; **McNemar p=2.5e-14**, survives Holm. Arm A reproduced the published 63.1% on-device
full-frame control **exactly** (RQ-R14.2), so the +22.1 pp is the intervention, not a harness
change. Prefill ratio A/B = **2.68x** (vs 2.7x at n=10 in 2026-06-26), confirmed at n=878. Both
arms landed on their *published* numbers to reported precision even though the original 85.2% was
HF bf16 on the 3090 with a different checkpoint — the ROI effect transfers across machine and
quantisation without loss. Registry: `P3-ROI-M2.0-512-ondevice`, `machine: jetson-orin-nano-8gb`,
per-item rows in `experiments/2026-07-21-roi-ondevice/raw/items-{full,roi}.jsonl`. Proof:
`experiments/2026-07-21-roi-ondevice/proof/{paired-iou,discordant-examples,prefill-vs-tokens}.png`.
Upper-bound caveat: the ROI prior is the oracle inflated GT box (same as the original sweep), so
this bounds what the deployed tracker-driven re-anchor gets from a drifted box.

**Composite-comparison correction (2026-07-21T20:20Z, R-7/R-21):** the earlier parenthetical "85.2% @ ≈2.0 s, beats even 1920 whole-frame" put three configurations side by side as if they were one measurement. **85.2%** is HF bf16 on the RTX 3090 with the *JSON-format* checkpoint (`2026-06-25-roi-crop-anchor/sweep_summary.json`), measured at 1374 ms Orin prefill + 964 ms decode ≈ **2.33 s** in that harness. The **≈2.0 s** is a different thing: the deployed *terse* Q8_0 re-anchor cadence measured on-device (`2026-06-26-roi-demo-tab/README.md`: 2021 ms, range 1694–2081, n=10), whose decode is ~535 ms because of the terse lever. The **65.1%** at 1920 is Orin Q8_0 terse (this table). So neither the accuracy nor the latency in that sentence was measured on the configuration it describes, and "beats even 1920 whole-frame" is not a like-for-like on-device comparison. What is supported: the ROI crop is ~2.7× cheaper in prefill on the Orin, and it is far more accurate than full-frame @512 on the same machine and runtime. The on-device Q8_0 ROI accuracy that would make this one comparison is open — see [`experiments/2026-07-21-roi-ondevice/`](../../experiments/2026-07-21-roi-ondevice/README.md) (R-14), which pairs a full-frame @1024 control against the M=2.0 @512 ROI arm on the Orin at Q8_0.

## 2026-07-22 — R-13 detector baseline: OWLv2 vs the deployed VLM, both on the Orin

The missing comparison behind the whole architecture. The 2026-06-14 campaign closed the
"end-to-end VLM vs decomposed detector+LLM" fork **on latency grounds alone, with no detector
ever run**. This runs it: `google/owlv2-base-patch16-ensemble` fp16 on the Orin Nano (15 W +
`jetson_clocks`), same 439 RefDrone val samples, same `contract.py` scoring path, VLM comparator
taken unchanged from R-14 arm A (no re-run). 1317 forward passes in 459.9 s.

| arm | k/n | IoU@0.25 | mean IoU | center_std | latency ms (med) |
|---|---|---|---|---|---|
| VLM Q8_0 full-frame @1024 (R-14 arm A) | 277/439 | **63.10%** | 0.477 | 21.9 | 4319 (wall) |
| D-oracle — best of top-10 chosen with GT | 397/439 | **90.43%** | 0.789 | 22.5 | — (bound, not a system) |
| D-phrase — noun phrase, adjectives kept | 208/439 | 47.38% | 0.414 | 23.7 | 263.5 (forward) |
| D-full — the whole referring expression | 113/439 | 25.74% | 0.228 | 21.9 | 263.5 (forward) |
| D-head — bare head noun | 108/439 | 24.60% | 0.219 | 22.7 | 263.5 (forward) |

Paired McNemar, VLM vs each arm, deflated to n_effective=316 unique images: vs D-full b=186 c=22
(**p=2.2e-24**), vs D-phrase b=100 c=31 (**p=2.3e-07**), vs D-head b=181 c=12 (p=1.3e-28), vs
D-oracle b=1 c=121 (p=5.8e-25, **in the detector's favour**). `center_std` is flat at 21.9-23.7
across all arms, so no rate is a mode-collapse artefact.

**The result is a decomposition, not a rate.** D-phrase recall@k = 47.4 / 63.0 / 72.4 / 81.5 /
88.8% at k = 1 / 2 / 3 / 5 / 10. OWLv2's *second* proposal already ties the VLM's top-1 (63.0% vs
63.10%), and by k=10 it holds the right box on 88.8% of items without being able to say which one
it is — a **41.5 pp selection gap**. Only 49/439 (11.2%) of items have no correct box anywhere in
its proposals. Two supporting splits: relational language actively *hurts* (D-full is 21.6 pp
below D-phrase — the clause is scored, not ignored, and drags the match off target), and
appearance adjectives carry the whole detector contribution (D-phrase − D-head = 22.8 pp).

**Cost, which reverses the original rationale.** OWLv2 forward 263.5 ms median (p90 264.1 — flat
and input-independent) at 415.3 MB peak CUDA, against the VLM's 4319 ms wall: **16.4x cheaper per
call, ~5x smaller**. The 2026-06-14 latency argument was backwards. What rules the decomposed path
out is the selection gap, a quality argument. Caveat: that 16.4x compares one detector forward to
one full generative anchor, and a decomposed system still needs the selection stage nobody has
costed — if that stage is itself a VLM the saving evaporates.

**Architectural ceiling found on the way:** OWLv2's text encoder has `max_position_embeddings=16`
and a 17-token query *crashes* the forward pass rather than degrading (this killed the first full
run). RefDrone captions are 7-27 tokens (median 10), so 5/439 (1.1%) exceed what the model can
represent at all. A hard 16-token budget for a task whose inputs are sentences is a finding about
fitness, not a nuisance.

Registry: `P3-R13-owlv2-vs-vlm`, `machine: jetson-orin-nano-8gb`. Proof:
`experiments/2026-07-21-detector-baseline/proof/{arms-bar,oracle-gap,qualitative-grid}.png`.
Full record incl. the pixel-vs-0-100 contamination bug and the verb-leak in head extraction:
[`experiments/2026-07-21-detector-baseline/`](../../experiments/2026-07-21-detector-baseline/README.md).

