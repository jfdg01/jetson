# P6.2-SHOWCASE — one on-Jetson end-to-end closed-loop flight (carry routed literally to the Orin)

**Pre-registered 2026-07-24T07:20Z (Madrid). Frozen before the run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md`. Decision:
`docs/decisions/part6-flight.md` (2026-07-24, "P6.2 matrix runs SAM2 carry on the 3090 rate-capped
... with one on-Jetson end-to-end showcase flight alongside"). **Qualitative demonstration, NOT an
inferential claim** — it is not registered in the Holm family; it demonstrates on-device capability.

## Status / next step

- **PRE-REGISTERED, BLOCKED on the host GPU (2026-07-24).** The host RTX 3090 has an nvidia
  kernel-module / userspace version mismatch — loaded module **595.71.05** (`/proc/driver/nvidia/version`)
  vs libnvidia-ml **595.84** (an apt driver upgrade landed mid-session, 2026-07-22..24, without a
  module reload). `nvidia-smi` fails: `Failed to initialize NVML: Driver/library version mismatch`.
  **CARLA cannot render without the GPU, so the closed-loop flight cannot run.** Host `sudo` needs a
  password (not NOPASSWD, unlike the Jetson), so the fix is a **human action**:
  ```bash
  # no display manager holds the GPU here, so a module reload (no reboot) should suffice:
  sudo rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia && sudo modprobe nvidia nvidia_uvm
  nvidia-smi                 # confirm it initializes
  sudo nvidia-smi -pl 220    # re-apply the 220 W cap (session directive: keep the fans sane)
  # if rmmod reports the module is in use, a reboot is the fallback.
  ```
  Everything downstream of a working GPU is ready: the Jetson SSH-carry path is already proven end to
  end (R-16 measured it at 2.69 Hz using this exact `jetson_carry_service.py`), the rig exists
  (`runners/run_p62_flight.py` / `run_p62_matrix.py`), and the carry backend is swappable at one seam
  (below). Once the GPU initializes this is a single flight + a parity re-check.

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

## Results (TBD — blocked on the host GPU reload)

| metric | value | note |
|---|---|---|
| flight lock held (Jetson carry) | | VIEWED overlay frame |
| parity SSH-Jetson vs 3090 (median IoU/frame) | | expected >= 0.95 (E1 1.000) |
| SSH round-trip latency (median ms/frame) | | bench artifact, not deployment cost |

**Verdict:** TBD. **Proof (>=2):** (1) mid-run flight overlay with the Jetson-carried track on the
target, opened with the Read tool; (2) parity figure (SSH-Jetson vs 3090 carry IoU per frame); (3)
SSH round-trip latency distribution. From a committed `make_proof.py`, reproducible from
`runs/p62_showcase/`.
