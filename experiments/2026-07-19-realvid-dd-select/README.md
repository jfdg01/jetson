# P5.14 — Direct-delivery select on real UAV123: unpark P5.6, run the contract off the sim

**Pre-registered:** 2026-07-19T14:05Z (Madrid wall-clock). Design + patches by Fable; **Opus runs
the matrix and fills Results only — do NOT re-patch code.**
**Status:** COMPLETE — run 2026-07-19T13:35Z–13:51Z. **OVERALL: YES** (WSEL 5/5, SWAP 4/5 strengthened; visual gate V PASS, no downgrade).
**Branch:** `experiment/realvid-dd-select` (off `main` @ `0e7308e`, the P5.13 merge).
**Part:** V — anticipatory grounding / warm-start acquire.
**Rig:** RTX 3090 workstation (SAM2 carry, scoring, UAV123 frames) + Jetson Orin Nano 8 GB
(VLM: idle ROI re-anchors + non-gating shadow call only), `15W` + `jetson_clocks`.

## Provenance: this is the parked P5.6, renumbered and unparked

The entire rig (`select_p56.py`, `verdict_p56.py`, `make_proof.py`, `annotate_p56.py`,
`scenes_p56.json`, `curation/*.jpg`) is imported **byte-unchanged** from the parked branch
`experiment/direct-delivery-select` @ `df6de31` (pre-registered 2026-07-14T07:25Z, never run).
Internal filenames and printed labels keep the `p56` lineage tag; **RQ-P5.14a ≡ RQ-P5.6a and
RQ-P5.14b ≡ RQ-P5.6b**, thresholds unchanged — the bar was frozen five days and four campaigns
ago and is not being moved now that we have seen the sim results. The only new file is
`dump_frames_p514.py` (visual-gate PNG extraction; the P5.6 rig predates the "Look at it" rule
and writes only per-cell `overlay.mp4`, which the Read tool cannot open).

`select_p56.py --selfcheck` re-verified green on this branch 2026-07-19 (it also re-runs the
upstream P5.3 + P5.5 suites): `select_p53 selfcheck OK`, `select_p55 selfcheck OK`,
`select_p56 selfcheck OK`. UAV123 data and the P5.3/P5.5 `runs/` dirs (read by `make_proof.py`
for the historical comparison) confirmed present on disk.

## RQ-P5.14

Under the **direct-delivery contract** (the operator phrase binds to a warm-carried candidate by
its stored caption — string equality, captions asserted distinct; that candidate's carried box at
the prompt frame is delivered directly; no prompt-time VLM, no IoU match, acquire_s = 0):

- **RQ-P5.14a (WSEL):** select-the-target passes **>= 4/5** gating scenes.
  (History, same scenes, RG contract: P5.3 3/5, P5.5 MC 4/5.)
- **RQ-P5.14b (SWAP):** select-the-distractor passes **>= 4/5** gating scenes under the
  **strengthened** rule — delivered box IoU **< 0.25 vs target GT** AND **>= 0.25 vs the
  hand-annotated distractor GT at the prompt frame** (junk cannot pass; the old weak
  off-target-only rule is computed non-gating). (History under the *weaker* rule: P5.3 2/5,
  P5.5 MC 3/5 — 14b is strictly harder than the historical bar.)
- **Overall: YES iff both**, computed by `verdict_p56.py`; the visual gate V can only downgrade
  a YES to NO.

Cell PASS rules (frozen in `verdict_p56.py`, unchanged from the P5.6 pre-registration): WSEL =
genuine lock (delivered box IoU >= 0.25 vs target GT at the deliver frame) AND coverage >= 0.5
over the 10 s follow window; SWAP = the strengthened rule above. 5 gating scenes
(car10:240, car10:615, car9:300, car7:460, car9:560) + car3:200 as a non-gating control.

### Why this is the highest-leverage question now (audit of P5.10–P5.13)

**The audit.** P5.13 (NO, branch 3) is valid — I reproduced the totals from `raw/verdict.txt`,
spot-checked `runs/bank09_white/results.json` (the one RG fail is a mask leak over RG's
109-frame delivery lag with the VLM's grounding *correct*: `vlm_iou_named` 0.735, `selection` 0),
and opened `proof/p513_pass_grid.png` + `proof/p513_headline_dd_vs_rg.png` with the Read tool:
genuine Gazebo renders, the 47-green/1-red grid matches the table, and the `DELIVERY_DRIFT`
balloon box is plainly visible. The verdict stands, and so does the orchestrator-audit finding:
the post-crossing segment is near-static (target moves 0.4–15.6 px over the 109-frame lag), so
RG's lag was free and the tie was structurally likely. P5.12 (YES) also stands — its S6
delta-0 prediction table and 12/12 visual gate are internally consistent.

**What the results actually say.** Two full A/B campaigns (P5.10 on bank v1, P5.13 on the
designed-crossing bank v2.1) put DD and RG at ceiling: 24/24 vs 24/24, then 24/24 vs 23/24 with
the single discordant cell attributable to carry decay, not contract. On clean synthetic scenes
the fine-tuned VLM grounds everything and the SAM2 carry survives everything — including every
designed crossing. The sim, as built, cannot discriminate the contracts; the two properties left
to vary (target-in-front z-order, post-prompt target motion) both need generator redesign, and
each prior hardening cycle moved a property that then turned out not to bind.

**The override, stated plainly.** The standing human steer picked "harden the bank to v2" and
deferred P5.6 "unless the audit overrides". The picked direction has been *executed to
completion* — bank v2.1 built (P5.12 YES) and the discrimination A/B run (P5.13) — and it
answered: contracts still tie on synthetic data. P5.13's own ledger entry names the next lever as
"a property of the scene the bank has never varied (z-order / target-in-front) **or a move off
synthetic banks entirely**". Meanwhile the discrimination we have spent four cycles trying to
manufacture in sim *already exists in the recorded real-video results*: on these exact UAV123
scenes the RG contract measured WSEL 3-4/5 and SWAP 2-3/5 (P5.3/P5.5), with the fails
concentrated in the prompt-time re-ground + match step while the carried tracks were right or
fixable (the P5.6 raw-runs audit, verified cell-by-cell at its pre-registration). Running DD on
those same scenes is the real-data A/B against a known baseline. This audit therefore overrides
the deferral, per the steer's own escape clause.

**The rejected alternative (DECISIONS seed): bank v3.** A third bank cycle — post-prompt motion
gate (minimum target displacement between prompt and expected delivery frames), z-order
variation (target sometimes in front), crossing-peak diversity gates. Rejected *this cycle*
because: (a) it is the 5th+ consecutive scene-data cycle with a demonstrated risk of a third
ceiling tie (SAM2 + the VLM are simply strong on clean 25 fps renders); (b) it requires
re-authoring scenario trajectories and recalibrating the kerb-safe corridor, a multi-session
build before any contract evidence arrives; (c) whichever way P5.14 lands, its result is
decision-relevant for the north star (deploy DD, or learn that carry quality on real video sinks
both contracts). **Carried forward as mandatory, per the P5.13 audit:** if a later cycle returns
to a sim bank, its pre-registration MUST gate minimum post-prompt target displacement over the
delivery window, crossing-peak diversity, and z-order — those are pre-named here so they cannot
be reinvented post-hoc.

**Stale-assumption check on the parked design.** (1) The rig's dependencies (P5.3/P5.5 modules,
`grounding/`, UAV123 at `experiments/2026-07-03-real-video-replay/data/UAV123`, E24 scoring) are
all on main and the selfcheck passes on this branch. (2) The P5.6 predictions were written
before the sim arc; they still stand and are *sharpened* by it: P5.13 showed the SAM2 carry
survives designed occlusions on clean renders, but P5.5's real-video carry-drift cells
(car10:240 SWAP, car7:460 SWAP) are exactly where real video is harder than the sim — DD
delivers the carried box, so a drifted carry now *fails DD directly* instead of hiding behind
NO_MATCH. That makes RQ-P5.14b a genuine test of the carry on real video, not a formality.
(3) The `sam2-hiera-small` mention in old P5.6 text is the known doc mismatch; the code uses
`stream_carry.MODEL` (resolves to `sam2.1-hiera-tiny`, as recorded in P5.10/P5.13) — record
whatever `results.json` says.

### Prediction (estimates, recorded before the run)

- **WSEL 5/5** gating (all five target carries sat on GT at the prompt in P5.5) → RQ-P5.14a YES.
- **SWAP 4/5** gating: **car7:460 predicted to FAIL `carry-off-object`** (the one genuine carry
  failure in the P5.5 raw data — no delivery contract fixes a junk carry; the 4/5 bar tolerates
  exactly this cell). Tightest predicted pass: car9:560 (carried box IoU ~0.28 vs hand GT in
  P5.5 — just over the 0.25 floor; a marginal miss here → SWAP 3/5 → overall NO).
- car3:200 control (non-gating): WSEL predicted to **flip to PASS** (the P5.3/P5.4
  "resolution-bound" family was a re-grounding artifact, not a carry limit).
- Weak-vs-strong SWAP: car7:460 expected to pass weak / fail strong — the honest-scoring point.
- Shadow re-ground: expected to disagree with DD on the P5.5 NO_MATCH cells (that disagreement
  *is* the real-data contract separation, reported as the headline diagnostic).
- **Overall predicted: YES (5/5 + 4/5).** If instead the carries prove worse than the 07-14
  audit suggested, the fail classes say so mechanically — that negative is equally the point.

## Code changes (already committed on this branch — Opus: do NOT edit)

| File | What |
|---|---|
| `experiments/2026-07-19-realvid-dd-select/` (whole dir) | imported from `experiment/direct-delivery-select` @ `df6de31`, renamed from `2026-07-14-direct-delivery-select`; rig bytes unchanged (scripts self-locate via `Path(__file__)`; stale docstring path examples are cosmetic) |
| `dump_frames_p514.py` | **new** — extracts `viz_early.png` (25% into overlay.mp4) + `viz_late.png` (75%) per cell, with the CLAUDE.md frame-health asserts (>99%-one-colour = failed render; early==late byte-identical = dead feed). Compile-checked; correctly refuses when `runs/` is empty. |
| `README.md` | this file (replaces the P5.6 draft; the original stays readable at `df6de31`) |

## Run matrix (Opus starts here — exact commands)

Software versions are recorded into every `results.json` at runtime; copy one set into Results.
UAV123 = 1280x720 @ 30 fps. Constants (frozen in code): CARRY_HZ 6.15, CAND_HZ 3.075,
MATCH_FLOOR 0.10 (shadow only), DIST_FLOOR 0.25, cover_s 10.0, ROI_MARGIN 2.0, ROI_MIN_SIDE 256,
ROI_RES 512, REANCHOR_OFFSETS (90, 165), VLM = Qwen2-VL-2B **q8_0** terse (Jetson llama.cpp,
max_side 1024) — used ONLY for the two idle ROI re-anchors and the non-gating shadow call; the
gating delivery path makes no VLM call.

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-19-realvid-dd-select
mkdir -p $EXP/raw

# R0. offline selfcheck (no GPU/Jetson; must print "select_p56 selfcheck OK";
#     any failure -> STOP, record, do not run the matrix, do not fix code)
.venv-ft/bin/python $EXP/select_p56.py --selfcheck 2>&1 | tee $EXP/raw/selfcheck.log

# R1. Jetson power config (idempotent, NOPASSWD)
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"

# R2. the matrix: 6 scenes x 2 legs = 12 cells, sequential, resumable
#     (existing runs/DD_*/results.json are skipped;
#      single-cell rerun after a CRASH only: --only car9:560 --legs SWAP)
.venv-ft/bin/python $EXP/select_p56.py \
    --matrix $EXP/scenes_p56.json --out runs 2>&1 | tee $EXP/raw/matrix.log

# R3. mechanical verdict (paste FULL output verbatim into Results)
.venv-ft/bin/python $EXP/verdict_p56.py 2>&1 | tee $EXP/raw/verdict.txt

# R4. visual-gate frames (must print "dump_frames_p514 OK (12 cells)";
#     a FAIL line names an INVALID cell -> record it, that cell's verdict is INVALID)
.venv-ft/bin/python $EXP/dump_frames_p514.py 2>&1 | tee $EXP/raw/dumpframes.log

# R5. proof figures (after the verdict)
.venv-ft/bin/python $EXP/make_proof.py
```

Each cell writes `runs/DD_<LEG>_<clip>_<f0>/results.json` + `overlay.mp4` (~3–6 min/cell
estimated; each boots/reuses the Jetson q8_0 server). `runs/**` is gitignored by
`experiments/*/runs/**`; curated evidence goes to `proof/`.

### Abort criteria (mechanical — do not deliberate)

- R0 selfcheck fails → STOP; record the output; the matrix does not run.
- A cell CRASHES (exception, not a scored FAIL) → snapshot the traceback to `raw/`, retry once
  via `--only <clip>:<f0> --legs <LEG>`; a second crash → STOP and record (infra, not a verdict;
  the campaign is INCOMPLETE).
- A cell's wall time exceeds 20 min → kill, record, retry once; twice → STOP (Jetson hang).
- Jetson unreachable / q8_0 server fails to boot twice in a row → STOP, record, INCOMPLETE.
- Never rerun a scored cell; n=1 deterministic replay, first scored result stands.

## Visual verification (gating — CLAUDE.md "Look at it")

After R4, open with the **Read tool** (all 24 PNGs — 12 cells × 2):

- `runs/DD_<LEG>_<clip>_<f0>/viz_early.png` and `viz_late.png` for every cell.

**PASS looks like:** a real aerial UAV123 road scene (asphalt, vehicles, real-world texture —
not a black/flat frame), with the overlay's delivered/GT boxes drawn on actual vehicles. In a
WSEL cell the delivered box sits on the *target* vehicle (the object named by `target_caption`
in `scenes_p56.json`); in a SWAP cell it sits on the *distractor* (compare against the committed
zoom render `curation/prompt_<clip>_<frame>_z.jpg` for that scene — the hand GT provenance).
`viz_late` should show the same lock persisting later in the coverage window (the vehicle may
have moved; the box moves with it).

**FAIL looks like:** the box on the wrong vehicle (switch — for SWAP cells note the audit
histories in `scenes_p56.json` notes), on empty road/frame edge (drift/junk — e.g. the
predicted car7:460 `carry-off-object` should *visibly* show the box off the true distractor),
or a black/one-colour/duplicate frame (that cell INVALID — never a log-inferred pass).

Record one line per cell in Results ("what I saw"). A scored PASS whose frames contradict it →
**V downgrades the overall verdict to NO**; a scored FAIL is never rescued by V. A FAIL cell's
frames must *show* the failure mode the class claims — that agreement is thesis evidence
(negative proof), capture it in `proof/`.

## Verdict rules (frozen — `verdict_p56.py` is the sole authority)

- RQ-P5.14a = WSEL PASS count over the 5 gating scenes >= 4.
- RQ-P5.14b = SWAP PASS count (strengthened rule) over the 5 gating scenes >= 4.
- **OVERALL = YES iff both AND V does not downgrade.** car3:200 never gates.
- Fail classes are assigned mechanically by `classify()` (lost-track / carry-off-object /
  on-target / coverage / infra); report them verbatim.
- Any cell INVALID per the visual gate or missing `results.json` → INCOMPLETE, not a verdict.
- Non-gating diagnostics to report: weak-vs-strong SWAP per cell, the shadow re-ground table
  (shadow box, match IoUs, would-be selection + latency vs DD's actual delivery — the real-data
  DD-vs-RG attribution), reanchor accepted flags.

## Estimates (all marked as estimates)

| quantity | estimate | basis |
|---|---|---|
| matrix wall (R2) | **45–75 min** (12 cells × ~3–6 min) | P5.5 cell times + per-cell 10 s realtime coverage + Jetson boot once |
| WSEL / SWAP gating | 5/5 / 4/5 (car7:460 the predicted fail) | P5.6 raw-runs audit, unchanged |
| overall | **YES** | see Prediction; a NO localises to named cells |
| shadow latency | ~4.5–5 s/call | P5.3/P5.5 full-frame acquire |
| INFRA / crashes | 0 | replay rig, no gz-transport anywhere |

A wrong estimate is content — record estimate-vs-actual in Results wherever they diverge.

## Results (TBD — Opus fills; do not edit anything above this line except checkboxes)

Run date/time: **2026-07-19T13:35Z–13:51Z** (Madrid wall-clock). Rig: RTX 3090 workstation +
Jetson Orin Nano 8 GB at `15W` + `jetson_clocks` (R1 returned `POWER_OK`).
Versions: python 3.12.10, torch 2.6.0+cu124, transformers 4.57.6, SAM2 =
`facebook/sam2.1-hiera-tiny` (as predicted in the stale-assumption check — the old
`sam2-hiera-small` doc mention is wrong), VLM = `phase3-terse100eos-1024-q8_0.gguf` (Jetson
llama.cpp, terse, max_side 1024), branch commit `7b51b7c`. Constants as pre-registered
(CARRY_HZ 6.15, CAND_HZ 3.075, MATCH_FLOOR 0.10 shadow-only, DIST_FLOOR 0.25, cover_s 10.0,
ROI 512 / margin 2.0 / min_side 256, REANCHOR_OFFSETS (90, 165)).
**Matrix wall: ~4.4 min total** (12 cells, 21–22 s each) — see estimate-vs-actual below.

| cell | pass | weak_pass (SWAP) | deliver_iou (vs target GT) | deliver_iou_distractor | coverage | reanchor accepted | shadow_sel (agree?) | fail_class | V (what I saw) |
|---|---|---|---|---|---|---|---|---|---|
| DD_WSEL_car10_240 | PASS | — | 0.7988 | 0.0 | 1.0 | [True, True] | target (agree) | — | real palm-lined highway; green delivered box on the white target car, red GT boxed around it, lock persists to f=645 |
| DD_SWAP_car10_240 | PASS | True | 0.0 | 0.7557 | 0.0 | [True, True] | None (DISAGREE) | — | green box on the *other* car up-road, red GT on the target untouched — correct distractor delivery |
| DD_WSEL_car10_615 | PASS | — | 0.8679 | 0.0207 | 1.0 | [True, True] | None (DISAGREE) | — | green on target, red GT concentric, held at f=1020 |
| DD_SWAP_car10_615 | PASS | True | 0.0 | 0.8758 | 0.0 | [True, True] | distractor (agree) | — | green on the dark distractor car, red GT on the white target — two distinct vehicles, unambiguous |
| DD_WSEL_car9_300 | PASS | — | 0.8402 | 0.0 | 0.9733 | [True, True] | target (agree) | — | green on target at f=705, red GT concentric |
| DD_SWAP_car9_300 | PASS | True | 0.0 | 0.7253 | 0.0 | [True, True] | distractor (agree) | — | deliver frame f=540 opened: green box on the distant lead car (the distractor), red GT on the target below. Later f=705 the green box sits at the top frame edge — the distractor is *receding up-road and exiting the FOV*, not drifting to junk |
| DD_WSEL_car7_460 | PASS | — | 0.8911 | 0.0 | 1.0 | [True, True] | target (agree) | — | roundabout scene, green on the white target car at f=865 |
| DD_SWAP_car7_460 | **FAIL** | True | 0.0 | 0.0 | 0.0 | [True, True] | None (DISAGREE) | `carry-off-object` | deliver frame f=700 opened: blue distractor GT is on the dark car at the roundabout, the green delivered box is on **empty kerb/vegetation at the far-left frame edge** — the failure is plainly visible, exactly the predicted junk carry |
| DD_WSEL_car9_560 | PASS | — | 0.8637 | 0.0 | 0.97 | [True, True] | target (agree) | — | green on target at f=920, red GT concentric, white distractor alongside left un-boxed |
| DD_SWAP_car9_560 | PASS (marginal) | True | 0.0 | 0.2843 | 0.0 | [True, True] | distractor (agree) | — | deliver frame f=740 opened: green box sits *inside* the blue distractor GT on the distant lead car (green slightly smaller — hence the marginal 0.2843), red GT on the target below. f=920 shows it at the top edge as the distractor exits the FOV |
| DD_WSEL_car3_200 (control) | PASS | — | 0.7256 | 0.0 | 0.9367 | [True, True] | distractor (DISAGREE) | — | top-down golf-course road; green on target at f=605, red GT concentric — **flipped to PASS as predicted** |
| DD_SWAP_car3_200 (control) | PASS | True | 0.0 | 0.8864 | 0.0 | [True, True] | distractor (agree) | — | green on a different car up-road from the red-GT target |

- **RQ-P5.14a (WSEL >= 4/5 gating): 5/5 -> YES**
- **RQ-P5.14b (SWAP >= 4/5 gating, strengthened): 4/5 -> YES**
- **OVERALL RQ-P5.14: YES**, and the visual gate V did not downgrade it (all 24 `viz_*.png`
  opened with the Read tool, plus 3 deliver-frame overlays extracted for the SWAP cells whose
  late frames were ambiguous; every scored PASS is corroborated on the pixels and the one
  scored FAIL is visibly off-object).

`verdict_p56.py` output (verbatim, also in `raw/verdict.txt`):

```
cell                   pass  weak   d_iou d_dist    cov reanchor       fail_class / reason
----------------------------------------------------------------------------------------------------
DD_SWAP_car10_240      True  True     0.0 0.7557    0.0 [True, True]
DD_SWAP_car10_615      True  True     0.0 0.8758    0.0 [True, True]
DD_SWAP_car3_200       True  True     0.0 0.8864    0.0 [True, True]
DD_SWAP_car7_460       False True     0.0    0.0    0.0 [True, True]   carry-off-object:
DD_SWAP_car9_300       True  True     0.0 0.7253    0.0 [True, True]
DD_SWAP_car9_560       True  True     0.0 0.2843    0.0 [True, True]
DD_WSEL_car10_240      True  None  0.7988    0.0    1.0 [True, True]
DD_WSEL_car10_615      True  None  0.8679 0.0207    1.0 [True, True]
DD_WSEL_car3_200       True  None  0.7256    0.0 0.9367 [True, True]
DD_WSEL_car7_460       True  None  0.8911    0.0    1.0 [True, True]
DD_WSEL_car9_300       True  None  0.8402    0.0 0.9733 [True, True]
DD_WSEL_car9_560       True  None  0.8637    0.0   0.97 [True, True]

RQ-P5.6a (DD WSEL >= 4/5 gating): 5/5 -> YES
RQ-P5.6b (DD SWAP >= 4/5 gating, strengthened): 4/5 -> YES
OVERALL: YES
```

(The script prints the `P5.6` lineage tag; `RQ-P5.6a/b` ≡ `RQ-P5.14a/b`, per the provenance
section — the rig was imported byte-unchanged and its internal labels were not touched.)

**Weak-vs-strong SWAP gap.** Weak rule (old P5.3/P5.5 off-target-only) 6/6 vs strengthened 5/6.
The single cell the old rule flattered is `car7:460`: its delivered box is off *every* object,
so "not on the target" was trivially satisfied. The strengthened rule (must also land >= 0.25
on the hand-annotated distractor) is what catches it. This is the honest-scoring point the
pre-registration predicted, confirmed.

**Shadow re-ground (non-gating — the real-data DD-vs-RG attribution).** 4 of 12 cells DISAGREE
with DD: `DD_SWAP_car10_240` (shadow `None`), `DD_SWAP_car7_460` (`None`),
`DD_WSEL_car10_615` (`None`), `DD_WSEL_car3_200` (selected `distractor` — a wrong-object
selection, not just a miss). Three of the four disagreements are the prompt-time re-ground
returning **NO_MATCH**, i.e. the exact P5.3/P5.5 failure mode, on scenes where the carried box
was on the right object and DD passed. **Latency:** DD `acquire_s = 0.00` on all 12 cells by
construction, vs shadow full-frame re-ground mean **4.51 s** (min 4.48, max 4.53).

**Estimate-vs-actual.**

| quantity | estimate | actual | note |
|---|---|---|---|
| matrix wall (R2) | 45–75 min | **~4.4 min** (21–22 s/cell) | badly over-estimated: the Jetson q8_0 server is booted/reused once and each cell makes only 2 idle ROI re-anchors + 1 shadow call, and the 10 s coverage window is replayed from disk, not realtime |
| WSEL gating | 5/5 | **5/5** | exact |
| SWAP gating | 4/5, car7:460 the fail | **4/5, car7:460 the fail** | exact, including the named cell and its `carry-off-object` class |
| car9:560 SWAP margin | ~0.28 vs 0.25 floor | **0.2843** | exact; it remains the one cell a small carry regression would flip |
| car3:200 control WSEL | flips to PASS | **PASS** (0.7256) | confirms the P5.3/P5.4 "resolution-bound" family was a re-grounding artifact, not a carry limit |
| shadow latency | 4.5–5 s | **4.51 s mean** | exact |
| overall | YES | **YES** | — |
| INFRA / crashes | 0 | **0** | no retries, no aborts, no INVALID cells |

**What broke / what surprised.**
- Nothing broke: 12/12 cells scored first time, no crash, no hang, no rerun.
- The pre-registered predictions were correct cell-for-cell, including the named failure and
  the marginal cell's IoU to two decimals — unusual, and worth flagging as such: the design was
  written against an audit of the P5.5 raw runs, so the "prediction" was well-informed rather
  than a blind forecast. It is evidence the rig is deterministic, not evidence of foresight.
- The surprise is on the **shadow** side, not the DD side: the re-ground contract fails
  (`None` / wrong object) on 4/12 cells *whose carried track was fine*. That is the contract
  separation four sim cycles (P5.10–P5.13) tried and failed to manufacture, present in the real
  video for free — because on real UAV123 frames the prompt-time VLM re-ground is genuinely
  hard, while on clean Gazebo renders it never missed.
- Ambiguity found in the visual-gate wording (recorded, not silently resolved): the README says
  `viz_late` "should show the same lock persisting", but `viz_late` is sampled at 75% of the
  overlay — 5–6 s *after* the deliver frame — and in two SWAP cells (`car9:300`, `car9:560`)
  the correctly-delivered distractor had by then driven up-road to the frame edge. Read
  literally, that could have been called a V contradiction and flipped the verdict to NO. It was
  resolved by extracting and opening the actual **deliver-frame** overlays (the frame the score
  is computed on), which show the box correctly on the distractor. A future pre-registration
  should dump the deliver frame itself as the gating PNG, not a fixed 25%/75% sample.

## Definition of done

1. This README filled — Results, verdict output verbatim, V lines, estimate-vs-actual.
2. RESULTS row(s) appended to `docs/results/part5-anticipatory.md`.
3. QUESTIONS entry (RQ-P5.14a/b + one-line verdict) appended to
   `docs/questions/part5-anticipatory.md`.
4. DECISIONS entry appended to `docs/decisions/part5-anticipatory.md` — the audit-override of
   the steer's deferral, the bank-v3 rejection (+ the mandatory displacement/z-order/peak-
   diversity gates carried forward), and the p56→P5.14 renumber all qualify.
5. SOURCES unchanged unless something new is pulled in.
6. 2–3 deliverables under `proof/`, committed and captioned: `make_proof.py` figures
   (pass grid + contract figure) plus 1–2 headline artifacts — candidates:
   `DD_SWAP_car10_240` viz frames (the carry-was-right cell — before/after vs P5.5's NO_MATCH)
   and `DD_SWAP_car7_460` viz frames (the predicted honest failure, box visibly off-object).
   Clips allowed (behaviour is the point): copy the headline `overlay.mp4` to `proof/` renamed
   `p514_<cell>.mp4`.
7. Committed on `experiment/realvid-dd-select`; **not merged** (the orchestrator audits, then
   merges).

## Proof deliverables (committed, `proof/`)

| file | what it shows | run / config |
|---|---|---|
| `p56_pass_grid.png` | per-cell PASS/FAIL for P5.3 RG vs P5.5 MC-RG vs **P5.14 DD**, WSEL and SWAP side by side. DD's row is green everywhere except `car7:460` SWAP; the two rows above it carry the historical NOs. The numbers-are-the-point figure for the contract change. | this campaign + the committed P5.3/P5.5 `runs/` |
| `p56_contract.png` | left: delivered-box IoU vs the *correct* object at the prompt, per cell, with the 0.25 floor and shadow agree/disagree tags (`s` / `S!`); right: select latency — DD 0.00 s vs shadow full-frame re-ground ~4.51 s on every cell. | same |
| `p514_swap_car7_460_deliver_OFFOBJECT.png` | **negative proof.** The one FAIL, at its deliver frame f=700: blue distractor GT on the dark car at the roundabout, green delivered box on empty kerb at the far-left edge. A junk carry fails DD *directly* — no delivery contract can rescue it. | `runs/DD_SWAP_car7_460`, DD SWAP |
| `p514_swap_car9_560_deliver_PASS.png` | the marginal PASS at f=740: green delivered box inside the blue distractor GT (IoU 0.2843, floor 0.25) — shows what "just over the bar" looks like on the pixels. | `runs/DD_SWAP_car9_560`, DD SWAP |
| `p514_DD_WSEL_car10_240.mp4` / `p514_DD_SWAP_car10_240.mp4` | behaviour clips of the same scene under the two operator phrases: the delivered box lands on the target in WSEL and on the distractor in SWAP, both at zero acquire latency. Re-encoded to 854px/CRF 28 from `runs/*/overlay.mp4` for size. | `runs/DD_{WSEL,SWAP}_car10_240` |
