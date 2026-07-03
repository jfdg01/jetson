# E16 relock-rate — is E14's mask-gate win a reliable behavior or a lucky rate?

- **Pre-registered:** 2026-07-03T19:35Z (Madrid wall-clock)
- **Status:** PRE-REGISTERED, not yet run.
- **Roles:** design + audit by Fable (this README, `run_e16.py`; **no harness
  patches this cycle** — the config is expressed entirely with existing
  flags). Opus runs the matrix and fills **Results only** — do NOT re-patch
  code. Every judgment is pre-made below; if a case is not covered by a rule
  here, record it verbatim and mark the leg `UNRULED`, do not invent a rule.
- **Branch:** `experiment/relock-rate` (from clean main `8d6336e`, the E15
  merge — the code under test IS current main, deliberately).
- **Rig:** host 3090 runs SITL + SceneRenderer + StreamCarry (SAM2 @1024
  default); the Jetson runs the VLM (Qwen2-VL-2B Q8_0) and **self-boots per
  trial** — no manual server start. Jetson at 15W (`sudo nvpmodel -m 0`) +
  `sudo jetson_clocks` (NOPASSWD; there is NO MAXN on this board). Do **NOT**
  pass `--remote-carry` (mask gate is local-carry only; phase3_sitl refuses).
- **Versions:** same stack and venv (`.venv-ft`) as E14/E15 — pins in
  `requirements-ft.lock.txt`; SAM2.1-hiera-tiny on host, Qwen2-VL-2B Q8_0 on
  Jetson. Zero code deltas vs main `8d6336e`.

## RQ-E16

**What is the relock rate of E14's exact mask-gate config on current main —
is "identity hole closed 3/3" (RQ-E14 YES) a reliable behavior or a
stochastic win path that E15's reg-e14 caught missing?**

Over n=8 independent replicates of E14's byte-identical mk-decoy config
(`--speed 0.25 --twin decoy --decoy-shade 215 --duration-s 150 --loss-gate
motion --dr pursuit --acquire-hold motion --reground-gate mask`, app-tau
default 12), with r = per-rep PASS count over valid reps (rules below):

- **RELIABLE** iff at most one valid rep FAILs (r >= 7/8 at full
  denominator). E14's claim stands as a measured >= 87% rate; E15's reg-e14
  FAIL was an unlucky draw of a high-rate process.
- **FRAGILE** iff r <= denom/2 (r <= 4/8). E14's 3/3 was luck
  (p^3 = 0.125 at p = 0.5); the "closed" headline is demoted to a rate and
  the binding constraint moves to the post-reject relock proposal stream.
- **QUALIFIED** otherwise (r = 5-6/8): the gate wins most draws but relock
  is not reliable; the claim must carry the rate.
- **NOT-MEASURABLE** iff a selfcheck fails, the no-gate control fails to
  reproduce the wrong-lock twice, or fewer than 6 valid reps survive.
- Suffix **[identity-breach observed]** iff any rep's `relock_on` contains
  `"distractor"` (the gate ACCEPTED a decoy latch — qualitatively worse than
  a missed window; every failure observed so far is identity-preserving).

Any of RELIABLE / QUALIFIED / FRAGILE is a full answer; FRAGILE is thesis
content, not a failed experiment.

## Audit findings (why this experiment, and why E15's framing was wrong)

Audited 2026-07-03 from the run snapshots (`runs/<leg>/results.json`,
`acquire_log` entries are lists `[t, box, accepted, reason]`):

1. **E15's README misstates E14's replicates.** It claims "accept t=86.25 in
   all three" mk-decoy legs. False: mk-decoy-a accepted at **t=86.25**,
   mk-decoy-b at **t=81.38**, mk-decoy-c at **t=76.55** — three different
   accept times, and a's initial t=4.71 lock box (`[256.0, 96.0, 390.4,
   345.6]`) differs from b/c's (`[249.6, 96.0, 390.4, 340.8]`). E14's own
   three runs were NOT identical replays; the rig varies run-to-run **under
   fixed E14 code**. "Near-deterministic rig" was a stale assumption.
2. **reg-e14's trajectory starts inside E14's own draw distribution.** Its
   first two acquire_log entries (t=2.35 size-reject box AND the t=4.71
   accepted lock box) are byte-identical to mk-decoy-b/c's. The E15 code did
   not visibly perturb the E14 path — the failing run began exactly like two
   runs that PASSed.
3. **The failure is upstream of the gate.** In reg-e14, the mask gate's last
   consult was t=79.16; from t=81.57 to the 150 s end, **every** REGROUND
   resolve (27 of them) was rejected by the **size prior** — the VLM
   alternated near-full-frame boxes (`[192,0,537.6,480]` growing to
   `[243.2,0,595.2,480]`) and slivers, and never drew a size-passing clean
   true-car box. The gate behaved correctly (12 rejects, zero wrong
   accepts, `closest_at_end=true`, `in_fov=1.0`); the relock **proposal**
   stream failed. E14's win path needs the VLM to offer a clean box after
   separation, and that offer is a per-run random event.
4. **No mechanism or signature for a systematic patch effect.**
   `achieved_hz` is 19.6-19.8 across E14 and E15 legs (no slowdown); the E15
   patch touched only decoy2/occ2 plumbing, attribution (`closest_label`),
   and the multi-bridge metric — not the acquire/gate/submit path; render
   identity is asserted by the sitl_cam `np.array_equal` selfcheck; and
   finding 2 shows the E15-code run drew an in-distribution trajectory.
   Meanwhile E15's own harder legs accepted clean true boxes in 5/6 runs
   under the same patched code.

**Conclusion:** the live question is not patch-vs-rig — it is the **rate**.
E14's evidence is 3 PASSes in 3 draws; E15 added 1 FAIL in 1 draw of the
same config. Four draws cannot distinguish p ~ 0.95 from p ~ 0.6, and the
whole identity arc ("hole closed") plus E15's unattributable stress
observations rest on that distinction. Before adding any new lever (theme's
E3b appearance gate) or re-running stress attribution, measure P(relock)
under the code all future work runs on.

**Rejected alternatives** (seed for DECISIONS):

- *Git-worktree A/B (E14 merge `11698ee` vs main `8d6336e`, n per arm)* —
  E15's own seeded next question. Rejected: the audit already discriminates
  the hypotheses (findings 1-4: within-code variance exists, the failing
  run's prefix is in-distribution, no patch mechanism, no hz signature); at
  n <= 5 per arm the A/B can only resolve rate differences of ~50 pp; and
  the decision-relevant rate is main's regardless — every future experiment
  runs on main. Given up: forensic certainty about the E14-merge code's own
  rate; if E16 lands FRAGILE and someone still suspects the patch, a
  worktree arm can be a later cycle.
- *E3b CLIP appearance gate (the standing theme)* — rejected this cycle:
  building a second identity lever on a foundation whose reliability is
  unknown; also E13/E14 already showed crop-based cues (CLIP included) fail
  the blend box structurally, so the theme's specific proposal is stale.
- *Re-run E15's dd/ro stress attribution* — premature: stress rates are
  uninterpretable until the baseline rate is known (a 2/3 on dd means
  nothing if the baseline itself is 0.7).

## Independence of draws (pre-registered, per the E15 lesson)

The harness exposes **no RNG seed** and seeds nothing (`grep` confirms: no
`random`/`np.random` use in `phase3_sitl.py`). Replicates are independent
because each leg is a fresh full-process launch — new ArduCopter SITL boot,
new Jetson llama-server boot via `JetsonBackend`, new StreamCarry — driven
by a real-time ~20 Hz wall-clock loop; run-to-run variation enters through
loop/VLM timing jitter (which frame each ~2.35 s VLM draw sees). That
variation is **empirically nonzero under fixed code** (audit finding 1:
accepts at 76.55/81.38/86.25 s, two distinct t=4.71 boxes, gate rejects
13/13/11 across E14's own three replicates). Trial index varies nothing
explicitly; nothing else is varied on purpose. n=8 therefore samples the
same distribution E14 sampled 3 times and E15's reg-e14 sampled once.

## Run matrix (Opus: run exactly this)

Preconditions: host 3090 free; `ssh jetson` up. Then, from the repo root:

```bash
cd /home/gara/jetson
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"   # NOPASSWD, 15W mode 0
mkdir -p experiments/2026-07-03-relock-rate/raw
.venv-ft/bin/python experiments/2026-07-03-relock-rate/run_e16.py \
  2>&1 | tee experiments/2026-07-03-relock-rate/raw/matrix.log
```

That is the whole matrix. The runner executes, in order (do not reorder):

1. **Selfchecks** (`phase3_sitl.py --selfcheck`, `sitl_cam.py`) — any
   failure exits: PRECONDITION-FAIL, no legs, RQ-E16 = NOT-MEASURABLE.
2. **ctl** — no-gate control, must REPRODUCE the wrong-lock or the runner
   retries once (`ctl-retry`) then **halts** (NOT-MEASURABLE) — no point
   burning 8 reps on a drifted rig.
3. **rep-1 .. rep-8** — E14's exact config + `--reground-gate mask`.
4. **Retries** — any rep verdicted NOT-MEASURABLE (confident-latch) or
   INVALID is re-run once, max 2 retries total (a retry replaces its
   original in the rate; a failed retry excludes the rep from the
   denominator). More than 2 retry candidates → runner warns "rig likely
   sick", retries the first 2 only, the rest stay excluded.

| leg | flags | n | purpose |
|---|---|---|---|
| ctl | `--speed 0.25 --twin decoy --decoy-shade 215 --duration-s 150 --loss-gate motion --dr pursuit --acquire-hold motion` | 1 | no gate: wrong-lock still reproduces (rig/VLM drift guard) |
| rep-1..8 | ctl flags + `--reground-gate mask` | 8 | E14's exact config — the rate |

Every leg is snapshotted to
`experiments/2026-07-03-relock-rate/runs/<label>/{results.json,trial.csv,trial.mp4}`
immediately after it finishes (phase3_sitl **clobbers**
`experiments/2026-07-01-temporal-acquire-carry/raw/phase3a-sitl/trial-0.25ms.{csv,mp4}`
and `.../runs/phase3a-sitl/results.json` every run — only snapshots survive;
always read the snapshots). Every trial records video (`trial.mp4`).

**Gotchas:** run from repo root with `.venv-ft/bin/python` (the runner uses
absolute paths anyway); do not run anything else on the 3090 during the
matrix; do not touch `--app-tau`, shades, geometry, or flags mid-run — any
deviation is a new pre-registration. If the host GPU OOMs or SITL fails to
boot twice in a row, stop and report.

## Verdict rules (mechanical — the runner prints these; Opus does not deliberate)

All fields from the leg's snapshotted `results.json` `trial` object.
`acquire_log` entries are lists `[t, box, accepted, reason]`; relock accept
times = accepted entries after the first (the first is the initial ACQUIRE).

- **ctl REPRODUCES** iff `n_regrounds >= 1` AND `twin.closest_at_end ==
  "distractor"` AND `twin.final_d_true_m >= 10.0` (end-state attribution,
  E14's rule; `relock_on[0]` is never consulted).
- **rep PASS** iff `n_regrounds >= 1` AND `twin.relock_on` non-empty AND
  `twin.relock_on[-1] == "true"` AND `twin.closest_at_end == "true"` AND
  `twin.final_d_true_m <= 2.0` AND `in_fov_frac >= 0.90` — byte-identical to
  E14's mk-decoy PASS rule (same bar, so the rate is comparable).
- **rep FAIL subtypes** (recorded, all count as FAIL in r):
  *no-relock* (`relock_on` empty; report gate rejects + size rejects — the
  reg-e14 mode), *wrong-lock* (`relock_on[-1] != "true"`), *wrong-end*
  (relocked true but `closest_at_end != "true"`), *verified-but-lost*
  (relocked true, ended `> 2.0 m` or `in_fov < 0.90`).
- **rep NOT-MEASURABLE** iff `n_regrounds == 0` (confident-latch — nothing
  tested); triggers a retry (max 2 total).
- **leg INVALID** iff wall-clock > 1500 s (runner kills it) or snapshot
  `results.json` missing/unreadable; triggers a retry (max 2 total,
  shared with NOT-MEASURABLE retries).
- **GATE-BREACH flag** iff `"distractor" in twin.relock_on` for any rep —
  appended to the RQ verdict as `[identity-breach observed]`.
- **RQ-E16** over valid reps (PASS or FAIL after retries; denom = count):
  `denom < 6` → NOT-MEASURABLE; `denom - r <= 1` → RELIABLE;
  `2*r <= denom` → FRAGILE; else QUALIFIED. (At denom 8: RELIABLE r>=7,
  QUALIFIED 5-6, FRAGILE <=4. At denom 6: RELIABLE r>=5, QUALIFIED 4,
  FRAGILE <=3.)
- The runner prints the per-leg verdicts, the rate, and the RQ verdict —
  copy them into Results; if the runner's print and this README ever
  disagree, record both verbatim and mark `UNRULED` (do not pick).

## Estimates (pre-registered; wrong estimates are content)

- Runtime: 9-11 legs (ctl + 8 reps + up to 2 retries) x ~13 min +
  selfchecks ~= **120-150 min** (E15 actual: ~130 min for 9 legs).
- ctl REPRODUCES: ~90% (reproduced in E13, E14, E15-dd, E15-ro).
- Rate prior from the 4 historical draws (3/3 E14-code + 0/1 E15-code,
  same config): Beta-ish point estimate ~0.6-0.8. Expected outcome
  probabilities: RELIABLE ~25-30%, QUALIFIED ~35-45%, FRAGILE ~25-30%,
  NOT-MEASURABLE ~5-10%. Modal expectation: **QUALIFIED, r = 5-6/8**.
- Identity-breach: < 5% (never observed in 10 gated decoy legs to date;
  the analytic shade margin makes a decoy-accept require a majority-true
  mislabeled latch, which the E14 probe never produced).
- Expected accept-time spread of PASS reps: ~74-90 s (E14 saw 76.55-86.25;
  the car separates from the decoy from t ~ 51 onward).

## Results (TBD — Opus fills this section only)

| leg | verdict | n_regrounds | gate_rejects | size_rejects | relock_on | closest_at_end | final_d_true_m | in_fov_frac | accept_t_s |
|---|---|---|---|---|---|---|---|---|---|
| ctl | | | | | | | | | |
| rep-1 | | | | | | | | | |
| rep-2 | | | | | | | | | |
| rep-3 | | | | | | | | | |
| rep-4 | | | | | | | | | |
| rep-5 | | | | | | | | | |
| rep-6 | | | | | | | | | |
| rep-7 | | | | | | | | | |
| rep-8 | | | | | | | | | |

- **Relock rate r:** TBD / TBD valid reps (retries: TBD)
- **RQ-E16 verdict:** TBD (RELIABLE / QUALIFIED / FRAGILE / NOT-MEASURABLE,
  breach flag if any)
- **Accept-time spread (PASS reps):** TBD
- **Estimate vs actual:** TBD
- **Deviations/surprises:** TBD

## Proof clips (Opus: 2-3, committed under `proof/`, mechanical picks)

Copy (or ffmpeg-trim to roughly t 40-125 s) from `runs/<leg>/trial.mp4`;
caption each with the leg's config and verdict:

1. `proof/e16-ctl-wronglock.mp4` — the ctl leg: the no-gate baseline
   wrong-locks the decoy (the hole, still open without the gate).
2. `proof/e16-pass-relock.mp4` — the first PASS rep: reject-until-separated,
   then relock on the true car.
3. `proof/e16-fail-<subtype>.mp4` — the first FAIL rep (the rate's other
   face). If there are no FAIL reps, substitute the PASS reps with the
   earliest and latest `accept_t_s` (shows the window spread) and name them
   `e16-pass-early.mp4` / `e16-pass-late.mp4`. If there are no PASS reps,
   use the first two FAIL reps.

## Ledger updates on completion (Opus)

- `docs/results/part4-end-to-end.md`: one row per leg (config in every row:
  15W mode 0 + jetson_clocks, image-size 1024, app-tau 12, decoy-shade 215)
  plus the rate line.
- `docs/questions/part4-end-to-end.md`: RQ-E16 + one-line verdict, including
  the rate as a number (e.g. "r=6/8 QUALIFIED").
- `docs/decisions/part4-end-to-end.md`: fixed-code replication chosen over
  the git-worktree A/B, the E3b theme, and stress re-attribution — rationale
  and what was given up in "Rejected alternatives" above; also record the
  E15-README misstatement correction (finding 1) so the wrong "t=86.25 in
  all three" claim does not propagate into the thesis.
- No new SOURCES (no new external artifact).
- Set Status here to COMPLETE with a Madrid wall-clock timestamp; commit
  snapshots under `runs/`, `raw/matrix.log`, proof clips; leave `git status`
  clean. Merge per the loop protocol.
