# P5.8 — Scene-generator transport fix (persistent requester) + capability gate re-run

**Pre-registered:** 2026-07-17T15:09Z (Madrid wall-clock).
**Status:** PRE-REGISTERED, not yet run.
**Branch:** `experiment/scenegen-transport`.
**Division of labour:** design + patches by Fable; **Opus runs the matrix and fills
the Results section only — do NOT re-patch code.** All files under "Code changes"
are already committed. If a run crashes on an infra error, follow the abort
criteria below — never silently re-run a completed cell.

## Research question

**RQ-P5.8:** With the per-frame service calls moved from ephemeral `gz service`
CLI subprocesses (the P5.7 killer: ~480 short-lived transport nodes per run, MTTF
~236 calls) to **one persistent gz-transport requester node** living in a
dedicated no-subscriber child process, plus a reply-lost-aware retry layer — does
the select-arena rig now complete the 4-run matrix and pass the unchanged P5.7
capability gates? Meeting ALL of:

- **G0 completion (new — the gate P5.7 actually failed):** every gating run
  reaches finalize with 240/240 frames AND ≤ 12 failed-then-recovered service
  calls (`g0_retries_pose + g0_retries_step`; retries are recorded, not hidden).
- **G1 render-alive** (per run): 0 dead frames (std ≤ 5), 0 byte-identical
  consecutive frames, camera sim-stamps advance by exactly 40 ms every frame.
  (G1 also mechanically catches a double-step from the retry layer: a re-issued
  step that had in fact executed would show an 80 ms stamp jump.)
- **G2 GT-on-vehicle** (per run, both cars): median in-box colour purity ≥ 0.30
  AND ≥ 4× the lateral control-box purity (same definition as P5.7).
- **G3 co-visibility** (per run): both cars visible with bbox area ≥ 150 px in
  ≥ 80% of frames.
- **G4 determinism:** (a) same seed, fresh server session (`seed101_A` vs
  `seed101_D`) → canonical GT (sim-stamps excluded) byte-identical AND frames
  mean |diff| ≤ 2.0 with frac(|diff|>8) ≤ 1%; (b) different seeds → frame-0
  target positions ≥ 1 m apart pairwise.
- **G5 throughput** (per run): ≥ 0.5 generated frames/s wall.
- **V visual gate** (per run, judged by Opus from the dumped PNGs — see "Visual
  verification"): the overlay frames actually show what G1–G3 claim.

**Overall verdict: YES iff G0,G1,G2,G3,G5 pass on all 4 runs AND G4a AND G4b AND
V passes on all 4 runs.** Anything else is NO with the failing gate named.
`verdict_p58.py` computes G0–G5 mechanically; V can only downgrade its output.
G1–G5 thresholds are **identical to P5.7** — the capability claim is unchanged;
only the plumbing changed.

## Context & rationale (audit summary)

**P5.7 audit (adversarial, this cycle).** The NO [infra FAIL] verdict is
**valid**: raw logs match the record (attempt 1 died at frame 127 on
`set_pose_vector`, attempt 2 at frame 108 on `world control`, server ALIVE both
times, exactly one `NodeShared::RecvSrvRequest() ... Host unreachable` per server
log), and I independently re-verified the cross-session byte-identity claim
(frames 0000/0060/0107 of the two attempts byte-identical). The
orphaned-server-contamination alternative is refuted by that byte-identity plus
the executor's verified process-group kills. Two amendments to the post-mortem:

1. **The memoryless "0.42%/call" model is probably wrong.** Failures at ~254 and
   ~216 calls are suspiciously close for a geometric distribution (CV = 1 —
   draws of 30 and 700 would be unremarkable); two near-identical times-to-failure
   weakly suggest **cumulative transport-state degradation** from ephemeral-node
   churn (e.g. server-side ZMQ/discovery state accumulating dead endpoints), not
   a constant hazard. n=2 cannot decide. Design consequence either way: the
   primary fix is **eliminating the churn** (persistent node); retry-on-timeout
   alone — which keeps the churn — would be the weaker lever and was rejected as
   the primary mechanism (kept as a safety net).
2. **"Only GT projection remains untested" was slightly overstated** — the P5.7
   design smoke overlays (`../2026-07-17-sim-scenegen/curation/smoke900_overlay_*.png`)
   do show tight GT boxes on both cars, so projection was visually verified once;
   what was untested is projection at gating scale across seeds. This run tests it.

**Design-time probes (this cycle, disclosed — run before pre-registration to
de-risk the design, all on the RTX 3090 workstation, gz sim 8.14.0):**

- pybind `gz.transport13.Node.request()` exists with the needed signature and the
  gz.msgs10 protos parse from the exact text-format strings scenegen already
  builds — the persistent-requester design needs no request rewrite.
- **Stress probe** (`probe_stress.py`, committed; result
  `curation/probe_stress.json`): 2400 alternating set_pose_vector/control calls
  through the real `ProxyClient` code path against a live fresh server — **0
  failures, 0 proxy restarts, ~0.3 ms p50/call** (CLI was ~290 ms and failed
  ~1/236). That is 5× the per-run call count and 10× the P5.7 mean time to
  failure, on the same two services that failed.
- **Full-length 240-frame design smoke** (seed 900 — NOT a gating seed;
  `curation/smoke900_p58_results.json` + `curation/smoke900_p58_overlay_f0120.png`
  / `_f0180.png`, overlays viewed and PASS-looking): completed 240/240 at
  **8.32 fps** (P5.7: 1.48 fps), 0 retries / 0 lost replies / 0 proxy restarts,
  0 dead frames, stamps exact, purity 0.80/0.86, both-visible 1.0. P5.7's
  structural lesson applied: the smoke is **full length**, so run-length failure
  modes are inside what it can catch.

**Why the GIL crash does not come back:** the inherited gotcha
(`runners/sitl/GAZEBO_LIVE_FEED.md`) is that pybind `node.request()` **concurrent
with an image-subscriber callback in the same process** crashes on the GIL. The
persistent requester lives in its own child process (`scenegen.py proxy`) that
**never subscribes to anything**; the recorder keeps its subscribe-only node.
The crash precondition (request + subscriber callback in one interpreter) is
structurally absent. The stress probe and full smoke (which subscribe + request
simultaneously across the two processes) ran crash-free.

**Rejected alternative:** retry-on-timeout on top of the existing CLI transport
(no persistent node). Loser because (a) under the cumulative-degradation reading
of the P5.7 data, retries through yet more ephemeral nodes attack the symptom
while feeding the cause; (b) it keeps ~0.58 s/frame of CLI overhead (measured:
persistent proxy is ~1000× faster per call and lifts generation 1.48→8.3 fps);
(c) a retried world-control step is not idempotent, so retry logic alone still
needs the reply-lost frame-wait machinery — all of which is kept anyway as the
safety net. Recorded for DECISIONS.

**P5.6 call (one line):** `experiment/direct-delivery-select` (`df6de31`, unrun)
**stays PARKED** — still the live select lever, still the n=5-starved test this
generator exists to unblock; resume it on sim scenes once this gate passes.

## Code changes (already committed — Opus: do NOT edit these files)

| File | Change |
|---|---|
| `runners/scenegen.py` | **transport rewrite + hardening**: (1) `ProxyClient` + `proxy` subcommand — one persistent pybind requester `Node` in a dedicated no-subscriber child process, JSON-lines over pipes, auto-restart on hang; (2) retry layer — `set_pose_vector`/`create` idempotent-retry ×3; `world control` waits `RESPONSE_LOST_WAIT_S`=3 s for the frame before re-issuing (a lost *reply* ≠ an unexecuted step), counts `response_lost` separately; (3) **incremental artifacts** — `gt.jsonl` written+flushed per frame, `overlay_f*.png` written the moment frames 60/120/180 are captured (P5.7 wrote them only at finalize → mid-run death = V uncomputable; that cannot recur), `progress.json` every 40 frames with retry counters; (4) `results.json` gains `g0_*` counters; (5) `killserver` subcommand — kills select_arena servers **by process group** via /proc scan, excluding itself/ancestors/own group (fixes both recorded P5.7 teardown defects: nohup-wrapper pid kill orphaning the live ruby server, and `pkill -f "gz sim"` self-match); (6) selfcheck extended: proxy ping/pong + graceful failure on a nonexistent service + survives it |
| `experiments/2026-07-17-scenegen-transport/verdict_p58.py` | mechanical verdict from `runs/*` (G0–G5; G1–G5 thresholds byte-for-byte from P5.7) |
| `experiments/2026-07-17-scenegen-transport/make_proof.py` | proof grid + determinism figure + transport before/after figure + clip copy |
| `experiments/2026-07-17-scenegen-transport/probe_stress.py` | design-time transport stress probe (kept: reproduces `curation/probe_stress.json`) |
| `curation/*` | design-time probe + full-length smoke provenance (see above) |

Self-check (no gz server, no GPU needed):
`.venv-ft/bin/python runners/scenegen.py selfcheck` → must print `scenegen selfcheck OK`.

## Run matrix (Opus starts here)

Config: **RTX 3090 workstation only — the Jetson is NOT used** (as in P5.7; no
on-device claim in RQ-P5.8). gz sim 8.14.0 (Harmonic), Python 3.12.10 /
numpy 2.4.4 / opencv 4.13.0 via `.venv-ft`. No power-mode knob (desktop GPU,
stock clocks).

4 gating runs, **one fresh server session each** (session-per-run is what makes
G4a cross-session): `seed101_A`, `seed202_B`, `seed303_C`, `seed101_D`
(A/D = determinism pair). ~250 MB of PNG frames per run land in
`runs/<id>/frames/` (gitignored; `results.json` + `gt.jsonl` are tracked).
Nothing clobbers between runs; **never delete a completed run dir.**

Per run (repeat for `SEED`/`RUN` = 101/seed101_A, 202/seed202_B, 303/seed303_C,
101/seed101_D). **Keep the `nohup gz sim` launch as its own clean background
command — do not fold it into `&&` chains (the sandbox reaper kills gz+python
combos); the recorder is a separate command.**

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-scenegen-transport
SEED=101 RUN=seed101_A   # <-- change per run
mkdir -p $EXP/raw $EXP/runs

# 0. guarantee no stale server (kills by process group, verifies; exit 0 = clean)
.venv-ft/bin/python runners/scenegen.py killserver

# 1. fresh headless server, nohup'd alone
SITL=$PWD/runners/sitl/external/SITL_Models/Gazebo
__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
GZ_SIM_RESOURCE_PATH="$SITL/models:$SITL/worlds" \
nohup gz sim -s runners/sitl/worlds/select_arena.sdf > $EXP/raw/gz_$RUN.log 2>&1 &

# 2. wait for the camera topic (~15-25 s world load)
for i in $(seq 40); do gz topic -l 2>/dev/null | grep -q uav_cam && break; sleep 3; done
gz topic -l | grep uav_cam   # MUST print the image topic; if empty after 120 s see aborts

# 3. record (~1 min at the smoke's 8.3 fps + finalize; DONE line + results.json at end)
nohup .venv-ft/bin/python runners/scenegen.py record --seed $SEED --frames 240 \
    --out $EXP/runs/$RUN > $EXP/raw/rec_$RUN.log 2>&1 &
for i in $(seq 60); do test -f $EXP/runs/$RUN/results.json && break; sleep 5; done
tail -5 $EXP/raw/rec_$RUN.log   # expect "[scenegen] DONE ..."
cat $EXP/runs/$RUN/progress.json  # retry counters for the Results table

# 4. kill this session's server (same verified process-group kill as step 0)
.venv-ft/bin/python runners/scenegen.py killserver
```

After all 4 runs:

```bash
# mechanical verdict (paste its full output into Results)
.venv-ft/bin/python experiments/2026-07-17-scenegen-transport/verdict_p58.py

# proof deliverables (grid, determinism, transport before/after, clip)
.venv-ft/bin/python experiments/2026-07-17-scenegen-transport/make_proof.py
```

Gotchas: the pid file of P5.7 is gone on purpose — `killserver` is the only
sanctioned kill (it prints what it killed and `remaining: 0`; if it exits 1,
something survived: run it again, then `ps -ef | grep -i ruby` and kill the pgid
by hand, and record that in Results). `gt.jsonl`, overlays and `progress.json`
are written incrementally — a crashed run still has them up to the crash frame.

## Visual verification (gating — Opus MUST do this per the CLAUDE.md rule)

Each run dumps three GT-overlay PNGs **mid-run, the moment the frame is
captured** (not at finalize): `runs/<RUN>/overlay_f0060.png`, `overlay_f0120.png`,
`overlay_f0180.png`. **Open all three of every run with the Read tool** (12
images total) before writing any verdict.

- **PASS looks like:** grey asphalt track with yellow lane lines filling most of
  the frame (oblique aerial view; a checkered start-grid strip may pass through);
  **two** cars — one white, one blue, clearly different colours; a green GT box
  **tight on each car** (edges within ~10% of the car silhouette, car centred in
  its box) labelled `id0 white` / `id1 blue`; across f0060→f0120→f0180 of one run
  the cars/ground pattern have visibly moved. Reference:
  `curation/smoke900_p58_overlay_f0120.png` (this campaign's patched code, viewed
  and confirmed at design time).
- **FAIL looks like:** a black or single-colour frame; sky instead of ground;
  one car only, or two same-coloured cars; boxes floating off the vehicles,
  lagging them, or wildly mis-sized; three identical-looking frames (dead feed).
- Record one line per run in Results ("V: PASS — two colour-distinct cars, boxes
  tight, motion visible" or what was actually seen). **A missing PNG = that run
  is INVALID — never a log-inferred pass.** If V fails on any run, the overall
  verdict is NO even if `verdict_p58.py` prints YES; describe what the frames show.

## Verdict rules (mechanical — Opus does not deliberate)

- Run `verdict_p58.py`; its printed table + verdict is the G0–G5 result. Do the
  visual gate V yourself as specified above. **Overall = YES iff verdict_p58
  prints YES AND V passed on all 4 runs.**
- **Partial-run rule (pre-registered, not improvised):** if a run dies mid-clip,
  snapshot `raw/*_$RUN.log` + `progress.json`, rename the run dir
  `runs/<RUN>_attempt<N>_INVALID`, **open whatever overlay PNGs exist with the
  Read tool and describe them in Results** (they are written mid-run now, so a
  death after frame 60 leaves at least one), then re-run that cell **once** with
  a fresh server. A second death of the same cell → record that cell as `infra`
  FAIL, **continue with the remaining cells** (the per-call transport is now
  probed reliable, so unlike P5.7 a single flake does not doom the matrix), and
  the overall verdict is NO [G0] with the partial evidence documented.
- **Abort criteria:** step 2 finds no topic after 120 s → snapshot the gz log,
  `killserver`, retry once with a fresh server; twice → that cell INVALID/`infra`.
  Recorder shows no new `progress.json` update for > 5 min or no `results.json`
  after 15 min → `killserver`, kill the recorder pid, snapshot logs, apply the
  partial-run rule. Never delete a completed run dir; never edit code.
- `verdict_p58.py` prints INCOMPLETE / missing runs → verdict stays INCOMPLETE
  until every cell has either a results.json or a recorded `infra` FAIL.

## Estimates (marked as estimates)

- Per run ≈ 1.5–2.5 min (240 frames at ~6–8.5 fps + ~40 s server load + ~30 s
  finalize video write); matrix ≈ 12–20 min; verdict + proof ≈ 5 min.
- G0: expected PASS 4/4 with **0 retries** (probe: 0/2400 calls failed; smoke:
  0/486). Any nonzero retry count is worth a sentence in Results.
- G1/G3/G5: expected PASS on all runs (smoke: 0 dead, both-visible 1.0, 8.32 fps).
- G2: purity ≈ 0.6–0.9 per car (smoke 0.80/0.86); ratio ≫ 4.
- **G4a is still the genuinely open gate at full scale:** the P5.7 probe showed
  108/108 byte-identical frames across fresh sessions, so estimate mean |diff|
  ≈ 0.0 — but that covered 45% of a clip on one seed pair; 240-frame divergence
  (e.g. shadow/AA state later in the clip) remains possible. A G4a NO with G0-G3
  PASS would demote the claim to "deterministic GT + near-identical frames" and
  is a real finding, not a wasted cycle.
- Disk: ~1 GB total under `runs/` (gitignored).

## Results (filled by Opus)

Run date/time: TBD. Versions: TBD (record `gz sim --versions`, python, numpy,
cv2 from any `results.json`, plus GPU driver via `nvidia-smi`).

| run | seed | G0 (retries/lost/restarts) | G1 | G2 (pur0/pur1) | G3 bothvis | G5 fps | V visual (one line) |
|---|---|---|---|---|---|---|---|
| seed101_A | 101 | | | | | | |
| seed202_B | 202 | | | | | | |
| seed303_C | 303 | | | | | | |
| seed101_D | 101 | | | | | | |

- G4a (A vs D): TBD (gt_identical=?, frame mean |diff|=?, frac>8=?)
- G4b (seeds differ, min pairwise f0 distance): TBD
- `verdict_p58.py` full output (verbatim): TBD
- **RQ-P5.8 overall: TBD**
- Estimate-vs-actual: TBD

## Deliverables (cut by Opus after the matrix)

1. `proof/p58_overlay_grid.png` — 4 runs × 3 mid-run GT overlays (the V gate in
   one figure). Caption: which runs/seeds, what tight boxes demonstrate.
2. `proof/p58_determinism.png` — per-frame mean |diff| seed101_A vs seed101_D +
   worst frame pair. Caption: the G4a reading.
3. `proof/p58_transport_fix.png` — before/after: P5.7 CLI attempts (127/240,
   108/240 @ 1.48 fps) vs P5.8 persistent-proxy runs (frames completed, fps,
   retry counters). Caption: the campaign's actual finding.
4. `proof/p58_seed101_overlay.mp4` — behaviour clip of seed101_A.
5. Append: RESULTS row(s) to `docs/results/part5-anticipatory.md`; QUESTIONS
   entry (RQ-P5.8 + one-line verdict) to `docs/questions/part5-anticipatory.md`;
   DECISIONS entry to `docs/decisions/part5-anticipatory.md` covering (a)
   persistent proxy over CLI+retry (what was given up: none — retry kept as
   safety net; and the cumulative-degradation amendment to P5.7's 0.42% model),
   (b) reply-lost-aware step retry with G1 as the double-step tripwire, (c)
   killserver replacing the defective pid-file teardown, (d) P5.6 re-affirmed
   PARKED. No new SOURCES expected (no new external asset).
6. Commit on this branch; do not merge (the loop's reviewer merges).
