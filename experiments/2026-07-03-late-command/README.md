# E12 late-command — is the 3.5 m/s ceiling chase-validated, or a draw-1 artifact?

**Pre-registered:** 2026-07-03T15:50Z (Madrid wall-clock)
design + patches by Fable; Opus runs the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE 2026-07-03T16:20Z — **RQ-E12 = NO**. Hard-spawn (late command, gift
frame removed) validation demotes E11's ">= 3.5": d3.0 control PASS (genuine chase re-close,
locks 12.17 s) but d3.5 **0/3** never-locked. **Chase-validated follow ceiling = 3.0 m/s.**
See Results.
**Branch:** `experiment/late-command` (off main = 326863f)

## RQ-E12

**With the t=0 gift frame removed (`--acquire-delay 3.0`: no VLM draw may
submit before t=3.0 s — a late "follow that white car" command), does
chase-hold still deliver first-acquire and a passing follow at 3.5 m/s —
i.e. is E11's "ceiling >= 3.5 m/s" supported by the chase mechanism itself,
or was it a draw-1 easy-spawn artifact?**

Falsifiable form: **YES iff** d3.0 (the control leg) passes the standard
follow gate (`in_fov_frac >= 0.90 AND recovered_after_occlusion`) **and**
>= 2/3 of the d3.5 legs pass the same gate. Anything else = NO. The ceiling
statement each outcome pins is mechanical (see Verdict rules).

## Context & rationale (audit of E11)

This is the loop's **last cycle** (budget 1), so the experiment must close a
question, not open a thread. The audit found E11's headline — "measured
ceiling >= 3.5 m/s" — **conflates two claims, only one of which is tested.**

**Spot-check of the E11 raw (`experiments/2026-07-03-chase-acquire/runs/`):**

- **s3.0a/b/c are genuine chase passes.** All three had draw 1 *rejected*
  (`acquire_log[0] = (2.3, ..., false, "size")`); the s3.0a csv shows the
  copter translating N 0 → 25.98 m across 9.16 s of ACQUIRE while tracking
  the rover (at 28.0 m at lock), `in_fov = 1` continuously pre-lock. Chase
  really bought 13 rejected draws' worth of car-in-frame time. The 3.0 rung
  is chase-validated.
- **s3.5a/b are draw-1 locks that never stressed chase.** Both legs:
  `first_lock_s = 2.30` with `acquire_log[0] = (2.3, [big box], true, "")` —
  the winning frame is the t=0 spawn frame (car 0.5 m dead ahead). Worse, in
  both legs the car **escaped the FOV at t≈2.25 s, before the lock resolved**
  (csv: `in_fov` 1→0 at 2.25 with the copter at n≈2.07 vs car n≈8.4; chase
  was still accelerating at vx≈2.7 < 3.5). The pass was rescued by the E4
  submit-frame carry init + *post-lock* pursuit re-closing the gap — the
  *pre-lock* blind re-close (blob-seeded DR chasing a car that has left the
  frame, the exact mechanism that must work when draw 1 loses) was never
  exercised at 3.5. At Stage-0's ~74% accept rate, two draw-1 accepts in a
  row is ~55% luck. So "ceiling >= 3.5" decomposes into: *post-lock follow at
  3.5* (validated, in_fov 0.96 with occlusion recovery) and *first-acquire at
  3.5* (untested — conditioned on winning the first draw).

**Why this experiment:** E11's Results section itself says the ceiling is
"NOT pinned"; the audit shows it is not even *supported* at 3.5 on the
first-acquire side — precisely the side E10/E11 established as the binding
constraint above 2.5. `--acquire-delay 3.0` removes the gift frame: at
3.5 m/s the car is ~11 m N when the first draw may submit, out of the
±4.33 m N half-footprint, so **any frame a draw can win on exists only
because chase re-closed an out-of-FOV gap blind.** It also has a clean
deployment reading — the operator says "follow that white car" a few seconds
after the car starts moving away — which is the north-star scenario, not a
synthetic torture case. Whatever the outcome, the thesis gets a pinned,
honest ceiling statement (see Verdict rules), which is the right shape for a
final cycle.

**Rejected alternative** (→ DECISIONS seed): *probe 4.0/4.5 m/s to pin the
ceiling upward* (the theme-obvious move, and the brief's leading candidate).
Rejected because it inherits the unvalidated 3.5 rung and the draw-1 lottery
confound: a 4.0 leg can pass on an easy draw-1 accept (~74%/leg) or fail on
chase physics never separated from the lottery — either way the "ceiling"
number would carry the same weakness the audit just exposed at 3.5, and a
passing top rung would leave the ceiling unpinned *again* (open thread, wrong
shape for the last cycle). Validation dominates: it converts an
under-supported headline into a defensible one at fixed cost. *Not* rejected
but deferred with it: spawn-geometry variants (lateral offset, crossing
entry) — the delay knob is one parameter, reuses the standard spawn, and
directly forces the untested mechanism; geometry variants add render-path
work for the same stress.

## Code changes (already committed on this branch — Opus: do NOT edit these files)

| File | Change | Default behavior |
|---|---|---|
| `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` | `--acquire-delay S` (float, default 0.0): `AcquireCarrySM` gains `acquire_delay`; in `step()`, while `first_lock_t is None and t < acquire_delay`, no draw is submitted (`return None`). Pre-FIRST-lock only — REGROUND/RETARGET draws are never delayed (the guard tests `first_lock_t`). Hold/chase (`--acquire-hold`) runs from t=0 regardless: the blob track still feeds `hist` → `pursuit_vel`, so the copter chases during the delay window. `acquire_delay` recorded in the run manifest cfg. Selfcheck gains a delay block (no submit before t=delay; first submit at the first tick >= delay; carry inits on the delayed *submit* frame, E4). | default 0.0 → guard never true → bit-identical to E2–E11 |
| `experiments/2026-07-03-late-command/run_e12.py` | the matrix runner (below): 4 legs, per-leg snapshot, mechanical verdicts; `classify_fail` verbatim from run_e10/e11 plus a mechanical fallback for the new E12 FAIL shape (gate fell on the *pre-lock* escape window with a clean post-lock track); `chase_runaway()` detector for E11's pre-registered garbage-blob signature (pre-lock `copter_n > rover_n + 15`) | — |

No changes to `cascade_pid.py`, `sitl_cam.py`, `follow_demo.py`, or any
`grounding/` code. Speeds and vmax values are all within what E10/E11 already
threaded (world auto-extension `n_max = c(75)+20` ≈ 283 m at 3.5).

All three selfchecks pass post-patch (2026-07-03, host):
`.venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py --selfcheck`,
`.venv-ft/bin/python runners/sitl/cascade_pid.py`,
`.venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py`.

## Run matrix

Rig: host 3090 (SITL + renderer + SAM2 carry @1024) + Jetson Orin Nano over
`ssh jetson`. `phase3_sitl.py` **self-boots both** the ArduCopter SITL and the
Jetson Qwen2-VL-2B Q8_0 llama-server per trial (log line
"[3] booting Jetson q8_0 server..."); do NOT pass `--remote-carry`. **Power
mode: 15 W (mode 0) + jetson_clocks** — this board has no MAXN_SUPER (see
`docs/decisions/part2-rebuild.md`). Pre-flight once:
`ssh jetson sudo nvpmodel -q` (expect mode 0) and `ssh jetson sudo jetson_clocks`.
Software versions are auto-captured per run by the manifest, as E2–E11.

One command runs everything (4 legs, snapshots each into `runs/<label>/`):

```bash
cd /home/gara/jetson
mkdir -p experiments/2026-07-03-late-command/raw
echo "$(date -Is) EXEC-START late-command" >> .claude/loop.log
.venv-ft/bin/python experiments/2026-07-03-late-command/run_e12.py 2>&1 | tee experiments/2026-07-03-late-command/raw/matrix.log
```

Legs, in order (common flags: `--loss-gate motion --dr pursuit
--acquire-hold chase --acquire-delay 3.0`):

| leg | `--speed` | `--vmax` | purpose |
|---|---|---|---|
| d3.0 | 3.0 | 4.0 | **control** — chase is already validated at 3.0 (E11 s3.0: in_fov 1.000 pre-lock for 9.2 s, draw 1 rejected anyway), so the delay removes only an always-rejected early draw; if this leg fails, the delay harness itself binds and the 3.5 legs are not attributable to the 3.5 rung |
| d3.5a/b/c | 3.5 | 5.0 | **decision** — same config as E11 s3.5 except the gift frame is gone: the car escapes the FOV at ~2.25 s and no draw may submit before 3.0 s, so a lock requires the pre-lock blind DR chase to re-close the gap onto a moving car |

Gotchas (baked into the runner, listed so you can recognize them):
- `phase3_sitl.py` clobbers `raw/phase3a-sitl/trial-<v>ms.{csv,mp4}` and
  `runs/phase3a-sitl/results.json` on every run — the runner snapshots per leg
  immediately; the csv/mp4 filename depends on the speed (e.g. `trial-3.5ms.csv`).
- A leg is killed at 20 min (E10/E11 actuals: ~3–4 min/leg; 20 min = hung SITL).
- If SITL dies mid-matrix, re-run the whole matrix (~15–20 min) rather than
  surgering individual legs; `run_e12.py` re-executes all legs.
- Failure signatures to recognize (legitimate FAILs, not rig faults — snapshot
  and record, do not "fix"): (1) **chase-runaway** — a garbage early blob
  seeds a bad velocity and the copter chases off north at vmax in ACQUIRE;
  the runner prints `[CHASE-RUNAWAY: ...]` when pre-lock `copter_n` exceeds
  `rover_n + 15 m`. (2) **DR shortfall** — the blob-seeded velocity
  underestimates the car, the gap never re-closes, every draw sees empty
  road → `never-locked (first-acquire)`. (3) **pre-lock escape window** —
  it locks, tracks cleanly, but the pre-lock out-of-FOV seconds alone drag
  `in_fov_frac` below 0.90; the runner prints the E12 fallback label.

## Verdict rules (mechanical — Opus does not deliberate)

The runner prints all of this; the rules it applies:

- **Per-leg gate:** PASS iff `trial["in_fov_frac"] >= 0.90 AND
  trial["recovered_after_occlusion"] == true` in the leg's
  `runs/<label>/results.json` (identical to E2–E11 for comparability).
- **RQ-E12 = YES** iff d3.0 PASS **and** >= 2/3 of d3.5 legs PASS.
- **Ceiling statement** (what goes in the ledgers, verbatim per outcome):
  - YES → "the 3.5 m/s ceiling is now **chase-validated under a hard spawn**
    (late command, no gift frame); E11's >= 3.5 stands with first-acquire
    support."
  - d3.0 PASS, d3.5 < 2/3 → "**chase-validated ceiling = 3.0 m/s**; E11's
    3.5 passes were draw-1 easy-spawn artifacts — 3.5 holds only when the
    first draw wins (~74%/leg)."
  - d3.0 FAIL (CONTROL-FAIL) → RQ-E12 = NO regardless of d3.5; "a 3-s late
    command breaks first-acquire even at the chase-validated 3.0 m/s; the
    d3.5 results are not attributable to the 3.5 rung." Finish the matrix
    anyway and record everything plainly; do not debug in this campaign.
- **Per-FAIL-leg binding mode** (printed by the runner): `first_lock_s` null
  → "never-locked (first-acquire)"; else the state at the start of the first
  >= 1 s contiguous `in_fov == 0` run after first lock: ACQUIRE →
  first-acquire, REGROUND/RETARGET → relock, CARRY → tracking-trail; no such
  post-lock run → "occlusion-relock" if `recovered_after_occlusion` is false,
  else "first-acquire (pre-lock escape window)". Plus the `[CHASE-RUNAWAY]`
  tag when pre-lock `copter_n > rover_n + 15`.
- **Abort:** leg killed at 20 min or missing `results.json` → snapshot what
  exists, mark INVALID, continue; **2 INVALID legs → stop, campaign verdict
  INVALID-RUN** (fix the rig outside this campaign, re-run fresh).

## Estimates (marked as estimates)

- Runtime: ~15–20 min total (4 legs × ~3.5–4.5 min incl. SITL+Jetson boot;
  d3.5 legs lock later than E11's, adding ~5–10 s each).
- d3.0 PASS: ~85% (delay removes one draw that E11 s3.0 rejected anyway;
  chase held in_fov 1.000 for 9.2 s pre-lock at 3.0).
- d3.5 >= 2/3: **~40–50%** (genuinely uncertain — that is the point). Physics
  sketch: car exits FOV at ~2.25 s (observed, E11 s3.5); blob hist from
  0–2.25 s seeds DR; blind pursuit at vmax 5.0 gives a ~1.5 m/s closing
  margin; gap peaks ~7–8 m near t≈3–3.5 s, car re-enters the footprint
  ~t≈5.5–7 s; draws land every ~2.35 s from t=3.0 (the first on empty road),
  so first winnable draws are ~5.4/7.7 s; at ~74% accept, first lock
  ~**8–15 s** (est). Main risks: blob-seeded velocity error at 3.5 m/s
  (never exercised — this experiment exists to exercise it), chase-runaway,
  and the pre-lock escape window costing ~4–6 s of in_fov budget.
- in_fov_frac on a passing d3.5 leg: ~0.92–0.95 (est; 7.5 s total out-of-FOV
  budget at the 0.90 gate).
- first_lock_s at d3.0: ~7–12 s (est; E11 s3.0 was ~9.2 s).

## Results (TBD — Opus fills; one row per leg)

Ran 2026-07-03T16:20Z. Rig: host 3090 (SITL + SAM2 carry @1024) + Jetson Q8_0 acquire,
**15 W + jetson_clocks**. Common flags `--loss-gate motion --dr pursuit
--acquire-hold chase --acquire-delay 3.0`; `--vmax` per leg. Raw:
`raw/matrix.log`, per-leg `runs/<label>/{results.json,trial.csv,trial.mp4}`.

| leg | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean | binding mode (FAIL only) |
|---|---|---|---|---|---|---|---|---|---|---|
| d3.0 | PASS | 1.000 | True | 12.17 | 12 | 10 | 1 | 18.63 | 145.2 | — |
| d3.5a | FAIL | 0.030 | False | None | 31 | 30 | 0 | — | — | never-locked (first-acquire) |
| d3.5b | FAIL | 0.029 | False | None | 31 | 30 | 0 | — | — | never-locked (first-acquire) |
| d3.5c | FAIL | 0.030 | False | None | 31 | 30 | 0 | — | — | never-locked (first-acquire) |

**RQ-E12 verdict: NO** — d3.0 control PASS **and** d3.5 **0/3** PASS.

**Ceiling statement (verbatim from Verdict rules, d3.0 PASS + d3.5 < 2/3 outcome):**
*chase-validated ceiling = 3.0 m/s; E11's 3.5 passes were draw-1 easy-spawn artifacts —
3.5 holds only when the first draw wins (~74%/leg).*

**What this establishes:** The audit was correct. With the gift frame removed
(`--acquire-delay 3.0`, modeling a late "follow that white car" command), the chase-hold
still delivers a genuine hard-spawn first-acquire at **3.0 m/s** — d3.0 locked at 12.17 s
(vs E11's gift-frame 9.2 s: the delay pushed the winning draw ~3 s later, 10/12 draws
rejected, and the pre-lock blind DR chase re-closed the gap anyway, in_fov 1.000 to trial
end). But at **3.5 m/s the pre-lock blind DR cannot re-close**: all three legs never locked
(in_fov ~0.03, first_lock None, 30/31 draws rejected on empty road — the car exits the FOV
by ~2.25 s, and blind pursuit at vmax 5.0 gives too little closing margin to bring a 3.5 m/s
car back into the footprint before it is gone). E11's s3.5 2/2 was rescued entirely by the
t=0 gift frame (E4 submit-frame carry init + post-lock pursuit), not by the chase mechanism
the ceiling claim needed — E11's ">= 3.5" is **demoted to an easy-spawn artifact**. The
honest, first-acquire-supported follow ceiling is **3.0 m/s** (still 6x the E2-era "< 0.5",
and E11's chase-hold is what earns the 2.5 -> 3.0 gain under a hard spawn).

**Estimate-vs-actual (diverged — the uncertain leg resolved to the low side):** Fable
estimated d3.0 PASS ~85% (actual PASS, first_lock 12.17 s vs est 7-12 — slightly late but
in family), and d3.5 >= 2/3 at ~40-50% (**actual 0/3** — the blind-DR re-close was weaker
than the physics sketch's ~1.5 m/s margin suggested; the car never re-entered the footprint,
so no draw after t=3 ever saw the car). No chase-runaway fired on any leg; the FAIL mode was
uniformly the estimated "DR shortfall → never-locked", not the escape-window or runaway
branches. The negative result is the point: it converts E11's unpinned/optimistic ">= 3.5"
into a defensible "3.0 m/s under a hard spawn".

## Video deliverables (Opus cuts — DoD item 7)

Every leg's mp4 is snapshotted to `runs/<label>/trial.mp4` by the runner; the
"before" footage exists in E11's snapshots. Cut 3 clips into `proof/` (curated
thesis clips, **committed**), caption each here with what it shows and which
run it came from. Re-encode for clean seeks as E10/E11 did:
`ffmpeg -ss <t0> -t <dur> -i <src> -c:v libx264 -pix_fmt yuv420p proof/<name>.mp4`

Cut 2026-07-03T16:06Z (re-encoded libx264 for clean seeks):

1. `proof/e12-gift-frame.mp4` — **the artifact this campaign exposes.** Source:
   E11 `../2026-07-03-chase-acquire/runs/s3.5a/trial.mp4`, t=0–12 s: at 3.5 m/s
   the car escapes the FOV at ~2.25 s while the VLM is still resolving draw 1 on
   the easy t=0 frame; the lock lands at 2.30 s on a car already out of frame —
   first-acquire never actually stressed. This is why E11's ">= 3.5" needed E12.
2. `proof/e12-3.5-neverlock.mp4` — **the negative result (d3.5 fails).** Source:
   E12 `runs/d3.5a/trial.mp4`, t=0–22 s: with no draw allowed before t=3 s, the
   3.5 m/s car escapes and the pre-lock blind blob-seeded DR chase cannot re-close
   the gap — the car never re-enters the footprint, every post-t=3 draw sees empty
   road (30/31 rejected), first_lock None, in_fov 0.03. The chase mechanism does
   not deliver at 3.5 without the gift frame.
3. `proof/e12-control-3.0.mp4` — **the control (chase-validated speed).** Source:
   E12 `runs/d3.0/trial.mp4`, t=0–18 s: the same 3-s late command at 3.0 m/s —
   the car escapes, the blind DR chase genuinely re-closes the gap (copter
   translates N through ACQUIRE), and the VLM locks at 12.17 s on a chase-produced
   frame, then follows in_fov 1.000. This is the real 3.0 m/s ceiling.

## Closeout checklist (Opus)

1. Fill the Results table + verdict above (copy the runner's printed verdict
   + ceiling statement); record estimate-vs-actual divergences; set the
   Status line to COMPLETE + verdict.
2. Cut + caption + commit the video deliverables into `proof/` (section above).
3. Append one row per leg (or one summary row per speed) to
   `docs/results/part4-end-to-end.md` under E12.
4. Append RQ-E12 + one-line verdict to `docs/questions/part4-end-to-end.md`.
5. Append the DECISIONS entry to `docs/decisions/part4-end-to-end.md`: chose
   hard-spawn validation of the 3.5 rung (`--acquire-delay`) over probing
   4.0/4.5 to extend the ceiling (rationale in Context above — the audit
   found E11's s3.5 passes were draw-1 gift-frame locks with the car already
   out of FOV at resolve time, so the ceiling's first-acquire side was
   unsupported at 3.5; validation dominates extension on the loop's last
   cycle). Include the audit evidence (s3.5a/b `acquire_log[0]` accepts at
   2.30 s; `in_fov` 1→0 at t=2.25 pre-lock; s3.0a copter N 0→26 m during
   ACQUIRE = genuine chase).
6. Whatever the verdict, update the E11 ceiling claim wherever it is quoted
   with the E12 qualifier (the ledger entries link back here; do not rewrite
   E11's README — append a one-line pointer under its Results section:
   "Ceiling qualifier: see E12 (`../2026-07-03-late-command/`)").
7. Commit on this branch: `E12 late-command: <verdict summary>`.
   Do NOT merge — the parent session merges.
