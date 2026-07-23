# E18-n25 — the cold-acquire staleness effect, powered to n=25 (R-34)

- **Pre-registered:** 2026-07-23T19:40Z (Madrid wall-clock), BEFORE any run.
- **Status:** DONE 2026-07-23T20:45Z — YES [delivery-lag], ORACLE 23/25 vs COLD 3/25,
  deflated McNemar p = 4.01e-05 (survives per-Part and global Holm). See `## Results`.
- **Task:** `thesis/REMEDIATION.md` R-34. `E18-cold-acquire-vs-warm-oracle` is the
  closest miss in the whole claim registry — `b=5, c=0, n_eff=6, exact McNemar
  p=0.0625`, reachable, one discordant pair short of alpha. It is also Chapter 6's
  only positive claim: *the ~4.85 s cold blocking acquire delivers a box that is
  already stale on a moving target*, the finding that motivated the whole of Part V.
- **Rig:** host 3090 runs SAM2.1-hiera-tiny @1024 carry, rate-capped to CARRY_HZ =
  6.15 (E1's on-Orin co-resident TensorRT rate). R-16 has since retired 6.15 for the
  deployed 1024-eager stack (real rate 2.69 Hz); it is kept here purely for
  E18-comparability, and it is immaterial to this claim — the binder is the ~4.85 s
  real-Jetson acquire that drops ~146 frames (COLD leg), not the carry cap. Leg A's
  anchor tier IS real Jetson wall time via `JetsonBackend` (self-boot per run, q8_0
  terse, 15 W + jetson_clocks). No SITL, no world — perception on recorded footage only.
- **Code under test:** the E18 stack, with one deliberate correction. The pre-run
  smoke exposed a latent artifact in `replay_e18`'s oracle leg: it stamps the seed
  event at `video.t()`, which fires AFTER the ~1 s SAM2 init on frame 0, so the GT[0]
  box is scored at frame ~33 instead of frame 0. On E18's warmer GPU that init was
  0.34 s (frame ~10, still overlapping) so it hid; here it is ~1.1 s and the oracle
  spuriously FAILS `genuine_lock` on fast targets. That is init latency leaking into
  the timeline, not a modeled delay. P5.2a's `replay_e24` already fixed it
  (schedule-fixed deliver frame + `coverage_realtime` zeroes the wall clock at
  delivery); `replay_e18_clean.py` reuses that exact machinery at a frame-0 onset.
  The scoring metric (`score_run`) and the carry/VLM stack are otherwise identical to
  E18. `run_e18_n25.py` is the 40-line driver (the P5.2a pattern of a frozen harness
  over a clip list).
- **Venv:** `.venv-ft` (pins in `requirements-ft.lock.txt`).

## Why this is a re-run and not a new question

E18 answered its RQ at **n=6** (car clips) and landed *just* outside alpha because
six clips gave only six effective observations and five of six flipped. Nothing about
the design was unreachable — it was **underpowered**. R-34 asks for the same two
paired arms on **25 distinct UAV123 sequences**, one cell per sequence (the R-29
lesson: n counts clusters, not cells — so no within-clip reps to inflate n).

## The two arms (identical to E18 leg A / leg B)

- **COLD (leg A)** — E18's cold blocking acquire. A full-frame VLM grounding pass
  fires at frame 0; it blocks ~4.85 s of real Jetson wall time while `WallClockVideo`
  drops the ~146 intervening frames; the box (correct on the frame it saw) is
  delivered STALE at the arrival frame and time-stamped there. SAM2 carry seeds from
  it; REGROUND on loss with the E14/E16 mask gate (app-tau 12.0).
- **ORACLE / warm oracle (leg B)** — E18's control. SAM2 carry seeded from the GT
  frame-0 box, NO VLM, REGROUND disabled. Isolates the carry tier on real texture; a
  fresh (non-stale) seed at frame 0.

**Per-clip PASS** (E18 `score_run`, unchanged): `genuine_lock` (first accepted box
hits GT at IoU ≥ 0.25 at its delivery frame) **AND** `coverage ≥ 0.50` (fraction of
GT-valid frames after lock where the held box hits IoU ≥ 0.25, scored at native fps).
**n = 1 per leg per clip** (E18 found n=2 reps bit-identical; one cell per sequence is
the R-29-correct choice, not a within-clip rep).

## Clip set (frozen — P5.2a's 25, `clips.json`)

The P5.2a warm-start-generalization bank: 25 UAV123 sequences across 5 target classes
(car, boat, person, cyclist, wakeboarder), captions frozen and generic (`the car`,
`the boat`, …) — authored once for P5.2a, not tuned here (E18 D6: no caption tuning
after seeing results). Using the broad set rather than E18's 6 cars is deliberate and
is what R-34 asks: if the cold arm scores well above 1/6 on a broader set, E18's
original margin was a 6-clip artefact — **that is also content**, pre-registered here.

## Hypothesis and the pre-registered decision rule

- **H1 (primary):** paired McNemar (ORACLE vs COLD PASS) over the 25 clips is
  significant at alpha = 0.05 after deflation to distinct clips and Part-IV Holm.
- **Deflation:** the R-29 rule. One cell per clip, so clustering is by *source
  sequence*: `car3`/`car3_s` and `person1`/`person1_s` share source video (P5.2a's
  own note) → collapse those pairs; ICC calibrated on this run's paired outcome, upper
  95 % bound, `collapsed_floor` published. Expected `n_eff` ≈ 23-25.
- **PASS (H1 holds):** register `E18-...-n25` as GATE PASS; E18 promotes from
  "underpowered negative that motivated Part V" to "confirmed at n=25"; Chapter 6
  gains a survivor.
- **FAIL / surprise (pre-registered):** if COLD PASS ≫ 1/6 (say ≥ 10/25) the effect
  is weaker than E18's 6-clip snapshot implied — record it plainly, keep E18's n=6
  verdict as as-run, and state the broader-set attenuation. Either way the number is
  the deliverable.

## Independent corroboration already on disk (disclose, don't double-count)

P5.2a ran **ORACLE and COLD on these same 25 clips at a mid-flight onset t_p = 8 s**
(the warm-start select regime). Re-scored with E18's PASS rule, that data gives
**ORACLE 22/25 vs COLD 5/25, b=17 c=0** — the E18 arms at n=25 in a *different* onset
regime. This campaign's fresh **frame-0** run is the primary (matches E18's exact
onset and is independent of P5.2a's COLD runs, so no shared-arm dependency); the
P5.2a re-score is reported as a second regime that agrees. The delivery lag (~146 fr)
is identical in both regimes, which is why the onset shift is immaterial to a
delivery-staleness claim (P5.2b already showed the effect is delivery-lag, flat in
speed).

## Estimates (mark vs actual when done)

- Matrix wall time: ~1 h (leg B ~30 s/clip pure replay ×25; leg A ~60-90 s/clip incl.
  Jetson boot + real acquire ×25). 3090 idle at 8 W, Jetson up (both checked).
- Expected COLD PASS: **4-7/25** (P5.2a COLD scored 5/25 at t_p; frame-0 should be
  similar). Expected ORACLE PASS: **20-24/25** (carry is real-video home turf).
- Expected discordant b (ORACLE>COLD): **14-19**, all one-way → p far below alpha even
  deflated. E18's n=6 needed just one more pair; n=25 should clear comfortably.

## Results (filled 2026-07-23T20:45Z)

Matrix ran `2026-07-23T19:45–20:20Z`, 50 result files, 0 INVALID. Reproduce the
scoring with `../../.venv-ft/bin/python score.py` (raw capture: `raw/score.txt`).
`gl` = `genuine_lock`; `cov` = coverage; PASS = `gl AND cov >= 0.50`.

| clip | class | O | C | O gl/cov | C gl/cov | C mean_iou | disc |
|---|---|---|---|---|---|---|---|
| car10 | car | Y | n | True/1.0 | True/0.2137 | 0.0928 | O>C |
| car3 | car | Y | n | True/0.9831 | False/0.0 | 0.0 | O>C |
| car9 | car | Y | n | True/0.9931 | False/0.0 | 0.0 | O>C |
| car14 | car | Y | n | True/0.9 | False/0.0009 | 0.0106 | O>C |
| car7 | car | n | n | True/0.3396 | False/0.0 | 0.0032 | = |
| boat2 | boat | Y | Y | True/1.0 | True/0.9909 | 0.2998 | = |
| boat3 | boat | Y | n | True/1.0 | False/0.9974 | 0.6889 | O>C |
| person15 | person | Y | n | True/1.0 | False/0.0235 | 0.0768 | O>C |
| bike1 | cyclist | Y | n | True/0.9874 | False/0.0 | 0.0 | O>C |
| person13 | person | Y | n | True/0.966 | False/0.0 | 0.0 | O>C |
| person6 | person | Y | n | True/0.9256 | False/0.0 | 0.0 | O>C |
| person1 | person | Y | n | True/0.9312 | False/0.0 | 0.0 | O>C |
| wakeboard8 | wakeboarder | Y | n | True/0.7097 | False/0.0 | 0.0 | O>C |
| wakeboard3 | wakeboarder | Y | n | True/0.7424 | False/0.0 | 0.0 | O>C |
| car18 | car | Y | n | True/0.9851 | False/0.0 | 0.0 | O>C |
| car17 | car | Y | n | True/0.9839 | False/0.0 | 0.0 | O>C |
| car4_s | car | Y | n | True/0.8855 | False/0.0 | 0.0008 | O>C |
| car1_s | car | n | Y | True/0.4095 | True/0.5015 | 0.2868 | C>O |
| car3_s | car | Y | n | True/0.8392 | False/0.0043 | 0.0115 | O>C |
| person18 | person | Y | Y | True/1.0 | True/0.6381 | 0.2834 | = |
| person20 | person | Y | n | True/0.9647 | False/0.0 | 0.0015 | O>C |
| person10 | person | Y | n | True/0.8234 | False/0.0 | 0.0 | O>C |
| person1_s | person | Y | n | True/0.7306 | False/0.0743 | 0.0462 | O>C |
| wakeboard6 | wakeboarder | Y | n | True/0.5665 | False/0.0 | 0.0 | O>C |
| wakeboard2 | wakeboarder | Y | n | True/0.6821 | False/0.0 | 0.0 | O>C |

- **ORACLE PASS: 23/25 &nbsp; COLD PASS: 3/25 &nbsp; b(O>C)=21 c(C>O)=1.**
- **Deflation (R-29):** rows cluster by source video; only `car3`/`car3_s` and
  `person1`/`person1_s` are two-cell clusters and both are internally concordant
  (both O>C), so ICC(1) upper 95 % = 1.0 collapses them fully → **n_eff = 23**,
  and the discordants collapse to **b=19, c=1** (`collapsed_floor = 23`, published).
- **Exact McNemar p — raw 1.10e-05 / deflated 4.01e-05 / Holm (Parte IV) 3.61e-04
  / Holm (global) 1.36e-03.** All well under alpha = 0.05.
- **Verdict: YES [delivery-lag].** E18 promotes from underpowered negative
  (p = 0.0625 at n=6) to **confirmed at n=25**. It is now Part IV's only
  inferential survivor and the 9th global-Holm survivor (`E18-...-n25` in
  `thesis/stats-report.md`).
- **Estimate-vs-actual:** COLD expected 4–7/25 → **actual 3/25** (lower — effect
  did not attenuate on the broad set, it strengthened); ORACLE expected 20–24 →
  **23** (in range); b expected 14–19 → **21** (higher, stronger than E18's snapshot).
  The pre-registered surprise case (COLD ≥ 10/25) did **not** fire.
- **What surprised:** (1) the one C>O cell is `car1_s` — ORACLE genuine-locks but its
  carry drifts to coverage 0.41 < 0.50, while COLD's stale box happens to seed on the
  slow-moving car and holds 0.50; a carry-quality miss, not a cold-arm win. (2) `car7`
  is the one concordant fail — ORACLE genuine-locks but coverage 0.34 (fast target,
  carry loses it mid-clip); COLD never locks. (3) `boat3` COLD reaches coverage 0.9974
  yet FAILS: its delivered box misses GT at the delivery frame (`gl = False`), so
  post-lock coverage is scored but the lock itself never happened — exactly the
  staleness failure the metric is built to catch.

## Proof (`proof/`, from `make_proof.py`)

- `discordant-bike1.png` — the discordant pair verified by the look-at-it rule:
  `bike1` frame 300, ORACLE holds the green box on the cyclist (locked), COLD reads
  `LOST` with only the red GT box (the stale frame-141 seed never recovered).
- `pass-grid.png` — per-clip PASS grid, ORACLE 23/25 (green) vs COLD 3/25; the lone
  C>O cell (`car1_s`) and the concordant fail (`car7`) are both visible.
- `effect-3regimes.png` — the effect across three regimes: E18 as-run (n=6, 6/6 vs
  1/6), this run (frame-0, n=25, 23/25 vs 3/25), and the P5.2a re-score (t_p=8 s,
  n=25, 22/25 vs 5/25). The delivery lag (~146 frames) is identical in all three, so
  the onset shift is immaterial — the win is delivery-lag removal (P5.2b: flat in speed).

## Definition of done (CLAUDE.md)

1. This README filled (results, verdict, estimate-vs-actual).
2. RESULTS row → `docs/results/part4-*.md`.
3. QUESTIONS entry (RQ-R34 + verdict) → `docs/questions/part4-*.md`.
4. DECISIONS entry if a non-trivial choice was made (broad-set vs car-only; fresh
   frame-0 vs P5.2a-reuse).
5. `thesis/claims.json`: register `E18-...-n25` with `n_effective`, `icc`, counts,
   `independence_note`; regenerate `thesis/stats-report.md`; `make test` green.
6. 2-3 proof deliverables in `proof/`, committed, captioned.
7. Dataset stays OUT of git (`data/` under the E18 dir is gitignored).
