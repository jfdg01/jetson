# DECISIONS — Part I (Exploratory)

> Decision log for the exploratory device campaigns + grounding Stages 1–4. Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the **bottom** (chronological, oldest first; matches RESULTS/QUESTIONS).

---

### 2026-06-13T13:40 — Headline model: Llama-3.2-3B-Instruct Q4_K_M

- Best balance of capability + fits 8 GB with KV headroom. ~9 more models follow to cover size/quant spectrum.
</content>
### 2026-06-13T13:45 — Runtime: llama.cpp (CUDA), not Ollama

- `llama-bench` gives separated prefill (pp) vs decode (tg) throughput = reproducible thesis numbers. Ollama exposes only coarser eval rate + overhead.

### 2026-06-13T13:50 — Build llama.cpp natively on Orin

- x86_64 binary can't run on ARM Orin. Cross-compile needs aarch64 toolchain + CUDA target libs (fragile). Native build ~15–25 min, one-time cost. Pinned `57fe1f0`.

### 2026-06-13T14:17 — Upper bound = 15 W locked clocks; 25 W MAXN_SUPER not attempted

- Profile `p3767-0003` = 15 W / 7 W only. Unlocking Super requires bootloader update — unacceptable risk without physical access for recovery.

### 2026-06-13T14:30 — Remote access via Tailscale

- Enrolled in existing tailnet. Transport-only (not Tailscale-SSH). Jetson: `100.127.45.66` (alias `jetson-remote`); LAN `192.168.1.136` retained (alias `jetson`). `--accept-dns=false` (broken MagicDNS). Disable key expiry in Tailscale admin console.

### 2026-06-13T14:42 — Sudo on Jetson: scoped NOPASSWD allowlist

- `/etc/sudoers.d/10-jetson-bench`: NOPASSWD for `/usr/sbin/nvpmodel`, `/usr/bin/jetson_clocks`, `/usr/bin/tegrastats` only. `0440 root:root`. Expand via `visudo -cf`. History: blanket NOPASSWD → reverted on Tailscale enrollment → scoped allowlist restored.

### 2026-06-13T15:05 — Isolated-session methodology (designed; superseded by orchestrator for this sweep)

- **Design:** Each unit run by fresh `claude -p` session from `CLAUDE.md` + self-contained run card. Guard: `pgrep -x claude` defers to live session; `flock` no concurrent runs; STOP/DONE sentinels. Repo filesystem as message bus.
- **Remains valid for:** campaigns needing per-unit qualitative judgment (not just deterministic orchestration).

### 2026-06-14T13:30 — Run sweep via run_campaign.py (not isolated sessions)

- Orchestrator already debugged and covers full protocol. Single device = no parallelism benefit from fan-out. Supersedes the isolated-session methodology designed 2026-06-13.

### 2026-06-14T13:30 — TTFT: llama-completion (not llama-cli); stdin from /dev/null

- `llama-cli` dropped `-no-cnv` → interactive loop. `pkill -f tegrastats` killed SSH connection → use `pkill tegrastats` (name-only). `llama-completion` uses timestamp prefix + comma decimal separators (European locale) — `parsers.py` updated.

### 2026-06-14T17:00 — Use pinned `57fe1f0` for Gemma 4; no rebuild

- `GEMMA4` + `GEMMA4_ASSISTANT` present in `src/llama-arch.cpp` at `57fe1f0`. Confirmed by source inspection before download.

### 2026-06-14T18:30 — Correct swap + footprint metrics post-hoc; no re-sweep

- **Swap:** `any(swap > 0)` → `swap_growth_mb > 50 MB` (pre-existing ~300 MB baseline mis-flagged). **Footprint:** tegrastats under-counts mmap'd weights → re-measured via `--no-mmap --verbose` load report. Throughput/power/TTFT numbers unchanged.

### 2026-06-14T19:30 — Fix footprint parser: last-wins for compute, zero-filter for KV

- llama.cpp runs probe pass (compute=real, KV=0) + real allocation (all real). Original parser double-counted compute. `--verbose` added 2.3 GB debug output per model, flooded SSH, left stray process consuming 3.3 GB RAM.

### 2026-06-14T21:00 — Architecture fork (end-to-end vs decomposed) deferred to empirical result

- Decision criterion: if best VLM warm per_frame_ms ≤ 2000 ms AND grounding correct → end-to-end viable; otherwise → decomposed. SmolVLM-256M cold smoke test (~744 ms) is NOT a warm measurement.

### 2026-06-14T21:00 — VLM instrument: llama-server (not llama-bench or llama-mtmd-cli)

- `llama-bench` has no `--image` flag. `llama-mtmd-cli` is single-shot (each process pays CUDA graph compilation ~180 ms, can't measure warm state). `llama-server` keeps model + CUDA graphs loaded; `cache_prompt: false` per-frame. `timings.prompt_ms` includes CLIP encode (verified: `prompt_ms + predicted_ms ≈ wall-clock`).

### 2026-06-14T22:00 — Install ffmpeg on Jetson (permanent VLM dependency)

- `sudo apt install -y ffmpeg`. `llama-server` uses `ffprobe` to detect image format from base64. Without it: "Failed to load image or audio file" on every request. ~50 MB.

### 2026-06-14T20:00 — Gemma-4 E2B/E4B: disable reasoning (`--reasoning off`)

- Default thinking mode consumed all 50 `max_tokens` in `reasoning_content` → empty `content`. At 0.5–2 Hz drone control, thinking latency is unacceptable. Initial invalid runs retained as documented negative result.

### 2026-06-14 — RefDrone dataset: correct repo `sunzc-sunny/RefDrone`; images via VisDrone 2019-DET

- `sun-langwei/RefDrone` returns HTTP 401. Correct ID confirmed from GitHub project page. RefDrone annotations do NOT bundle images — VisDrone 2019-DET must be downloaded separately.

### 2026-06-14 — PaliGemma excluded from Stage 1

- PaliGemma 2 GGUF support (PR #7553) unmerged/draft as of 2026-06-14. Only PaliGemma v1 GGUF published. Custom build would break controlled-variable invariant on pinned `57fe1f0`.

### 2026-06-15T08:10 — Phase A gate: SmolVLM-500M Q8_0 selected for Phase C fine-tuning

- **Result:** Both models fail IoU@0.25 < 30% (both 0%). S1 (256M): 3.58 Hz, parse 0%. S2 (500M): 1.20 Hz, parse 4%, latent coordinate structure in responses. S2 chosen: structure to anchor fine-tuning on. Fits RAM (2734 MB, no swap).

### 2026-06-15 — Phase B toolchain: ArduPilot headless + x86_64; no Gazebo

- **Chosen:** ArduCopter SITL headless on local x86_64. Oracle bboxes from geometric projection (pinhole model). ByteTrack minimal in-repo (~250 lines, numpy+scipy only). Gazebo deferred to Phase C only if needed.
- **Why not Jetson SITL:** Conflates measurement device with stimulus; RAM/CPU contention.

### 2026-06-15T09:30 — Phase B: programmatic target + gimbal-stabilized oracle camera

- **Chosen:** Target = 0.25 m/s constant-velocity in copter's NED frame (not ArduRover telemetry — cross-instance NED origin mismatch ~584 m D). Camera = gimbal-stabilized nadir (roll/pitch=0, real yaw retained).
- **Why body-fixed failed:** ArduPilot nose-down accel pitch (~13°) → 130 px apparent target shift → positive feedback → vx pinned at 3 m/s, 246 px mean error.
- **Result:** 19.99 Hz, 12.9 px mean error, 100% oracle coverage, 0 track losses × 3×60 s. **Phase B PASS.**

### 2026-06-15T13:00 — Toy NL-command demo: honest zero-shot baseline, aerial imagery only

- **Chosen:** `runners/demo_nlcommand.py`. Three verbs: FOLLOW/ZOOM → VLM grounding; TURN → heuristic yaw. Tested on VisDrone nadir frames. Grounding failures reported honestly. Latency: 534 ms / 2046 ms (single calls, not campaign-grade).
- **Why:** Establishes zero-shot baseline before fine-tuning. TURN demonstrates pipeline working; FOLLOW/ZOOM demonstrate VLM path firing with honest negative result.

### 2026-06-15T17:30 — Phase C: async slot architecture + track-loss definition

- **Chosen:** `LatestDetectionSlot` (lock-protected, monotonic timestamp guard). Track-loss = empty ByteTracker returns only (not ID changes — ID changes would equal injection count at 1 Hz). Forced re-seed gap at t=30 s (`LOST_TIMEOUT_S + 1 = 4 s`) validates re-seed < 2 s reproducibly.
- **Live VLM path + Gazebo frame-grabber:** stubs (`NotImplementedError`); `--inject-oracle` bypasses both for Branch-1 gate.

### 2026-06-15T18:30 — Phase C Gazebo: decoupled render-only (not ArduPilot-Gazebo coupling)

- **Chosen:** Headless `gz sim -s -r`; Python moves poses via `/world/phase_c/set_pose` gz transport. SITL and Gazebo share no physics coupling. Reuses 100% of Phase B SITL pipeline unchanged.
- **Why coupling rejected:** Requires patching SDF + FDMCC bridge; ardupilot_gazebo Iris has no built-in camera.
- **gz bindings confirmed:** `/usr/lib/python3/dist-packages/gz/` (Harmonic 8.13.0, `transport13` + `msgs10`).

### 2026-06-15T22:00 — Stage 2 fine-tuning: LoRA on SmolVLM-500M with RefDrone MDETR JSON

- **Config:** LoRA r=16/α=32, `q/k/v/o_proj` only (vision frozen), lr 1e-4, effective batch 16. RefDrone MDETR JSON loaded directly (HF streaming interface fails). AutoProcessor instead of SmolVLMProcessor (fails in transformers 5.12 with video_processor_type error). Trainable: 4.16 M params (0.81%).
- **Export:** `peft.PeftModel.merge_and_unload()` → HF → scp to Jetson → `convert_hf_to_gguf.py --outtype q8_0` at `57fe1f0`.

### 2026-06-16T10:00 — Stage 2 FAIL: text-only LoRA insufficient for spatial grounding

- **Result:** IoU@0.25 = 1%, gate ≥20% = FAIL. Parse 100% (pipeline correct; failure is spatial). Frozen SigLIP → no gradient path for localization → model converges to marginal-mean bbox.
- **Decision:** Accept negative result. No further epochs (more training won't fix root cause). Thesis content: why naive text-only LoRA fails on aerial grounding.

### 2026-06-16T10:40 — Stage 3: re-diagnose Stage 2 as ill-posed target, switch to RefCOCO

- **Re-diagnosis:** Two stacked causes: (1, dominant) one-caption→many-boxes = ill-posed (marginal-mean box is correct loss-minimiser); (2) tiny-object pixel regression through frozen encoder.
- **Fixes:** Dataset → RefCOCO (many-captions→one-box, well-posed, large objects). Coords → normalized 0–1000 int bins. LoRA → attn+MLP (was attn-only). `center_std` collapse sentinel added.
- **Trade-off:** RefCOCO is ground-level → domain gap to aerial (measured as RQ-S3.4). Proves grounding skill learnable, not that it transfers.

### 2026-06-17T00:00 — Stage 4: NARROW MISS (19.5% vs ≥20% gate)

- **Result:** Well-posed RefDrone curriculum from ft3. Parse 100%, center_std 211.5 (healthy). IoU 12.5→16.0→19.5% across epochs, still rising at LR→0. Gate miss = **−0.5 pp**. ~2.7 h GPU on RTX 3090.
- **Root causes eliminated:** Stage-2 ill-posed target + Stage-3 domain gap — both fixed. Miss attributed to data budget (4101) / capacity limit, not a failure mode.
- **Key finding:** Motivates v2 — resolution ceiling (16 px aerial objects @512) is the remaining lever.

