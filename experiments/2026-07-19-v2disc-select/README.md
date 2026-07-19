# P5.13 — v2 discrimination A/B: DD vs RG on the bank v2.1 crossing bank

**Pre-registered:** 2026-07-19T13:40Z
**Status:** PRE-REGISTERED, not yet run.
**Branch:** `experiment/v2disc-select` (off `ea9e06c`, the P5.12 merge)
**Part:** V — anticipatory grounding / warm-start acquire

---

## RQ-P5.13

**RQ-P5.13a (primary, gating).** On a scene bank whose clips contain a *designed
crossing/occlusion* between the two candidate cars, do the two delivery contracts
— **DD** (direct delivery of the carried track, no VLM at prompt time) and **RG**
(prompt-time re-grounding through the VLM plus IoU match) — **separate**?

> Separate iff `|DD_total − RG_total| >= 4` of 24 cells.

**RQ-P5.13b (secondary, diagnostic, NON-gating).** Is the separation, if any,
driven by the designed occlusion? The white car is the occluded target in 12/12
clips and the blue car is never occluded, so the two legs are an internal control:

> Occlusion-driven iff `blue-leg DD − white-leg DD >= 3` of 12.

RQ-P5.13b cannot change the overall verdict. It is recorded because a separation
that shows up equally on both legs is *not* the crossing doing the work, and that
distinction decides the next lever.

### Why the margin is symmetric, and why that is a change

P5.10 pre-registered a **directional** threshold, `DD_total >= RG_total + 4` — it
assumed direct delivery would win. P5.13 uses `|DD − RG| >= 4`. The reason is
that P5.13's own prediction runs the *other* way (see below), and a threshold
that can only fire in the direction the experimenter expects is not a test. The
magnitude (4 of 24) is carried forward unchanged from the P5.11 / P5.12
pre-registrations so the bar is not being moved.

### Prediction (estimate, recorded before the run)

**RG > DD.** RG re-grounds at f150, where the two cars are separated in all 12
clips (GT-GT IoU <= 0.084, table below) — the same clean-render condition under
which P5.10's RG scored 24/24. DD must instead carry identity *through* the
crossing at ~f81. If SAM2's carry survives that, both contracts ceiling again and
we get branch 3; if it does not, DD drops and we get branch 2 — the first Part V
result favouring prompt-time re-grounding over the carry.

---

## Context: why this experiment, now

Three straight select campaigns (P5.3, P5.4, P5.5) returned NO, all
match/carry-bound. P5.10 then ran the DD-vs-RG A/B on the P5.9 sim bank and got
**DD 24/24 == RG 24/24, margin 0** — both contracts at ceiling, no separation.
The diagnosis was that **bank v1 was too easy**: its clips contained no crossing
(max GT-GT IoU 0.000 across all 12), so a prompt-time re-ground was never asked
to resolve an ambiguity and a carry was never asked to survive one. The select
NOs read as **scene-bound, not contract-bound**.

P5.11 built a designed-crossing bank and failed its *build gate* (3/12).
P5.12 showed that failure was **admission-calibration-bound, not render-bound**,
and delivered bank v2.1: 12/12 cells, 12 genuine crossings, 0 render defects.

P5.13 is the deferred A/B, now run on scene data that can actually discriminate.
This is the fourth cycle spent on the scene data rather than the contracts; it is
the one that finally puts the contract question to a bank built to answer it.

### What we rejected

- **Re-running P5.10 unchanged on the new bank.** Its prompt frame (75) lands at
  t=3.0 s, which is *inside* the crossing window (peaks f56–f94). Both contracts
  would be graded mid-occlusion and a null would be uninterpretable — we could not
  tell a contract failure from a "we asked at the worst possible moment" artifact.
  P5.13 moves the prompt to f150, cleanly after every crossing.
- **Adding new fail classes or scoring rules.** The scoring code is a forward copy
  of P5.10's with constants changed and nothing else, so a P5.13-vs-P5.10 delta is
  attributable to the bank and the prompt frame, not to the grader.
- **Widening the bank first.** n=12 is what exists and what P5.12 validated. If
  P5.13 nulls, the pre-registered explanations below say what to check — adding
  clips before knowing which explanation holds would be guessing.

### The caveat carried forward from P5.12 (mandatory, pre-registered)

Verbatim from the merged P5.12 README's orchestrator-audit section:

> If P5.13's contracts fail to separate, the two pre-registered explanations to
> check first — in this order — are the crossing-peak uniformity and constant
> z-order measured in the audit section above, then bank05 / bank06's weaker
> occlusion stress. P5.13's pre-registration must name both **before** it runs.

Both are named here and are wired into the verdict script's branch 3 text, so a
null prints its own explanation list and no third explanation can be invented
post-hoc:

1. **Crossing-peak uniformity + constant z-order.** At the crossing peak the 12
   clips converge: white-box centre y std 6.1 px on a 720 px frame, centre x std
   27.9 px on 1280, area std 592. And **white is the nearer car in 0 of 300 frames
   in every clip** — the bank never renders the target in front. G4b's 1.11 m
   diversity is a whole-trajectory statistic; the graded moment and the z-order
   are near-constant and neither has a gate. (Partial mitigation, measured here:
   the peak *frame* does vary, f56–f94. The peak *position* and z-order do not.)
2. **bank05 / bank06 weaker occlusion stress.** Peak GT-GT IoU 0.217 and 0.251
   versus 0.352 for bank07 — the two weakest crossings in the bank.

---

## Method

### Scene source (consumed unchanged — do NOT regenerate)

`experiments/2026-07-17-bankv21-recal/runs/bank01..bank12`, the P5.12 deliverable.
Seeds 1, 2, 3, 4, 6, 14, 17, 28, 29, 33, 40, 56. 300 frames @ 25 fps, 1280×720,
per-frame GT for **both** cars (id0 `"the white car"`, id1 `"the blue car"`,
`visible` true 300/300). Exact dual GT makes selection scoring exact.

Measured crossing geometry (from `gt.jsonl`, no renderer — reproduce with the
snippet in "Verification already run"):

| clip | peak GT-GT IoU | peak frame | t (s) | GT-GT IoU @ f150 |
|---|---|---|---|---|
| bank01 | 0.331 | f87 | 3.5 | 0.056 |
| bank02 | 0.265 | f74 | 3.0 | 0.014 |
| bank03 | 0.269 | f85 | 3.4 | 0.056 |
| bank04 | 0.329 | f88 | 3.5 | 0.004 |
| bank05 | 0.217 | f69 | 2.8 | 0.010 |
| bank06 | 0.251 | f56 | 2.2 | 0.044 |
| bank07 | 0.352 | f82 | 3.3 | 0.011 |
| bank08 | 0.286 | f92 | 3.7 | 0.084 |
| bank09 | 0.274 | f94 | 3.8 | 0.030 |
| bank10 | 0.242 | f77 | 3.1 | 0.000 |
| bank11 | 0.249 | f83 | 3.3 | 0.056 |
| bank12 | 0.275 | f89 | 3.6 | 0.013 |

Every crossing peaks between f56 and f94; every clip is separated by f150. That
is the design: **the carry must survive the crossing, the VLM sees a clean scene.**

### Cells

24 cells = 12 clips × 2 legs (`white` = "the white car", `blue` = "the blue car").
**Both contracts are scored inside every cell off one shared carry pass**, so
DD and RG are paired by construction — the A/B is within-cell, not across runs.
Totals are therefore DD_total/24 and RG_total/24.

### Contracts

- **DD** — the idle-window carry track for the named object is delivered directly
  at the prompt frame. No VLM call. Fail classes: `CARRY_LOST`, `CARRY_SWITCH`,
  `CARRY_DRIFT`.
- **RG** — at the prompt frame the operator phrase goes to the VLM, the returned
  box is IoU-matched (floor 0.10) against the live candidate tracks, and the
  matched track is delivered. Fail classes: `NO_BOX`, `OVERRUN`, `NO_MATCH`,
  `MATCH_WRONG`, `DELIVERY_LOST`, `DELIVERY_SWITCH`, `DELIVERY_DRIFT`.

PASS for both = `iou_named >= 0.25` **and** `iou_named > iou_other` (dominance),
identical to P5.10.

### Changes from P5.10, exhaustively

`select_p513.py` is a forward copy of the byte-frozen `select_p510.py`. Every
substantive change:

| # | Change | Value | Why |
|---|---|---|---|
| 1 | `N_FRAMES` | 240 → **300** | bank v2.1 clip length |
| 2 | `T_P` / `PROMPT_FRAME` | 3.0 s / f75 → **6.0 s / f150** | prompt must land *after* the crossing (peaks f56–f94) |
| 3 | `BANK` default | kerbsafe-scenebank → **bankv21-recal** | new bank |
| 4 | selfcheck + preflight literals | f75→f150, f239→f299, coverage n 165→**150**, deliver frame 190→**265** | mechanical consequences of 1–2 |

Everything else — `CARRY_HZ`, `CAND_STRIDE`, `MATCH_FLOOR` 0.10, `DELIVER_FLOOR`
0.25, both fail-class sets, the scoring functions, the overlay writer — is
unchanged.

`verdict_p513.py` is a forward copy of `verdict_p510.py` with the threshold block
replaced: `SEP_MARGIN = 4` (symmetric, replacing directional `B_MARGIN`),
`LEG_ASYM = 3` (new, diagnostic), `CEILING = 20` (interpretation only), plus a
pure `decide()` helper and rewritten branch texts.

### Two consequences that are NOT bugs — read before interpreting Results

1. **`DELIVERY_SWITCH` is reachable for the first time.** P5.10's bank had max
   GT-GT IoU 0.000, so `ok` (dominance) and `strict_ok` coincided everywhere. On
   this bank several clips exceed `DELIVER_FLOOR` at their peak (bank01 0.331,
   bank12 0.275, bank05 0.217), so the two rules genuinely diverge. `strict_ok`
   remains non-gating, as in P5.10.
2. **`cov_*` is not comparable to P5.10's.** The coverage window is
   `N_FRAMES − PROMPT_FRAME`, which shrinks from 165 to **150** frames. Compare
   `frac_lock` fractions, never the raw `n`.

Overrun threshold shifts 6.56 s → 5.96 s (`(299 − 150)/25`). Observed P5.10
acquire was ~4.37 s, so this is still clear — but it is a **tighter** margin and
an `OVERRUN` fail class in Results is a real signal, not a scoring artifact.

### Load-bearing core modules — already committed, executor: do NOT edit

- `select_p513.py` — matrix runner + scorer. `--selfcheck` passes offline (no
  GPU, no Jetson, no bank): scripted carries + scripted VLM exercise every
  scoring rule and every fail class, the `gt.jsonl` parser on a synthetic clip,
  the overlay writer, and the frame-health asserts.
- `verdict_p513.py` — mechanical verdict. `--selfcheck` passes: fabricated runs
  dirs exercise counting, the INCOMPLETE and infra-cap rules, and a pure
  `decide()` branch table including both margin edges (diff 4 fires, diff 3 does
  not).
- `make_proof.py` — the three deliverables, reproducible from
  `runs/*/results.json` + the committed overlay PNGs.

### Verification already run (before freezing this document)

```
.venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --selfcheck
    -> select_p513 selfcheck OK
.venv-ft/bin/python experiments/2026-07-19-v2disc-select/verdict_p513.py --selfcheck
    -> verdict_p513 selfcheck OK
.venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --preflight
    -> preflight OK (12 clips); all 12 report "300 frames, phrases OK,
       min-visible 300/300", max GT-GT IoU 0.217..0.352
```

Jetson confirmed reachable, 15 W, `llama-server` warm on port 18080 (`/health`
returns `{"status":"ok"}`).

---

## Run matrix

**Rig:** RTX 3090 workstation (bank frames, SAM2 carry, all scoring) + Jetson
Orin Nano 8 GB (VLM only, `15W` + `jetson_clocks`).
**Frames never leave the workstation.** The bank is read in place; exactly one
PNG per cell crosses the wire, base64-inlined in the HTTP chat payload through
the `ssh -N -L 18080:localhost:18080 jetson` tunnel. Do not copy the bank.

The runner boots the Jetson `llama-server` itself if it is not already up, and
reboots it on VLM failure (`vlm.reboots` is reported at the end — a non-zero
count goes in Results).

| run | command | snapshot |
|---|---|---|
| R0 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --selfcheck` | — (must print `select_p513 selfcheck OK`) |
| R1 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/verdict_p513.py --selfcheck` | — (must print `verdict_p513 selfcheck OK`) |
| R2 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --preflight` | — (must print `preflight OK (12 clips)`) |
| R3 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --matrix 2>&1 \| tee experiments/2026-07-19-v2disc-select/raw/matrix.log` | writes `experiments/2026-07-19-v2disc-select/runs/<clip>_<leg>/` directly — no clobber, no manual snapshot |
| R4 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/verdict_p513.py 2>&1 \| tee experiments/2026-07-19-v2disc-select/raw/verdict.txt` | the verdict is this output, verbatim |
| R5 | `.venv-ft/bin/python experiments/2026-07-19-v2disc-select/make_proof.py` | writes `proof/p513_*.png` |

R3 is resumable: completed cells are skipped, so a partial matrix can be resumed
with the same command. Single-cell rerun: `--only bank03 --legs white`.

`mkdir -p experiments/2026-07-19-v2disc-select/raw` before R3.

Each cell writes `results.json` plus four overlay PNGs: `overlay_dd_f0150.png`,
`overlay_vlm_f0150.png`, `overlay_rg_f<deliver>.png`, `overlay_end_f0299.png`.

### Abort criteria (mechanical — do not deliberate)

- A cell that hangs > 10 min, crashes, or leaves no `results.json`: write
  `runs/<clip>_<leg>.INFRA` containing the reason, continue to the next cell.
- **> 1 INFRA cell total** → the verdict script prints `NO [infra]` and exits 1.
  Stop, record it, do not re-run to get a better number.
- `vlm.reboots > 3` → note it prominently in Results; it does not by itself
  invalidate the run.
- Any selfcheck (R0/R1) failing → stop before R3. Do not "fix" the committed
  scripts; report the failure.

---

## Verdict rules (frozen)

`verdict_p513.py` is the sole authority. It applies:

- **RQ-P5.13a** = `abs(DD_total − RG_total) >= 4`.
- **RQ-P5.13b** = `blue_DD − white_DD >= 3` (printed, diagnostic, does not gate).
- **OVERALL RQ-P5.13** = RQ-P5.13a.
- INFRA cells count as FAIL for both contracts; > 1 INFRA → `NO [infra]`.
- Missing cell with no `.INFRA` marker → `INCOMPLETE`, exit 2 (not a verdict).

Interpretation branches (exactly one fires):

| branch | condition | reading |
|---|---|---|
| 1 | separate, DD > RG | carry survives the crossing, VLM re-ground is the weak link. Next = unpark P5.6 (direct delivery on real UAV123). |
| 2 | separate, RG > DD | the crossing breaks the carry, re-grounding repairs identity. Inverts the warm-start premise for occluded targets; next = hybrid (carry + re-ground confirmation), not more scene data. |
| 3 | no separation, both >= 20/24 | bank still does not discriminate. Check the two pre-registered explanations above, in order. No third explanation post-hoc. |
| 4 | no separation, at least one < 20/24 | stack fails at f150 upstream of the contract question; diagnose the stack first. |

**Visual gate V (operator, at audit).** Per CLAUDE.md "Look at it": the
orchestrator opens the proof PNGs and a sample of per-cell overlays with the Read
tool before accepting any verdict. **V can only downgrade a YES to NO** — it can
never rescue a NO. A cell whose overlay shows a black frame, a box on empty road,
or a stale GT is INVALID regardless of its `results.json`.

---

## Estimates (recorded before the run)

All marked as estimates.

| quantity | estimate | basis |
|---|---|---|
| matrix wall time (R3) | **6–12 min** | P5.10 ran 24 cells in ~2.75 min at 240 frames; +25% frames and a warm Jetson, widened for a cold-boot case |
| VLM acquire per cell | ~4.4 s | P5.10 measured 4.37 s, same model/quant/prompt |
| RG_total | **20–24 / 24** | RG grounded 24/24 on clean renders in P5.10 and f150 is clean in all 12 clips |
| DD_total | **12–20 / 24** | the prediction: the crossing costs the carry somewhere; wide because SAM2-through-occlusion is untested on this bank |
| most likely branch | **2**, then 3 | if the carry is robust this collapses to 3 |
| `vlm.reboots` | 0 | Jetson already warm |
| INFRA cells | 0 | no gz-transport in this pipeline; it reads recorded frames |

A wrong estimate is content — record estimate-vs-actual below wherever they diverge.

---

## Results (TBD)

**Run date/time:** TBD (Madrid wall-clock)
**Versions:** TBD — recorded into every `results.json` at runtime (torch / numpy /
cv2 / python / sam2_model / VLM).
**Matrix wall time:** TBD. **VLM reboots:** TBD. **INFRA cells:** TBD.

### Per-cell table

Paste `verdict_p513.py` stdout verbatim (columns: `cell`, `DD`, `dd_class`,
`ddIoU`, `RG`, `rg_class`, `vlm_on`, `acq_s`, `delivF`, `ddCov`, `rgCov`).

```
TBD
```

### Totals

| contract | white | blue | total |
|---|---|---|---|
| DD | TBD/12 | TBD/12 | TBD/24 |
| RG | TBD/12 | TBD/12 | TBD/24 |

| item | value |
|---|---|
| RQ-P5.13a (\|DD − RG\| >= 4) | TBD |
| RQ-P5.13b (blue DD − white DD >= 3) | TBD |
| **OVERALL RQ-P5.13** | TBD |
| branch fired | TBD |
| DD fail classes | TBD |
| RG fail classes | TBD |
| visual gate V | TBD |

### Estimate vs actual

| quantity | estimate | actual | note |
|---|---|---|---|
| matrix wall time | 6–12 min | TBD | |
| RG_total | 20–24/24 | TBD | |
| DD_total | 12–20/24 | TBD | |
| branch | 2, then 3 | TBD | |

### What broke / what surprised

TBD — honest, including anything that had to be worked around.

---

## Proof deliverables (TBD)

Three, all from the committed `make_proof.py`, committed under `proof/` and
captioned here. The numbers are the point in the first two; the behaviour is the
point in the third.

| file | shows | from |
|---|---|---|
| `proof/p513_pass_grid.png` | 12 clips × {DD,RG} × {white,blue} pass/fail grid — the separation (or its absence) at a glance | all 24 `results.json` |
| `proof/p513_failclass.png` | fail-class histogram per contract — *how* each contract fails, not just how often | all 24 `results.json` |
| `proof/p513_headline_dd_vs_rg.png` | side-by-side delivery overlays for a cell where the two contracts disagree (picker is direction-agnostic — it does not assume DD wins) | that cell's `overlay_dd_f0150.png` + `overlay_rg_f<deliver>.png` |

If no cell disagrees, the headline falls back to any non-both-pass cell, then to
`bank01_white`; note in the caption which fallback fired.

---

## Definition of done

1. This README filled — Results, estimate-vs-actual, what broke.
2. RESULTS row(s) appended to `docs/results/part5-anticipatory.md`.
3. QUESTIONS entry (RQ-P5.13a/b + one-line verdict) appended to
   `docs/questions/part5-anticipatory.md`.
4. DECISIONS entry appended to `docs/decisions/part5-anticipatory.md` — the
   symmetric-margin change and the f150 prompt frame both qualify.
5. SOURCES — no new external source expected; append only if one is pulled in.
6. Three proof PNGs committed under `proof/` and captioned above.
7. `runs/*/results.json` committed. Per-cell overlay PNGs stay **uncommitted** —
   `.gitignore:35` (`experiments/*/runs/**`) covers them by design; curated
   evidence goes to `proof/` instead. No video in this campaign.
