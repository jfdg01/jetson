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
