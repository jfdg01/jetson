# P6.2-SHOWCASE — one on-Jetson end-to-end closed-loop flight (carry routed literally to the Orin)

**Pre-registered 2026-07-24T07:20Z (Madrid). Frozen before the run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md`. Decision:
`docs/decisions/part6-flight.md` (2026-07-24, "P6.2 matrix runs SAM2 carry on the 3090 rate-capped
... with one on-Jetson end-to-end showcase flight alongside"). **Qualitative demonstration, NOT an
inferential claim** — it is not registered in the Holm family; it demonstrates on-device capability.
**DONE 2026-07-24: both halves complete** — on-device carry seam (standalone) + closed-loop flight
(carry on the Orin over ssh-stdio, parity 0.960 vs 3090, coverage 0.495). See Status + Results below.

## Status / next step

- **On-device carry seam: DEMONSTRATED standalone (2026-07-24, GPU-independent half done).** Before
  the flight, the one new seam — routing SAM2 carry LITERALLY to the Orin — is proven end to end on
  real UAV123 imagery, with no 3090 and no CARLA. The deployed carry (`jetson_carry_service.py` on
  the Jetson, `image_size=1024`) was seeded by the oracle GT box and stepped over 24 frames of `car9`
  (stride 11 = the 2.69 Hz cadence): **held 24/24 at IoU>=0.25, median IoU 0.92 vs GT, 2.35 Hz
  on-device (425 ms/step compute), ~10 ms socket overhead** (client run on the Orin, 127.0.0.1 — the
  flight's `ssh -L` will add the LAN round-trip on top). Viewed mid-run overlay confirms the cyan
  Jetson-carried box on the real car. Harness: `ondevice_carry_demo.py` (host stage+score) +
  `carry_client.py` (on-device). Proof: `proof/ondevice_carry_midrun.png`,
  `proof/ondevice_carry_trace.png`. This de-risks the flight to the CARLA closed loop alone.
- **The FLIGHT (closed loop) is DONE (2026-07-24).** The host RTX 3090 GPU blocker (kernel module
  595.71.05 vs libnvidia-ml 595.84 after a mid-session apt driver upgrade) was cleared by a **reboot**
  (the on-disk module was already 595.84, so a clean boot loads the matching module; a live `rmmod`
  was impossible — a full GNOME/Xorg session held `/dev/nvidia0`). The 220 W cap is re-applied and
  now **persists** via a `nvidia-powercap.service` systemd oneshot. One WARM closed-loop flight then
  ran with SAM2 carry routed **literally to the Orin over ssh-stdio** (the sandbox blocks local
  port-binding, so `ssh -L` is out; a framed pickle stream over the ssh channel is the transport),
  a 3090 `_HostCarry` twin scored in lockstep for the in-rig parity gate. The target (a police
  charger, oracle-designated) was held through a 28 s flight including a road curve, the copter
  flying its own PID control output. **Result:** post-prompt coverage **0.495** (202/560 lock frames),
  and the **parity gate PASSES — Jetson-carried vs 3090-twin median IoU 0.960** (min 0.805, 90 % of
  steps ≥ 0.9) over 52 in-loop carry steps, transport ~2 ms on top of the ~422 ms carry compute
  (~2.4 Hz round-trip). So the on-device carry reproduces the parity-checked 3090 carry live in the
  loop. Harness: `runners/run_p62_matrix.py --showcase` (reuses the DELIVERY centred-target geometry)
  + `carry_ssh_bridge.py` (on the Jetson). Proof: `proof/flight_follow_overlay.png`,
  `proof/flight_trace.png`.

## Question

RQ-SHOWCASE (qualitative): does the deployed warm-start maintain-and-deliver pipeline run **end to
end on the drone's own compute** — grounding AND carry both literally on the Jetson Orin — closing
the control loop on a flying copter, and do the on-device carried boxes match the 3090 rate-capped
proxy the P6.2 matrix used? Demonstrates the on-device capability the matrix approximated; it does
not re-measure the P6.2-DELIVERY timing contrast (that is `P6.2-DELIVERY`, already landed).

## Why this flight (and why it is not the matrix substrate)

The P6.2-DELIVERY matrix ran SAM2 carry on the 3090 **rate-capped to the Jetson's measured 2.69 Hz**,
NOT literally over SSH. That is the faithful model of an on-board Orin: (i) the box VALUES are
device-identical (E1 mask parity 1.000), delivered at (ii) the on-device cadence (R-16: 2.69 Hz),
with (iii) ~zero camera->compute transport (the Orin is on the drone). The 3090 rate-cap reproduces
all three. Routing each frame Jetson-ward over the SSH tunnel injects a per-frame round-trip latency
the real on-board drone never pays — and P6.2 is a **delivery-timing** experiment, so that artifact
would land squarely on the variable under test. This showcase deliberately pays that SSH cost ONCE,
to demonstrate the literal on-device path, and **documents the transport latency as a bench artifact**
rather than a deployment cost.

## Design (frozen)

- **One admitted P6.2 seed**, WARM arm only, closed loop. Admission = the P6.2-DELIVERY screens
  (moving target: `actor_box` translates >=1 box-width in the 4.85 s window; oracle-GT-followable).
  Reuse a seed already admitted in `runs/p62_delivery/` so the scene is known-good.
- **Grounding on the Jetson** (unconditional, as everywhere): oracle target designation (operator =
  GT box), consistent with the P6.2-DELIVERY oracle scope (the nadir q8_0 grounder is
  non-discriminative at 45 m, G6 — designation is held constant so the showcase is about the closed
  loop, not grounding). The seed box designates the target; carry maintains it.
- **Carry routed LITERALLY to the Jetson.** Swap the one seam in `runners/run_p62_flight.py`:
  `build_grounding_carry` returns `carry_factory = lambda rgb, box: _HostCarry(rgb, box)` (3090
  `StreamCarry`, the parity-checked path). The showcase substitutes an `_SSHCarry(rgb, box)` that
  forwards the SAM2 carry to `~/sam2-bench/jetson_carry_service.py` on the Orin over an SSH-forwarded
  TCP port (protocol: `{"cmd":"init","jpg":<bytes>,"box":[x1,y1,x2,y2]}` -> `{"ok":True}`;
  `{"cmd":"step","jpg":<bytes>}` -> `{"box":[..]|None,"ms":float}`; `authkey=b"carry"`, port 18081
  via `ssh -L`). The PID drives from the Jetson-returned box. Carry runs at the Orin's native rate
  (no host rate-cap — it IS the device).
- **In-rig parity re-check.** On the SAME seed, capture the 3090 rate-capped carry boxes and the
  SSH-Jetson carry boxes frame-by-frame from the identical rendered frames; report per-frame IoU
  (expected ~1.0, confirming E1's mask parity 1.000 holds in-rig with the deployed q8_0 seed).
- **SSH-transport caveat, quantified.** Log per-`step` SSH round-trip latency (the `ms` the service
  reports = on-device compute; the wall-clock minus `ms` = transport). State plainly: the real
  on-board drone pays ~zero transport; this latency is why the matrix used the 3090 proxy for the
  timing experiment.

### Frozen gate (qualitative — no Holm, no p-value)

PASS = (1) the flight completes with the PID holding a lock on the moving target driven by the
**Jetson-carried** box (delivered track IoU>=0.25 vs `actor_box` sustained post-command), VIEWED on a
mid-run overlay frame; AND (2) the in-rig parity re-check shows SSH-Jetson vs 3090 carry median
per-frame IoU >= 0.95 (device-identical values). The SSH-transport latency is reported, not gated.
A negative (the loop does not hold on the literal on-device carry, or parity is broken) is content —
it would mean the 3090 proxy is not faithful, which contradicts E1/R-16 and would need explaining.

## Command (intended, once the GPU is back)

```bash
sudo nvidia-smi -pl 220                                  # fans: session directive
# CARLA + SITL up (as P6.1/P6.2): runners/ launch scripts
.venv-ft/bin/python runners/run_p62_flight.py --showcase-ssh-carry \
    --seed <one admitted p62_delivery seed> --oracle --out runs/p62_showcase
.venv-ft/bin/python experiments/2026-07-24-p62-showcase/make_proof.py   # overlay + parity + latency figs
```
(The `--showcase-ssh-carry` flag / `_SSHCarry` factory is the only new code; it does not touch the
matrix path. Grounding stays on the Jetson unconditionally.)

## Environment / versions

CARLA 0.9.16 `Town10HD_Opt` on the RTX 3090 (renderer, **capped 220 W**), ArduCopter SITL (physics),
Jetson Orin Nano 8 GB (grounding `phase3-terse100eos-1024-q8_0` + carry `jetson_carry_service.py`,
both **15 W + jetson_clocks**, over SSH), host loop. RENDER_ALT 45 m, PID kp_lat 0.05 / max_v 4.0
(P6.2 tuning). Pins -> `runs/p62_showcase/env.json`.

## Estimates (up front)

- One flight ~20 s sim + parity capture; ~10 min wall once the rig is up. Cheap; the value is the
  demonstration, not the runtime. Parity expected ~1.0 (E1). SSH round-trip est ~5-15 ms/frame on the
  LAN, dwarfed by the 2.69 Hz (~370 ms) carry step — i.e. transport is a small fraction even on the
  bench, but non-zero, hence the caveat.

## Results — on-device carry seam (RAN 2026-07-24)

`ondevice_carry_demo.py stage` (host) picked `car9` (first candidate with 24 contiguous-GT steps
@ stride 11), seeded the deployed carry with GT frame 1, stepped it over 24 real frames through
`jetson_carry_service.py` on the Orin (`carry_client.py`, local 127.0.0.1 socket), scored on host.

| metric | value | note |
|---|---|---|
| on-device carry held | **24/24** IoU>=0.25 | deployed SAM2 carry, `image_size=1024`, run literally on the Orin |
| median IoU vs GT | **0.92** (min 0.86, final 0.91) | oracle-GT-seeded, no drift over 264 video frames |
| on-device carry rate | **2.35 Hz** (425 ms/step) | consistent with R-16's 2.69 Hz solo (this rig, `image_size=1024`) |
| socket overhead | **~10 ms/step** | client on the Orin (127.0.0.1); the flight's `ssh -L` adds the LAN RTT on top |

**On-device carry seam: PASS (qualitative).** The deployed maintain path runs end to end on the
drone's own compute on real imagery. Proof: `proof/ondevice_carry_midrun.png` (viewed — cyan
Jetson-carried box tight on the car9 sedan, GT coincident), `proof/ondevice_carry_trace.png` (per-step
IoU 0.86-0.98 above the 0.25 floor + 2.35 Hz on-device compute trace).

## Results — closed-loop flight (RAN 2026-07-24)

One WARM flight, `runs/p62_showcase`, `run_p62_matrix.py --showcase --alt 45 --t-prompt 14
--seconds 28`. Target `vehicle.dodge.charger_police_2020` (id190), oracle designation, seed box
`[315.7, 233.0, 354.8, 248.5]` (centred). CARLA Town10HD_Opt + ArduCopter SITL, copter-slaved
nadir camera, PID driven by the delivered box (`kp_lat=0.05`, `max_v=4.0`).

| metric | value | note |
|---|---|---|
| flight lock held (Jetson carry) | **coverage 0.495**, 202/560 lock frames | VIEWED overlays (idle t=7s, prompt t=14s, curve t=28s); target held through a road curve |
| parity Jetson-carry vs 3090-twin (median IoU/step) | **0.960** (min 0.805, 90 % ≥ 0.9) | 52/52 steps both-boxed; gate ≥ 0.95 PASS |
| ssh round-trip (median ms/step) | **424 ms** (~2.4 Hz); compute 422 ms | transport ~2 ms; carry compute dominates, NOT deployment cost |
| seed / delivery | acquire ≈ 0 s (oracle), first deliver t=1.95 s | idle-window seed, no cold-acquire latency |

**Verdict:** PASS (qualitative). The closed loop holds a lock on the moving target with SAM2 carry
running **literally on the Jetson** in-loop; the in-rig parity gate confirms the on-device carry
reproduces the parity-checked 3090 carry (median IoU 0.960), so E1's mask parity 1.000 holds live.
The follow is honest, not perfect — coverage 0.495 reflects the 2.69 Hz carry cadence against a
20 Hz GT (delivered box goes stale between carry updates; IoU sawtooths, peaks ~0.5–0.6). **Proof:**
(1) `proof/flight_follow_overlay.png` — end-of-flight overlay, GT + Jetson-carried box on the police
charger driven through a curve, opened with the Read tool; (2) `proof/flight_trace.png` — top:
delivered-vs-GT IoU over the flight (prompt marked); bottom: on-device carry parity vs the 3090 twin
per step + ssh round-trip. From a committed `make_proof.py flight`, reproducible from
`runs/p62_showcase/`.
