# R-36 — maintain-and-deliver vs select-among-candidates, paired at n>=25

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md` (S1-S7). Tracked as **R-36** in
`thesis/REMEDIATION.md`. Wave B (real-imagery, no rig build; runs in parallel with the R-35 flight
build). If this README and the program doc disagree on the frozen gate, the program doc wins.

## Status / next step

- **DONE 2026-07-24 — verdict NO [underpowered, scene-starved].** The reachability risk fired:
  8/10 curated candidates were single-target, the bank could not reach n>=25, and the analysis
  landed in the pre-registered MISS branch (b=5/c=0, p=0.0625 on the audit-clean n=14 bank). See
  `## Results` below. Claim registered; ledgers + `thesis/claims.json` updated.

## Question

RQ-R36: at a properly powered n, does maintain-and-deliver (carry the named salient target over the
idle window, deliver on command) **outperform select-among-candidates** (name one of several, bind
at prompt time)? This powers the Part V select negative, which was only ever called descriptively.

## Design (frozen)

- **Paired-binary, exact McNemar** (two-sided p<0.05), deflated to distinct clips (R-29 ICC
  upper95), Part-V Holm family.
- **Arm A = WSEL** (maintain-and-deliver): `leg_pass_p56(leg,'wsel')` = selection_correct AND
  genuine_lock AND coverage >= 0.5.
- **Arm B = SWAP** (name the distractor; strengthened): `leg_pass_p56(leg,'swap')` =
  selection=='distractor' AND deliver_iou < 0.25 AND deliver_iou_distractor >= 0.25 (DIST_FLOOR)
  AND reason is None.
- **Unit = one distinct UAV123 base capture** (strip onset + `_s`). One curated hard SWAP scene per
  clip (multiple onsets per clip wash out under S1). **n >= 25 distinct clips, target 30.**

### FROZEN GATE (verbatim)

Reject H0(maintain==select) at exact two-sided McNemar p<0.05, deflated to distinct clips, Part-V
Holm. Discordant = pairs where WSEL and SWAP outcomes differ; b = (WSEL pass, SWAP fail); c =
(WSEL fail, SWAP pass). Reaches alpha only at **b+c >= 6 one-directional**. Directional expectation
b > c.

### REACHABILITY — the one honest risk, disclosed up front

The committed SWAP data (P5.18, 13 distinct clips) is **b=3, c=0, n=13 -> exact McNemar p=0.25**.
That is **3 discordant pairs short of significance and NOT reachable as-is**. R-36 therefore requires
**>=12 NEW distinct SWAP-hard base clips** curated to reproduce the ~0.23 WSEL>SWAP discordance
one-directionally. Projected b~6 at n=25-26 is **marginal**; the plan over-provisions to **n~30**
(projected b~7). New clips are drawn from SWAP-hard families:
- **late-entry** (target enters after the idle window, e.g. car18-like),
- **carry-drift** (small/fast target the carry can leak off, e.g. person10-like),
- **distractor-confusion** (>=2 same-class objects near the target).

**Pre-registered miss branch:** if b<6 or the discordance splits two-directional ->
**"select fails but is not separable-from-maintain at this n"** — cited as the powered ceiling of the
select negative, honest content, not a failed run. This is stated so no gate is chosen post-hoc.

## Command (intended)

```bash
# curate + GT-verify the new SWAP-hard clips into the bank
.venv-ft/bin/python experiments/2026-07-23-r36-maintain-vs-select/curate_r36.py \
    --families late-entry,carry-drift,distractor --n-new 17 --verify --out runs/r36/bank
# paired matrix over the full >=25-clip bank (reuses the P5.18 select_p56 legs)
.venv-ft/bin/python experiments/2026-07-20-n25-select/select_p56.py \
    --bank runs/r36/bank --arms wsel,swap --out runs/r36
# verdict + McNemar + required-audit list
.venv-ft/bin/python experiments/2026-07-20-n25-select/verdict_p518.py runs/r36
```

## Environment / versions

RTX-3090; Python 3.12 `.venv-ft` (`uv.lock`); SAM2 (hiera, TensorRT fp16 per E1, `prune_after=32`);
deployed q8_0 VLM via `JetsonBackend` over SSH for prompt-time grounding (Jetson 15 W +
jetson_clocks). UAV123 clips. Exact pins stamped into `runs/r36/env.json`.

## Reuse map

| Need | Symbol / file:line |
|---|---|
| WSEL/SWAP leg pass predicate | `experiments/2026-07-19-realvid-dd-select/select_p56.py:212` `leg_pass_p56` |
| caption binding | `select_p56.py:87` `bind_by_caption` |
| verdict / classify / required-audit | `experiments/2026-07-20-n25-select/verdict_p518.py:86` `run`, :47 `classify`, :66 `required_audit` |
| scene-set validator + GT loader | `experiments/2026-07-20-n25-select/curate_p518.py:149` `verify`, :49 `load_gt` |
| grace delivery (if late-entry needs it) | `experiments/2026-07-20-late-entry-rescue/rescue_p519.py:170` `run_leg_p519` (GRACE_MAX_S=2.0) |
| stats | `grounding/stats.py` `mcnemar` :114, `deflate_to_effective` :69 |

## Estimates (up front)

- Est WSEL 22-24/30, SWAP 15-18/30 (P5.18 was WSEL 22/26, SWAP 17/26 at n=26 mixed-difficulty; the
  new clips are curated harder for SWAP). Est b~7, c~1 => reachable if the curation holds.
- **Risk (disclosed):** if the new SWAP-hard clips do NOT reproduce a one-directional discordance,
  b stays < 6 and the miss branch fires. Curation quality is the gating variable, not n alone.
- Runtime (est): curation + GT verify ~2-3 h (the real cost); matrix ~1-2 h; verdict ~10 min.

## Decisions / rationale (recorded — supersedes the original single-arm R-36)

- **Design change: paired maintain-vs-select supersedes REMEDIATION's original single-arm SWAP.**
  Why: a lone SWAP pass-rate at n=25 answers "does select fail" but not "does *maintain* beat
  select" — the thesis defends maintain, so the paired contrast is the claim that matters and is
  more powerful (McNemar on discordants vs a one-sample proportion). Given up: a simpler single-arm
  design. Recorded in `docs/decisions/part5-anticipatory.md`.
- One hard SWAP scene per distinct clip (not multiple onsets) — onsets collapse under S1.

## Results (RAN 2026-07-24)

**Headline: scene scarcity, not analysis.** The pre-registered reachability risk fired. Hand-curating
10 fresh UAV123 candidates (5 background agents, 2 clips each) returned **8/10 single-target** — the
drone-follows-one-target framing structurally almost never frames two co-visible same-class
candidates. Only 2 were usable, and both weak (`boat2`: distant ambiguous yacht cluster; `person13`:
distractor legs-only at f0). The bank could not reach n>=25 without contaminating it, so the analysis
lands in the **pre-registered MISS branch**, not a forced pass.

Three readings, all miss or fragile (WSEL=maintain-and-deliver, SWAP=name-distractor select):

| bank | n | WSEL pass | SWAP pass | b (WSEL+/SWAP-) | c | McNemar p (2-sided) | verdict |
|---|---|---|---|---|---|---|---|
| clean P5.18 subset | 13 | 13/13 | 9/13 | 4 | 0 | 0.125 | miss (b+c<6) |
| **audit-clean +boat2 (REGISTERED)** | **14** | **13/14** | **8/14** | **5** | **0** | **0.0625** | **MISS [b+c=5 < floor 6]** |
| mechanical full (incl. defective person13) | 15 | 14/15 | 8/15 | 6 | 0 | 0.03125 | clears gate, **WITHDRAWN** |

**Verdict: NO [underpowered, scene-starved] — select fails but is not separable-from-maintain at
reachable clean n.** Direction is consistent (select never wins a discordant: c=0 in every reading),
which supports maintain-and-deliver, but the clean bank yields only 5 discordants against the frozen
floor of 6. The mechanical n=15 crosses the gate but is withdrawn on the mandatory visual audit:
`person13`'s `distractor_gt_prompt` sits on empty ground (excluded), and `boat2`'s SWAP fail is q8_0
failing to ground a tiny distant yacht (discovery scarcity, not a select-binding error) — remove
either weak clip and it reverts to a miss. Registered in `thesis/claims.json` as
`R-36-maintain-vs-select` (n_rows=14, b=5/c=0, verdict "NO [SIN POTENCIA, escaso en escenas]").

### As-run deviations from the frozen command

- **Bank build:** `build_bank_r36.py` (not the aspirational `curate_r36.py --bank`) — reuses the 26
  P5.18 committed cells cell-for-cell (deterministic; P5.20 replicated P5.19 with 0 flips) + 2 new
  clips. `curate_r36.py` was kept as the proposer only; findings in `runs/r36/bank/curation_r36_findings.json`.
- **Runner:** the 2 new clips ran through the P5.18 GT-free discovery harness `discover_p516.py`
  (`DSC_` prefix), NOT `select_p56.py` — P5.18's actual harness discovers the distractor via VLM
  rather than hand-seeding `distractor_box`, so this keeps the contract identical across the bank.
- **Verdict:** `verdict_r36.py` (paired McNemar + mandatory discordant visual audit via
  `runs/r36/visual_downgrades.json`), NOT `verdict_p518.py` (which is a per-leg n=26 bar counter, not
  a paired test).

**Proof (committed):** (1) `proof/r36_scarcity.png` — the 8/10 single-target curation outcome, the
headline; (2) `proof/r36_person13_swap_delivers_target.png` — the SWAP select failure overlaid on the
delivered frame, and the mis-placed distractor GT the "look at it" audit caught. From `make_proof.py`,
reproducible from `runs/r36/`.
