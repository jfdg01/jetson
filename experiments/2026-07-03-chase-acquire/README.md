# E11 chase-acquire — can the copter chase what it hasn't locked yet? (first-acquire at 3.0 m/s)

**Pre-registered:** 2026-07-03T13:11Z (Madrid wall-clock)
design + patches by Fable; Opus runs the matrix and fills Results only — do NOT re-patch code.
**Status:** COMPLETE 2026-07-03T13:40Z — **RQ-E11 = YES**. Chase-hold makes first-acquire
reliable at 3.0 m/s (s3.0 3/3 PASS, locks ~9.2 s vs E10 never-locked), no chase-regression
at 2.5, and s3.5 2/2 → **ceiling now >= 3.5 m/s** (top rung tested, not pinned). See Results.
**Branch:** `experiment/chase-acquire` (off main = 0ddbbb9)

## RQ-E11

**Does upgrading the pre-first-lock hold from a positional servo to a
blob-pursuit chase (`--acquire-hold chase`: the motion blob's world track
feeds the existing hist → hist_vel → pursuit_vel DR machinery before the
first lock) make first-acquire reliable at 3.0 m/s, raising the measured
follow ceiling from 2.5 to >= 3.0 m/s?**

Falsifiable form: **YES iff** reg-2.5 passes the standard follow gate
(`in_fov_frac >= 0.90 AND recovered_after_occlusion`) **and** >= 2/3 of the
s3.0 legs pass the same gate. Anything else = NO. Secondary (does not decide
the RQ): the highest speed whose legs meet their quota (2.5: 1/1, 3.0: >=2/3,
3.5: 2/2, lower speeds must also pass) is recorded as the **new measured
ceiling**; s3.5 runs at `--vmax 5.0` to keep a >= 1.5 m/s closing margin.

## Context & rationale (audit of E10 + E6)

Theme for this cycle: *"improve the speed at which the system can operate so
we can track fast moving objects."* E10 measured the ceiling at 2.5 m/s and
named first-acquire as the binding constraint above it. This design audit
spot-checked that claim in the raw before building on it.

**E10's headline holds, and the raw sharpens it.** Spot-check of
`experiments/2026-07-03-fast-follow-ceiling/runs/s3.0{a,b}/results.json`:
both 3.0 legs really are never-locked (in_fov_frac 0.0521, first_lock None;
31 resolved draws all rejected `size`, the 32nd in-flight at trial end; the
two legs' acquire_logs differ slightly — genuine n=2, so the failure is
structural, not one unlucky seed). But E10's framing — "can't get a
*repeatable* VLM draw" — is subtly off. The log shows the VLM got exactly
**one** car-in-frame draw: submitted at t≈0 (car 0.5 m ahead, fully visible),
it lost the greedy lottery with a garbage near-full-frame box
`[134.4, 0, 499.2, 480]` (E6 Stage-0: cm-scale pose changes flip the greedy
output). Draw 2 resolved at t=2.3 s, by which time a 3.0 m/s car had already
crossed the ±4.33 m N half-footprint (FOCAL 554 px / 10 m AGL). From t=6.96 s
to t=72.85 s **every draw returned the byte-identical road-dash box**
`[307.2, 144, 332.8, 264]` — the copter was hovering over an empty road, and
the car never re-entered. The car was in FOV for 3.9 s total; the VLM never
got a second chance. So it is not draw *repeatability* that binds (Stage-0
measured ~74% accept on car-in-frame frames); it is **car-in-frame time**.

**The mechanism is the pre-lock control law, not the VLM.** E6's
`--acquire-hold motion` is a position-only P-servo on the frame-diff blob
(`pid.compute(hold)`, KP_LAT 0.02): no velocity feed-forward, no memory. When
the blob leaves the frame, `hold = None` → `pid.compute(None)` → **hover**.
And pre-lock `hist` is empty, so the DR/pursuit machinery that owns every
*post*-lock blind phase (E4 replay, E5 pursuit) never engages. E6 validated
the hold only at 0.5–1.5 m/s, where hovering between draws nearly suffices;
its silent assumption — the copter need not translate much to keep the car
drawable — breaks at 3.0. This is the asymmetry E11 removes: **pre-lock
blindness hovers forever; post-lock blindness chases.**

**Fix under test — chase-hold (`--acquire-hold chase`):** while pre-first-lock
and blind, each frame's motion blob is converted to a world position (same
`box_to_world` geometry the carry path uses, anchored on the sweep-center row
— see `blob_chase_box` rationale in the code) and appended to `hist`. The
existing, already-validated machinery then does everything: `hist_vel` gives
the mover's velocity, the E5 `pursuit_vel` DR (a) closes on the blob with
velocity feed-forward while it is visible and (b) keeps chasing the last
estimate when the mover outruns the FOV — instead of hovering. The first
~0.5 s (before hist spans 0.5 s) falls back to the E6 positional servo as a
bootstrap. The VLM remains the **sole lock authority**: chase-hold only buys
car-in-frame time for more draws, exactly the E6 mechanism extended with
feed-forward. Physics estimate (marked estimate): pursuit engages ~1.0–1.4 s
in at up to `--vmax` 4.0 m/s; the gap to a 3.0 m/s car peaks ~4–6 m around
t≈2–3 s (the car may exit the footprint briefly), then closes at ~1.0 m/s;
draws land every ~2.35 s on car-in-frame frames from ~t=4–6 s; at Stage-0's
~74% accept rate, first lock within ~2–4 such draws (~5–15 s).

**Rejected alternatives** (→ DECISIONS seed):
- *Blob-seeded CARRY (track-first, verify-later)* — init SAM2 on the blob
  before any VLM accept, decoupling lock from the draw wall entirely. Rejected:
  it surrenders target identity to "whatever moves" (the north star is
  language-selected targets; E3 showed identity-blind priors wrong-lock), and
  it is a much larger state-machine change. Chase-hold keeps the VLM as the
  only thing that can lock.
- *VLM draw-latency cut* — E5's DECISIONS entry already records no cheap
  headroom, and the s3.0a raw shows latency is not what binds: draws landed
  every 2.35 s for 73 s — on car-less frames. Faster wrong frames don't help.
- *Spawn-geometry sweep* (validate E10's 3.0 fail across headings/offsets) —
  unnecessary: the raw already exposes the mechanism (hover on blob loss +
  car never returns), which any standing-start geometry with the car
  outrunning a hovering copter reproduces.

## Code changes (already committed on this branch — Opus: do NOT edit these files)

| File | Change | Default behavior |
|---|---|---|
| `experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py` | `blob_chase_box()` helper (blob → box anchored on the sweep-center row); `--acquire-hold` gains `chase` (pre-lock, blob-visible frames append the blob's world position to `hist`, so the existing `hist_vel`/`pursuit_vel` blocks chase pre-lock); selfcheck gains a chase-box anchor assertion (sweep-center row strictly inside the rendered sweep span) | bit-identical for `none`/`motion` (the chase append is guarded by `acquire_hold == "chase"`); `--vmax` default still 2.5 |
| `experiments/2026-07-03-chase-acquire/run_e11.py` | the matrix runner (below); per-leg `--vmax` (3.5 m/s legs need 5.0) | — |

No changes to `cascade_pid.py`, `sitl_cam.py` (E10's `--vmax` threading and
world auto-extension already cover 3.0/3.5: `n_max = c(75)+20` ≈ 246/283 m).
Known bounded artifact, accepted by design: for <= 2.4 s after first lock the
pre-lock blob entries coexist in `hist` (maxlen 48 @ 20 Hz) with the E4
replay's box entries; the two anchor conventions differ by ~1 m, a <~0.5 m/s
transient in `hist_vel` that pursuit's position term absorbs (comment at the
append site).

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
Software versions are auto-captured per run by the manifest, as E2–E10.

One command runs everything (6 legs, snapshots each into `runs/<label>/`):

```bash
cd /home/gara/jetson
mkdir -p experiments/2026-07-03-chase-acquire/raw
echo "$(date -Is) EXEC-START chase-acquire" >> .claude/loop.log
.venv-ft/bin/python experiments/2026-07-03-chase-acquire/run_e11.py 2>&1 | tee experiments/2026-07-03-chase-acquire/raw/matrix.log
```

Legs, in order (common flags: `--loss-gate motion --dr pursuit --acquire-hold chase`):

| leg | `--speed` | `--vmax` | purpose |
|---|---|---|---|
| reg-2.5 | 2.5 | 4.0 | regression guard at the E10 ceiling: exact E10 s2.5 config except `chase` — the new mode must not break the passing speed (E10 baseline: 3/3, first_lock 2.30 s) |
| s3.0a/b/c | 3.0 | 4.0 | primary RQ — E10 "before" is s3.0 0/2 never-locked with `motion` |
| s3.5a/b | 3.5 | 5.0 | stretch probe (does not decide the RQ); vmax 5.0 keeps a 1.5 m/s closing margin |

Gotchas (baked into the runner, listed so you can recognize them):
- `phase3_sitl.py` clobbers `raw/phase3a-sitl/trial-<v>ms.{csv,mp4}` and
  `runs/phase3a-sitl/results.json` on every run — the runner snapshots per leg
  immediately; the csv/mp4 filename depends on the speed (e.g. `trial-3.0ms.csv`).
- A leg is killed at 20 min (E10 actuals: ~3 min/leg; 20 min = hung SITL).
- If SITL dies mid-matrix, re-run the whole matrix (~25 min) rather than
  surgering individual legs; `run_e11.py` re-executes all legs.
- New failure signature to recognize (not a rig fault): if a bad early blob
  seeds a garbage velocity, the copter can chase off north at vmax with no
  pre-lock timeout — visible in the csv as a monotonic `copter_n` runaway with
  `state=ACQUIRE`. That is a legitimate FAIL of the chase design; snapshot and
  record it, do not "fix" it.

## Verdict rules (mechanical — Opus does not deliberate)

The runner prints all of this; the rules it applies:

- **Per-leg gate:** PASS iff `trial["in_fov_frac"] >= 0.90 AND
  trial["recovered_after_occlusion"] == true` in the leg's
  `runs/<label>/results.json`.
- **RQ-E11 = YES** iff reg-2.5 PASS **and** >= 2/3 of s3.0 legs PASS.
- **reg-2.5 FAIL → CHASE-REGRESSION:** RQ-E11 = NO regardless of the 3.0
  results (chase broke a passing speed; 3.0+ numbers not comparable to E10).
  Finish the matrix anyway and record everything plainly; do not debug in
  this campaign.
- **New measured ceiling** (secondary): highest speed meeting its quota
  (2.5: 1/1, 3.0: >=2/3, 3.5: 2/2) with all lower rungs also meeting theirs;
  if reg-2.5 fails or s3.0 < 2/3, the ceiling stays "2.5 m/s (E10, unchanged)".
- **Per-FAIL-leg binding mode** (printed by the runner, verbatim E10 rules):
  `first_lock_s` null → "never-locked (first-acquire)"; else the state at the
  start of the first >= 1 s contiguous `in_fov == 0` run after first lock:
  ACQUIRE → first-acquire, REGROUND/RETARGET → relock, CARRY → tracking-trail.
- **Abort:** leg killed at 20 min or missing `results.json` → snapshot what
  exists, mark INVALID, continue; **2 INVALID legs → stop, campaign verdict
  INVALID-RUN** (fix the rig outside this campaign, re-run fresh).

## Estimates (marked as estimates)

- Runtime: ~20–30 min total (6 legs × ~3–4 min incl. SITL+Jetson boot, per
  E10 actuals of ~3 min/leg).
- reg-2.5 PASS: ~85% (E10 s2.5 locked on draw 1 at t=2.30 s, so chase engages
  for at most ~1.3 s pre-lock; small trajectory perturbation only).
- s3.0 >= 2/3: ~50–60% (chase physics feasible per the gap analysis above;
  residual risks: blob/warp noise at 4 m/s ego-motion, Stage-0 ~74% accept on
  possibly-clipped frames, occlusion relock at only 1.0 m/s closing margin).
- s3.5 2/2: ~20% (gap peaks larger, ~7–9 m; blob quality at 5 m/s ego-motion
  untested).
- first_lock_s at 3.0: ~5–15 s. relock_walls at 3.0: expect < 10 s (E10 trend:
  relock falls with speed — 25.9 @1.5 → 6.8 @2.5).

## Results (TBD — Opus fills; one row per leg)

> **Ceiling qualifier: see E12 (`../2026-07-03-late-command/`).** The ">= 3.5 m/s" below
> was a draw-1 easy-spawn artifact — E12's hard-spawn re-run (`--acquire-delay 3.0`, gift
> frame removed) fails 3.5 **0/3** and passes 3.0, so the **chase-validated ceiling is 3.0
> m/s**, not 3.5. The reg-2.5 / s3.0 passes below stand; the s3.5 passes do not.

Ran 2026-07-03T13:40Z. Rig: host 3090 (SITL + SAM2 carry @1024) + Jetson Q8_0
acquire, **15 W + jetson_clocks**. Common flags `--loss-gate motion --dr pursuit
--acquire-hold chase`; `--vmax` per leg. Raw: `raw/matrix.log`, per-leg
`runs/<label>/{results.json,trial.csv,trial.mp4}`.

| leg | gate | in_fov_frac | recovered | first_lock_s | attempts | rejected | n_regrounds | relock_walls_s | carry_px_err_mean | binding mode (FAIL only) |
|---|---|---|---|---|---|---|---|---|---|---|
| reg-2.5 | PASS | 1.000 | True | 2.30 | 8 | 6 | 1 | 16.22 | 127.9 | — |
| s3.0a | PASS | 1.000 | True | 9.21 | 15 | 13 | 1 | 25.74 | 146.8 | — |
| s3.0b | PASS | 1.000 | True | 9.31 | 15 | 13 | 1 | 25.74 | 148.5 | — |
| s3.0c | PASS | 1.000 | True | 9.26 | 8 | 6 | 1 | 9.24 | 147.4 | — |
| s3.5a | PASS | 0.962 | True | 2.30 | 4 | 2 | 1 | 6.82 | 174.6 | — |
| s3.5b | PASS | 0.964 | True | 2.30 | 5 | 3 | 1 | 9.17 | 174.7 | — |

**RQ-E11 verdict: YES** — reg-2.5 PASS (no chase-regression: first_lock 2.30 s,
in_fov 1.000, byte-identical to E10 s2.5) **and** s3.0 **3/3** PASS. The chase-hold
makes first-acquire reliable at 3.0 m/s: where E10's `motion` hold left the s3.0 car
never-locked (in_fov 0.052, first_lock None), chase-hold keeps it in-frame across
draws until the VLM locks at **~9.2 s** (s3.0a/b took 15 acquire attempts / 13
rejected before the winning draw — chase bought that time; s3.0c locked on the same
schedule but relocked faster). Once locked, carry+pursuit hold in_fov **1.000** to
trial end.

**New measured ceiling: >= 3.5 m/s** (top rung tested — NOT pinned). s3.5 passed
**2/2** at `--vmax 5.0` (in_fov 0.96, first_lock 2.30 s, recovered through occlusion),
so the real ceiling is above 3.5 and E11 did not find it. The follow ceiling has moved
2.5 → **at least 3.5 m/s** in one lever; the E2-era "< 0.5" is now 7x behind.

**Estimate-vs-actual (diverged — chase over-performed):** Fable estimated reg-2.5
~85% (actual PASS), s3.0 >= 2/3 at ~50-60% (**actual 3/3**), s3.5 2/2 at ~20%
(**actual 2/2**). The pre-lock chase physics were more robust to 4-5 m/s ego-motion
blob/warp noise than estimated; no garbage-blob DR runaway occurred on any leg. Ceiling
was expected to *maybe* reach 3.0; it cleared 3.5 without a failing rung, so the probe
under-reached — the next campaign must test higher speeds to actually pin it. first_lock
at 3.0 landed at ~9.2 s (within the estimated 5-15 s); relock walls 9-26 s (higher than
the estimated < 10 s on the two legs that needed a full reground).

## Video deliverables (Opus cuts — DoD item 7)

Every leg's mp4 is snapshotted to `runs/<label>/trial.mp4` by the runner; the
"before" footage already exists in E10's snapshots. Cut 3 clips into `proof/`
(curated thesis clips, **committed**), caption each here with what it shows
and which run it came from. Re-encode for clean seeks as E10 did:
`ffmpeg -ss <t0> -t <dur> -i <src> -c:v libx264 -pix_fmt yuv420p proof/<name>.mp4`

Cut 2026-07-03T15:42Z (re-encoded libx264 for clean seeks):

1. `proof/e11-before-hover.mp4` — **the failing behaviour (before).** Source:
   E10 `../2026-07-03-fast-follow-ceiling/runs/s3.0a/trial.mp4`, t=0–25 s: E10's
   3.0 m/s leg with `motion` hold — the car crosses and escapes the FOV early,
   the copter hovers over empty road in ACQUIRE (never locks, in_fov 0.052).
2. `proof/e11-s3.0-chase.mp4` — **the RQ moment (after).** Source: E11
   `runs/s3.0a/trial.mp4`, t=0–30 s: standing-start blob-pursuit chase keeps the
   3.0 m/s car in-frame across draws, first VLM lock at ~9.2 s, then follow. Same
   speed and spawn as clip 1 — this is the direct before/after.
3. `proof/e11-occlusion-relock.mp4` — **holding at the new ceiling.** Source: E11
   `runs/s3.5a/trial.mp4`, t=22–48 s (occlusion window ~30–35 s): 3.5 m/s
   (`--vmax 5.0`), the bridge occlusion and relock at the highest passing speed —
   in_fov 0.96, recovered.

## Closeout checklist (Opus)

1. Fill Results table + verdicts above; record estimate-vs-actual divergences;
   set the Status line to COMPLETE + verdict.
2. Cut + caption + commit the video deliverables into `proof/` (section above).
3. Append one row per leg (or one summary row per speed) to
   `docs/results/part4-end-to-end.md` under E11.
4. Append RQ-E11 + one-line verdict to `docs/questions/part4-end-to-end.md`.
5. Append the DECISIONS entry to `docs/decisions/part4-end-to-end.md`: chose
   chase-hold (pre-lock blob track feeds the existing pursuit DR) over
   blob-seeded CARRY / VLM draw-latency work / spawn-geometry sweep
   (rationales in Context above); include the audit refinement (E10's 3.0
   failure = car-in-frame time under a hover-on-blob-loss control law, not
   VLM draw repeatability).
6. Commit on this branch: `E11 chase-acquire: <verdict summary>`.
   Do NOT merge — the parent session merges.
