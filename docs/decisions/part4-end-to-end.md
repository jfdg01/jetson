# DECISIONS — Part IV (v4 End-to-End Workflow Refinement)

> Decision log for hardening the integrated end-to-end follow pipeline (v4). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the bottom (chronological, oldest first; matches RESULTS/QUESTIONS).

---

### 2026-07-02 — ★ Spine stays Qwen2-VL-2B; bake-off early-stopped

- **What:** keep Qwen2-VL-2B Q8_0 as the grounding spine; stop the bake-off before arm D and arm E
  legs 2–3; cancel Jetson latency measurement for arms A/C/D.
- **Why:** every measured challenger lost on accuracy (48.5 / 53.1 / 56.0 / 5.5% vs the 62.6–63.1%
  incumbent); arm B proved the deployed ROI lever (85.2%) does not transfer across backbones; and the
  pending acquire-once re-layer (`experiments/2026-07-01-temporal-acquire-carry/`) demotes anchor
  speed — the bake-off's criterion 1 — to a once-per-acquire cost, making accuracy the binding axis,
  which the incumbent wins outright. No remaining run could change the adoption decision.
- **Given up:** Florence-2's "speed-ceiling" datapoint; SmolVLM2 lr=2e-4/4e-4 legs; A/C/D latency
  numbers; the vision-tower-unfreeze follow-up (branch `experiment/vlm-vision-unfreeze` parked as a
  pre-draft).
- → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](../../experiments/2026-06-30-vlm-backbone-bakeoff/README.md)

### 2026-07-02 — Deploy drift repaired: restore the gated ROI config (M=2.0 @512 upscaled, acquire 4.8 s)

- **What:** `grounding/deploy/video.py` + `gui.py` were running `ROI_MARGIN=4.0`, `ROI_OUT_RES=1024`,
  `upscale=False`, `ACQUIRE_PERIOD_S=2.0` — a config matching **no measured number**, introduced by
  undocumented tweak commits `7874726` ("Tweaking the timings on the gui": acquire 4.8→2.0 s) and
  `4eae99f` ("Working on improving the efficency": M 2.0→4.0, 512→1024, upscale off). Restored the
  gated config: **M=2.0, out_res=512, upscale=True (85.2% IoU@0.25), acquire 4.8 s** — the numbers
  the thesis quotes. Also fixed `gui.py`'s compare path missing the `ROI_MIN_CROP` shrink-spiral
  floor, and its `_track` timing defaults now import the measured constants instead of hardcoding.
- **Why:** the drift was a chain of symptom-patches — OUT_RES was pushed to 1024 hoping for accuracy,
  a square 1024² upscale then exceeded the letterboxed full frame's pixel count and *inverted* the
  prefill saving, so upscale was disabled, then the margin widened to compensate. At the gated 512
  budget the trap doesn't exist: fed ≤512² is far below the full frame, which is exactly why M=2.0
  @512 measured 2.7× cheaper AND +22.6 pp. Code and measurement must agree or the quoted numbers
  are fiction. Selfchecks + 58-test suite pass post-repair.
- **Given up:** the (unmeasured) hope that M=4.0 @1024 sees more context; if a wider/hi-res
  re-anchor is ever wanted, re-run the `grounding.roi` sweep and re-gate first — the sweep already
  showed M=2.0 @512 dominating.

### 2026-07-02 — ★ Knowledge over infrastructure: v3 deploy loop frozen as baseline; the temporal orchestrator succeeds it

- **What:** user directive — build on previous *knowledge* (measured configs, the ROI/terse levers,
  the acquire contract), not previous *infrastructure*. The v2/v3 deploy loop
  (`grounding/deploy/video.py`/`gui.py`, periodic re-anchor + CSRT coast) is now **maintenance-only**:
  kept at the gated config as the measured baseline and demo, but not extended. New capability lands
  in the temporal campaign's `ACQUIRE → CARRY → REGROUND` orchestrator
  ([`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md)),
  which reuses the acquire stack (`contract.py`, `roi.py`, `serve.py`, `backends.py`) whole. Past
  decisions may be re-opened when the project clearly benefits.
- **Why:** the periodic-re-anchor shape is the thing the temporal re-layer exists to replace;
  investing further in it is sunk-cost. The knowledge it produced (gated configs, lever behavior,
  measured walls) transfers; the loop code does not.
- **Given up:** incremental upgrades to the v3 demo path (e.g. dynamic re-anchor cadence) — any such
  effort goes to the orchestrator instead.

### 2026-07-02 — Carry tier stays zero-shot: SAM2.1-tiny adopted, temporal training lever unpulled

- **What:** Phase 0 gate (RQ-T.1) passed — the ACQUIRE→CARRY→REGROUND orchestrator's carry tier is
  off-the-shelf SAM2.1-hiera-tiny with no temporal fine-tuning. AerialMind stays eval-only.
- **Why:** zero-shot carry already matches the deployed v3 loop's headline accuracy (IoU@0.25 0.849
  vs 85.2%) with **zero** per-frame VLM calls; ID-consistency 0.891. Training could only buy back
  the occlusion tier (32.9% recovery), which the REGROUND trigger owns more cheaply.
- **Given up:** a temporally fine-tuned tracker (reserved lever — re-open only if Phase 2/3 shows
  the on-device carry degrading); EdgeTAM/EfficientTAM stay candidates for the *Jetson FPS* gate,
  not the accuracy gate.
- → [`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md)

### 2026-07-02 — Acquire-carry replaces per-frame grounding; OP=768; perception-on-Jetson/control-host split

- **What:** the temporal campaign closes with the two-tier architecture adopted for Part IV:
  language-conditioned ACQUIRE/REGROUND/RETARGET (VLM, seconds-scale, **size-prior validated**)
  + zero-shot SAM2.1-tiny memory-carry per frame, operating point **image_size 768** (frozen knee
  rule: 640 missed the 0.799 accuracy bar by 1.2 pp; 768 = 0.830 acc / 4.89 FPS). In the
  integrated loop, per-frame perception runs on the Jetson (carry service + co-resident VLM
  server); SITL, renderer, PID and MAVLink stay host-side.
- **Why:** carry matches the deployed v3 re-anchor loop's accuracy (0.830–0.849 vs 85.2%) with
  zero per-frame VLM calls; validation is load-bearing (3a-1 falsified unvalidated reground);
  the host keeps only what is host-bound by nature (sim + microsecond PID) — the on-device claim
  covers the binding resource.
- **Given up:** the fully-passing rate criterion today (carry-phase 4.1 vs ≥5 FPS at OP=768 —
  eager PyTorch's ceiling; E1 TensorRT export is the budgeted fix); a fully-on-device binary;
  fastest-possible relock (validated reground waits for the target to actually reappear).
- Also recorded: Phase 3b transport deviation from the frozen `jetson_percept.py` spec
  (stdlib `multiprocessing.connection` carry-only service; acquire stays host-side via the
  existing JetsonBackend against the same Jetson llama-server) — compute placement identical,
  deviation and rationale in the campaign README.
- → [`experiments/2026-07-01-temporal-acquire-carry/`](../../experiments/2026-07-01-temporal-acquire-carry/README.md)

### 2026-07-02 — E1: carry tracker variant + encoder export path ([`experiments/2026-07-02-carry-trt-export/`](../../experiments/2026-07-02-carry-trt-export/README.md))

- **Decision #1 (tracker variant): keep SAM2.1-hiera-tiny.** EdgeTAM fallback not needed — the
  TensorRT fp16 encoder cleared the ≥5 FPS gate at OP=768 (6.15 co-resident), so the accuracy risk
  of swapping trackers was not worth taking.
- **Decision #2 (encoder export path): TensorRT fp16, encoder-only.** Export the ViT-Hiera image
  encoder (per-frame dominant cost); memory attention + the two high-res 1×1 convs stay PyTorch.
  - **Why:** encoder is ~2.3× faster in fp16 (65 ms vs ~150 ms), lifting 768 carry to 6.15 FPS
    with no accuracy loss (IoU@0.25 1.000, mean IoU +0.006) and mask parity 1.000 — the lazy fix
    that keeps the whole v3 accuracy story intact.
  - **Runtime = TensorRT Python API + torch-tensor bindings, not ONNX Runtime** (frozen plan's
    Plan A). Reasons found at execution: Jetson venv had neither ORT nor TRT; system TRT 10.3.0 was
    already present (zero new deps); ORT numpy I/O forces a per-frame host round-trip that defeats
    the latency goal. Documented deviation in the campaign README.
  - **Given up:** end-to-end engine (more speedup, weeks of ONNX-ing the stateful memory bank — the
    known-hard part); a further ~30 ms that the retained torch memory-attention + default-stream
    TRT sync still cost (a dedicated CUDA stream could reclaim some, not pursued — gate already met).
- → [`experiments/2026-07-02-carry-trt-export/`](../../experiments/2026-07-02-carry-trt-export/README.md)

### 2026-07-02 — Stop tuning occlusion levers; attack the two binding failure modes instead

- **Decision:** after E2 showed the levers-on ceiling is < 0.5 m/s (all speeds FAIL), do NOT run
  more speed/lever-tuning trials on the current lever set. The next follow-hardening work targets
  the two failure modes E2 named: (1) make the loss signal confidence/staleness-aware so a
  confident-but-wrong carry box (occluder latch) still triggers REGROUND — today both DR and
  REGROUND gate only on `box is None`; (2) velocity-extrapolate the stale acquire box before
  prompting SAM2 (and/or hold the last chase velocity during first acquire) so a car moving ≥1 m/s
  can be locked before it exits the FOV.
- **Why:** the levers were built to widen the REGROUND blind window, but E2 proves the blind window
  is never the binding constraint with real carry — confident-latch binds at 0.5, acquire-latency
  binds at ≥1.0. Tuning the levers further cannot move a ceiling set by constraints they don't
  touch. Phase 1's oracle-box ceiling (1.0 m/s) was optimistic because the oracle removed exactly
  these two modes.
- **Given up:** further speed trials with the current lever set (ceiling already sits below the
  lowest test speed, so they'd add no information); a same-session fix (E2 is measurement-only).
- → [`experiments/2026-07-02-follow-speed-ceiling/`](../../experiments/2026-07-02-follow-speed-ceiling/README.md)
