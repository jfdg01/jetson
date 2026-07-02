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
| baseline Qwen2-VL-2B (deployed) | — | WF@1024 / ROI M=2.0@512 | 100% | 63.1% / 85.2% | 0.477 / — | 4400 / ≈2000 ms | **incumbent, kept** |
| A InternVL3-2B | 4e-4 | WF@1024 (HF, n=200) | 100% | 48.5% | 0.298 | N/A — GGUF export blocked @`57fe1f0` | eliminated |
| B Qwen2.5-VL-3B | 2e-4 | WF@1024 / ROI M=2.0@512 (Jetson Q8_0, n=439) | 100% | 53.1% / **33.0% (ROI collapse)** | 0.399 / 0.170 | 5990 / 2817 ms | eliminated |
| C PaliGemma2-3B@448 | 2e-4 | WF@448 (HF, n=200) | 100% | 56.0% | 0.391 | not measured (moot) | eliminated |
| E SmolVLM2-500M | 1e-4 (leg 1 only) | WF@512 (in-loop val) | 100% | **5.5% (capacity collapse)** | 0.038 | not deployed | eliminated |
| D Florence-2-large | — | — | — | cancelled un-run | — | — | cancelled |

### 2026-07-02 — Temporal acquire-carry, Phase 0 zero-shot ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md))

Zero-shot SAM2.1-hiera-tiny (`sam2==1.1.0`, bf16 autocast, RTX 3090) memory-carry from a single
first-frame GT box prompt; AerialMind 93 seqs × 2 tracks (longest + longest-with-gap), ≤300-frame
window, scored on labeled frames only. First launch invalidated at 42/93 by a GT decode bug
(labels are top-left-encoded, not JDE center — see campaign README Findings); rerun clean.

| Run | tracks | mean IoU | IoU@0.25 | IoU@0.5 | ID-consistency | occ-recovery | pred-absent | FPS (3090) | wall |
|---|---|---|---|---|---|---|---|---|---|
| phase0-zeroshot-carry | 186 | 0.602 | **0.849** | 0.750 | **0.891** | 0.329 (70 gaps) | 3.5% | 14.4 | 58.4 min |

Demo (real Jetson Q8_0 acquire, M0205): occlusion clip — acquire IoU 0.947 @4.54 s, carry 252 f
through a 40-frame GT gap, mean IoU 0.886; retarget clip — mid-video caption switch truck→"the
black car", retarget IoU 0.721 @4.1 s, mean IoU 0.887. Committed `ab6d6d7`.

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
≥0.99). Integrated trials: ArduCopter SITL + synthetic nadir renderer, real Jetson Q8_0 VLM
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

| Run | size | FPS solo | FPS co-res (VLM Q8_0) | p50 ms | RAM | IoU@0.25 / mean (M0205) | verdict |
|---|---|---|---|---|---|---|---|
| eager baseline | 768 | 4.89 | 4.89 | 204.6 | 612 MB | 1.000 / 0.821 | reference |
| TRT fp16 encoder | 768 | 6.15 | **6.15** | 162.4 | 4980/7607 MB (w/ VLM) | **1.000 / 0.826** | **PASS (≥5)** |

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
real carry (local 3090 SAM2 @1024, local-VLM acquire path), one trial per speed. Gate = in-FOV ≥
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

Same rig as E2 (local-VLM path, 3090 carry @1024, gate = in-FOV ≥ 0.90 AND recovered). Two fixes
vs E2: **Fix B** (always-on) inits carry on the acquire *submit* frame + replays the buffered gap;
**Fix A** a trust-aware loss gate demoting an untrusted carry box to `None` so the existing
REGROUND machinery fires (flag `--loss-gate {none,score,motion}`).

**Stage 1 — gate selection @ 0.5 m/s (the E2 confident-latch speed):**

| gate | in-FOV | n_regrounds | relock (s) | recovered | verdict |
|---|---|---|---|---|---|
| none | 1.000 | 1 | 9.43 | true | **PASS** — control; Fix B alone recovered 0.5 (E2 was FAIL 0.484) |
| score | 1.000 | 1 | — | false | **FAIL** — over-fires, relock never confirmed |
| motion | 1.000 | 1 | 9.32 | true | **PASS** — behaves as `none`, gate inert |

`score` diagnostic: SAM2 `object_score_logits` separates occlusion cleanly (occluded mean −3.23 vs
clear +8.61) but the clear tail dips to −3.94, so at tau=0 it demotes good boxes on clean-track
noise → relock never confirmed. Signal real, threshold over-fires. Chosen gate (mechanical rule):
**motion** — but note the loss gate was **not the operative fix at 0.5**; Fix B was (`none` passes).

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

Config: `local-VLM, 3090 carry @1024, loss-gate motion, dr pursuit, 75 s`. Pursuit DR replaces
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

Config: `local-VLM, 3090 carry @1024, loss-gate motion, dr pursuit, acquire-hold motion, 75 s`.
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
