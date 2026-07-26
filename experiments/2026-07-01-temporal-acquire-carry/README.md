# Temporal follow — acquire-once + memory-carry ("follow the white car")

**Date:** 2026-07-01T15:05Z (pre-registration) · **Branch:** `experiment/temporal-carry` (off `main` @ `a2fd695`)
**Status:** **CAMPAIGN COMPLETE** 2026-07-02 (`00aa244`) — all phases run. Phase 0 PASS (RQ-T.1),
Phase 2 verdict = **RQ-T.2 marginal FAIL at 768** (accuracy holds at 0.830, rate 4.89 FPS misses
the ≥5 gate), Phase 3b on-device = both behavioral legs PASS (in-FOV 1.000, validated relock),
rate leg 4.1/5 marginal FAIL exactly as pre-registered. Superseded on the rate leg by
[E1 (TensorRT SAM2 encoder)](../2026-07-02-carry-trt-export/README.md), which lifted the same
768 carry to 6.15 FPS co-resident and re-ran 3b at 5.0/5 PASS.
<!-- This header read "Phase 2 RUNNING · Phases 1, 3 pending" until 2026-07-21T18:10Z, three
     weeks after the campaign finished and while its own log below said "CAMPAIGN PHASES
     COMPLETE". A stale status header is the cheapest way to make a fresh session redo
     finished work. -->

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
| 2 | RQ-T.2 / T.3 | FPS @ 15 W; peak RAM co-resident | @1024: **2.68 FPS** (p50 373 ms, est. 1.5–4 — inside band, gate FAIL); @512: **12.13 FPS** (p50 82.5 ms, est. 4–10 — *above* band); co-resident @1024 with VLM Q8_0 server: **2.68 FPS unchanged, server survived, peak RAM 6963/7607 MB** (est. "likely does not fit" — **wrong**, fits with ~650 MB headroom); 100/100 masks non-empty in all passes. Knee sweep (full table below): 768 = 4.89 FPS / IoU@0.25 **0.830**; 640 = 7.24 FPS co-res / **0.787**; 512 acc 0.737 | RQ-T.2 **marginal FAIL — OP=768 by the frozen rule** (640 misses the 0.799 accuracy bar by 1.2 pp; 768 holds accuracy but misses ≥5 FPS by 2.2% — TensorRT campaign `2026-07-02-carry-trt-export` is the named fix); RQ-T.3 **PASS — co-residency holds at every size (zero FPS cost), no load-on-demand needed** |
| 3 | RQ-T.4 / T.5 | occlusion recovery; in-frame fraction, integrated | **3.0 parity:** stream-vs-batch mean IoU 0.9974 @1024 / 0.9968 @512 (gate ≥0.99). **3a (3090 carry + real Jetson acquire):** run 1 FAIL in-FOV 0.544 (VLM locked a road dash during occlusion + ingress lag — falsified *unvalidated* reground); run 2 with size-prior validation + dead-reckoning + 3 s loss gate: in-FOV **1.000**, 5/7 acquires rejected, relock 13.9 s, px_err 16.2, carry 13.6 FPS. **3b (carry on Jetson @768, VLM co-resident):** in-FOV **1.000**, relock 14.35 s, recovered, px_err 22.5, **carry-phase rate 4.1 FPS < 5** (whole-trial 7.6 Hz; est. 4.5–4.8 — wire overhead underestimated). **3b re-run + E1 TRT encoder (`--trt-encoder enc768.plan`):** in-FOV **1.000**, relock 14.17 s, recovered, px_err 23.0, **carry-phase rate 5.0 FPS ≥ 5** (eager→TRT 4.1→5.0; solo E1 bench was 6.15, integrated loop pays ~1.15 FPS JPEG+tunnel wire) | RQ-T.4/T.5 **PASS on both behavioral legs @0.25 m/s** (acquire→carry→validated-reground→relock works end-to-end, on-device); **rate criterion marginal FAIL at OP=768 eager (4.1/5) → PASS with E1 TRT encoder (5.0/5)** — campaign fully met |

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

Phase 2 knee table (Jetson FPS = M0205 100-frame bench @ 15 W + jetson_clocks; accuracy = full
186-track eval on the 3090, same protocol as Phase 0; ACC bar = 0.799 = 1024's 0.849 − 5 pp):

| image_size | Jetson FPS solo | co-resident | IoU@0.25 | mean IoU | ID-cons | verdict |
|---|---|---|---|---|---|---|
| 1024 | 2.68 | 2.68 | **0.849** | 0.602 | 0.891 | accuracy reference; FPS FAIL |
| **768 (OP)** | 4.89 | 4.89 | **0.830** (−1.9 pp) | 0.585 | 0.889 | acc PASS; FPS **marginal FAIL** (−2.2% vs ≥5) |
| 640 | 7.25 | 7.24 | 0.787 (−6.2 pp) | 0.551 | 0.859 | FPS PASS; acc FAIL **by 1.2 pp** |
| 512 | 12.13 | — | 0.737 (−11.2 pp) | 0.506 | 0.823 | FPS PASS; acc FAIL |

768/640 evals: 42.0 / 37.4 min wall on the 3090 (est. 768 acc 0.80–0.84, 640 acc 0.77–0.82 —
both inside band; 640 landed on the failing side of exactly the uncertainty the estimate named).
Runs: `runs/phase2-carry-{768,640}/`, logs `raw/phase2-carry-{768,640}.log`; Jetson bench JSONs
+ tegrastats in `raw/phase2-jetson/` (solo 640/768, co-resident 640 RAM peak 6144/7607 MB,
co-resident 768 spot-check 4.89 FPS — zero contention at every size).

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
- **Unvalidated reground is the architecture's real failure mode (Phase 3a run 1, kept as
  content):** ask a VLM to find an occluded object and it returns the most plausible visible
  match (a white road dash for "the white car"); the tracker then carries the wrong object
  faithfully. The size-prior accept/reject on acquire is what flipped the integrated gate from
  FAIL (in-FOV 0.544) to PASS (1.000) — 5 of 7 acquire attempts were correctly rejected in both
  the 3a-2 and 3b passing runs.
- **The knee is real and unkind (Phase 2):** accuracy holds to 768 (−1.9 pp) then falls off a
  cliff (640: −6.2 pp, 512: −11.2 pp — small aerial targets die with resolution), while the ≥5
  FPS gate on eager PyTorch needs ≤~700. No size passes both; the 2.2% shortfall at 768 is the
  entire remaining gap to a fully-passing on-device loop (E1's job).
- **Dataset gotcha (cost ~28 min GPU + a morning):** AerialMind `labels_with_ids` stores `x y w h`
  with `x,y` = box **top-left**, *not* the JDE center convention the filename layout implies. Center
  decoding shifts every box up-left by half its size — plausible-looking but wrong everywhere
  (out-of-bounds "clamping" at parse was a symptom, not a fix). Verified visually before re-running.

## Decision

**Acquire-once + memory-carry replaces the per-frame v2/v3 grounding pipeline.** The carry is
**zero-shot SAM2.1-hiera-tiny** (no temporal fine-tune — RQ-T.1 resolved favorably, the training
lever stays unpulled), operating point **image_size 768** (frozen knee rule; 640 missed the
accuracy bar by 1.2 pp). Matched accuracy evidence: carry IoU@0.25 0.849 @1024 / 0.830 @768 vs
the deployed v3 ROI re-anchor loop's 85.2% — equal accuracy **without any per-frame VLM call**,
and the VLM is repurposed to what only it can do (language-conditioned ACQUIRE/REGROUND/RETARGET).

Supporting decisions, each with what was given up:
- **Validated reground (size prior [0.5, 2.0] on expected pixel size from altitude)** is
  load-bearing, not optional — run 3a-1 falsified unvalidated reground (VLM hallucinates a
  plausible box when the target is occluded). Given up: fastest-possible relock (rejections keep
  polling until the target actually reappears; relock wall grows from ~2.4 s to ~14 s across a
  real occlusion — the *correct* behavior).
- **Dead-reckoning during blind windows** (command last estimated target velocity) — held the
  copter-target gap constant (~2.2 m) through a 13.9 s blind window vs diverging under hover.
  Given up: nothing measurable; it is a strict improvement at these speeds.
- **Perception on the Jetson, control host-side** (SITL/renderer/MAVLink are host processes by
  nature; PID is microseconds). The on-device claim covers the binding resource — per-frame
  perception. Given up: a fully-on-device demo binary; honest framing recorded.
- **Eager PyTorch at OP=768 leaves the rate criterion 4.1/5 FPS short.** Adopted anyway as the
  Part IV operating point because both behavioral legs pass and the shortfall has a named,
  budgeted fix (E1 TensorRT export, `experiments/2026-07-02-carry-trt-export/`). Given up:
  declaring the campaign criterion fully met on this hardware today.

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

*Earlier entries — the full session-by-session log of launches, deviations and
false starts — moved to `STATUS-LOG.md` on 2026-07-26. The closing entries stay
here.*

- **2026-07-02T11:45Z — Phase 2 DONE: RQ-T.2 marginal FAIL, OP=768 (frozen rule fired
  mechanically).** 768 accuracy **0.830** (≥0.799 bar, est. band 0.80–0.84 — inside); 640
  accuracy **0.787** (misses the bar by **1.2 pp**; est. band 0.77–0.82 — inside, on the failing
  side, exactly the uncertainty the estimate named). No eager-PyTorch size passes both gates:
  verdict per the frozen sentence — *"RQ-T.2 marginal FAIL at 768: accuracy holds (0.830) but
  4.89 FPS misses the ≥5 gate by 2.2%; TensorRT campaign (2026-07-02-carry-trt-export) must
  close it."* Step B co-residency spot-check at OP done pre-emptively while 640 evaluated:
  **cores-768 = 4.89 FPS, identical to solo** (`raw/phase2-jetson/bench_cores768.json`) — zero
  contention at 1024/768/640, RQ-T.3 settled. Knee table in Results. Consequence for 3b: flight
  runs at `--image-size 768`; expected control rate ~4.5–4.8 Hz = marginal FAIL on the rate leg
  only (pre-registered as the expected outcome for OP=768; the in-FOV and relock legs are the
  informative ones, E1 buys the rate).
- **2026-07-02T11:49Z — Phase 3b flown at OP=768: in-FOV and relock legs PASS, rate leg marginal
  FAIL exactly as pre-registered. CAMPAIGN PHASES COMPLETE.** Same scenario as 3a run 2, carry on
  the Jetson (`--remote-carry --image-size 768`, VLM Q8_0 co-resident on the same Orin): in-FOV
  **1.000**, first lock 3.02 s, 7 acquire attempts / 5 rejected by the size prior, 1 reground,
  relock wall 14.35 s, **recovered after occlusion**, px_err mean 22.5 (vs 16.2 @1024 in 3a — the
  768 accuracy cost + slower loop), 569 frames / 75 s. Rate: whole-trial 7.6 Hz, but that number
  is inflated by the blind ACQUIRE/REGROUND phases (no perception in the loop); the honest
  criterion number is the **carry-phase loop rate = 4.1 FPS < 5** (solo Jetson bench 4.89 −
  JPEG-decode + tunnel round-trip ≈ 40 ms/frame; est. 4.5–4.8 — actual slightly below band, the
  wire overhead was underestimated). The run's `results.json` prints `gate: PASS` because the
  code gated on whole-trial hz; the gate is now fixed to `carry_fps` for the post-E1 re-run, and
  the recorded verdict here is the honest one: **rate leg FAIL (4.1/5), both behavioral legs
  PASS** — the runbook's expected outcome for OP=768; E1 (TensorRT export) must buy the ~20%.
  Artifacts: `raw/phase3b-sitl/` (CSV, mp4, SITL log), `raw/phase3b-sitl.log`,
  `runs/phase3b-sitl/`. RAM held (llama-server + SAM2@768 + service co-resident, no OOM).
- **2026-07-02T15:12Z — Phase 3b RE-RUN with the E1 TRT encoder: rate leg now PASS (5.0/5),
  CAMPAIGN FULLY MET.** After E1 (`2026-07-02-carry-trt-export`, `e99120b`) closed, re-ran the same
  3b harness with `phase3_sitl.py --remote-carry --image-size 768 --trt-encoder enc768.plan` — the
  carry service now monkeypatches `predictor.forward_image` with the fp16 TensorRT encoder, so every
  streamed frame runs the fast path (same patch E1 validated). Gate is now `carry_fps` (fixed from
  the whole-trial-hz bug noted above). Result: in-FOV **1.000**, first lock 5.43 s, 8 acquire
  attempts / 6 rejected by the size prior, 1 reground, relock wall 14.17 s, **recovered after
  occlusion**, px_err 23.0, achieved_hz 8.7, 651 frames, **carry-phase rate 5.0 FPS ≥ 5 → gate
  PASS**. The rate leg that was 4.1/5 eager is met: eager→TRT lifted carry 4.1→5.0. Margin is thin
  (5.0 exactly) — the solo E1 bench was 6.15 FPS, but the integrated loop pays ~1.15 FPS in per-frame
  JPEG encode/decode + ssh-tunnel wire transfer the solo bench doesn't. Both behavioral legs stay
  PASS. This closes the parent campaign's only marginal-FAIL leg; all phases now fully met.
  Code deltas: `--trt-encoder` arg threaded through `phase3_sitl.py` (ssh boot cmd) and
  `jetson_carry_service.py` (monkeypatch after building the predictor; scp'd to `~/sam2-bench/`).
  Artifacts: `runs/phase3b-sitl/results.json`.
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
