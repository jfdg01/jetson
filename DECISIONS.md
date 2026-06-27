# DECISIONS — project-wide decision log

> Project-wide decision log. Per-experiment decisions also live in `results/<campaign>/README.md`.
> Compressed archive of original: `archive/DECISIONS.md`.

---

# Part III — Persistent tracking / object permanence (v3)

### 2026-06-27 — Floor the ROI re-anchor crop (`min_side=384`)

- **Chosen:** `ROI_MIN_CROP = 384` px floor in deploy re-anchor path; eval default stays `min_side=0` (no eval impact). Code: `grounding/roi.py` + `grounding/deploy/video.py`.
- **Why:** Shrinking box → smaller crop → fewer pixels → smaller box = unbounded feedback. Observed: box collapsed to 21 px → crop 86 px → 64 tokens → degenerate 0×21 px latch onto wrong car.
- **Alternatives rejected:** `upscale=True` for small crops (more vision tokens, defeats prefill saving); divergence-triggered full-frame re-acquire (needs threshold, deferred); per-step shrink cap (still collapses slowly).
- **Trade-off:** Receding target sits in fixed 384 px crop fed native → Part II resolution ceiling, but no longer drifts. `384` is hand-tuned for 1080-wide demo frames.

### 2026-06-26T09:00 — Add "Re-anchor speedup" demo tab (ROI vs full-frame, live on Orin)

- **Chosen:** Fourth tab (`/compare`) in `grounding/deploy/gui.py`; full-frame anchor vs ROI-crop re-anchor side-by-side on one uploaded image. Reuses `grounding/roi.py` as-is.
- **On-device validation:** ROI prefill **~1375 ms** vs full-frame 3042–4034 ms → **2.2–2.9× speedup**, boxes preserved/tightened. Confirms latency lever transfers to deployed Q8_0.
- **Trade-off:** Confirms latency only — quantified on-device IoU@0.25 stays as open follow-up.

### 2026-06-26T02:30 — Adopt ROI-crop re-anchor (M=2.0 @512): −2.7× prefill + +22.6 pp accuracy ★

- **Chosen:** While lock holds, feed VLM a square crop inflated by **M=2.0** upscaled to `out_res=512`. Cold/re-acquire stay full-frame (two-mode). No retraining. Code: `grounding/roi.py`.
- **Results (Orin Q8_0 15 W n=10 / HF bf16 RefDrone val n=439):**
  - Prefill: **1374 ms vs 3691 ms full-frame = 2.7× cheaper**
  - Accuracy: **85.2% vs 62.6% baseline = +22.6 pp**
  - Mechanism: full frame downscaled to 512 → 15.9%; tight crop upscaled to 512 = super-resolution on target
  - Drift robustness: flat 82–85% to 0.5·box offset; 74.3% at full-box offset — all above baseline
- **Alternatives rejected:** native crop size (no upscale → 39%); M=2.0 @384 (4.2× prefill, 82.5% — kept as tight-budget alt); M=3.0 (≈2 pp lower peak, better drift tolerance).
- **Trade-off:** Re-anchor only — crop can't re-find object that left ROI. Accuracy is HF bf16; latency is Q8_0 — HF↔Q8_0 gap ≈±3 pp, dwarfed by +20 pp headroom. On-device Q8_0 ROI accuracy confirm is the open follow-up.
- **Process note:** Shared `grounding/contract.py` edited mid-experiment (COORD_SCALE 1000→100 by terse experiment) → first RQ4 run got bogus 0.0%. Diagnosed, corrected. Never `git add -A` on shared working tree.

### 2026-06-26T04:30 — KEEP terse (bare ints @0–100 + EOS): replaces JSON deploy artifact ★

- **Chosen:** `runs/v2/phase3-terse100eos-1024` GGUF Q8_0 as deployed grounding artifact. Output: four bare space-separated ints (`28 44 36 59`).
- **Results vs old JSON (Orin Q8_0, 15 W):** IoU@0.25 **63.1% vs 62.6%** (+0.5 pp), parse **100%**, decode **12 tok vs 21 (−43%)**, decode **531 ms vs 967 (−45%)**, anchor wall **1372 ms vs 1807 (−24%)**.
- **Three pieces (none sufficient alone):** (1) 0–100 precision — digit-per-token; 0–100 keeps 100% of RefDrone-val boxes above IoU@0.25. (2) EOS supervision — without it, iter-2 collapsed to 5% parse (model rambled to token cap, never supervised to stop). (3) Bracketless falls out for free.
- **Trade-off:** No structural parser anchor — mitigated by exactly-4-ints guard + 100% measured parse. Old JSON GGUF kept on Jetson for rollback. Synthetic-frame timing OOD; always measure decode on real images.

### 2026-06-26T23:30 — Terse output: coord precision (0–100) not JSON syntax; + EOS fix

- **Chosen:** COORD_SCALE 1000→100, EOS appended to every supervised target. Supersedes iter-1.
- **Why iter-1 failed:** Qwen tokenizes digit-per-token — digit count dominates cost, not JSON syntax. Iter-1 reverted to bracketed prior → only −3 tokens, −6.7% wall. Real lever = fewer digits.
- **Why 0–100 safe:** 0% of RefDrone-val boxes drop below IoU@0.25 under 0–100 rounding.
- **Why iter-2 (0–100 bare, no EOS) collapsed:** Rambled to token cap (never supervised to stop). EOS fix is strictly more correct for all formats.

### 2026-06-25T15:00 — Replace opencv-python with opencv-contrib-python (CSRT)

- **Chosen:** `opencv-contrib-python==4.13.0.92` replaces `opencv-python` (strict superset, ships `TrackerCSRT_create`). Auto-selected in `video.py:_make_tracker()`.
- **Why:** User requested CSRT for Level-2 demo. Same version satisfies ultralytics requirement. `cv2` imports identically; torch+CUDA intact; mp4 decode OK. Verified: real end-to-end /track on Orin produced coherent CSRT GIF.
- **Trade-off:** `pip check` notes dist-name mismatch — cosmetic only (`cv2` fully present).

### 2026-06-25T13:00 — Demo rebuilt as 2-tab live gui.py; old static 4-tab page retired

- **Chosen:** `grounding/deploy/gui.py`: tab 1 = manual grounding (live Orin VLM), tab 2 = Level-2 tracking (3 short VisDrone clips as mp4). Heavy GIFs (~40 MB) deleted; mp4 ~0.6 MB each.
- **Why:** User's ask — keep only manual VLM test + Level-2. Permanence/closed-loop panels dropped ("for now I only need …") — still documented in `results/` and GIFs in git history.
- **Trade-off:** Tab 1 needs `ssh jetson` live; tab 2 does not.

### 2026-06-25T12:30 — Level-2 tracker = MIL (built-in); CSRT deferred

- **Chosen:** `cv2.TrackerMIL` (only tracker in installed headless OpenCV 4.13). `_make_tracker()` auto-upgrades to CSRT if present.
- **Why:** Ladder discipline — use what's installed. Adding contrib touches the painful pinned lockfile. First job: validate architecture cadence, not tracker quality.
- **Superseded by:** 2026-06-25T15:00 (CSRT installed).

### 2026-06-25T00:00 — Whole-system demo = static HTML folder, not live tool

- **Chosen:** Static `results/2026-06-25-system-demo/index.html` + 3 GIFs, opened from `file://`. Stage-4 closed-loop added via `experiments/sitl/closedloop_viz.py` (`on_frame` hook on `run_t3.run_loop`, no new control code).
- **Why:** User explicit: *"static so I can simply show it."* No `ssh jetson` needed mid-talk. Pre-rendered anchor GIF = 3 genuine VLM passes. Self-check asserts re-ID coverage > baseline and ≥ 80%.
- **Trade-off:** No live "type-a-phrase" interactivity (live GUI remains separate). Demo shows three honest stages with a stated seam, never a faked end-to-end.

### 2026-06-24T18:40 — T4 PASS: on-Orin timing within T0 budget ★

- **Results:** Fast tier **0.143 ms median / 0.291 ms p99** on aarch64 @ 15 W = **99.7% of 20 Hz budget free** (~350× headroom). Real VLM anchor: **2264 ms / 0.44 Hz, −0.03% drift vs T0a, 100% bbox parse**. Anchor period 2.26 s > 1.5 s coast → event-triggered re-acq confirmed. `deploys_within_t0_budget = True`.
- **Scope:** Timing feasibility via real deployed artifacts, not a physical flight. **Closes Part III (T0–T4 all PASS).**

### 2026-06-24T12:00 — T3 PASS: closed-loop A/B ★

- **Setup:** New runner `experiments/run_t3.py` (reuses oracle_bbox + bytetrack + cascade_pid + offboard + T2 `_observe`). Distractor crosses + briefly occludes target at t=29–31 s, then veers away. One fresh flight per policy (shared flight gives 2.8% re-ID vs 71.5% on fresh takeoff — start conditions matter).
- **Results:** Phase-C ≈ 0% → re-ID **97.6% / 71.5%** (kinematic/live SITL) true-target coverage vs memoryless **49.2% / 53.7%**. Live margin < kinematic due to PID-lag/inertia; direction + mechanism hold.
- **SITL gotchas:** GUIDED before takeoff; `--uartA=tcp:5760` (lockstep clock); drain `LOCAL_POSITION_NED` to freshest; hard-reap arducopter between flights; run foreground.

### 2026-06-24T00:00 — T2 PASS: appearance-memory re-ID with SNR/range knob ★

- **Chosen:** Stored appearance descriptor behind refuse-to-lock gate (`experiments/sitl/reid_policy.py`). Scalar appearance model; observation noise scales with crop size → `snr` knob = separability-vs-range frontier.
- **Results (snr ≳ 1):** identity purity 0.725→1.000, ID switches 1→0, failed re-acq 1→0, coverage 0.575→0.695, following error 67.7→0.13 px. Below knee: degrades to baseline.
- **Trade-off:** Win conditional on separability. Scalar+noise isolates mechanism from encoder — RGB rendering and real embeddings deferred to T3/T4.

### 2026-06-18T15:30 — T1 PASS: temporal contract + renderer-free clip set ★

- **Chosen:** §6 metrics locked in `contract.py`. Renderer-free clips: NED trajectory→pixel-GT via `oracle_bbox.project_object`, scored by memoryless-ByteTrack baseline. Gazebo rendering deferred to T2.
- **Results:** Control clip purity 1.0; 4-stressor clip purity 0.725 / 1 ID-switch / coverage 0.575. Suite discriminates and quantifies constraint #2 as explicit T2 target.

### 2026-06-18T13:30 — T0 PASS: anchor spine = Qwen2-VL-2B Q8_0 @512; two-tier architecture confirmed ★

- **Locked:** Anchor = Qwen2-VL-2B Q8_0 @512 long-edge, **0.44 Hz / 2.27 s/anchor** on Orin (15 W). 768/1024 dropped (640×480 SITL camera = no upscale → pure latency cost). Gemma 4 dropped (E2B/E4B 0.34–0.49 Hz, slower).
- **Budget split:**
  - Inter-anchor tracking: comfortable — target motion ≤ 27.7 px vs 110–222 px box; tracker 0.051 ms (~1000× headroom)
  - Recovery-after-loss: tight — anchor period 2.27 s > coast horizon 1.5 s → event-triggered re-acq mandatory
- **Architecture not optional:** Timer-only periodic re-anchor rejected (anchor arrives 0.8 s after track dropped). The two-tier + event-triggered re-acq is forced by the numbers.
- **Caveat:** `jetson_clocks` not confirmed engaged → conservative default-15 W numbers; clock-locked can only be faster.

### 2026-06-18 — Open Part III on branch `v3/object-permanence`

- **Chosen:** Persistent single-object tracking under language conditioning. Reuse Part-I SITL stack + Part-II Qwen2-VL-2B Q8_0 anchor. Pre-register constraints + gated plan T0–T4 in `results/2026-06-18-part3-charter/README.md` before any code or GPU.
- **Two binding constraints:** #1 detection-cadence vs target-dynamics budget; #2 identity-through-absence (object permanence). Forced architecture: sparse VLM anchor + 20 Hz fast tracker.
- **Why charter-first:** Phase C proved the naive loop fails; pre-register before spending GPU — same discipline as v2.

---

# Part II — Principled rebuild (v2)

### 2026-06-18T01:30 — Phase 4 PASS: Q8_0 as deployment artifact; Part-I fidelity gap eliminated ★

- **Results (Orin Q8_0, 15 W, n=439 RefDrone val):** HF 59.5% → F16 **62.2%** (−2.7 pp runtime gap) → Q8_0 **62.6%** (−0.5 pp quant gap). Both clear the 57.5% fidelity floor. Q8_0 chosen over F16: 1.65 vs 3.09 GB at indistinguishable accuracy.
- **Significance:** SmolVLM/Idefics3 had −23 pp runtime + −7 pp quant. Qwen2-VL = −2.7 pp. Phase-0 spine selection eliminated the binding constraint. **Phases 0–4 all green.**

### 2026-06-18T01:15 — Phase 4 gate runs on the Jetson, not local CPU

- **Why:** Jetson is the deployment target; CUDA = seconds/sample vs CPU-hours; same pinned llama.cpp commit. Trusting HF number without on-device eval is exactly the Part-I mistake (−23 pp gap invisible until measured on real backend).

### 2026-06-18T01:00 — Jetson 8 GB OOM fix: `-np 1 --cache-ram 0 --no-cache-idle-slots`

- **Why:** Default `--cache-ram 8192 MiB` on unified 8 GB collides with model weights + KV + CUDA context. F16 eval crashed at sample 64/439 (server SIGKILL). Fix: stable ~5.8 GB RSS, ~1.3 GB headroom. Single-stream eval needs no multi-slot or prompt caching.

### 2026-06-18T00:55 — mmproj reuse: regenerate from merged checkpoint (bit-equivalent to base)

- Vision frozen in Phase-3 → mmproj tensors unchanged from base. Confirmed by identical byte size (1334666400 B). Regenerated for self-contained provenance; one mmproj serves base and fine-tune.

### 2026-06-18T00:50 — Jetson power: 15 W only (no 25 W MAXN_SUPER on this unit)

- `nvpmodel -q` on device lists only modes 0 = 15 W (max) and 1 = 7 W. CLAUDE.md mention of 25 W MAXN_SUPER does not apply to this board/firmware. All Phase-4 evals at mode 0 + `jetson_clocks` locked.

### 2026-06-18T00:45 — Auto-continuation: OS crontab (not harness CronCreate)

- **Chosen:** `scripts/auto_continue.sh` every 15 min by user crontab. Guard ladder: STOP sentinel → DONE sentinel → `flock` (no concurrent runs) → `pgrep -x claude` (defer to live session) → `timeout 3h`. Headless `claude -p --dangerously-skip-permissions`; never pushes; `.auto-continue/BLOCKED.md` for human-needed items.
- **Why CronCreate rejected:** `durable:true` not honored — schedule died with session on token exhaustion.
- **Trade-off:** ≤15 min resume latency. Unattended headless agent mitigated by kill switch, DONE auto-stop, repo-scoped `--add-dir`.

### 2026-06-18T00:30 — Phase 3 PASS: Qwen2-VL-2B LoRA on RefDrone well-posed ★

- **Config:** LoRA r16/α32/dropout0.05 on LLM attn+MLP (vision frozen, 18.5 M params = 0.83%), lr 2e-4, 3 epochs, batch 2×grad_accum 8, bf16, seed 42, `max_side=1024`, RefDrone well-posed (4101 train / 439 val).
- **Results:** In-loop val epoch1/2/3 = 63.0 / 65.0 / 65.0%. **Authoritative full-val n=439 = 59.5% IoU@0.25, parse 100%, mean_iou 0.451, center_std 215.2** (vs Phase-2 base-1024: 30.3%).
- **Reserved levers not used** (gate cleared at epoch 1): `largest_box_aug`, `max_side=1280`, RefCOCO warm-start via `init_from`.
- **Significance:** Part-I 19.5% narrow miss → v2 59.5%. Gain decomposes into two independently measured levers: resolution (4.1%→30.3% zero-shot) × fine-tune (30.3%→59.5%).

### 2026-06-17T20:00 — Phase 2: `max_side=1024` as input long-edge ★

- **Resolution ladder (base Qwen2-VL-2B, n=439, no training):**

| Resolution | IoU@0.25 | Parse | center_std |
|-----------|----------|-------|------------|
| 512 | 4.1% | 100% | 129.1 |
| 768 | 10.7% | 100% | 157.9 |
| **1024** | **30.3%** | 91.8% | 192.0 |
| 1280 | 38.7% | 92.0% | 196.1 |

- **Chosen:** 1024 — largest marginal jump (768→1024 = +19.6 pp), captures ~78% of 1280 ceiling at ~35% fewer visual tokens.
- **1280 not chosen:** +8.4 pp but ~1.56× visual tokens; past the elbow; kept as explicit Phase-3 lever.

### 2026-06-17T18:00 — Phase 1: one-box well-posed filter; budget 4101/439 ★

- **Audit results (CPU-only, no GPU):** RefDrone train mean 3.80 boxes/caption, **33.2% well-posed → 4101 train / 439 val**. Aerial object @512: **median ≈16 px, p25 6–10 px** vs RefCOCO control median 172 px.
- **Gate:** fails on raw corpus (0.332), passes on filtered subset (1.000). Confirms ill-posed target as Stage-2 root cause.
- **Significance:** Object-size measurement establishes resolution as dominant downstream lever.

### 2026-06-17T16:30 — Phase 0c.2: select Qwen2-VL-2B as v2 spine ★

- **Probe results (n=100, seed-42, RefCOCO val, HF bf16 greedy):**

| Model | IoU@0.25 | Parse | center_std | HF→F16 gap |
|-------|----------|-------|------------|------------|
| **Qwen2-VL-2B** | **15.0%** | **24%** | **162.1 (healthy)** | **−2 pp** |
| SmolVLM-500M | 0.0% | 9% | 61.3 (collapsed) | −16 pp |

- **Chosen:** Qwen2-VL-2B — grounding-native (real zero-shot floor), deployment fidelity 8× better, native dynamic resolution attacks binding constraint #2.

### 2026-06-17T16:00 — Phase 0c.1: disqualify PaliGemma 2 + Florence-2 before download

- **Method:** Deployment-backwards filter — grep `paligemma|florence` in `clip.cpp` at `57fe1f0` → 0 hits = zero projector support. Disqualified at zero cost (no download).
- **Survivors:** SmolVLM-500M (IDEFICS3) + Qwen2-VL-2B (QWEN2VL, `conversion/qwenvl.py`).

### 2026-06-17T14:30 — Phase 0b: GGUF fidelity gap on local CPU llama.cpp

- **Setup:** CPU-only llama.cpp at pinned `57fe1f0`; mmproj scp'd from Jetson. Greedy decode (determinism > reproducing Part-I exact magnitude). `eval/parity.py` composes three committed manifests.
- **Results:** HF 85.0% → F16 **69.0%** (runtime **−16.0 pp**) → Q8_0 **67.0%** (quant −2.0 pp). Runtime ≫ quant confirmed.

### 2026-06-17T12:30 — RefCOCO loader in Phase 0 (read-only)

- `grounding/data/refcoco.py` read-only during Phase 0. Lifts exact subset construction from Part-I `run_stage3_finetune.RefCOCODataset` so n=100 seed-42 subset is identical → 85.0% ≈ 82.5% comparison valid. Phase-1 audit stats added on top.

### 2026-06-17T12:00 — v2 operational toolchain

- **(a) deps:** `uv` + `requirements-ft.lock.txt` frozen from live `.venv-ft` (not re-resolved — avoids bumping the validated cu124 stack).
- **(b) experiment tracking:** `grounding/manifest.py` — per-run `manifest.json` + `run-card.md`: git SHA, pinned llama.cpp commit, lockfile sha256, dataset sha256, full config.
- **(c) testing:** `pytest` 9.1.0 in `requirements-dev.txt`; 22 tests locking prompt byte-string, parser, IoU/center_std maths.
- **(d) llama.cpp pinned:** `57fe1f07c3b6a1de3f4fff19098e2056a85275b7`.
- **(e) Makefile:** `test/sync/dev/lock/env-ft`.
- **Why:** Cross-backend comparability is the binding constraint. Pytest turns "five copies silently diverged" (Part-I failure) into a CI-style guarantee.

### 2026-06-17T00:00 — Principled rebuild: branch `v2/principled-rebuild`, shared contract, fidelity-before-GPU

- **Chosen:** (a) Consolidated Part I onto `main`, branched `v2/principled-rebuild`. (b) Archive not delete: legacy trainers/exporters → `experiments/legacy/`. (c) Importable `grounding/` package; `contract.py` as single source of truth. (d) Phase arc 0–4.
- **Root causes addressed:** (1) −23 pp runtime + −7 pp quant (Idefics3 preprocessing) discovered after training → Phase-0 fidelity gate before GPU. (2) Tiny-object 512 resolution ceiling → Phase-2 as explicit pre-registered variable.

---

# Part I — Exploratory (device campaigns + grounding Stages 1–4)

### 2026-06-17T00:00 — Stage 4: NARROW MISS (19.5% vs ≥20% gate)

- **Result:** Well-posed RefDrone curriculum from ft3. Parse 100%, center_std 211.5 (healthy). IoU 12.5→16.0→19.5% across epochs, still rising at LR→0. Gate miss = **−0.5 pp**. ~2.7 h GPU on RTX 3090.
- **Root causes eliminated:** Stage-2 ill-posed target + Stage-3 domain gap — both fixed. Miss attributed to data budget (4101) / capacity limit, not a failure mode.
- **Key finding:** Motivates v2 — resolution ceiling (16 px aerial objects @512) is the remaining lever.

### 2026-06-16T10:40 — Stage 3: re-diagnose Stage 2 as ill-posed target, switch to RefCOCO

- **Re-diagnosis:** Two stacked causes: (1, dominant) one-caption→many-boxes = ill-posed (marginal-mean box is correct loss-minimiser); (2) tiny-object pixel regression through frozen encoder.
- **Fixes:** Dataset → RefCOCO (many-captions→one-box, well-posed, large objects). Coords → normalized 0–1000 int bins. LoRA → attn+MLP (was attn-only). `center_std` collapse sentinel added.
- **Trade-off:** RefCOCO is ground-level → domain gap to aerial (measured as RQ-S3.4). Proves grounding skill learnable, not that it transfers.

### 2026-06-16T10:00 — Stage 2 FAIL: text-only LoRA insufficient for spatial grounding

- **Result:** IoU@0.25 = 1%, gate ≥20% = FAIL. Parse 100% (pipeline correct; failure is spatial). Frozen SigLIP → no gradient path for localization → model converges to marginal-mean bbox.
- **Decision:** Accept negative result. No further epochs (more training won't fix root cause). Thesis content: why naive text-only LoRA fails on aerial grounding.

### 2026-06-15T22:00 — Stage 2 fine-tuning: LoRA on SmolVLM-500M with RefDrone MDETR JSON

- **Config:** LoRA r=16/α=32, `q/k/v/o_proj` only (vision frozen), lr 1e-4, effective batch 16. RefDrone MDETR JSON loaded directly (HF streaming interface fails). AutoProcessor instead of SmolVLMProcessor (fails in transformers 5.12 with video_processor_type error). Trainable: 4.16 M params (0.81%).
- **Export:** `peft.PeftModel.merge_and_unload()` → HF → scp to Jetson → `convert_hf_to_gguf.py --outtype q8_0` at `57fe1f0`.

### 2026-06-15T18:30 — Phase C Gazebo: decoupled render-only (not ArduPilot-Gazebo coupling)

- **Chosen:** Headless `gz sim -s -r`; Python moves poses via `/world/phase_c/set_pose` gz transport. SITL and Gazebo share no physics coupling. Reuses 100% of Phase B SITL pipeline unchanged.
- **Why coupling rejected:** Requires patching SDF + FDMCC bridge; ardupilot_gazebo Iris has no built-in camera.
- **gz bindings confirmed:** `/usr/lib/python3/dist-packages/gz/` (Harmonic 8.13.0, `transport13` + `msgs10`).

### 2026-06-15T17:30 — Phase C: async slot architecture + track-loss definition

- **Chosen:** `LatestDetectionSlot` (lock-protected, monotonic timestamp guard). Track-loss = empty ByteTracker returns only (not ID changes — ID changes would equal injection count at 1 Hz). Forced re-seed gap at t=30 s (`LOST_TIMEOUT_S + 1 = 4 s`) validates re-seed < 2 s reproducibly.
- **Live VLM path + Gazebo frame-grabber:** stubs (`NotImplementedError`); `--inject-oracle` bypasses both for Branch-1 gate.

### 2026-06-15T13:00 — Toy NL-command demo: honest zero-shot baseline, aerial imagery only

- **Chosen:** `experiments/demo_nlcommand.py`. Three verbs: FOLLOW/ZOOM → VLM grounding; TURN → heuristic yaw. Tested on VisDrone nadir frames. Grounding failures reported honestly. Latency: 534 ms / 2046 ms (single calls, not campaign-grade).
- **Why:** Establishes zero-shot baseline before fine-tuning. TURN demonstrates pipeline working; FOLLOW/ZOOM demonstrate VLM path firing with honest negative result.

### 2026-06-15T09:30 — Phase B: programmatic target + gimbal-stabilized oracle camera

- **Chosen:** Target = 0.25 m/s constant-velocity in copter's NED frame (not ArduRover telemetry — cross-instance NED origin mismatch ~584 m D). Camera = gimbal-stabilized nadir (roll/pitch=0, real yaw retained).
- **Why body-fixed failed:** ArduPilot nose-down accel pitch (~13°) → 130 px apparent target shift → positive feedback → vx pinned at 3 m/s, 246 px mean error.
- **Result:** 19.99 Hz, 12.9 px mean error, 100% oracle coverage, 0 track losses × 3×60 s. **Phase B PASS.**

### 2026-06-15 — Phase B toolchain: ArduPilot headless + x86_64; no Gazebo

- **Chosen:** ArduCopter SITL headless on local x86_64. Oracle bboxes from geometric projection (pinhole model). ByteTrack minimal in-repo (~250 lines, numpy+scipy only). Gazebo deferred to Phase C only if needed.
- **Why not Jetson SITL:** Conflates measurement device with stimulus; RAM/CPU contention.

### 2026-06-15T08:10 — Phase A gate: SmolVLM-500M Q8_0 selected for Phase C fine-tuning

- **Result:** Both models fail IoU@0.25 < 30% (both 0%). S1 (256M): 3.58 Hz, parse 0%. S2 (500M): 1.20 Hz, parse 4%, latent coordinate structure in responses. S2 chosen: structure to anchor fine-tuning on. Fits RAM (2734 MB, no swap).

### 2026-06-14 — PaliGemma excluded from Stage 1

- PaliGemma 2 GGUF support (PR #7553) unmerged/draft as of 2026-06-14. Only PaliGemma v1 GGUF published. Custom build would break controlled-variable invariant on pinned `57fe1f0`.

### 2026-06-14 — RefDrone dataset: correct repo `sunzc-sunny/RefDrone`; images via VisDrone 2019-DET

- `sun-langwei/RefDrone` returns HTTP 401. Correct ID confirmed from GitHub project page. RefDrone annotations do NOT bundle images — VisDrone 2019-DET must be downloaded separately.

### 2026-06-14T20:00 — Gemma-4 E2B/E4B: disable reasoning (`--reasoning off`)

- Default thinking mode consumed all 50 `max_tokens` in `reasoning_content` → empty `content`. At 0.5–2 Hz drone control, thinking latency is unacceptable. Initial invalid runs retained as documented negative result.

### 2026-06-14T22:00 — Install ffmpeg on Jetson (permanent VLM dependency)

- `sudo apt install -y ffmpeg`. `llama-server` uses `ffprobe` to detect image format from base64. Without it: "Failed to load image or audio file" on every request. ~50 MB.

### 2026-06-14T21:00 — VLM instrument: llama-server (not llama-bench or llama-mtmd-cli)

- `llama-bench` has no `--image` flag. `llama-mtmd-cli` is single-shot (each process pays CUDA graph compilation ~180 ms, can't measure warm state). `llama-server` keeps model + CUDA graphs loaded; `cache_prompt: false` per-frame. `timings.prompt_ms` includes CLIP encode (verified: `prompt_ms + predicted_ms ≈ wall-clock`).

### 2026-06-14T21:00 — Architecture fork (end-to-end vs decomposed) deferred to empirical result

- Decision criterion: if best VLM warm per_frame_ms ≤ 2000 ms AND grounding correct → end-to-end viable; otherwise → decomposed. SmolVLM-256M cold smoke test (~744 ms) is NOT a warm measurement.

### 2026-06-14T19:30 — Fix footprint parser: last-wins for compute, zero-filter for KV

- llama.cpp runs probe pass (compute=real, KV=0) + real allocation (all real). Original parser double-counted compute. `--verbose` added 2.3 GB debug output per model, flooded SSH, left stray process consuming 3.3 GB RAM.

### 2026-06-14T18:30 — Correct swap + footprint metrics post-hoc; no re-sweep

- **Swap:** `any(swap > 0)` → `swap_growth_mb > 50 MB` (pre-existing ~300 MB baseline mis-flagged). **Footprint:** tegrastats under-counts mmap'd weights → re-measured via `--no-mmap --verbose` load report. Throughput/power/TTFT numbers unchanged.

### 2026-06-14T17:00 — Use pinned `57fe1f0` for Gemma 4; no rebuild

- `GEMMA4` + `GEMMA4_ASSISTANT` present in `src/llama-arch.cpp` at `57fe1f0`. Confirmed by source inspection before download.

### 2026-06-14T13:30 — TTFT: llama-completion (not llama-cli); stdin from /dev/null

- `llama-cli` dropped `-no-cnv` → interactive loop. `pkill -f tegrastats` killed SSH connection → use `pkill tegrastats` (name-only). `llama-completion` uses timestamp prefix + comma decimal separators (European locale) — `parsers.py` updated.

### 2026-06-14T13:30 — Run sweep via run_campaign.py (not isolated sessions)

- Orchestrator already debugged and covers full protocol. Single device = no parallelism benefit from fan-out. Supersedes the isolated-session methodology designed 2026-06-13.

### 2026-06-13T15:05 — Isolated-session methodology (designed; superseded by orchestrator for this sweep)

- **Design:** Each unit run by fresh `claude -p` session from `CLAUDE.md` + self-contained run card. Guard: `pgrep -x claude` defers to live session; `flock` no concurrent runs; STOP/DONE sentinels. Repo filesystem as message bus.
- **Remains valid for:** campaigns needing per-unit qualitative judgment (not just deterministic orchestration).

### 2026-06-13T14:42 — Sudo on Jetson: scoped NOPASSWD allowlist

- `/etc/sudoers.d/10-jetson-bench`: NOPASSWD for `/usr/sbin/nvpmodel`, `/usr/bin/jetson_clocks`, `/usr/bin/tegrastats` only. `0440 root:root`. Expand via `visudo -cf`. History: blanket NOPASSWD → reverted on Tailscale enrollment → scoped allowlist restored.

### 2026-06-13T14:30 — Remote access via Tailscale

- Enrolled in existing tailnet. Transport-only (not Tailscale-SSH). Jetson: `100.127.45.66` (alias `jetson-remote`); LAN `192.168.1.136` retained (alias `jetson`). `--accept-dns=false` (broken MagicDNS). Disable key expiry in Tailscale admin console.

### 2026-06-13T14:17 — Upper bound = 15 W locked clocks; 25 W MAXN_SUPER not attempted

- Profile `p3767-0003` = 15 W / 7 W only. Unlocking Super requires bootloader update — unacceptable risk without physical access for recovery.

### 2026-06-13T13:50 — Build llama.cpp natively on Orin

- x86_64 binary can't run on ARM Orin. Cross-compile needs aarch64 toolchain + CUDA target libs (fragile). Native build ~15–25 min, one-time cost. Pinned `57fe1f0`.

### 2026-06-13T13:45 — Runtime: llama.cpp (CUDA), not Ollama

- `llama-bench` gives separated prefill (pp) vs decode (tg) throughput = reproducible thesis numbers. Ollama exposes only coarser eval rate + overhead.

### 2026-06-13T13:40 — Headline model: Llama-3.2-3B-Instruct Q4_K_M

- Best balance of capability + fits 8 GB with KV headroom. ~9 more models follow to cover size/quant spectrum.
