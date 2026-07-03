# E13 identity-gate: appearance-template gate on REGROUND acceptance

**Pre-registered:** 2026-07-03T17:00Z (Madrid wall-clock)
**Status:** COMPLETE 2026-07-03T18:20Z. **RQ-E13 = NO** — the appearance-color
gate does NOT close the identity hole (ap-decoy 0/3; the gate fires 14-26
rejects but a blend box passes and wrong-locks 3/3). All regression legs PASS
(no plain-relock, ceiling, or retarget regression). Smoke PASS 10/10.
**Division of labor:** design + patches by Fable; Opus runs the matrix and fills
Results only — do NOT re-patch code.

## RQ-E13

Does an appearance-template gate on REGROUND acceptance — bind a body-color
descriptor to the target at NL grounding time, then accept a size-passing
reground box only if its crop descriptor matches within tau — convert the E3-S2
decoy wrong-lock into a relock on the true car (3/3 at 0.25 m/s, 150 s, decoy
shade 215), without regressing plain-occlusion relock at 0.5 m/s, the
chase-validated 3.0 m/s hard-spawn ceiling leg (E12 d3.0 config), or the E9
retarget switch?

## Context

The identity hole (open since E3, 2026-07-02): REGROUND wrong-locks a parked
same-class decoy 2 m past the bridge north edge, 3/3. The size prior is
identity-blind. Two geometry-only levers already failed on it:
- **E7 motion gate** (`--reground-gate motion`): fires (6–8 rejects/leg) but the
  copter drives through the decoy's position, so a decoy box eventually sits on
  the copter's own motion sweep and passes. Wrong-lock 3/3 unchanged.
- **E8 more time** (`--duration-s 150`): after the wrong-lock the copter parks
  on the decoy; by the next loss-gate reground the true car is ~26.5 m
  downstream and out of FOV — nothing true-car to reacquire. E8's conclusion:
  "geometry-only correction has a ceiling; search or identity is required."

This experiment is the identity arm. It must act at the FIRST reground (before
the copter ever parks on the decoy), which a reground acceptance gate does by
construction.

### Audit (pre-registration, 2026-07-03)

**(a) Is the wrong-lock still reproducible on current code?** Yes. E7's
`ctl-decoy` and E8's control were both run 2026-07-03 on the current lever
stack (`--loss-gate motion --dr pursuit --acquire-hold motion`) and wrong-lock
every time (E7 ctl: `relock_on ["distractor","distractor"]`; E8 ctl-long: 4
wrong relocks). E9–E12 patches are all default-off flags with bit-identical
defaults (each README's regression legs verify it). The matrix below
re-controls anyway (`ctl-decoy`), because the decoy shade changes (next point).

**(b) Can an appearance cue discriminate the two cars at all?** Not in the
unmodified rig: `sitl_cam.render()` draws the decoy with the identical polygon
and color by construction (`distractor_color=(245,245,245)` default), which is
exactly why E7 rejected CLIP "on validity, not cost". **Pre-registered
decision: option (i) — give the decoy a discriminable same-class difference.**
`--decoy-shade 215` renders the decoy body grey (215,215,215) vs the true
car's (245,245,245). Fairness case:
- A byte-identical twin is unsolvable for ANY appearance mechanism,
  information-theoretically — it stays recorded as a theoretical bound of the
  approach, not as a target this experiment claims.
- Real same-class distractors ("another white car") are never byte-identical;
  a slightly-dimmer white car is the realistic hard case, and 215 is still
  emphatically "a white car" in this palette (road dash = 200, parapet = 140,
  asphalt = 70).
- The premise is **checked, not assumed**: the smoke precondition requires the
  VLM to still box the 215 decoy as "the white car" when it is the only car in
  frame (the wrong-lock situation — the wrong-lock decision happens while the
  true car is occluded), and `ctl-decoy` must still wrong-lock at shade 215 for
  the treatment to be attributable (see verdict rules).

**(c) What does the VLM actually propose during the reground window?** E7's
`mg-decoy-a` acquire log (audited): from reground (t≈34.8) to the wrong-lock
accept (t≈69.3), every proposal tracks the decoy / a merged two-car region at
the top of the frame; the wrong-lock accepts in E7 are giant boxes spanning
BOTH cars (e.g. `[249.6, 0.0, 422.4, 441.6]` ≈ 172x442 px vs a ~113x252 px
car). Three design consequences, baked in:
1. The gate must reject **blend boxes** (a box over both cars), not just clean
   decoy boxes — tau 12 is under half the 30-unit gap, so a blend passes only
   when it is >~60% true-car body.
2. The **win path is the decoy leaving the frame**: under `--dr pursuit` the
   copter dead-reckons north with the true car while the gate keeps it
   unlatched, and the parked decoy exits the frame bottom at t≈72 (copter
   N ≥ ~18.5, decoy at N=12.75, half-footprint 3.8 m). At E3/E7's 75 s the
   trial ends right there, so decoy legs run `--duration-s 150` (E8's
   committed knob): ~75 s of decoy-free frames for a clean true-car accept and
   a long post-relock follow to measure.
3. "Gate correctly rejects everything and never relocks" is pre-registered as
   a **distinct FAIL subtype** (identity-preserving no-relock): fail-safe
   behavior, thesis content, but NO for the RQ.

## Design

**Gate** (`--reground-gate appearance`, off by default — E7/E11 flag
discipline, default path bit-identical):
- **Descriptor** = mean BGR of the crop's brightest quartile, ranked by
  max-channel value (`appearance_descriptor()` in `phase3_sitl.py`). Bright
  quartile = car-body pixels (body outshines road/grass; dark windshield drops
  out), so it survives loose boxes and partially-emerged cars. Max-channel
  ranking (not grey luminance) keeps it valid for saturated bodies: the blue
  escort's B=230 outranks grass, which would beat the blue car in luminance.
- **Template** bound at NL grounding time: at the first ACQUIRE accept, the
  descriptor of the accepted box's crop on its own submit frame (the box is
  only valid on the frame the VLM drew it on — E4's lesson, reused). Frozen
  for the rest of the trial; on RETARGET the template is voided and rebound at
  the switch accept, so the gate never blocks a newly commanded target.
  REGROUND accepts never rebind — reground identity is what the gate judges.
- **Accept** iff L-inf BGR distance ≤ `--app-tau` (default 12.0). Measured
  distances (offline, oracle crops over the 10 smoke poses): true car 0.0,
  215-decoy 30.0, all poses. tau=12 also rejects two-car blend boxes up to
  ~60% true-car content while a pure true-car crop sits at ~0.
- Gate consulted **only on REGROUND resolves** (SM behavior committed since
  E7, selfcheck-enforced): never on the first ACQUIRE (nothing to compare
  yet), never on RETARGET (a new identity claim, not a continuity claim).

**Rejected alternative (DECISIONS seed):** CLIP crop-embedding similarity.
Rejected on cost AND necessity, not validity: an extra model co-resident on
the 8 GB Jetson (or a host dependency), ~100s-of-ms per check, against a
discriminandum this rig can only render as a color/shape difference — a
3-channel color statistic already separates it 30-to-0 at zero dependencies
and microseconds per check. This is the laziest gate that actually
discriminates; CLIP earns a slot only when the rig renders distractors that
differ in ways a color statistic cannot see (texture/shape at same color).
Also rejected: testing "search" (spiral reacquire) instead — E8 showed
identity-at-first-reground is the binding constraint; search without identity
re-locks whatever it finds first.

## Code changes (already committed — Opus: do NOT edit these files)

All in `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`
(`sitl_cam.py` untouched — `distractor_color` was already parameterized by E9):
- `appearance_descriptor()` module function (descriptor above).
- `--reground-gate appearance` closure in `run_trial` + frozen-template
  capture at NL-grounding accepts + template void on retarget.
- `--decoy-shade` (int, default 245 = E3's byte-identical twin, bit-identical
  E2–E12 default; must stay >200: road-dash grey and the sitl_cam selfcheck
  blob threshold live there) and `--app-tau` (float, default 12.0). Both in
  the run manifest cfg; `app_template` recorded in results.json.
- acquire_log reject-reason literal for reground-gate rejections renamed
  `"motion"` → `"gate"` (it now covers two gate types; E7's recorded artifacts
  keep the old spelling — do not re-interpret them).
- Selfcheck extended (E13 block: descriptor values on rendered white car /
  215-decoy / blue escort, gap ≥ 25, degenerate-crop None; reason-literal
  asserts updated). Run at design time 2026-07-03, host, `.venv-ft`:
  `phase3_sitl.py --selfcheck` PASS, `sitl_cam.py` selfcheck PASS.

New files in this campaign dir:
- `e13_appearance_smoke.py` — precondition smoke (decoy-capture + descriptor
  separability + descriptive two-car preference), pattern of E9's color smoke.
- `run_e13.py` — matrix runner: smoke gate, 7 legs, per-leg snapshot +
  mechanical verdict print.

No installs needed (numpy/opencv already in `.venv-ft`).

## Run matrix (Opus runs this)

Rig: host 3090 (SITL + renderer + SAM2 carry @1024) + Jetson Orin Nano over
`ssh jetson`. `phase3_sitl.py` **self-boots both** the ArduCopter SITL and the
Jetson Qwen2-VL-2B Q8_0 llama-server per trial (log line "[3] booting Jetson
q8_0 server..."); do NOT pass `--remote-carry`. **Power mode: 15 W (mode 0) +
jetson_clocks** — this board has no MAXN_SUPER (see
`docs/decisions/part2-rebuild.md`). Pre-flight once:
`ssh jetson sudo nvpmodel -q` (expect mode 0) and `ssh jetson sudo jetson_clocks`.
Software versions are auto-captured per run by the manifest, as E2–E12.

One command runs everything (smoke + 7 legs, snapshots each into
`runs/<label>/`):

```bash
cd /home/gara/jetson
echo "$(date -Is) EXEC-START identity-gate" >> .claude/loop.log
.venv-ft/bin/python experiments/2026-07-03-identity-gate/run_e13.py 2>&1 | tee experiments/2026-07-03-identity-gate/raw/matrix.log
```

(`mkdir -p experiments/2026-07-03-identity-gate/raw` first if tee complains.)

| leg | flags | purpose |
|---|---|---|
| smoke | `e13_appearance_smoke.py` (in the runner) | **precondition gate** — VLM still boxes the 215 decoy as "the white car" alone in frame (≥7/10) AND oracle-crop descriptor separability at tau (all true ≤12, all decoy >12); also records two-car preference (descriptive) |
| ctl-decoy | `--speed 0.25 --twin decoy --decoy-shade 215 --duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion` | **control** — the E3-S2/E7/E8 wrong-lock must reproduce at shade 215 for the treatment to be attributable |
| ap-decoy-a/b/c | ctl flags + `--reground-gate appearance` | **decision** — identity gate on, 3 independent runs |
| ap-reg-0.5 | `--speed 0.5 --loss-gate motion --dr pursuit --acquire-hold motion --reground-gate appearance` | regression: plain-scene occlusion relock (E7 mg-reg-0.5 analog) |
| ap-reg-3.0 | `--speed 3.0 --vmax 4.0 --loss-gate motion --dr pursuit --acquire-hold chase --acquire-delay 3.0 --reground-gate appearance` | regression: the honest 3.0 m/s ceiling config (E12 d3.0) with the gate on |
| ap-rt | `--speed 0.5 --twin escort --loss-gate motion --dr pursuit --acquire-hold motion --retarget-t 50 --reground-gate appearance` | regression: E9 retarget switch — gate must not block the new target (template voids on retarget; gate skipped on RETARGET resolves by SM construction) |

Gotchas (baked into the runner, listed so you can recognize them):
- `phase3_sitl.py` clobbers `raw/phase3a-sitl/trial-<v>ms.{csv,mp4}` and
  `runs/phase3a-sitl/results.json` (in the 2026-07-01 dir) on every run — the
  runner snapshots per leg immediately into `runs/<label>/{results.json,
  trial.csv,trial.mp4}`; the raw filename depends on the speed
  (`trial-0.25ms.*`, `trial-0.5ms.*`, `trial-3.0ms.*`).
- A leg is killed at 25 min (150 s legs + boots; E10–E12 actuals 3–5 min/leg).
- If SITL dies mid-matrix, re-run the whole matrix rather than surgering legs;
  `run_e13.py` re-executes everything including the smoke.
- Annotated video for proof clips is recorded automatically every leg and
  snapshotted to `runs/<label>/trial.mp4` — do not delete these.

Expected wall time: smoke ~5 min (20 VLM draws + boot), legs ~4 min (75 s) /
~5.5 min (150 s) each — **~40–50 min total** (estimate).

## Verdict rules (mechanical — `run_e13.py` prints these per leg)

- **Smoke:** PASS iff `decoy_hits_of_10 >= 7` AND `max(true_dists) <= 12` AND
  `min(decoy_dists) > 12`. FAIL → runner exits 1, legs skipped, record
  **PRECONDITION-FAIL** (if decoy-capture failed: the shade change alone broke
  the wrong-lock premise → RQ-E13 NOT-MEASURABLE at shade 215; that is a
  finding, record it).
- **Any decoy leg with `n_regrounds == 0`:** "not measurable — confident-latch"
  (E3 amendment): carry never released, the gate was never consulted. Neither
  PASS nor FAIL for that leg; if it is an ap-decoy leg, RQ-E13 cannot be YES.
- **ctl-decoy (attribution):** reproduces iff `twin.relock_on` is non-empty
  and its first entry == `"distractor"`. If instead it relocks true (or never
  regrounds), the 215 decoy no longer captures REGROUND → **RQ-E13
  NOT-MEASURABLE** (premise broken); still run/record all legs.
- **ap-decoy-a/b/c, each:** PASS iff ALL of
  `twin.relock_on` non-empty AND `twin.relock_on[-1] == "true"` AND
  `twin.closest_at_end == "true"` AND `twin.final_d_true_m <= 2.0` AND
  `in_fov_frac >= 0.90`.
  Distinct FAIL subtype to label explicitly: **identity-preserving no-relock**
  (`n_regrounds >= 1`, `relock_on` empty, `n_reground_gate_rejects` counting
  up) — the gate rejected everything and the trial ended blind.
- **ap-reg-0.5, ap-reg-3.0:** PASS iff `in_fov_frac >= 0.90` AND
  `recovered_after_occlusion == true` (the standing per-leg gate, E2–E12).
- **ap-rt:** PASS iff all 7 E9 criteria: `retarget.switch_walls_s[0] <= 15.0`;
  `retarget.switch_on[-1] == "distractor"`; `twin.closest_at_end ==
  "distractor"`; `twin.final_d_dist_m <= 2.0`;
  `retarget.frac_box_closer_dist_post >= 0.80`;
  `retarget.dist_in_fov_frac_post >= 0.90`; `in_fov_frac >= 0.90`.
- **RQ-E13 = YES** iff smoke PASS AND ctl-decoy reproduces the wrong-lock AND
  ap-decoy 3/3 PASS AND ap-reg-0.5 PASS AND ap-reg-3.0 PASS AND ap-rt PASS.
  **NO** if any ap-leg fails with the control reproducing. **NOT-MEASURABLE**
  if smoke decoy-capture fails or ctl-decoy does not reproduce.
- **Abort/INVALID:** leg killed at timeout or no results.json → leg INVALID
  (not FAIL); 2 INVALID legs → stop, campaign INVALID-RUN (rig fault, not a
  verdict). A leg whose results.json is byte-identical to another leg's →
  INVALID (snapshot bug), rerun the matrix.

## Estimates (pre-registered, marked as estimates)

- Smoke PASS ~80% — oracle separability is already measured (0.0 vs 30.0, all
  10 poses, offline); live decoy-capture at 215 is the real unknown.
- ctl-decoy reproduces wrong-lock ~85%.
- ap-decoy 3/3 PASS ~45% — win path needs: gate rejects all decoy/blend
  proposals (t≈35–72), DR pursuit keeps the true car in FOV ~40 s blind,
  decoy exits frame ~t72, clean true-car accept by ~t85 (expected relock wall
  ~40–55 s), then ~65 s clean follow. Most likely failure: identity-preserving
  no-relock (VLM keeps proposing decoy-region boxes even after separation).
- ap-reg-0.5 ~90%, ap-reg-3.0 ~85%, ap-rt ~85%.
- Overall RQ-E13 YES ~35–45%.

## Results (2026-07-03T18:20Z)

Ran: `.venv-ft/bin/python experiments/2026-07-03-identity-gate/run_e13.py`
(host 3090 SITL + SAM2 carry @1024, Jetson Qwen2-VL-2B Q8_0 self-booted per
trial over `ssh jetson`, 15 W mode 0 + jetson_clocks). Matrix wall ~110 min
(vs ~40-50 min estimate — the four 150 s decoy legs plus per-trial SITL+Jetson
boots dominate). Raw: `raw/matrix.log`; per-leg snapshots in `runs/<label>/`.

| leg | key metrics | n_regrounds | gate_rejects | relock_on | closest_at_end | final_d_true / final_d_dist (m) | in_fov_frac | verdict |
|---|---|---|---|---|---|---|---|---|---|
| smoke | decoy_hits 10/10, pref_true 10/10; true_dists all 0.0, decoy_dists all 30.0 | — | — | — | — | — | — | **PASS** |
| ctl-decoy | template none (no gate) | 10 | 0 | `[true, distractor×4, ?,?,?, distractor]` | distractor | 31.53 / 6.88 | 0.449 | reproduces wrong-lock (see note) |
| ap-decoy-a | template `[245,245,245]` | 2 | 26 | `[distractor]` | distractor | 26.50 / 1.76 | 0.503 | **FAIL** |
| ap-decoy-b | template `[245,245,245]` | 2 | 24 | `[distractor]` | distractor | 26.49 / 1.79 | 0.488 | **FAIL** |
| ap-decoy-c | template `[245,245,245]` | 2 | 14 | `[distractor]` | distractor | 27.01 / 2.33 | 0.490 | **FAIL** |
| ap-reg-0.5 | recovered=True | 1 | 0 | — | — | — | 1.000 | **PASS** |
| ap-reg-3.0 | recovered=True | 1 | 0 | — | — | — | 1.000 | **PASS** |
| ap-rt | E9 checks 7/7 True; switch_wall 2.35 s, template rebinds `[230,90,40]` (blue) | 1 | 0 | `[true, distractor]` | distractor | 4.18 / 0.42 | 1.000 | **PASS** |

**RQ-E13 verdict: NO.** The appearance-color gate does not convert the decoy
wrong-lock. ap-decoy 0/3 PASS (all end latched on the decoy, true car escaped to
~26.5 m, in-FOV ~0.49), so the RQ is NO by the aggregate rule (an ap-leg fails
with the control reproducing). Regression clean: ap-reg-0.5, ap-reg-3.0, ap-rt
all PASS — the gate, off by default and consulted only on REGROUND, does not
touch plain-scene relock, the 3.0 m/s ceiling, or the E9 retarget switch.

**Why it fails (the valuable negative — acquire_log audited).** The gate *fires
correctly and hard*: template bound to `[245,245,245]` (true white car) at first
ACQUIRE, and 14-26 REGROUND rejects per leg (reason `gate`) of the clean
top-of-frame decoy boxes (e.g. `[249.6,14.4,390.4,254.4]`, descriptor ≈215 → >
tau 12 → rejected). Control had 0 such rejects and re-locked the decoy directly.
But the gate is defeated by a **blend box**: at t≈67-69 s the true car emerges
from under the bridge co-located with the parked decoy, and the VLM proposes a
giant box spanning both (`[268.8,0.0,428.8,441.6]`, 160×441 px). Its brightest
quartile is dominated by the emerging true car's 245 pixels, so the descriptor
lands within tau of the template and the box **passes** — but the box *centres*
on the decoy, so SAM2 latches the decoy anyway. This is exactly the pre-registered
blend-box risk. Root cause: a bright-pixel colour statistic over a loose box is
not spatially bound to the tracked instance — a box whose brightest pixels come
from the true car but whose mass/centre is the decoy sails through. Identity must
be bound to the tracked *mask/instance*, not to a crop statistic. The colour gate
is defeated the same way the size prior (E3) and the motion gate (E7) were: a
global cue over the crop cannot enforce object identity when a two-car blend box
mixes both cars' pixels. Named next lever: an embedding computed on the SAM2
*mask* (not the box crop), or rejecting blend/oversized boxes at REGROUND before
the descriptor is even consulted.

**ctl-decoy attribution note (Opus, transparency — flags a rule edge case for
the next-cycle audit).** The README's ctl attribution rule reads "reproduces iff
`relock_on[0] == distractor`". Here `relock_on[0] == "true"`: a *transient* early
REGROUND at t≈46 s caught the true car while it was still visible pre-occlusion,
because the 150 s control fires 10 regrounds (vs the 75 s E3/E7 single-reground
trials the rule was written for). The control nonetheless **reproduces the E3-S2
wrong-lock in substance** — it ends firmly latched on the decoy
(`closest_at_end=distractor`, `final_d_true=31.53 m`, true car escaped, `relock_on`
dominated by and terminating on `distractor`). The rule's own stated intent ("the
215 decoy captures REGROUND / the follow collapses onto the decoy") is met, and
the gate legs show the identical end-state despite the gate firing, so the test is
measurable and the gate demonstrably loses. I therefore apply RQ-E13 = **NO**
(not NOT-MEASURABLE) on the rule's intent, and record the literal-`relock_on[0]`
divergence here for the Fable audit to re-examine.

**Estimate-vs-actual.** Smoke PASS predicted ~80% → PASS 10/10 (the shade-215
decoy-capture, the live unknown, held perfectly — descriptor gap 0.0 vs 30.0
exactly as measured offline). ctl reproduces ~85% → reproduced (with the
first-reground caveat above). ap-decoy 3/3 PASS ~45% → 0/3 (the pessimistic
"most likely failure" branch, blend-box pass, is what happened — though as a
*blend accept*, not the identity-preserving no-relock also flagged). Regressions
~85-90% → all PASS. Overall RQ-E13 YES ~35-45% → NO. Matrix wall ~110 min vs
~40-50 min estimate (the 150 s decoy legs + per-trial dual boots were
underestimated).

## Proof clips (cut 2026-07-03T18:20Z, committed in `proof/`)

1. **`e13-wronglock-ctl.mp4`** (ctl-decoy, t≈44-90 s) — **the before**: no gate.
   The true car goes under the bridge, REGROUND fires, and the copter latches the
   parked decoy, ending 31.5 m from the true car. The E3-S2 wrong-lock reproduced
   at shade 215.
2. **`e13-gate-blendbox-fail.mp4`** (ap-decoy-a, t≈55-95 s) — **the after (still
   FAIL)**: gate ON. It correctly rejects the tight decoy boxes (26 `gate`
   rejects), but at t≈69 s the true car emerges co-located with the decoy, the VLM
   draws a two-car blend box, its bright quartile (dominated by the 245 true-car
   pixels) passes tau=12, and SAM2 latches the decoy the box centres on — the
   colour gate defeated by a blend box. This is the proof the fix did not change
   the behaviour.
3. **`e13-reg-3.0-noregress.mp4`** (ap-reg-3.0, t≈0-40 s) — no regression at the
   honest 3.0 m/s ceiling (E12 hard-spawn config) with the gate on: first-acquire
   chase, lock, in-FOV 1.000.

## Closeout checklist (Opus — after the matrix)

1. Fill Results + verdict + estimate-vs-actual above; set Status: COMPLETE.
2. Append one row per leg to `docs/results/part4-end-to-end.md` (config
   string included), one RQ-E13 line to `docs/questions/part4-end-to-end.md`.
3. Append the DECISIONS entry to `docs/decisions/part4-end-to-end.md`: the
   shade-215 rig decision (option (i), fairness case above) + color-descriptor
   over CLIP (seed text in Design). SOURCES: nothing new expected.
4. Proof clips cut, committed, captioned above.
5. Commit everything on `experiment/identity-gate`. Do NOT merge and do NOT
   relaunch the loop — the parent session reviews and merges.
