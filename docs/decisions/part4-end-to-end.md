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

### 2026-07-03T12:30Z — Notebook correction: "MAXN_SUPER" power-mode label was wrong; every run was at 15 W

- **What / why:** while pre-flighting E10 (fast-follow-ceiling) the Jetson power mode was
  audited against the hardware. `nvpmodel.conf` on this board (Orin Nano Dev Kit, L4T R36.5)
  defines **only** ID=0 **15 W** and ID=1 **7 W** — there is **no MAXN_SUPER / 25 W profile**.
  Part I (`experiments/2026-06-13-llamacpp-upper-bound`) and Part II
  (`docs/decisions/part2-rebuild.md`) had already established this, but several later records
  copied a "MAXN_SUPER + jetson_clocks" label anyway: E9 (retarget-switch, 4 spots), E7
  (reground-gate) and E8 (reground-selfcorrect) ("deployed MAXN config"), the Part-IV results
  row for E9, and the Part-I/II `2026-06-15-stage2-finetune` records (3 spots).
- **Impact — label only, zero numeric effect:** because 15 W was the *only* available mode,
  every "MAXN_SUPER" run physically executed at 15 W + jetson_clocks. **No measurement is
  invalidated and nothing is re-run.** The error was purely a mislabel.
- **Chosen:** correct all wrong labels to `15 W (mode 0) + jetson_clocks`, each pointing to
  `docs/decisions/part2-rebuild.md`, and note the correction inline. Left the already-correct
  Part-I/II records untouched. E10 is labelled 15 W from birth. **Over:** leaving the labels
  and adding a single global erratum note — rejected because the wrong label sits *in each
  run's config line*, exactly where a future reader (or the loop's Fable audit) reads the
  config to judge comparability, and would bias toward "match MAXN_SUPER" or treating 15 W
  runs as non-comparable. **Given up:** nothing — the correction costs only edits.
- **Standing rule:** this hardware has no MAXN_SUPER. All Jetson numbers are 15 W + jetson_clocks
  unless a future firmware flash adds a mode (would be a dated, explicit change).

### 2026-07-03T12:45Z — E10: probe the follow ceiling by removing the rig, not by adding a lever

- **What / why:** the follow "ceiling" was inherited as E2's "< 0.5 m/s", but the E10 audit
  found it never isolated the controller from the rig: the 140 m SITL world edge (car ran
  off-map) and three hard-coded caps (pursuit vmax 2.5, hist_vel clamp ±2.5, PID MAX_VX/VY
  3.0) all bit before the tracker did. **Chosen:** parameterize the three caps (`--vmax`,
  defaults bit-identical to E2-E9) + auto-extend the world texture per trial's reach, then run
  a plain speed ladder {1.5, 2.0, 2.5, 3.0}. This is a *measurement fix*, not a new capability —
  reg-1.5 confirms no ≤1.5 behavior change. Result: ceiling is **2.5 m/s**, 5x the E2 figure;
  the E2 number was a rig artifact.
- **Rejected alternatives (Fable named these; all deferred, not killed):** (1) **relock-latency
  cut at 1.5** — optimizing relock wall-time; rejected because E10 showed relock time *falls*
  with speed and in_fov stays 1.000 through occlusion, so relock latency is not the binding
  constraint. (2) **VLM draw-latency work** — speeding the acquire draw itself; deferred, but
  now *reframed*: E10 shows the constraint above 2.5 is first-acquire *reliability* (repeatable
  draw before the car crosses FOV from a standing start), which draw-latency work plausibly
  helps — this is the leading next candidate. (3) **on-device carry FPS** — moving SAM2 to the
  Jetson for throughput; rejected because carry held in_fov 1.000 at every passing speed, so
  carry FPS is not binding at ≤2.5 m/s.
- **Given up:** the ceiling is measured only for a *co-moving* target the copter is chasing
  from behind (the E2/E6 lineage scenario); crossing / counter-moving fast targets and the
  first-acquire-at-speed lever are the named next probes. The 3.0 failure is diagnosed
  (first-acquire) but not fixed — deliberately, as E10 was scoped to *locate* the ceiling, not
  raise it past 2.5.
- → [`experiments/2026-07-03-fast-follow-ceiling/`](../../experiments/2026-07-03-fast-follow-ceiling/README.md)

### 2026-07-03T13:40Z — E11: fix first-acquire-at-speed in the pre-lock control law, not the VLM

- **What / why:** E10 showed the follow ceiling is bound above 2.5 m/s by first-acquire, not
  tracking. The E11 audit sharpened *why*: E10's s3.0 raw shows the VLM got exactly **one**
  car-in-frame draw (submitted t≈0, lost the greedy lottery); by draw 2 (t≈2.3 s) the 3.0 m/s
  car had crossed the ±4.33 m half-footprint, and E6's position-only `motion` hold
  (`pid.compute(None)` → zeros) hovered on blob loss for the rest of the trial — 73 s of
  byte-identical empty-road draws. So the binding failure is the **pre-lock control law** (pre-lock
  `hist` is empty, so the proven DR/pursuit machinery never engages), NOT VLM draw repeatability
  (~74% accept on car-in-frame frames, E6 Stage-0). **Chosen:** `--acquire-hold chase` — pre-lock,
  each visible motion blob is converted to a world position and appended to `hist`, so the existing
  `hist_vel`→`pursuit_vel` DR chases the mover pre-lock (feed-forward while visible, DR when it
  outruns the FOV), buying car-in-frame time until the VLM locks. Minimal, default-preserving
  (`none`/`motion` never append to hist), reuses validated machinery. Result: s3.0 3/3, ceiling
  moved to **>= 3.5 m/s**.
- **Rejected alternatives (Fable named these):** (1) **blob-seeded CARRY** — hand the pre-lock
  blob straight to SAM2 as the track; rejected as identity-blind (E3: size prior can't tell the
  target from a decoy) and a large state-machine change vs the small pre-lock-hint chase. (2)
  **VLM draw-latency cut** — speed the acquire draw; rejected because the audit showed latency is
  not binding (the VLM *did* draw; the car left frame between draws), and the E9 max_workers=1
  non-cancellation quirk makes faster draws risky. (3) **spawn-geometry sweep** — vary heading /
  crossing angle to characterize the acquire lottery; rejected because the mechanism was already
  unambiguous from the s3.0 raw, so a sweep would spend the cycle measuring instead of fixing.
- **Given up:** the ceiling is now **unpinned** (>= 3.5, top rung tested) — E11 under-reached its
  own ceiling, so the next campaign must probe higher (4.0+) to find where chase-hold actually
  breaks and what the new binding mode there is. Still only the co-moving chase-from-behind
  scenario; crossing / counter-moving fast targets remain untested. The pre-lock chase has no
  timeout guard (a garbage early blob could DR-runaway north at vmax) — it did not bite on any
  E11 leg, but it is an un-guarded edge, deliberately left as a design fact to revisit if it ever
  fires.
- → [`experiments/2026-07-03-chase-acquire/`](../../experiments/2026-07-03-chase-acquire/README.md)

### 2026-07-03T16:25Z — E12: validate the E11 ceiling by hard-spawn (remove the gift frame), not by probing upward

- **What:** the E11 audit (Fable) flagged E11's ">= 3.5 m/s" as under-supported. The E11 s3.5
  passes locked at `acquire_log[0]` = 2.30 s on the t=0 easy frame, but `in_fov` had already
  fallen 1→0 at t=2.25 s — the lock landed on a car that had left the FOV, so the pre-lock blind
  chase was never actually exercised at 3.5. E12 added `--acquire-delay 3.0` (default 0.0 =
  bit-identical) to block any lock before t=3 s, forcing the chase to earn the lock, and re-ran a
  d3.0 control (genuine at E11) + d3.5 ×3.
- **Why this over the alternative — probing 4.0/4.5 upward:** a higher probe would have stacked a
  new optimistic top rung on top of an unvalidated one; the honest move is to first pin whether
  3.5 is even real. Removing the gift frame is the minimal, decisive test — it isolates the
  pre-lock chase as the mechanism instead of the spawn geometry. Rejected the upward probe as
  "measuring before validating."
- **Result:** d3.5 **0/3** never-locked (blind DR can't re-close on a 3.5 m/s escaper before the
  first legal draw), d3.0 PASS (locks 12.17 s, ≈3 s later than the gift-frame 9.2 s — the genuine
  re-close costs the delay it was denied). **Chase-validated ceiling demoted 3.5 → 3.0 m/s.**
- **Given up:** the optimistic ">= 3.5" number; the ceiling is now a defensible, pinned 3.0 m/s.
  The next lever past 3.0 is pre-lock chase *reach* (DR gain, or a faster first draw so the target
  is still near the footprint when the chase seeds), not the tracker or carry. Audit evidence:
  s3.5a/b `acquire_log[0]` accept at 2.30 s with in_fov 1→0 at 2.25 s (gift frame); s3.0a copter
  translated N 0→26 m through ACQUIRE (genuine chase).
- → [`experiments/2026-07-03-late-command/`](../../experiments/2026-07-03-late-command/README.md)

### 2026-07-03 — E13: shade-215 decoy rig + colour-descriptor gate over CLIP ([`experiments/2026-07-03-identity-gate/`](../../experiments/2026-07-03-identity-gate/README.md))

- **Decision (rig):** test the appearance gate against a **discriminable same-class** decoy
  (`--decoy-shade 215`, grey-white) rather than E3's byte-identical twin (`245`). A byte-identical
  twin is unsolvable for ANY appearance mechanism information-theoretically — E7 rejected CLIP on
  exactly that. 215 is still emphatically "a white car" in this palette (road dash 200, parapet
  140) and the smoke precondition *checks* it (VLM boxes the 215 decoy as "the white car" 10/10;
  ctl still wrong-locks), so the test is fair and the negative is attributable to the gate, not the
  rig. **Given up:** the strongest adversarial case (identical twin) stays a recorded theoretical
  bound, not a claim.
- **Decision (mechanism):** a **zero-dependency colour descriptor** (mean BGR of the crop's
  brightest quartile, max-channel ranked) over CLIP crop-embedding similarity. Rejected CLIP on
  cost + necessity, not validity: an extra co-resident model on the 8 GB Jetson (or a host
  dependency) + ~100s-of-ms/check, against a discriminandum this rig renders only as a colour/shape
  difference that a 3-channel statistic separates 30-to-0 at microseconds. Laziest gate that could
  discriminate.
- **Result: RQ-E13 = NO.** The colour gate fires correctly (14-26 rejects/leg, template
  `[245,245,245]`) but is defeated by a **two-car blend box** whose bright quartile is dominated by
  the emerging true car's 245 pixels (passes tau) while the box centres on the decoy (SAM2 latches
  the decoy). 0/3, ends wrong-locked ~26.5 m from true. Regression clean.
- **What this buys the thesis:** the identity hole now has **three** failed cues — size (E3),
  motion (E7), colour (E13) — and they fail for one shared reason: each is a global cue over the
  proposed *box*, not bound to the tracked *instance*. That sharpens the next lever from "try
  another cue" to "bind identity to the segmented mask" — an embedding on the SAM2 mask, or
  rejecting blend/oversized boxes at REGROUND before any descriptor. CLIP is not re-opened by
  this result (a mask-embedding, cheap or not, is the structural fix; CLIP-on-a-box would inherit
  the same blend-box defeat).
- **Process note (Opus):** the ctl-decoy attribution rule (literal `relock_on[0]=="distractor"`)
  was written for E3/E7's single-reground 75 s trials; the 150 s control fired 10 regrounds with a
  transient `relock_on[0]="true"` yet ended firmly on the decoy. Applied the rule's *intent*
  (decoy captures REGROUND — satisfied by `closest_at_end`/`final_d_true`/terminal relock) →
  NO, not NOT-MEASURABLE. Flagged in the README for the next-cycle audit. Future decoy-leg
  attribution should key on `closest_at_end`/`final_d_true`, not `relock_on[0]`, when trials run
  long enough to reground multiple times.

## E14 — bind the REGROUND identity gate to the SAM2 mask, not the box crop (2026-07-03)

- **Decision:** close the identity hole with a **mask-bound median** REGROUND gate: on a
  size-passing reground, run the exact StreamCarry init the accept would run and take the
  per-channel *median* BGR over its frame-0 SAM2 mask (the instance actually latched); accept iff
  L-inf ≤ tau 12 vs the template bound at NL grounding. Off by default (`--reground-gate mask`),
  consulted only on REGROUND after the size prior. **Result: RQ-E14 = YES**, mk-decoy 3/3
  (final_d_true 0.21 m), zero regression. First identity cue to survive the two-car blend box.
- **Why the mask median (not the crop):** E13 proved a crop statistic answers "is the template
  colour *present* in this box?" — a two-car blend box says yes (245 true pixels inside) while
  SAM2 latches the decoy it centres on. The median over the *mask* answers "what did SAM2
  *actually latch*?" — a majority vote that reads 215 for a majority-decoy blend even with true
  pixels present. It needs >50% true content to flip, vs E13's brightest-quartile flipping at
  ≥25%. Binding the descriptor to the segmented instance, not the proposed box, is the structural
  fix the whole E3/E7/E13 arc pointed to.
- **Alternatives rejected (given up):**
  - *Geometry blend-box pre-filter* (reject reground boxes much larger than the last-known target
    box before any descriptor). Rejected: a fourth instance-blind global cue that stacks another
    tunable and would reject a legitimately loose-but-correct box with no path to accept. The mask
    gate needs no size-ratio threshold and admits a correct loose box as long as the latch is the
    true car.
  - *CLIP crop embedding* (E13's other named alternative). Rejected: crop-based, so it inherits the
    exact blend-box defeat (the embedding of a two-car crop is not the embedding of the latched
    car), at ~10× the descriptor cost. The blend diagnosis strengthens E13's cost-based rejection.
- **What it costs:** ~40 ms per consulted REGROUND resolve (a throwaway StreamCarry init on the
  host predictor); negligible against the ~2.3 s VLM draw cadence. And the gate is **local-carry
  only** — it verifies with the host SAM2 predictor, so the 3b remote-carry path is unported and a
  `--remote-carry` run is refused at startup. Porting to remote carry is deferred (open question).
- **What it does NOT claim:** reliability was shown for one discriminable decoy shade (215 vs 245),
  a single distractor, and a clean physical separation of the two cars. Near-identical shades, >2
  distractors, and re-occlusion during separation are untested — the win path depends on the VLM
  producing a clean separated true box (reject-until-separated), which a persistent co-location
  would starve. That is the next lever if harder ambiguity breaks it.

## E15 — geometry stress of the E14 gate; direction (a) over (b) (2026-07-03)

- **Design choice (Fable):** harden the E14 gate against **win-path geometry** — a double-decoy
  with no clean window (`--decoy2 7.0`) and a re-occlusion covering E14's accept window
  (`--occ2 82 10`) — rather than (b) move to the next constraint. Rationale: E14's "identity hole
  closed 3/3" is load-bearing for the thesis but the audit showed the 3/3 was three near-identical
  replays of ONE favourable geometry, and the shade margin is *analytic* in this flat-shaded
  renderer (mask median == body shade, zero variance → a shade sweep measures the constant tau), so
  geometry is the only real untested axis. Rejected: (b) the 3b remote-carry port (right step only
  AFTER robustness; a heavy multi-file port is the wrong shape for a zero-judgment executor), a
  shade-convergence sweep (analytic), and pre-lock chase-reach >3.0 m/s (E12 parked that arc).
- **Outcome: RQ-E15 = NOT-MEASURABLE** — and the finding is a *process* one that outranks the
  designed question. The regression guard leg (reg-e14, E14's exact config under the E15 code)
  FAILed with no-relock where E14 passed 3/3. The pre-registered rule correctly halted attribution.
  What this buys the thesis, and the decision it forces on the next cycle:
  - **E14's robustness is now an open question, not a settled claim.** The gate's *rejection* of
    decoy/blend boxes is rock-solid (0 false accepts across every gated leg, controls wrong-lock
    every time). The *reject-until-separated win path* — waiting for a clean true box to appear and
    catching it — is what looks fragile: the easiest leg missed its accept window while 5/6 harder
    legs caught theirs (t≈100–114). This is consistent with a narrow, stochastically-missable accept
    window, which n=3 in E14 could not have exposed.
  - **Decision for the next cycle (seed):** before any further hardening or the remote-carry port,
    the highest-leverage move is a *determinism characterization* — re-run E14's exact mk-decoy
    config at n≥3 on the **merged E14 code** (no E15 patch present) and, separately, on the E15 code,
    to split "E15 patch perturbed the E14 path" from "E14's win is stochastic." Only one of those two
    is a real E14 caveat; the other is an E15 instrument bug. The `np.array_equal` render-identity
    selfcheck is necessary but insufficient — it proves the frame is identical, not that the
    SITL/VLM/pursuit *timing* is bit-identical across the closest_label/multi-bridge/sitl_cam deltas.
    Future off-by-default patches touching the shared harness should include a behavioral
    baseline-parity leg in the *same* matrix, not just a render-identity assert.
  - **What was given up by merging a NOT-MEASURABLE:** nothing on `main` behaves differently (the E15
    knobs are off by default; E2–E14 configs render bit-identically per selfcheck). The cost is one
    cycle that produced a limiting result rather than a robustness confirmation — but per the loop
    design that is thesis content, and the next-cycle audit inherits a sharp, well-scoped question.

### E16 relock-rate (2026-07-03) — fixed-code replication over the git-worktree A/B

- **Chosen:** measure E14's mask-gate relock rate by n=8 fixed-code replication of its byte-identical
  config on **current main** (the E15 merge, knobs off), with a no-gate ctl rig-drift guard and a
  mechanical rate verdict (RELIABLE/QUALIFIED/FRAGILE). Result: **QUALIFIED, r=6/8** — the gate's
  rejection is solid (0/8 identity breaches) but the reject-until-separated re-acquire wins ~75%,
  bounded by the VLM offering a clean post-separation box, not by the gate.
- **Rejected — the git-worktree A/B E15 seeded** (re-run E14's config on E14 code vs E15 code to split
  patch-vs-rig): Fable's cycle-4 audit already discriminated it — reg-e14's trajectory prefix is
  byte-identical to two E14 replicates that PASSed, the E15 patch never touched the acquire/gate path,
  and achieved_hz was identical (19.6-19.8), so there is no patch mechanism or signature. An n<=5/arm
  A/B is also underpowered for a ~0.75 rate. The decision-relevant number is main's rate, which the
  fixed-code run gives directly. Given up: a formal patch-vs-rig isolation — but the audit + the
  matching rate make E15's reg-e14 FAIL a plain draw from this distribution, so the isolation is moot.
- **Rejected — the E3b CLIP appearance-embedding theme:** stale. Crop-based cues (colour E13, and CLIP
  crop similarity) structurally fail the two-car blend box for the same reason size/motion did — they
  do not bind to the tracked instance; the mask-median gate is the structural fix and it holds. No new
  lever belongs on an unmeasured foundation; measure the foundation first (this experiment).
- **Rejected — re-attributing E15's stress families (dd/ro):** uninterpretable without a passing
  baseline rate, which is exactly what this experiment establishes; revisit only if a future harder
  scenario is worth its own pre-registration.
- **Correction recorded:** E15's README/ledger stated E14 accepted "at t=86.25 in all three" mk-decoy
  replicates. False — E14's accepts were 76.55/81.38/86.25 s with two distinct init boxes; E14 already
  varied under fixed code. The "near-deterministic rig" assumption that made reg-e14's FAIL look like a
  regression was stale. Lesson reaffirmed: an off-by-default patch's render-identity assert
  (`np.array_equal`) is necessary but not sufficient — behaviour varies run-to-run under identical
  code, so a rate (n>=3, independent process launches) is the only honest read of a stochastic win path.

### E17 reground-chase (2026-07-03) — extend E11 chase-hold to REGROUND; rejected (regressed the rate)

- **Chosen (as the final-cycle experiment):** test whether E11's validated pre-lock blob-chase,
  extended to REGROUND blind phases (`--reground-hold chase`, off by default), lifts E16's 6/8
  re-acquire rate. Rationale: E16's audit isolated both FAILs as FOV-loss during REGROUND (rg_fov
  discriminates PASS 1.000 from FAIL 0.20-0.51 perfectly), and the failure looked like passive
  DR-coast drifting off the mover — for which an *already-validated* fix (E11 chase-hold) existed,
  gated pre-first-lock only. **Result: rejected — r=0/10, a hard regression from 6/8.**
- **Why it backfired (the finding worth more than a PASS would have been):** the premise "chase =
  keep the car in FOV" is false in REGROUND. Pre-first-lock (where E11 validated it) the scene has
  one dominant blob — the target — so the chase servos toward it. In REGROUND the target is lost and
  the *decoy* is the dominant blob, so the chase servos onto the decoy and drives the drone ~82 m off
  (vs passive DR-coast's ~27 m worst). The lever's proximal metric inverted (rg_fov 0.025, not the
  predicted >=0.95). A control law validated in one regime does NOT transfer to a superficially
  similar one when the blob it locks onto changes identity. E16's passive DR-coast stands as the best
  REGROUND policy.
- **Guards (kept):** the 3.0 m/s honest-ceiling guard legs both PASS with the lever on, so the
  regression is specific to slow-mover REGROUND, not a follow-ceiling break — worth recording that
  the lever is *safe* at follow speed even though it is *useless* (harmful) for re-acquisition.
- **Rejected alternatives (seeded by the audit):** the E3b CLIP appearance gate (stale — E16 proved
  re-acquire is already identity-safe, 0 breaches in 8; discrimination is not the problem); an
  accept-hysteresis / accept-window widener (would touch the accept path E16 showed is upstream-bound
  by the VLM's clean-box offer, not by timing on our side); a 3.0 m/s decoy characterization (the
  guards already confirm no ceiling regression); a longer-duration re-run baseline arm (E16 already
  gives the 6/8 baseline). What was given up by picking the chase lever: a direct attempt at the
  upstream bound (VLM box-offer reliability in the separation window) — but that needs a
  grounding-side change out of this loop's scope, and is the clean next thread if the work resumes.
- **Arc closed:** across E3/E7/E13 (identity cues, all NO) -> E14/E16 (mask gate, identity-safe at
  ~0.75) -> E17 (pursuit lever, NO), the standing answer is the E14/E16 mask-median REGROUND gate:
  it never wrong-locks the twin, and the residual ~25% miss is an upstream VLM limit that a
  pursuit-side lever cannot touch. Next thread (out of loop): lift the VLM's clean-box offer rate in
  the post-separation window.

### 2026-07-03 — E18: dataset = UAV123 car sequences (D2); host rig at the measured on-Orin carry cap (D3)

- **D2 — dataset: UAV123, car-class sequences.** *What:* score the real-footage test on UAV123 aerial
  vehicle-tracking clips (per-frame `x,y,w,h` GT, NaN = absent, 30 fps); 6 sequences chosen — 4 plain
  {car3, car9, car14(occ), car18} + 2 distractor {car7(occ), car10}, all 1280×720, standalone (not
  split `carN_M`), `_s` flight-sim sequences excluded (synthetic). *Why:* it is the exact thesis
  scenario (aerial cars) with quantitative GT, so the RQ can be scored, not eyeballed. *Given up:*
  own-drone footage (no GT → no quantitative claim); the VisDrone2019-SOT fallback (D2) went unused —
  UAV123 downloaded in ~1 h via the HF mirror `xche32/UAV123`, well inside the ~2 h fallback budget.
  Practical: the 14 GB tarball did not fit (ENOSPC) → selectively extracted the 6 seqs + anno (~1.1 GB)
  and deleted the tarball (re-downloadable, documented in the campaign README).
- **D3 — host rig with the measured on-device carry cap, not on-Jetson orchestration.** *What:* run
  the carry tier on the 3090 but rate-cap it to 6.15 Hz (E1's measured co-resident TensorRT number on
  the Orin) and run the acquire tier as REAL Jetson wall time (q8_0 self-boot per run). *Why:* cadence
  is already pinned by E1; the new variable in E18 is the DATA, and a fresh on-Jetson replay harness
  would add failure modes without adding information. *Given up:* exact on-device 720p SAM2 timing (may
  run slightly under 6.15 Hz measured at 640×480) — recorded as a known approximation; an on-Jetson
  replay is the natural E19 if E18 had been YES. *Consequence realised:* the finding turned out to live
  in the acquire tier's ~4.85 s latency (real Jetson time, faithfully measured) — exactly the axis D3
  kept honest, so the [grounding-bound] verdict is not a rig artifact.
