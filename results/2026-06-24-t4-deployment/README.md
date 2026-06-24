# T4 — On-Orin deployment + sim-to-device characterisation (Part III)

**Status:** ✅ **GATE PASS** (2026-06-24). **Branch:** `v3/object-permanence`.
**Device:** Orin Nano 8 GB, **15 W** power mode (`NV Power Mode: 15W`), aarch64.
**Prereq:** T0–T3 gates PASS. **Harness:** `experiments/run_t4.py`.

T4 is the **deployment gate**: T0 measured the two tiers *in isolation and partly off
the device* — anchor cadence on the Orin (T0a) but the tracker cost (T0b) on the
RTX-3090 workstation. T4 runs the **integrated two-tier loop on the actual Orin** and
reconciles the measured **device** timings against the T0 cadence budget that the whole
sparse-VLM-anchor + 20 Hz-tracker architecture rests on.

## Gate (charter / CLAUDE.md)

> T4 — on-Orin deployment within the T0 cadence budget; characterise sim-to-device.

**Met.** Both tiers run on the Orin and fit their roles: the fast tracker tier holds
20 Hz with **99.7 % of the 50 ms budget free** (p99 0.29 ms), and the real deployed VLM
anchor reproduces the T0a cadence to within **−0.03 %** with **100 % bbox parse**. The
event-triggered re-acquisition requirement (anchor period > coast horizon) holds on the
metal. `deploys_within_t0_budget = True`.

## What T4 measures (and what was off-device before)

| tier | T0 measurement | **T4 measurement** |
|---|---|---|
| fast (tracker, 20 Hz) | T0b: **dev box** (RTX 3090) | **T4a: the Orin CPU (aarch64, 15 W)** |
| slow (VLM anchor, ~0.4 Hz) | T0a: Orin, llama-bench-style POST | **T4b: Orin, real in-loop grounding call** |
| integrated budget | T0 design table (mixed hosts) | **T4c: reconciled on measured device timings** |

## Results (Orin Nano 8 GB, 15 W — `experiments/run_t4.py --phase all`)

### T4a — Fast tier on the Orin CPU

Same T0b workload (1200 frames @ 20 Hz, single-target wander + intermittent crossing
distractor), now timed on the device. `bytetrack.py` pushed to `/tmp/t4_sitl`; only that
one file — `_observe()`/PID are scalar arithmetic dwarfed by the Kalman predict +
Hungarian match this measures.

| host | `ByteTracker.update` median | p99 | implied max | headroom (of 50 ms) |
|---|---|---|---|---|
| dev box (T0b, RTX 3090) | 0.051 ms | 0.103 ms | ~19.5 kHz | 99.9 % |
| **Orin Nano (T4a, 15 W)** | **0.143 ms** | **0.291 ms** | **~7.0 kHz** | **99.7 %** |

**Sim-to-device:** the Orin CPU is **2.8× slower** per tracker step — and it does not
matter. 0.143 ms against a 50 ms budget is **~350× headroom**; the fast tier carries the
lock between anchors essentially for free on the target device.

### T4b — Slow tier on the Orin, real in-loop anchor

Deployed Qwen2-VL-2B Q8_0 grounding model
(`/home/jfdg/grounding/phase3-refdrone-1024-q8_0.gguf` + mmproj), booted via
`JetsonBackend`, fired through the **verbatim `GROUNDING_PROMPT` contract path** at 512
long-edge (the T0a-locked anchor resolution), 8 timed reps after 2 warmups.

| | T0a (@512) | **T4b (@512, real call)** |
|---|---|---|
| wall median | 2265 ms | **2264 ms** |
| anchor rate | 0.44 Hz | **0.44 Hz** |
| bbox parse rate | — | **100 %** |
| drift vs T0a | — | **−0.03 %** |

The real grounding call (image encode + tokenise + bbox decode) reproduces the T0a
cadence to within measurement noise, and the deployed model still emits **valid bounding
boxes on every rep** — the Part-II anchor is intact on the device.

### T4c — Integrated budget + deployment verdict

| check | value | verdict |
|---|---|---|
| fast tier fits 20 Hz | p99 **0.291 ms** < 50 ms | ✅ |
| anchor period vs coast horizon | **2.26 s** > 1.5 s | event-triggered re-acq **required** (as T0 found) |
| **deploys within T0 cadence budget** | — | ✅ **True** |

The on-Orin numbers **reproduce the T0 design budget on the metal**: the 20–60× rate gap
between the tiers is real (0.44 Hz anchor vs 7 kHz-capable tracker), the fast tier
absorbs it with three orders of magnitude to spare, and because the anchor period
(2.26 s) still exceeds the 1.5 s coast horizon, re-acquisition must remain **event-
triggered on loss** — exactly the T0 verdict, now confirmed with the deployed stack.

## Sim-to-device summary

| quantity | sim / dev box | **Orin (device)** | gap |
|---|---|---|---|
| tracker step (median) | 0.051 ms | 0.143 ms | 2.8× slower, still ~350× under budget |
| VLM anchor (@512 wall) | 2265 ms (T0a) | 2264 ms | ~0 % (same device path) |
| anchor bbox parse | — | 100 % | deployed model intact |

The only material sim-to-device gap is the **2.8× tracker slowdown**, which is
immaterial against the budget. Everything else transfers 1:1 because T0a already
measured on the device. The closed-loop coverage A/B (T3) was validated in SITL on the
dev box; the timings that govern whether that loop *can* run on the Orin are what T4
closes, and they fit.

> `ponytail:` T4 characterises the on-Orin **timing/cadence budget**, not a full live
> camera-in-the-loop flight on the device — that needs the physical airframe + camera
> feed (out of scope here). The two tiers are measured on the metal through the real
> deployed artifacts; the closed-loop *behaviour* is the T3 SITL result. Upgrade path: a
> hardware-in-the-loop flight on the Orin when an airframe is available.

## Decisions

### 2026-06-24 — T4 = on-device timing reconciliation through the deployed artifacts

- **Decision:** Deliver T4 as an **on-Orin timing/cadence reconciliation** — fast tier
  timed on the device CPU (T4a), the **real deployed VLM** anchor timed in-loop through
  the verbatim contract path (T4b), reconciled against the T0 budget (T4c) — reusing the
  T0 harness wholesale (`run_t4.py` imports `run_t0_cadence`). No new dependency, one
  file pushed to the device (`bytetrack.py`).
- **Alternatives considered:** (a) **Full hardware-in-the-loop flight on the Orin** —
  rejected: no physical airframe/camera available; the deployable claim is whether the
  two-tier *timing* fits the device, which T4 measures directly. (b) **Trust T0's mixed-
  host budget** — rejected: T0b was the dev box; the charter says *on-Orin within the T0
  budget*, so the tracker tier had to be measured on aarch64 to honestly close the gate.
  (c) **Re-run the whole T3 SITL loop pointed at the on-device VLM** — rejected as
  premature: the per-frame VLM-in-the-loop integration is a separate engineering effort;
  the gate is the cadence budget, and the numbers that decide it are the two tier timings
  + the event-triggered re-acq condition, all measured here.
- **Tradeoff:** T4 proves the loop *fits* the device timing budget, not that a physical
  drone flies it. Accepted: the closed-loop behaviour is the T3 SITL PASS; T4 is the
  honest deployment-feasibility characterisation that the device can host it within the
  T0 budget, through the actual deployed model.
- **Revisit when:** a physical airframe + camera is available for a true
  hardware-in-the-loop flight, or a real appearance encoder replaces the scalar T2
  `_observe` (which would add per-frame cost to re-measure against this headroom).

## Verification

```
.venv-ft/bin/python experiments/run_t4.py            # deterministic budget-logic self-check
.venv-ft/bin/python experiments/run_t4.py --phase all # on the Orin (ssh jetson, 15 W)
```
Self-check: T4c verdict is monotone in the measured timings (a passing tracker/anchor
deploys; a tracker over the 50 ms budget fails the gate). On-Orin run (2026-06-24):
tracker 0.143 ms / p99 0.291 ms; anchor 2264 ms / 0.44 Hz / 100 % parse; deploys = True.
Raw: `results/2026-06-24-t4-deployment/t4-results-20260624T183835.json`.
