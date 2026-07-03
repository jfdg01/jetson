# E15 mask-hardening — does the E14 mask gate survive geometry stress?

- **Pre-registered:** 2026-07-03T18:40Z (Madrid wall-clock)
- **Status:** PRE-REGISTERED — matrix not yet run
- **Branch:** `experiment/mask-hardening`
- **Roles:** design + patches by Fable (this README, `phase3_sitl.py`/`sitl_cam.py`
  E15 knobs, `run_e15.py`). Opus runs the matrix and fills **Results only** —
  do NOT re-patch code. Every judgment is pre-made below; if a case is not
  covered by a rule here, record it verbatim and mark the leg `UNRULED`, do
  not invent a rule.
- **Rig:** host 3090 runs SITL + StreamCarry (`--image-size 1024` default);
  Jetson runs the VLM (Qwen2-VL-2B Q8_0) and **self-boots per trial** — no
  manual server start. Jetson at 15W (`nvpmodel -m 0`) + `jetson_clocks`
  (there is NO MAXN on this board). Do **NOT** pass `--remote-carry`: the
  mask gate is local-carry only (phase3_sitl exits if you try).
- **Versions:** same stack and venv (`.venv-ft`) as E14; see
  `experiments/2026-07-03-mask-identity/README.md` for the pinned list. The
  only code deltas vs E14's merge (`11698ee`) are the E15 patches on this
  branch, all **off by default** (see "Code changes").

## Research question

**RQ-E15: Is the E14 mask-median REGROUND gate robust to the win-path
geometry, or did E14's 3/3 depend on its single favourable accept window?**

E14 (RQ-E14 YES, `experiments/2026-07-03-mask-identity/`) closed the E3/E7/E13
identity hole: with `--reground-gate mask`, mk-decoy went 3/3 — the gate
rejected every decoy/blend resolve until the true car cleanly separated from
the single parked decoy, then accepted it. The audit of those runs (below)
shows the 3/3 is three near-identical replays of ONE scenario whose win
depended on an untested assumption: after the trap there is exactly one clean,
unoccluded accept window (observed accept t=86.25, car ~8.8 m past the decoy),
and the DR-drifting copter caught it. E15 attacks exactly that assumption with
two geometry stress families, keeping the shade/descriptor identical to E14:

- **dd (double-decoy):** a second parked decoy, same lane, same 215 shade,
  7 m north of the first. The car must clear two identity traps back-to-back;
  the gap (7 m) is smaller than E14's observed accept margin (8.8 m), so the
  clean window between trap 1 and open road is destroyed — the gate must keep
  rejecting through both traps and accept only past the second.
- **ro (re-occlusion):** a second full-occlusion bridge over t=[82, 92]
  (`--occ2 82 10` → world span N=[19.0, 25.5]). E14's observed accept at
  t=86.25 falls inside this window — the car is re-hidden exactly where E14
  won, so the gate must reject any resolve during the blind window (only the
  decoy or bridge junk is visible) and relock on the car as it re-emerges.

**Numeric pass/fail (pre-stated, mechanical — coded in `run_e15.py::verdict`):**

- A **control leg** (no gate) REPRODUCES iff `n_regrounds >= 1` AND
  `twin.closest_at_end != "true"` AND `twin.final_d_true_m >= 10.0`.
  (End-state attribution; `relock_on[0]` is never consulted — E14's fix.)
- A **gated stress leg** (dd-a/b/c, ro-a/b/c):
  - `n_regrounds == 0` → **NOT-MEASURABLE** (confident-latch, nothing tested).
  - `relock_on` empty with regrounds fired → **FAIL** subtype
    *identity-preserving no-relock* (report `n_reground_gate_rejects`).
  - **PASS** iff `relock_on[-1] == "true"` AND `closest_at_end == "true"` AND
    `final_d_true_m <= 2.0` AND `in_fov_frac >= 0.80`.
  - last relock "true" but end-state far → **FAIL** subtype *verified-but-lost*.
  - The in-FOV bar is **0.80** for stress legs (pre-registered relaxation:
    `--occ2` adds ~10 s of full blindness / ~26 s partial (t 66→92 ingress to
    nose-out), dd extends the reject window; both eat geometric FOV via DR
    drift). A PASS with `0.80 <= in_fov < 0.90` is annotated `[degraded-fov]`.
    reg-e14 keeps E14's original 0.90.
- **reg-e14** (regression, exact E14 mk-decoy config): PASS by the same rule
  with the 0.90 bar. It must PASS or the E15 patches perturbed the E14 path.

**RQ-E15 verdict rule:**

- **YES** iff reg-e14 PASS AND both controls REPRODUCE AND dd 3/3 PASS AND
  ro 3/3 PASS.
- **NO** iff reg-e14 PASS AND at least one reproducing family has a FAIL leg
  — record the family split (e.g. "dd survives, ro does not"); a family
  localization is the useful thesis result either way.
- **NOT-MEASURABLE** iff reg-e14 FAILs (patch regression — stop interpreting,
  report and halt) or NEITHER control reproduces. If exactly one control
  reproduces, compute the RQ on that family alone and say so.
- A NOT-MEASURABLE stress leg (confident-latch) is re-run ONCE; if it
  repeats, the family verdict is NOT-MEASURABLE (blocks YES, does not force NO).

## Audit of E14 (what motivated this design)

From `experiments/2026-07-03-mask-identity/runs/*/results.json`:

- **3/3 is one scenario, thrice.** mk-decoy a/b/c: first_lock 4.71/4.71/4.71,
  final_d_true 0.21/0.21/0.22, gate rejects 13/13/11, accept t=86.25 in all
  three (distinct file md5s — real runs, near-deterministic rig). n=3 measures
  replay stability, not robustness.
- **The shade margin is analytic, not empirical.** The renderer is
  flat-shaded, so the frame-0 mask median IS the body shade with zero
  variance (smoke: medians exactly 215.0/245.0, distances exactly 30.0/0.0).
  The gate accepts iff |Δshade| <= tau=12 — a shade-convergence sweep would
  measure a constant. A 245-shade decoy is byte-identical to the target and
  out of reach of ANY appearance cue *by construction* (E3's framing). So
  shade is NOT the untested axis; geometry is.
- **The win path is geometry-dependent.** mk-decoy-a acquire_log: lock 4.71;
  size rejects t=34.8-44.0 (bridge blend); 13 shade rejects t=46.3-81.6
  (decoy/blend resolves); accept t=86.25 when the true car re-entered the top
  of frame cleanly separated. One trap, one occlusion, one clean window.
  Untested: two traps (no clean window between), and re-occlusion during
  separation (the window itself removed). The predicted failure branch —
  identity-preserving no-relock (gate rejects everything, DR drifts blind
  forever) — was never observed in E14; E15's stress geometries are exactly
  the conditions that could trigger it.
- **Regressions were real but n=1.** mk-reg-3.0 first_lock 12.17 matches E12
  d3.0 exactly; mk-rt template rebind [230,90,40] correct. Fine as-is.

**Direction picked: (a) harden the E14 gate** (over (b) move to the next
constraint). Reason: E14's YES is load-bearing for the thesis narrative
("identity hole closed") but rests on one geometry; a 1-cycle stress test
either upgrades it to a defensible claim or finds the failure mode now,
while the fix's design is fresh. The runner-up (b) was the 3b remote-carry
port of the gate+lever stack — deferred, right step only AFTER robustness is
established, and a heavy multi-file port is the wrong shape for a
zero-judgment executor cycle. Also rejected: shade-convergence sweep
(analytic in this renderer, measures the constant tau — see audit) and
pre-lock chase reach >3.0 m/s (E12 closed and parked that arc).

## Code changes (committed on this branch, all off by default)

`experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`:

- `--decoy2 M` (default None): second parked decoy M meters north of the
  first (`bridge[1] + 2.0 + M`), same lane, same `--decoy-shade`. Requires
  `--twin decoy` (guarded).
- `--occ2 START_S DUR_S` (default None): second full-occlusion window — a
  second world-fixed bridge sized by the same formula as the first
  (`(c(START)-hl, c(START+DUR)+hl)`).
- `closest_label()` 3-way attribution helper: `d_d2=None` reproduces the
  E3-E14 two-way rule bit-identically (strict `dd < dt`, tie → "true");
  with a second decoy, `relock_on` may contain `"distractor2"` and
  `twin.closest_at_end` may be `"distractor2"`; `twin.final_d_dist2_m` added
  (None when no decoy2). Trial CSV columns unchanged (decoy2 distances live
  in results.json only — CSV stays bit-identical for E2-E14 configs).
- `occluded` metric generalized to `any(...)` over bridges (identical
  output with one bridge). Selfcheck extended with the `closest_label`
  truth table.

`experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py`:

- `NadirCam(bridge_n=...)` accepts one span (tuple, the E2-E14 form) or a
  list of spans; `render(..., extra_cars=[(ned, color), ...])`. Selfcheck
  asserts the single-bridge/no-extra-cars render is `np.array_equal` to the
  E2-E14 path (default-path identity), plus bridge-2 occlusion and 3-blob
  checks.

Defaults off → every E2-E14 config renders and scores bit-identically
(asserted by the sitl_cam selfcheck; behaviorally re-proven by reg-e14).

## Geometry (all at speed 0.25 m/s, c(t) = 0.5 + 0.25 t, hl = 2.0)

| thing | value | derivation |
|---|---|---|
| bridge 1 | N = (6.0, 11.25) | OCC_START=30, OCC_DUR=5 (constants) |
| decoy 1 | N = 13.25 | bridge1[1] + 2.0 |
| decoy 2 (dd) | N = 20.25 | decoy1 + `--decoy2 7.0` |
| car passes decoy 1 | t ≈ 51 | c(t) = 13.25 |
| car passes decoy 2 | t ≈ 79 | c(t) = 20.25 |
| E14-margin clean separation from decoy 2 | t ≈ 114 | c(t) = 20.25 + 8.8 |
| bridge 2 (ro) | N = (19.0, 25.5) | `--occ2 82 10` via the sizing formula |
| car partially hidden (ro) | t ≈ 66 → 108 | nose enters 19.0 / tail clears 25.5 |
| car FULLY hidden (ro) | t ∈ [82, 92] | by construction of the formula |
| E14's observed accept | t = 86.25 | inside the ro blind window (the point) |

Expected accepts: dd ~t 110-125, ro ~t 95-110 — both leave >=25 s of follow
inside the 150 s trial for the `final_d_true <= 2.0` convergence (pursuit
closes at up to 2.5 m/s vs car 0.25; E14 converged to 0.21 m).

## Run matrix (Opus: run exactly this)

```bash
cd /home/gara/jetson
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"   # NOPASSWD, 15W mode 0
mkdir -p experiments/2026-07-03-mask-hardening/raw
.venv-ft/bin/python experiments/2026-07-03-mask-hardening/run_e15.py \
  2>&1 | tee experiments/2026-07-03-mask-hardening/raw/matrix.log
```

The runner does, in order (do not reorder):

1. **Precondition:** both selfchecks (`phase3_sitl.py --selfcheck`,
   `sitl_cam.py`). Any failure → PRECONDITION-FAIL, legs skipped, verdict
   NOT-MEASURABLE. (No Jetson mask smoke: E15 uses E14's exact shade and
   descriptor; the no-gate controls are the behavioral precondition.)
2. **9 legs**, each snapshotted to `runs/<label>/{results.json,trial.csv,trial.mp4}`
   (phase3_sitl **clobbers** `raw/phase3a-sitl/trial-0.25ms.{csv,mp4}` and
   `runs/phase3a-sitl/results.json` every run — only the snapshots survive):

| label | flags (beyond the shared decoy set) | n | purpose |
|---|---|---|---|
| reg-e14 | `--reground-gate mask` | 1 | exact E14 mk-decoy config — patch regression |
| ctl-dd | `--decoy2 7.0` | 1 | no gate: dd geometry must wrong-lock |
| dd-a/b/c | `--decoy2 7.0 --reground-gate mask` | 3 | gate vs double trap |
| ctl-ro | `--occ2 82 10` | 1 | no gate: ro geometry must wrong-lock |
| ro-a/b/c | `--occ2 82 10 --reground-gate mask` | 3 | gate vs re-occlusion |

Shared decoy set (all 9 legs): `--speed 0.25 --twin decoy --decoy-shade 215
--duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion`.
All legs record video (every trial writes trial.mp4; the snapshot keeps it).

**Abort criteria:** a leg exceeding 1500 s wall-clock is killed → INVALID;
snapshot whatever exists and continue. Re-run an INVALID or NOT-MEASURABLE
leg ONCE at the end of the matrix; a still-missing/INVALID leg blocks YES.
If the host GPU OOMs or SITL fails to boot twice in a row, stop and report.

## Estimates (pre-registered; wrong estimates are content)

- Runtime: ~12 min/leg x 9 + selfchecks ≈ **110-125 min** (E14 actual was
  ~110 min for 8 legs + smoke).
- reg-e14 PASS: ~90% (near-deterministic rig; risk is only a patch slip).
- Each control REPRODUCES: ~85% (E14 ctl-decoy reproduced cleanly; new
  geometry could conceivably self-rescue, which would be a finding).
- dd 3/3: ~45-55% — the no-clean-window gauntlet is the harder family; the
  plausible failure is identity-preserving no-relock or verified-but-lost.
- ro 3/3: ~50-60% — reject-through-blindness then relock on emergence.
- Overall YES: ~25-35%. A NO with family localization is fully useful.

## Results (TBD — Opus fills this section only)

| leg | verdict | n_regrounds | gate_rejects | relock_on | closest_at_end | final_d_true_m | final_d_dist2_m | in_fov_frac | first accept t |
|---|---|---|---|---|---|---|---|---|---|
| reg-e14 | | | | | | | — | | |
| ctl-dd | | | | | | | | | — |
| dd-a | | | | | | | | | |
| dd-b | | | | | | | | | |
| dd-c | | | | | | | | | |
| ctl-ro | | | | | | | | | — |
| ro-a | | | | | | | | | |
| ro-b | | | | | | | | | |
| ro-c | | | | | | | | | |

- **RQ-E15 verdict:** TBD (apply the mechanical rule above; the runner prints
  per-leg verdicts — copy them, do not re-derive).
- **Estimate vs actual:** TBD (runtime, per-family outcomes vs the numbers above).
- **Deviations/surprises:** TBD (anything UNRULED goes here verbatim).

## Proof clips (TBD — 2-3, committed under `proof/`)

Pre-registered picks (copy from `runs/<label>/trial.mp4`, caption with the
leg's config and verdict):

1. `ctl-dd/trial.mp4` (or `ctl-ro` if dd does not reproduce) — the no-gate
   wrong-lock on the new geometry (the failing behaviour).
2. `dd-a/trial.mp4` — the gate running the double-trap gauntlet (the fix
   working, or the failure the fix could not prevent — either is the clip).
3. `ro-a/trial.mp4` — reject-through-re-occlusion then relock on emergence
   (or its failure).

## Ledger updates on completion (Opus)

- `docs/results/part4-end-to-end.md`: one row per leg (config + verdict).
- `docs/questions/part4-end-to-end.md`: RQ-E15 + one-line verdict.
- `docs/decisions/part4-end-to-end.md`: direction (a) over (b) with the
  rejected alternatives above (shade sweep analytic; 3b port deferred until
  robustness established; chase-reach parked); the 0.80 stress-leg FOV bar;
  same-shade decoy2 (isolates geometry — both traps stay equally
  discriminable from the 245 target, so shade difficulty is held at E14's
  level and geometry is the only new variable).
- No new SOURCES (no new external artifact).
