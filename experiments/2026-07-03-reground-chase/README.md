# E17 reground-chase — does extending E11's chase-hold to REGROUND lift the relock rate above E16's 6/8?

- **Pre-registered:** 2026-07-03T21:45Z (Madrid wall-clock)
- **Status:** COMPLETE 2026-07-04T00:35Z. RQ-E17 = **NO** (r=0/10, the lever REGRESSED E16's 6/8 to 0/10 via HOLD-MISS runaway); guards PASS (no 3.0 m/s ceiling regression), 0 identity breaches.
- **Roles:** design + patches by Fable (this README, `run_e17.py`, and the
  `--reground-hold` patch to `phase3_sitl.py` — **already committed on this
  branch; Opus: do NOT edit these files**). Opus runs the matrix and fills
  **Results only** — do NOT re-patch code. Every judgment is pre-made below;
  if a case is not covered by a rule here, record it verbatim and mark the
  leg `UNRULED`, do not invent a rule.
- **Branch:** `experiment/reground-chase` (from clean main `ad2c009`, the
  E16 merge).
- **Rig:** host 3090 runs SITL + SceneRenderer + StreamCarry (SAM2 @1024
  default); the Jetson runs the VLM (Qwen2-VL-2B Q8_0) and **self-boots per
  trial** — no manual server start. Jetson at 15W (`sudo nvpmodel -m 0`) +
  `sudo jetson_clocks` (NOPASSWD; there is NO MAXN on this board). Do **NOT**
  pass `--remote-carry` (mask gate is local-carry only; phase3_sitl refuses).
- **Versions:** same stack and venv (`.venv-ft`) as E14–E16 — pins in
  `requirements-ft.lock.txt`; SAM2.1-hiera-tiny on host, Qwen2-VL-2B Q8_0 on
  Jetson. One code delta vs main `ad2c009`: the `--reground-hold` flag
  (below), **default `none` = bit-identical to E2–E16** (with
  `reground_hold="none"`, `rg_hold` is constant `False` and the hold/chase
  conditions reduce exactly to the E6/E11 originals; verified by inspection
  and `--selfcheck` PASS).

## RQ-E17

**Does `--reground-hold chase` — E11's validated pre-lock blob-chase,
extended to REGROUND blind phases — lift the mask-gate relock rate above
E16's measured 6/8, with zero identity breaches and no regression at the
3.0 m/s honest follow ceiling?**

Over n=10 independent replicates of E16's byte-identical mask-gate decoy
config plus the lever (`--speed 0.25 --twin decoy --decoy-shade 215
--duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion
--reground-gate mask --reground-hold chase`, app-tau default 12), with r =
per-rep PASS count over valid reps (rules below), against E16's **historical
baseline r = 6/8** (same rig, previous day, byte-identical default code
path; the ctl leg guards rig validity — no baseline re-run, rationale under
Rejected alternatives):

- **LIFTS** iff zero valid reps FAIL (r = denom/denom). RQ-E17 = **YES**
  (given no breach and guards OK): the FAIL modes E16 measured at 2/8 are
  cut to 0/10; the relock claim upgrades from "~0.75 rate" to "reliable
  with reground-chase".
- **PARTIAL** iff exactly one valid rep FAILs. RQ-E17 = **QUALIFIED**: the
  lever helps (point estimate 0.9 vs 0.75) but one draw still misses;
  record the FAIL's mode attribution (HOLD-MISS vs PROPOSAL-MISS, below) —
  it names the residual constraint.
- **NO-LIFT** iff two or more valid reps FAIL. RQ-E17 = **NO**: at n=10 vs
  8, >=2 FAILs is indistinguishable from the 0.75 baseline; the lever does
  not move the rate and the residual constraint is not (only) FOV-keeping.
- **NOT-MEASURABLE** iff a selfcheck fails, ctl fails to reproduce twice,
  or fewer than 8 valid reps survive.
- Override, any band: **any** rep with `"distractor" in relock_on` →
  verdict suffix `[identity-breach observed]` and RQ-E17 = **NO**
  regardless of rate — the lever must not create breaches (E16 had 0/8;
  all E16 FAILs were identity-preserving).
- Override: guards (3.0 m/s ceiling legs, below) with fewer than 2 PASSes
  among valid guard legs → `[REGRESSED]`, RQ-E17 = **NO** (a relock lift
  that costs the follow ceiling is rejected for the stack). Fewer than 2
  *valid* guard legs after retries → `[guard-incomplete]`, RQ-E17 capped at
  **QUALIFIED** even if LIFTS.

NO-LIFT is a full answer and thesis content: it would show the E16 FAIL
modes are not FOV-keeping failures after all, pointing back at the VLM
proposal stream.

## Audit findings (why this lever; what E16's two FAILs actually were)

Audited 2026-07-03 from E16's snapshots
(`../2026-07-03-relock-rate/runs/<leg>/{results.json,trial.csv}`). E16's
README records the FAILs as "win-path timing failures upstream of the
gate"; this audit isolates the *mechanism* and finds both FAILs share one:
**the copter lost the true car from its FOV during REGROUND while
DR-coasting on a corrupted `hist`, even though the car — the scene's only
mover — was still visible when the drift began.**

1. **A new per-leg metric separates PASS from FAIL perfectly.** Define
   `rg_fov` = in-FOV fraction over REGROUND-state rows of the control CSV
   (the fraction of the *blind* phase the true car stayed in frame).
   Computed over all 9 E16 legs:

   | leg | verdict | rg_fov |
   |---|---|---|
   | rep-2,3,4,6,7,8 (all PASS) | PASS | **1.000** (all six) |
   | rep-1 | FAIL wrong-end | 0.507 |
   | rep-5 | FAIL no-relock | 0.203 |
   | ctl (no gate) | wrong-lock | 0.255 |

   Every PASS held the car in FOV through the entire reject window; both
   FAILs lost it. The relock win path needs the VLM to *see* the separated
   car; FOV-keeping during REGROUND is the gating resource.
2. **rep-5 mechanism: lateral DR escape.** Its REGROUND spans t=32.45 to
   the 150 s end. The trace shows `copter_e` drifting −1.04 → −24.13 m while
   `rover_e` stays at −0.01 — the loss transient left a spurious ~−0.18 m/s
   east-component in `hist`, and `pursuit_vel` faithfully integrated it:
   24 m west of the road by t≈137, car long out of frame (rg_fov 0.203).
   The VLM then had nothing to propose on (40 size rejects of empty-scene
   boxes) — the "no-relock" was downstream of the FOV loss.
3. **rep-1 mechanism: static-latch parking.** After its early wrong-end
   accept, the terminal phase shows the copter parked at n≈20.01 with
   v≈(−0.009, 0.033) — a motion-stale `hist` gave DR zero velocity — while
   the rover walked 25 → 36 m north *in FOV, then out of it* (rg_fov
   0.507). Same family: DR coasting on bad hist while the mover is
   observable.
4. **The validated fix already exists but is gated off during REGROUND.**
   E11's `--acquire-hold chase` solves exactly this — it feeds the
   ego-motion-compensated frame-diff blob (`motion_blob` →
   `blob_chase_box` → `box_to_world`) into `hist`, so pursuit chases the
   observed mover instead of a stale extrapolation. It is proven at
   3.0 m/s pre-lock (E11/E12). But the E6/E11 hold block is conditioned on
   `sm.first_lock_t is None` — it **never** runs during REGROUND. The decoy
   is parked; the true car is the only mover; the blob signal is exactly
   the "which one is the target" cue REGROUND lacks.
5. **What the lever does NOT address:** rep-1's *early accept* of a
   still-blended box at t=71.88 happened while the car was in FOV — that is
   an accept-path event, untouched by a control-law lever. One residual
   FAIL of the PROPOSAL-MISS type is therefore plausible even if the lever
   works (hence the PARTIAL band and the per-FAIL mode attribution).

**The lever (already committed on this branch):** `--reground-hold
{none,chase}`, default `none`. With `chase`, whenever the SM is in REGROUND
and the VLM has no accepted box, the existing E6 blob pipeline runs and the
E11 chase append feeds `hist`, so `pursuit_vel` servos the copter onto the
scene's mover — keeping the car in frame until the VLM offers a clean box
that the size prior + E14 mask gate (both **untouched**) can accept.
Control law only; identity is still judged by the gate. **REGROUND only,
never RETARGET** (post-switch, the old mover is precisely the wrong
target). Prediction: rg_fov → ~1.0 on all reps, and the no-relock/lateral-
escape mode disappears.

**Rejected alternatives** (seed for DECISIONS):

- *E3b CLIP appearance gate (the standing theme)* — rejected, now with
  data: E16 measured **0 identity breaches in 8** gated reps; re-acquire is
  already identity-safe, so an identity lever addresses a failure count of
  zero. The binding constraint is re-acquire *completion* (2/8), and both
  misses trace to FOV loss, not identity. Also E13/E14 showed crop-based
  cues fail the blend box structurally. Given up: nothing measurable this
  cycle.
- *Accept-hysteresis (require 2 consecutive gate-passing accepts)* —
  targets only rep-1's early-accept mode (1 of the 2 FAILs), adds a full
  VLM draw (~2.35 s) of latency to every legitimate relock, and interacts
  with the accept path (higher regression risk). The chase lever targets
  the FOV mechanism common to both FAILs and leaves the accept path
  untouched. Given up: a direct fix for the early-accept mode; if E17
  lands PARTIAL with a PROPOSAL-MISS FAIL, hysteresis is the natural next
  cycle.
- *Characterize the decoy trap at 3.0 m/s instead* — at speed the blend
  trap barely forms (emergence-to-clear ~2 s at 3.0 vs ~50 s at 0.25);
  the identity question is a slow-regime problem and E16 just measured it.
  Given up: nothing — the guards cover the 3.0 regime's regression risk.
- *Longer `--duration-s` to give the VLM more chances* — once the car
  exits FOV on a divergent DR track (rep-5: 24 m off-road and departing),
  more time observes more of the same empty frames. Does not touch the
  mechanism. Given up: a cheap flag-only cycle, but one the traces already
  refute.
- *Re-running an 8-rep no-lever baseline arm alongside* — E16 measured
  exactly that arm yesterday on this rig under byte-identical default-path
  code; re-measuring it would spend half the night to re-draw a known
  distribution. The ctl leg re-verifies the rig instead. Given up:
  same-night pairing; if rig drift is suspected post-hoc, the ctl leg is
  the tell (halt-on-fail).

## Independence of draws (pre-registered)

Unchanged from E16 (its README, "Independence of draws"): the harness
exposes no RNG seed; each leg is a fresh full-process launch — new
ArduCopter SITL boot, new Jetson llama-server boot via `JetsonBackend`, new
StreamCarry — on a real-time ~20 Hz wall-clock loop; variation enters
through loop/VLM timing jitter and is empirically nonzero under fixed code
(E16 accept times 81.30–133.90 s across its six PASSes). n=10 samples the
same distribution E16 sampled 8 times, plus the lever.

## Code changes (Fable, already committed on this branch — Opus: do NOT edit)

| file | change |
|---|---|
| `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` | `--reground-hold {none,chase}` (default `none`): adds `reground_hold` param to `run_trial`, extends the E6/E11 hold-block condition with `rg_hold = reground_hold == "chase" and sm.state == "REGROUND"`, and lets the E11 chase append fire when `rg_hold` (in addition to the pre-lock `acquire_hold == "chase"` path). Accept path (size prior, reground gate) untouched. Cfg manifest records the flag. |
| `experiments/2026-07-03-reground-chase/run_e17.py` | the run matrix (this campaign's only other new file) |

Bit-identical guarantee: with the default `none`, `rg_hold` is always
`False`; the two modified conditions reduce to
`acquire_hold in ("motion","chase") and sm.first_lock_t is None` and
`acquire_hold == "chase"` — the exact E6/E11 originals. E2–E16 configs
never pass the flag and are unaffected. `phase3_sitl.py --selfcheck`
passes on the patched file (verified before commit).

## Run matrix (Opus: run exactly this)

Preconditions: host 3090 free; `ssh jetson` up. Then, from the repo root:

```bash
cd /home/gara/jetson
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"   # NOPASSWD, 15W mode 0
mkdir -p experiments/2026-07-03-reground-chase/raw
.venv-ft/bin/python experiments/2026-07-03-reground-chase/run_e17.py \
  2>&1 | tee experiments/2026-07-03-reground-chase/raw/matrix.log
```

That is the whole matrix. The runner executes, in order (do not reorder):

1. **Selfchecks** (`phase3_sitl.py --selfcheck`, `sitl_cam.py`) — any
   failure exits: PRECONDITION-FAIL, no legs, RQ-E17 = NOT-MEASURABLE.
2. **ctl** — no-gate no-hold decoy control; must REPRODUCE the wrong-lock
   or the runner retries once (`ctl-retry`) then **halts**
   (NOT-MEASURABLE) — no point burning 10 reps on a drifted rig.
3. **guard-a, guard-b** — the 3.0 m/s honest-ceiling config (E12's d3.0 =
   E14's mk-reg-3.0 flags) **plus the lever**; 75 s default duration.
   These run *before* the reps as a cheap early regression warning, but
   whatever they say, the reps still run (the rate stands on its own; the
   guard result only feeds the override). **guard-c** runs only iff
   exactly one of guard-a/b is a valid PASS (tie-break to n=3, majority
   rules); INVALID guards get one retry each.
4. **rh-1 .. rh-10** — E16's exact mask-gate config + `--reground-hold
   chase`.
5. **Retries** — any rh rep verdicted NOT-MEASURABLE (confident-latch) or
   INVALID is re-run once, max 2 retries total (a retry replaces its
   original in the rate; a failed retry excludes the rep from the
   denominator). More than 2 candidates → runner warns "rig likely sick",
   retries the first 2 only, the rest stay excluded.

| leg | flags | n | purpose |
|---|---|---|---|
| ctl | `--speed 0.25 --twin decoy --decoy-shade 215 --duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion` | 1 | no gate, no hold: wrong-lock still reproduces (rig/VLM drift guard) |
| guard-a/b(/c) | `--speed 3.0 --vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold chase --acquire-delay 3.0 --reground-gate mask --reground-hold chase` | 2 (+1 tie-break) | lever ON at the E12 honest ceiling: no follow regression |
| rh-1..10 | ctl flags + `--reground-gate mask --reground-hold chase` | 10 | the rate, vs E16's 6/8 |

Every leg is snapshotted to
`experiments/2026-07-03-reground-chase/runs/<label>/{results.json,trial.csv,trial.mp4}`
immediately after it finishes (phase3_sitl **clobbers**
`experiments/2026-07-01-temporal-acquire-carry/raw/phase3a-sitl/trial-<speed>ms.{csv,mp4}`
— note the basename depends on `--speed`: `trial-0.25ms.*` for ctl/rh legs,
`trial-3.0ms.*` for guards — and `.../runs/phase3a-sitl/results.json` every
run; only snapshots survive; always read the snapshots). Every trial
records video (`trial.mp4`).

**Gotchas:** run from repo root with `.venv-ft/bin/python` (the runner uses
absolute paths anyway); do not run anything else on the 3090 during the
matrix; do not touch `--app-tau`, shades, geometry, or flags mid-run — any
deviation is a new pre-registration. If the host GPU OOMs or SITL fails to
boot twice in a row, stop and report. Watch the guard legs for the E12
chase-runaway signature (copter overshooting the rover pre-lock,
`copter_n > rover_n + 15`): if a guard FAILs, note whether the CSV shows
runaway (pre-lock chase artifact) vs a reground stall (the new lever) —
record, don't re-run for it.

## Verdict rules (mechanical — the runner prints these; Opus does not deliberate)

All fields from the leg's snapshotted `results.json` `trial` object.
`acquire_log` entries are lists `[t, box, accepted, reason]`; relock accept
times = accepted entries after the first. `rg_fov` = in-FOV fraction over
`state == "REGROUND"` rows of the snapshotted `trial.csv` (the runner
computes and prints it; `None` if the leg never entered REGROUND).

- **ctl REPRODUCES** iff `n_regrounds >= 1` AND `twin.closest_at_end ==
  "distractor"` AND `twin.final_d_true_m >= 10.0` (E14/E16's rule).
- **rh PASS** iff `n_regrounds >= 1` AND `twin.relock_on` non-empty AND
  `twin.relock_on[-1] == "true"` AND `twin.closest_at_end == "true"` AND
  `twin.final_d_true_m <= 2.0` AND `in_fov_frac >= 0.90` — byte-identical
  to E14/E16's PASS rule (same bar, so the rate is comparable to 6/8).
- **rh FAIL subtypes** (recorded, all count as FAIL in r): *no-relock*
  (`relock_on` empty), *wrong-lock* (`relock_on[-1] != "true"`),
  *wrong-end* (relocked true but `closest_at_end != "true"`),
  *verified-but-lost* (relocked true, ended `> 2.0 m` or `in_fov < 0.90`).
  **Mode attribution on every FAIL:** `[HOLD-MISS]` iff `rg_fov < 0.90`
  (the lever failed its proximal job — the car left FOV during REGROUND
  anyway), else `[PROPOSAL-MISS]` (the lever held the car in frame but the
  accept path still missed — the rep-1 family, out of the lever's scope).
- **rh NOT-MEASURABLE** iff `n_regrounds == 0` (confident-latch — nothing
  tested); triggers a retry (max 2 total).
- **guard PASS** iff `in_fov_frac >= 0.90` AND `recovered_after_occlusion`
  — E12's d3.0 PASS rule. Guard regression verdict: >=2 PASSes among valid
  guard legs → NO-REGRESSION; fewer with >=2 valid legs → REGRESSED (RQ →
  NO); <2 valid legs after retries → GUARD-INCOMPLETE (RQ capped at
  QUALIFIED).
- **leg INVALID** iff wall-clock > 1500 s (runner kills it) or snapshot
  `results.json` missing/unreadable; triggers a retry (rh: max 2 total,
  shared with NOT-MEASURABLE; guards: one retry each).
- **GATE-BREACH** iff `"distractor" in twin.relock_on` for any rh rep —
  `[identity-breach observed]`, RQ-E17 = NO regardless of rate.
- **RQ-E17** over valid rh reps (PASS or FAIL after retries; denom =
  count): `denom < 8` → NOT-MEASURABLE; FAILs = 0 → LIFTS → **YES**;
  FAILs = 1 → PARTIAL → **QUALIFIED**; FAILs >= 2 → NO-LIFT → **NO**.
  Then apply the breach and guard overrides above, in that order.
- The runner prints the per-leg verdicts, rg_fov, the rate, the band, and
  the RQ verdict — copy them into Results; if the runner's print and this
  README ever disagree, record both verbatim and mark `UNRULED`.

## Estimates (pre-registered; wrong estimates are content)

- Runtime: ctl ~13 min + 2–3 guards x ~6 min + 10 reps x ~13.5 min + up to
  2 retries + selfchecks ~= **190–230 min** (E16 actual: ~130 min for 9
  legs; guards are 75 s trials, E12 actual ~5 min/leg).
- ctl REPRODUCES: ~90% (reproduced E13, E14, E15-dd, E15-ro, E16).
- Guards both PASS: ~80% (E12 d3.0 and E14 mk-reg-3.0 both PASSed n=1;
  the lever adds a REGROUND-phase behaviour that E12-style runs rarely
  enter for long).
- Expected rate: **r = 9–10/10** (modal: LIFTS or PARTIAL with one
  PROPOSAL-MISS). The lever mechanically removes the rep-5 mode (rg_fov
  prediction: >= 0.95 on every rep, vs 0.203/0.507 in E16's FAILs); the
  rep-1 early-accept mode is out of scope and recurs at ~1/8 per draw.
- Identity-breach: < 5% (0 observed in ~19 gated decoy legs to date; the
  lever does not touch the accept path).
- Expected accept-time spread of PASS reps: ~74–95 s, possibly tighter
  than E16's 81.30–133.90 (a held FOV should shorten the wait for a clean
  post-separation box; car separates from t≈51).
- Risk worth naming: the blob chase during REGROUND could *overshoot* a
  slow (0.25 m/s) mover the way E12 saw pre-lock runaway at 3.5 — if so it
  shows up as verified-but-lost or HOLD-MISS FAILs and the answer is
  honestly NO-LIFT.

## Results (TBD — Opus fills this section only)

| leg | verdict | n_regr | gate_rej | size_rej | relock_on | closest_end | d_true_m | in_fov | rg_fov | relock_t_s |
|---|---|---|---|---|---|---|---|---|---|---|
| ctl | REPRODUCES | 5 | 0 | 36 | true,dist x3 | distractor | 26.69 | 0.447 | n/a | 46.20/59.22/64.79/113.59 |
| rh-1 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 53 | (empty) | distractor | 82.88 | 0.231 | 0.026 | (none) |
| rh-2 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 82.79 | 0.230 | 0.026 | (none) |
| rh-3 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 83.50 | 0.230 | 0.025 | (none) |
| rh-4 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 53 | (empty) | distractor | 82.13 | 0.228 | 0.025 | (none) |
| rh-5 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 83.62 | 0.230 | 0.025 | (none) |
| rh-6 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 81.63 | 0.230 | 0.025 | (none) |
| rh-7 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 82.34 | 0.228 | 0.025 | (none) |
| rh-8 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 81.20 | 0.228 | 0.025 | (none) |
| rh-9 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 53 | (empty) | distractor | 83.27 | 0.230 | 0.025 | (none) |
| rh-10 | FAIL no-relock [HOLD-MISS] | 1 | 0 | 52 | (empty) | distractor | 83.68 | 0.230 | 0.026 | (none) |

| leg | verdict | in_fov_frac | recovered | first_lock_s | n_regrounds | rg_fov |
|---|---|---|---|---|---|---|
| guard-a | PASS | 1.000 | True | 12.17 | 1 | 1.000 |
| guard-b | PASS | 1.000 | True | 9.86 | 1 | 1.000 |
| guard-c | not run (both a/b PASS) | — | — | — | — | — |

Config for every rh/ctl row: 15W mode 0 + jetson_clocks, image-size 1024,
app-tau 12, decoy-shade 215, `--speed 0.25 --twin decoy --duration-s 150
--loss-gate motion --dr pursuit --acquire-hold motion`; rh rows add
`--reground-gate mask --reground-hold chase` (ctl neither). Guard rows:
`--speed 3.0 --vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold
chase --acquire-delay 3.0 --reground-gate mask --reground-hold chase`.

- **Relock rate r:** **0 / 10** valid reps (0 retries, 0 exclusions — every
  rep produced exactly 1 reground). E16 baseline 6/8.
- **Guard regression verdict:** NO-REGRESSION (guard-a + guard-b both PASS at
  3.0 m/s, in_fov 1.000, recovered, rg_fov 1.000, first_lock 9.86-12.17 s).
  The lever is safe at the honest follow ceiling.
- **RQ-E17 verdict:** **NO** (0/10, >=2 FAILs -> NO-LIFT). No GATE-BREACH (no
  rep relocked the decoy; every rep never re-acquired at all -> relock_on
  empty). Guards PASS so no guard override. Runner print and README rule agree.
- **rg_fov spread:** 0.025-0.026 across all 10 reps -- the OPPOSITE of the
  predicted >=0.95. The lever did not keep the car in frame during REGROUND;
  it drove the drone almost entirely off it.
- **Accept-time spread (PASS reps):** n/a -- 0 PASS reps.
- **Estimate vs actual:** the design predicted r=9-10/10 (LIFTS) on the
  premise that a held FOV removes the rep-5 no-relock mode. **Inverted
  completely: r=0/10.** ctl REPRODUCES as expected; guards PASS as expected
  (~80% prior). The rg_fov prediction (>=0.95) was exactly backwards (0.025).
  Runtime ~200 min (est 190-230) -- on target. A wrong estimate is content:
  the mechanism assumption (chase = FOV-keeping) was false for this regime.
- **Deviations/surprises:** the load-bearing surprise. The blob-chase that
  HELPS pre-first-lock at 3.0 m/s (E11) is **actively harmful** when applied
  to REGROUND at 0.25 m/s. During a REGROUND blind phase the pursuit servos
  onto the nearest blob -- the 215 decoy, not the lost true car -- and drives
  the drone ~82 m away (final_d_true 81.2-83.7 m, vs E16's DR-coast 26.85 m
  worst case and 0.12-0.21 m on PASS). The true car leaves frame almost
  immediately (rg_fov 0.025, in_fov 0.23), so the VLM never sees it, never
  offers a clean box, the mask gate is never even consulted (gate_rejects 0,
  size_rejects ~52 -- all off-target off-road boxes). E16's *passive*
  DR-coast (hold last velocity) is strictly better here because it at least
  keeps the drone near the true car's path; the *active* chase chases the
  wrong thing. This is a clean directional negative: E11's chase-hold does
  NOT transfer from pre-lock acquisition to post-loss re-acquisition -- the
  failure mode inverts because pre-lock there is one blob (the target), but
  in REGROUND the decoy is the dominant blob. The E16 6/8 stands as the best
  REGROUND policy; `--reground-hold chase` is rejected.

## Proof clips (Opus: 2-3, committed under `proof/`, mechanical picks)

Copy (or ffmpeg-trim to roughly t 40–125 s; guards full length) from
`runs/<leg>/trial.mp4`; caption each with the leg's config and verdict:

Clip 1's pre-registered pick (latest-accept PASS rep) is unsatisfiable — there
were **0 PASS reps**. Substituted the load-bearing negative (the runaway FAIL)
and noted it here; the other two picks stand.

1. `proof/e17-hold-runaway.mp4` — rh-1, the negative result: with
   `--reground-hold chase` the REGROUND blob-chase servos onto the 215 decoy,
   not the lost true car, and drives the drone ~82.9 m off (rg_fov 0.026, the
   true car leaves frame at once, no relock, FAIL [HOLD-MISS]). This is the
   lever backfiring — the proof it did not work. (Substitutes the unsatisfiable
   "latest PASS" clip 1.)
2. `proof/e17-guard-ceiling.mp4` — guard-a PASS: the full stack (chase acquire
   + mask gate + reground-chase) at the 3.0 m/s honest ceiling, in_fov 1.000,
   locks at 12.17 s — the lever is safe at follow speed, so the regression is
   specific to the slow-mover REGROUND regime.
3. `proof/e17-ctl-wronglock.mp4` — ctl (no gate, no hold): E16's baseline
   regime, wrong-locks the decoy and ends 26.69 m from true. Contrast for the
   runaway clip — passive DR-coast stays ~27 m off, the active chase goes ~83 m
   off; both fail here but the lever makes it strictly worse.

## Ledger updates on completion (Opus)

- `docs/results/part4-end-to-end.md`: one row per leg (config in every
  row) plus the rate line and the guard verdict.
- `docs/questions/part4-end-to-end.md`: RQ-E17 + one-line verdict with the
  rate as a number vs the 6/8 baseline (e.g. "r=10/10 LIFTS vs 6/8").
- `docs/decisions/part4-end-to-end.md`: reground-chase chosen over the E3b
  appearance gate (0 breaches in 8 — identity already safe), accept-
  hysteresis, 3.0 m/s decoy characterization, longer duration, and a
  re-run baseline arm — rationale and what was given up in "Rejected
  alternatives" above; also record the rg_fov mechanism finding (audit
  findings 1–3) — it is the evidence the lever was designed against.
- No new SOURCES (no new external artifact).
- Set Status here to COMPLETE with a Madrid wall-clock timestamp; commit
  snapshots under `runs/`, `raw/matrix.log`, proof clips; leave
  `git status` clean. Merge per the loop protocol. This is the loop's
  final cycle (budget 1 → 0): after merging, park the loop.
