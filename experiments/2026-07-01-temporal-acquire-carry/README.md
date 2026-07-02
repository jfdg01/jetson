# Temporal follow — acquire-once + memory-carry ("follow the white car")

**Date:** 2026-07-01T15:05Z (pre-registration) · **Branch:** `experiment/temporal-carry` (off `main` @ `a2fd695`)
**Status:** Phase 0 **PASS** (RQ-T.1) · demo committed · **Phase 2 RUNNING** (Jetson benches done, 512 accuracy re-eval sweeping on the 3090). Phases 1, 3 pending.
**Train box (reserved lever only):** local RTX 3090 24 GB, `.venv-ft`, python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6, peft 0.19.1 (git_sha `6d9d3a2` at draft).
**Deploy / latency box:** Jetson Orin Nano 8 GB @ **15 W** (`nvpmodel -m 0` + `jetson_clocks`).
**Stack-native runtime:** llama.cpp `57fe1f0` CUDA sm_87 (`llama-server`, Q8_0, ngl=99) for the acquire VLM. Memory-carry runtime = TensorRT/ONNX (off-stack, same export path as the bake-off's arms C/D — recorded per phase).
**New tracker deps:** `sam2==1.1.0` pinned into `.venv-ft` (`requirements-ft.txt` + lock refreshed 2026-07-02); weights `facebook/sam2.1-hiera-tiny` via HF hub. (The `sam2._C` CUDA-ext warning at import is expected — hole-filling post-processing only, results unaffected per upstream INSTALL.md.)
**Data:** AerialMind (RMOT: referring expr + track-IDs + frames), **pulled local** `data/AerialMind/` (gitignored) — **93 sequences** confirmed on disk (`expression/`, `image_02/`, `labels_with_ids/`). RefDrone (single-frame) for the acquire VLM — unchanged from v2/v3.

## Goal (the north star this experiment serves)

Tell a drone **"follow the white car"** and have it comply. Everything below is scoped to that
one sentence: a single, appearance-named, physical target the drone acquires once and follows.

## Question

The whole v2/v3 line runs a **single-frame VLM on the hot path every frame** and fakes persistence
with ByteTrack + a ~2 s ROI re-anchor. That is (a) slow — per-frame grounding runs sub-1 FPS, so
the control loop can't keep a moving car framed — and (b) has no temporal representation: "object
permanence" is a heuristic patch over independent per-frame decisions. The architecture is sound
enough to have taught us the levers (ROI crop, terse output), but it is the wrong shape for a
moving target.

**Does re-layering to acquire-once + memory-carry — demote the VLM to a one-shot acquirer, carry
the target with a stateful memory tracker (SAM2-family), re-invoke language only on lock-loss —
give a temporally-resilient "follow the white car" loop that keeps the target framed and survives
occlusion, ideally with no new trained temporal model?**

## Design rationale (the decisions, pre-registered with what's given up)

- **★ Acquire-time identity — referring binds ONCE, tracking is pure appearance thereafter.**
  "The white car" names one physical object; the drone follows *that* car even if a second white
  car appears. *Why:* it is the matched semantics for the goal and it is the cheapest — no per-frame
  language. *Given up:* continuous semantic re-binding (expressions like "whoever is now nearest the
  building" are out of scope; those force the heavier RMOT paradigm, explicitly not chosen).
- **★ Zero-shot memory-carry FIRST; temporal fine-tuning is the reserved lever.** Test off-the-shelf
  SAM2-tiny/EdgeTAM carry before building anything trainable. *Why:* SAM2 is class-agnostic and
  strong zero-shot; if it holds on aerial, the "rewrite" collapses to integration + eval. *Given up:*
  possibly better in-domain carry — pulled only if Phase 0 shows zero-shot fails (same discipline as
  the bake-off's reserved vision-tower unfreeze).
- **Memory-carry (SAM2-family) over a plain visual SOT.** *Why:* a memory bank re-associates after
  occlusion / frame-exit — the actual object-permanence mechanism, not a heuristic. *Given up:* SOT
  is cheaper; it is held as the fallback if SAM2 won't hit the FPS gate on-device (Phase 2).
- **AerialMind for EVAL, not training (initially).** *Why:* it supervises the one thing v2/v3 could
  never measure — ID-consistency of the *right* track through occlusion. Training use is gated behind
  a zero-shot failure.
- **Reuse the acquire stack whole.** The fine-tuned VLM + `grounding/` (`contract.py`, `roi.py`,
  `deploy/serve.py`, `eval/backends.py`) become the one-shot acquire step unchanged. *Why:* the
  grounding model isn't the flaw; its position on the hot path is. This is a re-layer, not a rebuild.

## Pre-registration

### Research questions

- **RQ-T.1 (zero-shot carry — make-or-break):** Does off-the-shelf SAM2-tiny/EdgeTAM carry a
  first-frame-boxed aerial target across an AerialMind sequence *without temporal fine-tuning*?
  Measured by track-IoU and ID-consistency through occlusion vs the ground-truth track-ID.
- **RQ-T.2 (loop rate — the real win):** Does acquire-once + memory-carry hit **≥ 5 FPS** control-loop
  rate on the Jetson @ 15 W, vs the sub-1 FPS per-frame-grounding baseline?
- **RQ-T.3 (fit):** Do the acquire VLM (~4.6 GB Q8_0) and the carry tracker co-reside in 8 GB, or is
  load-on-demand forced — and if so, what is the re-ground reload cost?
- **RQ-T.4 (permanence):** Does memory re-association recover the target after full occlusion /
  frame-exit, where the v3 heuristic must re-ground blind?
- **RQ-T.5 (end-to-end):** In SITL, does "follow the white car" keep the car in frame across a
  trajectory with an occlusion event, closed-loop?

### Phases (gated; a later phase runs only if the earlier gate holds)

| Phase | What | Box | Contends with sweep? | Gate |
|---|---|---|---|---|
| **0** | AerialMind loader + temporal eval harness; zero-shot SAM2-tiny/EdgeTAM carry scored (track-IoU, ID-consistency, occlusion recovery) | CPU (local) | **No** — buildable now | RQ-T.1: carry holds; else pull the training lever |
| **1** | SITL oracle-follow control slice — perception-free (`oracle_bbox`), control keeps a moving white car framed, re-ground trigger fires on synthetic loss | CPU / SITL | **No** | RQ-T.5 skeleton: target stays framed with a perfect box |
| **2** | Jetson feasibility — SAM2 variant FPS + VLM co-residency in 8 GB (`tegrastats` peak RAM) | **Jetson** | **Yes** (queues behind sweep) | RQ-T.2 (≥5 FPS) + RQ-T.3 (fit) |
| **3** | Integrated — swap oracle→SAM2 carry→VLM acquire, SITL then on-device; full "follow the white car" | SITL + Jetson | **Yes** | RQ-T.4 + RQ-T.5 end-to-end |

### Success criterion (gate)

The experiment **succeeds** if a fully-integrated loop (Phase 3) keeps "the white car" in frame
across a SITL trajectory *with* an occlusion event, at ≥5 FPS control rate on-device, using the
acquire VLM only at start + on lock-loss. A **documented negative** — e.g. zero-shot carry collapses
on aerial (RQ-T.1), or the tracker can't hit 5 FPS on the Orin Nano (RQ-T.2) — is thesis content,
not a failure of the campaign: it names the reserved lever (temporal training) or the fallback
(visual SOT) to pull next.

## Method (entry points — mostly reuse; new pieces flagged)

1. **Acquire (reuse):** `grounding/deploy/serve.py` + `eval/backends.py` — VLM grounds the expression
   once → box. ROI crop (`roi.py`) may sharpen the acquire box before handoff.
2. **Carry (NEW):** SAM2-tiny / EdgeTAM, box-prompted on the acquire frame, memory-propagated per
   frame → mask → box (bbox of mask). Stateful — holds a memory bank across frames, unlike the
   stateless llama-server request/response.
3. **Orchestrator (NEW — the backbone):** a streaming loop owning the `ACQUIRE → CARRY → REGROUND`
   state machine, the frame pump, the tracker session, and the box→control handoff. This replaces
   the request/response *shape*, not any single model.
4. **Re-ground trigger (NEW — small):** threshold SAM2's per-frame object/occlusion score over N
   frames → re-invoke the VLM with the same expression. Threshold + hysteresis calibrated on
   AerialMind occlusion clips.
5. **Control (reuse):** mask centroid + area → `cascade_pid.py` → `offboard.py` (pymavlink offboard).
6. **Eval (NEW, CPU):** AerialMind loader (expr + track-IDs + frames) → run carry → score
   track-IoU / ID-consistency / occlusion-recovery.

## Estimates (up-front priors — mark as ESTIMATE, record actual-vs-estimate in Results)

Weak priors, stated so a wrong one becomes content.

| Quantity | Estimate | Confidence | Note |
|---|---|---|---|
| SAM2-tiny / EdgeTAM FPS, Orin Nano 8 GB @ 15 W | ~5–15 FPS (TensorRT) | **low** | EdgeTAM claims ~16 FPS on iPhone; Orin Nano unverified — the load-bearing number |
| Co-resident RAM (VLM Q8_0 + tiny tracker) | ~4.6 + ~0.3–0.5 GB ≈ 5–5.5 GB | medium | fits 8 GB but tight with KV cache; co-residency vs load-on-demand TBD |
| Zero-shot carry track-IoU on AerialMind | **honestly unknown** (aerial is OOD for SAM2) | **very low** | RQ-T.1 is exactly this question — no credible prior |
| New trained temporal model needed? | **probably not** (bet: zero-shot suffices) | low | the whole lazy hypothesis; Phase 0 decides |
| Control-loop rate, integrated | ≥5 FPS target vs sub-1 FPS baseline | medium | the win is the order-of-magnitude gap, not the exact number |

**Est. effort:** Phase 0 ~1–2 days (loader + harness + zero-shot run, CPU). Phase 1 ~1–2 days (SITL
control slice). Phases 2–3 gated on the sweep freeing the Jetson + on Phase 0/1 holding. Plan as a
**multi-session** campaign; Phases 0–1 can start immediately with zero sweep contention.

## Results

Fill per phase; record **actual** next to the estimate above and flag divergence.

| Phase | RQ | metric | result (Δ vs est.) | verdict |
|---|---|---|---|---|
| 0 | RQ-T.1 | track-IoU / ID-consistency / occ-recovery, zero-shot | mean IoU **0.602**, IoU@0.25 **0.849**, IoU@0.5 0.750, ID-consistency **0.891**, occ-recovery **0.329** (70 gaps), pred-absent 3.5%, 14.4 FPS on 3090; 186 tracks (93 seqs × 2, cap 300), 58.4 min wall (est. 45–90 min — inside band) | **PASS — carry holds zero-shot;** training lever stays unpulled. Occ-recovery 33% = REGROUND's job, not carry's |
| 1 | RQ-T.5 (skeleton) | target-in-frame fraction, oracle box | 0.25 m/s: in-FOV **1.000**, lock @4.31 s, occlusion relock **4.46 s** after LossGate, px-err 16.1 (est. PASS — right); 0.5 m/s: in-FOV **1.000**, relock 4.21 s, px-err 32.0 (est. "marginal" — cleaner than feared); 1.0 m/s: in-FOV **0.482**, locked @4.36 s but target exits FOV during occlusion+reground blind window, 8 failed re-acquires, never recovers (est. "never locks" — FAIL as predicted, but the *mechanism* differed: first acquire succeeded, recovery is what breaks) | **PASS — gate holds at 0.25 m/s (and 0.5); 1.0 m/s is the documented speed ceiling** |
| 2 | RQ-T.2 / T.3 | FPS @ 15 W; peak RAM co-resident | @1024: **2.68 FPS** (p50 373 ms, est. 1.5–4 — inside band, gate FAIL); @512: **12.13 FPS** (p50 82.5 ms, est. 4–10 — *above* band); co-resident @1024 with VLM Q8_0 server: **2.68 FPS unchanged, server survived, peak RAM 6963/7607 MB** (est. "likely does not fit" — **wrong**, fits with ~650 MB headroom); 100/100 masks non-empty in all passes | RQ-T.2 **FAIL @1024, PASS @512** (accuracy re-eval at 512: _running on 3090_); RQ-T.3 **PASS — co-residency holds, no load-on-demand needed** |
| 3 | RQ-T.4 / T.5 | occlusion recovery; in-frame fraction, integrated | _pending_ | _pending_ |

Phase 0 config: SAM2.1-hiera-tiny (`sam2==1.1.0`), fp32 weights under bf16 autocast, box prompt =
first GT frame, `offload_video_to_cpu=True`, /dev/shm symlink window; scored on labeled frames only.
Run: `runs/phase0-zeroshot-carry/` (per_track.csv + results.json + manifest), log `raw/`.
First launch was killed at 42/93 and invalidated by the GT decode bug (see Status 16:25Z entry).

Phase 2 config: Orin Nano 8 GB, **15 W + jetson_clocks**, L4T R36.5.0, CUDA 12.6,
`torch==2.8.0` / `sam2==1.1.0` in `~/sam2-bench/.venv` (install actuals in Status 18:45Z entry);
`jetson_carry_bench.py`, M0205 frames 395–494 (100 frames, 1024x540), box prompt = GT tid 20
@ frame 395, bf16 autocast, FPS = steady-state propagate (5 warmup frames dropped). Co-residency
pass: the deployed `llama-server` boot line from `grounding/eval/backends.py` (Q8_0 +
mmproj, `-ngl 99 -c 4096 -np 1 --cache-ram 0 --no-cache-idle-slots`), healthy in 8 s, idle
during propagation. Raw: `raw/phase2-jetson/` (bench JSONs + tegrastats logs); 512 accuracy
re-eval → `runs/phase2-carry-512/`, log `raw/phase2-carry-512.log`.

Phase 1 config: ArduCopter SITL (CMAC home, GUIDED, 10 m AGL, gimbal-level oracle, yaw PID off per
Phase B), copter SITL only — rover programmatic north at trial speed, anchored to fresh
LOCAL_POSITION_NED per trial. Injected costs: latency U(4.1, 4.6) s, parse-fail p=0.007, occlusion
5 s @ t=30 s, LossGate 60 no-box frames @ 20 Hz. 75 s/trial, seed 7+i. `phase1_sitl.py`
(state-machine selfcheck: `--selfcheck`); raw: `raw/phase1-sitl/` (per-frame CSVs + SITL log),
`runs/phase1-sitl/` (results.json + manifest), log `raw/phase1-sitl.log`.

## Findings

- **RQ-T.1 PASS (the make-or-break):** zero-shot SAM2.1-tiny carries aerial targets from one box
  prompt — IoU@0.25 0.849 / ID-consistency 0.891 across 186 tracks. The "aerial is OOD, honestly
  unknown" prior resolved *favorably*; no temporal fine-tune needed. The carry tier matches the
  deployed v3 re-anchor loop's accuracy (85.2%) **without any per-frame VLM calls**.
- **Occlusion recovery is the weak tier, as designed:** after a ≥3-frame GT gap, memory re-associates
  within 5 labeled frames only 32.9% of the time (70 events). This is precisely the REGROUND
  trigger's job — the demo's LossGate (75-frame streak) covers it. Not a blocker; it defines the
  REGROUND budget for Phase 1's latency-injection test.
- **Demo (committed `ab6d6d7`, videos in `raw/`):** end-to-end ACQUIRE→CARRY on real Jetson VLM
  acquire (4.1–4.6 s wall): occlusion clip mean IoU 0.886 through a 40-frame GT gap with zero
  re-grounds; **RETARGET** (mid-video caption switch = fresh acquire + `reset_state`) works — truck
  → "the black car" @500, retarget IoU 0.721, mean 0.887.
- **Negative (kept):** AerialMind *behavioral* captions ("Black car invading other lanes", "The
  parked taxi") ground at IoU 0.0 from a single frame — the VLM returns a plausible *appearance*
  match; behavior is invisible in one frame. Single-frame acquire needs appearance-style captions;
  behavioral referring expressions are themselves an argument for the temporal tier.
- **RQ-T.5 skeleton PASS, and the failure boundary is mapped:** with perfect perception and only
  the temporal design's *costs* injected (4.1–4.6 s blind acquire, 0.7% parse-fail, 5 s occlusion,
  3 s LossGate), the follow loop holds at 0.25 and 0.5 m/s with in-FOV = 1.000 and occlusion relock
  in ~4.2–4.5 s (one reground, exactly one LossGate trip — the machine behaves as designed). At
  1.0 m/s the loop *locks* fine (4.36 s) but cannot survive the occlusion: LossGate (3 s) + acquire
  latency (~4.3 s) is a ~7.3 s blind window during which a 1 m/s target exits the 10 m-AGL footprint
  — 8 consecutive failed re-acquires, never recovers. **The speed ceiling is set by the REGROUND
  blind window, not by first acquire or by PID tracking** — pre-registered estimate had the right
  verdict (1.0 m/s FAIL) for the wrong mechanism (predicted first-acquire failure; actual geometry
  gives more first-lock margin than the naive N-S half-footprint suggested). Levers if a faster
  ceiling is ever needed: shorter LossGate, search-pattern motion during REGROUND (climb = wider
  footprint), or velocity extrapolation during the blind window.
- **Dataset gotcha (cost ~28 min GPU + a morning):** AerialMind `labels_with_ids` stores `x y w h`
  with `x,y` = box **top-left**, *not* the JDE center convention the filename layout implies. Center
  decoding shifts every box up-left by half its size — plausible-looking but wrong everywhere
  (out-of-bounds "clamping" at parse was a symptom, not a fix). Verified visually before re-running.

## Decision

TBD — does acquire-once + memory-carry replace the per-frame v2/v3 pipeline (and if so, is the
carry zero-shot or trained; SAM2 or SOT), with what was given up.

## Risks / honest caveats (pre-registered)

- **FPS is unverified and load-bearing.** If SAM2-tiny can't clear ~5 FPS on the Orin Nano, Phase 2
  fails the gate and the design degrades to the visual-SOT fallback. This is the single biggest risk.
- **Zero-shot carry on aerial is a genuine unknown.** SAM2 is trained on natural video; small,
  top-down/oblique aerial targets are OOD. RQ-T.1 could collapse — then the training lever is pulled.
- **Off-stack edge export (SAM2 → TensorRT/ONNX)** is integration time, same class of work as the
  bake-off's arms C/D. Budgeted, not free.
- **Co-residency in 8 GB is tight.** VLM + tracker + KV cache + frame buffers may force load-on-demand,
  adding a ~2 s reload to every re-ground.
- **AerialMind license chain:** derives from VisDrone (CC BY-NC-SA 3.0, academic-only) + UAVDT —
  fine for the thesis, not for non-academic use (identical to RefDrone; see `docs/dataset-survey-refdrone.md` §5.1).
- **Acquire ambiguity:** "the white car" with three white cars → acquire highest-confidence match,
  document the limitation. Twin white cars mid-track → ID-switch risk (AerialMind ID-consistency
  measures it; reserved mitigation = appearance-embedding gate).

## Status & next step (where a cold session picks up)

- **2026-07-01T15:05Z — pre-registered, nothing run.** Design + phases + gate + estimates frozen above.
  The bake-off (`experiments/2026-06-30-vlm-backbone-bakeoff/`) still owns the 3090 and Jetson; this
  campaign's **Phases 0–1 are CPU-only and can start immediately without contending** for either.
- **2026-07-02T13:05Z — Phase 0 launched.** Bake-off early-stopped (see its README), so the 3090 is
  free — **deviation from pre-reg: Phase 0 runs on the 3090, not CPU** (the "CPU-only" constraint
  existed only because the sweep owned the GPU; zero-shot inference numbers are box-independent,
  Jetson FPS stays a Phase 2 question). Exact command:
  `TQDM_DISABLE=1 nohup .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/carry_eval.py --cap 300 > raw/phase0-zeroshot-carry.log 2>&1 &`
  Scope: 93 seqs × 2 tracks (`pick_eval_tracks`: longest + longest-with-gap; 82 picked tracks have
  ≥3-frame occlusion gaps), window ≤300 frames/track (RAM bound: fp32@1024² ≈ 12.6 MB/frame, max seq
  1859 frames ≈ 23 GB > free RAM — symlinked `/dev/shm` window instead). Smoke (1 seq, cap 100):
  ~28 it/s propagation, ~19 FPS wall on the 3090; est. full run **~45–90 min** (ESTIMATE).
  Outputs → `runs/phase0-zeroshot-carry/{per_track.csv,results.json,<manifest>}`, log → `raw/`.
- **2026-07-02T16:25Z — Phase 0 first run KILLED at seq 42/93: GT decode bug.** While building the
  demo (`follow_demo.py`), an oracle smoke returned mean IoU 0.021 against a perfect acquire box;
  frame renders showed **every** GT box shifted up-left by half its size. Root cause: AerialMind's
  `labels_with_ids` stores `x y w h` with `x,y` = box **top-left**, not the JDE center convention
  the loader assumed (verified visually: with top-left decoding all boxes sit exactly on their
  vehicles, e.g. M0205 frame 414). The earlier out-of-bounds boxes that motivated clamping at parse
  time were the same bug — real top-left boxes are in-bounds. Every number in the first run
  (log archived as `raw/phase0-zeroshot-carry.INVALID-gt-decode-bug.log`) is an artifact — the
  "iou25 0.05–0.13, occasional 0.7" spread was SAM2 tracking correctly against displaced GT.
  Fixed in `aerialmind.py`, selfcheck re-passed, **relaunched 2026-07-02T16:30Z** (same command).
  Also: first-run pace was ~40 s/seq → full run ≈ **65 min**, not the 45–90 min upper band feared.
- **2026-07-02T17:35Z — Phase 0 DONE, RQ-T.1 PASS.** 186/186 tracks, 58.4 min (inside the 45–90 min
  estimate band). Results table + Findings filled above; ledgers appended (Part IV). Demo (occlusion
  + retarget) built, run on real Jetson VLM, committed `ab6d6d7`, videos in `raw/`.
- **Next step:** Phase 1 (SITL oracle-follow slice with injected VLM latency/parse-fail
  distributions — the measured 4.1–4.6 s acquire walls and the behavioral-caption failure mode are
  now the injection priors). Phase 2 (Jetson SAM2 FPS + co-residency) no longer waits — Jetson free.
- **2026-07-02T09:00Z — Phase 2 pre-registered (runs before Phase 1; Jetson is free now and RQ-T.2
  is the campaign's biggest open risk).** Question: SAM2.1-tiny video-propagation FPS on the Orin
  Nano 8 GB @ 15 W (RQ-T.2 gate ≥5 FPS), and VLM-Q8_0 co-residency (RQ-T.3). Setup to install on
  the Jetson (documented here per working agreement): `uv` (standalone installer), venv
  `~/sam2-bench/.venv` (system Python 3.10), CUDA torch/torchvision from the JetPack-6 wheel index
  (`https://pypi.jetson-ai-lab.dev/jp6/cu126`), `sam2==1.1.0` with `SAM2_BUILD_CUDA=0` (the `_C`
  extension is optional post-processing; already absent on the 3090 runs). Bench: `jetson_carry_bench.py`
  (scp'd over), M0205 frames 395–494 (100-frame window — `init_state` preloads frames as fp32
  1024² tensors at 12.6 MB/frame; 100 frames ≈ 1.3 GB of the 7.6 GB unified RAM), box prompt from
  GT frame 395, bf16 autocast, report steady-state propagate FPS + `tegrastats` peak RAM.
  Passes: (a) solo; (b) solo with `image_size=512` if (a) fails the gate (compute lever — accuracy
  re-eval required before adoption); (c) llama-server Q8_0 resident alongside → rerun (a), record
  FPS + peak RAM or OOM → co-residency vs load-on-demand verdict.
  **Estimates (ESTIMATE):** PyTorch eager @1024 on Orin Nano ≈ **1.5–4 FPS** (3090 does 14–27 FPS;
  Orin Nano GPU is ~1/15–1/30 of a 3090) — i.e. the pre-registered 5–15 FPS band assumed TensorRT,
  and eager PyTorch likely FAILS the 5 FPS gate at 1024; @512 ≈ 4–10 FPS (borderline). Co-residency:
  VLM server ≈ 5.2–5.5 GB + torch CUDA context ≈ 1–1.5 GB + frames → **likely does not fit**;
  expected verdict is load-on-demand or a streaming (non-preload) frame path. A documented FAIL
  names the lever: TensorRT export / EdgeTAM / streaming init. Est. wall: setup 20–40 min
  (torch wheel download dominates), bench minutes.
- **2026-07-02T09:35Z — Phase 2 setup actuals** (Jetson: L4T R36.5.0 / JetPack 6, CUDA 12.6,
  Python 3.10, uv 0.11.26, venv `~/sam2-bench/.venv`):
  - Wheel index domain moved: `pypi.jetson-ai-lab.dev` no longer resolves (DNS dead from both
    boxes); the live index is **`pypi.jetson-ai-lab.io`**`/jp6/cu126`.
  - `torch==2.11.0` (index latest) fails to import — linked against cuDSS (`libcudss.so.0: cannot
    open shared object file`), which JetPack 6 doesn't ship and the index doesn't carry.
    **Pinned `torch==2.8.0` + `torchvision==0.23.0`**: imports clean, CUDA available, device "Orin".
  - torch 2.8.0 aarch64 build is compiled against NumPy 1.x → **pinned `numpy<2`** (1.26.4).
  - `sam2==1.1.0` via `SAM2_BUILD_CUDA=0` + `--no-build-isolation` (optional `_C` post-processing
    ext skipped, same as the 3090 Phase 0 runs); `huggingface_hub` added (sam2 `from_pretrained`
    needs it but doesn't declare it).
  - Bench inputs: M0205 frames 395–494 (100 frames, 1024x540) at `~/sam2-bench/clip/`; prompt box
    `496,69,577,110` = GT tid 20 @ frame 395. Power: 15 W confirmed + `jetson_clocks`; RAM via
    `tegrastats --interval 1000`.
- **In parallel: demo (`follow_demo.py`).** ACQUIRE (Jetson VLM) → CARRY (SAM2) → REGROUND-on-loss,
  plus **RETARGET** (mid-video caption switch = fresh acquire + `predictor.reset_state`, cached
  frames kept). Two M0205 clips: occlusion demo (`"Commercial truck"` tid 25, frames 395–646,
  40-frame gap @562) and retarget demo (`"Black car invading other lanes"` tid 22 → @220
  `"The parked taxi"` tid 4, frames 1–440; both single-target expressions).
- **2026-07-02T09:55Z — Phase 1 pre-registered (SITL oracle slice, RQ-T.5 skeleton).** Question:
  perception made *perfect* (oracle box @ 20 Hz), the temporal design's **costs** injected — does the
  follow loop survive the blind windows? Injection priors, all measured: ACQUIRE/REGROUND latency
  **U(4.1, 4.6) s** (demo's real Jetson Q8_0 acquire walls); parse-fail **p = 0.007** per acquire
  (deployed terse config parses 99.3–100% on Orin, `docs/results/part3-permanence.md` — worst case);
  synthetic occlusion **5 s @ t=30 s** (oracle forced None); LossGate **60 consecutive no-box frames**
  (3 s @ 20 Hz ≈ the demo's 75-frame @ 25 fps gate). During ACQUIRE/REGROUND the copter hovers blind
  while the rover keeps driving — the sweep asks at what target speed that breaks the loop.
  Command: `.venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase1_sitl.py`
  (new file; reuses `runners/run_phase_b.py` SITL boot/telemetry-drain/programmatic-rover and
  `runners/sitl/` oracle/PID/offboard verbatim; **ByteTrack dropped** — the temporal state machine
  replaces it. Copter SITL only; rover stays programmatic per Phase B's NED-mismatch rationale).
  Trials: rover **0.25 / 0.5 / 1.0 m/s** north × 75 s, 10 m AGL. Metrics: geometric in-FOV fraction,
  time-to-first-lock, acquire attempts, REGROUND count + relock wall, CARRY pixel error.
  **Gate (RQ-T.5 skeleton): at 0.25 m/s, in-FOV ≥ 90% AND relock after the occlusion.**
  **Estimates (ESTIMATE — geometry: 10 m AGL, 60° HFOV → half-footprint 5.77 m E-W × 4.33 m N-S):**
  0.25 m/s PASS (acquire drift ≈ 1.6 m; occlusion→relock blind window ≈ 7.4 s → drift ≈ 1.8 m, in
  FOV); 0.5 m/s marginal PASS (occlusion drift ≈ 3.7 m vs 4.33 m edge); 1.0 m/s **FAIL at first
  acquire** (rover exits FOV at 0.5 + 1.0×~4.35 ≈ 4.85 m > 4.33 m before the first acquire returns
  — never locks). Est. wall: 6–10 min total. Outputs → `raw/phase1-sitl/` (CSVs + SITL logs),
  `runs/phase1-sitl/` (results.json + manifest).
- **2026-07-02T10:05Z — Phase 1 DONE, RQ-T.5 skeleton PASS.** Selfcheck passed (lock @4.55 s, gate
  @32.95 s, relock wall 4.35 s — modeled timeline exact), then 3 SITL trials in one flight, ~5 min
  wall (est. 6–10 — inside band). Results row + Findings filled above; the 1.0 m/s speed-ceiling
  mechanism (REGROUND blind window, not first acquire) is the phase's main content. Ledgers
  appended (Part IV). Next: Phase 2 verdict when the 512 accuracy re-eval lands, then Phase 3
  pre-registration (integrated oracle→SAM2→real VLM; image_size choice hangs on the 512 verdict).
- **Open decisions still pending:** (1) SAM2 variant — SAM2.1-tiny vs EdgeTAM vs EfficientTAM (decide
  on Jetson FPS, Phase 2); (2) TensorRT vs ONNX for the carry export (shared with the bake-off's C/D
  question); (3) Part assignment — this seeds the "v5 temporal" line but is left under Part IV
  (end-to-end) until it produces results (see Ledger follow-through).

## Files

- `README.md` — this pre-registration (source of truth + handoff).
- `configs/` — carry/orchestrator config(s), one per variant (created at Phase 0/2).
- `raw/` — verbatim run/eval logs for this campaign (created when a phase runs).
- `runs/` — per-run provenance manifests (git_sha, lockfile, config) — created when a phase runs.

## Ledger follow-through (per CLAUDE.md definition-of-done)

Held until results exist (these append a *verdict*, not a plan): **RESULTS** — per-phase metric rows ·
**QUESTIONS** — RQ-T.1…T.5 one-line verdicts · **DECISIONS** — the spine choice (acquire+carry vs
per-frame; zero-shot vs trained; SAM2 vs SOT) + what was given up · **SOURCES** — SAM2 / EdgeTAM /
AerialMind cards. **Part assignment** (IV vs a new v5 line) is decided when Phase 0/3 land, since a
new Part requires the three ledger-root index rows + `docs/{results,questions,decisions}/partN-*.md`.
