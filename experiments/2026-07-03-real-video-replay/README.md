# E18 real-video-replay — does the deployed two-tier stack hold a real target on real aerial footage at true cadence?

- **Pre-registered:** 2026-07-03T22:58Z (Madrid wall-clock)
- **Status:** COMPLETE (2026-07-03). RQ-E18 = **NO [grounding-bound]** — carry
  is real-video-ready (B 6/6) but the ~4.85 s acquire lands stale on moving
  targets (A 1/6 PASS). Results + proof clips below.
- **Roles:** design + audit by Fable (this README + `replay_source.py`, selfcheck
  green). Opus does Steps 1-6: dataset acquisition, `replay_e18.py` wiring per the
  spec below, the matrix, Results, ledgers, proof clips. Every judgment is pre-made
  below; if a case is not covered by a rule here, record it verbatim and mark the
  leg `UNRULED`, do not invent a rule.
- **Branch:** `experiment/real-video-replay` (from clean main `997f08e`, the E17
  merge — the code under test IS current main).
- **Rig:** host 3090 runs the replay + StreamCarry (SAM2.1-hiera-tiny @1024, rate-
  capped, see D3); the Jetson runs the VLM (Qwen2-VL-2B Q8_0 terse, self-boot per
  trial as in E16). Jetson at 15W (`sudo nvpmodel -m 0`) + `sudo jetson_clocks`
  (NOPASSWD; there is NO MAXN on this board). No SITL, no ArduPilot, no world —
  perception only (see D1).
- **Versions:** same stack and venv (`.venv-ft`) as E14-E17 — pins in
  `requirements-ft.lock.txt`. Zero deltas to existing code; E18 adds only new files
  in this campaign dir.

## Context — why this experiment

Everything E2-E17 ran on Gazebo-style synthetic renders (`sitl_cam.py`: flat
texture, polygon cars). Real footage differs exactly where the stack is most
exposed: real texture/clutter for the VLM anchor, real appearance statistics for
the SAM2 mask and the E14/E16 mask gate, motion blur, compression, real target
scale. `grounding/deploy/video.py` ("Level 1") already showed the anchor alone on
real video; its own docstring defers "Level 2" — the fast tier holding lock between
anchors — to later. E18 is Level 2, scored quantitatively against dataset GT
instead of eyeballed.

## RQ-E18

**On real aerial car-tracking footage replayed at wall-clock rate (frames dropped
during inference), does the deployed stack — NL full-frame acquire, SAM2 carry,
mask-gated REGROUND on loss — genuinely lock and then hold the target, scored
against dataset ground truth?**

Per clip, from `score_run` (see `replay_source.py`): **PASS** = `genuine_lock`
(first accepted box hits GT at IoU >= 0.25) AND `coverage` >= 0.50 (fraction of
GT-valid frames after lock where the held box hits IoU >= 0.25, scored at native
fps so staleness and declared-lost time cost coverage). A clip's PASS is the
better of its n=2 full-stack reps (rate reported alongside).

- **YES** iff >= 4 of 6 clips PASS.
- **PARTIAL** iff 2-3 of 6 PASS.
- **NO** iff <= 1 of 6 PASS.
- **NOT-MEASURABLE** iff the dataset cannot be obtained (D2 fallback also fails),
  a selfcheck fails, or the Jetson VLM server cannot be brought up.
- Attribution suffix from the oracle-init B legs (D5): append
  **[grounding-bound]** if >= 2 clips FAIL leg A while PASSing leg B; append
  **[carry-bound]** if >= 2 clips FAIL leg B.

Any verdict is a full answer. A NO with clean attribution (which tier breaks on
real data) is thesis content — it is the sim-to-real gap, measured.

## Design decisions (pre-registered, with rationale)

- **D1 — perception-only, no closed loop.** Prerecorded video has no actuation;
  closed-loop follow stays SITL (E10/E12 ceilings stand). E18 tests acquire ->
  carry -> REGROUND end-to-end on real appearance. Given up: nothing — this is the
  only honest option on recorded footage.
- **D2 — dataset: UAV123, car-class sequences.** Real drone footage, per-frame GT
  boxes (`x,y,w,h`, NaN = absent), 30 fps, and the exact thesis scenario (aerial
  vehicle tracking). Fallback if the download is infeasible after reasonable
  effort (~2 h): VisDrone2019-SOT, same selection rules; record the swap and the
  reason here. Given up: own-drone footage (no GT, no quantitative claim) — can be
  a qualitative extra later, not part of the scored matrix.
- **D3 — host rig with the measured on-device carry cap, not on-Jetson
  orchestration.** The carry tier runs on the 3090 but is rate-capped to
  **6.15 FPS** (E1's measured co-resident TensorRT number on the Orin); the anchor
  tier is REAL Jetson wall time (ssh round trip included, as in
  `deploy/video.py`'s measured ~4.8 s full-frame acquire). Rationale: cadence is
  already pinned by E1; the new variable in E18 is the DATA, and confounding it
  with a new on-device replay harness adds failure modes without adding
  information. Given up: exact on-device timing (720p SAM2 on Orin may run
  slightly under 6.15 FPS measured at 640x480 — record this as a known
  approximation; an on-Jetson replay is the natural E19 if E18 is YES).
- **D4 — SITL-coupled levers are OUT; declare-loss is mask-empty streak.** The
  motion loss gate, motion/chase acquire-hold, pursuit DR, and blob-chase all
  consume SITL pose/world state that does not exist on replay footage — they are
  structurally absent, not disabled. Loss = carry emits empty mask (box None) for
  **LOSS_S = 1.0 s** of consecutive steps at the capped rate (the E4 score gate is
  NOT used: E4 rejected it as over-firing). During declared loss the pipeline
  emits `(t, None)` — scored as 0, honestly. REGROUND = full-frame re-acquire with
  the **E14/E16 mask gate** (`mask_descriptor` of the proposal vs the init-mask
  descriptor, accept iff distance <= app-tau 12.0, the E14 default) — the mask
  gate is appearance-only, so it transfers; it is the one identity lever E14-E17
  validated. Given up: hold-stale-box during loss and periodic ROI re-anchor
  (deployed in the anchor-only demo) — both are levers for a follow-up, not part
  of the deployed carry stack under test.
- **D5 — oracle-init control leg (B) per clip.** Init StreamCarry from the GT
  frame-0 box with NO VLM at all (carry + capped rate only, REGROUND disabled;
  on loss it stays lost). B isolates the carry tier on real texture; A-vs-B
  attributes every failure to grounding or carry. n=1 (carry is the less
  stochastic tier).
- **D6 — captions are authored from frame 0 only, before any run.** For each
  clip, write the NL caption (class + colour/context visible in frame 0, the way
  an operator would phrase it) into the table below BEFORE the first full-stack
  run. No caption tuning after seeing results — a caption that fails is a result.

## Clip selection rules (apply BEFORE any stack run)

From UAV123 `car*` (and `truck*`/`van*` if needed to reach 6) sequences:

1. Target class: road vehicle.
2. Length >= 900 frames (30 s at 30 fps). Truncate runs at 4500 frames (150 s,
   the E14-E17 trial length) if longer.
3. Pick **4 "plain"** clips (single dominant vehicle) and **2 "distractor"**
   clips (at least one same-class vehicle near the target at some point —
   judged by scanning the video, allowed; scanning GT overlap is also allowed).
   If the set offers a clip with a GT NaN gap (full occlusion), prefer it into
   the six and flag it `occ` — it exercises REGROUND for free.
4. Record for each chosen clip: sequence name, frame count, fps (UAV123 nominal
   30), native resolution, why chosen, caption (D6). Chosen clips and captions
   go in the table below before the matrix starts.

## Harness spec — `replay_e18.py` (Opus writes this, ~150-250 lines)

Reuse, do not rewrite: `WallClockVideo` / `load_uav123_gt` / `score_run` /`iou`
from `replay_source.py` (this dir); `StreamCarry` from
`experiments/2026-07-01-temporal-acquire-carry/stream_carry.py`;
`mask_descriptor` from
`experiments/2026-07-01-temporal-acquire-carry/phase3_sitl.py`; the Jetson
submit path (JetsonBackend + terse contract + self-boot) cribbed from
`phase3_sitl.run_trial`'s `_acquire`/`submit` (lines ~346-360) — import if
clean, copy the ~15 lines with a provenance comment if the SITL imports drag.
Do NOT import PermanenceController (world-coupled, D4).

Single-threaded loop — a blocking VLM call is CORRECT here, wall-clock frame
drop is the realism (no threads, no queues):

```
video = WallClockVideo(seq_dir, fps=30); events = []; video.start()
state = ACQUIRE
while (grab := video.latest()) is not None:
    i, frame = grab
    if state == ACQUIRE (or REGROUND):
        box = submit(frame, caption)          # blocks ~4.8 s; frames drop meanwhile
        if box is None or degenerate: continue        # retry on the then-current frame
        if state == REGROUND and mask_gate_rejects(box, frame): log reject; continue
        carry = StreamCarry(predictor, frame, box); init descriptor if ACQUIRE
        events.append((video.t(), box)); empty_streak = 0; state = TRACK
    else:  # TRACK
        sleep to hold <= CARRY_HZ = 6.15      # D3 cap
        mask, box = carry.step(frame)
        if box is None: empty_streak += 1
            if empty_streak >= LOSS_S * CARRY_HZ: events.append((video.t(), None)); state = REGROUND
        else: empty_streak = 0; events.append((video.t(), box))
```

- Leg B: skip submit entirely; init from `gt[0]`; REGROUND disabled (on loss,
  record `(t, None)` once and keep stepping carry — SAM2 may self-recover; that
  is part of what B measures).
- Every run writes `runs/<leg>/results.json`: the events list, the `score_run`
  dict, config echo (leg, clip, caption, seed-irrelevant), wall duration, and
  `runs/<leg>/overlay.mp4` (held box + GT box drawn per frame — this is also
  the proof-clip source).
- `--selfcheck` mode: fake clock + synthetic frames + a stub submit, asserting
  the state machine transitions ACQUIRE->TRACK->REGROUND->TRACK. Run it green
  before the matrix.

## Matrix (18 runs + smoke)

| leg | clips | init | REGROUND | n | purpose |
|---|---|---|---|---|---|
| smoke | 1 short clip | VLM | mask gate | 1 | end-to-end plumbing before the matrix |
| A-full | 6 | VLM caption | mask gate, app-tau 12.0 | 2 | the RQ |
| B-oracle | 6 | GT frame-0 box | disabled | 1 | attribution control (D5) |

Order: smoke, then all B (cheap, no Jetson), then A. Jetson 15W + jetson_clocks
before any A leg; log `nvpmodel -q` output into `raw/`.

## Estimates (mark vs actuals when done)

- Dataset download: 1-3 h (UAV123 is ~13 GB; only `car*` sequences + anno are
  needed if a partial fetch is possible).
- Matrix wall time: ~2 h (18 runs x 30-150 s of wall-clock replay + Jetson boots).
- B-oracle: 5-6/6 PASS expected (SAM2 is trained on real video; this should be
  its home turf — a B failure is a bigger finding than an A failure).
- A-full: genuine_lock on ~4-5/6 (the Phase-3 LoRA was trained on RefDrone — real
  drone imagery — so acquire is in-domain-ish; the risk is small/low-contrast
  targets and REGROUND proposal quality, the E16 upstream failure mode, now on
  real clutter). Overall estimate: **PARTIAL-to-YES, 3-5/6 PASS**, coverage
  0.5-0.7 on passing clips.

## Dataset (Step 1 — done 2026-07-03)

- **Source:** UAV123 (D2, no fallback needed). HF mirror
  `https://huggingface.co/datasets/xche32/UAV123/resolve/main/UAV123.tar.gz`
  (the official KAUST Google-Drive tarball is the same data; the HF mirror is a
  direct `curl`, no browser/gdown). Downloaded 2026-07-03. Tarball size
  14 033 813 268 bytes (~14 GB), gzip.
- **What was kept:** the full dataset does not fit — disk hit ENOSPC at 100% on
  the 14 GB extract. Selectively extracted only the 6 chosen `car*` sequences +
  all anno (`data/UAV123/{data_seq,anno}/UAV123/`, ~1.1 GB) and **deleted the
  tarball** to reclaim 14 GB. Re-downloadable from the URL above if needed.
- **`_s` sequences excluded** (flight-simulator synthetic, not real footage, per
  D2). **Split subsequences (`carN_M`) excluded** — they share a parent image
  dir with frame offsets; standalone sequences align 1:1 to their anno file
  (verified: jpg count == anno line count, first frame `000001.jpg`, all six).

## Chosen clips + captions (D6 — locked BEFORE first A run)

All UAV123 `car*`, 1280x720, 30 fps nominal, none over the 4500-frame cap (no
truncation). Captions authored from frame 0 only (D6), by montage inspection.

| clip | frames | res | plain/distractor/occ | why chosen | caption |
|---|---|---|---|---|---|
| car3 | 1717 | 1280x720 | plain | single dominant vehicle, clean | the red car |
| car9 | 1879 | 1280x720 | plain | single dominant vehicle | the white car |
| car14 | 1327 | 1280x720 | plain, occ | 77 NaN GT gap (full occlusion) — exercises REGROUND for free | the red car |
| car18 | 1207 | 1280x720 | plain | oblique test-track view, real scale change | the red car |
| car7 | 1033 | 1280x720 | distractor, occ | 73 NaN gap + same-class cars beside target (~f520, ~f780) | the silver car |
| car10 | 1405 | 1280x720 | distractor | van + white car beside target (~f700) | the red car |

## Results (2026-07-03, matrix complete)

Rig: host 3090 (SAM2.1-hiera-tiny @1024, capped 6.15 Hz) + Jetson Orin Nano
q8_0 terse, 15W + jetson_clocks (`raw/jetson-power.txt`). 18 runs + smoke, all
valid. Per-clip PASS = better of n=2 A reps; PASS iff `genuine_lock` AND
`coverage` >= 0.50.

| clip | leg | rep | t_lock (s) | genuine | coverage | mean_iou | n_scored | gate_rej | leg verdict |
|---|---|---|---|---|---|---|---|---|---|
| car3 | B | 1 | 0.34 | True | 0.984 | 0.641 | 1706 | 0 | PASS |
| car3 | A | 1 | 4.89 | False | 0.976 | 0.595 | 1570 | 0 | FAIL (stale acquire) |
| car3 | A | 2 | 4.87 | False | 0.976 | 0.594 | 1570 | 0 | FAIL (stale acquire) |
| car9 | B | 1 | 0.34 | True | 0.990 | 0.788 | 1868 | 0 | PASS |
| car9 | A | 1 | 4.88 | False | 0.993 | 0.781 | 1732 | 0 | FAIL (stale acquire) |
| car9 | A | 2 | 4.88 | False | 0.993 | 0.781 | 1732 | 0 | FAIL (stale acquire) |
| car14 | B | 1 | 0.34 | True | 0.915 | 0.585 | 1239 | 0 | PASS |
| car14 | A | 1 | 4.82 | False | 0.903 | 0.550 | 1105 | 0 | FAIL (stale acquire) |
| car14 | A | 2 | 4.82 | False | 0.903 | 0.550 | 1105 | 0 | FAIL (stale acquire) |
| car18 | B | 1 | 0.34 | True | 0.987 | 0.703 | 1196 | 0 | PASS |
| car18 | A | 1 | 4.81 | False | 0.711 | 0.544 | 1062 | 1 | FAIL (stale acquire) |
| car18 | A | 2 | 4.81 | False | 0.711 | 0.543 | 1062 | 1 | FAIL (stale acquire) |
| car7 | B | 1 | 0.35 | True | 0.993 | 0.743 | 949 | 0 | PASS |
| car7 | A | 1 | 4.81 | False | 0.285 | 0.227 | 815 | 0 | FAIL (stale acquire + REGROUND drift) |
| car7 | A | 2 | 4.81 | False | 0.285 | 0.228 | 815 | 0 | FAIL (stale acquire + REGROUND drift) |
| car10 | B | 1 | 0.34 | True | 1.000 | 0.806 | 1394 | 0 | PASS |
| car10 | A | 1 | 4.84 | True | 1.000 | 0.797 | 1259 | 0 | **PASS** |
| car10 | A | 2 | 4.85 | True | 1.000 | 0.796 | 1259 | 0 | **PASS** |

Per-clip roll-up: **A PASS = 1/6** (car10 only). **B PASS = 6/6.**

- **RQ-E18 verdict: NO [grounding-bound]** (A PASS 1/6 <= 1; 5 clips — car3,
  car9, car14, car18, car7 — FAIL leg A while PASSing leg B, so the binding tier
  is the acquire/grounding path, not carry). No UNRULED legs: every leg is
  covered by the pre-registered PASS + attribution rules.
- **Estimate-vs-actual:**
  - Dataset download: est. 1-3 h — **actual ~1 h** (HF mirror direct `curl`, no
    KAUST Drive/gdown needed; no VisDrone fallback). Extraction hit ENOSPC on the
    full 14 GB, resolved by selective extract of the 6 seqs + delete tarball.
  - Matrix wall time: est. ~2 h — **actual ~35 min** (B ~5 min total, A legs
    ~35-63 s each incl. Jetson self-boot).
  - B-oracle: est. 5-6/6 PASS — **actual 6/6** (carry is real-video home turf,
    cov 0.92-1.00). Estimate held.
  - A-full: est. genuine on ~4-5/6, overall PARTIAL-to-YES 3-5/6 — **actual 1/6,
    NO.** Estimate WRONG, and the reason is the finding below: the estimate
    assumed acquire *accuracy* was the risk; the actual binder is acquire
    *latency*.
- **What broke / what surprised:**
  - **The acquire lands stale, not wrong.** The 4.8-4.9 s full-frame VLM acquire
    (t_lock ~4.85 s on every A leg) computes a *correct* box on the frame it saw,
    but by the time it returns the target has moved ~146 frames (30 fps). The box
    is time-stamped at arrival and scored there, so `genuine_lock` (first accepted
    box vs GT at the arrival frame) misses on 5/6 clips. Proof it's staleness not
    misgrounding: SAM2 latches the *right* car from that box and coverage on the
    three loss-free clips (car3/car9/car14) is 0.90-0.99 — carry corrects the stale
    lock within ~5 frames. So [grounding-bound] is the right *tier* (the binder
    lives in the acquire path) but the mechanism is **latency vs target motion,
    not model accuracy.**
  - **car10 passes because its target is slow at t=0** — a frame-0 box still
    overlaps GT ~146 frames later, so genuine_lock holds. It is the existence
    proof that the stack works end-to-end when acquire latency < target
    displacement time; the other five just move too fast for a ~5 s acquire.
  - **REGROUND inherits the same staleness and the mask gate can't catch it.**
    car7 (occlusion clip) is the only A leg whose *carry* also collapses (cov
    0.28 vs B 0.99): the 73-frame occlusion trips a loss, REGROUND fires a fresh
    full-frame acquire that ALSO lands stale, and the appearance-only E14/E16 mask
    gate accepts it (gate_rej=0 — right colour, wrong place) so carry re-latches
    off-target and drifts. car18 shows the milder version (1 gate-reject, cov
    0.71). The mask gate guards *identity*, not *position* — it has no defence
    against a stale-but-right-appearance box.
  - **Net thesis point:** the deployed carry tier is real-video-ready; the
    deployed *acquire cadence* (~4.85 s) is the sim-to-real wall. On UAV123 speeds
    a single blocking full-frame acquire cannot land on target. Natural follow-ups
    (out of E18 scope): motion-compensated acquire (predict target forward by the
    measured latency), a faster/ROI acquire, or a position-aware REGROUND gate.

## Proof clips (`proof/`, committed)

- **`car10_A_PASS.mp4`** — leg A, car10 (the one A PASS). Green = held box, red =
  GT. Acquire lands ~4.85 s in and still overlaps the slow-moving target;
  genuine_lock True, coverage 1.00 for the rest of the clip. End-to-end stack
  working on real footage.
- **`car7_A_FAIL.mp4`** — leg A, car7 (occlusion + distractor). The visible
  failure: after the mid-clip occlusion trips a loss, REGROUND re-acquires stale
  and the mask gate accepts it, so the green box drifts off the target (coverage
  0.28). The REGROUND-staleness failure mode.
- **`car9_A_vs_B.mp4`** — the attribution pair, same clip stacked. Top = leg A (NL
  VLM acquire, genuine_lock FALSE — box locks ~4.88 s late and lands stale before
  carry recovers, cov 0.99). Bottom = leg B (oracle GT-init carry, PASS, cov
  0.99). Identical carry quality; the only difference is the stale VLM acquire —
  this is the [grounding-bound] attribution, visualised.

## Definition of done (per CLAUDE.md)

1. This README completed (clips, captions, results, verdict, estimate-vs-actual).
2. RESULTS row(s) -> `docs/results/part4-*.md`.
3. QUESTIONS entry (RQ-E18 + one-line verdict) -> `docs/questions/part4-*.md`.
4. DECISIONS entries (D2 dataset choice, D3 rig choice) -> `docs/decisions/part4-*.md`.
5. SOURCES: UAV123 (or fallback) appended to `SOURCES.md` (link + what for).
6. 2-3 proof clips in `proof/` (committed): one PASSing A overlay, one FAILing A
   overlay, one A-vs-B pair on the same clip if attribution fired. Captioned here.
7. Dataset itself stays OUT of git (`data/` is gitignored); document the exact
   source URL, size, and date in this README.

## Steps for Opus (in order)

1. `mkdir data && echo 'data/' > .gitignore` (this dir). Download UAV123 into
   `data/` (document source + size here). Fallback per D2 after ~2 h of failed
   attempts.
2. Apply clip selection rules; fill the clips+captions table; commit ("clips
   pre-registered").
3. Write `replay_e18.py` per spec; `--selfcheck` green; commit.
4. Smoke run; if plumbing fails, fix and note what was wrong here.
5. Run matrix (B then A); write `runs/`, `raw/` logs as you go.
6. Fill Results + verdict per the pre-registered rules, complete definition of
   done, commit everything on this branch. Do NOT merge to main — Fable audits
   first.
