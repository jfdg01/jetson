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

**Key verdicts:** anchor_period (2.27 s @512) > coast_horizon (1.5 s) → re-acq must be event-triggered on loss. Tracker holds lock between anchors with ~1000× headroom. **Spine confirmed: Q8_0 @512** (768/1024 add latency with no fidelity gain on 640×480 camera + downscale).

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

---

### T3 — Closed-loop integration in SITL (2026-06-24) ✅
Full writeup: [`experiments/2026-06-24-t3-closed-loop/`](../../experiments/2026-06-24-t3-closed-loop/README.md)  
Lock drives the camera (cascade-PID → body velocity → copter → re-projection). 20 Hz control / 1 Hz detect, 10 m alt. Distractor crosses + briefly occludes at t=29–31 s.

| Policy | Kinematic A/B coverage | Live ArduCopter SITL coverage | Occlusion frames |
|---|---|---|---|
| memoryless baseline | 49.2% | 53.7% | 40 |
| **re-ID (snr 8)** | **97.6%** | **71.5%** | 40 |

**✅ Gate PASS:** Phase-C ≈0% → 97.6% kinematic / 71.5% live SITL. Live margin smaller due to PID-lag + inertia lowering both policies' absolute coverage; direction + mechanism hold.

---

### T4 — On-Orin deployment + sim-to-device (2026-06-24) ✅
Full writeup: [`experiments/2026-06-24-t4-deployment/`](../../experiments/2026-06-24-t4-deployment/README.md)  
Integrated two-tier loop on actual Orin Nano 8 GB (15 W). One file (`bytetrack.py`) pushed to device.

| Tier | Dev box / T0a | Orin (T4) | Sim-to-device |
|---|---|---|---|
| fast: `ByteTracker.update` median (p99) | 0.051 ms (0.103) | **0.143 ms (0.291)** | 2.8× slower, **99.7% of 50 ms budget free** |
| slow: VLM anchor @512 wall | 2265 ms (0.44 Hz) | **2264 ms (0.44 Hz), 100% parse** | **−0.03%** |

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
| decode tokens | ~24 | 21 | **12** (−43%) |
| decode ms | 967 | — | **531** (−45%) |
| anchor wall @512 | 1807 ms | 2114 ms | **1372 ms** (−24%) |

**Iter-2b win** (bare ints 0–100 + EOS-supervision fix): halve the digits + supervise `<|im_end|>` on the target (iter-2 without fix collapsed to 5% parse — outputs never learned to stop). Clean bare `28 44 36 59`, 100% parse. **Strict upgrade: better accuracy AND ~half decode.** Replaces the deploy artifact.

---

### 2026-06-26 — ROI-crop anchor (GATE PASS)
Full writeup: [`experiments/2026-06-25-roi-crop-anchor/`](../../experiments/2026-06-25-roi-crop-anchor/README.md)  
Inference-time only — no retraining. Feed anchor a crop around tracker's box (GT box × margin M) instead of full frame.

| Config (M=2.0) | Prefill ms (Orin Q8_0, 15W) | Decode ms | IoU@0.25 (HF n=439) | vs full-frame |
|---|---|---|---|---|
| full-frame @1024 (baseline) | 3691 | 966 | 62.6% | — |
| **ROI crop @512 ← deploy** | **1374** | 964 | **85.2%** | **2.7× prefill · +22.6 pp** |
| ROI crop @384 (max-speed) | 885 | 964 | 82.5% | 4.2× prefill · +19.9 pp |
| full-frame @512 (downscaled) | — | — | 15.9% | resolution ceiling laid bare |

Drift (RQ4): flat 82–85% up to 0.5·box prior drift; 74–80% even at full-box drift — all above baseline. Tight upscaled crop is *both* faster *and* more accurate (super-resolution beats resolution constraint #2). Decode unchanged — orthogonal to terse decode lever; two stack toward sub-1s anchor.

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

### 2026-06-30 — ROI super-resolution: learned SR (Swin2SR) loses to classical upscale (negative)
Full writeup: [`experiments/2026-06-30-roi-sr-upscale/`](../../experiments/2026-06-30-roi-sr-upscale/README.md)  
Does a learned upscaler beat LANCZOS/bicubic on the ROI lever? Oracle 400² crops upscaled to a 1024 feed (Qwen `max_pixels` confound defused), n=429, RTX 3090 HF bf16, spine `phase3-terse100eos-1024`.

| method | parse% | IoU@0.25 | mean IoU | med SR ms | med VLM ms |
|---|---|---|---|---|---|
| native | 100.0% | 78.8% | 0.651 | 0 | 306 |
| bicubic | 100.0% | **80.9%** | **0.695** | 0 | 635 |
| lanczos | 100.0% | 80.2% | 0.690 | 0 | 634 |
| swin2sr | 100.0% | 78.6% | 0.682 | **1331** | 635 |

Swin2SR is the worst upscaler (below native on IoU@0.25) and adds ~1.3 s/crop. **Decision: reject SR, keep deployed LANCZOS.** Upscaling helps box tightness (mean IoU +0.04) but the *method* doesn't matter; learned high-freq detail buys nothing a 2B VLM can use for localization.

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

512→1024 doubles IoU@0.25 (+31.7pp); 1024→1536 buys only +2.3pp for ~2× wall; 1536≈1920 is a literal duplicate (downscale-only clamp to native ~1360px for ~70% of val). Decode flat (~545 ms) — cost is all prefill. **Whole-frame 1024 @ 4.4 s is too slow for the ~2 s anchor budget; this is the baseline that justifies the ROI-crop lever (85.2% @ ≈2.0 s, beats even 1920 whole-frame).** Caveat: the run's per-sample CSV was lost when the results→experiments rename landed mid-run (aggregates intact in `run.log`).
