# Remediation archive — second and third waves, R-22..R-38 (all DONE, 2026-07-23/24)

*Closed history, split out of `thesis/REMEDIATION.md` on 2026-07-26 so the live
ledger only carries open work. Nothing here is actionable; it is the audit trail.
Cite by R-ID, never by line number (HANDOFF invariant I8).*

## Status board — second and third waves

**Second wave, R-22..R-32.** Opened 2026-07-23T11:55Z from the arc audit
(`wf_3976b3e6-a4f`, 9 agents, 28 findings, all surviving an adversarial refutation
pass). The first wave fixed the *claims*; this wave fixes the *apparatus that
reports them*, which the first wave never audited because it was the thing doing
the auditing. Every P0 below was independently reproduced by hand before being
written down — the reproduction command is in the task.

| ID | Task | Pri | Blocks | Status |
|---|---|---|---|---|
| R-22 | Paired deflation uses the wrong denominator; report contradicts itself | **P0** | R-23 | **DONE** 2026-07-23 |
| R-23 | The four claim buckets overlap and are mislabelled | **P0** | — | **DONE** 2026-07-23 |
| R-24 | R-14 proof figure draws contract coords as pixels | **P0** | — | **DONE** 2026-07-23 |
| R-25 | Registry + module hygiene (`gate_p`, selfcheck, hand-counts) | **P0** | — | **DONE** 2026-07-23 |
| R-26 | `README.md` is stale against R-13/R-14/R-16 | **P0** | — | **DONE** 2026-07-23 |
| R-27 | `P3-E1-TRT-fps` never marked superseded by R-16 | **P0** | — | **DONE** 2026-07-23 |
| R-28 | The defended sentence claims *select*; nothing inferential carries it | P1 | — | **DONE** 2026-07-23 (author decided) |
| R-29 | `n_effective` = 13 vs the measured ICC | P1 | — | **DONE** 2026-07-23 (calibrated) |
| R-30 | Holm family boundary + undisclosed dependencies | P1 | — | **DONE** 2026-07-23 (per-Part) |
| R-31 | Retire or re-run P3-T2 / P3-T3; backlog commands are fiction | P1 | — | **DONE** 2026-07-23 (retired) |
| R-32 | Spot-check the assertion-only DONEs (R-19, R-7, R-21) | P1 | — | **DONE** 2026-07-23 |
| R-33 | `claims.json` caveats quote numbers the registry contradicts (P5.15) | P1 | R-22 | **DONE** 2026-07-23 |
| R-34 | Re-run E18 at n>=25 — Chapter 6 has zero surviving claims | P2 | R-30 | **DONE** 2026-07-23 (YES, ORACLE 23/25 vs COLD 3/25, deflated p=4.01e-05) |
| R-35 | Run P6.2 — Chapter 8 has zero surviving claims | P2 | R-16 | **DONE** 2026-07-24 (P6.2-DELIVERY WARM 23/25 vs COLD 2/25, McNemar p=9.5e-07 survives Holm; P6.2-COUPLING bounded null — Chapter 8 now has a surviving claim) |
| R-36 | SWAP arm at n>=25 **distinct clips**, not 26 cells from 13 | P2 | R-29 | **DONE** 2026-07-24 (NO [underpowered, scene-starved]; pre-registered MISS branch, b=5/c=0 p=0.0625 at audit-clean n=14; UAV123 is scene-starved for SWAP-hard pairs, 8/10 curated candidates single-target) |
| R-37 | P5.21 ROI-carry vs plain carry (paired, pilot-gated) | P2 | R-16 | **DONE** 2026-07-24 (TIE [measured negative]; pilot 5/8 headroom PASS; plain 28/34 vs ROI 26/34, b=1/c=3 p=0.625, direction AGAINST ROI; drift-reinforcement fired on car10; closes the last non-capacity carry lever) |
| R-38 | REG grounding isolation (paired, on-device) | P2 | R-16 | **DONE** 2026-07-24 (SYMMETRIC [pre-registered branch]; isolated distractor grounding 12/14=0.857 >> P5.18's 0.65 end-to-end; matrix target 13/14 vs distractor 12/14, b=2/c=1 p=1.0; grounding is NOT the bottleneck — residual select failure redirects downstream to carry/delivery; dependent decomposition of R-36, same Holm family) |

---

# Second wave — the apparatus, R-22..R-32

Opened 2026-07-23T11:55Z. Wave one audited the claims; nobody audited the code that
computes and prints them. These are its defects.

## R-22 — Paired deflation uses the wrong denominator — DONE **P0** (2026-07-23T12:25Z)

`grounding/stats.py:333` deflates `b`/`c` against `claim.n_rows`. The single-arm
branch at `:355` deflates against `counts["n"]`. Seven paired claims record `b`/`c`
**already collapsed to the clip scale** (`counts["n"] = 6`, `n_rows = 12`, and the
`independence_note` says so: *"12 rows, 6 observations"*), so R-3's fix halves them a
second time.

Reproduce:

```
.venv-ft/bin/python -c "
import json,sys; sys.path.insert(0,'thesis')
from grounding.stats import deflate_to_effective, mcnemar
for x in json.load(open('thesis/claims.json'))['claims']:
    co = x.get('counts') or {}
    if x['design']!='paired-binary' or 'b' not in co or co.get('n') in (None, x['n_rows']): continue
    f=lambda d: mcnemar(*[deflate_to_effective(co[k], d, x['n_effective'])[0] for k in 'bc'])
    print(x['id'], 'as-is', f(x['n_rows']), 'correct', f(co['n']))"
```

| claim | report prints | correct |
|---|---|---|
| `E18-cold-acquire-vs-warm-oracle` | 0.5 | **0.0625** |
| `P5.1-warm-vs-cold` | 0.5 | **0.125** |
| `E19-motion-compensated-acquire` | *"0 pares discordantes"* (NaN) | **1.0**, b=1 |
| `E20`, `E21`, `E23` | 1.0 | 0.5 |

`thesis/stats-report.md` therefore **contradicts itself**: `:59` prints E18 at
`p=0.5, b=2, c=0` while `:171` says *"se queda en p = 0,0625 ... solo volcaron
cinco"*. The hand-written caveat is right; the generated table is wrong. Same at
`:74` vs `:201` for P5.1 — and `CLAUDE.md` has said 0.125 all along, so the repo has
been carrying both numbers.

E18 is the pivot claim of Chapter 6. p=0.5 reads *compatible with chance*; p=0.0625
reads *the floor a 6-pair design can reach — five of six flipped, six were needed*.

Blast radius, measured: **all 8 Holm survivors unchanged**; live family 34 -> 35.

`tests/test_stats.py:251` currently pins the bug — it must be corrected, not deleted.

**Done when:** the paired branch deflates against `counts["n"]` where present, the
regenerated `stats-report.md` prints 0.0625 for E18 in BOTH places, a test asserts
the table/prose agreement, and every doc quoting the six p-values is swept.

### Resolution (2026-07-23T12:25Z)

`grounding/stats.py` now reads `den = claim.counts.get("n", claim.n_rows)` in the
paired branch, with the whole diagnosis in the comment above it. Six p-values move,
exactly the six predicted: E18 0.5 -> 0.0625, P5.1 0.5 -> 0.125, E19 NaN -> 1.0, and
E20/E21/E23 1.0 -> 0.5. **All 8 Holm survivors are unchanged**, which is the point
worth stating plainly: this was a reporting defect, not a result that moved.

`DEFLATION_PROBES` was the wrong home for the regression. That list asserts deflation
**must move** the p-value, and R-22's property is the opposite — that it moves
*nothing* when b/c are already at clip scale. `tests/test_stats.py` gets a dedicated
`test_paired_deflation_measures_from_the_scale_bc_were_recorded_at` instead, pinning
both directions: `{"b": 5, "c": 0, "n": 6}` stays at 0.0625, and the same counts with
no `"n"` still deflate to 0.5 off `n_rows`.

**The fix exposed a second defect the bug had been hiding.** E19's caveat read *"UN
solo par discordante: p = 1.0 ... b=0, c=0, McNemar indefinido"* — self-contradictory
in a single sentence, and it had been in the registry for eight days. Rewritten in
both `caveats` and `caveats_en`, with the R-22 history stated rather than quietly
swapped.

**The doc sweep, in full.** Every claim's hand-written caveat was checked against its
recomputed counts, not just the six:

- The five other changed claims (E18, E20, E21, E23, P5.1) needed **no edit** — their
  caveats carried the correct numbers all along. That is the finding, not an aside:
  the prose was right and the code was wrong, for eight days, in a repository whose
  premise is that the generated artefact is the trustworthy one.
- `00-esquema.md` P5.1 row: `b = 2, c = 0, p = 0,5` -> `b = 4, c = 0, p = 0,125`, with
  a paragraph naming R-22 as the cause so the changed number is not silent.
- `00-esquema.md` Ch. 6 caveat list said the arc had *"sin prueba estadística
  posible"*. Overstated: the tests do run, they just cannot get far. Replaced with the
  actual four p-values and the reason (n = 6 needs all six pairs).
- `00-esquema.md` sim-tie prose said one discordant cell gives *"p = 0,5"*. That is
  the one-sided value in a document that reports two-sided everywhere; it is 1,0
  undeflated and undefined after deflation. Both spots rewritten.
- `00-esquema.md` bucket table 33 -> 32, with a note that the table still does not sum
  to 70 and that R-23 owns the partition.
- The R-19 resolution block above carries a `Superseded in part` note: its
  *"P5.1 is b=2 (not 4)"* edit was propagating this bug, not correcting anything.

**A test the Done-when asked for and did not get, deliberately.** A general
"caveat p-value must equal computed p-value" check flags **thirteen** claims and all
thirteen are legitimate — counterfactuals (*"even a perfect 5/5 would give p = 0.33"*),
sibling arms (P3-R13's D-full at 2.2e-24), undeflated values the same sentence goes on
to deflate, and numbers explicitly marked retired. That test would be noise with a
maintenance bill. What went into `tests/test_thesis_integrity.py` instead is the
unambiguous half:
`test_paired_caveats_do_not_contradict_their_own_discordant_counts` fails if a caveat
asserts zero discordance while the counts record some. It is exactly the shape of the
E19 defect and has no judgement call in it.

`make test`: 162 passed, 1 skipped.

## R-23 — The four claim buckets overlap and are mislabelled — DONE **P0** (2026-07-23T12:35Z)

`thesis/00-esquema.md` reports 8 + 33 + 38 + 3 over 70 claims. That sums to 82, and
recomputing from the registry gives 8 + 36 + 41 + 3 = **88** — because **29 claims
sit in two buckets at once**. A partition that double-counts 29 of 70 is not a
partition.

The labels are also wrong:

- *"33 tuvieron 0 pares discordantes"* — only **4** paired claims genuinely observed
  b=c=0 (`P1-S1.4`, `P5.10`, `P5.19-wsel-no-regression`, `P5.20-replication`). Of the
  36 with no defined p, **26 are not paired designs at all**. Four more had exactly
  one discordant pair that deflation rounded to zero, and print *"0 pares
  discordantes"* immediately followed by *"[deflactado desde b=1, c=0]"*.
- *"38 diseños no podían alcanzar alfa"* — of the 41 flagged, only **4** are gated
  paired designs no outcome could have cleared. 23 are `single-arm-binary` with no
  pre-registered gate (hardcoded `could_ever_reach_alpha=False` at `stats.py:358`,
  no power calculation), 12 are `descriptive` (`:411`, never a hypothesis by intent),
  2 are aggregate-only.

"Twelve gated designs could never have cleared" is damning and true. "38" is
refutable in a minute and takes the framework's credibility with it.

**Done when:** the buckets are disjoint and sum to exactly 70, each label says what
its bucket actually contains, `run_stats.py` computes them (no hand-counts), and a
test asserts the partition sums to `len(claims)`.

### Resolution (2026-07-23T12:35Z)

`run_stats.py` grows a `BUCKETS` list and a `bucket_of()` that returns **one** key
per claim, assigned by the first rule that fires. The order is the semantics:
specific beats generic, so *"the pre-registered gate was unreachable"* outranks
*"the test did not reject"* — the first says something about the design, the second
only about the result.

| bucket | n | what it actually contains |
|---|---|---|
| Significativas tras Holm | 8 | defensible as effects |
| Probadas, no significativas | 15 | a real contrast that did not reject |
| **Puerta pre-registrada inalcanzable por diseño** | **12** | a gate no possible outcome could clear at that n |
| Descriptivas, sin hipótesis | 12 | nothing to contrast, by design |
| Sin puerta pre-registrada, sólo intervalo | 12 | Wilson interval and nothing more |
| Pareadas sin un solo par discordante | 6 | the arms never separated in any cell |
| Sin datos crudos | 3 | in the re-run queue |
| Sólo sobreviven agregados | 2 | per-item values lost |

Sums to 70 exactly. `tests/test_thesis_integrity.py::test_the_claim_buckets_are_a_partition`
asserts the total and that the report prints each count, so the table cannot drift
from the registry again.

**One number in the task description above was itself wrong.** It said 23 claims
are `single-arm-binary` with no pre-registered gate. There are 30 single-arm claims
and **12** of them have `gate_p is None`. The 50-claim figure you get from counting
`gate_p is None` across all designs is meaningless, because paired designs never use
that field. Fixed here and in `00-esquema.md`, which had been about to inherit it.

`00-esquema.md` now carries the eight-row table, a note that the eight are disjoint
and why, and a boxed record of what the four-row version claimed. The framing that
matters is preserved rather than softened: **twelve gated designs that no outcome
could have cleared** is the sentence the chapter should carry. It is damning and
true, where "38" is refutable in a minute — and a reader who refutes it stops
believing the rest of the chapter.

The intro line *"Sobre 70 afirmaciones con puerta"* was also wrong on its face:
24 of the 70 never had anything to contrast. Corrected.

## R-24 — R-14 proof figure draws contract coords as pixels — DONE **P0** (2026-07-23T12:32Z)

`experiments/2026-07-21-roi-ondevice/make_proof.py:75-92` passes `gt` and `pred`
straight to `cv2.rectangle`. Those are contract-space [0, `COORD_SCALE`] values
(`grounding/contract.py:30`, `COORD_SCALE = 100`); the sibling `win` field is in
pixels, which is what makes the mistake invisible in the data. On a 1360x765
VisDrone frame a box at `[27, 48, 34, 65]` is a sliver in the top-left corner, and
the panel then *zooms to that sliver*.

Opened with the Read tool 2026-07-23T11:40Z. The committed
`proof/discordant-examples.png` shows: both boxes on a **tennis court** for *"The
yellow pedestrian is near the center of"*; a **grey blur** for *"The cars on the
road"*; a **blank building facade** for *"The pedestrians in red walk near the
center"*; a **flat cream gradient** for *"The yellow bus in left side"*. No green GT
box renders anywhere, though the title promises `green=GT`.

This is a live I5 violation inside the campaign that cites I5 by name, backing one
of the 8 Holm survivors. **The statistic is unaffected** — 85.19 % vs 63.10 %
re-derives from `raw/items-{full,roi}.jsonl`, 439 rows each. Only the deliverable is
dead.

Second, smaller defect: the six panels are `sort(key=roi_iou - full_iou)[:6]`, all
at delta exactly 1.0 — the best ~5 % of 112 discordant cells, captioned as a sample.

Inputs are all local: 548 frames under `data/VisDrone2019-DET/images/val/`. No GPU.

**Done when:** boxes are scaled to pixels, the regenerated figure is **opened with
the Read tool** and described in the README by what it actually shows, the panel
selection is either stated as best-case or made a stratified sample, and a mechanical
assert rejects a box whose coords are all <= COORD_SCALE on an image larger than that.

### Resolution (2026-07-23T12:32Z)

`make_proof.py` gains `to_pixels()` (contract -> pixels, `round(x * W / COORD_SCALE)`)
and two mechanical checks that run on every regeneration:

- `_assert_looks_like_pixels()` per box: fails if all four coordinates fit inside
  [0, COORD_SCALE] on a frame more than twice that size. Verified to fire on the
  exact box the old code drew — `[27, 48, 34, 65]` on 1360x765 — and to pass on its
  converted form `[367, 367, 462, 497]`.
- a flat-crop check per panel: `crop.std() > 1.0`. The old figure's cream-gradient
  panel would not have survived it.

Panel selection is now stratified: ranks 1, 23, 45, 68, 90 and 112 of the 112
discordant cells by ROI−full delta, each title carrying its rank and the suptitle
saying "stratified over all 112". The old `sort(delta)[:6]` was the top ~5 %, every
panel at delta exactly 1.0, captioned as a sample.

**Regenerated and opened with the Read tool at 2026-07-23T12:32Z.** It shows six real
aerial scenes: a crowded basketball court, two multi-lane roads, a parking row, a
crossroads, and a motion-blurred street. In four of the six the blue ROI box is on a
plausible target while the red full-frame box is on a *different object elsewhere in
the scene* — which is the b-cell mechanism made visible: the full-frame arm does not
miss by pixels, it grounds the wrong instance. Green GT appears as its own box only
where ROI IoU < 1.0; at 1.00 it is exactly under the blue box, which is the correct
appearance rather than the old failure to render. The README caption is rewritten to
this, with the retraction stated rather than the old text quietly swapped.

**The statistic never moved.** 85.19 % vs 63.10 % re-derives from
`raw/items-{full,roi}.jsonl`, 439 rows each; the drawing path was never in it. What
was dead was the deliverable, in the campaign that cites the "look at it" rule by
name, backing one of the eight Holm survivors — and its caption said "Verified by
opening the image".

## R-25 — Registry and module hygiene — DONE **P0** (2026-07-23T12:34Z)

Three small things, each of which makes a future session distrust the core:

- **`python -m grounding.stats` exits 1.** `stats.py:456` still asserts the English
  `"absence of a test"` after `eacf746` translated the reading to *"ausencia de
  prueba"*. `make test` stays green because `tests/test_stats.py` never enters that
  branch, so the module's own advertised self-check is the only thing that catches
  it, and it is broken.
- **Two Holm survivors store their achieved p-value in `gate_p`.**
  `P3-ROI-M2.0-512-ondevice` holds `2.501505063220086e-14` and `P3-R13-owlv2-vs-vlm`
  holds `2.2605981543610277e-07`, bit-identical to what `evaluate()` recomputes: the
  pre-registration was prose, so the result got written into the pre-registration
  field. Inert only because the paired branch never reads `gate_p`. Set both to null
  and add a test that no `paired-binary` claim carries one.
- **`thesis/run_stats.py:185` still hand-counts.** `71b0128` replaced *"Solo tres
  afirmaciones"* with *"Seis afirmaciones"* under a commit message saying a generated
  document should not carry a hand-counted constant. It still does; it just counts
  higher. Derive it.

**Done when:** the self-check exits 0, both `gate_p` are null with a test, and no
generated line contains a literal count.

### Resolution (2026-07-23T12:34Z)

All three, each with a test so it cannot rot back:

- **`python -m grounding.stats` exits 0.** The assertion now checks the Spanish
  *"ausencia de prueba"* and prints `o.reading` on failure.
  `test_the_stats_module_selfcheck_passes` runs it as a subprocess from the suite,
  which is the actual repair: the self-check was the only thing positioned to catch
  that drift, and nothing was positioned to catch the self-check.
- **Both `gate_p` are null.** `test_paired_claims_carry_no_gate_p` fails on any
  `paired-binary` claim that carries one. The field is inert for paired designs, so
  nothing in the numbers moves — the point is that a field meaning *"the bar we set
  in advance"* was holding *the number we got*, on two of the eight survivors.
- **The machine sentence is derived.** `on_device` and `on_device_sig` are computed
  from `claim.machine` and the Holm result, spelled through `_spell()`, and the two
  inferential ones are named by claim id instead of by a hand-typed *"(R-14) y
  (R-13)"*. `test_no_generated_report_line_hand_counts_the_registry` asserts the
  rendered sentence agrees with the registry.

## R-26 — `README.md` is stale against R-13/R-14/R-16 — DONE **P0** (2026-07-23T12:42Z)

The repo's front door. Last touched `95228e2` (2026-07-21); R-13, R-14 and R-16
landed 22-23 July and appear nowhere (`grep -c 'R-13\|R-14\|R-16\|OWLv2'` = 0).

- `:19` still says the 1024 carry rate *"no está medida ... plausiblemente por ~2x"*.
  R-16 measured it: 2.688 Hz, a 2.30x correction. The line also still leads with
  6.15 FPS, which R-16 retired.
- `:59` and `:91` say *"las 65 afirmaciones"*. The registry holds 70.
- The machine table at `:62-67` reads 47/13/**3**/2. The registry says 47/15/**6**/2
  — it under-reports the on-device claims by half, which is the exact axis the whole
  first wave was about.
- `:51` still leads with the superseded `P3-ROI-M2.0-512` and +21.2 pp, while
  `00-esquema.md:415` says the headline is now the on-device +22.1 pp.

R-6's done-criterion was *"every number in the front matter resolves to a registry
claim"*. It did, on 2026-07-21. No task owned the re-sweep after new claims landed.

**Done when:** every number in `README.md` resolves to a current registry claim, and
a test asserts the claim count and machine table are generated, not typed.

### Resolution (2026-07-23T12:42Z)

Four stale things, one of them load-bearing:

- **`:19`, the carry rate.** Rewritten to lead with R-16's measurement — 2.69 Hz solo
  at the deployed `image_size` 1024, a **2.30x** correction on the 6.15 FPS the line
  used to headline (`P4-R16-carry-rate-1024`, measured wholly on the board). The same
  paragraph now records that E1's most-quoted corollary — *"co-residency costs 0 FPS"* —
  was timed against an **idle** `llama-server`, and that the previous "~2x optimistic"
  hedge pointed the right way but fell short.
- **The machine table at `:62-67`** read 47/13/**3**/2 against a registry that says
  47/15/**6**/2. It under-reported the wholly-on-device claims by half — the exact
  axis the entire first remediation wave was about. It is no longer typed: the block
  between `<!-- BEGIN generated: machine-table -->` and `<!-- END ... -->` is written
  by `sync_readme()` in `thesis/run_stats.py`, from the same `load_claims()` the
  report uses.
- **`:51`, the ROI headline.** Now leads with `P3-ROI-M2.0-512-ondevice` (+22.1 pp,
  n=439 paired, p = 2.5e-14, survives Holm) and names the superseded 3090-control
  version (`P3-ROI-M2.0-512`, +21.2 pp) as superseded. A new bullet carries
  `P3-R13-owlv2-vs-vlm` (277 vs 208, p = 2.26e-07, survives Holm) with both of its
  caveats: the 16.0x latency comparison **excludes the selection stage** a decomposed
  route would still need, and the 90.4% `D-oracle` arm picks with ground truth, so it
  is a ceiling on any re-ranker and **not** an OWLv2 result. The tracker bullet now
  says 372 ms at the deployed 1024, not ~162 ms at 768.
- **"las 65 afirmaciones"**, twice, against a registry of 70 — now 70, with the
  Holm/24/12 bucket detail.

Two tests replace the sweep: `test_readme_machine_table_is_generated_and_current`
regenerates the block and asserts the file already matches it, and
`test_readme_quotes_no_stale_claim_count` fails on any "N afirmaciones" whose N is
not the live registry size.

R-6's done-criterion — *"every number in the front matter resolves to a registry
claim"* — was true when it was written on 2026-07-21. Nothing owned the re-sweep
after R-13, R-14 and R-16 landed new claims two days later. Generation plus the two
tests is the part that survives the next claim landing; another manual sweep would
not have.

`make test`: 169 passed, 1 skipped.

## R-27 — `P3-E1-TRT-fps` never marked superseded — DONE **P0** (2026-07-23T12:36Z)

R-14 wrote a supersede marker into the verdict of the claim it replaced. R-16 wrote
none. `P3-E1-TRT-fps` still reads headline *"TensorRT fp16 lifts the co-resident
carry rate 4.89 -> 6.15 FPS"*, verdict `PASS`, `machine: jetson-orin-nano-8gb`, and
is pinned by name in `tests/test_thesis_integrity.py:163` — for a configuration
(`image_size` 768, **idle** server) that R-16 proved was never deployed.
`experiments/2026-07-22-sam2-coresidency/README.md:278` states flatly: *"E1's
'co-residency costs 0 FPS' is falsified."*

The supersede marker went on the number that got better and not on the one that got
worse. That asymmetry is the part worth noticing.

**Done when:** the claim carries a supersede marker naming `P4-R16-carry-rate-1024`,
and a test asserts that a claim whose successor exists cannot read `PASS` unqualified.

### Resolution (2026-07-23T12:36Z)

`P3-E1-TRT-fps` verdict `PASS` becomes:

> PASS at image_size=768 against an IDLE server [SUPERSEDED by P4-R16-carry-rate-1024,
> R-16: the deployed carry runs at 1024 and delivers 2.69 Hz solo, a 2.30x correction;
> "co-residency costs 0 FPS" was measured against an idle llama-server and is falsified]

The test enforces **two** rules, because the obvious one alone would not have caught
this. `test_supersede_markers_are_bidirectional_and_qualify_the_verdict` requires that
a `SUPERSEDED by X` marker names a real claim **and that X names it back**, plus that a
superseded verdict is not a bare `PASS`. R-16's omission was precisely a missing link,
so a rule that only checks the marker end would have been satisfied by writing the
marker and nothing else. `P4-R16-carry-rate-1024` now carries `; supersedes
P3-E1-TRT-fps`, which is the half that was missing.

Verified the test fails on the pre-fix state: removing that clause and re-running gives
*"P3-E1-TRT-fps points at P4-R16-carry-rate-1024, but P4-R16-carry-rate-1024's verdict
never names it back."*

`P3-E1-TRT-fps` stays pinned in `test_on_device_claims_really_are_on_device` and stays
`machine: jetson-orin-nano-8gb` — the measurement did happen on the Orin. What was
wrong was the configuration it stood for, and that is now in the verdict where a reader
meets it.

## R-28 — The defended sentence claims *select* — **AUTHOR**

`thesis/00-esquema.md:53-57` defends spending the idle window to keep candidates
alive and *"limitarse a **seleccionar**"*. The maintain-and-deliver half is carried
by P5.2a (p=6.10e-05, survives Holm). The **select** half has produced no inferential
result in eight campaigns — and from P5.13 onward the DD arm *cannot mis-select by
construction*: `experiments/2026-07-19-realvid-dd-select/select_p56.py:87`
`bind_by_caption` is string equality plus `assert len(matches) == 1`.

That is a **disclosed** scope cut — the docstring says so, and
`thesis/analyse_shadow_rg.py:11` says *"DD cannot lose on selection"*. What never
happened is propagating it to the sentence the thesis defends.

Prepared recommendation, for the author to accept or reject: re-scope to *mantener y
entregar sin latencia de adquisición*. Everything surviving supports that; Chapter 7
becomes a well-measured negative about selection instead of a weak positive.

**Done when:** the author has decided, and the sentence and Chapter 7 framing match
the decision.

### Resolution — AUTHOR DECIDED, landed 2026-07-23T14:05Z

The author's own words: *"intenté montar un selector y tracker, pero con el hardware
constraint no conseguí que funcionase, me quedé en un (proposed)"* — accept the
re-scope, and name the hardware as the reason the selector stayed proposed.

Landed in `thesis/00-esquema.md`: the defended sentence (`:53-60`), a
`Decisión de autor` block under it, subordinate-claim row 3, and two Chapter-7
thread bullets. Two corrections were folded in, because the author's framing taken
literally is falsifiable against this repo's own record:

1. **"ni el tracker funcionó" is false.** P5.2a's WARM arm *is* maintain-and-deliver
   end to end (idle-window VLM seed, SAM2 carry, no re-ground at delivery): 21/25 vs
   5/25, p=6.10e-05 deflated, Holm 0.001831. It is the only Part V claim that survives
   Holm. The thesis defends it; it does not concede it.
2. **Hardware forecloses the selector but does not explain the measured failures.**
   R-16 is the real wall and it is specific: at N=2 with the deployed ring
   (`PRUNE_AFTER=100`) the process is OOM-killed on the Orin, surviving only at ring
   32 and 0.540 Hz/candidate — the binding constraint is MEMORY and it appears at
   exactly the second candidate. But every select cell that was actually measured ran
   in replay on the 3090, where memory never bound. P5.20 handed the arm a larger SAM2
   for free (26.3 vs 26.4 min wall) and recovered **0** cells; P5.4 cut acquire
   4.9 s to 2.08 s and moved the verdict by **0** cells. The measured causes are carry
   drift and referring-expression ambiguity. Both reasons are stated; attributing the
   whole thing to hardware would be the comfortable version.

What is given up: Chapter 7 no longer claims a positive select result. It becomes a
well-measured negative plus a deployability veto, which matches the project's own
stated preference (`00-esquema.md:40`) for a well-measured negative over a badly
delimited positive.

## R-33 — `claims.json` caveats quote numbers the registry itself contradicts — DONE P1 (2026-07-23T14:05Z)

Opened and closed the same day. R-22 ran a caveat-p vs computed-p sweep, got 13 flags,
judged **all thirteen legitimate** and scoped its shipped test down to the deflation
case only. That judgement was wrong for one of the 13, and the reason it was invisible
is a bug in the scanner R-22 itself used: the regex `([0-9][0-9.,]*...)` captures the
trailing comma in `p = 0.0016,`, `float()` raises `ValueError`, and the `except:
continue` swallows the row without a word. The same hole shipped in
`tests/test_thesis_integrity.py::test_first_read_surfaces_cite_the_deflated_p`
(commit `5e38265`). Fixed: greedy capture plus `.rstrip(".,")` before `float()`.

**The real defect — P5.15.** The caveat said *"an exact one-sided p of 0.0016"* and
*"THIS IS A PROPERLY CERTIFIED RESULT"*. Against the pre-registered floor the claim
actually declares (`gate_p: 0.72`, and `experiments/2026-07-19-carry-horizon/README.md:87`
*"RQ-a floor 18/25 (72%)"*), `binomial_gate_test(24, 25, 0.72)` = **0.002908**, Holm
**0.07852** — it does **not** survive the correction, and `stats-report.md:113` files it
under *"Probadas, no significativas"*, contradicting its own caveat prose eleven pages
later. The 0.0016 is `P(X>=24 | n=25, p=0.70)`: computed against a 0.70 gate nobody
pre-registered. Corrected in `claims.json` (both language fields),
`thesis/provenance-sweep.md:361`, and the regenerated `stats-report.md`. The Wilson
interval [0.80, 0.99] and the load-bearing reading (*the carry is not the fragile
part*) stand — as description, not as certification.

**Re-triage of the other 12 flags** (done, not deferred): 2 are the undeflated value
disclosed in the same sentence as the deflated one (`P5.2a` 3.05e-05,
`P3-carry-OP768` 0.013); 4 are explicit counterfactuals — *"even a perfect 5/5 would
give p = X"* (`P5.3`, `P5.14-wsel`, `E16`, `E18-A-vs-gate`); 3 are the claim's own
undeflated p quoted with the deflation named in the next clause (`P5.14-swap`,
`P5.18-n25-wsel`, `P5.19`); 2 are sibling-arm p values (`P3-R13` 2.2e-24 for the
D-full arm, `P3-SR` for the three bicubic/lanczos comparisons); 1 is
`P5.14-shadow-rg` quoting its own p where the deflated and undeflated agree. Twelve
legitimate, one defect. R-22's verdict was 13/13 legitimate; the corrected count is
12/13.

**Standing lesson, worth more than the fix:** a sweep that silently `continue`s on a
parse failure reports "no defects" and "the parser never matched" as the same output.
Every scanner in `thesis/` and `tests/` that catches an exception in a match loop
should count what it skipped and assert the count is 0.

## R-29 — `n_effective` = 13 vs the measured ICC — DONE P1 (2026-07-23T16:40Z)

Collapsing P5.19's 26 cells to 13 clips assumes cells within a clip are perfectly
correlated. Measured, they are not: `bike1`'s six SWAP cells are `[1,1,0,1,0,1]`,
`car9`'s four are `[0,1,1,0]`. A one-way ANOVA ICC over the committed `results.json`
gives roughly 0.13-0.25, so deff ~ 1.1-1.5 and n_eff ~ 18-24, not 13. Only 5 clusters
are non-singleton, so the estimate is noisy — that caveat is part of the finding.

It has a consequence: `min_successes_for_gate(26, 0.8) = 25` is reachable while
`0.8^13` is not, so the deflation *created* the unreachability that `R-4` describes
as having been hidden by it.

Invariant I2 forbids moving to the less conservative number. The prepared
recommendation is therefore: **keep 13 as citable**, put the measured ICC in the
`independence_note`, and give the method chapter a paragraph. That turns the most
aggressive and most probe-able judgement in the framework from unexamined into
calibrated.

**Done when:** the author has decided whether to keep, calibrate or revise.

### Resolution — AUTHOR DECIDED: revise, landed 2026-07-23T16:40Z

**Decision: calibrate, not keep.** The collapse-to-clusters rule is the design-effect
formula `deff = 1 + (n0 - 1) * ICC` evaluated at ICC = 1 — an assumption nobody
measured. R-29 measures it instead, by one-way random-effects ANOVA on the per-cell
outcome grouped by source clip, on the **14 claims deflated for clustering**. Claims
deflated for *determinism* (E18's two identical repetitions, `P4-R16`'s single
benchmark, E13's 4.16/4.16/4.17) are untouched: there ICC really is 1.

**The guard is the whole design, and it is load-bearing.** Deflation uses the **upper
95 % confidence bound** on the ICC (Searle), never the point estimate. Naive point
estimates undo R-4 wholesale — P3-R13 goes 316 -> 439, the P5.18 shadow ceiling
13 -> 48 — because an ICC of 0.000 measured over 13 clusters is noise, not evidence of
independence. With the upper bound, few clusters give a wide interval, the bound sits
near 1, and `n_effective` stays near the conservative collapse. The calibration only
moves away from the collapse when the data actually *rule out* high correlation.

| claim | N | clusters | ICC | ICC hi95 | deff | old n_eff | new |
|---|---:|---:|---:|---:|---:|---:|---:|
| P3-ROI-M2.0-512-ondevice | 439 | 316 | 0.039 | 0.226 | 1.09 | 316 | 404 |
| P3-R13-owlv2-vs-vlm | 439 | 316 | 0.000 | 0.138 | 1.05 | 316 | 417 |
| P3-SR-swin2sr-accuracy | 429 | 312 | 0.000 | 0.110 | 1.04 | 312 | 412 |
| P3-carry-OP768-accuracy | 186 | 93 | 0.185 | 0.373 | 1.37 | 93 | 135 |
| P5.2a-warm-generalization | 25 | 23 | 0.000 | 0.747 | 1.06 | 23 | 24 |
| P5.5-select-generalization | 5 | 3 | 0.000 | 0.901 | 1.54 | 4 | **3** |
| P5.13-dd-vs-rg-tie | 24 | 12 | 0.000 | 0.548 | 1.55 | 12 | 15 |
| P5.17-dd-vs-rg-tie-n56 | 56 | 28 | 0.000 | 0.365 | 1.37 | 28 | 41 |
| P5.18-n25-wsel | 26 | 13 | 0.454 | 0.795 | 1.72 | 13 | 15 |
| P5.18-n25-swap | 26 | 13 | 0.254 | 0.695 | 1.63 | 13 | 16 |
| P5.18-shadow-rg-ceiling | 48 | 13 | 0.000 | 0.354 | 1.89 | 13 | 25 |
| P5.19-swap-late-entry-rescue | 26 | 13 | 0.418 | 0.778 | 1.70 | 13 | 15 |
| P5.19-shadow-rg-ceiling | 50 | 13 | 0.086 | 0.445 | 2.18 | 13 | 23 |
| P5.20-carry-capacity | 52 | 13 | 0.000 | 0.150 | 1.42 | 13 | 37 |

**The result that makes it defensible: it recovers zero survivors.** Ten before, ten
after; none gained, none lost. What it does change:

- **Two gates stop being unreachable-by-design.** `P5.18-n25-wsel` and `-swap` flip
  `reachable` False -> True (15/15 and 16/16 now clear alpha). This is exactly what
  R-29 argued: the deflation had *manufactured* part of the unreachability.
- **Three "no test" readings become tests again.** P5.13, P5.17 and P5.20 had their
  single discordant pair rounded to zero by the rescale, producing `p = nan` and the
  self-contradictory "0 discordant pairs [deflated from b=1, c=0]" line R-23 flagged.
  They now read `p = 1`. Still not significant — but said by a test, not a division.
- **Two Part III survivors strengthen without changing side.** P3-ROI on-device
  2.50e-14 -> 6.38e-18; P3-R13 2.26e-07 -> 2.21e-09.
- **One claim tightens.** P5.5 goes 4 -> 3, because the registry had assigned
  `n_effective = 4` over 3 real clusters — an R-4 defect the calibration exposed by
  requiring `collapsed_floor <= n_effective`.
- **One borderline to state before a reader finds it.** P3-carry-OP768 moves
  p = 0.096 -> 0.030, uncorrected-significant; per-Part Holm leaves it at 0.060, so it
  is still cited as not significant.

Landed in: `thesis/claims.json` (14 `icc` blocks + rewritten `independence_note`s, each
ending `**Suelo publicado: {old}**`), `grounding/stats.py` (the `icc` dataclass field),
`thesis/01-metodo-estadistico.md` (new subsection *Calibrar el agrupamiento en lugar de
colapsarlo*), `HANDOFF.md` (new invariant **I2b**, since this is the one operation that
may raise `n_effective`), and `tests/test_thesis_integrity.py`
(`test_icc_calibrated_n_effective_is_derived_not_chosen` recomputes `n_effective` from
the stored ICC, so it cannot be hand-tuned; `test_n_effective_respects_the_distinct_clip_count`
now skips `icc`-bearing claims, since it encodes R-4's superseded rule).

**What this does not buy.** Calibrating recovers some of the power the collapse threw
away; it recovers none of the power that was never recorded. The design rule stands
unchanged: **n counts clusters, not cells** — see R-36.

## R-30 — Holm family boundary + undisclosed dependencies — DONE P1 (2026-07-23T15:20Z)

Global family of 34 live p-values gives 8 survivors; per-Part families give 10. The
two extras are `P5.15-plain-carry-survival` (p=0.0029) and `P2-RQ4.1-deploy-fidelity`
(p=0.0355) — the latter being the claim that the Part I fidelity catastrophe is
eliminated. Counter-argument to record: at m=3..7 per part, per-Part Holm keeps every
uncorrected-significant claim, i.e. it barely corrects at all. Part V (m=15) is the
only family where it still bites.

Two dependencies inflate the family either way:

- `P3-ROI-M2.0-512` and its own declared on-device replacement are both counted.
- `P3-R13-owlv2-vs-vlm`'s VLM arm **is** R-14's arm A — the same `items-full.jsonl`,
  same k. Two of the 8 survivors share a measurement.

`00-esquema.md:794-804` discloses the R-13/R-14 shared arm. It does not disclose the
ROI double-count, and `stats-report.md` — the file the project's own rules point
readers at — discloses neither.

Prepared recommendation: keep the global family, state the choice in two sentences in
`01-metodo-estadistico.md`, report per-Part as a declared sensitivity analysis, and
render both dependency notes into `stats-report.md`.

**Done when:** the author has picked the family, and both dependencies appear in the
generated report.

### Resolution — AUTHOR DECIDED: per-Part, landed 2026-07-23T15:20Z

**Decision: the family is the Part.** Holm now runs inside each empirical chapter,
not over the whole registry. Survivors go from **8 to 10**; the two that only clear
per-Part are `P2-RQ4.1-deploy-fidelity` (p=0.0355 — the claim that the Part I
fidelity catastrophe was eliminated) and `P5.15-plain-carry-survival` (p=0.002908).

Implemented in `thesis/run_stats.py:263-273`. The global family is **not deleted** —
it is rendered in a neighbouring `p (Holm, global)` column of the main table, so
every reader sees both numbers on the same row. A new section, *La familia de
corrección, y por qué ésta y no la otra*, carries the justification, the family
sizes, the two claims that change hands, and the counter-argument in full: at
m = 2..15 per Part, Holm barely corrects, so per-Part buys credibility it has not
earned everywhere except Part V (m = 18 after R-29), which is the only family where it still
bites. It also records that the author saw both numbers before choosing — that
belongs on the page, not in a commit message.

Both dependencies are now disclosed in the generated report rather than only in
`00-esquema.md`: the `P3-ROI-M2.0-512` / `-ondevice` double count, and
`P3-R13-owlv2-vs-vlm`'s VLM arm being R-14's arm A on the same `items-full.jsonl`.
Direction is noted too — double-counting enlarges m and *hardens* the correction, so
it works against the thesis, which is why it can be disclosed rather than fixed.

## R-31 — Retire or re-run P3-T2 / P3-T3 — DONE P1 (2026-07-23T15:30Z)

Both are `GATE PASS` on prose alone, no raw data, and both are Chapter 5 spine.
`thesis/rerun-backlog.md` already argues against re-running: T2 is one scripted clip
= one Bernoulli draw, and *"regenerar el vuelo único no hace la afirmación
defendible; solo la haría citable, que es distinto y peor"*.

Separately, and this is a plain defect rather than a judgement: **all three backlog
commands are fiction.** `grounding.eval.score_clips` does not exist (`grounding/eval/`
holds `backends`, `harness`, `parity`, `run`); `runners/run_phase_c.py` has no
`--arms` and no `--reps` (its flag is `--runs`) and contains zero references to CARLA.
`rerun-backlog.md:16` also still says *"Son tres sobre 65"*.
`test_missing_claims_declare_a_rerun` asserts only that a `rerun` key is present —
never that it resolves.

**Done when:** the author has said retire-or-run; the commands either work or are
replaced by an honest "no runnable command exists, here is what would have to be
built"; and the test checks resolvability.

### Resolution — AUTHOR DECIDED: retire, landed 2026-07-23T15:20Z

**Decision: retire both.** `P3-T2-permanence-reid` and `P3-T3-closedloop-coverage`
are no longer defended and will not be re-run. Their `verdict` in `claims.json` is now
`RETIRED (R-31, author decision) - was GATE PASS on README prose alone`, and both
caveats lead with the reasoning: recovering the lost file would make each number
*citable*, not *defensible*, and a citable number that cannot be defended is worse
than none — it invites a tribunal question with no answer. Doing either properly is
not "an hour", it is a fresh n>=25 campaign on ground the registry already calls thin.

**The fiction is gone.** All three backlog commands claimed a runnable path and had
none. Each `rerun.command` now begins `NO RUNNABLE COMMAND EXISTS` and states what
would actually have to be built:

- T2: `grounding.eval.score_clips` does not exist (`grounding/eval/` holds `backends`,
  `harness`, `parity`, `run`). Building it = a per-clip scorer plus a crossing-clip
  bank at n>=25.
- T3: `runners/run_phase_c.py` has no `--arms`, no `--reps` (its flag is `--runs`) and
  zero references to CARLA. Building it = memoryless/reid arms on the P6.1 rig with
  n>=10 flights per arm, which is effectively P6.2.
- `P1-S1.4-phaseC-vlm-closed-loop` carried the same fiction and got the same treatment.

**The test now checks resolvability, not presence.** `test_missing_claims_declare_a_rerun`
asserted only that a `rerun` key existed, which is how a backlog of unrunnable commands
read as a costed, actionable plan for two days. New
`test_rerun_commands_resolve` resolves every `-m module` through `importlib.util.find_spec`,
checks every `*.py` path exists, and greps every `--flag` against the script it is passed
to. An honest `NO RUNNABLE COMMAND EXISTS` passes; a command naming a module or flag that
does not exist fails.

## R-32 — Spot-check the assertion-only DONEs — DONE P1 (2026-07-23T13:05Z)

Eight of the 21 first-wave tasks are artifact-backed (R-1, R-2, R-3, R-5, R-8, R-9,
R-12, R-15) — the statistics and the survivor set reproduce. The rest are the agents'
word about their own work. Ranked by what breaks if the word was wrong:

1. **R-19** (`:987`). Its done-criterion is literally *"a spot-check of 10 verdicts
   drawn at random"*. No record of that spot-check exists. Run it and write the
   result into the row — it is the criterion the task chose for itself.
2. **R-7** (`:362`). *"Done when: every number in the ledgers appears in that table
   with a tag."* 279 rows delivered of 2320 numbers examined. 88 % were dropped as
   clean without being recorded as such.
3. **R-21** (`:420`, `:1080`). 74 rows closed: 62 recovered from a workflow journal,
   12 reconstructed from the diff, exactly 2 independently re-derived. The file itself
   says *"that is their own account of their work, not an audit of it"* three lines
   before declaring CLOSED. Re-derive 5 from the cited `results.json`.
4. **R-16 raw edited after DONE** (`81df727`). 30 rows across two committed
   `raw/*.jsonl` had their `carry` label rewritten *after* `6073cf5` recorded R-16
   DONE. Labels only, timings untouched — but raw files are supposed to be immutable
   evidence, and this is the second wave's own campaign.

**Done when:** each of the four has a recorded spot-check result, pass or fail.

### Resolution (2026-07-23T13:05Z)

All four run. Three pass outright; the fourth passes on its own criterion and
turned up one defect of a different kind, now fixed and tested. Every draw uses
`random.Random(1926)` over a sorted key list, so any of them re-runs identically.

**1. R-19 — the 10-verdict spot-check its own done-criterion named. PASS 10/10.**
Drawn from the 28 Part V/VI registry ids:
`P5.5-select-generalization`, `P6.0-flight-rig-gate`, `P5.2b-speed-sweep`,
`P5.9-kerbsafe-scenebank`, `P5.16-autodisc-wsel`, `P5.18-n25-wsel`,
`P5.15-plain-carry-survival`, `P5.3-multi-candidate-select`, `P5.14-swap`,
`P5.1-warm-vs-cold`. Each was checked on all three surfaces R-19 claimed to have
swept. Every one either matches `thesis/claims.json` or carries its correction
inline: the QUESTIONS doc has a *Statistical standing (R-19)* note on each section
the registry materially contradicts, all nine sampled memories carry a
`CORRECTED 2026-07-21` block, and the `CLAUDE.md` Part V block quotes the deflated
P5.2 p-value with the undeflated one marked as such.

**The one defect, found while checking the surface rather than the sample.** The
banner at the top of `docs/questions/part5-anticipatory.md` — the sentence whose
entire job is to tell the reader which figure to cite — said *"**P5.2 is the
properly powered claim** (p = 3.05e-05, survives Holm)"*. That is the **undeflated**
value, which HANDOFF invariant I2 forbids citing. `CLAUDE.md` and the auto-memory
both had it right, so this was not a misunderstanding of the rule; it was the one
surface nobody swept twice. `docs/questions/part6-flight.md:88` had the same value
in the same shape. Both now lead with 6.10e-05 and name 3.052e-5 as undeflated.

New test: `test_first_read_surfaces_cite_the_deflated_p`. For every paired claim
where deflation actually moved the p, it scans the five first-read surfaces for a
`p = X` matching the **undeflated** value and requires the word "deflat"/"deflact"
on the same line. It is scoped two ways on purpose — the match must be attributable
(the line names the claim, or the value is < 0.01), because p = 0,25 is McNemar for
b=3, c=0 *and* the p of four unrelated claims, and a loose match flags every correct
sentence in the repo. Same judgement as the R-22 test docstring records, for the
same reason.

**2. R-7 — five numbers it dropped as clean, re-derived. PASS 5/5 (20 values).**
The complaint is that 2320 numbers were examined and 279 recorded, so 88 % were
dropped as clean with no record of the check. Sampled from the ledger rows that
carry a manifest path and a rate but appear in no sweep row — 17 such rows exist —
and recomputed every cell from `runners/runs/<id>/results.json`:

| ledger row | run | ledger | artifact |
|---|---|---|---|
| `part2:59` ladder @1024 | `20260617T191739Z` | 91.8 % / 30.3 % / 0.202 / 192.0 | 0.918 / 0.303 / 0.2019 / 191.986 |
| `part2:74` +LoRA in-loop | `20260617T212559Z` `final` | 100.0 % / 65.0 % / 0.497 / 226.6 | 1.0 / 0.65 / 0.4969 / 226.579 |
| `part2:20` Qwen2-VL-2B base HF | `20260617T170339Z` | 24 % / 15.0 % / 0.393 / 162.1 | 0.24 / 0.15 / 0.3933 / 162.078 |
| `part2:22` Qwen2-VL-2B base Q8_0 | `20260617T172502Z` | 19 % / 14.0 % / 0.533 / 187.5 | 0.19 / 0.14 / 0.5335 / 187.534 |
| `part2:18` smolvlm_ft3 Q8_0 | `20260617T121756Z` | 100 % / 67.0 % / 0.389 / 148.0 | 1.0 / 0.67 / 0.3889 / 148.015 |

Every value matches to the digit the ledger prints. This does not prove the other
2041 were checked; it says the dropped-as-clean population, where sampled, is clean.

**3. R-21 — five resolutions re-derived from the artifact each one cites. PASS 5/5.**
Sampled from the 7 of 74 rows whose `detail` names a `results.json` or
`sweep_summary.json`, since those are the only ones a third party can re-derive
without re-reading a prose source:

- **`0.2`** (export parity, `part2-rebuild.md`) — HF `full_val` 0.595, F16 0.621868,
  Q8_0 0.626424. HF→F16 = **+2.69 pp**, F16→Q8_0 = **+0.46 pp**; both gains, so the
  published minus signs were indeed backwards. 439 × those rates = 261 / 273 / 275,
  which is the "12 and 14 items above the HF reference" the rewritten line claims.
- **`0.18`** (resolution ladder) — 30.296 − 10.706 = **19.590 pp**, 30.296 / 38.724 =
  **78.2 %**, 30.3 % = **133/439**, and the 4.1 % → 38.7 % span is **9.44×**. The
  arithmetic was never wrong; only its status as a "gate" was.
- **`5.10`** (reground-chase, `part4-end-to-end.md`) — all ten `runs/rh-*/results.json`
  read back: `in_fov_frac` **0.2279–0.2305**, `carry_frames` **464–474**,
  `carry_px_err_mean` **8.6** in all ten, `n_regrounds` **1** in all ten,
  `relock_walls_s` empty in all ten. Every figure in the resolution reproduces; the
  field is named `relock_walls_s`, not `relock_on`.
- **`4.13`** (P6.1 CARLA, `part6-flight.md`) — `runs/g1-scripted/results.json` has
  `ticks` **400**, `frames_received` **399**; the 599 that had been published there
  is `runs/g3-mavlink/results.json`'s frame count (600 ticks). Confirmed as stated.
- **`5.12`** (streaming-carry parity) — the negative claim holds. A whole-repo search
  for `0.9974` and `0.9968` returns the ledger line, the campaign README prose, and
  otherwise only `frag` values inside `experiments/2026-07-17-bankv2-crossing/runs/*/gt.jsonl`.
  No parity log, `results.json` or CSV exists. The figures are correctly flagged
  unbacked, and landing an artifact for that leg is still open.

**4. R-16's raw rows edited after DONE (`81df727`). PASS — labels only, and
re-derivable.** 16 rows across the two committed `raw/*.jsonl`, 15 changed. The key
set is byte-identical before and after and the **only** field that differs anywhere
is `carry`; every timing, memory and rate field is untouched. Each rewritten label
is re-derivable from a field in its own row: `m3-clean.jsonl` rows carry
`prune_after` directly, and `m34.jsonl` rows — which have no `prune_after` field —
encode it in `tag` (`ring32`/`ring100`, absent on the three rows predating the flag,
which now read `prune_after=None`). The source fix in `cores_bench.py` makes the
label an f-string over `a.prune_after`, so it cannot recur.

One inaccuracy worth recording: the commit message says the rows were normalised
"from that field", meaning `prune_after`. That is true of `m3-clean.jsonl` only.
`m34.jsonl` has no such field and was normalised from `tag`. Both are in-row and
both check out, so the labels are right and the message is loose about which field.

**What the four together say.** The assertion-only DONEs hold where sampled, which
is the honest form of this result — a spot-check licenses the population it drew
from, not the whole. The defect that turned up was not in any sampled *verdict*; it
was in the sentence directing which p-value to cite, on the page that exists to be
read first. That is the shape to keep watching: the corrections landed and the
correction *instructions* drifted.


# Third wave — the empirical gaps the per-Part family exposes, R-34..R-36

Opened 2026-07-23T15:40Z, directly out of the R-30 decision. With Holm applied per
Part, the survivor count by chapter is:

| Parte | Cap. | m (p definidos) | Sobreviven |
|---|---|---|---|
| I | 4 | 8 | 1 |
| II | 4-5 | 5 | 3 |
| III | 5 | 14 | 3 |
| **IV** | **6** | **15** | **0** |
| V | 7 | 26 | 3 |
| **VI** | **8** | **2** | **0** |

**Chapters 6 and 8 have no inferential claim at all.** That is the gap, and it is not
uniformly serious — read each one before spending GPU on it.

**Chapter 6 is mostly fine as a negative chapter.** Its thesis is *"cold acquire is the
bottleneck, and optimising acquisition does not fix it"*. E19/E21/E22/E23 failing to
reject is **consistent with** that thesis, not a hole in it — you do not need Holm
survival to report five levers that did not work. The hole is the chapter's one
*positive* spine claim, and it is a single observation wide. See R-34.

**Chapter 8 has no claim because Part VI has run no experiment.** P6.0 and P6.1 are
capability gates, correctly recorded as descriptive. The fix is not statistical, it is
to run the experiment that was already proposed. See R-35.

## R-34 — Re-run E18 at n>=25 — P2

`E18-cold-acquire-vs-warm-oracle` is the closest miss in the entire registry:

    counts  b=5, c=0   k1=6/6 (warm oracle)  k2=1/6 (cold)
    n_rows 12 -> n_effective 6 (deterministic n=2 reps, correctly collapsed)
    exact McNemar p = 0.0625        reachable = yes, and it needs b = 6

Five discordant pairs, all one-way, out of six effective observations. **One more
one-way pair and it clears alpha**, and the design was reachable all along — this is
not an unreachable gate, it is an underpowered one. It is also Chapter 6's only
positive claim: *the ~4.85 s cold acquire delivers a box that is already stale on a
moving target*, which is the finding that motivated the whole of Part V.

**Design.** Same paired arms (cold blocking acquire vs the GT-seed warm oracle) on
**25 distinct UAV123 sequences**, one cell per sequence — not multiple onsets per
clip, per the R-29 lesson. Pure replay, no Jetson, no new infrastructure: this is the
P5.2a harness with the E18 arms. Estimated cost is hours, not days.

**Pre-register before running**, per the project workflow, and pre-register the
failure case too: if the effect is real at 20/25 the claim clears Part IV's family
comfortably; if the cold arm scores well above 1/6 on a broader clip set, the honest
result is that E18's original margin was a 6-clip artefact, and *that is also content*.

**RESOLVED 2026-07-23 (confirmed). YES [delivery-lag].** Pre-registered
2026-07-23T19:40Z; matrix `2026-07-23T19:45–20:20Z`; 50 result files, 0 INVALID.
`experiments/2026-07-23-e18-n25-replication/`.

    ORACLE 23/25   COLD 3/25   b(O>C)=21  c(C>O)=1   raw McNemar p = 1.10e-05
    R-29 deflation: 2 two-cell source clusters (car3/car3_s, person1/person1_s),
      both internally concordant -> ICC(1) upper95 = 1.0 -> n_eff = 23, b=19, c=1
    deflated p = 4.01e-05   Holm(Parte IV) 3.61e-04   Holm(global) 1.36e-03

E18 promotes from underpowered negative (p=0.0625, n=6) to confirmed at n=25. It is
now **Part IV's only inferential survivor** and the **9th global-Holm survivor**;
per-Part survivors 10→11, global 8→9 (`E18-...-n25` in `thesis/stats-report.md`).
The pre-registered surprise case did **not** fire — COLD scored 3/25, *below* E18's
1/6, so the effect strengthened on the broad set (b 17→21) rather than attenuating.

Three notes for the record: (1) the design line above said "no Jetson"; that
understates the cold arm — E18's leg A *is* a real Jetson q8_0 acquire (the ~4.85 s
wall time is the mechanism), so the COLD leg self-boots `JetsonBackend` per clip and
uses real Orin latency, which is the faithful choice. (2) The pre-run smoke caught a
latent init-latency stamping artifact in `replay_e18`'s oracle leg; forked
`replay_e18_clean.py` reusing P5.2a's `coverage_realtime` (D-R34.2). (3) Registered as
a NEW claim; E18 (n=6) kept as the as-run record with its "one clip too few" caveat
(D-R34.3). Proof: `proof/{discordant-bike1,pass-grid,effect-3regimes}.png`.
`make test` green (172 passed).

## R-35 — Build the closed-loop CARLA harness + run P6.2-DELIVERY — P1 (IN PROGRESS 2026-07-23)

Chapter 8's first real claim and **the round's flagship** (author steer 2026-07-23:
CARLA-primary, piloting-first — see below). Pre-registered:
`experiments/2026-07-23-p62-delivery/README.md`; full build spec + frozen gates in
`experiments/PART6-PROGRAM-warm-start-significance.md` §4.

**Not a simple port — a merge.** Grounding the rig (2026-07-23) corrected the earlier
"port the select modules into `run_phase_c.py`" framing: `run_phase_c.py` is the OLD
Gazebo rig (scripted rover, SmolVLM, no `import carla`). CARLA lives in two **disjoint**
scripts — `runners/carla_render.py` (async flight + position-slaved camera, NO GT/target)
and `runners/carla_gt_bank.py` (per-frame identity GT for a designated moving target, NO
SITL/MAVLink). R-35 = **merge both into one async closed-loop harness**
(`runners/run_p62_flight.py`) wired into `run_phase_c.py`'s source-agnostic seams
(`LatestDetectionSlot` :123, `_control_step_c` :584).

**Must be WRITTEN (Part V modules are replay-only):** the WARM and COLD detection
producers, and a **live ring buffer** for the idle window — `idle_catchup_multi`
re-walks PAST frames by index, structurally impossible on a live camera. Only
`StreamCarry.step` is stream-native. Latency becomes real `time.monotonic` wall-clock,
not frame-index emulation. Ring length **`PRUNE_AFTER=32`** (R-16: the deployed 100 is
OOM-killed at N=2). `CARRY_HZ=6.15` is retired (R-16: 2.69 Hz solo @1024). Fix/bound the
R-10 yaw (immaterial under the nadir camera, so bound it explicitly).

**G6 first:** run the never-executed grounding-over-CARLA check — does the deployed q8_0
resolve ~25x50 px cars at 60 m AGL? Unknown, gates every P6.x number.

Scope at n>=25 distinct CARLA scenarios from the start (one flight per arm per scenario)
— a closed-loop campaign at one flight per arm reproduces exactly the P3-T3 defect this
ledger retired. Determinism is lost (async on purpose); mitigate with a measured
schedule-noise band (P5.20 precedent).

**Author steer (frozen 2026-07-23T23:05Z):** CARLA `Town10HD_Opt` is the primary
substrate (reusable, controllable scenarios — weather/ToD/camera-angle), and piloting a
moving-target follow is the round's priority. Real-imagery perception/carry claims (R-36,
P5.21, REG) stay on UAV123 per the S5 honesty caveat. Weather/ToD/angle enter this round
only as seed-bank covariate diversity; a powered condition-robustness sweep is next round.

## R-35b — P6.2-COUPLING (isolates C1) — P2

Pre-registered `experiments/2026-07-23-p62-coupling/README.md`. Rides the R-35 harness and
reuses the P6.2-DELIVERY WARM flights as the coupled arm; only the decoupled (oracle-drive)
arm is new. Paired-continuous Wilcoxon + bootstrap CI — **cannot be cluster-deflated**
(`n_effective==n_rows`), so one flight per arm per seed, no reps, per-item values saved.
Runs after DELIVERY.

## R-36 — SWAP at n>=25 distinct clips — P2

Part V's residual, and the cleanest illustration of the R-29 lesson. P5.18/P5.19's
SWAP arm keeps missing, and the sample is **26 cells cut from 13 clips**. Measured
ICC on that data is ~0.25, so the 26 cells are worth roughly 21 independent
observations, not 26 and not 13. Cutting a 27th scene from `bike1` would add almost
nothing; a 14th clip would add a full observation.

**The rule this yields, which belongs in the method chapter:** *n counts clusters, not
cells.* Every future arm samples distinct source sequences first and extra onsets per
sequence only after the cluster count is met.

**Design (UPDATED 2026-07-23 — paired maintain-vs-select supersedes the single-arm SWAP).**
Pre-registered `experiments/2026-07-23-r36-maintain-vs-select/README.md`. The claim the
thesis defends is *maintain beats select*, so R-36 is now the **paired** WSEL-vs-SWAP
McNemar contrast (more powerful than a one-sample SWAP proportion), not a lone SWAP rate.
Decision + rationale in `docs/decisions/part5-anticipatory.md`.

**Reachability, disclosed up front:** the committed 13-clip SWAP data is **b=3, c=0,
p=0.25 — NOT reachable** (3 discordant pairs short of the 6 McNemar needs). R-36 requires
**>=12 NEW distinct SWAP-hard clips** (late-entry / carry-drift / distractor-confusion
families), one hard SWAP scene per clip, over-provisioned to **n~30** (projected b~7,
marginal). Pre-registered miss branch: b<6 or two-directional -> "select fails but is not
separable-from-maintain at this n," the powered ceiling of the select negative. Lower
priority than the R-35 flight (which rescues a chapter with zero claims); runs as a
Wave-B real-imagery bank in parallel.

**RESOLVED 2026-07-24 — NO [underpowered, scene-starved], the pre-registered MISS branch.**
The reachability risk fired at its worst: hand-curating 10 fresh candidates returned
**8/10 single-target** — UAV123 follows one target and structurally almost never frames two
co-visible same-class candidates, so the bank could not grow to n>=25 without contaminating
it. Bank = 13 reused P5.18 clips (deterministic; P5.20 replicated P5.19 with 0 flips) + the 2
usable-weak new clips (boat2, person13). Three reads, all miss or fragile: clean n=13 b=4
c=0 p=0.125; **audit-clean n=14 b=5 c=0 p=0.0625 (REGISTERED)**; mechanical full n=15 b=6 c=0
p=0.031 (WITHDRAWN — rests on person13's mis-placed distractor GT, which the mandatory visual
audit caught and excluded, plus boat2's discovery-scarcity SWAP fail). Direction is consistent
across all three (c=0 everywhere: select never wins a discordant), which **supports
maintain-and-deliver** — but it is the powered ceiling of the select negative, not an
inferential separation. Registered `R-36-maintain-vs-select` in `claims.json` (n_rows=14,
b=5/c=0). The scene-starvation is itself the finding. Detail:
`experiments/2026-07-23-r36-maintain-vs-select/README.md`.

## R-37 — P5.21 ROI-carry vs plain carry (paired) — DONE 2026-07-24

Pre-registered `experiments/2026-07-23-p521-roi-carry/README.md`. Paired McNemar, n>=27
distinct UAV123 hard-carry sequences. Closes the last non-capacity carry lever (bigger
SAM2 is dead, P5.20) as an OUTCOME contrast — the ROI re-anchor was only ever justified on
prefill cost / single-frame IoU, never as plain-vs-ROI carry survival. **Pilot-gated
(S2):** the plain-carry base rate must show headroom (0<rate<1) before the gate is locked,
or it repeats the P5.3/P5.4/P5.5 construction trap. Wave B.

**RESOLVED — TIE [measured negative]. Pilot gate PASS (5/8 = 0.62, headroom).** Matrix at
n=34 distinct-base hard-carry sequences (42 available locally after streaming the UAV123
tarball; 8 held out for the pilot). Plain 28/34 vs ROI 26/34; McNemar b=1, c=3, p=0.625
(n_eff=34, no deflation) — **direction is AGAINST ROI** (net-negative, not a clean tie).
The pre-registered drift-reinforcement failure fired: car10 re-anchor cropped a drifted box,
on-device VLM grounded off-target, track lost while plain held (IoU 0.86); guard flagged 1/3
c-side. One b-side win (car14). Grounding on Jetson q8_0, SAM2 carry on 3090 (rate-capped to
the deployed 2.69 Hz per R-16). Closes the last non-capacity carry lever — keep ROI for
acquire prefill only. Registered `P5.21-roi-carry` in `thesis/claims.json` (75 claims;
"Probadas, no significativas" 20→21; survivors unchanged 12/10). Proof:
`proof/p521_drift_reinforcement.png`, `proof/p521_per_seq_iou.png`. Visual gate PASS.

## R-38 — REG grounding isolation (paired, on-device) — P2

Pre-registered `experiments/2026-07-23-reg-grounding-isolation/README.md`. Paired McNemar
on the same prompt frame, target-phrase vs distractor-phrase, n>=28 (shares the R-36 bank).
A **dependent decomposition** of R-36 — declared in the same Part-V Holm family, not
independent confirmation. Decides whether the residual select failures are a grounding
asymmetry or live downstream (carry/delivery). Pilot the isolated distractor-grounding rate
first (P5.18's 0.65 is end-to-end, confounded). Wave B, on-device (`machine='both'`).

**RESOLVED 2026-07-24 — SYMMETRIC [pre-registered branch]: grounding is NOT the bottleneck.**
The n>=28 estimate was unreachable — the R-36 bank is scene-starved (14 gating scenes, all
distinct base captures) — but the frozen gate (b+c>=6 one-directional) *was* reachable at
n_eff=14, and the effect is genuinely symmetric so power was not the binder. **Pilot:** the
isolated distractor-grounding rate is 12/14 = 0.857, far above P5.18's 0.65 end-to-end — so
that 0.65 was never a grounding deficit, it confounded carry+delivery. **Matrix:** on the same
prompt frame, target-phrase 13/14 vs distractor-phrase 12/14; paired McNemar b=2, c=1, p=1.0
(n_eff=14, b+c=3 < the 6-discordant floor). The distractor box lands on the distractor *object*
(viewed: car9 sign gantry, car10 distant car, wakeboard8 boat), refuting the OOD
"always-lands-on-salient" reading. The 3 discordants are IoU-floor near-misses on tiny objects
plus person13 — the same mis-placed-GT cell R-36 withdrew (excluding it → b=1/c=1, more
symmetric). The residual select failure is therefore **not isolable to grounding** → attribution
redirects downstream to carry/delivery, supporting maintain-and-deliver. Registered
`R-38-REG-grounding-isolation` in `claims.json` as a dependent decomposition (76 claims;
"Probadas, no significativas" 22→23; survivors 12/10 as counted on the day — **corrected to 11/10
on 2026-07-25 by R-39**: registering R-36, R-38 and P5.21 grew Part V's family to m = 21 and pushed
`P5.15-plain-carry-survival` out, which nobody noticed at the time. That is the mechanism R-39
exists to catch). Proof: `proof/reg_landing.png`,
`proof/reg_per_clip_outcome.png`. Visual gate PASS.

---

