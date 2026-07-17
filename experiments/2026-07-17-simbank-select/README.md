# P5.10 — Select on the scene bank: direct delivery vs prompt-time re-ground (paired A/B, n=12)

**Pre-registered:** 2026-07-17T17:25Z (Madrid wall-clock).
**Status:** PRE-REGISTERED, not yet run.
**Branch:** `experiment/simbank-select`. **Part V** (anticipatory grounding / warm-start acquire).
**Division of labour:** design + patches by Fable; **Opus runs the matrix and fills Results only — do
NOT re-patch code.** All files under "Code changes" are already committed; both selfchecks and the
bank preflight passed at pre-registration time on this machine.
**Prior art:** P5.3/P5.4/P5.5 (three select-on-command NOs, `../2026-07-14-*-select*/`), the PARKED
P5.6 direct-delivery pre-reg (`experiment/direct-delivery-select`, `df6de31`, never run), and the
P5.9 scene bank this experiment consumes (`../2026-07-17-kerbsafe-scenebank/`, RQ-P5.9 = YES).

## Research question

**RQ-P5.10:** On the P5.9 12-clip sim scene bank (two colour-distinct cars, exact per-frame GT for
both), with both candidates carried from oracle f0 seeds under the deployed two-candidate SAM2
budget, does the **direct-delivery contract** (phrase binds to the carried candidate by stored
caption; its carried box at the prompt frame is delivered; no VLM call, acquire_s = 0) select
correctly at scale — **and does it beat the P5.3 re-ground contract** (full-frame VLM at the prompt,
IoU-match vs carried boxes, deliver the matched track at prompt + measured latency) **evaluated
paired on the identical carries**?

- **RQ-P5.10a (DD works at n=12):** DD delivers the named car (delivery rule below) in
  **>= 10/12 clips on EACH leg** (white-phrase leg AND blue-phrase leg).
- **RQ-P5.10b (contract separation):** over all 24 (clip, leg) cells,
  **DD_total >= RG_total + 4** (a pre-registered practical margin; if every discordant cell favors
  DD, 4 discordant cells corresponds to a two-sided sign-test p = 0.125 — reported as a margin, not
  framed as significance).
- **Overall verdict: YES iff both.** Computed mechanically by `verdict_p510.py`; the visual gate V
  (below) can only downgrade to NO.

Delivery rule (per contract, per cell): delivered box IoU vs the NAMED car's GT at that contract's
delivery frame **>= 0.25** (P5.3-consistent lock floor) **AND > IoU vs the other car's GT**
(dominance — robust to any GT-GT overlap; the strict P5.6-shape variant `IoU_other < 0.25` is also
computed, non-gating). RG additionally requires the match step to select the named candidate
(MATCH_FLOOR 0.10, argmax — numerically identical to P5.3/P5.4/P5.5) and no clip-end overrun.
Preflight measured **max GT-GT IoU = 0.000 across all 12 clips**, so dominance and strict coincide
on this bank unless a delivered box is junk; both are recorded.

## Context & rationale (audit of P5.9 before building on it)

**Bank validity — spot-checked from the raw artifacts, not the P5.9 README:** `bank01/gt.jsonl`
carries 2 track IDs on every one of 240 frames with per-object phrases ("the white car" /
"the blue car"), pixel bboxes, visibility, purity and frag fields; `--preflight` (committed,
offline) re-verified all 12 clips on this machine: 240 frames each on disk, phrases distinct and
exactly the expected pair, both cars visible 240/240 (co-visibility is real, not just >= 0.80),
no dead/flat frames at f10/f75/f180, f75 != f76 byte-wise. The bank supports a select experiment
structurally.

**The critical bias question, head-on.** A select experiment on this bank is at risk of being a
rigged test: oracle f0 seeds + colour-distinct clean renders + string-equality phrase binding mean
the DD contract *should* be near ceiling, and a DD-only "12/12 PASS" would carry almost no
information about the P5.3/4/5 failure modes (prompt-time NO_MATCH, carry-drift). The design
confronts this three ways:

1. **The gating claim is the PAIRED contrast, not DD's absolute number.** Every cell scores BOTH
   contracts on byte-identical carries (the carry pass is computed once per clip and cached), so
   the experiment measures the *contract difference* under controlled conditions — the exact
   attribution P5.3/4/5 could not give, because on UAV123 the carries, the VLM and the scenes all
   varied together and distractor GT was hand-annotated at one frame only.
2. **The RG arm directly tests the steer's premise.** The SIMULATOR steer's rationale was that the
   select arc was *scene-data-starved* — UAV123 almost never offers two same-class candidates with
   a clean disambiguating attribute. If that premise is right, the old contract should work here:
   the VLM gets a rendered frame with exactly one white and one blue car and the phrase "the white
   car". If RG *still* fails (NO_MATCH / miss), the bottleneck is the VLM or the sim-to-real gap,
   not scene murk. Every RG fail is mechanically attributed (`vlm_on` = named/other/miss vs exact
   GT), separating "the VLM cannot ground Gazebo renders at all" from "it grounds fine but the
   match step loses it".
3. **A too-easy bank cannot manufacture a YES.** If both contracts sit at ceiling, RQ-P5.10b fails
   its margin and the overall verdict is NO with the pre-registered branch-2/3 interpretation
   (below) — an easy sim produces an honest negative, not a fake positive.

**External validity is explicitly bounded:** a P5.10 YES validates the delivery-contract change on
clean-attribute scenes at n=12. It does **not** claim real-video select is solved; it gates
unparking P5.6 (the same contract on UAV123, still parked on `experiment/direct-delivery-select`).

**Adaptations of the parked P5.6 design to the bank (stale-assumption audit):** P5.6 was written
against UAV123 (30 fps, hand-annotated distractor GT, t_p = 8 s, 10 s coverage). The bank is 240
frames at 25 fps = **9.6 s per clip**, which forces real changes, all pre-registered here:
`t_p = 3.0 s` (prompt f75; an 8 s idle window does not fit), RG delivery lands at
f75 + round(acquire_s x 25) ~= f183–f213 for the expected 4.3–5.5 s acquire (overrun iff
acquire_s > 6.56 s — scored OVERRUN fail, P5.3's "deliver past clip end"), and coverage is
clip-end-bounded (6.6 s for DD, ~1–2 s for RG) and therefore **non-gating** (in P5.3-5, coverage
never flipped a correctly-delivered cell). P5.6's hand-annotation machinery (`annotate_p56.py`,
`curation/`) is obsolete here — the bank has exact GT for both objects, so the strengthened-SWAP
intent (delivered box must be ON the named object, junk cannot pass) is enforced exactly, on every
frame, via the delivery rule. P5.6's idle ROI re-anchor maintenance is dropped: with a 3 s idle
window it has no room to act (offsets were at +3 s/+5.5 s), and dropping it keeps the cell
single-factor (contract is the only difference between DD and RG).

**Known limitations of bank v1 recorded up front** (these bound what a YES means, and are the
pre-registered triggers for a bank-v2 cycle): no crossings/occlusion (max GT-GT image IoU 0.000 —
the ID-switch hazard is under-exercised), 3 s idle under-exercises long-idle carry-drift (the P5.5
surviving failure mode), only 2 objects (the P5.4 in-crop-third-object mode cannot occur), and
longer clips are NOT a free fix (the calibrated kerb-safe corridor caps s <= 70, so 9.6 s at the
current speed bands is the safe length; longer needs recalibration).

**Rejected alternatives (DECISIONS seed):**

- *Run the parked P5.6 verbatim on UAV123 instead.* Deferred, not dead — it stays the designated
  follow-up if P5.10 lands branch 1. Rejected for this cycle because the steer directs using the
  just-delivered sim, because n=5 with one hand-annotated distractor frame is strictly weaker
  evidence than n=12 with exact dual per-frame GT, and because only the sim A/B can answer the
  scene-bound-vs-contract-bound attribution question that three NOs left open.
- *Scale/harden the bank first (more seeds, crossings, longer clips).* Rejected as premature:
  hardening is blind until we measure whether v1 scenes discriminate the contracts at all —
  P5.10's RG arm IS that measurement, and branches 2/3 explicitly route to a bank-v2 cycle with
  the specific hardening the fail classes call for. n=12 is already 2.4x the arc's n=5.
- *VLM-in-the-loop idle discovery (no oracle seeds).* Rejected this cycle: two sequential
  full-frame discovery calls (~9.4 s) do not fit the 9.6 s clip before a usable prompt, and it
  would confound seeding with the contract factor. Candidate discovery stays a recorded open
  problem (as in P5.1–P5.6).
- *Union-crop / ROI-crop select for the RG arm.* Dead lever (P5.4) — RG is full-frame P5.3,
  byte-consistent floors (MATCH_FLOOR 0.10, lock 0.25).

**Pre-registered interpretation branches** (printed by `verdict_p510.py`; the matching one applies):

1. a YES, b YES — contract change validated on clean scenes at n=12; next lever = unpark P5.6.
2. a YES, b NO with RG_total >= 20 — RG near ceiling: the P5.3/4/5 NOs are scene-bound, not
   contract-bound; DD's remaining edge is latency (0 s vs ~5 s).
3. a YES, b NO with RG_total < 20 — contracts not separable on bank v1; harden the bank.
4. a NO — DD fails on clean sim: carry-bound or stack-on-sim gap; select is blocked upstream of
   any delivery contract.

## Method (one cell = one clip x one leg; both contracts inside)

Per clip (12): load `bank<NN>/frames/*.png` + `gt.jsonl`; seed two SAM2 carries at f0 from both
cars' GT boxes (oracle-seed scope cut, unchanged P5.1–P5.6); one **deterministic carry pass**
stepping both candidates on every 8th frame (`CAND_STRIDE 8` -> 3.125 Hz per candidate, the E1
6.15 Hz on-Orin budget shared two ways) plus forced samples at f75 and f239, zero-order hold
between samples, cheap frame-health asserts on every sampled frame (>99%-one-colour = failed
render; byte-identical consecutive samples = dead feed). The pass is cached to
`runs/carry_<clip>.json` and reused by both legs and any resume (SAM2 bf16 is not guaranteed
bit-identical across sessions — the cache is what keeps the paired comparison exact; **never
delete it mid-matrix**).

Per leg (white: "the white car"; blue: "the blue car"):

- **DD:** deliver `zoh(named carry, f75)`. Fail classes: CARRY_LOST / CARRY_SWITCH / CARRY_DRIFT.
- **RG:** fire the deployed VLM (Qwen2-VL-2B q8_0 terse, Jetson llama.cpp over SSH, full frame,
  max_side 1024) on frame 75 with the same phrase; measure `acquire_s` wall; IoU-match the raw box
  vs both carried boxes at f75 (floor 0.10); deliver the matched track's ZOH box at
  f75 + round(acquire_s x 25). Fail classes: NO_BOX / OVERRUN / NO_MATCH / MATCH_WRONG /
  DELIVERY_LOST / DELIVERY_SWITCH / DELIVERY_DRIFT; `vlm_on` (named/other/miss) recorded always.
  A clean parse-fail (None) is a legitimate NO_BOX result and is never retried; only transport
  EXCEPTIONS get one reboot+retry (no outcome shopping).
- Non-gating: coverage (per-frame ZOH IoU vs named GT to clip end from each contract's delivery
  frame), strict-rule variant, GT-GT overlap at prompt, carried tracks embedded in results.json.

n=1 deterministic discipline as P5.3–P5.6: temperature-0 VLM, fixed frame arithmetic; first scored
result stands, no reruns of scored cells.

## Code changes (already committed — Opus: do NOT edit these files)

| File | Role |
|---|---|
| `select_p510.py` | the rig: bank loader + preflight, deterministic dual carry pass + cache, DD/RG scoring, fail classes, overlays, VLM client (one reboot+retry on transport exception only), `--selfcheck` (offline: every fail class, dominance-vs-strict, ZOH, parser, overlay writer, health asserts — all exercised on scripted carries/VLM; no GPU/Jetson) |
| `verdict_p510.py` | mechanical verdict: per-cell table, RQ-a/b, overall, infra cap, interpretation branches; `--selfcheck` fabricates runs and asserts counting + INCOMPLETE + infra rules |
| `make_proof.py` | proof figures from `runs/*/results.json` + overlays (pass grid, fail-class histogram, mechanically-picked headline DD-vs-RG pair) |

Selfchecks (offline, no GPU/Jetson/bank) — both PASSED at pre-registration:

```bash
.venv-ft/bin/python experiments/2026-07-17-simbank-select/select_p510.py --selfcheck
.venv-ft/bin/python experiments/2026-07-17-simbank-select/verdict_p510.py --selfcheck
```

## Run matrix (Opus starts here)

Config: **RTX 3090 workstation** runs the harness + SAM2 (`facebook/sam2-hiera-small` per
`stream_carry.MODEL`, bf16 autocast); the **Jetson Orin Nano 8 GB** serves the VLM
(Part II/III Qwen2-VL-2B **q8_0** terse via `JetsonBackend` over `ssh jetson`, max_side 1024) —
this is the deployed grounding runtime, so the RG arm's latency and accuracy are the deployment
numbers. Jetson power: 15 W + clocks (NOPASSWD; there is no MAXN on this board). Scene source:
the committed P5.9 bank runs already on this disk (`--preflight` re-verifies before anything
boots). Software versions are recorded into every `results.json` at runtime (torch / numpy / cv2 /
python / sam2 model id); copy one into Results.

```bash
cd /home/gara/jetson
EXP=experiments/2026-07-17-simbank-select

# 0. offline gates (must print "select_p510 selfcheck OK", "verdict_p510 selfcheck OK",
#    "preflight OK (12 clips)"; any failure -> STOP, record, do not run the matrix)
.venv-ft/bin/python $EXP/select_p510.py --selfcheck
.venv-ft/bin/python $EXP/verdict_p510.py --selfcheck
.venv-ft/bin/python $EXP/select_p510.py --preflight

# 1. Jetson power config (idempotent, NOPASSWD)
ssh jetson "sudo nvpmodel -m 0 && sudo jetson_clocks"

# 2. the matrix: 12 clips x 2 legs = 24 cells, sequential, resumable
#    (completed cells skipped; carry pass cached per clip and shared by both legs)
mkdir -p $EXP/raw
.venv-ft/bin/python $EXP/select_p510.py --matrix --out $EXP/runs \
    2>&1 | tee $EXP/raw/matrix.log

# (single-cell rerun after a CRASH only — never after a scored result:
#  .venv-ft/bin/python $EXP/select_p510.py --matrix --only bank03 --legs white --out $EXP/runs)

# 3. mechanical verdict (paste its FULL output verbatim into Results)
.venv-ft/bin/python $EXP/verdict_p510.py | tee $EXP/raw/verdict.txt

# 4. proof figures (after the verdict)
.venv-ft/bin/python $EXP/make_proof.py
```

Gotchas: the matrix keeps ONE Jetson server for all 24 cells (boot ~1–2 min once); a transport
exception mid-call triggers exactly one reboot+retry and is counted in `vlm_reboots_so_far`.
`runs/**/results.json` is auto-tracked by git; overlays and `carry_*.json` are gitignored (stay on
disk; copy nothing by hand — `make_proof.py` composes the committed evidence). Disk ~200 MB.
**Never delete `runs/carry_<clip>.json` or a completed cell dir.**

### Abort criteria (mechanical)

- Selfcheck or preflight fails -> STOP; record the output in Results; the matrix does not run.
- A cell CRASHES (exception, not a scored FAIL) -> snapshot the traceback into `raw/`, retry that
  cell once via `--only <clip> --legs <leg>`; a second crash -> create `runs/<clip>_<leg>.INFRA`
  (one-line reason inside) and continue. `verdict_p510.py` counts an INFRA cell as FAIL for both
  contracts; **<= 1 INFRA cell tolerated, >= 2 -> overall NO [infra]** (enforced by the script).
- No new `results.json` for > 20 min -> kill the matrix, snapshot `raw/matrix.log`, resume (the
  matrix skips completed cells); treat the stuck cell per the crash rule.
- Jetson unreachable / q8_0 server fails to boot twice in a row -> STOP, record (the RG arm cannot
  be measured; the campaign is INCOMPLETE, not a verdict).
- Never rerun a scored cell to shop outcomes; first scored result stands.

## Visual verification (gating — per the CLAUDE.md "Look at it" rule)

Open with the **Read tool** before writing any verdict — **minimum 16 images, plus every fail**:

- For clips **bank01, bank04, bank07, bank10**, both legs: `runs/<clip>_<leg>/overlay_dd_f0075.png`
  and `runs/<clip>_<leg>/overlay_rg_f0*.png` (16 images — the fixed sample, chosen up front so a
  clean sweep still gets looked at).
- For EVERY cell where DD or RG is FAIL: that cell's `overlay_dd_f0075.png`,
  `overlay_vlm_f0075.png` and `overlay_rg_f0*.png`.

**PASS looks like:** oblique aerial view of grey asphalt, one white car and one blue car, each an
intact connected body (P5.9 quality); the **green delivered box sits tightly on the car the phrase
named** (red thin box = named car's GT, orange thin box = the other car's GT; in a white-leg cell
green must sit on the white car, in a blue-leg cell on the blue car); in `overlay_vlm_f0075.png`
the yellow raw VLM box (RG) also sits on the named car. Frame index and pass/fail text are burned
into each overlay top-left and must agree with the results.json verdict you report.

**FAIL looks like:** the green box on the WRONG car (switch), on empty asphalt/kerb (drift/junk),
missing entirely (lost/NO_BOX/NO_MATCH — overlay then shows only red+orange GT boxes), or a yellow
VLM box on the wrong car or on nothing. Black/flat frame or missing PNG = that cell INVALID —
never a log-inferred pass.

Record one line per opened cell in Results ("what I saw"). If what a frame shows contradicts the
mechanical verdict of that cell in either direction, that disagreement is a finding — record it
with the frame path; V downgrades the overall verdict to NO if any opened PASS cell's frames
contradict its scored result.

## Verdict rules (mechanical — Opus does not deliberate)

- `verdict_p510.py` output is the verdict: per-cell PASS/FAIL, RQ-P5.10a (DD >= 10/12 each leg),
  RQ-P5.10b (DD_total >= RG_total + 4 over 24 cells), overall YES iff both, INFRA cap, and the
  matching interpretation branch. **Overall = script YES AND V passed.** Paste the full output.
- INCOMPLETE (exit 2) -> campaign stays INCOMPLETE until every cell has results.json or an .INFRA
  marker.
- Estimate-vs-actual: fill the table below; a wrong estimate is content, not a problem.

## Estimates (all marked as estimates)

- **Runtime:** SAM2 + model load ~1 min; carry pass ~20–60 s/clip (33 sampled steps x 2 candidates
  on the 3090); Jetson boot ~1–2 min once; VLM ~4.3–5.5 s/call x 24; **matrix total ~15–35 min**;
  verdict + proof ~2 min.
- **acquire_s:** 4.3–5.5 s (same 1280x720 -> max_side 1024 full-frame path as P5.3's 4.5–4.9 s);
  RG delivery ~f183–f213; OVERRUN not expected (needs > 6.56 s).
- **DD:** white leg 12/12, blue leg 11–12/12 (clean renders, 3 s idle, no crossings; residual risk
  = SAM2 ID ambiguity on similar hatchback silhouettes). RQ-P5.10a expected YES.
- **RG:** genuinely uncertain — the RefDrone-fine-tuned VLM has never seen a Gazebo render.
  Point estimate 6–9/12 per leg (RG_total ~12–18), fail classes dominated by NO_BOX/VLM_MISS
  (sim-gap) and/or NO_MATCH. This is the number the experiment exists to measure.
- **Overall predicted: YES via branch 1** (DD ~23–24 vs RG ~12–18). Live alternative: branch 2
  (RG also near ceiling — solid-colour cars on clean asphalt may be an *easy* grounding target,
  in which case the P5.3/4/5 NOs read as scene-bound). Either outcome redirects the arc.
- Disk ~200 MB under `runs/` (mostly overlays, gitignored). No new external sources -> no SOURCES
  entry expected.

## Results (filled by Opus — TBD)

Run date/time: TBD. Versions (from any results.json): TBD. Rig: RTX 3090 workstation + Jetson
Orin Nano 15 W + jetson_clocks. Matrix wall time: TBD. VLM reboots: TBD. INFRA cells: TBD.

| cell | DD | dd_class | dd IoU_named | RG | rg_class | vlm_on | acquire_s | deliver_f | match_ious (0/1) | cov_dd | cov_rg | V (one line) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bank01_white | | | | | | | | | | | | |
| bank01_blue | | | | | | | | | | | | |
| bank02_white | | | | | | | | | | | | |
| bank02_blue | | | | | | | | | | | | |
| bank03_white | | | | | | | | | | | | |
| bank03_blue | | | | | | | | | | | | |
| bank04_white | | | | | | | | | | | | |
| bank04_blue | | | | | | | | | | | | |
| bank05_white | | | | | | | | | | | | |
| bank05_blue | | | | | | | | | | | | |
| bank06_white | | | | | | | | | | | | |
| bank06_blue | | | | | | | | | | | | |
| bank07_white | | | | | | | | | | | | |
| bank07_blue | | | | | | | | | | | | |
| bank08_white | | | | | | | | | | | | |
| bank08_blue | | | | | | | | | | | | |
| bank09_white | | | | | | | | | | | | |
| bank09_blue | | | | | | | | | | | | |
| bank10_white | | | | | | | | | | | | |
| bank10_blue | | | | | | | | | | | | |
| bank11_white | | | | | | | | | | | | |
| bank11_blue | | | | | | | | | | | | |
| bank12_white | | | | | | | | | | | | |
| bank12_blue | | | | | | | | | | | | |

- **RQ-P5.10a (DD >= 10/12 each leg): TBD**
- **RQ-P5.10b (DD_total >= RG_total + 4): TBD**
- **Overall + interpretation branch: TBD**
- `verdict_p510.py` full output (verbatim): TBD
- Estimate-vs-actual table: TBD

## Deliverables checklist (definition of done)

- [ ] Results table + verdict output + V lines filled above; estimate-vs-actual noted.
- [ ] `proof/p510_pass_grid.png` — the 24-cell DD-vs-RG pass grid (the headline number). Caption
      here with the final counts.
- [ ] `proof/p510_failclass.png` — fail-class histogram per contract (the attribution evidence).
- [ ] `proof/p510_headline_dd_vs_rg.png` — the mechanically-picked headline cell, DD delivery vs
      RG delivery on the same clip/leg. Caption with what it shows.
- [ ] RESULTS row appended to `docs/results/part5-anticipatory.md`.
- [ ] QUESTIONS entry (RQ-P5.10a/b + one-line verdict) appended to
      `docs/questions/part5-anticipatory.md`.
- [ ] DECISIONS entry appended to `docs/decisions/part5-anticipatory.md`: A/B-on-bank over
      verbatim-P5.6 and over bank-scaling (rationale in "Rejected alternatives"); the dominance
      delivery rule; t_p = 3.0 s forced by clip length; maintenance dropped for single-factor.
- [ ] SOURCES.md unchanged unless something new was pulled in.
- [ ] Committed on `experiment/simbank-select`; **not merged** (the loop's reviewer merges).
