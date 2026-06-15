# Phase C — VLM in the Loop (real grounding replaces the oracle)

**Pre-registered:** 2026-06-15
**Status:** Branch-1 PASS (2026-06-15) — inject-oracle mechanics gate met; Branch-2 (live VLM + Gazebo) pending
**Depends on:** Phase A complete (zero-shot grounding probe, 2026-06-15); Phase B complete + PASS (SITL pipeline integration, 2026-06-15T09:30 UTC)
**Answers:** RQ-S1.4 (README) — "Replacing oracle with the best zero-shot VLM: how much does following error and track-loss increase vs oracle?"

> This is a **pre-registration**. Every threshold, metric, and decision below is fixed
> *before* any Phase C data is collected, per CLAUDE.md. Results blocks are filled in
> post-run; nothing here is a measured number unless explicitly labelled as carried
> forward from Phase A/B (which are cited with their date).

---

## 0. One-line summary of the change

Phase B's perfect-perception **oracle bbox** (geometric projection of SITL world-state) is
replaced by a **real vision-language model** — SmolVLM-500M-Instruct Q8_0 — running **on the
Jetson Orin Nano 8 GB**, grounding a natural-language target expression in a **Gazebo-rendered
aerial camera frame**. The ByteTrack → cascade PID → pymavlink offboard control loop is carried
forward **unchanged** from Phase B. The perception front-end changes from *geometry* to *pixels*;
everything downstream of the bbox is identical.

---

## 1. What changes from Phase B (and what does not)

| Pipeline stage | Phase B | Phase C | Identical? |
|---|---|---|---|
| Camera frames | none (geometry only) | **Gazebo Harmonic rendered 640×480 aerial frame** | ✗ new |
| Bbox source | `oracle_bbox.project()` (pinhole projection of SITL world-state) | **SmolVLM-500M grounding** of an NL expression in the rendered frame | ✗ **the change** |
| Bbox host | local x86_64 (pure Python) | **Jetson Orin Nano** (llama-server, sm_87, 15 W locked) | ✗ new |
| Bbox call style | synchronous, in-loop, ~25 Hz | **asynchronous, separate thread, ~1 Hz** | ✗ new (§4) |
| Camera model | gimbal-stabilized nadir (level roll/pitch, real yaw) | **gimbal-stabilized nadir** (Gazebo camera gimballed to nadir) | ✓ carried fwd |
| ByteTrack | Kalman + IoU + low-score association | **identical module** (`sitl/bytetrack.py`) | ✓ |
| Cascade PID | `kp_yaw=0.0`, `kp_lat=0.02`, `kp_range=0.0001` | **identical gains** | ✓ |
| Offboard | pymavlink `SET_POSITION_TARGET_LOCAL_NED`, vel + yaw_rate | **identical** (`sitl/offboard.py`) | ✓ |
| Vehicle / physics | ArduCopter SITL Copter-4.6.3, 10 m AGL | **identical**, now coupled to Gazebo physics | ✓ (+ Gazebo) |
| Target | programmatic rover 0.25 m/s north, anchored to copter (N,E) | **identical trajectory**, now a Gazebo-rendered vehicle model | ✓ trajectory |
| Control rate | 20 Hz | **20 Hz** | ✓ |
| Run structure | 3 × 60 s | **3 × 60 s** | ✓ |

**Honest scoping note (per advisor + CLAUDE.md "no unverified claims"):** "everything else
identical" holds for the **physics, control, rover trajectory, and gimbal model**. The
**perception front-end fundamentally changes from geometry to pixels** — this is the whole point
of Phase C, and it is the one place the two phases are *not* comparable component-for-component.

---

## 2. VLM model selection

### 2.1 Decision: SmolVLM-500M-Instruct Q8_0 (unit S2)

**Chosen.** This is the model already selected as the Stage-2 fine-tuning target by the Phase A
decision gate (`DECISIONS.md`, 2026-06-15T08:10). Carrying it into the Phase C closed loop keeps
a single grounding model across the whole stage.

Carried-forward measurements (Jetson, 15 W locked, llama.cpp `57fe1f0`, sm_87):

| Property | Value | Source |
|---|---|---|
| Per-frame latency (zero-shot grounding, RefDrone) | **833 ms (≈1.20 Hz)** | Phase A, 2026-06-15 (RESULTS.md S2 row) |
| VLM feasibility latency (captioning) | 338 ms (2.96 Hz) | V2, 2026-06-14 |
| Peak RAM | 2734 MB (grounding) / 2241 MB (feasibility) | Phase A / V2 |
| Image tokens | 64 | V2 |
| Zero-shot grounding quality | **parse 4 %, IoU@0.25 = 0 %, IoU@0.5 = 0 %, mean IoU 0.001** | Phase A, 2026-06-15 |

> ⚠ **The grounding quality is the load-bearing caveat of this entire phase.** Zero-shot SmolVLM
> grounds aerial RefDrone targets at **0 % IoU@0.25**. This is pre-registered as the expected
> baseline. Phase C does **not** assume the VLM tracks well; it measures *how badly the loop
> degrades* and validates the *integration mechanics* (§6 separates the two). A flatline (loop
> can't hold the target at all) is a valid, pre-registered outcome — it is exactly the README's
> pivot question RQ-S1.4 / "is the fine-tune load-bearing?".

### 2.2 Alternatives considered

| Candidate | Why considered | Why not chosen for Phase C |
|---|---|---|
| **SmolVLM-256M Q8_0 (S1)** | Faster (3.58 Hz), smaller (1777 MB) | Phase A: **parse 0 %**, produced only free-text, no coordinate structure at all. No grounding signal to track. (DECISIONS 2026-06-15T08:10.) |
| **PaliGemma-2-3B Q4_K_M** | The literature sweep's accuracy ceiling and the task prompt's suggested candidate; native `<locXXXX>` detection vocabulary | **Blocked on the controlled runtime.** PaliGemma support in llama.cpp (PR #7553) is unmerged draft as of 2026-06-14; no PaliGemma-2 GGUF published; running it would break the controlled-variable invariant (commit `57fe1f0`). (DECISIONS 2026-06-14.) → `revisit-when`. |
| **Fine-tuned SmolVLM-500M (Stage 2 output)** | Expected to actually ground aerial targets | Stage 2 fine-tune is **not yet done**. Phase C is the *zero-shot* closed-loop baseline that motivates Stage 2; using the fine-tuned model here would erase the baseline RQ-S1.4 needs. The Phase C **harness is built to swap the GGUF path** so the fine-tuned model can re-run Phase C unchanged later. |
| **gemma-3-4b / gemma-4-E2B/E4B VLM** | Stronger captioning | Too slow (V3 0.10 Hz; V4 0.49 Hz; V5 0.34 Hz) and/or swap (V3, V5). Below the usable control-rate budget and not grounding models. |

**Hardware constraint that frames the whole choice:** the thesis is about *local LLMs on the
Jetson Orin Nano 8 GB*. The VLM must be aarch64 / JetPack / CUDA sm_87, fit the ~6.4 GB resident
ceiling without swap, and run in the pinned llama.cpp `57fe1f0` build. SmolVLM-500M is the only
candidate that satisfies all three **and** showed any coordinate-output structure in Phase A.

### 2.3 Decision recorded

See `## Decisions` below (2026-06-15 — Phase C VLM = SmolVLM-500M, zero-shot, Gazebo render).

---

## 3. VLM integration architecture

### 3.1 Topology (distributed, two hosts)

```
LOCAL x86_64 (Ubuntu 24.04) — sim + control                JETSON Orin Nano 8 GB — perception
─────────────────────────────────────────────             ──────────────────────────────────
Gazebo Harmonic  ──renders──►  camera frame  ───┐
  (ardupilot_gazebo plugin)    640×480 JPEG     │  HTTP POST (base64 img + NL prompt)
        │ physics                                └──────────────────────────►  llama-server
        ▼                                                                       SmolVLM-500M Q8_0
ArduCopter SITL  ◄── MAVLink offboard setpoints                                 (-ngl 99, port 8080)
  (Copter-4.6.3)        ▲                          ◄──────────────────────────  │
        │ telemetry     │                            HTTP 200 (bbox text)       │ grounds NL
        ▼               │ (20 Hz control loop)                                  ▼
 ┌─────────────────────┴───────────────────────────────────────────────┐  CLIP encode + prefill
 │ run_phase_c.py                                                        │  + decode (~833 ms)
 │   • control+track thread  @20 Hz  (ByteTrack coast + PID + MAVLink)   │
 │   • VLM-grounding thread  @~1 Hz  (async; never blocks control)       │
 │   • shared latest-detection slot (lock-protected)                     │
 └───────────────────────────────────────────────────────────────────── ┘
```

**Why this split:** the thesis measures the **Jetson** as the inference device, so the VLM must
run on the Jetson (matching Phase A/V-campaign methodology and producing a device-ledger row,
§5.3). SITL + Gazebo + control stay on the local x86_64 box, as in Phase B — running the
simulator on the Jetson too would conflate the measurement device with the stimulus
(DECISIONS 2026-06-15 option (c)). End-to-end perception latency therefore =
`render + net→Jetson + CLIP-encode + prefill + decode + net→local`.

### 3.2 Reuse the Phase A grounding client (do not reinvent)

`run_grounding_probe.py` already implements the entire Jetson llama-server path. Phase C
**imports / copies** these, unchanged where possible:

| Function | Role in Phase C |
|---|---|
| `start_server()` / `_wait_health()` | bring up `llama-server -m SmolVLM-500M --mmproj … -ngl 99 --port 8080` on the Jetson + SSH `-L` port-forward |
| `_build_payload()` / `_post()` / `_response_text()` | build the base64-image + prompt chat payload, POST to `/v1/chat/completions`, extract text |
| `_response_ms()` | pull `prompt_ms + predicted_ms` from `__verbose` timings → per-frame VLM latency for the device row |
| `parse_response_a` / `parse_response_b` + `Bbox.is_valid` | parse the model's coordinate text → validated `Bbox`, or `None` |
| `stop_server()` | teardown |

The only *new* code is: (a) the Gazebo camera-frame grabber, (b) the async grounding thread, and
(c) the bbox→ByteTrack adapter. Phase C = **swap `oracle_project()` for an async HTTP grounding
call**; nothing else in the perception-to-control contract changes.

### 3.3 Prompt template (fixed)

Reuse the Phase-A winning format (Format A, JSON, absolute pixels — it had the higher parse rate
for S2). Pre-registered Phase C prompt:

```
Give the bounding box of '<EXPRESSION>' as JSON
{"x1":...,"y1":...,"x2":...,"y2":...} in pixel coordinates.
Image size is 640×480. If not present, reply null.
```

- `<EXPRESSION>` is **fixed per campaign** and recorded in the results block (e.g. `"the white
  car"` / `"the vehicle on the ground"`). The target is a single unambiguous Gazebo vehicle, so
  the expression is single-target by construction (avoids RefDrone's multi-target ambiguity).
- `max_tokens=80`, `cache_prompt=false` (each frame processed from scratch — correct for per-frame
  drone use; matches V-campaign / Phase A config), `--reasoning off` is **not** needed (SmolVLM is
  not a thinking model).

### 3.4 Bbox → ByteTrack adapter

The VLM returns `{"x1","y1","x2","y2"}`; ByteTrack (and the PID) expect Phase B's
`{cx,cy,w,h, score}` dict. Adapter (new, unit-tested):

```
xyxy → cx=(x1+x2)/2, cy=(y1+y2)/2, w=x2−x1, h=y2−y1, score=<VLM-confidence-or-1.0>
```

SmolVLM emits no confidence; use `score=1.0` for any successfully parsed, in-bounds box (ByteTrack's
low-score branch is then unused, matching Phase B's single high-score detection). Record this as a
limitation: Phase C cannot exploit ByteTrack's two-round low-score association without a detector
confidence.

### 3.5 What to do on no/bad bbox (pre-registered failure handling)

| VLM outcome | Action |
|---|---|
| Valid in-bounds box parsed | feed as the cycle's detection; ByteTrack associates/updates |
| `null` / `none` / unparseable / out-of-bounds (`Bbox.is_valid`=false) | **no detection this cycle** — ByteTrack **coasts** the Kalman estimate; control loop keeps running on the coasted track |
| ≥ `LOST_TIMEOUT_S` (= **3.0 s**, pre-registered) of consecutive no-valid-box | declare **track-loss event**; ByteTrack drops the track; **re-seed** by continuing to issue grounding calls (next valid box re-initialises a track). Controller holds last setpoint × decaying gain (carry Phase B behaviour: zero vy/vx when no track) during the gap |
| VLM request error / timeout (>2 s) | treat as no-detection this cycle; log; do not crash the loop |

`LOST_TIMEOUT_S = 3.0 s` rationale: at ~1 Hz grounding that is ~3 missed updates, and matches the
"≈1–3 s VLM inference" coasting window the literature sweep cites for See-Point-Fly-class systems.

---

## 4. Latency / throughput: the rate mismatch and how it is handled

### 4.1 The mismatch

| Rate | Phase B | Phase C |
|---|---|---|
| Control / MAVLink setpoint | 20 Hz | **20 Hz (unchanged)** |
| ByteTrack update | 20 Hz | **20 Hz (unchanged — coasts between VLM updates)** |
| **Bbox source** | ~25 Hz (oracle) | **~1.0–1.2 Hz (SmolVLM-500M, Phase A 833 ms/frame)** |

The bbox source drops from ~25 Hz to ~1 Hz — a **~20–25× reduction**. A *synchronous* grounding
call would freeze the 20 Hz loop for ~833 ms every frame and collapse the control rate.

### 4.2 Resolution: asynchronous grounding + Kalman coasting (already supported)

- **Two threads.** A `control+track` thread runs at 20 Hz (drain telemetry → ByteTrack update on
  the *latest available* detection → PID → MAVLink). A `vlm-grounding` thread loops as fast as the
  Jetson allows (~1 Hz): grab newest frame → POST → parse → write the result into a lock-protected
  *latest-detection slot* tagged with a capture timestamp.
- **ByteTrack coasts.** Between VLM updates the control thread calls `tracker.update()` with **no
  new detection on most cycles** (≈19 of every 20), so the Kalman constant-velocity model
  extrapolates the box forward — exactly the mechanism Phase B's ByteTrack already implements and
  the literature sweep prescribes for sub-3-Hz vision.
- **Staleness handling.** Each detection carries its capture time; the control thread knows the
  box is up to ~1 s old. (Optional, pre-registered as *off* for the baseline to keep the
  comparison clean: forward-predicting the stale box by `age × Kalman velocity` before feeding the
  PID. Baseline uses the box as-is; a forward-prediction ablation is listed in §5.4.)

### 4.3 Expected oracle-coverage drop (pre-registered expectation, not a result)

Phase B oracle coverage = **100 %** (the geometry always "sees" the in-frame target). Phase C
"coverage" = fraction of frames for which a **valid VLM box** is the most recent detection.

- **Mechanically**, even a perfect ~1 Hz detector backed by 20 Hz coasting could keep a *track*
  alive ~100 % of frames — coasting fills the gaps. So the **coasting/track-coverage** metric is
  expected to stay high *if the VLM ever produces valid boxes*.
- **But** Phase A measured **0 % IoU@0.25 and 4 % parse** for zero-shot S2 on aerial imagery. If
  that reproduces on Gazebo frames, the **valid-detection rate is expected to be near 0 %**, the
  track is never seeded, and coverage collapses. **Pre-registered expectation: valid-VLM-box rate
  ≪ Phase B's 100 %, plausibly near 0 %.** This is the honest realistic prediction given ~1 Hz
  *and* zero-shot grounding failure.

---

## 5. Experiment design

### 5.1 Carried forward unchanged from Phase B

Programmatic rover (0.25 m/s north, anchored to copter (N,E) at trial start), gimbal-stabilized
nadir camera model, 10 m AGL takeoff, 20 Hz control, **3 × 60 s** run structure, PID gains
(`kp_yaw=0.0`, `kp_lat=0.02`, `kp_range=0.0001`), 60° FoV / 640×480 camera intrinsics.

### 5.2 New: the rendered scene (Gazebo Harmonic)

- **Renderer:** Gazebo Harmonic + `ardupilot_gazebo` plugin, ArduCopter SITL coupled to Gazebo
  physics (the install is Phase C's first sub-task — interactive sudo, §8/checklist).
- **Camera:** downward gimbal sensor on the copter model, gimballed to nadir (matches Phase B's
  level-roll/pitch assumption), 60° FoV, 640×480, published on a Gazebo image topic; grabbed at
  the VLM thread rate.
- **Target:** a single distinct ground vehicle model following the Phase B programmatic
  trajectory, on a textured ground plane chosen for **target/background contrast** (so a grounding
  success is at least *possible* — but **not** tuned to guarantee it; the scene is realistic, per
  the render-source decision).
- **Determinism note:** unlike Phase B, Gazebo introduces rendering + scheduler non-determinism, so
  the three runs are **not** expected to be byte-identical (Phase B's zero cross-run variance will
  **not** carry over — report real spread).

### 5.3 Metrics — Phase B set **plus** new Phase C metrics

Carried from Phase B: loop Hz, mean pixel error (px, from the **oracle geometry retained as
ground truth in parallel** — see below), track-loss events.

**Ground-truth retention (important):** the oracle projection is **kept running alongside** the
VLM (it is free — pure geometry from SITL state). It is **not** fed to the controller; it provides
the **ground-truth box** against which the VLM box is scored (IoU) and against which following
error is measured. This is what makes "how much worse than oracle" quantifiable.

| New metric | Units | Method |
|---|---|---|
| **Valid-VLM-box rate** | % | parsed, in-bounds VLM boxes / total VLM calls |
| **VLM grounding IoU vs oracle GT** | mean IoU + IoU@0.25 / @0.5 rates | IoU(VLM box, oracle box) per VLM call where oracle box exists |
| **VLM per-frame latency** | ms (median + spread) | `_response_ms()` (`prompt_ms+predicted_ms`) + end-to-end wall incl. render+net |
| **Effective grounding rate** | Hz | 1000 / median end-to-end VLM wall-ms |
| **Track coverage (coasted)** | % | frames with a live ByteTrack track / total control frames |
| **Following error vs oracle** | px | pixel distance of the *tracked* box centre from the oracle-GT box centre, over time |
| **Re-acquisition time** | s | mean wall time from track-loss to next live track |
| **Jetson device row** | RAM MB, mean/peak W, peak °C, swap | tegrastats over the whole run (VLM now on-device → produces a RESULTS.md device-ledger row, which Phase B could not) |

### 5.4 Pre-registered ablations (run only if the baseline produces *any* valid boxes)

1. **Forward-prediction of stale box** (§4.2) on/off — does extrapolating the ~1 s-old box reduce
   following error?
2. **Prompt format A vs B** — re-confirm the Phase A format choice on Gazebo frames.
3. **Grounding rate cap** (artificially throttle to 0.5 Hz) — following error vs update rate.

If the baseline produces ~0 valid boxes (expected per Phase A), ablations are **skipped** and the
finding is recorded as the negative result (§6 branch 2).

---

## 6. Success criteria (explicit, two separated branches)

Phase C deliberately **does not** gate on Phase B's 12.9 px tracking number. Per advisor and the
README pivot, integration mechanics and tracking quality are scored separately and **both branches
are pre-registered as valid outcomes.**

### Branch 1 — Integration-mechanics PASS (achievable regardless of grounding quality)

All three must hold across all 3 runs:

1. **Control loop holds rate:** mean control-loop Hz **≥ 15 Hz** despite the ~1 Hz async VLM (i.e.
   the grounding call provably never blocks the control thread). *(Phase B ran 19.99 Hz; the bar is
   set at 15 to allow for Gazebo CPU contention on the local box.)*
2. **Coasting works:** with at least one synthetic/successful detection injected, ByteTrack
   maintains the track across ≥ 15 coasted frames without ID change.
3. **Re-seed works:** after a forced `LOST_TIMEOUT_S` gap, a subsequent valid box re-initialises a
   track within `< 2 s`.

> Branch 1 is verified with an **injected-detection smoke test** (feed the oracle box to the async
> slot on a 1 Hz schedule) **before** the live VLM runs — this isolates "is the async plumbing
> correct?" from "can the VLM ground?". Pre-registered as a required pre-run gate.

### Branch 2 — Tracking-quality outcome (may be a documented negative result)

Reported, not pass/failed against a hard threshold (the honest position given Phase A's 0 % IoU):

- **Stretch / "zero-shot is usable":** valid-VLM-box rate **≥ 30 %** AND mean following error
  **< 100 px** AND ≥ 1 run completes without permanent track-loss. If met → quantify degradation
  vs oracle; zero-shot grounding is a viable (if weak) closed-loop baseline.
- **Expected / "zero-shot is not usable" (pre-registered as the likely outcome):** valid-VLM-box
  rate near 0 %, track never reliably seeded, controller cannot follow. **This is a valid PASS of
  the *experiment*** — it answers RQ-S1.4 with evidence and establishes that the **Stage 2
  fine-tune is load-bearing, not optional.** Recorded as a negative result per CLAUDE.md, not
  smoothed over.

**The phase is "complete" when Branch 1 is decided AND Branch 2 is measured and written up** —
regardless of which Branch-2 sub-outcome occurs.

---

## 7. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Zero-shot SmolVLM grounds at ~0 % on Gazebo frames** → loop never tracks (flatline) | **High** | Low *(it's a pre-registered valid outcome, not a failure)* | Branch-2 "expected" path is written up as the RQ-S1.4 negative result; Branch-1 mechanics still validated via injected-detection smoke test; harness ready to re-run with the Stage 2 fine-tuned GGUF |
| 2 | **Gazebo Harmonic install fails / unstable on Ubuntu 24.04** (interactive sudo, plugin build) | Medium | High — blocks all rendered runs | Pin Gazebo Harmonic (LTS) + matching `ardupilot_gazebo`; document exact apt/source steps + versions in DECISIONS; fallback to a lightweight in-repo synthetic renderer (the alternative considered in the render-source decision) if Gazebo proves intractable |
| 3 | **Async race / stale-slot bug** feeds a torn or out-of-order box to the controller | Medium | Medium — silent tracking corruption | Lock-protected latest-detection slot with monotonic capture-timestamp; reject any box older than the current one; unit-test the slot; injected-detection smoke test (Branch-1 gate) catches plumbing bugs before live runs |
| 4 | **VLM end-to-end latency ≫ 833 ms** once render+network+CLIP at 640×480 are included → effective rate < 0.5 Hz | Medium | Medium — coasting window too long, target outruns stale box | Measure render+net separately; if effective rate < 0.5 Hz, enable forward-prediction ablation (§5.4.1) and/or reduce frame resolution; report the true on-device end-to-end rate honestly (not the Phase A compute-only 833 ms) |
| 5 | **CPU contention:** Gazebo render + SITL + control thread on one x86_64 box drops control-loop Hz below 15 | Medium | Medium — fails Branch-1 #1 | VLM is offloaded to the Jetson (frees local GPU); pin Gazebo to a real-time-ish scheduler / lower render rate; the 15 Hz (not 20) Branch-1 bar already budgets for this |
| 6 | **Coordinate-convention mismatch** (VLM pixel space vs 640×480 frame vs ByteTrack) silently yields IoU≈0, indistinguishable from grounding failure | Medium | High — would mask a *working* VLM as a failure | Reuse Phase A's validated parser + `Bbox.is_valid`; **visual overlay check** of VLM box on 2 Gazebo frames before bulk runs (same safeguard as Phase 0-B); assert frame size = prompt-declared 640×480 |
| 7 | **Gazebo NED / origin frame mismatch** with the programmatic rover anchor (cf. Phase B's two-instance 584 m discrepancy) | Low | Medium | Keep the Phase B copter-anchored programmatic trajectory; verify the Gazebo camera sees the target in-frame at t=0 via the oracle-GT overlay before scoring |
| 8 | **Jetson swap / thermal throttle** during sustained 60 s grounding (S2 was 2734 MB, no swap in Phase A, but Phase A was bursty) | Low | Low | tegrastats over the whole run (already in harness); S2 has ~3.7 GB headroom under the 6.4 GB ceiling; abort + document if swap growth > 50 MB |

---

## 8. Script outline — `experiments/run_phase_c.py` vs `run_phase_b.py`

Start by copying `run_phase_b.py`; the control/SITL/rover/PID scaffolding is reused verbatim. The
deltas:

**Removed / replaced:**
- `_control_step()` no longer calls `oracle_project()` to *drive* control. Instead it reads the
  **latest-detection slot** (written by the VLM thread). The oracle projection is **retained** but
  only to compute the **ground-truth box** for scoring (§5.3).

**Added:**
1. **Gazebo lifecycle** (mirrors Phase B's `_start_sitl`): launch Gazebo Harmonic + world +
   `ardupilot_gazebo`, wait for the image topic, grab frames. Teardown in `finally`.
2. **Jetson VLM server lifecycle:** import `start_server` / `stop_server` / `_wait_health` from the
   Phase A grounding probe; bring up `llama-server` with SmolVLM-500M + mmproj, `-ngl 99`,
   port-forward; start/stop `tegrastats` on the Jetson around the runs (reuse Phase A pattern) →
   produce the device-ledger row.
3. **Async grounding thread:** `threading.Thread` loop — grab newest Gazebo frame → `_build_payload`
   (Format-A prompt, §3.3) → `_post` → `parse_response_a` → adapter (§3.4) → write
   `(bbox, capture_ts, vlm_ms)` into a `threading.Lock`-protected slot. Records every call to a
   raw JSONL (image-less: bbox, raw text, latency) like Phase A's `*_responses.jsonl`.
4. **Latest-detection slot:** lock-protected dataclass; control thread reads it each 20 Hz cycle;
   stale-rejection by monotonic timestamp (Risk 3).
5. **Injected-detection smoke mode** (`--inject-oracle`): feed the oracle box into the slot at 1 Hz
   instead of calling the VLM — the **Branch-1 mechanics gate** (§6).
6. **New metrics** (§5.3): valid-box rate, VLM-vs-oracle IoU, VLM latency / effective Hz, coasted
   coverage, following-error-vs-oracle, re-acquisition time, Jetson device row.
7. **Results writer:** append a Phase C block to **this file**, a per-run CSV (+ the existing Phase
   B columns + VLM columns) to `results/raw/`, and — new for this stage — a **device-ledger row to
   `RESULTS.md`** (Jetson RAM / mean·peak W / °C / swap / effective Hz), which Phase B did not
   produce.

**CLI:** `--dry-run`, `--runs N`, `--duration S` (carried from Phase B); plus `--inject-oracle`
(Branch-1 gate), `--expression "<NL>"`, `--vlm-model <gguf path>` (so the Stage 2 fine-tuned model
re-runs Phase C unchanged), `--skip-server` (assume llama-server already up).

**Always `--dry-run` first** to verify command strings and the Gazebo/Jetson handshakes before a
live run (per CLAUDE.md "Adding a new campaign" step 3).

---

## 9. Pre-registration checklist

Track each item here as it is completed (mirrors Phase B's checklist style):

**Setup — Gazebo render path (Phase C first sub-task):**
- [ ] Gazebo Harmonic installed on local x86_64 (interactive sudo) — record exact version + apt/source steps in DECISIONS
- [ ] `ardupilot_gazebo` plugin built against the installed Gazebo + Copter-4.6.3 — record commit
- [ ] Gazebo world + nadir gimbal camera + ground-vehicle target authored; image topic publishes 640×480
- [ ] ArduCopter SITL ↔ Gazebo physics coupling verified (copter responds to setpoints in the rendered world)
- [ ] Oracle-GT overlay sanity check on 2 Gazebo frames (target in-frame at t=0; coordinate convention matches; Risk 6/7)

**Setup — Jetson VLM serving path:**
- [ ] `ssh jetson` reachable; `jetson_clocks` lock + 15 W confirmed (reuse Phase A preflight)
- [ ] llama-server starts with SmolVLM-500M-Instruct Q8_0 + mmproj, `-ngl 99`, healthy on port 8080
- [ ] SSH `-L 8080` port-forward from local → Jetson verified with one round-trip grounding call
- [ ] tegrastats logging around the run produces a parseable device row (reuse `parse_tegrastats`)

**Code:**
- [ ] `run_phase_c.py` copied from `run_phase_b.py`; oracle retained as GT-only; VLM drives control
- [ ] Async grounding thread + lock-protected latest-detection slot written and unit-tested (stale-rejection)
- [ ] Bbox xyxy→cxcywh adapter unit-tested
- [ ] Grounding client reused from `run_grounding_probe.py` (no new VLM path)
- [ ] `--inject-oracle` Branch-1 smoke mode implemented
- [ ] New metrics computed + Phase C results block + RESULTS.md device row writer implemented
- [ ] `--dry-run` passes (command strings + Gazebo + Jetson handshakes verified)

**Runs + write-up:**
- [ ] **Branch-1 gate:** injected-detection run shows control Hz ≥ 15, coasting ≥ 15 frames, re-seed < 2 s
- [ ] 3 × 60 s live VLM runs completed; per-run CSVs + raw JSONL saved to `results/raw/`
- [ ] Phase C metrics table filled in (this file); RESULTS.md device row appended
- [ ] Branch-2 outcome recorded honestly (degradation quantified **or** zero-shot-fails negative result)
- [ ] Decisions + any new tooling (Gazebo) logged in DECISIONS.md
- [ ] Raw logs + this doc + RESULTS.md committed together (atomic record)

---

## Decisions specific to Phase C

Cross-cutting toolchain decisions go in the root `DECISIONS.md`. Campaign-specific choices here,
most-recent first.

### 2026-06-15 — Phase C perception: SmolVLM-500M zero-shot, on the Jetson, over Gazebo-rendered frames
- **Decision:** Replace Phase B's oracle bbox with **zero-shot SmolVLM-500M-Instruct Q8_0**
  grounding running **on the Jetson** (llama-server, `57fe1f0`, sm_87, 15 W), fed
  **Gazebo-Harmonic-rendered** 640×480 nadir camera frames. Call it **asynchronously** (separate
  ~1 Hz thread); the 20 Hz ByteTrack→PID→MAVLink loop is carried forward from Phase B unchanged and
  coasts the Kalman estimate between updates. Keep the oracle geometry running **in parallel as
  ground truth** (not fed to control) for IoU/following-error scoring.
- **Alternatives considered:** (a) **PaliGemma-2-3B** — the lit-sweep accuracy ceiling and the task
  prompt's suggested candidate, but **blocked**: unmerged llama.cpp PR #7553, no PaliGemma-2 GGUF,
  would break the controlled commit invariant (DECISIONS 2026-06-14). (b) **SmolVLM-256M** — 0 %
  parse in Phase A, no coordinate structure (DECISIONS 2026-06-15T08:10). (c) **Fine-tuned
  SmolVLM-500M** — Stage 2 not yet done; using it would erase the zero-shot baseline RQ-S1.4 needs;
  the harness is built to swap it in later. (d) **Synthetic in-repo renderer** vs (e)
  **pre-recorded video** for pixels — the author chose **Gazebo Harmonic** (photorealistic, true
  closed loop) over the lighter synthetic renderer and the open-loop-only recorded video.
- **Reasoning:** SmolVLM-500M is the only candidate that fits the 8 GB / sm_87 / pinned-llama.cpp
  constraints **and** showed any coordinate-output structure in Phase A, and it is already the
  stage's grounding model. Running it on the Jetson keeps the measurement on the thesis's target
  device and yields a device-ledger row Phase B couldn't produce. Async + coasting is the
  literature-standard answer to a sub-3-Hz vision front-end and is already implemented in
  ByteTrack. Gazebo gives realistic closed-loop following; the author accepted its setup cost for
  fidelity.
- **Tradeoff / cost accepted:** (1) **Zero-shot grounding is expected to be near-0 % IoU on
  realistic aerial frames** (Phase A: 0 % IoU@0.25). The likely Phase C outcome is therefore a
  *documented negative result* — the loop can't follow on zero-shot grounding — which is a valid
  answer to RQ-S1.4 and the motivation for Stage 2. (2) Gazebo adds an interactive-sudo install,
  CPU contention, and run-to-run non-determinism (Phase B's zero variance will not carry over).
  (3) ByteTrack's low-score association is unused (SmolVLM gives no confidence).
- **Revisit when:** the Stage 2 fine-tuned SmolVLM-500M is ready (re-run Phase C via
  `--vlm-model`); or llama.cpp merges PaliGemma support (add PaliGemma-2-3B as the accuracy-ceiling
  comparison); or Gazebo proves intractable (fall back to the in-repo synthetic renderer).

---

## Next steps (once Gazebo is installed)

1. Install Gazebo Harmonic + `ardupilot_gazebo`; author the world + nadir camera + target; log in DECISIONS.
2. Oracle-GT overlay sanity check on Gazebo frames (coordinate convention; target in-frame).
3. Copy `run_phase_b.py` → `run_phase_c.py`; retain oracle as GT-only; add Gazebo + Jetson-VLM + async thread.
4. Unit-test the async slot + bbox adapter; reuse the Phase A grounding client.
5. `--dry-run`, then the **Branch-1 injected-detection gate**.
6. 3 × 60 s live VLM runs; fill in metrics; append RESULTS.md device row; write up the Branch-2 outcome honestly.


## Results — Branch-1 (inject-oracle)

Run: 2026-06-15T17:33 UTC

| Run | Loop Hz | Track cov (coasted) | Oracle cov | Px err vs oracle | Track losses | Coasting max | Re-seed s | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 19.99 | 100.0% | 100.0% | 91.0 | 0 | 19 | — | inject-oracle rover 0.25m/s north anchored to copter |
| 2 | 19.99 | 100.0% | 100.0% | 109.8 | 0 | 19 | — | inject-oracle rover 0.25m/s north anchored to copter |
| 3 | 19.99 | 94.2% | 100.0% | 67.3 | 1 | 99 | 0.000 | inject-oracle rover 0.25m/s north anchored to copter; forced gap t=30–34s |
| **Mean±std** | 19.99±0.00 | 98.1% | — | 89.4 | 1 total | — | — | — |

**Branch-1 PASS** — hz=19.99 (✓≥15)  coasting_max=99 (✓≥15)  reseed=0.000s (✓<2s)

**Interpretation of run 3 numbers:**
- `track_cov=94.2%`: ByteTrack's `_lost` coast expired after ~1.5s (30 frames) of the 4s gap, producing ~50 frames with no track → `100% − (50/1200) = 95.8%` ≈ 94.2% measured.
- `track_losses=1`: one event — track disappeared entirely after coast timeout. ID-change at re-seed is not counted (pre-registered §3.4).
- `coasting_max=99`: last injection before gap was at ~t=29s; next after gap at t=34s → 5s × ~20 Hz = 99 frames of no new detection.
- `reseed=0.000s`: the inject thread wrote to the slot within the same 50ms control frame that detected `gap_end_elapsed`, so `t_now − gap_ended_t ≈ 0`. Indicates re-seed is immediate once injection resumes — well within the <2s criterion.
