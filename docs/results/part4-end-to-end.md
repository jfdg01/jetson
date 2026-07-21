# RESULTS — Part IV · End-to-end workflow refinement (v4)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part IV — End-to-end workflow refinement (v4)

Goal: the two-tier follow loop passed T0–T4 in isolation, but the integrated NL→ground→track→fly pipeline does not hold up end-to-end. Part IV hardens it.

### 2026-06-30 — VLM backbone bake-off ([`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md))

FT: LoRA r=16/α=32 bf16, vision frozen, eff. batch 16, lr swept {1e-4, 2e-4, 4e-4}, ≤3 epochs,
RefDrone well-posed (4101/439), RTX 3090. Deploy rows: Jetson Orin Nano 8 GB @ 15 W, llama.cpp
`57fe1f0` Q8_0 ngl=99. **Campaign early-stopped 2026-07-02** — decision determined before arms D /
E-legs-2-3 (see README Findings).

| Arm | best lr | path | parse | IoU@0.25 | mean IoU | wall/anchor | verdict |
|---|---|---|---|---|---|---|---|
| baseline Qwen2-VL-2B (bake-off harness) | — | WF@1024 / ROI M=2.0@512 | 100% | 63.1% / 85.2% | 0.477 / — | 4400 / ≈2000 ms | **incumbent, kept** |
| A InternVL3-2B | 4e-4 | WF@1024 (HF, n=200) | 100% | 48.5% | 0.298 | N/A — GGUF export blocked @`57fe1f0` | eliminated |
| B Qwen2.5-VL-3B | 2e-4 | WF@1024 / ROI M=2.0@512 (Jetson Q8_0, n=439) | 100% | 53.1% / **33.0% (ROI collapse)** | 0.399 / 0.170 | 5990 / 2817 ms | eliminated |
| C PaliGemma2-3B@448 | 2e-4 | WF@448 (HF, n=200) | 100% | 56.0% | 0.391 | not measured (moot) | eliminated |
| E SmolVLM2-500M | 1e-4 (leg 1 only) | WF@512 (in-loop val) | 100% | **5.5% (capacity collapse)** | 0.038 | not deployed | eliminated |
| D Florence-2-large | — | — | — | cancelled un-run | — | — | cancelled |

Baseline-row label corrected 2026-07-21T18:05Z (R-21): the row was published as
"(deployed)" carrying **63.1%**, which is the `2026-06-30-whole-frame-resolution`
re-measurement (n=439, the same Jetson harness arm B was benched on) — *not* the
deployed configuration. The deployed Phase-4 Q8_0 figure is **62.6%** (registry
`P2-RQ4.1-deploy-fidelity`). Both are the same model/config measured in two campaigns,
0.5 pp apart; 63.1% is kept here because every arm delta in this table is against the
harness, and the campaign README ("Two incumbent numbers, used deliberately") is the
source of the convention.

### 2026-07-02 — Temporal acquire-carry, Phase 0 zero-shot ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Zero-shot SAM2.1-hiera-tiny (`sam2==1.1.0`, bf16 autocast, RTX 3090) memory-carry from a single
first-frame GT box prompt; AerialMind 93 seqs × 2 tracks (longest + longest-with-gap), ≤300-frame
window, scored on labeled frames only. First launch invalidated at 42/93 by a GT decode bug
(labels are top-left-encoded, not JDE center — see campaign README Findings); rerun clean.

| Run | tracks | mean IoU | IoU@0.25 | IoU@0.5 | ID-consistency | occ-recovery | pred-absent | FPS (3090) | wall |
|---|---|---|---|---|---|---|---|---|---|
| phase0-zeroshot-carry | 186 | 0.602 | **0.849** | 0.750 | **0.891** | 0.329 (70 gaps) | 3.5% | 14.4 | 58.4 min |

Demo (real Jetson Q8_0 acquire, M0205): occlusion clip — acquire IoU 0.947 @4.58 s, carry 252 f
through a 40-frame GT gap, mean IoU 0.886; retarget clip — mid-video caption switch truck→"the
black car", retarget IoU 0.721 @4.1 s, mean IoU 0.887. Committed `ab6d6d7`.
(Acquire wall corrected 4.54 → **4.58 s** on 2026-07-21T18:05Z, R-21: 4.54 s is the *retarget*
run's acquire wall, `runs/20260701T230746Z`; the occlusion clip's own run `runs/20260701T230357Z`
— the one the 252 frames and the 0.886 mean come from — logs `ACQUIRE wall_s 4.58`.)

### 2026-07-02 — Temporal acquire-carry, Phase 1 SITL latency-injection ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Oracle-box follow loop (perception perfect) with the temporal design's measured costs injected:
acquire/reground latency U(4.1, 4.6) s, parse-fail p=0.007, 5 s synthetic occlusion @ t=30 s,
LossGate 60 no-box frames (3 s @ 20 Hz). ArduCopter SITL, 10 m AGL, gimbal-level camera, rover
programmatic north; 75 s/trial. `phase1_sitl.py`, raw CSVs in campaign `raw/phase1-sitl/`.

| Rover speed | in-FOV frac | first lock | regrounds | occlusion relock wall | carry px-err | verdict |
|---|---|---|---|---|---|---|
| 0.25 m/s (gate) | **1.000** | 4.31 s | 1 | **4.46 s** | 16.1 px | **PASS** |
| 0.5 m/s | **1.000** | 4.26 s | 1 | 4.21 s | 32.0 px | PASS |
| 1.0 m/s | 0.482 | 4.36 s | 1 (8 failed re-acquires) | never | 66.2 px | FAIL — speed ceiling |

### 2026-07-02 — Temporal acquire-carry, Phase 2 Jetson FPS knee ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

SAM2.1-hiera-tiny on the Orin Nano 8 GB @ **15 W + jetson_clocks** (`torch==2.8.0`,
`~/sam2-bench/.venv`, M0205 100-frame bench); accuracy = full 186-track AerialMind eval on the
3090, same protocol as Phase 0. Accuracy bar = 0.799 (1024's 0.849 − 5 pp); FPS gate ≥ 5.

| image_size | Jetson FPS solo | co-resident (VLM Q8_0) | IoU@0.25 | mean IoU | verdict |
|---|---|---|---|---|---|
| 1024 | 2.68 | 2.68 (RAM 6963/7607 MB) | **0.849** | 0.602 | accuracy reference; FPS FAIL |
| **768 (OP)** | 4.89 | 4.89 | **0.830** | 0.585 | acc PASS; FPS marginal FAIL (−2.2%) |
| 640 | 7.25 | 7.24 (RAM 6144/7607 MB) | 0.787 | 0.551 | FPS PASS; acc FAIL by 1.2 pp |
| 512 | 12.13 | — | 0.737 | 0.506 | FPS PASS; acc FAIL (−11.2 pp) |

Operating point **768** by the pre-frozen rule; co-residency costs zero FPS at every size
measured (RQ-T.3). TensorRT export (`experiments/2026-07-02-carry-trt-export/`) is the named
fix for the 2.2% rate shortfall.

### 2026-07-02 — Temporal acquire-carry, Phase 3 integrated end-to-end ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Streaming carry parity (3.0): stream-vs-batch mean box-IoU 0.9974 @1024 / 0.9968 @512 (gate
≥0.99) — **unbacked, flagged 2026-07-21T18:05Z (R-21):** no parity log, `results.json` or CSV was
committed for this leg. The two figures exist only as prose, here and in the campaign README's
2026-07-02T10:30Z entry (which adds min IoU 0.9485 @1024 / 0.9353 @512 and stream FPS 18.2/38.8 on
the 3090). The generating script *is* committed — `experiments/2026-07-01-temporal-acquire-carry/stream_carry.py`
on the M0205 100-frame window — so this is a cheap deterministic re-run, not a lost measurement;
until it is re-run and its output landed under `raw/`, treat the parity gate as asserted rather than
evidenced. Integrated trials: ArduCopter SITL + synthetic nadir renderer, real Jetson Q8_0 VLM
acquire, 5 s bridge occlusion @ t≈30 s, rover 0.25 m/s north, 75 s.

| Run | carry | in-FOV | first lock | acq (rej) | relock wall | px-err | carry rate | verdict |
|---|---|---|---|---|---|---|---|---|
| 3a run 1 | 3090 @1024 | 0.544 | 2.7 s | 2 (0) | 2.36 s | 8.6 | 12.0 FPS | FAIL — VLM locked a road dash during occlusion (unvalidated reground) + ingress lag |
| 3a run 2 (+size-prior validation, dead-reckoning, 3 s loss gate) | 3090 @1024 | **1.000** | 2.65 s | 7 (**5**) | 13.9 s | 16.2 | 13.6 FPS | **PASS** |
| 3b | **Jetson @768, VLM co-resident** | **1.000** | 3.02 s | 7 (5) | 14.35 s | 22.5 | **4.1 FPS** | behavioral legs **PASS**; rate leg **4.1 < 5 FPS marginal FAIL** (pre-registered expected outcome at OP=768) |

3b rate: whole-trial 7.6 Hz is inflated by blind phases; carry-phase 4.1 FPS = Jetson 204.6 ms/step
+ ~40 ms JPEG/tunnel (est. 4.5–4.8 — wire overhead underestimated). Dead-reckoning held the
copter-target gap at ~2.2 m across the 13.9 s blind window (3a-2 CSV forensics).

### 2026-07-02 — E1 Carry TensorRT encoder export ([`experiments/2026-07-02-carry-trt-export/`](../../experiments/2026-07-02-carry-trt-export/README.md))

SAM2.1-tiny image encoder → ONNX (opset 17, fixed 1×3×768×768) → TensorRT fp16 engine
(`trtexec --fp16`, median GPU compute 65.1 ms). Memory attention + the two high-res 1×1 convs
stay PyTorch; encoder swapped via one `forward_image` monkeypatch (`--trt-encoder`). Bench =
M0205 100-frame window, box 496,69,577,110, Jetson 15 W + jetson_clocks.

| Run | size | FPS solo | FPS co-res (VLM Q8_0) | p50 ms | CUDA peak | sys RAM (w/ VLM) | IoU@0.25 / mean (M0205) | verdict |
|---|---|---|---|---|---|---|---|---|
| eager baseline | 768 | 4.89 | 4.89 | 204.6 | 612 MB | not logged | 1.000 / 0.821 | reference |
| TRT fp16 encoder | 768 | 6.15 | **6.15** | 162.4 | **533 MB** | 4980/7607 MB | **1.000 / 0.826** | **PASS (≥5)** |

Memory column split 2026-07-21T18:05Z (R-21): the two rows previously shared one "RAM"
column holding two different quantities — the eager row's 612 MB is `cuda_peak_mb`, the TRT
row's 4980/7607 MB is whole-system RAM with the VLM co-resident. Read side by side that
implied TRT costs ~8x the memory; `runs/bench.json` says the opposite, `trt_768_cores.cuda_peak_mb`
= **533 MB**, i.e. 79 MB *below* eager. No FPS/latency/accuracy cell changed.

Host parity (fp32 ONNX vs eager): max-abs-diff 3.1e-04 (<1e-2), end-to-end mask IoU 1.000. On-device
fp16 vs eager: IoU@0.25 Δ 0.00 pp, mean IoU +0.006 (fp16 does not degrade — marginally higher). Per-frame
saving ~42 ms not the estimated ~75 ms (retained memory-attention + TRT stream sync); co-residency
cost 0 FPS (confirms parent RQ-T.3). EdgeTAM fallback not needed. Raw:
`experiments/2026-07-02-carry-trt-export/{raw,runs}/`.

### 2026-07-02 — Phase 3b re-run with E1 TRT encoder ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Same 3b SITL harness (`phase3_sitl.py --remote-carry --image-size 768`, gate = `carry_fps`), now
booting the carry service with `--trt-encoder enc768.plan` so the E1 fp16 encoder patches
`forward_image` for every streamed frame. VLM Q8_0 co-resident. 15 W + jetson_clocks, 0.25 m/s.

| Run | carry | in-FOV | first lock | acq (rej) | relock wall | px-err | carry rate | verdict |
|---|---|---|---|---|---|---|---|---|
| 3b eager (above) | Jetson @768 | 1.000 | 3.02 s | 7 (5) | 14.35 s | 22.5 | 4.1 FPS | rate leg marginal FAIL |
| 3b + E1 TRT | **Jetson @768 + TRT enc** | **1.000** | 5.43 s | 8 (6) | 14.17 s | 23.0 | **5.0 FPS** | behavioral legs **PASS**; rate leg **5.0 ≥ 5 PASS** → **gate PASS** |

Eager→TRT lifts carry-phase rate 4.1→5.0 FPS, clearing the ≥5 gate exactly. Margin is thin: the
solo E1 bench measured 6.15 FPS, but the integrated loop pays ~1.15 FPS in per-frame JPEG
encode/decode + ssh-tunnel wire transfer that the solo bench doesn't. Behavioral legs unchanged
(in-FOV 1.000, recovered after occlusion, relock 14.17 s). Closes the parent campaign's only
marginal-FAIL leg. Raw: `experiments/2026-07-01-temporal-acquire-carry/runs/phase3b-sitl/`.

### 2026-07-02 — E2 speed ceiling with levers on ([`experiments/2026-07-02-follow-speed-ceiling/`](../../experiments/2026-07-02-follow-speed-ceiling/README.md))

Integrated SITL follow, levers ON (size-prior validation, dead-reckoning, time-based LossGate),
real carry (local 3090 SAM2 @1024, Jetson Q8_0 acquire over ssh), one trial per speed. Gate = in-FOV ≥
0.90 AND recovered_after_occlusion. Levers-OFF Phase-1 baseline (oracle box) put the ceiling at
1.0 m/s.

| speed (m/s) | in-FOV | first lock | acq (rej) | regrounds | verdict | binding failure mode |
|---|---|---|---|---|---|---|
| 0.5 | 0.484 | 5.0 s | 2 (1) | 0 | **FAIL** | confident-latch: SAM2 tracks the occluder, returns non-`None`, None-gated levers never fire, copter parks |
| 1.0 | 0.076 | never | 32 (31) | 0 | **FAIL** | acquire latency: copter frozen at home, car exits FOV at t≈6 s before the ~5 s acquire+stale-box init can lock |
| 1.5 | 0.051 | never | 32 (31) | 0 | **FAIL** | same as 1.0 |

**Ceiling: 1.0 (levers off, oracle) → < 0.5 (levers on, real carry).** The levers do not lift the
ceiling and cannot, because at each speed the binding constraint is not the REGROUND blind window
they target: 0.5 fails to a *confident* carry-loss (the levers only detect `box is None`), 1.0/1.5
fail at *first acquire* (latency vs target speed). 0.5 reproduced trial-1 (in-FOV 0.486 → 0.484,
deterministic). Both modes are fixable (confidence/staleness loss test; velocity-extrapolated
acquire box) — deferred, named in the campaign README. Raw:
`experiments/2026-07-02-follow-speed-ceiling/runs/speed-{0.5,1.0,1.5}/`.

### 2026-07-02 — E3 twin-distractor identity test ([`experiments/2026-07-02-twin-distractor/`](../../experiments/2026-07-02-twin-distractor/README.md))

Integrated SITL follow at 0.25 m/s, levers ON, real carry (local 3090 SAM2 @1024), with an
*identical* second white car. Two SITL scenarios + an AerialMind analysis leg. All 4 trials pass
the base gate (in-FOV 1.000, recovered); the twin verdict is a separate per-frame box-center
distance-to-true vs distance-to-distractor check.

| scenario | runs | metric | verdict |
|---|---|---|---|
| S1 crossing (distractor passes at 3 m, in-frame) | 1 | ID-switch **0.0 s**, 0.0% frames closer-to-distractor; ends 0.27 m to true vs 25.94 m to distractor | **PASS** — CARRY holds |
| S2 decoy (parked in-lane past bridge, seen during occlusion) | 3 | REGROUND wrong-locks the decoy **3/3** (`n_regrounds=1` each → measurable, not confident-latch); then static-latch park, true car escapes | **FAIL (expected)** |

S2 detail: every REGROUND's first re-lock landed on the decoy (t≈47 s) — the size-prior lever is
identity-blind and cannot reject an identical twin. Because the decoy parks in the true car's
lane, the emerging true car drives through the decoy's position at t≈50 s and the box transiently
transfers to the true car (t≈51-68 s), but the copter has already **static-latched** at N≈15.7 m
(the E2 latch mode reappearing post-reground) and never resumes the follow; the true car escapes
to N≈19.1 m (final d_true 3.5-3.9 m vs d_dist 2.1-2.4 m). The honest negative that motivates an
appearance-embedding gate on reground acceptance.

**AerialMind leg** (`distractor_density.py`, 186 Phase 0 tracks, top-quartile density split ≥6.96):
distractor-heavy quartile (n=47, density 11.27) IoU@0.25 **0.858** / ID-consistency **0.896** vs
rest (n=139, density 2.98) **0.846** / **0.890** — heavy is marginally *better* (+0.011 / +0.006),
NOT the estimated 2-8 pp worse. Scene density alone does not hurt zero-shot carry; the S2 failure
needs occlusion + a same-appearance in-lane decoy during REGROUND. Raw:
`experiments/2026-07-02-twin-distractor/runs/{s1-crossing,s2-decoy-run{1,2,3}}/`.

### 2026-07-02 — E4 follow hardening: two E2 binding-mode fixes ([`experiments/2026-07-02-follow-hardening/`](../../experiments/2026-07-02-follow-hardening/README.md))

Same rig as E2 (Jetson Q8_0 acquire, 3090 carry @1024, gate = in-FOV ≥ 0.90 AND recovered). Two fixes
vs E2: **Fix B** (always-on) inits carry on the acquire *submit* frame + replays the buffered gap;
**Fix A** a trust-aware loss gate demoting an untrusted carry box to `None` so the existing
REGROUND machinery fires (flag `--loss-gate {none,score,motion}`).

**Stage 1 — gate selection @ 0.5 m/s (the E2 confident-latch speed):**

**Superseded 2026-07-21 (R-7): stage 1 was executed twice and only the first run was published.**
`runs/stage2.log` re-ran all three stage-1 legs before the ladder and overwrote every
`runs/s1-*/results.json`, so the committed artifacts are run B while the table below was written
from run A (`runs/stage1.log`). Both are kept:

| gate | relock (s) | attempts | recovered | verdict (run A, published) | verdict (run B, committed) |
|---|---|---|---|---|---|
| none | 9.43 → [] | 6 → 20 | true → false | **PASS** | **FAIL** |
| score | [] → 21.04 | 20 → 11 | false → true | **FAIL** | **PASS** |
| motion | 9.32 → 9.32 | 6 → 6 | true → true | **PASS** | **PASS** |

In-FOV is 1.000 and `n_regrounds` is 1 in every leg of both runs. **Two of the three legs invert
under replication of an identical configuration**, which makes the run-to-run variance of a single
0.5 m/s SITL trial larger than the effect the stage was built to measure. The mechanical selection
rule as written ("pick the gate that recovers") does not resolve on the committed run — `score`
satisfies it and `none` does not. What survives is the leg that replicated: **`motion` recovers in
both runs**, so the gate chosen is still `motion`, but it is chosen because it is the only stable
leg, not because the rule discriminated. The stronger original reading — "Fix B alone recovered
0.5, the loss gate was not the operative fix" — **does not survive**: `none` fails on the
committed run. n=1 per cell; this whole stage needs replication before any of it is quoted.

`score` diagnostic, recomputed from the committed `runs/s1-score/trial.csv` (the published
−3.23 / +8.61 / −3.94 at n=53/472 came from the overwritten run A): SAM2 `object_score_logits`
separates occlusion cleanly (occluded mean **−3.18**, n=54, range −3.44..−2.83 vs clear mean
**+8.84**, n=888) but the clear tail dips to **−4.25**, so at tau=0 it demotes good boxes on
clean-track noise. Signal real, threshold over-fires — that conclusion is unchanged by the re-run.

**Stage 2 — speed ladder, motion gate:**

| speed (m/s) | in-FOV | first lock | n_regrounds | recovered | verdict | E2 was |
|---|---|---|---|---|---|---|
| 0.5 | 1.000 | 4.96 s | 1 | true | **PASS** | FAIL 0.484 |
| 1.0 | 0.073 | 5.01 s | 4 | true | **FAIL** | FAIL 0.076 |
| 1.5 | 0.051 | never | 0 | false | **FAIL** | FAIL 0.051 |

**Ceiling: `< 0.5` (E2) → 0.5 (E4).** Fix B lifts 0.5 from FAIL to PASS by landing the initial lock
on the true car instead of the stale box. 1.0/1.5 stay pinned to the E2 floor: 1.0 locks (5.01 s)
and regrounds 4× but in-FOV 0.073 — the car escapes during the ~5 s **first-acquire hover** before
any lock exists to seed the replay/DR; 1.5 never locks. First-acquire hover is the remaining
ceiling, deliberately out of E4 scope. Replay-stall watch item bounded (max loop_ms ~0.6 s). Raw:
`experiments/2026-07-02-follow-hardening/runs/{s1-none,s1-score,s1-motion,ladder-1.0,ladder-1.5}/`.

### 2026-07-03 — E5 pursuit-chase ([`experiments/2026-07-02-pursuit-chase/`](../../experiments/2026-07-02-pursuit-chase/README.md))

Config: `jetson-acquire, 3090 carry @1024, loss-gate motion, dr pursuit, 75 s` (the config string as logged reads `local-VLM`, which meant local *carry*; see R-17). Pursuit DR replaces
velocity-matching with position-seeking (`v_est + 0.5·(dead-reckoned pos − copter pos)`, 2.5 m/s
cap) on the blind branch. Baselines are the E4 Stage-2 `--dr velocity` rows above (not re-run).

| run | speed | in-FOV | first lock | n_regrounds | relock (s) | recovered | verdict | E4 (velocity) was |
|---|---|---|---|---|---|---|---|---|
| p-0.5 | 0.5 | 1.000 | 5.06 s | 1 | 9.32 | true | **PASS** | PASS 1.000 |
| p-1.0 | 1.0 | 0.076 | never | 0 | — | false | **FAIL** | FAIL 0.073 |
| p-1.5 | 1.5 | 0.051 | never | 0 | — | false | **FAIL** | FAIL 0.051 |
| p-1.5b | 1.5 | 0.927 | 4.66 s | 2 | 6.89, 6.92 | true | **PASS** | — |

**RQ-E5 = NO. Ceiling unchanged at 0.5 m/s.** p-0.5 held 1.000 (pursuit near-inert at small
deficit — not a regression). The high-speed failures were **acquire failures, not pursuit
failures**: p-1.0 and p-1.5 both `first_lock = None` (32 attempts, 31 rejected, zero locks), so
`hist` never seeded and pursuit never engaged (empty history → ACQUIRE hover). p-1.0 could not test
pursuit at all this run because 1.0 happened to never lock (E4's 1.0 *did* lock @5.01 s) — the
stochastic first-acquire rejection now biting at both high speeds. **p-1.5b is the one clean pursuit
test and it PASSes**: identical config to p-1.5 but its t=0 submit-frame attempt was accepted (lock
@4.66 s), and pursuit then held 0.927 in-FOV through 2 regrounds/relocks — overturning E4's "1.5
never acquires". So **1.5 = SPLIT (stochastic)**; pursuit holds 1.5 m/s once seeded, but the binding
constraint is the acquire lottery, which pursuit cannot touch. p-1.0 diag: car in-FOV t=0–5.66 s,
exits t=5.71 s at gap 6.14 m, never re-enters (gap → 75.4 m). Raw:
`experiments/2026-07-02-pursuit-chase/runs/{p-0.5,p-1.0,p-1.5,p-1.5b}/`.

### 2026-07-03 — E6 first-acquire ([`experiments/2026-07-03-first-acquire/`](../../experiments/2026-07-03-first-acquire/README.md))

Config: `jetson-acquire, 3090 carry @1024, loss-gate motion, dr pursuit, acquire-hold motion, 75 s` (logged as `local-VLM`; see R-17).
New lever: **motion-hold acquire** (`--acquire-hold motion`) — before the first lock, servo the PID
on the largest ego-motion-compensated frame-diff blob, keeping the car in FOV across repeated VLM
draws until one accepts. acquire_log (per-attempt raw box + accept flag) now captured (E5's blind
spot).

| run | speed | in-FOV | first lock | attempts | rejected | accept_frac | relock (s) | recovered | gate |
|---|---|---|---|---|---|---|---|---|---|
| mh-0.5  | 0.5 | 1.000 | 4.71 s  | 6  | 4  | 0.33 | 9.32  | true | **PASS** |
| mh-1.0a | 1.0 | 1.000 | 4.66 s  | 5  | 3  | 0.40 | 7.09  | true | **PASS** |
| mh-1.0b | 1.0 | 1.000 | 4.66 s  | 5  | 3  | 0.40 | 6.86  | true | **PASS** |
| mh-1.0c | 1.0 | 1.000 | 4.66 s  | 5  | 3  | 0.40 | 6.91  | true | **PASS** |
| mh-1.5a | 1.5 | 1.000 | 16.57 s | 10 | 8  | 0.20 | 7.05  | true | **PASS** |
| mh-1.5b | 1.5 | 1.000 | 16.57 s | 19 | 17 | 0.11 | 28.44 | true | **PASS** |
| mh-1.5c | 1.5 | 1.000 | 4.66 s  | 12 | 10 | 0.17 | 23.59 | true | **PASS** |

**RQ-E6 = YES. Follow ceiling lifts from 0.5 to at least 1.0 m/s (1.5 also passes 3/3).** 0.5 PASS
(regression check clean); 1.0 PASS 3/3; 1.5 PASS 3/3. The motion-hold converts E5's "acquire
lottery" into unlimited draws on a car-in-FOV frame: at 1.5 m/s the VLM rejected 8-17 draws before
the first accept, yet **in_fov_frac = 1.000 in every run** — the hold servo held the car in frame
across all those car-in-FOV rejected draws until a repeatable accept landed. Without the hold (E5
p-1.0) the car exited the FOV after ≤2 draws and the trial died (in-FOV 0.076, never locked). All
three 1.0 runs locked identically @4.66 s (draw 2; deterministic greedy → identical first lock
across seeds). Residual cost at 1.5 is slower *relock* after the single occlusion (23-28 s vs ~7 s at
1.0) and higher carry px_err (76-82 vs 50 at 1.0), not first-acquire. Raw:
`experiments/2026-07-03-first-acquire/runs/{mh-0.5,mh-1.0{a,b,c},mh-1.5{a,b,c}}/`.

### 2026-07-03 — E7 reground-gate: motion-consistency gate on REGROUND ([`experiments/2026-07-03-reground-gate/`](../../experiments/2026-07-03-reground-gate/README.md))

Deployed levers on all legs (`--loss-gate motion --dr pursuit --acquire-hold motion`);
treatment adds `--reground-gate motion` (accept a size-passing REGROUND box only if its
center lands on the ego-compensated mover blob + 60 px pad). Trials 75 s.

| label | speed | gate | relock_on[0] | final_d_true (m) | final_d_dist (m) | in-FOV | recovered | relock (s) | n_gate_rejects | leg |
|---|---|---|---|---|---|---|---|---|---|---|
| ctl-decoy  | 0.25 | none   | distractor | 7.91 | 1.93 | 0.903 | true | 23.38, 2.32 | 0 | CONTROL (wrong-lock reproduced) |
| mg-decoy-a | 0.25 | motion | distractor | 4.32 | 1.68 | 1.000 | true | 36.91 | 8 | **FAIL** |
| mg-decoy-b | 0.25 | motion | distractor | 4.05 | 1.94 | 1.000 | true | 37.10 | 7 | **FAIL** |
| mg-decoy-c | 0.25 | motion | distractor | 4.07 | 1.93 | 1.000 | true | 37.12 | 6 | **FAIL** |
| mg-reg-0.5 | 0.5  | motion | — | — | — | 1.000 | true | 9.32 | 0 | **PASS** |
| mg-reg-1.0 | 1.0  | motion | — | — | — | 1.000 | true | 6.92 | 0 | **PASS** |
| mg-reg-1.5 | 1.5  | motion | — | — | — | 1.000 | true | 6.78 | 0 | **PASS** |

**RQ-E7 = NO.** The gate does not convert the E3-S2 decoy wrong-lock into a true relock:
mg-decoy a/b/c all FAIL (`relock_on[0] == "distractor"`, `final_d_true` 4.05-4.32 m > 2.0
on all three). Control reproduced E3-S2 (`closest_at_end == "distractor"`) → attribution
clean. mg-decoy results are **not** byte-identical (rejects 8/7/6; distinct md5s) — real
n=3 via wall-clock VLM submit timing. The gate *fired hard* (6-8 REGROUND rejects vs 0 in
control, reason `motion` in `acquire_log`) and delayed re-acquisition, but the relock still
landed on the decoy: the true car drives past the parked decoy, transiently co-locating it
with the mover blob, so a decoy box eventually passes the gate. **Motion consistency is
necessary but not sufficient** against a same-lane parked distractor on the target's path —
a static-but-co-located cousin of the "moving same-appearance distractor" limit named up
front. Regression legs all PASS (`in_fov_frac == 1.0`, `recovered == true`) — no
plain-occlusion regression. Raw: `experiments/2026-07-03-reground-gate/runs/`.

### 2026-07-03 — E8 reground-selfcorrect: does the E4+E7 machinery self-correct given time? ([`experiments/2026-07-03-reground-selfcorrect/`](../../experiments/2026-07-03-reground-selfcorrect/README.md))

Same levers as E7 (`--loss-gate motion --dr pursuit --acquire-hold motion`); gated legs add
`--reground-gate motion`. Only knob changed vs E7: `--duration-s 150` (2x E7's 75 s) to give
the already-deployed E4 stillness loss-gate room to complete a full detect+wait+reacquire
cycle after the E7 wrong-lock. n=3 gated (mg-decoy-*-long) + 1 descriptive control.

| label | speed | gate | n_regrounds | relock_on (all) | final_d_true (m) | final_d_dist (m) | closest_at_end | in-FOV | leg |
|---|---|---|---|---|---|---|---|---|---|
| ctl-decoy-long  | 0.25 | none   | 5 | distractor x4 | 26.67 | 1.96 | distractor | 0.438 | descriptive |
| mg-decoy-a-long | 0.25 | motion | 2 | distractor    | 26.51 | 1.93 | distractor | 0.495 | **FAIL** |
| mg-decoy-b-long | 0.25 | motion | 2 | distractor    | 26.61 | 1.93 | distractor | 0.481 | **FAIL** |
| mg-decoy-c-long | 0.25 | motion | 2 | distractor    | 26.51 | 1.93 | distractor | 0.493 | **FAIL** |

**RQ-E8 = NO.** A 150 s trial (2x E7) does not let the deployed E4+E7 machinery self-correct
off the E7 decoy wrong-lock: all three gated legs fail every PASS gate (last `relock_on ==
"distractor"`, `closest_at_end == "distractor"`, `final_d_true` ~26.5 m > 2.0, in-FOV ~0.49
< 0.90). Not byte-identical (distinct md5s; `relock_walls_s` 37.13/34.98/37.0). Crucially
this is **not** a dead-mechanism failure: the E4 stillness loss-gate fired (`n_regrounds` 2
gated, 5 control) and the E7 reground-gate actively rejected the still decoy (`n_reground_
gate_rejects` 29/32/29 vs 0 control). The binding constraint is **upstream of both gates** —
by the time the loss-gate demotes the wrong-lock and forces a reground (~67-69.5 s), the true
car has driven ~26.5 m downstream and out of frame (in-FOV ~0.49), so the only salient
near-camera car the VLM can propose is the parked decoy; more clock time cannot help when
there is no true-car box left to reacquire. Control (loss-gate alone, no reground gate) also
ends `closest_at_end == "distractor"` (re-locks the decoy on all 4 extra regrounds) → the
loss-gate alone does not self-correct either, so attribution is unchanged from E7. This is
the **geometry-only correction has a ceiling; search/identity required** outcome, adding a
durability caveat to E7's NO rather than reversing it. Raw:
`experiments/2026-07-03-reground-selfcorrect/runs/`.

### 2026-07-03 — E9 retarget-switch: mid-follow NL target switch ([`experiments/2026-07-03-retarget-switch/`](../../experiments/2026-07-03-retarget-switch/README.md))

Deployed levers on all legs (`--loss-gate motion --dr pursuit --acquire-hold motion`), 0.5
m/s, real carry (local 3090 SAM2 @1024), Jetson Q8_0 acquire, 15 W + jetson_clocks
(corrected from "MAXN_SUPER": this board's firmware has no MAXN_SUPER, only 15W/7W — the
runs were physically at 15W; see `docs/decisions/part2-rebuild.md`).
New **escort twin** (`--twin escort`): a BLUE car (BGR 230,90,40) 2.5 m behind + 3 m east of
the white rover, co-moving — NL-referable by construction, so the E3 identical-twin identity
problem does not apply. **Retarget** (`--retarget-t 50`): at the first CARRY tick >= t=50 the
SM swaps its submit caption white→"the blue car", drops the carry, and re-acquires via the
whole not-CARRY path (E7 reground gate not consulted). Trials 75 s. Post-switch the escort
("distractor" label) IS the commanded target, so the twin metrics' PASS sign is flipped.

Precondition color smoke (10 poses x 2 captions, greedy decoding):

| Caption | hits / 10 | verdict |
|---|---|---|
| the white car | 10 | PASS (>= 7) |
| the blue car | 10 | PASS (>= 7) |

Legs:

| Leg | in_fov | switch_wall (s) | switch_on (last) | closest_at_end | final_d_dist (m) | frac_closer_dist_post | dist_in_fov_post | verdict |
|---|---|---|---|---|---|---|---|---|
| ctl  | 1.000 | — | — | true | — | — | — | **PASS** (escort alone does not break follow) |
| rt-a | 1.000 | 2.35 | distractor | distractor | 0.41 | 1.00 | 1.00 | **PASS** (7/7) |
| rt-b | 1.000 | 2.35 | distractor | distractor | 0.43 | 1.00 | 1.00 | **PASS** (7/7) |
| rt-c | 1.000 | 2.35 | distractor | distractor | 0.43 | 1.00 | 1.00 | **PASS** (7/7) |

**RQ-E9 = YES.** The two-tier loop executes a mid-follow natural-language target switch:
commanded "the blue car" at t=50 s, it locks the new (escort) target in **2.35 s** (well
under the 15 s bar) and follows it to trial end **3/3** at 0.5 m/s, whole-trial in-FOV
1.000, without breaking the ctl leg (escort present, no retarget → follow held, in-FOV
1.000, `closest_at_end == "true"`). The switch mechanically reuses the not-CARRY
acquire/relock path already validated at 0.5 m/s; the first post-switch VLM draw returned
the blue escort directly (single draw, no white-car false-accept). This closes the second
half of the north-star sentence ("switch to that blue truck") — the retarget verb, untested
in E1-E8, works at the E6 follow ceiling. Colour discrimination on synthetic top-down frames
is not a bottleneck (smoke 10/10 both, the pre-registered blue open question did not bite).
Post-switch `switch_on`/`closest_at_end == "distractor"` and `id_switch_s` ~22.3 s are the
*intended* values (the copter is supposed to move onto the escort), per the verdict sign
flip. n=3 real (distinct md5s, n_frames 1378/1313/1319; deterministic switch wall 2.35).
Raw: `experiments/2026-07-03-retarget-switch/runs/{color-smoke,ctl,rt-a,rt-b,rt-c}/`.

### 2026-07-03 — E10 fast-follow-ceiling: where does the follow loop actually stop? ([`experiments/2026-07-03-fast-follow-ceiling/`](../../experiments/2026-07-03-fast-follow-ceiling/README.md))

Full lever stack (`--vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold motion`), real
carry (local 3090 SAM2 @1024), Jetson Q8_0 acquire, 15 W + jetson_clocks. Speed ladder with
the two rig artifacts removed: the 140 m world edge (world texture auto-extended per reach)
and the three hard-coded caps parameterized (pursuit vmax 2.5, hist_vel clamp ±2.5, PID
MAX_VX/VY 3.0 → all lifted via `--vmax 4.0`). Defaults bit-identical to E2-E9; reg-1.5
confirms no ≤1.5 behavior change. Per-leg gate: PASS iff `in_fov_frac >= 0.90 AND
recovered_after_occlusion`. Trials 75 s.

| leg | speed (m/s) | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean | binding mode (FAIL) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reg-1.5 | 1.5 | PASS | 1.000 | True | 16.57 | 18 | 16 | 1 | 25.89 | 80.2 | — |
| s2.0a | 2.0 | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.87 | 102.2 | — |
| s2.0b | 2.0 | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.82 | 102.1 | — |
| s2.0c | 2.0 | PASS | 1.000 | True | 2.30 | 7 | 5 | 1 | 13.89 | 102.1 | — |
| s2.5a | 2.5 | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 127.4 | — |
| s2.5b | 2.5 | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 127.9 | — |
| s2.5c | 2.5 | PASS | 1.000 | True | 2.30 | 4 | 2 | 1 | 6.76 | 128.9 | — |
| s3.0a | 3.0 | FAIL | 0.052 | False | None | 32 | 31 | 0 | — | — | never-locked (first-acquire) |
| s3.0b | 3.0 | FAIL | 0.052 | False | None | 32 | 31 | 0 | — | — | never-locked (first-acquire) |

**RQ-E10 = YES** (reg-1.5 PASS **and** s2.0 3/3 PASS). **Measured ceiling = 2.5 m/s** (1.5
1/1, 2.0 3/3, 2.5 3/3, 3.0 0/2). The follow stack holds 2.0 and 2.5 m/s once the rig edge +
caps are removed — the old E2 "< 0.5 m/s" ceiling was a rig artifact (world edge + 2.5 caps),
not physics; the loop tracks to **5x** the E2 figure. Above 2.5 the binding constraint flips
to **first-acquire**, not tracking: both 3.0 legs never locked (in_fov 0.052, 31/32 acquires
rejected, first_lock None — the E5/E6 acquire-lottery, a standing-start copter can't get a
repeatable VLM draw before a 3.0 m/s car crosses the FOV); once locked (2.0/2.5) carry+pursuit
hold in_fov 1.000 to trial end. Latency signature (secondary): relock wall-time *falls* with
speed (25.9 s @1.5 → 13.9 @2.0 → 6.8 @2.5 — faster car re-enters the acquire FOV sooner) and
carry pixel error rises modestly (80 → 128 px, benign while in_fov 1.000). So the next lever to
raise the ceiling past 2.5 is first-acquire reliability at speed, not the pursuit controller or
carry FPS. Raw: `experiments/2026-07-03-fast-follow-ceiling/runs/{reg-1.5,s2.0a-c,s2.5a-c,s3.0a-b}/`.

### 2026-07-03 — E11 chase-acquire: pre-lock blob-pursuit chase, first-acquire at 3.0 m/s ([`experiments/2026-07-03-chase-acquire/`](../../experiments/2026-07-03-chase-acquire/README.md))

> **Ceiling qualifier — the ">= 3.5 m/s" below is RETRACTED by E12** (banner added here
> 2026-07-21T18:05Z, R-21; the campaign README has carried the same one since E12 landed).
> s3.5a/b were a draw-1 easy-spawn artifact: both accepted `acquire_log[0]` at 2.30 s on the
> t=0 gift frame, after in_fov had already fallen 1→0 at t=2.25 s, so the pre-lock chase was
> never exercised at 3.5. E12's hard-spawn re-run (`--acquire-delay 3.0`) fails 3.5 **0/3**
> and passes 3.0, so the **chase-validated ceiling is 3.0 m/s**. The reg-2.5 and s3.0 3/3
> passes below stand unaffected; the s3.5 rows do not. Registry `E10-fast-follow-ceiling`
> records the real-follow headline as 2.5 m/s.

Follows E10's finding that above 2.5 m/s the binding constraint is **first-acquire, not
tracking**. E10's `--acquire-hold motion` was a position-only P-servo on the frame-diff blob
that hovered (`pid.compute(None)` → zeros) the moment the blob left the FOV; a 3.0 m/s car
crossed the ±4.33 m half-footprint by draw 2, so the VLM got exactly one car-in-frame draw and
lost the greedy lottery. E11 adds `--acquire-hold chase`: pre-first-lock, each visible motion
blob is converted (`blob_chase_box` sweep-center anchor → `box_to_world`) into a `hist` append,
so the *existing* `hist_vel`→`pursuit_vel` DR chases the mover pre-lock (velocity feed-forward
while visible, dead-reckoning when it outruns the FOV), buying car-in-frame time until the VLM
(sole lock authority) locks. Defaults bit-identical (`none`/`motion` never append to hist).
Full lever stack, real carry (3090 SAM2 @1024), Jetson Q8_0 acquire, 15 W + jetson_clocks.
Per-leg gate: PASS iff `in_fov_frac >= 0.90 AND recovered_after_occlusion`. Trials 75 s.

| leg | speed (m/s) | vmax | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reg-2.5 | 2.5 | 4.0 | PASS | 1.000 | True | 2.30 | 8 | 6 | 1 | 16.22 | 127.9 |
| s3.0a | 3.0 | 4.0 | PASS | 1.000 | True | 9.21 | 15 | 13 | 1 | 25.74 | 146.8 |
| s3.0b | 3.0 | 4.0 | PASS | 1.000 | True | 9.31 | 15 | 13 | 1 | 25.74 | 148.5 |
| s3.0c | 3.0 | 4.0 | PASS | 1.000 | True | 9.26 | 8 | 6 | 1 | 9.24 | 147.4 |
| s3.5a | 3.5 | 5.0 | PASS | 0.962 | True | 2.30 | 4 | 2 | 1 | 6.82 | 174.6 |
| s3.5b | 3.5 | 5.0 | PASS | 0.964 | True | 2.30 | 5 | 3 | 1 | 9.17 | 174.7 |

**RQ-E11 = YES** — reg-2.5 PASS (no chase-regression; **not** "byte-identical to E10 s2.5" as first published — corrected 2026-07-21, R-7: acquire attempts 8 vs 4, rejected 6 vs 2, relock 16.22 s vs 6.76 s, and the four `results.json` have four distinct md5s. What matches is the *gate verdict*, on a rig with visible run-to-run variance) **and** s3.0
**3/3** PASS. Chase-hold makes first-acquire reliable at 3.0 m/s: E10's `motion` s3.0 never
locked (in_fov 0.052, first_lock None); chase-hold keeps the car in-frame across draws until
the VLM locks at **~9.2 s** (s3.0a/b needed 15 acquire attempts / 13 rejected before the
winning draw — chase bought that time), then carry+pursuit hold in_fov **1.000** to trial end.
**New measured ceiling: >= 3.5 m/s** — **RETRACTED, see the banner above; chase-validated
ceiling = 3.0 m/s (E12)** — (as published: NOT pinned — s3.5 passed 2/2 at `--vmax 5.0`, the top
rung tested; the real ceiling is above 3.5 and E11 did not find it). The follow ceiling moved
2.5 → **at least 3.5 m/s** in one lever (7x the E2-era "< 0.5") — **now 3.0 m/s, 6x, per E12**.
The fix is entirely in the
pre-lock control law — it reuses the already-validated DR/pursuit machinery, changes nothing
about the VLM or carry, and is off by default. Est-vs-actual: chase over-performed (s3.0
estimated 50-60% → 3/3; s3.5 estimated ~20% → 2/2; no garbage-blob DR runaway on any leg); the
probe under-reached its own ceiling. Raw: `experiments/2026-07-03-chase-acquire/runs/{reg-2.5,s3.0a-c,s3.5a-b}/`.

### 2026-07-03 — E12 late-command: hard-spawn validation of the E11 ceiling ([`experiments/2026-07-03-late-command/`](../../experiments/2026-07-03-late-command/README.md))

Config: 15 W + jetson_clocks, Jetson Q8_0 acquire + host 3090 SAM2 carry @1024, full lever
stack `--loss-gate motion --dr pursuit --acquire-hold chase --acquire-delay 3.0`. The
`--acquire-delay 3.0` (E12 patch, default 0.0 = bit-identical) blocks any VLM lock before
t=3 s, removing the t=0 "gift frame" that E11's s3.5 passes rode.

| leg | speed (m/s) | vmax | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean | binding mode (FAIL) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d3.0  | 3.0 | 4.0 | PASS | 1.000 | True  | 12.17 | 12 | 10 | 1 | 18.63 | 145.2 | — |
| d3.5a | 3.5 | 5.0 | FAIL | 0.030 | False | None  | 31 | 30 | 0 | — | — | never-locked (first-acquire) |
| d3.5b | 3.5 | 5.0 | FAIL | 0.029 | False | None  | 31 | 30 | 0 | — | — | never-locked (first-acquire) |
| d3.5c | 3.5 | 5.0 | FAIL | 0.030 | False | None  | 31 | 30 | 0 | — | — | never-locked (first-acquire) |

**RQ-E12 = NO** — with the gift frame removed, 3.5 m/s does **not** hold: d3.5 **0/3**
never-locked (first_lock None, 30/31 draws rejected, in_fov ~0.03 — the 3.5 m/s car escapes
the FOV and the pre-lock blind DR chase cannot re-close the gap before every post-t=3 draw sees
empty road). The d3.0 control still PASSes (in_fov 1.000, recovered), locking at **12.17 s** —
~3 s later than E11's gift-frame 9.2 s, i.e. the genuine blind-chase re-close costs the delay it
was denied. **E11's ">= 3.5" was a draw-1 easy-spawn artifact** (s3.5a/b `acquire_log[0]` accepted
at 2.30 s on the t=0 frame, but in_fov had already fallen 1→0 at t=2.25 s — the lock landed on a
car no longer in frame, so the pre-lock chase was never actually exercised at 3.5). s3.0 were
genuine (copter translated N 0→26 m through ACQUIRE). **Honest chase-validated follow ceiling =
3.0 m/s** — still 6x the E2-era "< 0.5". Est-vs-actual: matched the pre-registration (d3.0 PASS
expected, d3.5 expected to fail once the gift frame was removed). Raw:
`experiments/2026-07-03-late-command/runs/{d3.0,d3.5a,d3.5b,d3.5c}/`.

### 2026-07-03 — E13 identity-gate (appearance-color gate on REGROUND) ([`experiments/2026-07-03-identity-gate/`](../../experiments/2026-07-03-identity-gate/README.md))

Rig: host 3090 SITL + SAM2 carry @1024, Jetson Qwen2-VL-2B Q8_0 self-booted per trial, 15 W
mode 0 + jetson_clocks. Gate = `--reground-gate appearance` (off by default): descriptor = mean
BGR of the crop's brightest quartile (max-channel ranked), template bound at first ACQUIRE, accept
iff L-inf ≤ `--app-tau 12`. Decoy rendered `--decoy-shade 215` (discriminable same-class white).

| leg | speed (m/s) | flags | n_regr | gate_rej | relock_on | closest_end | final_d_true / d_dist (m) | in_fov | verdict |
|---|---|---|---|---|---|---|---|---|---|
| smoke | — | 215-decoy capture + descriptor sep | — | — | — | — | — | — | PASS (10/10, dists 0.0 vs 30.0) |
| ctl-decoy | 0.25 | `--twin decoy --decoy-shade 215 --duration-s 150`, no gate | 10 | 0 | `[true,dist×4,?,?,?,dist]` | distractor | 31.53 / 6.88 | 0.449 | reproduces wrong-lock |
| ap-decoy-a | 0.25 | ctl + `--reground-gate appearance` | 2 | 26 | `[dist]` | distractor | 26.50 / 1.76 | 0.503 | FAIL |
| ap-decoy-b | 0.25 | ctl + gate | 2 | 24 | `[dist]` | distractor | 26.49 / 1.79 | 0.488 | FAIL |
| ap-decoy-c | 0.25 | ctl + gate | 2 | 14 | `[dist]` | distractor | 27.01 / 2.33 | 0.490 | FAIL |
| ap-reg-0.5 | 0.5 | plain occlusion + gate | 1 | 0 | — | — | — | 1.000 | PASS |
| ap-reg-3.0 | 3.0 | E12 d3.0 hard-spawn config + gate | 1 | 0 | — | — | — | 1.000 | PASS |
| ap-rt | 0.5 | E9 retarget @50 s + gate | 1 | 0 | `[true,dist]` | distractor | 4.18 / 0.42 | 1.000 | PASS (E9 7/7, switch 2.35 s) |

**RQ-E13 = NO** — the appearance-color gate does not close the identity hole. ap-decoy **0/3**:
the gate fires correctly (14-26 REGROUND `gate` rejects of clean decoy boxes vs 0 in control,
template correctly `[245,245,245]`) but is defeated by a **blend box** — at t≈67-69 s the true car
emerges co-located with the parked decoy, the VLM draws a two-car box (`[268.8,0,428.8,441.6]`,
160×441 px), its brightest quartile is dominated by the 245 true-car pixels so it passes tau=12,
but the box centres on the decoy → SAM2 latches the decoy, wrong-lock 3/3 (final_d_true ~26.5 m,
true car escaped). A bright-pixel colour statistic over a loose box is not bound to the tracked
instance — defeated the same way the size prior (E3) and motion gate (E7) were. Regression clean
(ap-reg-0.5/-3.0/ap-rt all PASS): the gate does not touch plain relock, the 3.0 m/s ceiling, or
the E9 retarget switch. Attribution note: ctl `relock_on[0]="true"` (a transient early reground
in the 150 s multi-reground control) but ctl ends firmly wrong-locked on the decoy — the rule's
intent (decoy captures REGROUND) holds, so NO not NOT-MEASURABLE (see README for the literal-rule
divergence, flagged for audit). Est-vs-actual: smoke ~80%→10/10; ap-decoy ~45% PASS→0/3 (the
pre-registered blend-box failure branch); regressions ~85-90%→all PASS. Named next lever: an
embedding on the SAM2 *mask* (not the box crop), or blend/oversized-box rejection at REGROUND.
Raw: `experiments/2026-07-03-identity-gate/runs/`.

### 2026-07-03 — E14 mask-identity (mask-bound median gate on REGROUND) ([`experiments/2026-07-03-mask-identity/`](../../experiments/2026-07-03-mask-identity/README.md))

Rig: host 3090 SITL + SAM2 carry @1024, Jetson Qwen2-VL-2B Q8_0 self-booted per trial, 15 W
mode 0 + jetson_clocks. Gate = `--reground-gate mask` (off by default): on a size-passing REGROUND,
run the exact StreamCarry init the accept would run and take the per-channel **median** BGR over
its frame-0 SAM2 mask (the instance actually latched); accept iff L-inf ≤ `--app-tau 12` vs the
template bound at NL grounding. Decoy `--decoy-shade 215`. The median is a majority vote over the
latch, so a majority-decoy blend reads 215 (reject) even with true pixels inside — the fix E13's
crop-brightest-quartile could not do.

| leg | speed (m/s) | flags | n_regr | gate_rej | relock_on | closest_end | final_d_true / d_dist (m) | in_fov | verdict |
|---|---|---|---|---|---|---|---|---|---|
| smoke | — | 215-decoy capture + mask-latch sep + blend probes | — | — | — | — | — | — | PASS (10/10; 4 blend probes median [215,215,215] REJECT, true-strip [245,245,245] ACCEPT) |
| ctl-decoy | 0.25 | `--twin decoy --decoy-shade 215 --duration-s 150`, no gate | 6 | 0 | `[true,dist×4]` | distractor | 26.68 / 1.95 | 0.447 | reproduces wrong-lock |
| mk-decoy-a | 0.25 | ctl + `--reground-gate mask` | 1 | 13 | `[true]` | true | 0.21 / 24.53 | 1.000 | PASS |
| mk-decoy-b | 0.25 | ctl + gate | 1 | 13 | `[true]` | true | 0.21 / 24.53 | 1.000 | PASS |
| mk-decoy-c | 0.25 | ctl + gate | 1 | 11 | `[true]` | true | 0.22 / 24.52 | 1.000 | PASS |
| mk-reg-0.5 | 0.5 | plain occlusion + gate | 1 | 0 | — | — | — | 1.000 | PASS |
| mk-reg-3.0 | 3.0 | E12 d3.0 hard-spawn config + gate | 1 | 0 | — | — | — | 1.000 | PASS |
| mk-rt | 0.5 | E9 retarget @50 s + gate | 1 | 0 | `[?,dist]` | distractor | 4.19 / 0.42 | 1.000 | PASS (E9 7/7, template rebinds [230,90,40]) |

**RQ-E14 = YES** — the mask-bound median gate closes the identity hole **3/3** (mk-decoy final_d_true
0.21-0.22 m, in_fov 1.000, template `[245,245,245]`) with zero regression (mk-reg-0.5/-3.0 and mk-rt
all PASS). First identity cue to survive the two-car blend box that defeated size (E3), motion (E7),
and crop-colour (E13). Mechanism from the acquire_log: while the true car is co-located with the
decoy the gate rejects every blend/decoy box (11-13 `gate` rejects/leg — the box straddles both
cars so the latch is majority-decoy → median 215 → reject vs the 245 template), then accepts the
first clean true-car box once the cars separate (t=86.25 s in mk-decoy-a) → SAM2 locks the true car.
The win path is **reject-until-separated**, not first-frame accept; the pre-registered failure branch
(*identity-preserving no-relock*) did not materialise — the VLM produced a separated true box well
within 150 s in all 3 repeats. Est-vs-actual: runtime ~110 min (on est); smoke ~85%→PASS (probe held
exactly, blend median [215,215,215]); mk-decoy ~50-60%→3/3 (top of range); regressions unaffected
(gate off by default, consulted only on REGROUND after the size prior, 0 rejects on single-car legs).
Raw: `experiments/2026-07-03-mask-identity/runs/`.

### 2026-07-03 — E15 mask-hardening (geometry stress of the E14 mask gate) ([`experiments/2026-07-03-mask-hardening/`](../../experiments/2026-07-03-mask-hardening/README.md))

Rig: host 3090 SITL + SAM2 carry @1024, Jetson Qwen2-VL-2B Q8_0 self-booted per trial, 15 W
mode 0 + jetson_clocks. Same shade/descriptor as E14 (`--decoy-shade 215`, `--reground-gate mask`,
tau 12); two new geometry knobs (off by default): `--decoy2 7.0` (second same-shade decoy 7 m north,
destroys E14's clean accept window) and `--occ2 82 10` (second occlusion bridge over t[82,92],
covering E14's observed accept at t=86.25). Shared decoy set on all 9 legs: `--speed 0.25 --twin
decoy --decoy-shade 215 --duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion`.

| leg | flags (beyond shared set) | n_regr | gate_rej | relock_on | closest_end | final_d_true / d_dist2 (m) | in_fov | verdict |
|---|---|---|---|---|---|---|---|---|
| reg-e14 | `--reground-gate mask` (E14 config) | 1 | 12 | `[]` | true | 3.41 / — | 1.000 | **FAIL (no-relock)** |
| ctl-dd | `--decoy2 7.0`, no gate | 12 | 0 | `[true,dist×...]` | distractor | 26.64 / 8.93 | 0.450 | REPRODUCES |
| dd-a | `--decoy2 7.0` + gate | 2 | 11 | `[true,true]` | true | 0.21 / 17.54 | 1.000 | PASS (unattributable) |
| dd-b | `--decoy2 7.0` + gate | 2 | 13 | `[true,true]` | true | 0.21 / 17.54 | 1.000 | PASS (unattributable) |
| dd-c | `--decoy2 7.0` + gate | 2 | 14 | `[true]` | distractor2 | 20.18 / 2.44 | 0.630 | FAIL (verified-but-lost) |
| ctl-ro | `--occ2 82 10`, no gate | 8 | 0 | `[true,dist×6]` | distractor | 26.61 / — | 0.450 | REPRODUCES |
| ro-a | `--occ2 82 10` + gate | 1 | 11 | `[true]` | true | 0.21 / — | 1.000 | PASS (unattributable) |
| ro-b | `--occ2 82 10` + gate | 2 | 10 | `[true,true]` | true | 0.20 / — | 1.000 | PASS (unattributable) |
| ro-c | `--occ2 82 10` + gate | 2 | 8 | `[true,true]` | true | 0.53 / — | 1.000 | PASS (unattributable) |

**RQ-E15 = NOT-MEASURABLE** — the pre-registered patch-regression guard fired: **reg-e14**
(E14's byte-for-byte mk-decoy config, re-run under the E15 patched code) FAILed with
identity-preserving no-relock (gate rejected all 12 reground boxes, never re-accepted, coasted on
DR to 3.41 m from true — did NOT wrong-lock the decoy, `closest=true in_fov=1.000`), where E14 went
3/3 converging to 0.21 m. The rule routes reg-e14 FAIL → NOT-MEASURABLE and halts attribution of the
stress families. Both controls reproduced (ctl-dd/ctl-ro latched the decoy ~26.6 m from true), so the
geometries are valid traps; the block is the broken baseline. **The anomaly** (for the next-cycle
audit): reg-e14, the EASIEST scenario, failed to accept, while 5/6 HARDER stress legs (dd-a/b, ro-a/b/c)
accepted clean true boxes late (t≈100–114) and converged to ≤0.53 m — a pattern that fits stochastic
win-path fragility (E14's 3/3 = three catches of one narrow accept window; an independent draw can
miss it) more than a systematic code regression (which would disable accepts uniformly). Two readings —
E15-patch perturbation vs E14 fragility — this cycle cannot decide; the `np.array_equal` selfcheck
proves render identity, not SITL/VLM/pursuit timing identity across the code deltas. Stress numbers are
RECORDED but NOT claimed (dd 2/3, ro 3/3) — un-attributable without a passing baseline. Est-vs-actual:
runtime ~130 min (est 110–125); overall YES est ~25–35% → NOT-MEASURABLE (the anticipated reg-e14-FAIL
halt branch). Raw: `experiments/2026-07-03-mask-hardening/runs/`.

### E16 relock-rate (2026-07-03) — RQ-E16 QUALIFIED, r=6/8

Fixed-code n=8 replication of E14's exact mask-gate config on current main (`8d6336e`, the E15
merge; E15 knobs off by default, so the code under test = E14's gate). No harness patches. All legs:
15W mode 0 + jetson_clocks, image-size 1024, app-tau 12, decoy-shade 215, `--reground-gate mask`
(reps; ctl no gate), `--speed 0.25 --twin decoy --duration-s 150 --loss-gate motion --dr pursuit
--acquire-hold motion`.

| leg | verdict | n_regr | gate_rej | size_rej | relock_on | closest_end | d_true_m | in_fov | relock_t_s |
|---|---|---|---|---|---|---|---|---|---|
| ctl | REPRODUCES | 5 | 0 | 39 | distractor x4 | distractor | 26.71 | 0.448 | 55.68/65.39/85.33/117.33 |
| rep-1 | FAIL wrong-end | 2 | 8 | 33 | true | distractor | 18.15 | 0.680 | 71.88 |
| rep-2 | PASS | 1 | 12 | 9 | true | true | 0.21 | 1.000 | 81.30 |
| rep-3 | PASS | 1 | 13 | 9 | true | true | 0.21 | 1.000 | 83.94 |
| rep-4 | PASS | 1 | 13 | 8 | true | true | 0.21 | 1.000 | 81.46 |
| rep-5 | FAIL no-relock | 1 | 11 | 40 | (empty) | true | 26.85 | 0.371 | (none) |
| rep-6 | PASS | 1 | 12 | 9 | true | true | 0.12 | 1.000 | 81.52 |
| rep-7 | PASS | 1 | 13 | 11 | true | true | 0.20 | 1.000 | 88.62 |
| rep-8 | PASS | 1 | 12 | 31 | true | true | 0.21 | 1.000 | 133.90 |

**Relock rate r = 6/8** valid reps (0 retries, 0 exclusions — every rep produced >=1 reground).
**RQ-E16 = QUALIFIED (6/8)**: denom 8, denom-r=2 (not RELIABLE), 2r=12>8 (not FRAGILE). No
GATE-BREACH (no rep relocked the decoy). ctl REPRODUCES -> rig valid. PASS accept-time spread
81.30-133.90 s (five in the estimated 74-90 band; rep-8 late at 133.90). Est-vs-actual: modal
prediction QUALIFIED r=5-6/8 hit exactly; ctl reproduce ~90% prior held; identity-breach <5% ->
observed 0; runtime ~130 min (est 120-150). The two FAILs are win-path timing misses of different
kinds (never-acquired vs acquired-too-early), both upstream of the gate. Raw:
`experiments/2026-07-03-relock-rate/runs/`.

### E17 reground-chase (2026-07-03) — RQ-E17 NO, 0/10 identical failures (n_effective 1; lever regressed E16's 6/8)

One harness patch (`--reground-hold {none,chase}`, default none = bit-identical to E2-E16, selfcheck
PASS). Extends E11's blob-chase to REGROUND blind phases (control law only; size prior + E14 mask gate
untouched; REGROUND only, never RETARGET). Branch off main `ad2c009`. All rh/ctl legs: 15W mode 0 +
jetson_clocks, image-size 1024, app-tau 12, decoy-shade 215, `--speed 0.25 --twin decoy --duration-s
150 --loss-gate motion --dr pursuit --acquire-hold motion`; rh rows add `--reground-gate mask
--reground-hold chase` (ctl neither). Guards: `--speed 3.0 --vmax 4.0 --loss-gate motion --dr pursuit
--acquire-hold chase --acquire-delay 3.0 --reground-gate mask --reground-hold chase`.

| leg | verdict | n_regr | gate_rej | size_rej | relock_on | closest_end | d_true_m | in_fov | rg_fov | relock_t_s |
|---|---|---|---|---|---|---|---|---|---|---|
| ctl | REPRODUCES | 5 | 0 | 36 | true,dist x3 | distractor | 26.69 | 0.447 | n/a | 46.20/59.22/64.79/113.59 |
| rh-1..10 | FAIL no-relock [HOLD-MISS] (all 10) | 1 | 0 | 52-53 | (empty) | distractor | 81.2-83.7 | 0.228-0.231 | 0.025-0.026 | (none) |
| guard-a | PASS | 1 | — | — | — | — | — | 1.000 | 1.000 | first_lock 12.17 |
| guard-b | PASS | 1 | — | — | — | — | — | 1.000 | 1.000 | first_lock 9.86 |

(Per-rep rh rows are near-identical; full values in `experiments/2026-07-03-reground-chase/README.md`.)

**Relock rate r = 0/10** valid reps (0 retries, 0 exclusions). **RQ-E17 = NO** (>=2 FAILs -> NO-LIFT;
the lever regressed E16's 6/8 to 0/10). **Read 0/10 as a mechanism, not a rate** (added
2026-07-21T18:05Z, R-21): the ten reps are one observation repeated, `n_effective = 1` per registry
`E17-reground-chase`. The table row above already collapses them because the traces are
near-identical — verified in `runs/rh-{1..10}/results.json`: `in_fov_frac` 0.2279–0.2305,
`carry_frames` 464–474, `carry_px_err_mean` **8.6 in all ten**, `n_regrounds` 1 in all ten,
`relock_on` empty in all ten. The defensible claim is that the REGROUND blob-chase servos onto the
decoy in every rep; no relock *rate* and no Wilson interval should be quoted from this leg, and the
"0/10 vs E16's 6/8" contrast overstates the comparison by treating both as sampled rates.
No GATE-BREACH. **Guard verdict NO-REGRESSION** (both PASS at
3.0 m/s) — the lever is safe at the honest follow ceiling; the harm is specific to slow-mover REGROUND.
Mechanism: the REGROUND blob-chase servos onto the 215 decoy (dominant blob), driving the drone ~82 m
off; the true car leaves frame (rg_fov 0.025), the VLM never offers a clean box, the mask gate is never
consulted. E16's passive DR-coast is strictly better. Est-vs-actual: design predicted r=9-10/10 LIFTS
(premise: held FOV removes the no-relock mode) — **inverted to 0/10**; the mechanism assumption
(chase = FOV-keeping) was false for this regime, a wrong estimate that is itself the finding. Runtime
~200 min (est 190-230). Raw: `experiments/2026-07-03-reground-chase/runs/`.

### 2026-07-03 — E18 real-video-replay ([`experiments/2026-07-03-real-video-replay/`](../../experiments/2026-07-03-real-video-replay/README.md))

First real-footage test of the deployed two-tier stack (all prior E2–E17 ran on synthetic
`sitl_cam` renders). UAV123 aerial car sequences replayed at wall-clock 30 fps (frames DROP during
inference — a live-camera realism), scored against dataset GT at native fps. Rig: host 3090
SAM2.1-hiera-tiny @1024 rate-capped 6.15 Hz (E1's on-Orin number, D3 — but measured at
`image_size` **768**, not the 1024 the carry runs at, so the emulated stride is optimistic;
see the rig-cap note below and machine-disclosure M1); Jetson Orin Nano q8_0 terse
15W + jetson_clocks (real acquire wall time). Perception-only (no SITL/actuation, D1). PASS =
`genuine_lock` (first accepted box hits GT IoU≥0.25 at its arrival frame) AND `coverage` ≥ 0.50;
clip PASS = better of n=2 A reps. Leg B = oracle GT-frame-0 carry init, REGROUND off (D5 attribution).

| clip | class | A rep1 genuine/cov | A rep2 genuine/cov | A t_lock | B genuine/cov | clip A verdict |
|---|---|---|---|---|---|---|
| car3 | plain | F / 0.976 | F / 0.976 | 4.89 | T / 0.984 | FAIL (stale acquire) |
| car9 | plain | F / 0.993 | F / 0.993 | 4.88 | T / 0.990 | FAIL (stale acquire) |
| car14 | plain, occ | F / 0.903 | F / 0.903 | 4.82 | T / 0.915 | FAIL (stale acquire) |
| car18 | plain | F / 0.711 | F / 0.711 | 4.81 | T / 0.987 | FAIL (stale acquire) |
| car7 | distractor, occ | F / 0.285 | F / 0.285 | 4.81 | T / 0.993 | FAIL (stale acquire + REGROUND drift) |
| car10 | distractor | **T / 1.000** | **T / 1.000** | 4.84 | T / 1.000 | **PASS** |

**A PASS = 1/6** (car10) · **B PASS = 6/6.** **RQ-E18 = NO [grounding-bound]** (5 clips FAIL A while
PASS B → binder is the acquire tier, not carry). No UNRULED legs. Mechanism: the ~4.85 s full-frame
VLM acquire computes a *correct* box (SAM2 latches the right car — carry cov 0.90–0.99 on the three
loss-free clips) but by arrival the target has moved **~134 frames** (30 fps), so genuine_lock scored at
the arrival frame misses — **latency-vs-motion, not misgrounding.** car10 passes because its target is
slow at t=0. car7 is the only A leg whose carry also collapses (0.285 vs B 0.993): its 73-frame
occlusion trips a loss, REGROUND re-acquires *also* stale, and the appearance-only E14/E16 mask gate
accepts it (gate_rej=0 — right colour, wrong place) → drift. Est-vs-actual: predicted 3–5/6 PASS
(PARTIAL-to-YES) assuming acquire *accuracy* was the risk; **actual 1/6 NO** — the binder is acquire
*latency*, a wrong estimate that is the finding. Matrix ~35 min (est ~2 h); download ~1 h via HF
mirror (no VisDrone fallback). Raw: `experiments/2026-07-03-real-video-replay/runs/`, proof in
`.../proof/`.

Two rig/units corrections, 2026-07-21T18:05Z (R-21), neither of which moves the 1/6 vs 6/6 verdict:

- **Staleness displacement was published as ~146 frames; the measured value is ~134.** 146 was
  `t_lock` x 30 (4.85 s x 30 fps = 145.5), but `t_lock` is submit-to-*lock-delivered*
  and includes the post-arrival SAM2 init. `genuine_lock` is scored at the **box-arrival** frame, and
  E18's own runs log only `t_lock`. The submit→arrival index comes from E19's `mc_log` on the
  byte-identical rig (`experiments/2026-07-04-motion-comp-acquire/runs/*/results.json`, incl. the
  `ctl_none_car{3,10}` regression controls): `submit_i` 0 → `arrival_i` **133–135** on all 27 legs,
  mean 134.3 = **4.48 s**. An 8% overstatement of exactly the quantity the Part V warm-start reframe
  rests on; the ~4.85 s figure stays valid as *lock delivery*, and both numbers are now stated with
  their definition.
- **The 6.15 Hz cap is a 768 measurement applied to a 1024 carry.** `runs/bench.json` records
  `trt_768_cores.fps` = 6.15 at `image_size` 768; E1 never measured 1024 and said so. 1024 costs
  ~1.9x the encoder compute, so the true on-device stride is plausibly ~3 Hz and the emulated one
  is roughly 2x optimistic (machine-disclosure M1). Direction of the bias is uniform and known:
  carry-dependent PASSes are optimistic, carry-dependent FAILs conservative. **For E18 this makes
  the NO conservative** — the finding is that acquire latency binds, not carry rate. The same cap is
  inherited verbatim by E19/E20/E21/E23, where coverage *is* carry-rate-sensitive; those sections
  carry a pointer back here. No carry-dependent PASS in this arc may be described as an on-device
  rate until R-16 re-measures at 1024.

### 2026-07-04 — E19 motion-comp-acquire ([`experiments/2026-07-04-motion-comp-acquire/`](../../experiments/2026-07-04-motion-comp-acquire/README.md))

Two motion-compensation arms for E18's stale-lock gap, same six UAV123 clips / frozen captions /
byte-identical scoring, rig unchanged (3090 SAM2.1-tiny @1024 capped 6.15 Hz — a 768-measured cap,
~2x optimistic at 1024; see the E18 rig-cap note — + Jetson q8_0 terse
self-boot, 15W + jetson_clocks). ctl (`--mc none`, D4 regression guard) reproduced E18's signature
(car3 genuine=False cov 0.976; car10 PASS). Per-clip PASS = genuine_lock AND coverage >= 0.50,
better of n=2.

| clip | E18 A (baseline) | A-flow (NCC shift) | A-buf (catch-up) |
|---|---|---|---|
| car3 | F / 0.976 | **T / 0.982 PASS** (ncc 0.87) | F / 0.941 |
| car9 | F / 0.993 | F / 0.000 (ncc 0.32 refused) | F / 0.950 |
| car14 | F / 0.903 | F / 0.000 (ncc 0.64 wrong-match) | F / 0.850 |
| car18 | F / 0.711 | F / 0.000 (ncc 0.51 wrong-match) | F / 0.914 |
| car7 | F / 0.285 | F / 0.000 (ncc 0.56 wrong-match) | F / **0.934** |
| car10 | T / 1.000 PASS | **T / 1.000 PASS** (ncc 0.96) | **T / 1.000 PASS** |

**A-flow 2/6, A-buf 1/6 → RQ-E19 = PARTIAL [flow-fragile]** (best arm 2/6 in the 2-3 band; suffix
fires on 4 clips: car9 refusal + car14/car18/car7 wrong-matches, shifted IoU 0.000 at arrival while
unshifted scores same-or-better). Key mechanics: (1) FLOW is catastrophic when wrong — arrival-frame
init throws away E18's submit-frame-correct carry init, and a wrong/refused box there latches the
wrong object AND poisons the E14 mask-gate template, so REGROUND rejects genuine relocks (3-9
rej/run) and coverage pins at 0.000, strictly below no-MC. NCC 0.5 threshold does not separate:
wrong-matches score 0.51-0.64, right matches 0.87-0.96 (logged per D5, not tuned). (2) BUF cannot
structurally flip genuine_lock (first event = raw box at arrival, per spec) but converges exactly as
designed (backlog ~237 f, 19 steps, 3.09 s, gap < 12 on all 12 runs) and repairs coverage — car7
0.285 -> 0.934 (kills the E18 REGROUND-drift mode), car18 0.711 -> 0.914. Est-vs-actual: predicted
YES 4-6/6, actual PARTIAL 2/6 — both arm estimates wrong (flow 4-5/6, buf 5-6/6). Matrix ~22 min
summed run wall (est ~45 min). Raw: `experiments/2026-07-04-motion-comp-acquire/runs/`, proof in
`.../proof/`.

### 2026-07-04 — E20 prompt-scoped-acquire ([`experiments/2026-07-04-prompt-scoped-acquire/`](../../experiments/2026-07-04-prompt-scoped-acquire/README.md))

Operator-phrase-scoped first acquire vs E18's stale locks: the spatial part of the command ("the
red car **in the bottom left**") is parsed client-side into a padded 3x3-cell crop (pad 10% W/H,
`scope.py`), the frozen E18 caption is grounded inside the crop (sent native, no resize), and the
box maps back to full-frame. Scope on the FIRST ACQUIRE attempt only; retries + REGROUND stay
full-frame (D4). Same six UAV123 clips / frozen captions / byte-identical E18 scoring; rig
unchanged (3090 SAM2.1-tiny @1024 capped 6.15 Hz — 768-measured cap, ~2x optimistic at 1024; see the
E18 rig-cap note — + Jetson q8_0 terse self-boot, 15W + jetson_clocks). 27/27 legs clean; controls
reused from E18 A / E19 ctl (D6). Per-clip PASS = genuine_lock AND coverage >= 0.50, better of n=2.

| clip | hint | E18 A (baseline) | cell | cellbuf | scoped acquire_s |
|---|---|---|---|---|---|
| car3 | bottom left | F / 0.976 | F / 0.982 | F / 0.977 | 1.57 |
| car7 | top center | F / 0.285 | F / **0.997** | F / 0.975 | 1.83 |
| car9 | bottom center | F / 0.993 | **T / 0.996 PASS** | **T / 0.990 PASS** | 1.83 |
| car10 | center | T / 1.000 PASS | **T / 1.000 PASS** | **T / 1.000 PASS** | 2.03-2.07 |
| car14 | center | F / 0.903 | **T / 0.907 PASS** | **T / 0.904 PASS** | 2.00 |
| car18 | middle left | F / 0.711 | F / **0.980** | F / 0.958 | 1.83 |

**cell 3/6, cellbuf 3/6 (same set) → RQ-E20 = PARTIAL [hint-fragile]**. Mean scoped acquire
**1.85 s** vs E18's **~4.48 s** on the same definition (**2.4x**, backlog ~134 -> 47-62 frames)
— corrected 2026-07-21T18:05Z (R-21): as published this read "vs E18's ~4.85 s (2.6x, backlog
~146 -> 47-62 frames)", which juxtaposed two differently-defined latencies. 1.85 s is
`acquire_s` = (`arrival_i` − `submit_i`)/fps, i.e. **submit to box arrival** (campaign README,
"Latency is measured per submit in `mc_log`"); E18's 4.85 s is `t_lock`, **submit to lock
delivered**, ~0.35 s longer than its own `acquire_s`. The backlog pair inherited the same mismatch
(47-62 is `acquire_s` x 30, ~146 was `t_lock` x 30 against a logged arrival index of 133-135). Like
for like, either **acquire_s 1.85 s vs ~4.48 s (2.4x)** or **t_lock 2.22 s vs 4.84 s (2.2x)**; the
2.6x figure belongs to neither pairing. The mechanism and the PARTIAL verdict are untouched — the
ROI-campaign prefill
scaling (2026-06-26) delivered at first acquire, estimates hit exactly (est 1.7-2.3 s, est 3/6).
Regression guard: no breach; the earlier lock alone lifts coverage car7 0.285 -> 0.997, car18
0.711 -> 0.981. Residual FAILs (car3/car7/car18, arrival-IoU 0.00/0.00/0.02) are target-size
bound: small targets displace more than their own footprint even in ~1.8 s, while coverage is
0.98+ on all six (submit-frame carry init latches the right object). [hint-fragile]: the wrong
probe (car10 mis-hinted "top left") hallucinated a lock 2/2 reps, coverage 0.000, and the
poisoned mask-gate template then rejected all 10 genuine REGROUND re-offers — E19-FLOW-style
poisoning at the UX layer, no in-clip recovery. Matrix ~30 min wall. Raw:
`experiments/2026-07-04-prompt-scoped-acquire/runs/`, proof in `.../proof/`.

### 2026-07-04 — E21 coarse-to-fine acquire ([`experiments/2026-07-04-coarse-to-fine-acquire/`](../../experiments/2026-07-04-coarse-to-fine-acquire/README.md))

PASS = genuine_lock AND coverage >= 0.50; clip = best of n=2 reps. c2f = a cheap 320-px
coarse VLM pass votes a 3x3 cell, then E20's scoped fine crop. 13/13 legs clean, 15W +
jetson_clocks.

| clip | E18 A best | E20 cell best | c2f r1 | c2f r2 | c2f PASS? | coarse cell | GT cell | hit? |
|---|---|---|---|---|---|---|---|---|
| car3 | F / 0.976 | F / 0.982 | F / 0.980 | F / 0.980 | FAIL | bottom center | bottom left | MISS |
| car7 | F / 0.285 | F / **0.997** | F / 0.000 | F / 0.000 | FAIL | top center | top center | **HIT** |
| car9 | F / 0.993 | **T / 0.996** | F / 0.991 | F / 0.989 | FAIL | bottom center | bottom center | **HIT** |
| car10 | **T / 1.000** | **T / 1.000** | F / 0.000 | F / 0.000 | FAIL | middle right | center | MISS |
| car14 | F / 0.903 | **T / 0.907** | **T / 0.590** | **T / 0.590** | **PASS** | top left | center | MISS |
| car18 | F / 0.711 | F / **0.981** | F / 0.888 | F / 0.885 | FAIL | top left | middle left | MISS |

**c2f 1/6 → RQ-E21 = NO (REGRESSIVE) [prior-wrong]** (E20 cell was 3/6, E18 A 1/6).
Coarse-hint hit rate 4/12 reps (2/6 clips) → [prior-wrong] (>=2 wrong clips). Regression
guard BREACH on car7 (0.000 vs E18A 0.285), car10 (0.000 vs 1.000), car14 (0.590 vs 0.903)
→ (REGRESSIVE). Latency: coarse pass 0.97 s (n=12, 0.93-1.00), total acquire **2.73 s**
(2.57-2.90) — additive over E20's 1.85 s, backlog 47-62 → 77-87 frames (all four figures are
`acquire_s`, submit-to-arrival, so this comparison is like-for-like; cf. the E20 note). The extra pass
un-flips E20's wins: car9 (correct cell, same fine crop) drops arrival-IoU 0.32 → 0.24 under
the 0.25 lock threshold from ~1 s more target motion; car7 (correct cell) collapses cov 0.997
→ 0.000 as the widened SAM2 init→first-live jump breaks carry; car10 (wrong cell) hallucinates
a right-edge box and poisons the mask gate (gate_rej 10). A coarse VLM pass is inaccurate on
the EASY central targets (car10/car14 grounded off-cell) AND its latency re-opens the staleness
gap the crop closes. Matrix ~35 min wall. Raw: `experiments/2026-07-04-coarse-to-fine-acquire/runs/`,
proof in `.../proof/`.

### 2026-07-04 — E22 cv-proposal acquire ([`experiments/2026-07-04-cv-proposal-acquire/`](../../experiments/2026-07-04-cv-proposal-acquire/README.md))

A ~3 ms CPU location prior (phaseCorrelate camera-motion comp → absdiff motion mask
T=25 → caption-colour HSV mask → combine → largest CC ≥30px@320w → centroid →
`scope.hint_for`) replaces E20's operator hint with no second VLM call. **Phase-0
offline prior audit is a MANDATORY gate (t=0 cell-hit ≥ 4/6); it FAILED at 2/6, so NO
Jetson leg was run** (D4). Thresholds FROZEN (D5); prior selfcheck green.

Phase-0 audit (proposed 3x3 cell vs GT cell; `raw/phase0_prior_audit.txt`):

| clip | kw | t=0 proposed | source | t=0 GT | t=0 | motion_inGT | color_inGT |
|---|---|---|---|---|---|---|---|
| car3 | red | None | — | bottom left | miss | 0 | 0 |
| car7 | silver | center | color | top center | miss | 0 | 56 |
| car9 | white | bottom center | motion+color | bottom center | **HIT** | 329 | 79 |
| car10 | red | None | — | center | miss | 0 | 3 |
| car14 | red | None | — | center | miss | 0 | 0 |
| car18 | red | middle left | color | middle left | **HIT** | 0 | 171 |

**t=0 cell-hit 2/6, t=10s 0/6 → RQ-E22 = NO [prior-insufficient]** (< the 4/6 gate). No
[prior-wrong] suffix: it is defined on an accepted garbage lock on a Jetson leg, and the
offline gate stopped the campaign before any VLM call — which is what D4 buys. Diagnosis:
the two HITs are both **large** targets carried by the **colour** channel (car9 also
motion); the four misses split as (a) car3/car10/car14 — tiny red cars (~4–12 px wide at
320w) that displace sub-pixel over 0.5 s, so camera-comp cancels their motion (motion_inGT
0) and their red is too weak/small in-GT → prior None → harmless full-frame fallback; and
(b) car7 — the silver HSV mask FLOODS the bright roundabout (23,741 px), centroid drifts to
a confident-wrong "center" — the automatable version of E20's [hint-fragile] hallucination,
which the offline gate is the only defense against. The motion channel — the campaign's
headline idea — contributed to exactly one cell (car9). Prior latency ~3 ms (10× under the
<30 ms estimate) — **unbacked, flagged 2026-07-21T18:05Z (R-21):** the selfcheck that produced
~3 ms was never committed. The campaign's only raw file, `raw/phase0_prior_audit.txt`, carries the
cell-hit table and the per-stage mask-pixel counts but **no timing line at all**, so neither the
~3 ms nor the "10× under estimate" framing resolves to an artifact; the same applies to the
"~4–12 px wide at 320w" target-size figure above, which exists only as a README annotation. What
*is* fully backed is the number that decided the campaign — the 2/6 t=0 and 0/6 t=10 s cell-hit
rates, verified cell-for-cell against that file — so the NO verdict is unaffected. Acquire not
measured (no Jetson leg). No matrix, no overlays; proof =
`proof/phase0_prior_stages.png` (mask-stage montage: car9 HIT, car3 tiny-miss, car7
silver-flood). Raw: `experiments/2026-07-04-cv-proposal-acquire/raw/phase0_prior_audit.txt`.

### 2026-07-04 — E23 tolerant-cell sizing ([`experiments/2026-07-04-tolerant-cells/`](../../experiments/2026-07-04-tolerant-cells/README.md))

UX coda to E20: replace E20's rigid `third+pad` crop with one overlapping half-width knob HW
(cells centered at {1/6,3/6,5/6}, span [c-HW,c+HW]; HW=0.2667 reproduces E20). Score against a
FUZZED operator (tau=0.10, worst-case plausible phrasing) to ask if bigger cells absorb casual
edge-fuzz without regressing E20's acquire win. Phase-0 offline sweep picks HW*; 13 on-device
legs (Jetson Q8_0, 15W + jetson_clocks) confirm only that size.

Phase-0 sweep (frame-0 GT, tau=0.10, worst-case containment / mean crop-area frac):

| HW | wc containment /6 | all-phrasing | mean area frac | note |
|---|---|---|---|---|
| 0.2667 | 2/6 | 11/19 | 0.364 | E20-equiv (too cagey, NOT [already-tolerant]) |
| 0.3200 | 5/6 | 17/19 | 0.492 | |
| **0.3800** | **6/6** | **19/19** | **0.660** | **HW\*** |
| 0.4400 | 6/6 | 19/19 | 0.745 | |
| 0.5000 | 6/6 | 19/19 | 0.789 | |

On-device at HW*=0.38, worst-case fuzzed hints, n=2 (PASS = genuine_lock AND cov>=0.50, best of 2):

| clip | true→fuzzed hint | E18 A best | E20 cell best | tol best | tol PASS? | acquire_s |
|---|---|---|---|---|---|---|
| car3 | bottom left→center | F/0.976 | F/0.982 | F/0.901 | FAIL | 3.93 |
| car7 | top center→top center | F/0.285 | F/0.997 | F/0.286 | FAIL | 2.67 |
| car9 | bottom center→middle left | F/0.993 | **P**/0.996 | F/0.988 | FAIL | 2.83 |
| car10 | center→top center | **P**/1.000 | **P**/1.000 | F/0.000 | FAIL | 2.67 |
| car14 | center→top left | F/0.903 | **P**/0.907 | **P**/0.916 | **PASS** | 2.10 |
| car18 | middle left→top center | F/0.711 | F/0.981 | F/0.987 | FAIL | 2.63 |

**tol PASS = 1/6 (only car14), E20 set {car9,car10,car14} kept 1/3 → RQ-E23 = NO (REGRESSIVE)
[containment-not-sufficient]**. mean scoped acquire_s = **2.80 s** (n=12, 2.10–3.93) vs E20 1.85
/ E18 **~4.48** on the same `acquire_s` definition (published as "E18 4.85", which is E18's
`t_lock`; corrected 2026-07-21T18:05Z, R-21, per the E20 note) — inside the <3.0 s budget, so
latency is NOT the binder. Regression guard: car10
BREACH (tol cov 0.000 vs E18-A 1.000). Phase-0 guaranteed 6/6 geometric containment at HW*, yet
containment did not yield a lock: (a) car10's enlarged worst-case "top center" crop still contains
the target but ALSO a second red car → VLM grounds the decoy (cov 0.000, 9–10 REGROUND gate
rejects = E20-style poisoned template); (b) car3/car9/car18 reach high coverage (0.90–0.99) but
`genuine_lock` FALSE — the ~2.8 s acquire lands after the arrival frame on moving targets, E18's
acquire-latency-vs-motion binder untouched by fuzz-tolerance. car14 is the lone survivor (E18-A
stale FALSE → tolerant cell locks, genuine, 2.10 s). Bigger tolerant cells re-import the two
problems E20's tight cell suppressed (distractors + moving-target staleness); operator
fuzz-tolerance and small distractor-free crops are in tension. Proof: `proof/cell_sweep.png`,
`proof/car10_E18_vs_E23tol_regression.mp4`, `proof/car9_E23tol_stale.mp4`,
`proof/car14_E23tol_survivor.mp4`. Raw: `experiments/2026-07-04-tolerant-cells/raw/`.
