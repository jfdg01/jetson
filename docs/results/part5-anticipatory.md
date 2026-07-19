# RESULTS — Part V · Anticipatory grounding / warm-start acquire (v5)

Index: [`../../RESULTS.md`](../../RESULTS.md) · Companion: [`../questions/`](../questions/) (research questions) · [`../decisions/`](../decisions/) (what was chosen & why).
Per-campaign detail lives in `experiments/<campaign>/README.md`. Append, never overwrite.

---

## Part V — Anticipatory grounding / warm-start acquire (v5)

Goal: the operator's prompt does not arrive at frame 0 — the drone streams video for seconds
before the operator speaks, so the pre-prompt window is free compute. Instead of a cold
blocking acquire at prompt time (which lands stale, Part IV E18–E23), keep salient objects
already tracked over the idle window and **select on command**. Reframe origin:
`experiments/PART5-PROPOSAL-anticipatory-grounding.md`.

<!-- append one result row per campaign below -->

### P5.1 — warm-start acquire (2026-07-04)

Detail: [`../../experiments/2026-07-04-warm-start-acquire/README.md`](../../experiments/2026-07-04-warm-start-acquire/README.md).
Config: Qwen2-VL-2B Q8_0 terse acquire on Jetson Orin Nano (15 W + jetson_clocks, `nvpmodel -m 0`,
no MAXN on this board); SAM2.1-hiera-tiny StreamCarry on RTX 3090 rate-capped 6.15 Hz; mask gate
app-τ=12.0; prompt t_p=8.0 s, 10 s coverage window; 6 clips × {WARM,COLD,ORACLE} × n=2 = 36 runs,
0 INVALID, 0 n=2 splits. Metric: genuine_lock at deliver-frame AND coverage ≥ 0.50 over the window,
best of n=2. Best-of-n from `runs/*/results.json` via `make_proof.py`.

| leg | PASS | passing clips | mechanism |
|---|---|---|---|
| WARM (idle-window VLM seed, select at t_p) | **5/6** | car3, car9, car10, car14, car18 | fresh carry still locked at prompt |
| COLD (E18-A cold acquire shifted to t_p) | 1/6 | car14 | ~135-frame (~4.5 s) stale box; only slow car14 still overlaps |
| ORACLE (GT[0] seed, same catch-up, ceiling) | 5/6 | car3, car9, car10, car14, car18 | GT-seed ceiling — identical PASS set to WARM |

Per-clip (WARM / COLD / ORACLE, genuine_lock·coverage·deliver_iou):
car3 T·1.00·.62 / F·.00·.00 / T·1.00·.66 · car7 F·.11·.00 / F·.00·.00 / F·.11·.00 ·
car9 T·1.00·.88 / F·.00·.06 / T·1.00·.88 · car10 T·1.00·.81 / F·.00·.00 / T·1.00·.81 ·
car14 T·.98·.69 / T·.95·.50 / T·.98·.73 · car18 T·.99·.90 / F·.00·.00 / T·.99·.94.

W=5/6, C=1/6, O=5/6. **WARM-vs-ORACLE gap = EMPTY** (real idle VLM seed == GT seed on every clip;
zero detection headroom). Sole failure car7 = occlusion at the prompt frame (`gt[240]` absent) →
carry-bound, also fails ORACLE. See `proof/warm_vs_cold_vs_oracle.png` (coverage + freshness) and
`proof/car10_warm_vs_cold.mp4` (fresh vs stale delivery).

### P5.2 — warm-start generalization + on-screen-speed sweep (2026-07-04)

Detail: [`../../experiments/2026-07-04-warm-start-generalization/README.md`](../../experiments/2026-07-04-warm-start-generalization/README.md).
Config identical to P5.1 (Q8_0 terse acquire, SAM2.1-tiny TRT fp16 6.15 Hz, mask gate app-τ=12.0,
t_p=8 s, 10 s window, Jetson 15 W + jetson_clocks). Extends P5.1's 6 cars to **25 clips × 5
categories × a data-driven on-screen-speed sweep** (0.00–15.62 %frame-diag/s), clips selected from
UAV123 GT via `profiles.py` (measured, not eyeballed). n=1 (P5.1 was bit-identical across reps);
75 legs, 0 INVALID. Metric unchanged: genuine_lock at deliver-frame AND coverage ≥ 0.50.

| leg | PASS | mechanism |
|---|---|---|
| WARM (idle-window VLM seed, select at t_p) | **21/25** | fresh carry still locked at prompt; 5 categories (car/person/boat/wakeboard/bike) |
| COLD (cold acquire at prompt, delivered stale) | 5/25 | ~135-frame stale box; survivors are deliver-frame geometry accidents, not slow clips |
| ORACLE (GT[0] seed, ceiling) | 22/25 | GT-seed ceiling; 2-clip detection headroom over WARM at scale |

WARM 4 misses: car7, person10 `[deliver-occluded]` (GT absent at deliver frame 240 → fail ORACLE
too; 21/23 = 91% on the non-degenerate set); person18, car17 `[detection-bound]` (ORACLE passes,
idle-window VLM seed is the binder). WARM *beats* ORACLE on wakeboard2 (cov 0.677 > 0.443).

**Speed sweep (RQ-P5.2b):** per-clip WARM−COLD coverage gap vs on-screen speed — Spearman
ρ = **−0.06** (flat). Per-bin mean gap: slow **+0.42**, med **+0.76**, fast **+0.62** — large and
positive in every bin, NOT rising with speed. The staleness-grows-with-speed prediction is
refuted: warm-start's payoff is a flat offset (COLD's *delivery* lag sinks it broadly, independent
of motion). Full per-clip table in the experiment README. Proof: `proof/gap_vs_speed.png` (the
thesis figure — ρ + per-bin means), `proof/generalization_grid.png` (PASS by category),
`proof/person20_warm_vs_cold.mp4` (fast non-car money shot: fresh WARM tracks, stale COLD misses).

### P5.3 — multi-candidate select-on-command (late-binding phrase select, 2026-07-14)

Detail: [`../../experiments/2026-07-14-multi-candidate-select/README.md`](../../experiments/2026-07-14-multi-candidate-select/README.md).
First Part V test of the *selection* stage (P5.1/P5.2 all had one dominant target, so select was
trivially satisfied). Two same-class candidates carried through the idle window (target = oracle
GT[f0] seed, distractor = hand box); at t_p the deployed VLM (Qwen2-VL-2B q8_0 terse, max_side 1024,
Jetson 15 W + jetson_clocks) fires on the prompt frame, and its stale box is **matched by IoU
against the candidates' carried boxes at the prompt frame** (`argmax IoU`, NO_MATCH floor 0.10) —
then the matched *track's live box* is delivered. 5 car scenes × 3 legs (WSEL / SWAP / CSEL), n=1
deterministic, 15/15 ran clean (exit 0), no abort. Same-frame delivery for all legs (isolates the
late-binding claim from the delivery-lag win already proven in P5.1/P5.2).

| leg | PASS | mechanism |
|---|---|---|
| WSEL (target phrase → matched live track) | **3/5** | car10:240, car9:300, car7:460 lock at IoU 0.81-0.87; car10:615 + car3:200 fail |
| SWAP (distractor phrase → should flip selection) | **2/5** | car9:300, car3:200 flip correctly; other 3 NO_MATCH on the distractor caption |
| CSEL (cold deployed baseline, non-gating) | **1/5** genuine_lock | car10:240 only — cold stays broadly stale, consistent with COLD 5/25 (P5.2) |

**Verdict: NO** (RQ-P5.3a FAIL 3/5 < 4; RQ-P5.3b FAIL 2/5 < 4). **Dominant failure = NO_MATCH**
(4 of 7 non-passes): the stale VLM box at the prompt frame overlapped neither carried candidate
(max IoU ~0.000), i.e. the deployed VLM grounded the caption onto an object outside both tracks
(third in-frame cars; type/colour phrase ambiguity for the distractor captions). **Not a match-rule
bug** — the 3 WSEL passes deliver the correct live track at IoU 0.81-0.87 whenever the VLM boxes a
carried candidate. The late-binding IoU-match mechanism is *sound but not robust*: it is bottlenecked
by the deployed VLM's raw grounding accuracy at the prompt frame, not by carry drift or the match
rule. Motivates the crop-scoring family (CLIP crop-text / VLM multiple-choice over the carried
candidate crops directly) as the next deep-research target. Proof: `proof/p53_pass_grid.png`
(outcome grid), `proof/p53_deliver_iou.png` (WSEL matched 0.81-0.87 vs CSEL stale ~0 same frame),
`proof/car9_300_WSEL.mp4` + `proof/car9_300_SWAP.mp4` (phrase flips the selected track in one scene).

### P5.4 — ROI-constrained select-on-command (2026-07-14)

`experiments/2026-07-14-crop-select/` · Jetson 15W + jetson_clocks, q8_0 VLM max_side 1024 fired on
the candidates-union ROI crop (margin 1.5, min_side 256, LANCZOS@512), SAM2 carry on local RTX 3090
rate-capped to 6.15 Hz. 5 frozen P5.3 scenes x {VSEL, VSWP} = 10 runs, n=1/cell, deterministic,
10/10 ran clean (exit 0), no abort. Same rig and frozen scenes as P5.3 -> before/after is cell-by-cell.

| leg | PASS | vs P5.3 | mechanism |
|---|---|---|---|
| VSEL (target phrase, ROI crop) | **3/5** | = WSEL 3/5 | car10:240, car9:300, car7:460 lock at deliver-IoU 0.59-0.83; car10:615 NO_MATCH (in-crop third car), car3:200 wrong-object (16x40 px target) |
| VSWP (distractor phrase, ROI crop) | **3/5** | up from SWAP 2/5 | car10:240, car9:300, car3:200 flip correctly; car10:615 NO_MATCH, car7:460 NO_MATCH (carry-drift cell) |
| CLIP circlectx (non-gating secondary) | **7/10** correct | — | agrees with VLM on the 7 grounded runs; would not rescue car10:615 |

**Verdict: NO [match-bound, resolution-bound]** (RQ-P5.4a FAIL 3/5, RQ-P5.4b FAIL 3/5). **The one
unambiguous win: ROI cut acquire latency ~2.3x — 2.08 s median vs P5.3 full-frame ~4.5-4.9 s** (the
Part III ROI-anchor lever transferring as predicted, est. ~1.5-2.5s -> actual 2.08s). But the select
verdict did not move: VSEL identical to P5.3 WSEL cell-for-cell. The pre-registered "ROI kills
NO_MATCH by construction" hypothesis is **falsified** — NO_MATCH only fell 4->3, because a distractor
object *between* the two carries (car10:615's big silver sedan) is inside the union crop by
construction and the VLM grounds onto it. The 2-5x LANCZOS upscale did not rescue the ~16x40 px
car3:200 target (still mis-grounds, match valid at 0.48 -> wrong track delivered = `[resolution-bound]`).
VSWP improved 2/5->3/5 (crop helps the distractor-caption grounding). Bottleneck remains the deployed
VLM's grounding accuracy at the prompt, now at ~2s instead of ~4.5s. Proof: `proof/p54_pass_grid.png`,
`proof/p54_acquire_match.png` (the 2.3x latency cut), `proof/p54_vsel_car10_615.mp4` (in-crop
third-object NO_MATCH), `proof/p54_vsel_car9_300.mp4` (grounded-carry PASS at IoU 0.83).

### P5.5 — Maintained-candidate select-on-command (2026-07-14)

`experiments/2026-07-14-select-generalization/` · Jetson 15W + jetson_clocks, q8_0 VLM terse
(max_side 1024 full-frame select + 512 pre-resized ROI crops for the idle re-anchor), SAM2 carry on
local RTX 3090 rate-capped to 6.15 Hz (CAND_HZ 3.075/candidate). 6 scenes (5 frozen P5.3 + new
car9:560) x {WSEL, SWAP} = 12 MC runs (gating) + 4 M runs (attribution, old P5.3 captions), n=1/cell,
deterministic, 16/16 ran clean, no `infra`. Two levers on the frozen P5.3 rig: (1) idle-window
distractor ROI re-anchor at f0+90/165 (accept = parseable + in-frame, no IoU floor), (2)
referentially-unique captions on the two audit-tagged caption-bound cells.

| leg | PASS | vs P5.3 | mechanism |
|---|---|---|---|
| MC WSEL (target phrase) | **4/5** | up from WSEL 3/5 | car10:240, car9:300, car7:460, car9:560 lock at deliver-IoU 0.77-0.87; car10:615 NO_MATCH |
| MC SWAP (distractor phrase) | **3/5** | up from SWAP 2/5 | car10:615, car9:300, car9:560 flip correctly; car10:240 + car7:460 carry-drift NO_MATCH |
| M arm (old captions, attribution) | **= MC cell-for-cell** | — | caption lever inert: car10:240 SWAP + car10:615 WSEL FAIL NO_MATCH in both M and MC |
| car3:200 control (resolution) | WSEL FAIL / SWAP PASS | = P5.3/P5.4 | levers do not move the ~16x40 px resolution cell |

**Verdict: NO [match/carry-bound]** (RQ-P5.5a YES 4/5, RQ-P5.5b NO 3/5; YES iff both). Idle-window
maintenance re-anchored in **every** cell (`[True, True]` throughout) but did not close the SWAP gap:
two distractor carries (car10:240, car7:460) still fail **carry-drift NO_MATCH** (carried box vs
select-time full-frame VLM box IoU 0.000) *after* two accepted ROI re-anchors. The caption lever
(Lever 2) is **falsified** as a select-fix — M == MC on both targeted cells; the P5.5 audit's
"phrase-ambiguity"/"tiny-box near-miss" re-diagnoses were partly wrong (both cells are
match/carry-bound under maintenance, not caption-bound). Third consecutive select-on-command NO
(P5.3 match-bound, P5.4 match/resolution-bound, P5.5 match/carry-bound): the binding constraint stays
the agreement between the carried SAM2 box and the deployed full-frame VLM grounding at the prompt.
Proof: `proof/p55_pass_grid.png` (WSEL 4/5, SWAP 3/5, M==MC), `proof/p55_reanchor_traj.png`
(re-anchors fire/accepted yet carry still not matching), `proof/car7_460_SWAP_MC_driftNOMATCH.mp4`
(surviving carry-drift NO_MATCH), `proof/car10_615_WSEL_MC_captionNOMATCH.mp4` (inert caption lever).

### P5.7 — Simulator scene-generator capability gate (select-arena v1) (2026-07-17)

`experiments/2026-07-17-sim-scenegen/` · **RTX 3090 workstation only, Jetson not used** (Gazebo does
not run on it; no on-device claim in RQ-P5.7). gz sim 8.14.0 (Harmonic), Python 3.12.10 / numpy 2.4.4
/ opencv 4.13.0 via `.venv-ft`, driver 595.71.05, headless EGL (`__EGL_VENDOR_LIBRARY_FILENAMES`
pinned to 10_nvidia.json). No power-mode knob (desktop GPU, stock clocks). Planned: 4 runs
(`seed101_A`, `seed202_B`, `seed303_C`, `seed101_D`), 240 frames @ 25 fps virtual, one fresh
`gz sim -s` session each. **Actual: 1 run attempted, twice, both INVALID; B/C/D never ran** (abort
rule: INVALID -> re-run once with a fresh server -> fails again -> record `infra` FAIL and stop).

| attempt | frames | died on | wall / fps | server at crash |
|---|---|---|---|---|
| seed101_A #1 | **127/240** (53%) | `set_pose_vector failed: Service call timed out` | 14:31:50->14:33:16, 1.48 fps | **ALIVE** |
| seed101_A #2 | **108/240** (45%) | `world control failed: Service call timed out` | 14:44:06->14:45:19, 1.48 fps | **ALIVE** |
| seed202_B / seed303_C / seed101_D | — | NOT RUN (stop rule) | — | — |

**Verdict: NO [`infra` FAIL: gz-transport service flake].** `verdict_p57.py` -> `INCOMPLETE: missing
runs ['seed101_A','seed202_B','seed303_C','seed101_D']` (exit 2). G1/G2/G3/G4a/G4b/G5 **unmeasured**
(all are computed at finalize) and the mandatory visual gate **V is uncomputable** — overlays,
`gt.jsonl`, `overlay.mp4` and `results.json` are all finalize-time artifacts, so 0 of the required 12
overlay PNGs exist; recorded INVALID, never a log-inferred pass. Root cause (evidence, not inference):
the sim never crashed — server alive and camera topic up at both crashes; `scenegen.py` drives the
world with **two `gz service` CLI subprocess calls per frame** (~480 ephemeral gz-transport nodes per
run) and the server intermittently fails to route a response back to one ("`NodeShared::RecvSrvRequest()
error sending response: Host unreachable`", the only error in both server logs, identical across
sessions), so the CLI burns its 5000 ms timeout and the recorder raises. Different services hit in the
two attempts -> transport/discovery layer, not one handler. **Rate (ESTIMATE, n=2):** ~236 calls
mean-time-to-failure -> ~0.42%/call -> P(240-frame run completes) ~= **13%**, P(4 runs) ~= **0.03%** —
the matrix as designed is essentially unrunnable, not unlucky.

**Non-gating salvage (the pre-registered open risk, answered favourably):** both INVALID attempts are
seed 101 under *fresh* sessions, so their 108 overlapping raw frames are exactly G4a's cross-session
comparison (frame half only). Measured with `verdict_p57.frame_diff`'s metric: **108/108 byte-identical,
mean |diff| = 0.000000** (gate <= 2.0), frac(|diff|>8) = 0.0 (gate <= 0.01); render health min
per-frame std 21.07 (dead if <= 5), 0 byte-identical consecutive frames. **Not a G4a pass** (runs
INVALID, GT half uncheckable, 108/240 frames) but GPU AA/shadow nondeterminism did **not** materialise
across sessions — better than the "mean |diff| < 1.0" estimate. Raw frames viewed directly (per the
visual-verification rule): two colour-distinct cars (blue + white), grey asphalt, yellow lane lines,
checkered start grid, UAV-style oblique aim — the render path, EGL pin, camera aim and solid-colour
materials all work; only the per-frame service-call transport is broken. Throughput 1.48 fps was
**on estimate** (1.3-1.5), so G5 would very likely have passed had the clip finished.
Proof: `proof/p57_infra_fail.png` (both attempts stop mid-clip, server alive),
`proof/p57_crosssession_determinism.png` (flat 0.0 vs the 2.0 gate, non-gating),
`proof/p57_render_ok_f0060.png` (scene renders correctly; no GT box drawn — why V is uncomputable).

### P5.8 — Scene-generator transport fix (persistent requester) + capability gate re-run (2026-07-17)

`experiments/2026-07-17-scenegen-transport/` · **RTX 3090 workstation only, Jetson not used** (no
on-device claim in RQ-P5.8). gz sim 8.14.0 (Harmonic), Python 3.12.10 / numpy 2.4.4 / opencv 4.13.0
via `.venv-ft`, driver 595.71.05, headless EGL (`__EGL_VENDOR_LIBRARY_FILENAMES` pinned to
10_nvidia.json). No power-mode knob (desktop GPU, stock clocks). Transport: **one persistent
gz-transport requester node** in a dedicated no-subscriber `proxy` child process (replacing P5.7's
~480 ephemeral `gz service` CLI subprocesses/run), plus a reply-lost-aware retry layer. 4 runs
(`seed101_A`, `seed202_B`, `seed303_C`, `seed101_D`), 240 frames @ 25 fps virtual, one fresh
`gz sim -s` session each (killed via the `killserver` process-group scan between runs).
**Actual: 4/4 runs completed first attempt**, 15:12Z->15:17Z.

| run | seed | frames | fps wall | retries / lost / restarts | G0 | G1 | G2 pur0/pur1 (bg) | G3 bothvis | G5 |
|---|---|---|---|---|---|---|---|---|---|
| seed101_A | 101 | **240/240** | 8.35 | 0 / 0 / 0 | PASS | PASS | 0.761 / 0.472 (0.020 / 0.000) | 1.000 | PASS |
| seed202_B | 202 | **240/240** | 8.34 | 0 / 0 / 0 | PASS | PASS | 0.804 / 0.750 (0.002 / 0.000) | 1.000 | PASS |
| seed303_C | 303 | **240/240** | 8.36 | 0 / 0 / 0 | PASS | PASS | 0.857 / 0.845 (0.000 / 0.000) | 1.000 | PASS |
| seed101_D | 101 | **240/240** | 8.35 | 0 / 0 / 0 | PASS | PASS | 0.761 / 0.472 (0.020 / 0.000) | 1.000 | PASS |

**Verdict: NO [G4b — seed-diversity gate].** Everything the cycle set out to fix works; the matrix
fails on one gate that turns out to be mis-calibrated.

**The transport fix (the point of the cycle): unambiguous PASS.** G0 4/4 at **240/240 frames with
0 retries, 0 lost replies, 0 proxy restarts, 0 spawn warnings** — the retry safety net never fired
across **1920 gating service calls** (4 x 240 x 2), on the same two services (`set_pose_vector`,
`world control`) that killed P5.7 twice inside ~240 calls. Completion 0/2 -> **4/4**; throughput
1.48 -> **8.34 fps (5.6x)**; wall 28.7 s/run record loop. P5.7's ~236-call mean-time-to-failure and
its ~0.42%/call model both predicted <13% chance a single run finishes — the observed 4/4 with zero
failures falsifies the memoryless model and supports the pre-registered **cumulative-degradation**
reading (ephemeral-node churn, not a constant per-call hazard) recorded in that cycle's amendment.

**G4a — the pre-registered "one genuinely open gate" — PASS, and stronger than estimated.**
seed101_A vs seed101_D (same seed, **fresh server session each**): canonical GT **byte-identical**,
frame `mean |diff| = 0.0` (gate <= 2.0) and `frac(|diff|>8) = 0.0` (gate <= 0.01) **across all 240
frames**, worst frame pair f=0 at 0.000. P5.7's probe covered 108/240 frames on one seed pair; the
feared late-clip shadow/AA divergence **did not materialise**. Sim scene generation on this rig is
now demonstrably deterministic end-to-end (GT *and* pixels) across sessions.

**G4b — FAIL, 0.216 m < 1.0 m required — and this is the gate's fault, not the generator's.**
Target (`objs[0]`, car_white) f0: seed101 (2.346, 1.390), seed202 (1.485, 1.335), seed303
(1.671, 1.226); pairwise 101-202 **0.863 m**, 101-303 **0.695 m**, 202-303 **0.216 m** — all three
under the gate. Diagnosis (executor, quantitative, no threshold/seed/code changed): recorded
`gt.jsonl` f0 reproduces `author_scenario()` **exactly** offline, so the GT path is faithful and this
is not a transport artefact; the target f0 spreads **~8 m x 7 m over 120 seeds** (x in [-1.98, 5.98],
y in [-1.39, 5.72]), so the generator *does* diversify; but sampling **2000 random 3-seed triples**,
only **74.6%** pass G4b (median min-pairwise 1.52 m, p10 0.59 m) — with 3 seeds there are 3 pairs, so
near-collisions are a birthday effect and **G4b has a ~25% false-failure rate on an arbitrary triple**.
The pre-registered {101, 202, 303} landed in that 25%. The seeds differ materially on every other
axis: distractor f0 (-8.91, 0.60) / (-11.05, 5.79) / (-11.60, 5.03) (~5 m lateral spread),
v_target 5.83 / 4.04 / 3.64 m/s, standoff 17.8 / 18.2 / 21.4 m, alt 16.3 / 19.5 / 21.6 m.

**Visual gate V: PASS 4/4** (12/12 required overlays opened with the Read tool before any verdict was
written, per the mandatory-visual-verification rule). All runs: grey asphalt + yellow lane lines,
checkered start-grid strip, **two colour-distinct cars** (white `id0`, blue `id1`) each in a green GT
box, scene visibly advancing f0060->f0120->f0180; no black/single-colour frames, no dead feed; the
white target's box is tight and centred in every frame of every run. seed202_B / seed303_C are clean
(purity 0.75-0.86). **seed101_A / seed101_D are PASS-with-caveat:** in this seed the blue distractor
spawns near the median kerb (lat y = 0.596 vs 5.79 / 5.03 for the other seeds) and **clips into the
kerb geometry** — by f0180 it renders as two disconnected blue blobs straddling the kerb line with
the mid-body hidden below the surface. The box still bounds the full 3D model and tracks the car
(no float/lag/drift), so this is a **scene-geometry defect, not a projection error**; it is what
drives pur1 = 0.472 (lowest cell, still >> the 0.30 gate and >> 4x its 0.000 control). Recorded as a
caveat rather than a V FAIL because the pre-registered FAIL list is not met — but **a half-sunk
distractor is not a fair grounding target and should be fixed before this generator feeds a select
experiment.** seed101_D is visually indistinguishable from seed101_A at all three overlays,
independently corroborating G4a. V did not decide the verdict (NO on G4b regardless).

**Estimate-vs-actual:** matrix **~5 min vs 12-20 min estimated** (~1.0 min/run vs 1.5-2.5); G0 and
G5 hit exactly (0 retries; 8.34-8.36 fps vs 6-8.5 est.); G2 purity **0.472 low-side of the 0.6-0.9
estimate** on seed101's blue car (kerb-clipping); G4a **0.0 exactly** as estimated. **The risk model
inverted:** the pre-registration flagged G4a as the one genuinely open gate and treated G4b as a
formality — G4a passed perfectly and G4b is the sole failure. No estimate had been pre-registered
for G4b.
Proof: `proof/p58_transport_fix.png` (0/2 -> 4/4 completion, 1.48 -> 8.34 fps, retries 0),
`proof/p58_determinism.png` (G4a flat at 0.0 for all 240 frames vs the 2.0 gate),
`proof/p58_overlay_grid.png` (4 runs x 3 overlays — the V gate in one figure),
`proof/p58_seed101_overlay.mp4` (behaviour clip, seed101_A).

### P5.9 — kerb-safe scene bank (2026-07-17)

Detail: [`../../experiments/2026-07-17-kerbsafe-scenebank/README.md`](../../experiments/2026-07-17-kerbsafe-scenebank/README.md).
Config: RTX 3090 workstation only (Jetson NOT used); gz sim 8.14.0, Python 3.12.10 / numpy 2.4.4 /
cv2 4.13.0 via `.venv-ft`; persistent-proxy transport (P5.8), one fresh server session per run,
teardown via `killserver` (`remaining: 0` every time). 16 runs: 4 gate (seed101_A/202_B/303_C/101_D)
+ 12 bank (seeds 1-12). Calibrated kerb-safe spawn bands (target lat0 U(-4.5,-2.2), distractor lat0
U(0.5,1.3), amp U(0.2,0.5), distractor s0 U(4,10), v_d cap 6.0 → worst-case lat ∈ [-5.0,+1.8] ⊂
LAT_SAFE (-5.2,2.0), s ≤ 67.4 ≤ 70), asserted per scenario in `author_scenario`. New gate **G6**
(rendered integrity): per car frag p10 ≥ 0.95 AND frac(frag<0.90) ≤ 0.02 AND ≥ 200 scored frames.
G4b **redefined** to whole-scenario divergence ≥ 1.0 m (was min pairwise target-f0 distance).

**RQ-P5.9 = YES.** Full capability gate 16/16 (G0,G1,G2,G3,G5,G6 all PASS every cell), G4a PASS,
G4b (redefined) PASS, 12/12 bank cells clean, **V PASS 16/16**, zero clipping. Matrix landed on the
first attempt: 0 INVALID, 0 INFRA, 0 re-runs, 240/240 frames × 16 = 3840 frames, **0 retries across
1920 service calls**, 8.18–8.33 fps.

| gate | value | note |
|---|---|---|
| G0 | 0/0/0 retries all 16 cells | 1920 calls, 0 retries (as P5.8) |
| G2 purity | 0.712–0.911 (both cars) | lowest pur0 bank07 0.712; NO blue-car <0.6 outlier (P5.8's 0.472 clip did not recur) |
| G5 fps | 8.18–8.33 | on estimate |
| **G6** frag p10 | min 0.9967 across 16 runs (gate 0.95) | margin +0.047; below-0.90 frac 0.000 everywhere; no cell in [0.95,0.99) watch band. Marginal cells are the WHITE target (self-occlusion), not the blue distractor (P5.8's clip victim, now p10 ≥ 0.9893) |
| G4a | GT byte-identical, mean\|diff\| 0.0, frac(>8) 0.0 | cross-session determinism, exactly as P5.8 |
| G4b (redef) | min divergence **1.36 m** ≥ 1.0 at pair (8,12); f0-faithful True/16 | on design estimate to 2 d.p. |
| G4b OLD-stat diagnostic | min pairwise target-f0 dist **0.135 m** at pair (1,12) | **far below the retired 1.0 m gate — the OLD G4b would have failed this bank.** Corroborates the redefinition: seeds 1&12 start 13.5 cm apart at f0 but diverge 1.36 m scenario-wide (single-frame coincidence between diverging trajectories = the birthday noise the old point-stat false-failed on) |
| corridor safety | worst distractor lat +1.674 m (bank12, 0.326 m margin to paint) | all connected on-asphalt by eye; the "close to line" residual risk materialised at ~0.33 m and rendered clean = PASS |

Every gate landed inside its pre-registered estimate; no estimate flipped (contrast P5.8, where the
"formality" G4b was the sole failure). The design-time calibration (kerb sweep + G6 tuning on P5.8
frames + fixed-code seed-101 smoke) correctly predicted the whole matrix.
Proof: `proof/p59_beforeafter_kerb.png` (P5.8 seed101 f0180 two-blob clip vs P5.9 same seed/frame
intact), `proof/p59_kerb_calibration.png` (the (s,lat) integrity sweep + ~4° kerb skew that
explains P5.8's late-clip), `proof/p59_bank_grid.png` (12 clips at f0180, all clean, per-run G6),
`proof/p59_g6_teeth.png` (frag p10 all 16 runs vs the P5.8 clipped 0.666 reference).

### P5.10 — select on the P5.9 scene bank: direct delivery vs prompt-time re-ground (2026-07-17)

Detail: [`../../experiments/2026-07-17-simbank-select/README.md`](../../experiments/2026-07-17-simbank-select/README.md).
Config: RTX 3090 + SAM2.1-hiera-tiny StreamCarry (bf16), CAND_STRIDE 8 dual carry, oracle f0 seeds;
Jetson Orin Nano 15 W + jetson_clocks serving Qwen2-VL-2B q8_0 terse (llama.cpp over SSH, full frame,
max_side 1024). 12 P5.9 bank clips × 2 legs (white/blue phrase) = 24 paired cells, each scoring BOTH
contracts on byte-identical cached carries. Delivery rule: delivered box IoU vs named-car GT ≥ 0.25
AND > IoU vs other-car GT (dominance; strict variant coincides — GT-GT IoU 0.000 on all 12).
t_p = 3.0 s (prompt f75). Matrix wall ~2.75 min, 0 VLM reboots, 0 INFRA, 0 INCOMPLETE, no reruns.
Versions: torch 2.6.0+cu124, numpy 2.4.4, cv2 4.13.0, python 3.12.10.

| contract | white | blue | total | fail classes | delivery latency |
|---|---|---|---|---|---|
| DD (direct delivery, phrase→carried candidate, acquire 0 s) | 12/12 | 12/12 | **24/24** | none | 0 s |
| RG (P5.3 prompt-time full-frame VLM + IoU-match, measured latency) | 12/12 | 12/12 | **24/24** | none | mean 4.37 s (4.36–4.39), deliver f184–185 |

**RQ-P5.10a YES** (DD ≥ 10/12 each leg). **RQ-P5.10b NO** (DD_total 24, RG_total 24, margin 0 < 4).
**Overall NO; interpretation branch 2** — RG at ceiling: the P5.3/4/5 select NOs are *scene-bound*
(UAV123 attribute murk), not contract-bound; DD's remaining edge is **latency only** (0 s vs 4.37 s).
The pre-registered sim-gap NO_BOX sweep did **not** occur: `vlm_on = named` on all 24 cells — the
RefDrone-fine-tuned VLM grounded every Gazebo render on the first call (0 NO_BOX, 0 NO_MATCH, 0
OVERRUN). **Visual gate V PASS** — all 16 opened sample overlays (bank01/04/07/10 both legs, DD+RG)
show the green delivered box on the named car; no V-vs-script contradiction. Bank v1 is honestly
*too easy to separate the contracts* (2 colour-distinct cars, no crossings, 3 s idle) — the pre-reg
called this the live alternative and it fired. Proof: `proof/p510_pass_grid.png` (24/24 both
contracts), `proof/p510_failclass.png` (0/24 fails each), `proof/p510_headline_dd_vs_rg.png`
(bank01_white: DD f75 vs RG f185, both on the white car, RG paid 4.39 s to reach the same box).

### P5.11 — bank v2 designed-crossing scene bank (build gate) (2026-07-17)

Detail: [`../../experiments/2026-07-17-bankv2-crossing/README.md`](../../experiments/2026-07-17-bankv2-crossing/README.md).
Config: RTX 3090 workstation, gz sim 8.14.0 (Harmonic) headless, `.venv-ft` python 3.12.10 / numpy
2.4.4 / cv2 4.13.0. No model inference (dataset-build gate, no Jetson leg). World `select_arena.sdf`
1280×720 @ 25 Hz, hfov 1.2 rad. Two-stage overtake (`scenegen.py` profile v2): white constant-lane
target, blue distractor pulls in behind → holds dead-centre (sustained occlusion) → pulls out;
300 frames = 12.0 s, prompt f150 (6.0 s idle, double P5.10). 16 runs, one fresh gz server per run
(4 gate 101/202/303/101 + 12 bank seeds 1,2,3,4,5,6,7,8,9,10,13,14). Occlusion partition by per-frame
GT `occl`: CLEAR (occl≤0.05) graded v1-style, OCCLUDED (white occl≥0.50) graded only on occluder
(blue) intactness (G8c) + blue-dominance z-order (G8b). Matrix wall **13.6 min** (est 30–40), fps
8.60–8.78, 0 INFRA, 0 INCOMPLETE, 0 reruns, killserver remaining:0 before+after every run.

| axis | result | detail |
|---|---|---|
| Gate runs G0–G6c | **4/4 PASS** | seed101_A/202_B/303_C/101_D all green; fps 8.60–8.70 |
| G4a determinism (A vs D) | **PASS** | gt byte-identical, frame mean\|diff\| 0.0, frac(>8)=0.0 (byte-perfect) |
| G4b seed diversity (16 seeds) | **FAIL** | min pairwise scenario divergence **0.77 m < 1.0** at seed pair (9,14); recorded-f0 faithful 16/16 |
| Bank cells all gates | **3/12 PASS** (bank01/03/04) | G6c fails 7 cells (n_clear<60), G8b fails 3 cells (bdom<0.55); bank11 both |
| G9 crossing-as-designed | 12/12 | every clip: peak IoU 0.22–0.35 pre-prompt, tail ≤0.15 post-prompt |
| Visual gate V | **PASS (no downgrade)** | 12 crossing-peaks + 3 post-prompt + 2 gate mid-run + montage opened; all genuine occlusions, 0 render defects |

**RQ-P5.11 = NO** [G4b FAIL; bank 3/12 < 11/12]. The generator DOES author genuine designed
occlusions — V confirmed all 12 crossing peaks (blue occluder in front of white target, intact
bodies, overlapping GT boxes, on the start line; no shards/z-fighting/road-sink), and G9=12/12 shows
correct pre-prompt peak + post-prompt separation. The bank fails on **integrity-threshold
calibration**, not render quality: (1) the G6c n_clear floor (60, calibrated off the single seed-1
probe's 80) is too tight — deeper/longer crossings across the seed population eat >240 of white's 300
frames, leaving <60 CLEAR frames on 7 cells that visually render valid occlusions; (2) G8b bdom<0.55
on 3 shallow-occlusion seeds where the white roof stays prominent (a real depth property, not a
defect); (3) G4b seed-diversity FAIL — the offline crossing screen picked the first 12 passing seeds
with no pairwise-diversity constraint, admitting near-duplicates 9 & 14 (0.77 m). All three are
NEW-pre-registration fixes (recalibrate n_clear floor to the population, add a diversity constraint,
possibly relax/re-derive G8b for shallow seeds), NOT threshold nudges — reported as the P5.11
follow-up trigger; the pre-registered P5.12 v2-discrimination A/B is blocked until the bank passes.
Proof: `proof/p511_occlusion_montage.png` (12 genuine crossings), `proof/p511_gate_grid.png`
(failure partition heatmap, 3/12), `proof/p511_crossing_traces.png` (per-clip IoU/occlusion traces,
peaks pre-prompt, tails post-prompt).

### P5.12 — bank v2.1 recalibrated designed-crossing scene bank (build gate) (2026-07-19)

Re-run of the identical 16-run P5.11 v2 record matrix over a **v2.1 seed bank** chosen by an offline
admission screen (S6 predicted-clear-frame floor ≥45, S7 pairwise divergence ≥1.1 m) against two
floors recalibrated **once, before any v2.1 frame was recorded**, from P5.11's 12-cell visually
confirmed population (`curation/p511_population.json`): G6c `n_clear` 60→40, G8b `bdom` 0.55→0.40.
Generator (`author_scenario`, `profile="v2"`, `record()`) untouched. Bank seeds
`[1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56]`. RTX 3090, gz sim 8.14.0, 1280×720 @ 25 Hz, 300
frames/clip, `--profile v2`, fresh server session per run.

| axis | result | detail |
|---|---|---|
| Gate runs G0–G6c | **4/4 PASS** | seed101_A/202_B/303_C/101_D all green; fps 7.99–8.26 |
| G4a determinism (A vs D) | **PASS** | gt byte-identical, frame mean\|diff\| 0.0, frac(>8)=0.0 |
| G4b seed diversity (15 seeds) | **PASS** | min pairwise scenario divergence **1.11 m ≥ 1.0** at pair (2,29); recorded-f0 faithful 16/16 |
| G7 screen pin (new) | **PASS** | `sg.v2_1_bank()` reproduces the pinned bank byte-for-byte at verdict time |
| Bank cells all gates | **12/12 PASS** | vs P5.11's 3/12 on the same generator; 0 INFRA, 0 present-but-failing |
| G6c margin | min n_clear **57** (bank02) | floor 40; at P5.11's old floor of 60 this defect-free clip would still fail → bank would be 11/12 |
| G8b margin | min bdom **0.488** (bank05/seed 6) | floor 0.40; this is the exact value that failed P5.11's 0.55 floor, visually confirmed a genuine shallow occlusion |
| **S6 predicted vs recorded n_clear** | **12/12, delta 0 on every cell** | pure-projection prediction reproduces the recorded G6c pool exactly, incl. all six never-rendered seeds |
| Visual gate V | **PASS (no downgrade)** | 12 crossing-peaks + 12 post-prompt + 2 gate mid-run + 3 proof figures opened with the Read tool; 12/12 genuine occlusions, **0 render defects** |
| Wall | **~18 min** for 16 runs | estimate was 30–40 min; 0 retries, 0 gz-transport flake |

**RQ-P5.12 = YES** [12/12 bank; V PASS]. P5.11's NO is confirmed **gate-calibration-bound, not
render-bound**: the same untouched generator, re-screened offline and re-graded at floors frozen
before recording, clears the whole bank. The load-bearing evidence is the **delta-0 S6 transfer
table** — `predicted_clear_count()` computes the recorded `n_clear` exactly on 12/12 cells with no
renderer in the loop, which makes the screen a legitimate pre-selection rather than a post-hoc
filter, and it held identically on the six seeds (17, 28, 29, 33, 40, 56) that had never been
rendered before. The pre-registered hypothesis actually under test ("does the offline screen predict
render *integrity* on unseen seeds?") passed. Two floors are proven load-bearing rather than
loosened-to-fit: bank02 (n_clear 57) and bank05 (bdom 0.488) are visually flawless clips that
P5.11's floors rejected. **Caveat carried forward from looking, not from the numbers:** bank05
(seed 6) and bank06 (seed 14) are visibly shallower occlusions than the other ten and their
occlusion window is fragmented (multiple bands in the trace figure) — they pass every gate but carry
less occlusion stress, and are the first place to look if P5.13's contracts fail to separate.
Unblocks the deferred **P5.13 v2-discrimination A/B**, which consumes this bank unchanged.
Proof: `proof/p512_occlusion_montage.png` (12 genuine crossings, one per cell),
`proof/p512_gate_grid.png` (12/12 all-green, the before/after against P5.11's 3/12),
`proof/p512_crossing_traces.png` (per-clip IoU traces: peak inside the occlusion window, tail decayed
before the f150 prompt frame). Detail:
[`../../experiments/2026-07-17-bankv21-recal/README.md`](../../experiments/2026-07-17-bankv21-recal/README.md).

### P5.13 — v2 discrimination A/B: DD vs RG on the bank v2.1 crossing bank (2026-07-19)

Config: bank v2.1 (`experiments/2026-07-17-bankv21-recal/runs/bank01..bank12`, consumed unchanged),
12 clips x 2 legs = 24 cells, 300 frames @ 25 fps 1280x720, prompt frame **f150 (t=6.0 s, after every
crossing; peaks f56-f94)**. Both contracts scored inside every cell off one shared SAM2 carry pass, so
DD and RG are paired by construction. PASS = `iou_named >= 0.25` and `iou_named > iou_other`.
Rig: RTX 3090 workstation (frames, carry, scoring) + Jetson Orin Nano 8 GB `15W` + `jetson_clocks`
(VLM only, Qwen2-VL-2B Q8_0 terse on `llama-server` :18080 over an SSH tunnel; one PNG per cell crosses
the wire). torch 2.6.0+cu124 / numpy 2.4.4 / cv2 4.13.0 / python 3.12.10 / `facebook/sam2.1-hiera-tiny`.

| contract | white | blue | total |
|---|---|---|---|
| DD (direct delivery of the carried track, no VLM at prompt time) | 12/12 | 12/12 | **24/24** |
| RG (prompt-time re-ground + IoU match, floor 0.10) | 11/12 | 12/12 | **23/24** |

| metric | value | note |
|---|---|---|
| RQ-P5.13a `\|DD - RG\| >= 4` | **NO** (\|24 - 23\| = 1) | primary, gating; symmetric margin, carried at 4/24 from P5.11/P5.12 |
| RQ-P5.13b `blue_DD - white_DD >= 3` | NO (12 - 12 = 0) | diagnostic, non-gating |
| branch fired | **3** — no separation, both >= 20/24 | bank still does not discriminate |
| DD fail classes | none, 0/24 | no `CARRY_LOST`, no `CARRY_SWITCH`, no `CARRY_DRIFT` anywhere |
| RG fail classes | `DELIVERY_DRIFT` x1 (`bank09_white`) | VLM grounded correctly (`vlm_iou_named` 0.735, match 0.665, `selection` 0); the mask leaked between f150 and the f259 delivery |
| DD IoU at f150 | 0.462-0.643, all 24 cells | tight band, all well over the 0.25 floor |
| VLM acquire | 4.34-4.38 s (est. 4.4 s) | no `OVERRUN` despite the tighter 5.96 s ceiling |
| INFRA cells / VLM reboots | **0 / 0** | 24/24 cells completed in one pass, no resume |
| Wall | **~3.4 min** for 24 cells | estimate was 6-12 min; warm Jetson + per-clip carry cache shared by both legs |
| Visual gate V | PASS (non-operative) | 3 proof PNGs + 4 per-cell overlays opened with the Read tool; genuine renders, boxes on the cars, no black/blank frames. V can only downgrade a YES. |

**RQ-P5.13 = NO** [branch 3; contracts do not separate, 24 vs 23 of 24]. The pre-registered
prediction was the opposite direction (RG > DD, on the theory that the crossing costs the carry) and
it was **wrong**: SAM2's carry survived all 12 designed crossings with zero fails and a tight IoU
band, so DD ceilinged. RG's single loss is not a grounding loss — the VLM found and matched the right
object, and the cell failed because the delivered mask leaked off the white car during RG's 109-frame
delivery lag, which makes the 24-vs-23 gap even less contract-informative than it looks. Per the
frozen branch-3 caveat the two pre-registered explanations apply in order: (i) crossing-peak
uniformity + constant z-order (white-box centre y std 6.1 px; white is the nearer car in **0/300
frames in every clip**, so the bank never renders the target in front), then (ii) bank05/bank06's
weaker occlusion stress (peak GT-GT IoU 0.217/0.251 vs 0.352). The DD result does not localise to
(ii) — the two weakest-crossing clips passed exactly like the strongest — which points at (i), the
geometry that has no gate. No third explanation is offered, per the pre-registration. This is the
fourth cycle spent on scene data rather than contracts, and the second consecutive DD==RG ceiling
(P5.10 was 24/24 vs 24/24 on bank v1).
Proof: `proof/p513_pass_grid.png` (47/48 tiles green — the absence of separation),
`proof/p513_failclass.png` (DD panel empty, RG panel one `DELIVERY_DRIFT` bar),
`proof/p513_headline_dd_vs_rg.png` (`bank09_white`: DD tight box at f150 vs RG mask ballooned across
road and wall at f259; no picker fallback fired). Detail:
[`../../experiments/2026-07-19-v2disc-select/README.md`](../../experiments/2026-07-19-v2disc-select/README.md).

### P5.14 — realvid-dd-select (direct-delivery contract on real UAV123): **YES**

| run | contract | scenes | WSEL (gating) | SWAP strengthened (gating) | acquire_s | fail class | verdict |
|---|---|---|---|---|---|---|---|
| P5.14 | **DD** — phrase binds to the warm-carried candidate by stored caption; carried box delivered at the prompt frame; no prompt-time VLM, no IoU match | 5 gating UAV123 `car*` scenes + `car3:200` control | **5/5** | **4/5** | **0.00 s** (all 12 cells) | `carry-off-object` x1 (`car7:460` SWAP) | **YES** (both RQs; visual gate V PASS) |
| P5.14 shadow (non-gating) | RG — prompt-time full-frame re-ground + IoU match, run alongside DD on the same frames | same | — | — | **4.51 s** mean (4.48–4.53) | NO_MATCH x3, wrong-object x1 | 4/12 cells DISAGREE with DD |

Config: RTX 3090 (SAM2 carry `facebook/sam2.1-hiera-tiny`, scoring, UAV123 replay) + Jetson Orin
Nano 8 GB at `15W` + `jetson_clocks` (VLM `phase3-terse100eos-1024-q8_0.gguf`, terse, max_side 1024,
used only for the 2 idle ROI re-anchors and the non-gating shadow call). python 3.12.10, torch
2.6.0+cu124, transformers 4.57.6. CARRY_HZ 6.15, CAND_HZ 3.075, DIST_FLOOR 0.25, MATCH_FLOOR 0.10
(shadow only), cover_s 10.0, ROI 512 / margin 2.0 / min_side 256, REANCHOR_OFFSETS (90, 165), n=1
deterministic replay. Matrix wall ~4.4 min (21–22 s/cell) against a 45–75 min estimate.

Per-cell delivered-box IoU vs the correct object at the prompt: WSEL 0.7256–0.8911 (all 6 cells);
SWAP 0.7253–0.8864 on four cells, 0.2843 on the marginal `car9:560`, 0.0 on the failing `car7:460`.
All 24 idle re-anchors accepted. The strengthened SWAP rule (delivered box must land >= 0.25 on the
hand-annotated *distractor*, not merely off the target) scores 5/6 where the old weak rule scores
6/6 — the flattered cell is `car7:460`, whose box is off every object. **First campaign in Part V
where the two delivery contracts separate on the same frames:** the shadow re-ground fails on 4/12
cells (3x NO_MATCH, 1x wrong-object selection) whose carried track was on the right object and whose
DD cell passed — the separation four sim cycles (P5.10–P5.13) could not manufacture is present for
free in real video, because the prompt-time re-ground is genuinely hard on UAV123 frames and never
missed on clean Gazebo renders. The `car3:200` control, which failed WSEL under RG in P5.3/P5.4/P5.5
and was labelled "resolution-bound", **flips to PASS under DD (0.7256)** — that family was a
re-grounding artifact, not a carry limit.
Proof: `proof/p56_pass_grid.png` (P5.3 RG vs P5.5 MC-RG vs P5.14 DD, per cell),
`proof/p56_contract.png` (delivered-box IoU with the 0.25 floor + shadow agree/disagree tags;
DD 0.00 s vs shadow 4.51 s), `proof/p514_swap_car7_460_deliver_OFFOBJECT.png` (the one FAIL, box on
empty kerb — negative proof), `proof/p514_swap_car9_560_deliver_PASS.png` (the 0.2843 marginal pass),
`proof/p514_DD_{WSEL,SWAP}_car10_240.mp4` (same scene, two phrases, zero acquire latency). Detail:
[`../../experiments/2026-07-19-realvid-dd-select/README.md`](../../experiments/2026-07-19-realvid-dd-select/README.md).

### P5.15 — carry-horizon: warm-carry survival at 8/16/24 s idle on real video (2026-07-19)

Rig: RTX 3090 host (`.venv-ft`: python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6),
SAM2 `sam2.1-hiera-tiny` stepped at the deployed 6.15 Hz idle budget (stride 5 @ 30 fps),
seeded at GT[0]; MAINT arm adds the deployed P5.5 idle ROI re-anchor (margin 2.0, min_side
256, crop 512, LANCZOS, accept = parseable + in-frame, **no IoU floor**) every 165 frames
with the clip's generic P5.2 caption, VLM = Jetson `phase3-terse100eos-1024-q8_0.gguf`,
15W + `jetson_clocks`. Clip set = the frozen 25-clip P5.2 set (5 categories). n=1
deterministic, alive = carried-box IoU >= 0.25 vs UAV123 GT at the scoring frame. 50/50
cells scored, 0 INVALID, 0 N/A. Matrix wall ~10 min (PLAIN 8.4 s/cell, MAINT 16.5 s/cell)
against a 35–60 min estimate — the second consecutive ~4x overestimate.

| arm | alive @8 s | alive @16 s | alive @24 s | deaths (clip) |
|---|---|---|---|---|
| PLAIN (unmaintained carry) | 25/25 | **24/25** | 24/25 | `car7` (f270, never recovers) |
| MAINT (+ P5.5 idle re-anchor) | 24/25 | 22/25 | 22/25 | `car10`, `car3`, `person10` (identity swap); `car7` rescued |

RQ-P5.15a floor was 18/25 at 16 s; measured 24/25. Surviving cells sit at IoU 0.6–0.97 at
24 s, i.e. not marginal. RQ-P5.15b did not run its comparison — the pre-registered ceiling
(PLAIN@24s >= 22) fired. Non-gating: MAINT accepted **100/100** re-anchor rounds and is
**net -2 clips**, because a generic-caption re-ground with no identity constraint
eventually lands on a different same-class object (visible in the h24 frames). Health
signals: `area_ratio` separates alive from dead (median 1.039 vs 0.163 over 150 horizon
points), `hist_corr` does not (0.742 both).
Proof: `proof/p515_arms.png` (survival vs horizon, both arms, floor line),
`proof/p515_alive_grid.png` (per-clip x per-horizon IoU grid),
`proof/p515_decay.png` (per-step IoU traces by category),
`proof/p515_maint_car10_h24_IDENTITY_SWAP.png` (negative proof: re-anchor moved onto a
different car), `proof/p515_plain_car7_h16_DEAD.png` (the one RQ-a failure).
Detail: [`../../experiments/2026-07-19-carry-horizon/README.md`](../../experiments/2026-07-19-carry-horizon/README.md).

### P5.16 — autodisc-select (2026-07-19T15:03Z)

Direct-delivery select with the **seed oracle removed**: both candidate carries are seeded by
the deployed Jetson VLM itself during the idle window (discovery starts at f0-150, target
caption first, accept = parseable + in-frame + IoU < 0.5 vs the other carry). No ground truth
anywhere in the loop. Everything else imported byte-identical from P5.14 `select_p56`.
Rig: RTX 3090 (SAM2 `facebook/sam2.1-hiera-tiny`, CARRY_HZ 6.15 / CAND_HZ 3.075) + Jetson Orin
Nano `phase3-terse100eos-1024-q8_0.gguf`, MAX_SIDE 1024, `15W` mode 0 + `jetson_clocks`.
python 3.12.10 / torch 2.6.0+cu124 / transformers 4.57.6. DS_OFFSET 150, IOU_SAME 0.5,
DIST_FLOOR 0.25, ROI 2.0/256/512, reanchor [90,165], cover_s 10.0. n=1 deterministic, 6 scenes
x 2 legs, UAV123 1280x720 @ 30 fps.

| leg | gating PASS | vs P5.14 (oracle seeds) | control car3:200 |
|---|---|---|---|
| WSEL (select warm target) | **4/5** | 5/5 — lost `car7:460` | PASS (predicted to flip; did not) |
| SWAP (select warm distractor, strengthened) | **4/5** | 4/5 — unchanged | PASS |

**Oracle delta = 1 flip in 12 cells.** Discovery accepted **24/24** VLM calls (0 invalid, 0
duplicate, 0 in-flight-at-prompt, 0 `discovery-failed` legs) at mean full-frame latency
**4.51 s** (min 4.49 / max 4.56, n=24), both captions completing 2.0–4.0 s before the prompt.
Target seed IoU vs GT 0.52–0.80 (median 0.63) where discovery was correct, **0.0** on the one
failure. Delivery `acquire_s = 0.00` vs shadow re-ground 4.48–4.53 s; the non-gating shadow
**disagreed on 4/12 cells** (3x NO_MATCH, 1x wrong-object) — same separation as P5.14, now with
no GT in the loop. Weak-vs-strengthened SWAP 6/6 vs 5/6. Both re-anchor boundaries behaved as
designed (f0+90 skipped `in-discovery` in all 12, f0+165 accepted in all 12, none harmful over
this ~8 s idle). Matrix wall 5.7 min, mean 29 s/cell.
The single failure `car7:460` is a **language** failure, not vision or tracking: two adjacent
silver cars make "the silver car" ambiguous at the discovery frame, the VLM grounds the wrong
one (`seed_iou_gt` 0.0), that carry dies during idle and the cell scores `lost-track`.
Proof: `proof/p516_pass_grid.png` (P5.14 vs P5.16, per cell x leg),
`proof/p516_discovery.png` (discovery call timelines),
`proof/p516_flip_DSC_WSEL_car7_460_discovery.png` + `..._deliver.png` (negative proof of the
one flip: wrong silver car at discovery, then no box at delivery).
Detail: [`../../experiments/2026-07-19-autodisc-select/README.md`](../../experiments/2026-07-19-autodisc-select/README.md).
