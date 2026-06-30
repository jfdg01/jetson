# DECISIONS — Part III (v3 Object Permanence)

> Decision log for persistent tracking / object permanence (v3). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `results/<campaign>/README.md`. ★ = headline decision.
> **Newest at top** — prepend each new decision above the most recent one.

---

### 2026-06-30 — ROI lever stays LANCZOS; learned SR (Swin2SR) rejected

- Swin2SR x4 loses to free bicubic/lanczos on grounding IoU (78.6% vs 80.9% IoU@0.25) and costs ~1.3 s/crop — most of the anchor budget. Full writeup: [`results/2026-06-30-roi-sr-upscale/`](../../results/2026-06-30-roi-sr-upscale/README.md).

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
</content>
