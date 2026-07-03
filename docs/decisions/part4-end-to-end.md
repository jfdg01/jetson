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

### 2026-07-02 — Defer twin-rejection to an appearance-embedding gate; don't extend the size prior

- **Decision:** the fix for the E3 wrong-lock (REGROUND accepting an identical decoy, 3/3) is an
  **appearance-embedding gate on reground acceptance** — embed the acquire crop (e.g. CLIP), keep
  a reference from the confident pre-occlusion carry, and reject a re-lock whose cosine similarity
  to the reference is below a threshold learned from true-car crops. Reserved as future work (E3b
  scaffold exists in the campaign README); not implemented this session.
- **Why:** E3 proves the current lever set is identity-blind. The size-prior validation rejects
  boxes of implausible *size*; a same-appearance twin is identical in size by construction, so no
  amount of size/geometry tuning can distinguish it. The only signal that separates true target
  from decoy is *appearance*, which none of the deployed levers use. S1 also shows CARRY's own
  memory already solves the non-occluded crossing, so the gap is specifically the REGROUND
  re-acquisition path, which starts appearance-free.
- **Given up:** extending the size/geometry prior further (cannot separate identical twins — wrong
  tool); running E3b this session (out of scope unless asked); a same-session fix (E3 is
  measurement-only). Also noted: the AerialMind leg shows density alone is not the problem, so a
  crowding-robustness effort would be misdirected — the target is occlusion + in-lane same-look decoy.
- → [`experiments/2026-07-02-twin-distractor/`](../../experiments/2026-07-02-twin-distractor/README.md)

### 2026-07-02 — Keep submit-frame carry init always-on; ship `motion` as a backstop; reject the `score` gate at tau=0

- **Decision:** make **Fix B (submit-frame carry init + gap replay) the permanent, always-on
  behavior** — it, not the loss gate, is what lifted the follow ceiling from `< 0.5` to 0.5 m/s
  (E4: the `none` control passed identically to `motion`). Of the two trust-aware loss gates from
  the E2 decision above, keep **`motion`** (geometry backstop) as an available but off-by-default
  lever, and **do not ship `score` at tau=0**.
- **Why:** E4 Stage 1 @0.5 showed `none` and `motion` both PASS with in-FOV 1.000 and identical
  relock timing, so at this speed the gate never fired — Fix B already made the honest-loss REGROUND
  path work by landing the *initial* lock on the true car instead of the 2.5-5 s stale VLM box, which
  was E2's confident-latch. `score` FAILed (`recovered=false`): SAM2 `object_score_logits` *does*
  separate occlusion (occluded mean −3.23 vs clear +8.61), but its clear-frame tail dips to −3.94,
  so tau=0 over-fires on clean-track noise and the relock is never confirmed. `motion` can't be
  fooled that way and costs nothing when inert, so it stays as cheap insurance for a future
  confident-latch Fix B doesn't catch.
- **Given up:** shipping `score` (a higher or hysteretic tau might rescue it, but it isn't needed —
  the signal is redundant with Fix B here); closing the ≥1.0 m/s ceiling this session. **RQ-E4b is
  NO** — 1.0/1.5 stay on the E2 floor because the car escapes during the ~5 s *first-acquire hover*
  (no lock yet exists to seed replay/DR). Fixing that (hold a guessed chase velocity from t=0) is the
  named next lever, deliberately out of E4 scope.
- → [`experiments/2026-07-02-follow-hardening/`](../../experiments/2026-07-02-follow-hardening/README.md)

### 2026-07-03 — Chose pursuit DR over acquire-latency reduction (E5); result reframes the ceiling as an acquire-reliability problem

- **Decision:** to attack the ≥1.0 m/s follow ceiling, implemented **position-seeking pursuit DR**
  (`--dr pursuit`: blind command = est. velocity + 0.5·(dead-reckoned position − copter position),
  2.5 m/s cap) rather than trying to shrink the ~5 s VLM acquire latency. Kept behind a flag;
  `--dr velocity` remains the bit-identical E2/E4 baseline.
- **Why:** pursuit closes a deficit from *any* source (first-acquire hover, occlusion, estimate
  drift) once a lock exists, whereas cutting latency is not actionable — the ~5 s wall on Jetson
  Q8_0 is already characterized (E1/3b) with no cheap headroom, and it would only shrink, not
  remove, the deficit. The E4-named "hold a guessed chase velocity from t=0" lever is ill-posed:
  before the first lock there is no velocity estimate to hold.
- **Given up / what E5 actually showed:** nothing shrinks the ~5 s VLM wall — pursuit sidesteps it
  by chasing the extrapolated position. But **RQ-E5 = NO**: pursuit did not lift the ceiling (still
  0.5 m/s), and crucially the 1.0/1.5 failures were **acquire failures, not chase failures** — both
  never locked (31/32 rejected), so pursuit never engaged. The one high-speed run that *did* lock
  (p-1.5b) PASSed at 1.5 m/s with pursuit holding 0.927 in-FOV — evidence pursuit works once seeded.
  **This reframes the ceiling as an acquire-reliability problem**, not a controller problem: the
  next lever is making the t=0 first acquire reliable (retry / relaxed-validate on the submit frame),
  which pursuit cannot substitute for. Pursuit stays as the right blind-branch controller (keep
  `--dr pursuit` for the seeded case), off-by-default until the acquire path is fixed.
- → [`experiments/2026-07-02-pursuit-chase/`](../../experiments/2026-07-02-pursuit-chase/README.md)

### 2026-07-03 — Chose motion-hold acquire over retry-only / relaxed-prior to fix first-acquire (E6); ceiling lifts to ≥1.0 m/s

- **Decision:** to fix the first-acquire reliability that E5 identified as the binding constraint,
  implemented **motion-hold acquire** (`--acquire-hold motion`): before the first lock, when blind,
  servo the PID on the largest ego-motion-compensated frame-diff blob (previous acquire-buffer frame
  warped onto the current pose, ≥0.35 s baseline; the car is the scene's only mover, so the diff is
  its swept region). This keeps the car in FOV across repeated VLM draws until one accepts. Pose
  comes free (SITL truth here; EKF on real hardware). Kept behind a flag; after the first lock the
  existing replay/DR/pursuit machinery owns all blind phases — the hold never re-engages.
- **Why over the alternatives:** (a) *retry-only / more attempts* — at ≥1.0 m/s the car leaves the
  FOV after ≤2 draws, so retries land on car-less frames; this is exactly what E5's p-1.0 already did
  32 times and it never locked. (b) *relax the size prior* — the Stage-0 diagnostic showed the prior
  correctly rejecting dash boxes (IoU 0.0 on every reject); relaxing it would admit wrong locks (E2's
  failure mode). The hold instead buys *time* for a correct draw without touching the prior.
- **Result / given up:** **RQ-E6 = YES** — ceiling lifts from 0.5 to ≥1.0 m/s (1.0 PASS 3/3, 0.5 no
  regression, 1.5 also PASS 3/3). The now-captured acquire_log confirms the mechanism: the VLM
  rejected 8-17 draws at 1.5 m/s yet in_fov_frac = 1.000 — the hold held the car in frame until a
  correct draw landed, with the prior untouched. Given up: 2.0 m/s (NadirCam texture only covers
  N∈[-20,140]; a 2.0 m/s car runs off the world — not testable on this rig). Residual next-lever
  candidate surfaced at 1.5: slower relock after occlusion (23-28 s vs ~7 s at 1.0), higher carry
  px_err — the relock/blind-recovery path, not first-acquire.
- → [`experiments/2026-07-03-first-acquire/`](../../experiments/2026-07-03-first-acquire/README.md)

### 2026-07-03 — Chose motion-consistency reground gate over CLIP/DR-radius (E7); NO — defeated by drive-through co-location

- **Chosen:** motion-consistency gate on REGROUND acceptance (accept a size-passing box only
  if its center lands on the ego-compensated mover blob + 60 px pad), reusing the committed,
  E6-validated `motion_blob`. **Over:** (a) a CLIP appearance gate — the SITL decoy is
  rendered with the *identical* polygon and color, so an embedding cannot separate them even
  in principle (rejected on validity, not cost); (b) a DR-position radius gate — needs a
  pixel-to-world drift calibration and a radius tuned to DR error growth, which E5 showed
  compounds during long blind phases (more machinery, weaker guarantee).
- **Result / given up:** **RQ-E7 = NO.** The gate correctly rejects *standalone* parked-decoy
  boxes (6-8 rejects/run vs 0 control) but the true car's drive-through past the parked decoy
  transiently co-locates it with the mover blob, so a decoy box eventually passes and the
  relock lands on the decoy 3/3 (`final_d_true` 4.05-4.32 m > 2.0). Regression legs held (no
  plain-occlusion regression). **Known limit, now demonstrated:** motion consistency is
  necessary but not sufficient against a same-appearance distractor sitting on the target's
  own path — the "moving same-appearance distractor" out-of-scope note has a static-but-
  co-located cousin the geometric gate also misses. Reground acceptance for an on-path
  same-appearance distractor is not solvable by geometry alone; it needs either identity
  (impossible here by construction) or a track-continuity/search behavior, not a filter.
- → [`experiments/2026-07-03-reground-gate/`](../../experiments/2026-07-03-reground-gate/README.md)

### 2026-07-03 — Chose the retarget path (E9) over a 1.5 m/s relock-latency fix and a wrong-lock search behavior; YES — the untested north-star verb works

- **Chosen:** exercise the mid-follow NL target switch (a co-moving BLUE **escort** twin the
  VLM can name by color + an `--retarget-t 50` state-machine swap that drops the carry and
  re-acquires under the new caption via the whole not-CARRY path). This is a whole untested
  verb of the north-star sentence ("switch to that blue truck"), it reuses the E3/E7/E8 twin
  metrics with only a verdict sign flip (post-switch the "distractor" IS the commanded
  target), and the SM change is small (swap the acquire closure, drop the carry). **Over:**
  (a) a 1.5 m/s first-acquire relock-latency fix — a quality improvement on a config that
  already PASSes (E5/E6), lower leverage; (b) a wrong-lock search behavior — a third run at
  the E3/E7/E8 adversarial decoy corner that two experiments already say needs identity, which
  the synthetic pixel-identical twin cannot provide (corner parked). The escort's *color* makes
  it NL-referable by construction, side-stepping the E3 identity impossibility.
- **Result / given up:** **RQ-E9 = YES** — smoke PASS (white 10/10, blue 10/10), ctl PASS,
  rt-a/b/c all PASS 7/7: switch locks the blue escort in 2.35 s (<< 15 s bar) and follows to
  trial end 3/3 at 0.5 m/s, in-FOV 1.000, ctl leg unbroken. The retarget verb works at the E6
  follow ceiling; the first post-switch draw returned the escort directly (single draw). Given
  up: the switch is only demonstrated at 0.5 m/s (E6 ceiling for the underlying relock path)
  and against a benign co-moving escort — a retarget onto a *crossing* or *counter-moving*
  target, and at higher speed, are the named next candidates. The VLM-draw non-cancellation
  quirk (max_workers=1) never bit: the switch resolved in one draw, so no queue delay appeared.
- → [`experiments/2026-07-03-retarget-switch/`](../../experiments/2026-07-03-retarget-switch/README.md)
