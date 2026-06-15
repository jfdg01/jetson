# DECISIONS — project-wide decision log

Cross-cutting decisions and their rationale, most recent first. Campaign-specific
decisions live in the relevant `results/*.md`. Format defined in `CLAUDE.md`.

---

### 2026-06-15T18:30 — Phase C Gazebo integration: decoupled render-only approach + gz transport Python bindings

- **Decision:** Implement the Phase C Gazebo rendering layer as a **decoupled, render-only** gz sim process. SITL runs with `--model quad` (same built-in physics as Phase B); Gazebo runs headless (`gz sim -s -r`). Python moves `downward_cam` and `target_rover` model poses every control frame via the `/world/phase_c/set_pose` gz transport service. SITL and Gazebo share no physics coupling.
- **Alternatives considered:** (a) Full ArduPilot-Gazebo coupling (`--model gazebo` + `libArduPilotPlugin.so`): SITL delegates physics to Gazebo, camera sensor built into the Iris model. Rejected: requires patching the ardupilot_gazebo world/model SDF to add a camera sensor, introduces complex FDMCC bridge handshake, and the ardupilot_gazebo Iris models have no built-in camera. (b) ROS 2 image bridge: gz→ROS→Python. Rejected: ROS overhead and extra dependency. (c) gz→socket bridge (custom C++ plugin): maintains render isolation but adds C++ build work.
- **Reasoning:** The decoupled approach reuses 100% of the Phase B SITL pipeline unchanged. All that changes is: (1) a headless gz sim process for rendering, (2) Python calls `_update_gz_pose()` to keep the camera and rover models in sync with SITL telemetry, (3) `_grab_gazebo_frame()` converts the gz transport `Image` callback (raw R8G8B8 bytes) to JPEG via Pillow. The gz Python transport bindings are confirmed available at `/usr/lib/python3/dist-packages/gz/` (Gazebo Harmonic 8.13.0, `transport13` + `msgs10`). The set_pose service uses a 50 ms timeout — well within the 50 ms control period at 20 Hz.
- **Tradeoff / cost accepted:** Camera pose is updated once per 20 Hz control frame (not continuously by the gz rendering thread). At 20 Hz copter motion is ≤0.05 m/frame, producing at most 1–2 px camera shift between pose updates at 10 m altitude — negligible for VLM grounding. The target rover NED position is programmatic, so the gz pose is the authoritative position (no physics drift).
- **Revisit when:** If per-frame pose calls at 20 Hz add measurable latency to the control loop (log loop_dt spikes > 10 ms in phase-c raw CSVs). Alternative: drop pose updates to 5 Hz in a background thread.

---

### 2026-06-15T17:30 — Phase C `run_phase_c.py`: async slot architecture, track-loss definition, re-seed test

- **Decision:** Build `experiments/run_phase_c.py` as a two-thread architecture: a 20 Hz control+track thread reading from a lock-protected `LatestDetectionSlot`, and a `~1 Hz` detection thread that writes either oracle injections (`--inject-oracle`) or live VLM calls (Gazebo frame → Jetson llama-server). Three specific design choices worth recording:
  1. **Track-loss events count empty-ByteTracker returns only** (not ID changes). With score=1.0 detections and the `_lost`-list re-detection pattern in ByteTrack, every 1 Hz injection creates a new track ID when the previous track has drifted to `_lost` after 30 frames (1.5 s). Counting ID changes would inflate the loss metric to equal the injection count. Pre-registered limitation (§3.4): "SmolVLM emits no confidence; score=1.0 for any parsed box; ByteTrack's low-score association unused."
  2. **Forced re-seed gap in run 3 of `--inject-oracle`**: injection pauses for `LOST_TIMEOUT_S + 1 = 4 s` at t=30 s, validates Branch-1 criterion 3 (re-seed < 2 s) reproducibly in a pre-registered run structure.
  3. **Gazebo frame-grabber left as `NotImplementedError` stub**: the exact gz transport topic name is not known until Gazebo Harmonic is installed. The stub raises a clear error with install instructions; `--inject-oracle` bypasses it entirely for the Branch-1 gate.
- **Alternatives considered:** (a) Import Gazebo Python bindings at module load time and mock them for `--inject-oracle` — rejected: couples the non-Gazebo code path to a not-yet-installed package. (b) Count ID changes as track-loss events (Phase B's definition) — rejected: produces misleading metric at 1 Hz VLM; honest to count only full-track-disappearance per the Phase C context. (c) Use `MAX_LOST_FRAMES = 60` in ByteTrack to match `LOST_TIMEOUT_S = 3.0 s` at 20 Hz — rejected: changing ByteTrack's constant without documenting it in the pre-registration would be an undocumented deviation; the 1.5 s drop is documented as a known difference.
- **Reasoning:** The `LatestDetectionSlot` stale-rejection (monotonic timestamp guard) was unit-tested for the read-returns-copy invariant, older-ts rejection, and same-ts rejection. The `xyxy_to_cxcywh` adapter was unit-tested for center, size, and degenerate (zero-size) boxes. The dry-run (`--inject-oracle --dry-run`) confirmed: Hz=20.31 ≥ 15, track-coverage=100%, coasting_max=19 ≥ 15, track-losses=0.
- **Tradeoff / cost accepted:** The live VLM path (`_vlm_grounding_thread`) and the Gazebo frame-grabber (`_grab_gazebo_frame`) are stubs — they raise `NotImplementedError` until Gazebo Harmonic is installed and the camera topic identified. The Branch-1 gate (`--inject-oracle`) is fully testable without Gazebo.
- **Revisit when:** Gazebo Harmonic is installed — implement `_grab_gazebo_frame()` against the real gz transport API (run `gz topic -l` to find the camera topic), then run Branch-1 in live mode to confirm the VLM path doesn't block the control thread.

### 2026-06-15T13:00 — Toy NL-command demo: scope, image source, and honest grounding claim

- **Decision:** Build `experiments/demo_nlcommand.py` as a lightweight orchestration
  layer over existing infrastructure (llama-server on Jetson, Phase A client helpers) with
  three command verbs (FOLLOW/ZOOM → VLM grounding; TURN → heuristic yaw with no VLM call).
  Tested on VisDrone nadir frames (the thesis target domain). Grounding failures reported
  honestly as the expected zero-shot result; not smoothed over or tested on easier imagery
  to manufacture a success.
- **Alternatives considered:**
  - (a) **Use non-aerial imagery** (street-level photo where SmolVLM might ground "white car")
    — rejected: the thesis target is aerial drone frames. Showing zero-shot success on a
    ground-level image would misrepresent the system's capability on the actual deployment
    domain.
  - (b) **Build as a full measurement campaign** with tegrastats, RESULTS.md device rows, and
    N-frame sweep — rejected: the demo's goal is pipeline validation and presentation, not a
    new benchmark. The latency numbers recorded in RESULTS.md (534 ms, 2046 ms) are real
    observations but not campaign-grade measurements (single calls, no spread).
  - (c) **Gate on VLM grounding working before writing the demo** — rejected: the pipeline
    mechanics (server lifecycle, async port-forward, command parsing, bbox parsing) are
    independent of grounding quality and are the deliverable. Grounding quality is a measured
    output, not a precondition.
- **Reasoning:** The toy demo serves two thesis purposes: (1) demonstrates the end-to-end
  pipeline concept for a committee/reader audience (TURN always works; FOLLOW/ZOOM show the
  VLM path firing); (2) records the honest zero-shot baseline that motivates Stage-2
  fine-tuning. Building it before the fine-tune exists is the correct sequence — it
  establishes what the zero-shot system does before fine-tuning changes it.
- **Tradeoff / cost accepted:** The demo is not visually impressive for FOLLOW/ZOOM on
  aerial imagery until Stage-2 fine-tuning is done. The honest outcome: TURN commands
  demonstrate the pipeline working; FOLLOW/ZOOM demonstrate the VLM path firing while
  being explicit that grounding fails zero-shot. This is documented in RESULTS.md and in
  `results/2026-06-15-toy-demo/README.md`.
- **Revisit when:** Stage-2 fine-tuned SmolVLM-500M GGUF is ready — re-run the demo
  with `--start-server` pointing at the fine-tuned weights; the rest of the pipeline is
  unchanged.

---

### 2026-06-15T09:30 — Phase B target: programmatic rover trajectory + gimbal-stabilized oracle camera

- **Decision:** Drive the Phase B target with a **programmatic** constant-velocity trajectory (0.25 m/s north, 0.5 m ahead) computed in the copter's own NED frame and anchored to the copter's captured (N,E) at each trial start, rather than reading the second SITL (ArduRover) instance's position telemetry. Pair this with a **gimbal-stabilized (nadir) oracle camera** — level roll/pitch fed into the projection, real yaw retained — modeling a 2-axis stabilized downward camera rather than an airframe-fixed one.
- **Alternatives considered:** (a) **ArduRover telemetry directly** — the two SITL instances don't share an NED origin (~584 m D discrepancy at CMAC home), so cross-instance position differencing is invalid without an uncalibratable frame offset. (b) **Body-fixed camera (real attitude into oracle)** — empirically diverged: ArduPilot's nose-down accel pitch (~13°) tilts a body-fixed camera, injecting `FOCAL_PX·tan(pitch) ≈ 130 px` of apparent target shift, far exceeding the true ~28 px offset and forming a positive-feedback loop (pixel error → vx → pitch → more apparent error → saturation; first live run hit 246 px mean, vx pinned at 3 m/s). (c) **Lower the P gain** to suppress pitch — treats the symptom, leaves the unstable mode in place.
- **Reasoning:** The programmatic trajectory sidesteps the cross-instance NED mismatch and makes runs self-consistent; anchoring to the copter's real (N,E) keeps the target in-frame from t=0 even as the copter drifts between runs. A gimbal-stabilized nadir camera is the standard tracking-UAV assumption and removes the attitude coupling at its source, touching only the oracle call site (not `oracle_bbox.py`). Yaw is kept because the body→NED velocity transform needs the true heading. With both in place: 19.99 Hz, 12.9 px mean error, 100% oracle coverage, 0 track losses across 3×60 s — **Phase B PASS**, threshold met honestly with no widening.
- **Tradeoff / cost accepted:** (1) The target is scripted, not a physics-simulated vehicle — Phase B validates the tracker→PID→MAVLink loop, not target dynamics. (2) The gimbal assumption means Phase B does not exercise attitude de-rotation; if Phase C's camera is **fixed-mount**, attitude compensation becomes a required, not-yet-validated pipeline step.
- **Revisit when:** Phase C uses a real/rendered **fixed-mount** camera (then add and validate attitude de-rotation) or needs a physics-driven target vehicle (then reconcile the two-instance NED frames or use a single combined sim).

Campaign-specific sub-decisions (honest pixel-error coverage gate, telemetry-drain bug fix, disabled yaw channel) are documented in `results/2026-06-14-stage1-baseline/phase-b-sitl.md` under `## Decisions`.

---

### 2026-06-15 — Phase B SITL toolchain: ArduPilot headless + local x86_64; no Gazebo for Phase B

- **Decision:** Use **ArduPilot SITL (ArduCopter/ArduRover, Copter-4.6.3, built 2026-06-15)** running headlessly on the **local x86_64 workstation (Ubuntu 24.04)**. No Gazebo for Phase B. Oracle bboxes are computed by geometric projection from SITL world-state telemetry, not from rendered video. pymavlink (offboard velocity setpoints) is the sole MAVLink interface. ByteTrack is implemented as a minimal in-repo Python module (~250 lines, numpy + scipy only). Gazebo Harmonic will be added for Phase C only if a real camera rendering is found necessary; the decision is deferred and documented as Phase C's first sub-task.
- **Alternatives considered:**
  - (a) **PX4 SITL**: Also mature and well-supported, but requires ROS2 for typical offboard workflows and has a heavier cmake build. CLAUDE.md specifies pymavlink directly; ArduPilot exposes the same offboard interface over raw MAVLink with less setup friction. PX4 is a valid alternative if ArduPilot SITL proves problematic, but there is no reason to prefer it here.
  - (b) **Gazebo Harmonic from the start**: Adds camera rendering and a physics-engine target vehicle but also adds ~1–2 hours of setup and a significant CPU draw during runs. Phase B only needs to validate that the MAVLink control loop achieves ≥1 Hz — no vision is in the loop yet. Oracle bbox from geometric projection is functionally equivalent for Phase B's success criterion.
  - (c) **Run SITL on the Jetson (aarch64)**: The Jetson has 153 GB free disk and 3.2 GB free RAM but only a 6-core Cortex-A78AE CPU. SITL + Gazebo + simultaneous VLM inference would exhaust RAM and compete heavily for CPU. aarch64 Gazebo pre-built packages are less mature. The Jetson is the *measurement device* for Phase C; running the simulation there as well conflates the measurement with the stimulus.
  - (d) **Pre-recorded video as camera feed (no SITL physics)**: Would validate VLM grounding (Phase A/C concern) but not the MAVLink offboard control loop — the drone's response to setpoints needs a dynamics model to close the loop. Ruled out for Phase B; acceptable as a supplementary offline probe in Phase C if needed.
- **Reasoning:** Phase B's sole job is to verify the tracker → PID → MAVLink loop works mechanically before the VLM is added. ArduPilot headless SITL on the local machine achieves this with the least external-dependency surface. A SITL vehicle responds to offboard velocity setpoints identically whether or not Gazebo is rendering it. The oracle bbox—computed from the SITL-reported world position of the target vehicle projected through a pinhole camera model—is functionally a perfect-perception upper bound, which is exactly what Phase B asks for. ArduCopter Copter is the controller mode; pymavlink sends `SET_POSITION_TARGET_LOCAL_NED` (type_mask: velocity + yaw_rate only). A second ArduRover SITL instance (port 5770) serves as the scripted ground vehicle at 2 m/s.
- **Tradeoff / cost accepted:** Without Gazebo, Phase B does not produce rendered camera frames — Phase C will need to revisit whether Gazebo is required or whether a pre-recorded aerial video over a similar scene can serve as the Phase C camera feed. This is the primary deferred cost. Also: headless oracle bbox bypasses any rendering/detection pipeline, so Phase B numbers represent an upper bound that VLM performance in Phase C will fall below by design.
- **Revisit when:** Phase C requires actual rendered camera frames (not just MAVLink position telemetry). If so, add Gazebo Harmonic with the `ardupilot_gazebo` plugin and log the Gazebo install as a new DECISIONS entry.

---

### 2026-06-15T08:10 — Phase A decision gate: S2 selected for Phase C fine-tuning

- **Decision:** Select SmolVLM-500M-Instruct Q8_0 (S2) as the fine-tuning target for Stage 2 (Phase C). The zero-shot baseline establishes that both SmolVLM models completely fail at drone grounding without fine-tuning.
- **Alternatives considered:** (a) S1 (SmolVLM-256M-Instruct Q8_0) — smaller, faster (3.58 Hz), but parse rate 0% with no bbox-structure in responses; (b) S2 (SmolVLM-500M-Instruct Q8_0) — slower (1.20 Hz), parse rate 4%, but generated bbox-like coordinate structures in most responses (using single-quoted Python dicts, failing JSON parser — not complete absence of grounding representation); (c) pursue prompt engineering before fine-tuning — ruled out because the binding constraint is zero localization signal, not output formatting.
- **Reasoning:** Both models fail the IoU@0.25 < 30% threshold (both 0%). Both also fail the parse-rate < 50% threshold (S1: 0%, S2: 4%). Under the pre-registered decision gate, fine-tuning is therefore load-bearing and Stage 2 is the thesis centerpiece. S2 is preferred over S1 because it demonstrated latent awareness of coordinate output structure in its raw responses — it generated `{'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}` and `{'bbox': [x,y,x2,y2]}` patterns consistently. S1 produced only free-text descriptions. S2's structure suggests the fine-tuning signal has something to anchor to. S2 also fits comfortably in RAM (2734 MB, no swap). The speed gap (1.20 Hz vs 3.58 Hz) is acceptable for evaluation runs and expected to narrow post-quantization if needed.
- **Tradeoff / cost accepted:** S2 runs more slowly at inference. At 1.20 Hz unquantized on the zero-shot probe, fine-tuned performance will depend on whether llama.cpp can export and run the fine-tuned weights at similar speed. The slower rate is within the thesis's 0.5–2 Hz target range for drone control.
- **Revisit when:** Phase C fine-tuning results show S2 fails to converge or occupies too much RAM in the fine-tuned form — then fall back to S1.

---

### 2026-06-14 — PaliGemma excluded from Stage 1; SmolVLM-only grounding path

- **Decision:** Remove PaliGemma (v1 and v2) from the Stage 1 grounding candidate list. Stage 1 Phase A will evaluate SmolVLM-256M Q8_0 and SmolVLM-500M Q8_0 only.
- **Alternatives considered:** (a) Use a custom llama.cpp build that includes PR #7553; (b) Proceed with SmolVLM-only path as pre-planned in the risk register.
- **Reasoning:** PaliGemma support in llama.cpp (PR #7553 by abetlen) is unmerged draft code as of 2026-06-14 — the maintainer deferred it pending a new vision API initiative. The controlled variable for this thesis is llama.cpp commit `57fe1f0`, which predates and excludes PR #7553. A custom build would break the controlled-variable invariant and introduce untested code. Additionally, no GGUF conversion of PaliGemma **2** (the model specified in the plan) has been published; the only available GGUF (`abetlen/paligemma-3b-mix-224-gguf`) is PaliGemma v1. This is exactly the risk the register anticipated: "PaliGemma fails to load in current llama.cpp commit."
- **Tradeoff / cost accepted:** We lose one data point (the potential accuracy ceiling from PaliGemma's native `<loc>` detection vocabulary). Phase A now answers: "What is the zero-shot ceiling for SmolVLM?" rather than "which of PaliGemma or SmolVLM is better?" The fine-tune target for Stage 2 will be SmolVLM-500M (or 256M if 500M underperforms). If PaliGemma GGUF support matures before Stage 2 fine-tuning, revisit.
- **Revisit when:** (1) A community GGUF for PaliGemma-2-3B-mix-224 is published AND (2) PaliGemma support is merged into llama.cpp mainline (or we decide to adopt a specific fork). At that point, add it as an optional Phase A extension rather than a controlled variable.

### 2026-06-14 — RefDrone HF dataset repo ID correction

- **Decision:** Use `sunzc-sunny/RefDrone` as the RefDrone dataset source, replacing `sun-langwei/RefDrone` cited in the Stage 1 README.
- **Alternatives considered:** None — the original ID returns HTTP 401; the correct ID was confirmed from the project's GitHub page.
- **Reasoning:** The Stage 1 README noted the repo as `sun-langwei/RefDrone` "or equivalent" with a flag that it was unconfirmed. Phase 0-C found the correct repo: the GitHub project (`github.com/sunzc-sunny/refdrone`) links explicitly to `huggingface.co/datasets/sunzc-sunny/RefDrone` (CC-BY-4.0, appears public). Additionally: RefDrone annotations do NOT bundle images — VisDrone 2019-DET images must be downloaded separately and matched by filename.
- **Tradeoff / cost accepted:** Minor extra download step (VisDrone images). No methodological impact.
- **Revisit when:** N/A — factual correction.

---

### 2026-06-14T20:00 — Gemma-4 E2B/E4B are thinking models; disable reasoning for VLM campaign

- **Decision:** Re-run V4 (Gemma-4-E2B) and V5 (Gemma-4-E4B) with `--reasoning off` passed
  to `llama-server`. Initial runs (thinking enabled, default) produced empty `content` fields
  — all 50 `max_tokens` were consumed by the `reasoning_content` chain-of-thought scratchpad.
- **Alternatives considered:** (a) increase `max_tokens` to 500–1000 to let thinking complete;
  (b) disable thinking with `--reasoning off`.
- **Reasoning:** For drone command generation, latency is the binding constraint (0.5–2 Hz
  target). Thinking mode adds hundreds of ms of per-token decode on top of the CLIP encode and
  prefill cost. A drone controller cannot budget extended reasoning on every camera frame.
  `--reasoning off` (llama-server 57fe1f0 flag, also `--reasoning-budget 0`) is the correct
  deployment configuration. The initial invalid runs are retained in the campaign README as a
  documented negative result.
- **Tradeoff / cost accepted:** With reasoning disabled, grounding quality may be slightly lower
  than thinking mode. Capability samples from the re-run suggest quality is acceptable for the
  "follow that object" task.
- **Revisit when:** If a future use case can tolerate >3 s latency per frame AND benefits from
  the reasoning overhead (e.g., complex scene parsing), re-enable thinking and increase
  `max_tokens` accordingly.

### 2026-06-14T22:00 — Install ffmpeg on Jetson for llama-server image decoding

- **Decision:** Install `ffmpeg` on the Jetson (`sudo apt install -y ffmpeg`).
- **Alternatives considered:** (a) pass image file paths via `file://` URL (blocked by server unless `--media-path` set, and then limited to that directory); (b) rebuild llama.cpp with a different image backend; (c) install ffmpeg.
- **Reasoning:** `llama-server` uses `ffprobe` (part of ffmpeg) to detect image/audio/video format when loading from base64 buffers. Without it, the server returns "Failed to load image or audio file" on every image request. ffmpeg is standard dev tooling with no downside.
- **Tradeoff / cost accepted:** None significant. ffmpeg is ~50MB installed.
- **Revisit when:** Never — this is a permanent tooling dependency for VLM work on the Jetson.

### 2026-06-14T21:00 — VLM measurement instrument: llama-server, not llama-mtmd-cli

- **Decision:** Use `llama-server` + Python `urllib` client as the timing instrument. `llama-bench` and `llama-mtmd-cli` were ruled out.
- **Alternatives considered:** (a) `llama-bench` (no image support confirmed); (b) `llama-mtmd-cli --perf -v` (single-shot only, can't do warm multi-frame); (c) `llama-server` with `cache_prompt: false`.
- **Reasoning:** `llama-bench` has no `--image` flag (confirmed). `llama-mtmd-cli` can only do single-shot inference per process invocation; two separate processes each pay CUDA graph compilation (~180ms), making warm-state measurement impossible from the CLI. `llama-server` keeps the model and CUDA graphs loaded across requests; `cache_prompt: false` ensures each request processes the full prompt from scratch (correct model for per-frame drone use). `timings.prompt_ms` in the `__verbose` response field includes CLIP encode time (verified empirically: `prompt_ms + predicted_ms ≈ wall-clock`). Also confirmed that `llama-mtmd-cli -hf` requires HTTPS (not built in `57fe1f0`), so model downloads must be done via `wget`.
- **Tradeoff / cost accepted:** `llama-server` adds small JSON serialization overhead (measured <10ms). Requires `ffmpeg` for image decoding (installed 2026-06-14).
- **Revisit when:** A later llama.cpp build adds image support to llama-bench with per-frame timing.

### 2026-06-14T21:00 — Architecture fork deferred to empirical result

- **Decision:** Defer the end-to-end-VLM vs. decomposed (detector + LLM) architecture decision to the VLM feasibility campaign result. The campaign's measured per-frame latency vs. required control rate (0.5–2 Hz) is the decision criterion. Not pre-deciding in favour of either architecture.
- **Alternatives considered:** (a) Adopt decomposed immediately (YOLO + LLM) as the practical choice; (b) adopt end-to-end VLM as the thesis-coherent narrative choice; (c) this — run the experiment and let the numbers decide.
- **Reasoning:** The 0.5–2 Hz control rate target is plausible even at 500 ms–2 s per-frame (the drone's own controller holds between high-level updates). A SmolVLM-256M smoke test produced a rough additive lower bound of ~744 ms (277 ms CLIP + 362 ms prefill + 105 ms decode) on a **cold, single-slice 512×512 image with a 14-token decode** — this is NOT a warm per-frame measurement (CUDA graph compilation fired mid-generation), underestimates image token count at campaign resolution (1280×720 will tile into more slices), and uses a shorter decode than the campaign will. **Do not interpret as "1.3 Hz viable."** A warm, 1280×720, 30-token measurement is required before any viability claim. Deciding before measuring would bias the framing. "End-to-end VLM can't close a tracking loop" is a valid thesis finding if the data show it; the decomposed path is the fallback documented in the thesis, not the default assumption.
- **Tradeoff / cost accepted:** Thesis narrative depends on what the data show. If end-to-end is too slow, the decomposed path needs its own measurement campaign.
- **Revisit when:** VLM campaign results are in. Decision criterion: if best-fitting VLM warm per_frame_ms ≤ 2000 ms AND grounding is correct → end-to-end viable; otherwise → document why decomposed is necessary.

---

### 2026-06-14T19:30 — Fix footprint parser (compute double-count) and drop --verbose from load probe

- **Decision:** Remove `--verbose` from the `_capture_load` command in `run_gemma_sweep.py`, and fix `parse_llama_load_buffers` in `parsers.py` to use **last-wins for compute buffers** and **zero-filtered accumulation for KV buffers** (skipping the probe pass's all-zero KV lines).
- **Alternatives considered:** (a) keep `--verbose` and filter by timestamp/pass; (b) take only the first occurrence of each buffer type; (c) this — minimal targeted fix with clear reasoning per field.
- **Reasoning:** llama.cpp runs two allocation passes per load: a probe/dry-run (model=0, KV=0, compute=real) and the real allocation (model=real, KV=real, compute=real). The original accumulating parser double-counted compute buffers (probe_value + real_value = 2×real). `--verbose` was intended to surface buffer-size lines, but those lines appear in normal (non-verbose) output anyway; `--verbose` only added GGML per-tensor debug output (2.3 GB for G2, 425 MB for G3) that flooded SSH buffers and left a stray llama-cli process on the Jetson for >10 min. Without `--verbose`, logs are tens of KB per model. Side effect of the stray process: it consumed 3.3 GB of RAM on the Jetson, causing subsequent footprint re-runs to falsely OOM.
- **Tradeoff / cost accepted:** The G2 footprint numbers come from the original (verbose) log parsed with the fixed parser (only 14 buffer-size lines in 2.3 GB, confirmed by grep). G4 cannot be measured with `--no-mmap` regardless of verbose flag (4.7 GiB malloc > free RAM on 8 GB Jetson); tegrastats 4374 MB remains the best estimate for G4.
- **Revisit when:** llama.cpp changes its buffer-reporting format, or a tegrastats-inline footprint approach makes the separate probe run unnecessary.

### 2026-06-14T18:30 — Correct two tegrastats-derived metrics post-hoc (swap + footprint), don't re-run the sweep

- **Decision:** After the gemma-family sweep, fix **two derived metrics in place** rather than re-running the campaign: (1) swap detection switched from `any(swap > 0)` to **growth over idle baseline** (`swap_growth_mb`, 50 MB threshold); (2) **true footprint** for RQ-G3 re-measured authoritatively via llama.cpp's own per-buffer load report (`--no-mmap --verbose`, new `--footprint` mode) instead of trusting tegrastats peak-RAM sampling. Directly measured throughput/power/TTFT numbers stand unchanged.
- **Alternatives considered:** (a) full re-sweep of all five units; (b) leave the numbers and footnote the caveats; (c) this — targeted parser fix + a ~20 min footprint-only re-run of G2/G3/G4 (+ G5 partial-offload probe).
- **Reasoning:** The expensive, device-bound measurements (pp/tg/TTFT/power) were never in question — only two *derived* fields were wrong: swap was a flat ~300 MB pre-existing baseline mis-flagged on every unit, and tegrastats RAM under-counts mmap'd weights (E2B's 2968 MB < its 3194 MB GGUF, an impossibility for resident weights). A full re-sweep would burn hours reconfirming good data. RQ-G3 (true PLE footprint) is the campaign's headline question, so it alone justified a small, focused re-measure using the runtime's own allocation report (authoritative, no sampling).
- **Tradeoff / cost accepted:** Footprint comes from a separate `--no-mmap` run, not the original benchmarked run, so it's a *characterisation* of the same model+ctx rather than a byte-exact reading of the benchmarked process. `--no-mmap` also changes the load path vs the original (mmap) runs — acceptable because we want the resident-allocation breakdown, which mmap obscures.
- **Revisit when:** the harness is changed to capture llama.cpp buffer sizes inline during the main benchmark run (would make the separate footprint pass unnecessary); or a quant-sensitivity sub-study re-runs these models anyway.

### 2026-06-14T17:00 — llama.cpp build gate for Gemma 4 (no rebuild required)

- **Decision:** Proceed with the existing `57fe1f0` llama.cpp binary for the Gemma-family sweep, including Gemma 4 (E2B/E4B) units. **No rebuild.**
- **Alternatives considered:** (a) Rebuild at a later commit with explicit Gemma 4 QAT GGUF testing; (b) proceed and fall back to rebuild only on runtime failure.
- **Reasoning:** Inspected `src/llama-arch.cpp` on the device at commit `57fe1f0`; the file contains `GEMMA4` and `GEMMA4_ASSISTANT` architecture enum entries and their string mappings. Gemma 4 shipped 2026-04-02 and QAT checkpoints 2026-06-05; `57fe1f0` post-dates both. The §7 gate in the campaign README is satisfied by source inspection rather than a live load probe. If a runtime failure occurs (e.g. `unknown tensor`), rebuilding at the latest commit is pre-approved and must be documented per the campaign README §7 protocol: record new commit hash, build flags, and note the runtime variable change on all affected rows.
- **Tradeoff / cost accepted:** Source inspection is not as definitive as a live model load. If Gemma 4 QAT GGUFs use a tensor name introduced after `57fe1f0`, we will learn this at runtime (unit G3/G4 will error). The fallback (rebuild) is low-risk.
- **Revisit when:** Unit G3 or G4 fails with an architecture/tensor error at runtime — at that point, rebuild, update this entry, and re-run.

### 2026-06-14T13:30 — Use llama-completion (not llama-cli) for TTFT measurement

- **Decision:** Switch the TTFT capture command from `llama-cli -no-cnv` to `llama-completion -no-cnv`, redirect stdin from `/dev/null` on the remote command, and add `stdin=subprocess.DEVNULL` to all local SSH subprocess calls.
- **Alternatives considered:** (a) keep `llama-cli` with different flags; (b) use `llama-server` endpoint; (c) parse TTFT from `llama-bench` output.
- **Reasoning:** `llama-cli` in build `57fe1f0` dropped `-no-cnv` support and dropped users into an interactive loop that flooded stdout indefinitely. `pkill -f tegrastats` was also replaced with `pkill tegrastats` (name-only match) because `-f` matched the word "tegrastats" in the SSH shell's own argv, killing the SSH connection (exit 255). The timing format changed in `llama-completion` (timestamp prefix; comma decimal separators from European locale); `parsers.py` was updated to handle both old and new formats.
- **Tradeoff / cost accepted:** TTFT prompt is ~9–11 tokens (short-prompt latency), not a 512-token prefill. Values (38–204 ms) represent latency lower bounds.
- **Revisit when:** llama.cpp is rebuilt; recheck if `llama-cli` restores `-no-cnv`.

### 2026-06-14T13:30 — Sequential automated sweep via run_campaign.py (not per-unit run cards)

- **Decision:** Run the 10-model sweep via `experiments/run_campaign.py` Python orchestrator rather than the isolated-Claude-session methodology designed 2026-06-13.
- **Alternatives considered:** The run-card / isolated-session methodology (see below).
- **Reasoning:** The orchestrator was already written, thoroughly debugged, and covers the full protocol. `run-unit.sh` driver was not yet built. Single device means no parallelism benefit from fan-out. The orchestrator produced identical data with less setup friction.
- **Tradeoff / cost accepted:** No per-unit context isolation. Acceptable because the orchestrator is deterministic code, not a language model that can drift between units.
- **Revisit when:** A campaign needs per-unit qualitative judgment (e.g. §7 capability eval) — then isolated Claude sessions are more appropriate.

### 2026-06-13T15:05 — Execute each experiment unit in a fresh, isolated Claude session

- **Decision:** Adopt an **isolated-session execution methodology** (in `experiments/`): every
  campaign is decomposed into independent **units** (for the model sweep, one unit per model),
  and **each unit is run by a freshly spawned, cold Claude session** initialized only from
  `CLAUDE.md` + a single self-contained **run card**. The repo filesystem is the message bus —
  run cards in, result blocks / `RESULTS.md` rows / raw logs out; no session shares another's
  in-memory context. A constant `bootstrap-prompt.md` enforces the restriction (one unit only,
  capture failures, fulfil the output contract, then STOP; BLOCKED+stop on ambiguity, never
  guess). Cards carry `status:` (TODO/RUNNING/DONE/FAILED/BLOCKED) as the single source of
  truth; `run-unit.sh` / `run-campaign.sh` spawn sessions via `claude -p`, sequential and
  resumable.
- **Alternatives considered:** (a) one long-lived session driving all ~10 models; (b) Agent-tool
  sub-agents fanned out from an orchestrator session; (c) this — independent headless `claude -p`
  sessions per unit.
- **Reasoning:** Fresh context per unit is an **experimental control**, not just tooling: it
  eliminates cross-run context contamination (earlier models' numbers/debugging can't bias later
  setup or interpretation) and forces every unit through the identical protocol by construction.
  It also stays within context budget (a 10-model sweep would overflow one session) and is
  reproducible/resumable (a unit = a versioned file; re-run = re-spawn). (a) contaminates and
  overflows; (b) keeps a long-lived orchestrator whose context still grows per spawned summary,
  and the Jetson is a single device so the fan-out parallelism sub-agents buy is unusable anyway.
- **Tradeoff / cost accepted:** Each unit pays cold-start overhead (re-reads `CLAUDE.md`,
  re-derives device state) and no live cross-unit synthesis — synthesis is a separate pass that
  reads the on-disk results. Hands-off runs default to `--permission-mode bypassPermissions`,
  acceptable only because this is the operator's own testbed device with a scoped sudo allowlist;
  tighten via `CLAUDE_PERM=acceptEdits` + `--allowedTools` if needed.
- **Revisit when:** A campaign genuinely needs live cross-unit reasoning mid-run (→ orchestrator +
  sub-agents), units can run concurrently on independent hardware (→ parallel dispatch), or the
  cold-start re-derivation cost becomes material (→ a cached device-state preamble).

---

### 2026-06-13T14:42 — Sudo on the Jetson: scoped passwordless for bench commands

- **Decision:** `jfdg` has NOPASSWD sudo for a tight, full-path command allowlist only,
  via `/etc/sudoers.d/10-jetson-bench` — `/usr/sbin/nvpmodel`, `/usr/bin/jetson_clocks`,
  `/usr/bin/tegrastats` (a `BENCH_CMDS` `Cmnd_Alias`). Everything else still requires the
  password. Expand the allowlist by adding a tool's absolute path to `BENCH_CMDS`, then
  `sudo visudo -cf /etc/sudoers.d/10-jetson-bench`. This is a consolidation of three
  same-day decisions: (1) full passwordless installed, (2) reverted once the device became
  reachable off-LAN via Tailscale, (3) scoped allowlist restored hands-off automation
  without standing full root.
- **Alternatives considered:** Blanket `NOPASSWD: ALL`; no NOPASSWD (pipe via `sudo -S`
  every time); this scoped allowlist.
- **Reasoning:** The scoped allowlist is the right balance now that the node is reachable
  off-LAN (Tailscale): it keeps power-mode flips, clock locking, and `tegrastats` logging
  hands-off while full paths + a curated alias keep the blast radius small and the intent
  auditable.
- **Tradeoff / cost accepted:** Any new privileged tool needs a one-line edit + re-validate
  before automation can use it passwordless — that friction is intentional (forces a
  conscious choice to widen privilege). File installed `0440 root:root`; `visudo -c`
  validates all of `/etc/sudoers.d/` OK.
- **Revisit when:** A new benchmark tool needs root (expand `BENCH_CMDS`); the allowlist
  grows large enough to warrant rethinking the trust model; or the device is repurposed
  or exposed to an untrusted network.

---

### 2026-06-13T14:30 — Remote access to the Jetson via Tailscale (WireGuard mesh)

- **Decision:** Enrolled the Jetson into the operator's existing Tailscale tailnet
  (account `javier.fco.dibo.gomez@`) for access from outside the LAN. Transport-only: no
  Tailscale-SSH/ACL mode — the existing OpenSSH `sshd` + `~/.ssh/jfdg01` key are
  unchanged; Tailscale only provides the network path. Brought up with
  `tailscale up --hostname=jetson --accept-dns=false`. Jetson tailnet IP: `100.127.45.66`.
  3090 workstation already on the tailnet (`100.103.89.71`). Added SSH alias
  `jetson-remote` → `100.127.45.66` (raw tailnet IP, not MagicDNS) in `~/.ssh/config`;
  LAN alias `jetson` → `192.168.1.136` retained for local low-latency use. Key expiry
  should be disabled for the `jetson` node in the Tailscale admin console (Machines →
  jetson → Disable key expiry) so the testbed doesn't drop off at the default ~180-day
  expiry.
- **Alternatives considered:** (a) Tailscale mesh; (b) Cloudflare Tunnel; (c) reverse SSH
  through a VPS (autossh/systemd); (d) public port-forward + DDNS.
- **Reasoning:** Tailscale needs no port-forwarding/router access, traverses NAT/CGNAT,
  self-heals across reboots and IP changes, gives a stable `100.x` address, and the 3090
  was already enrolled (zero account setup). It doesn't widen the public attack surface
  (no internet-facing sshd), unlike (d). Used the raw tailnet IP rather than a MagicDNS
  hostname because the tailnet reports a DNS health warning ("can't reach configured DNS
  servers"); a raw IP removes the DNS dependency entirely. `--accept-dns=false` so the
  broken MagicDNS resolver can't affect the Jetson's name resolution.
- **Tradeoff / cost accepted:** Dependency on a third-party coordination service (Tailscale
  control plane) and on the operator's identity provider for node auth. No hostname
  convenience until MagicDNS is fixed (raw IP only). Combined with the scoped
  passwordless-sudo entry, the device is now privileged-command-accessible from anywhere
  on the tailnet — acceptable because tailnet membership is gated by the operator's SSO
  and the device key.
- **Revisit when:** MagicDNS is fixed (switch alias to a hostname); or if a
  self-hosted/no-third-party path becomes a requirement (→ reverse SSH + VPS); or the
  device is exposed to an untrusted network.

---

### 2026-06-13T14:17 — Upper bound = 15 W with locked clocks

- **Decision:** Treat the **15 W locked-clock** config as today's upper bound. Did **not**
  enable 25 W MAXN_SUPER this session.
- **Alternatives considered:** Enable MAXN_SUPER via firmware/bootloader update + updated
  nvpmodel profile.
- **Reasoning:** The active nvpmodel profile (`p3767-0003`) only defines 15 W/7 W;
  unlocking Super requires a bootloader/firmware update. A failed flash leaves the device
  unbootable, and physical access is not available to recover from a brick.
- **Tradeoff / cost accepted:** Today's "upper bound" is the 15 W ceiling, not the absolute
  silicon ceiling. The 25 W Super number will be a separate, higher data point in a later
  session.
- **Revisit when:** A session where a firmware update is reasonable (physical access
  available as a fallback).

---

### 2026-06-13T13:50 — Build llama.cpp natively on the Orin, not cross-compiled locally

- **Decision:** Build llama.cpp directly on the Jetson (aarch64, CUDA `sm_87`) rather than
  building on the x86_64 workstation and copying the binary over.
- **Alternatives considered:** (a) Native on-device build; (b) cross-compile on the x86_64
  box with an aarch64 toolchain; (c) NVIDIA `jetson-containers` prebuilt images.
- **Reasoning:** Binaries are architecture-specific — an x86_64 build can't run on the ARM
  Orin. A correct cross-compile needs an aarch64 cross-toolchain + aarch64 CUDA target
  libs, which is fragile and slower to set up than the native build already underway.
  Critically, llama.cpp is built once and reused across all ~10 models — it's a one-time
  cost, not per-model.
- **Tradeoff / cost accepted:** Native build is slow on the 6-core CPU (~15–25 min, CUDA
  kernel compilation dominates). Accepted because it's one-time.
- **Revisit when:** We need frequent rebuilds (tracking llama.cpp master, sweeping build
  flags) — then switch to `jetson-containers` or a beefier aarch64 build host.

---

### 2026-06-13T13:45 — Runtime: llama.cpp (CUDA), not Ollama

- **Decision:** Use llama.cpp built with CUDA as the benchmarking runtime.
- **Alternatives considered:** Ollama (quick); llama.cpp (CUDA); both.
- **Reasoning:** `llama-bench` gives clean, separated prefill (pp) vs decode (tg)
  throughput and is the standard for reproducible thesis numbers. Ollama exposes only a
  coarser eval rate and adds overhead.
- **Tradeoff / cost accepted:** More setup (cmake install + on-device CUDA build).
- **Revisit when:** We want an easy-to-reproduce cross-check — add Ollama as a secondary,
  looser data source.

---

### 2026-06-13T13:40 — Headline model: Llama-3.2-3B-Instruct Q4_K_M

- **Decision:** Use Llama-3.2-3B-Instruct `Q4_K_M` as the first/most-solid general model.
- **Alternatives considered:** Llama-3.2-1B (max raw tok/s); Qwen2.5-7B (capability
  ceiling, tight fit).
- **Reasoning:** Best balance of "genuinely useful" and "fits 8 GB comfortably with KV
  headroom" — the README sweet spot. ~9 more models follow to cover the size/quant
  spectrum.
- **Tradeoff / cost accepted:** Not the absolute max-tok/s point (a 1B would be faster) nor
  the capability ceiling (7B) — those are separate data points in the broader sweep.
- **Revisit when:** Running the broader ~10-model sweep.
