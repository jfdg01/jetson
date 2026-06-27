# Phase C — VLM in the Loop

**Pre-registered:** 2026-06-15 | **Completed:** 2026-06-15
**Status:** COMPLETE — Branch-1 PASS · Branch-2 negative (pre-registered expected outcome)
**Answers:** RQ-S1.4 — "Replacing oracle with best zero-shot VLM: how much does tracking degrade?"

---

## What changed from Phase B

Phase B's oracle bbox (geometric projection of SITL world-state) replaced by **SmolVLM-500M-Instruct Q8_0** running on the Jetson, grounding an NL expression in Gazebo-rendered 640×480 aerial frames. Everything downstream (ByteTrack → cascade PID → MAVLink) unchanged.

| Stage | Phase B | Phase C |
|---|---|---|
| Bbox source | `oracle_bbox.project()` | SmolVLM-500M zero-shot grounding |
| Bbox host | x86_64 | **Jetson Orin Nano 8 GB** (llama-server, sm_87, 15 W) |
| Bbox rate | ~25 Hz synchronous | **~1 Hz async thread** |
| Camera frames | none (geometry) | Gazebo Harmonic 640×480 nadir |
| ByteTrack / PID / MAVLink | — | identical |

---

## Model selection

**SmolVLM-500M-Instruct Q8_0** — only candidate fitting all constraints: aarch64/JetPack/sm_87, ≤6.4 GB RAM, pinned llama.cpp `57fe1f0`, **and** showed any coordinate-output structure in Phase A.

| Candidate | Rejected because |
|---|---|
| SmolVLM-256M | Phase A: 0% parse, no coordinate structure |
| PaliGemma-2-3B | llama.cpp PR #7553 unmerged; no GGUF; breaks controlled-runtime invariant |
| Fine-tuned SmolVLM-500M | Stage 2 not done; would erase the zero-shot baseline RQ-S1.4 needs |

Phase A carried-forward numbers (Jetson, 15 W, `57fe1f0`):
- Latency: **833 ms/frame (≈1.2 Hz)**; RAM: 2734 MB; zero-shot IoU@0.25 = **0%**, parse = 4%

---

## Architecture

```
LOCAL x86_64 — sim + control                     JETSON — perception
─────────────────────────────────             ────────────────────────
Gazebo Harmonic → 640×480 JPEG ──HTTP POST──► llama-server SmolVLM-500M
ArduCopter SITL ◄── MAVLink ◄──┐             (-ngl 99, port 8080)
                               │  ◄──HTTP 200 (bbox text)──┘
run_phase_c.py:
  • control+track thread @20 Hz  (ByteTrack coast + PID + MAVLink)
  • vlm-grounding thread  @~1 Hz (async; never blocks control)
  • shared latest-detection slot (lock-protected, monotonic timestamp)
```

**Why split:** VLM must run on the Jetson (thesis device); SITL + Gazebo stay on x86_64 to avoid conflating measurement device with stimulus.

**Async + coasting:** ~1 Hz VLM → 19/20 control cycles use Kalman coast. Failure handling: `null`/unparseable → no detection, ByteTrack coasts. After `LOST_TIMEOUT_S=3.0 s` of no valid box → track-loss declared; next valid box re-seeds.

**Prompt (fixed, Format A):**
```
Give the bounding box of '<EXPRESSION>' as JSON
{"x1":...,"y1":...,"x2":...,"y2":...} in pixel coordinates.
Image size is 640×480. If not present, reply null.
```

**Bbox adapter:** VLM `xyxy` → ByteTrack `{cx,cy,w,h,score=1.0}` (SmolVLM emits no confidence; low-score branch unused).

---

## Success criteria

**Branch 1 — Integration mechanics** (all three required):
1. Control loop ≥15 Hz despite async VLM
2. ByteTrack coasts ≥15 frames with no ID change after injected detection
3. Re-seed after forced gap within <2 s

Validated via **injected-detection smoke test** (`--inject-oracle`) before live VLM runs.

**Branch 2 — Tracking quality** (reported, not pass/fail):
- Stretch ("zero-shot usable"): valid-box rate ≥30% AND mean px err <100 AND ≥1 complete run
- **Expected ("zero-shot not usable"):** valid-box rate ≈0%, track never reliably seeded — valid negative result for RQ-S1.4

---

## Results — Branch-1 (inject-oracle)

**Run:** 2026-06-15T17:33 UTC

| Run | Loop Hz | Track cov | Oracle cov | Px err vs oracle | Track losses | Coasting max | Re-seed s |
|---|---|---|---|---|---|---|---|
| 1 | 19.99 | 100.0% | 100.0% | 91.0 | 0 | 19 | — |
| 2 | 19.99 | 100.0% | 100.0% | 109.8 | 0 | 19 | — |
| 3 | 19.99 | 94.2% | 100.0% | 67.3 | 1 | 99 | 0.000 |
| **Mean** | 19.99 | 98.1% | — | 89.4 | 1 total | — | — |

**Branch-1 PASS** — hz=19.99 (✓≥15) · coasting_max=99 (✓≥15) · reseed=0.000 s (✓<2 s)

Run 3 notes: forced gap t=30–34 s → coast expired after ~1.5 s (30 frames), producing ~50 trackless frames (track_cov 94.2%). Re-seed was immediate (<50 ms frame) once injection resumed.

---

## Results — Branch-2 (live VLM)

**Run:** 2026-06-15T17:40 UTC · Gazebo Harmonic 8.13.0 headless · ArduCopter SITL Copter-4.6.3 · SmolVLM-500M Q8_0 · Jetson Orin Nano 8 GB · llama.cpp `57fe1f0` sm_87 · 15 W locked

| Run | Loop Hz | Track cov | Oracle cov | Px err vs oracle | Track losses | VLM calls | Valid |
|---|---|---|---|---|---|---|---|
| 1 | 19.98 | 24.3% | 41.8% | 209.3 | 8 | 64 | 10 (15.6%) |
| 2 | 19.99 | 16.7% | 37.9% | 234.6 | 5 | 67 | 7 (10.4%) |
| 3 | 19.99 | 21.2% | 37.9% | 127.7 | 6 | 77 | 9 (11.7%) |
| **Mean** | 19.99 | 20.7% | — | 190.5 | 19 total | 208 | 26 (12.5%) |

**Branch-2: NEGATIVE (zero-shot not usable)** — valid_rate=12.5% (<30%) · px_err=190.5 (≥100) · no run completed without track loss

### Comparison: Phase B oracle vs Phase C zero-shot

| Metric | Phase B oracle | Phase C zero-shot | Δ |
|---|---|---|---|
| Track coverage | ~100% | 21% | −79 pp |
| Oracle/GT coverage | ~100% | 39% | −61 pp |
| Mean px err vs oracle | 12.9 px | 190.5 px | +178 px (+1380%) |
| Track loss events (3 runs) | 0 | 19 | +19 |
| Control Hz | 19.99 | 19.99 | 0 |

### Interpretation

- **Parse rate 12.5%** (26/208): higher than Phase A's 4% on RefDrone (simpler Gazebo scene), but 87.5% of calls returned free-text or degenerate whole-image boxes (rejected by `Bbox.is_valid`).
- **Track coverage 21%**: sparse valid detections (~1 every 8 s) seed a track that coasts only 1.5 s (30 frames at 20 Hz) before expiring → trackless for ~6.5 s between seeds.
- **Oracle coverage 39%**: no reliable perception → copter hovers; rover walks north at 0.25 m/s and exits the 60° nadir FOV (~5.8 m radius at 10 m AGL) after ~25 s. Drop is a *consequence* of tracking failure, not independent.
- **Pixel error 191 px**: when a track is active it seeds from a likely-wrong VLM bbox, driving PID toward random positions.
- **19 track losses**: consistent with ~1 valid detection/8 s and a 1.5 s coast window (~1 loss/9.5 s over 3×60 s).

**Conclusion:** Pre-registered expected outcome confirmed. Zero-shot SmolVLM-500M cannot sustain closed-loop tracking of an aerial target. **Stage 2 fine-tune is load-bearing, not optional.** (RQ-S1.4 answered.)

---

## Decision (2026-06-15)

SmolVLM-500M Q8_0 as zero-shot perception, Jetson-hosted, Gazebo frames, async + coasting. Only candidate satisfying all hardware constraints with coordinate output in Phase A. Running on Jetson produces a device-ledger row Phase B couldn't. Gazebo accepted for realistic closed-loop fidelity despite setup cost and run-to-run non-determinism.

**Revisit when:** Stage 2 fine-tune done (re-run Phase C via `--vlm-model`); or llama.cpp merges PaliGemma support.
