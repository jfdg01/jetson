# E24 — warm-start acquire: select a pre-tracked candidate at t_p (Part V, first experiment)

**Pre-registered:** 2026-07-04T18:40Z. Design + the `warmstart.py` contract by the
orchestrator; the executor forks the replay harness, runs the matrix, and fills Results
only — **do NOT edit `warmstart.py` or re-interpret the verdict rules.**
**Status:** PRE-REGISTERED, not yet run.

First experiment of **Part V** (anticipatory grounding / warm-start acquire). Reframe:
`experiments/PART5-PROPOSAL-anticipatory-grounding.md`. Arc it closes on:
`experiments/HANDOFF-acquire-arc.md` (Part IV E18–E23). Self-contained handoff — a fresh
session runs this from this file alone.

## Research question

**RQ-E24:** On a t_p>0 replay (the operator's command arrives mid-flight, not at frame 0),
does a **warm-start** acquire — VLM acquire fired during the idle pre-prompt window, its box
carried by SAM2 to the prompt, then **selected** — beat the deployed **cold** acquire (fired
at the prompt, delivered stale) on the lock the operator actually receives, and how close does
it get to the **GT-oracle** ceiling?

Falsifiable, thresholds frozen below (Verdict rules).

## Context & rationale

The whole Part IV acquire-latency arc assumed **frame 0 = prompt arrival**: a cold ~4.85 s
blocking VLM acquire fires at t=0 and lands ~146 frames stale, so it misses moving targets
(E18-A **1/6** PASS). Every Part IV lever (motion-comp E19, operator-hint crop E20, automated
hints E21/E22, wider cells E23) attacked the *cold acquire* and capped or failed. But the
assumption is false: the drone streams video for seconds before the operator speaks, so the
VLM slot sits **idle** before the command. That idle window is free compute.

Two facts from E18 bound this experiment:
- **E18-B (oracle):** seed StreamCarry from the GT frame-0 box, carry the whole clip — **6/6
  PASS.** Carry from a correct seed holds on real UAV123 video. So "can SAM2 carry for
  seconds" is already answered YES; it is not what E24 tests.
- **E18-A (cold):** VLM acquire at t=0, carry forward — **1/6.** The failure is that the box
  is delivered stale (target moved during the blocking acquire), and a stale seed poisons the
  carry.

So the *only* gap between the proven 6/6 oracle and a deployable system is **replacing the GT
seed with a real VLM detection taken in the idle window, and scoring the lock at the operator's
real prompt time t_p** (by which carry has caught up to "now") **instead of at the stale
acquire-arrival frame.** E24 measures exactly that gap.

Why this is the right first experiment and not a bigger build: on the UAV123 `car*` clips there
is **one** salient target per clip, so "select the operator's phrase among warm tracks" is
unambiguous — E24 can defer the multi-candidate selector (that is the *next* experiment, on a
twin-distractor clip) and isolate the load-bearing unknown: **is a real idle-window detection
good enough to seed a carry that is still locked at t_p?** Rejected alternative: jump straight
to the full periodic-detection + phrase-selector system — it confounds detection quality, carry
hold, and phrase matching in one number; E24 pins the first two with the selector held trivial.

## The three legs (contract: `warmstart.py`, already committed)

All three answer ONE operator command issued at **t_p = 8.0 s**. Each leg is scored at the
frame the operator actually **receives** a box (`deliver_frame`), so the metric is "quality of
the box the operator gets, at the moment they get it, and whether it holds for `cover_s`". Frame
arithmetic is frozen in `warmstart.py` — import `schedule()` / `window()`, do not re-derive.

| leg | seed | seed frame | acquire fires | deliver/score frame (t_p=8s, acq≈4.85s) | REGROUND |
|---|---|---|---|---|---|
| **WARM** | real VLM box (submit frame) | frame 0 (cached) | t=0 (idle) | prompt = **240** (fresh) | on (mask gate, app-tau 12.0) |
| **ORACLE** | GT frame-0 box | frame 0 | — | prompt = **240** (fresh) | off (E18-B rule) |
| **COLD** | real VLM box (submit frame) | delivered at arrival | t=t_p (prompt) | prompt + acq = **~386** (stale) | on (mask gate, app-tau 12.0) |

**WARM mechanism (the free-compute premise, specify exactly — this is load-bearing):**
1. At t=0 fire the normal full-frame `vlm_acquire` (blocking ~4.85 s). Its box is computed from
   the **submit frame (frame 0)** — cache that frame.
2. Seed StreamCarry on the **cached submit frame** (E4 "Fix B" submit-frame init — never yet
   tested on real video; the E18-A bug was seeding at the *arrival* frame with a *submit*-frame
   box).
3. **Idle catch-up:** step carry forward through the buffered frames `0 → prompt_frame` **as
   fast as compute allows (non-realtime)** — this is legitimate because the operator has not
   spoken yet; the idle window is the free compute the reframe rests on. Sub-sample at the carry
   cadence if needed, but consume up to `prompt_frame` so the track is CURRENT at the prompt. If
   the E19 BUF helper is reused for this, say so; if you fall back to a single catch-up step,
   document it as a limitation.
4. At `prompt_frame` the operator selects the (single) carried track; the held box there is the
   delivered box. `genuine_lock` = IoU(held, GT) ≥ 0.25 at `prompt_frame`; `coverage` = IoU≥0.25
   fraction over `window(prompt_frame, cover_frames, clip_len)`.

**COLD** is E18-A shifted to t_p: at the prompt, fire the acquire; it lands `acq_frames` later;
seed carry at that arrival frame (E18-A behaviour); score `genuine_lock` at `cold_deliver_frame`
and `coverage` over the window from there. **ORACLE** is E18-B extended: seed GT[0] at frame 0,
idle catch-up to prompt, select at prompt.

The realtime frame-drop rule (E18 `WallClockVideo`) applies AFTER delivery (the drone acting
under load); the idle catch-up before the prompt is not realtime-bound.

## Frozen facts (do not re-derive)

- **Clips (6, UAV123, 30 fps) + captions:** car3 "the red car", car7 "the silver car",
  car9 "the white car", car10 "the red car", car14 "the red car", car18 "the red car".
  Data (gitignored, on disk): `experiments/2026-07-03-real-video-replay/data/UAV123/`.
- **t_p = 8.0 s** (> acquire ~4.85 s so the warm track is ready — the early-prompt / cold-fallback
  case t_p < acquire is a deliberate out-of-scope follow-up). **cover_s = 10.0 s. fps = 30. n = 2.**
- **Backend/tracker (unchanged from E18/E23):** Qwen2-VL-2B Q8_0 terse, `max_side = 1024`;
  StreamCarry SAM2.1-hiera-tiny TensorRT fp16 co-resident ~6.15 Hz; mask gate app-tau 12.0;
  LOSS_S 1.0. Jetson Orin Nano 8 GB, **15 W + jetson_clocks** (no MAXN on this board).
- **E18 baselines (gen/cov best):** A-cold car3 F/0.976, car7 F/0.285, car9 F/0.993,
  car10 P/1.000, car14 F/0.903, car18 F/0.711; **B-oracle 6/6.**
- **Lock metric:** `genuine_lock` at the leg's `deliver_frame`; `coverage` over its window;
  PASS = `genuine_lock AND coverage ≥ 0.50`, best of n=2. Rig near-deterministic (greedy decode).

## Code changes

- **`warmstart.py` — already committed, executor: do NOT edit.** Frame-schedule contract
  (`schedule()`, `window()`) + selfcheck (green: `prompt=240, cold_deliver=386, replay_end=686`).
- **Executor writes** (fork, do not rewrite from scratch — reuse E18's `WallClockVideo` /
  `load_uav123_gt` / `score_run` / `iou` / `vlm_acquire` / `MaskGate` / `StreamCarry`):
  - `replay_e24.py` — fork of `experiments/2026-07-03-real-video-replay/replay_e18.py`. Add
    `--leg {WARM,COLD,ORACLE}`, `--t-p` (default 8.0), `--cover-s` (default 10.0), `--caption`,
    `--clip`, `--out`. Implement the three legs above using `warmstart.schedule(t_p,
    measured_acquire_s)` — **COLD's `cold_deliver_frame` uses the MEASURED per-run acquire
    wall-time, not the nominal 4.85.** Emit `runs/<leg>/results.json` in E18's shape plus a
    `warm` block echoing `{leg, t_p, cover_s, acquire_s, deliver_frame, seed_frame,
    genuine_lock, coverage}`, and `runs/<leg>/overlay.mp4` (held box + GT box per frame — the
    proof-clip source). `--selfcheck` asserts each leg's seed/deliver frame matches
    `warmstart.schedule` on a stub backend; run it green before the matrix.
  - `run_matrix.py`, `summarize.py`, `make_proof.py` (deliverables below).

## Run matrix (18 legs + smoke; snapshot each to its own `runs/` dir immediately)

Power/versions first (NOPASSWD): `ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks && sudo nvpmodel -q; sudo jetson_clocks --show" | tee raw/jetson-power.txt`
(15 W mode index per E18; log whatever `-q` reports — do not claim MAXN).

```
# smoke: one clip end-to-end, all three legs, before the matrix
.venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py --selfcheck
.venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py --leg WARM --clip car10 --caption "the red car" --t-p 8.0 --out experiments/2026-07-04-warm-start-acquire/runs/smoke_warm_car10

# matrix: 6 clips x {WARM, COLD, ORACLE} x n=2  (ORACLE ignores --caption)
#   e.g. WARM car3 rep 1:
.venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py --leg WARM   --clip car3  --caption "the red car"    --t-p 8.0 --cover-s 10.0 --out .../runs/warm_car3_r1
#   COLD car3 rep 1, ORACLE car3 rep 1, ... through all 6 clips x 3 legs x 2 reps.
```

Order: `--selfcheck`, smoke, then **all ORACLE + COLD legs** (cheap-ish), then **WARM**. Jetson
15 W + jetson_clocks confirmed before any leg that calls the VLM (WARM/COLD). Snapshot each run
to its own dir immediately (outputs clobber between runs). Record `overlay.mp4` for every leg —
the deliverable clips are cut from WARM/COLD/ORACLE of the same clip.

**Abort criteria:** a run hangs > 8 min, crashes, or a `results.json` is missing → snapshot what
exists, mark that leg INVALID in the table, continue. Do NOT end your turn to "wait" for the
matrix — poll `runs/*/results.json` in a FOREGROUND loop and continue straight through to
Results + proof + commit.

## Verdict rules (mechanical — the executor does not deliberate)

Per clip, per leg: **PASS = `genuine_lock` (at that leg's `deliver_frame`) AND `coverage` ≥ 0.50,
best of n=2.** Let `W`, `C`, `O` = PASS counts /6 for WARM, COLD, ORACLE.

- **RQ-E24 = YES** iff `W ≥ 4` **AND** `W > C` **AND** WARM's PASS set ⊇ COLD's PASS set.
- **PARTIAL** iff `W > C` but (`W < 4` **OR** WARM's PASS set ⊉ COLD's set).
- **NO** iff `W ≤ C` (warm-start does not beat the deployed cold acquire).
- **Suffixes (append the one that fits the dominant failure mode):**
  - `[detection-bound]` if the clips WARM fails are ones ORACLE **passes** (real idle-window
    detection, not carry, is the binder — the natural next lever is periodic re-detection).
  - `[carry-bound]` if a clip ORACLE also **fails** at t_p (carry cannot hold even a perfect seed
    to t_p — a bigger finding than any detection issue; contradicts E18-B, investigate).
  - `[ready-only]` reminder that t_p (8 s) > acquire, so this is the "warm track already
    established" case; the early-prompt case is out of scope.
- Always report `W`, `C`, `O` and the **WARM-vs-ORACLE gap** (which clips warm loses that the
  oracle keeps = the detrection headroom).

No regression guard vs a deployed metric (new rig/metric); **COLD is the internal baseline** and
ORACLE the ceiling. Selection is trivial here (one target/clip) — state that plainly so the next
experiment (multi-candidate selector) is not conflated with this result.

## Estimates (mark vs actual when done)

- **WARM:** est **PARTIAL-to-YES, 4–5/6.** Carry from a correct seed is E18-B's 6/6; the only
  degradation is real-detection seed quality at frame 0 (E18-A acquire is in-domain-ish but
  misses small/low-contrast targets). Expect the larger/mid targets (car9/car10/car14/car18) to
  seed and hold; car3 (tiny red) and car7 (fast silver) are the detection risks.
- **COLD:** est **1–2/6** (E18-A shifted to t_p; delivered stale).
- **ORACLE:** est **6/6** (matches E18-B; a miss here would be a `[carry-bound]` surprise).
- **Runtime:** est **2–3 h** (18 legs + smoke × ~23 s replay to frame 686 + Jetson boots/acquires;
  ORACLE legs skip the VLM so are faster).
- Expected verdict: **PARTIAL-to-YES** — warm-start beats cold; whether it clears 4/6 and
  supersets cold depends on frame-0 detection on the two small/fast clips.

## Deliverables (proof/ — figure primary, clip secondary; committed + captioned)

1. **`proof/warm_vs_cold_vs_oracle.png`** (primary, `make_proof.py` from `runs/*/results.json`):
   grouped bars per clip — WARM / COLD / ORACLE coverage with a PASS marker, and a second panel
   or annotation showing **delivery freshness** (WARM delivers at frame 240, COLD at ~386 — the
   146-frame staleness the warm path removes). This is the "numbers are the point" deliverable.
2. **`proof/<clip>_warm_vs_cold.mp4`** (secondary): one clip where WARM passes and COLD fails,
   WARM and COLD overlays side by side (or stacked) — warm box locked-fresh on the target vs cold
   box stale/missed. If WARM instead fails a clip ORACLE passes, cut `<clip>_warm_vs_oracle.mp4`
   as the negative proof (detection-bound: same carry, real seed loses, GT seed holds).

## Execution plan (for the executor)

1. `git log --oneline -3` (on `experiment/warm-start-acquire`); confirm `warmstart.py` committed
   and its selfcheck green. Do NOT edit it.
2. Write `replay_e24.py` (fork E18); `--selfcheck` green; commit. Log Jetson power to `raw/`.
3. Run smoke (WARM car10); sanity-check `results.json` shape + overlay. Then run the full matrix,
   snapshotting each run immediately. **Poll `runs/*/results.json` in a foreground loop — do not
   stall waiting.**
4. Fill the Results table; apply the frozen Verdict rules to get W/C/O and the verdict + suffix.
5. Append the ledgers under **Part 5** (`docs/{results,questions,decisions}/part5-anticipatory.md`,
   not the roots): RESULTS row, QUESTIONS RQ-E24 + one-line verdict, DECISIONS entry (the
   warm-vs-cold choice / what was given up). Madrid wall-clock timestamps, no emojis.
6. `make_proof.py` → the figure; cut the clip(s). Commit everything on the branch with
   `E24 warm-start-acquire COMPLETE: RQ-E24 <verdict>`; `git status` clean.
7. Report: verdict + W/C/O table + `git log --oneline main..HEAD`. Do NOT merge or push — the
   orchestrator audits and merges.

## Results (TBD)

Per-clip PASS (best of n=2), deliver-frame genuine_lock / coverage:

| clip | caption | WARM gen/cov | COLD gen/cov | ORACLE gen/cov | WARM PASS? |
|---|---|---|---|---|---|
| car3 | the red car | | | | |
| car7 | the silver car | | | | |
| car9 | the white car | | | | |
| car10 | the red car | | | | |
| car14 | the red car | | | | |
| car18 | the red car | | | | |

`W = _/6, C = _/6, O = _/6.` **RQ-E24 = TBD.** WARM-vs-ORACLE gap: TBD.

Estimate vs actual + what broke / what surprised: TBD.
