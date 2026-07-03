# E18 real-video-replay — does the deployed two-tier stack hold a real target on real aerial footage at true cadence?

- **Pre-registered:** 2026-07-03T22:58Z (Madrid wall-clock)
- **Status:** PRE-REGISTERED, not yet run. Next step: Opus executes Steps 1-6 below.
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

## Chosen clips + captions (D6 — fill BEFORE first A run)

| clip | frames | res | plain/distractor/occ | why chosen | caption |
|---|---|---|---|---|---|
| TBD | | | | | |

## Results (TBD)

| clip | leg | rep | t_lock | genuine | coverage | mean_iou | verdict |
|---|---|---|---|---|---|---|---|
| TBD | | | | | | | |

- RQ-E18 verdict: TBD
- Estimate-vs-actual: TBD
- What broke / what surprised: TBD

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
