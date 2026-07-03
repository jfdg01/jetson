# E14 mask-identity: bind the REGROUND identity gate to the SAM2 latch, not the box crop

**Pre-registered:** 2026-07-03T17:52Z (Madrid wall clock)
**Status:** COMPLETE 2026-07-03T18:18Z (Madrid wall clock) — RQ-E14 = **YES**. The
mask-bound median gate closes the identity hole 3/3 (mk-decoy final_d_true 0.21 m) with
zero regression (0.5 relock, 3.0 ceiling, E9 retarget all PASS). First identity cue to
survive the blend box; the win path is reject-until-separated, not first-frame accept.
**Roles:** design + patches by Fable (already committed on this branch); Opus runs the
matrix and fills Results only — do NOT re-patch code.
**Rig:** host 3090 (SITL + renderer + SAM2 @1024) + Jetson Orin Nano (VLM Qwen2-VL-2B
Q8_0, self-boots per trial over `ssh jetson`). Jetson power mode: 15W (mode 0) +
`jetson_clocks` — there is NO MAXN on this board. No `--remote-carry` anywhere in this
matrix (the mask gate is local-carry only, enforced in code).

## RQ-E14

Does binding the REGROUND identity gate to the **instance SAM2 actually latches**
(per-channel median BGR over the frame-0 mask of a throwaway StreamCarry init on the
proposed box, L-inf <= tau 12 vs the template bound at NL grounding) defeat the two-car
blend box that defeated E13's crop gate — i.e. does the 215-shade decoy leg now end the
flight on the TRUE car, 3/3, with no regression on the 0.5 m/s relock, the 3.0 m/s
ceiling, or E9 retarget?

- **YES** iff smoke PASS AND ctl-decoy REPRODUCES AND mk-decoy-{a,b,c} all PASS AND
  mk-reg-0.5, mk-reg-3.0, mk-rt all PASS (rules below, all mechanical).
- **NO** iff smoke PASS AND ctl-decoy REPRODUCES AND any mk-decoy leg FAILs or any
  regression leg FAILs.
- **NOT-MEASURABLE** iff smoke fails its precondition or ctl-decoy does not reproduce.

## Context: the identity hole and why the mask

Three cues have now failed at REGROUND because none is bound to the tracked *instance*:
size (E3, wrong-lock 3/3), motion (E7, defeated by drive-through co-location), and
E13's crop color gate. E13's failure mode (audited from
`../2026-07-03-identity-gate/runs/ap-decoy-{a,b,c}/results.json`, raw acquire_logs):
as the true car emerges from under the bridge next to the parked 215 decoy, the VLM
draws one **blend box spanning both cars** (e.g. `[268.8, 0, 428.8, 441.6]` accepted at
t=69.5 in ap-decoy-a, identical pattern 3/3). The crop's brightest-quartile statistic
asks "is the template color PRESENT in this box?" — the emerging true car's 245 pixels
answer yes — while SAM2 inits on that box and latches the decoy it centers on. All
three ap-decoy legs ended `closest_at_end=distractor, final_d_true ~26.5 m`. The E13
audit also confirmed this is structural, not a shade-215 artifact: E7's shade-245
wrong-lock accepts were the same giant two-car boxes.

**E14 lever:** stop judging the crop; judge the latch. On a size-passing REGROUND
resolve, run the exact StreamCarry init the accept would run (same submit-frame bytes
via the q=95 jpg path, same box, same weights — so the verified instance IS the latched
instance), and take the per-channel **median** BGR over its frame-0 mask. The median is
a majority vote over what SAM2 actually latched: a majority-decoy latch reads 215 even
with true-car pixels inside the mask, and the ~16% dark windshield never outvotes the
body. (E13's brightest-quartile would re-admit blends at >=25% true-pixel content if
applied to the mask; the median needs >50%.)

**Design-time probe (2026-07-03, host 3090, scratchpad-only script):** recreated the
E13 emergence geometry (bridge N=(10,20), 215 decoy parked 2 m past the north edge,
blend box = visible true strip + full decoy). Result: at every emergence 0.5–4.0 m the
SAM2 init on the blend box latched a majority-decoy mask whose median was **exactly
[215, 215, 215]** (reject at tau 12 vs the 245 template) even with up to ~65%
true-region pixels in the mask; a true-strip-only box read 245.0 (accept — the relock
win path); a decoy-tight box read 215.0 (reject). Init cost 36–51 ms warm (334 ms first
call) — noise against the ~2.3 s VLM draw cadence. The premise is validated; what the
matrix tests is the closed-loop consequence (does rejecting blends until the true car
separates actually end the flight on the true car).

**Rejected alternatives** (seed for DECISIONS):
- *Geometry blend-box pre-filter* (reject REGROUND boxes much larger than the last
  known target box before consulting any descriptor): a fourth instance-blind global
  cue; stacks another heuristic with its own tunable instead of fixing the binding —
  and a legitimate loose-but-correct box would be rejected with no path to accept.
- *CLIP crop embedding* (E13's named alternative): being crop-based it fails the blend
  box for the same reason the color crop did; E13 already rejected it on cost grounds
  (~10x descriptor cost). The blend diagnosis strengthens that rejection.

## Code changes (already committed on this branch — Opus: do NOT edit these files)

All in `../2026-07-01-temporal-acquire-carry/`, all **off by default** (`--reground-gate
none`); every E2–E13 configuration is bit-identical unless `--reground-gate mask` is
passed. Software: same stack as E13 (torch/sam2/transformers pins in
`requirements-ft.lock.txt`; SAM2.1-hiera-tiny; Qwen2-VL-2B Q8_0 on the Jetson).

- `stream_carry.py`: `StreamCarry.__init__` now captures `self.init_mask` (frame-0
  video-res bool mask) from `add_new_points_or_box`, whose return value was previously
  discarded — capture-only, every prior caller is bit-identical.
- `phase3_sitl.py`:
  - `mask_descriptor(frame_bgr, mask)`: per-channel median BGR over mask pixels; `None`
    on a degenerate (<16 px) mask.
  - `--reground-gate mask`: on a REGROUND resolve (never ACQUIRE/RETARGET; consulted
    only after the size prior passes, same seam as E7/E13), init a throwaway
    StreamCarry on (submit frame, box), accept iff the mask median is within
    `--app-tau` (default 12.0) L-inf of the template. Fail-open while no template is
    bound. Rejects surface as reason `"gate"` in `acquire_log` and count in
    `n_reground_gate_rejects`; the template lands in `app_template` (results.json) —
    same fields as E13.
  - Template binds at NL grounding time from `sm.carry.init_mask` (the instance the
    accepted carry actually latched), voids on retarget and rebinds at the switch
    accept — same lifecycle as E13's crop template.
  - `mask` + `--remote-carry` is refused at startup (the gate verifies with the host
    predictor; the 3b remote path has no local predictor).
  - Selfcheck grew an E14 block (GPU-free): on a rendered two-car scene the E13 crop
    stat ACCEPTS the wide blend box (dist 0) while the mask median over the two-car
    latch region reads 215 and REJECTS — the exact hole, reproduced and closed in one
    assert pair; plus true/decoy/blue-escort/degenerate mask cases.

Verified by me before commit: `phase3_sitl.py --selfcheck` PASS (E4–E14 asserts),
`sitl_cam.py` selfcheck PASS.

## Run matrix (Opus: run exactly this)

Preconditions: host 3090 free; `ssh jetson` up; Jetson at 15W mode 0 + jetson_clocks
(`ssh jetson sudo nvpmodel -q` to confirm; `sudo nvpmodel -m 0 && sudo jetson_clocks`
are NOPASSWD). Then, from the repo root:

```bash
.venv-ft/bin/python experiments/2026-07-03-mask-identity/run_e14.py 2>&1 | tee experiments/2026-07-03-mask-identity/raw/run_e14.log
```

That is the whole matrix. The runner executes, in order:

1. `e14_mask_smoke.py` — precondition gate (details in its docstring): VLM
   decoy-capture >= 7/10 AND real-latch descriptor separability (all true dists <= 12,
   all decoy dists > 12) AND all 4 blend-emergence probes REJECTED AND the true-strip
   probe ACCEPTED. On fail: legs are skipped, RQ-E14 = NOT-MEASURABLE, record why.
2. Seven 150 s / 75 s SITL legs (labels below). `phase3_sitl.py` **clobbers**
   `raw/phase3a-sitl/trial-<speed>ms.{csv,mp4}` and `runs/phase3a-sitl/results.json`
   on every run (the E2–E13 gotcha); the runner snapshots each leg into
   `runs/<label>/{results.json,trial.csv,trial.mp4}` before the next leg — always read
   the snapshots, never the shared files.

| leg | flags (via `phase3_sitl.py`) | purpose |
|---|---|---|
| ctl-decoy | `--speed 0.25 --twin decoy --decoy-shade 215 --duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion` | wrong-lock still reproduces with no gate |
| mk-decoy-a/b/c | ctl flags + `--reground-gate mask` | the fix, 3 repeats |
| mk-reg-0.5 | `--speed 0.5 --loss-gate motion --dr pursuit --acquire-hold motion --reground-gate mask` | plain relock regression |
| mk-reg-3.0 | `--speed 3.0 --vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold chase --acquire-delay 3.0 --reground-gate mask` | E12 honest-ceiling regression |
| mk-rt | `--speed 0.5 --twin escort --loss-gate motion --dr pursuit --acquire-hold motion --retarget-t 50 --reground-gate mask` | E9 retarget regression (template rebind) |

The decoy legs are single-car-visible during occlusion by construction (decoy parked
2 m past the bridge north edge, same lane); identical geometry to E3/E7/E13.

## Verdict rules (mechanical — Opus does NOT deliberate)

`run_e14.py` prints these verbatim per leg; the README rule and the code are the same
rule. All fields from the leg's snapshotted `results.json` `trial` object.

- **ctl-decoy REPRODUCES** iff `n_regrounds >= 1 AND twin.closest_at_end ==
  "distractor" AND twin.final_d_true_m >= 10.0`. End-state attribution on purpose:
  E13's `relock_on[0] == "distractor"` rule broke on this exact leg when a transient
  early reground caught the still-visible true car (E13 ctl: `relock_on[0]="true"` yet
  the flight ended on the decoy at `final_d_true=31.5`). `relock_on` is recorded but
  not consulted. (Distractor proximity is deliberately not required: E13 ctl ended
  6.9 m from the decoy after it drifted; the escape distance is the honest signal.)
- **mk-decoy-{a,b,c} PASS** iff `n_regrounds >= 1` AND `twin.relock_on` non-empty AND
  `twin.relock_on[-1] == "true"` AND `twin.closest_at_end == "true"` AND
  `twin.final_d_true_m <= 2.0` AND `in_fov_frac >= 0.90`. If `n_regrounds == 0`:
  NOT-MEASURABLE (confident-latch — record, and if any repeat hits it, note whether
  E13's legs did too; they did not). If `relock_on` empty: FAIL, subtype
  *identity-preserving no-relock* (gate rejects everything, target never reacquired) —
  report `n_reground_gate_rejects` with it. A last-relock-true leg that then loses the
  car (`final_d_true > 2.0` or `in_fov_frac < 0.90`): FAIL, subtype *verified-but-lost*.
- **mk-reg-0.5, mk-reg-3.0 PASS** iff `in_fov_frac >= 0.90 AND
  recovered_after_occlusion == true` (same bar E10–E13 used).
- **mk-rt PASS** iff all seven E9 criteria: `retarget.switch_walls_s[0] <= 15.0`,
  `retarget.switch_on[-1] == "distractor"`, `twin.closest_at_end == "distractor"`,
  `twin.final_d_dist_m <= 2.0`, `retarget.frac_box_closer_dist_post >= 0.80`,
  `retarget.dist_in_fov_frac_post >= 0.90`, `in_fov_frac >= 0.90`.
- **RQ-E14** per the YES/NO/NOT-MEASURABLE block at the top. A single FAILed mk-decoy
  repeat is a NO (the claim is reliability, 3/3), but record the split — a 2/3 is
  thesis content about where the residual failure lives.

## Abort / invalid criteria

- Leg exceeds 1500 s wall (runner timeout): leg INVALID, snapshot whatever exists,
  continue the matrix.
- Missing/unreadable snapshot `results.json`: leg INVALID. Any INVALID leg: re-run that
  leg ONCE (rig flake happens: SITL boot, ssh drop); a second INVALID stands and the
  RQ verdict is computed without it (a missing mk-decoy repeat blocks YES).
- Smoke PRECONDITION-FAIL or ctl-decoy NOT-REPRODUCED: stop interpreting the mk-decoy
  legs; RQ-E14 = NOT-MEASURABLE, document what changed vs E13 (this would be a
  stale-assumption find, itself content).
- Do not tune `--app-tau`, shades, or geometry mid-run. Any deviation = new
  pre-registration.

## Estimates (marked as estimates)

- Smoke ~4–8 min (10 VLM draws + Jetson boot; ~20 SAM2 inits are seconds). Matrix
  total ~90–120 min (E13 actual was ~110 min for the same shape).
- Smoke PASS probability ~85% (the probe already validated the SAM2 legs of it; the
  VLM decoy-capture repeated E13's 10/10 setup).
- mk-decoy 3/3 ~50–60%: the gate side is near-certain to reject the blends (probe),
  the uncertainty is the win path — whether, post-rejection, the VLM produces a
  true-car box (strip or separated) before the 150 s ends, and whether the E4
  replay/DR keeps the copter close enough. Failure would most likely be
  *identity-preserving no-relock*, which is still the E13-predicted "correct rejects,
  no accept" half-win and pins the next lever (proposal diversity, not verification).
- Overall RQ-E14 YES ~40–50%.
- Gate cost: ~40 ms per consulted REGROUND resolve (probe) — no measurable effect on
  the 2.3 s draw cadence; regressions expected unaffected (gate is consulted only on
  REGROUND, and only after size passes).

## Results (TBD — Opus fills after the run)

| leg | verdict | n_regrounds | gate rejects | relock_on | closest_at_end | final_d_true_m | in_fov_frac | notes |
|---|---|---|---|---|---|---|---|---|
| smoke | PASS | — | — | — | — | — | — | decoy_hits 10/10; true_dists all 0.0, decoy_dists all 30.0; 4 blend probes (0.5-2.0 m) median [215,215,215] all REJECT, true-strip (3.0 m) median [245,245,245] ACCEPT |
| ctl-decoy | REPRODUCES | 6 | 0 (no gate) | ['true','distractor','distractor','distractor','distractor'] | distractor | 26.68 | 0.4467 | no-gate control accepts blend box at t=46.3, drifts onto decoy; final_d_dist 1.95 m |
| mk-decoy-a | PASS | 1 | 13 | ['true'] | true | 0.21 | 1.0 | template [245,245,245]; rejects blends t46.3-81.6, accepts clean true box t86.25 |
| mk-decoy-b | PASS | 1 | 13 | ['true'] | true | 0.21 | 1.0 | template [245,245,245]; identical reject-until-separated path |
| mk-decoy-c | PASS | 1 | 11 | ['true'] | true | 0.22 | 1.0 | template [245,245,245] |
| mk-reg-0.5 | PASS | 1 | 0 | — | — | — | 1.0 | recovered_after_occlusion=true; single-car scene, gate never had to reject |
| mk-reg-3.0 | PASS | 1 | 0 | — | — | — | 1.0 | recovered_after_occlusion=true; E12 honest 3.0 m/s ceiling holds with gate on |
| mk-rt | PASS | 1 | 0 | — | distractor | — | 1.0 | E9 7/7 checks; template rebinds to blue escort [230,90,40] on retarget; final_d_dist 0.42 m |

**RQ-E14 verdict: YES.** smoke PASS AND ctl-decoy REPRODUCES AND mk-decoy-{a,b,c} all
PASS (3/3, final_d_true 0.21-0.22 m) AND all three regression legs PASS. The mask-bound
median gate is the first identity cue (after size E3, motion E7, crop-color E13) to
defeat the two-car blend box. Mechanism confirmed from the acquire_log: the gate rejects
the blend/decoy boxes (11-13 rejects/leg) while the true car is co-located with the
decoy, then accepts the first clean true-car box once they separate (t=86.25 in
mk-decoy-a) and SAM2 locks the true car (relock_on=['true'], ends 0.21 m from true,
24.5 m from the decoy). Zero regression: the gate is off by default, consulted only on
REGROUND after the size prior, and the single-car regression legs recorded 0 rejects.

## Estimate vs actual

- Runtime: est ~90-120 min; **actual ~110 min** (matched E13). On estimate.
- smoke PASS: est ~85%; **actual PASS** (decoy_hits 10/10, all 4 blend probes rejected,
  true-strip accepted). The design-time GPU probe held exactly — blend median [215,215,215].
- mk-decoy 3/3: est ~50-60%; **actual 3/3 PASS**, at the top of the range. The predicted
  risk (*identity-preserving no-relock* — gate rejects everything and the VLM never draws
  an acceptable true box) did NOT materialize: in all three repeats the VLM produced a
  clean separated true-car box at ~t86 (well within 150 s) after the cars physically
  separated, and the E4 replay/DR kept the copter close enough to relock (final_d_true
  ~0.21 m). The reject-until-separated dynamic worked as designed.
- Overall RQ-E14 YES: est ~40-50%; **actual YES**. The uncertainty was entirely on the
  win path (whether a clean true box would appear post-rejection); it did, reliably.
- Gate cost: est ~40 ms/consult; not separately instrumented this run, but no leg
  timed out and the draw cadence was unaffected (consistent with the probe).

## Proof clips (Opus: 2–3, committed under `proof/`)

1. `proof/e14-ctl-decoy-wronglock.mp4` (ctl-decoy, t42-97) — **the failing behaviour, no
   gate.** The no-gate control accepts the two-car blend box as the true car emerges next
   to the 215 decoy (t=46.3), SAM2 latches the decoy, and the copter drifts onto the
   wrong car; ends 26.68 m from the true car, 1.95 m from the decoy. This is the E3/E7/E13
   identity hole, reproduced.
2. `proof/e14-mk-decoy-relock.mp4` (mk-decoy-a, t44-120) — **the fix.** The mask-bound
   median gate rejects every blend/decoy box while the cars are co-located (13 rejects,
   t46.3-81.6; the box straddles both cars so SAM2's latch is majority-decoy -> median
   215 -> reject vs the 245 template), then accepts the first clean true-car box once the
   cars separate (t=86.25) and locks the true car (ends 0.21 m from true, 24.5 m from the
   decoy). Reject-until-separated, not first-frame accept.
3. `proof/e14-reg-3.0.mp4` (mk-reg-3.0, t0-40) — **no regression.** The E12 honest
   3.0 m/s follow ceiling holds with the gate on (in_fov 1.0, recovered after occlusion);
   the gate is consulted only on REGROUND after the size prior, so the plain follow path
   is untouched.

## Closeout checklist (Opus)

1. Fill Results + RQ verdict + estimate-vs-actual divergences here; set Status to
   COMPLETE with a Madrid wall-clock timestamp.
2. Append the RESULTS row(s) to `docs/results/part4-end-to-end.md` (per-leg one-liners,
   config in every row: 15W mode 0 + jetson_clocks, image-size 1024, app-tau 12,
   decoy-shade 215).
3. Append RQ-E14 + one-line verdict to `docs/questions/part4-end-to-end.md` (NOT the
   root QUESTIONS.md).
4. Append the DECISIONS entry to `docs/decisions/part4-end-to-end.md`: mask-bound
   median gate chosen over (a) geometry blend-box pre-filter, (b) CLIP crop embedding —
   rationale in "Rejected alternatives" above; what was given up: ~40 ms per REGROUND
   consult + local-carry-only (3b remote path unported).
5. No new external sources expected (SAM2/Qwen already in SOURCES.md).
6. Commit everything on this branch (snapshots under `runs/`, `raw/run_e14.log`,
   proof clips); leave `git status` clean. Merge per the loop protocol.
