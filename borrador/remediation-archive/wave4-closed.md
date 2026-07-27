# Remediation archive — fourth wave, the closed items

*Closed history, split out of `thesis/REMEDIATION.md` on 2026-07-26 so the live
ledger only carries open work. Nothing here is actionable; it is the audit trail.
Cite by R-ID, never by line number (HANDOFF invariant I8).*

R-39..R-44, R-46, R-47, R-52, R-53, R-54. The open fourth-wave items (R-45, R-48,
R-49, R-50, R-51, R-55) stay in `thesis/REMEDIATION.md`.

---

## R-39 — Caveat prose must agree with the computed Holm verdict — DONE **P0** (2026-07-25)

**The defect.** `P5.15-plain-carry-survival`'s caveat said per-Part Holm "eleva a
0,04653: **sobrevive por poco**". The table two screens above it, in the *same
generated* `stats-report.md`, printed `0.05525`, and the survivor list omitted the
claim. One document asserted survival and non-survival on the same page.

**Nobody broke it.** No edit introduced this. Registering R-36, R-38 and P5.21 on
2026-07-24 grew Part V's Holm family from m = 18 to m = 21; the threshold tightened;
a claim that had survived stopped surviving. The p-values are *computed* and the
verdict prose is *stored*, so the arithmetic moved and the prose did not.

**This is the standing hazard of the R-30 per-Part family, and it recurs.** Every
future experiment added to a Part silently re-runs Holm over every claim already
published in that Part. Continuing to experiment inside Part V makes Part V's existing
claims more expensive. That is a real cost of the family convention, it was accepted
knowingly, and it now has to be *checked* rather than remembered.

**Resolution.** Rewrote both `caveats` and `caveats_en` on the claim to the current
numbers (per-Part 0.05525, global 0.09887, neither surviving), keeping the R-33 history
and adding the family-growth explanation — the mechanism is thesis content, not just a
correction. `verdict` stays `YES`: per registry convention the verdict is the as-run
label and statistical standing lives in the caveat (same shape as `P5.19-swap-late-entry-rescue`).
Regenerated `stats-report.md`.

Then made it mechanical: `tests/test_thesis_integrity.py::test_caveats_agree_with_the_computed_holm_verdict`.
It parses present-tense survival verdicts within 130 characters of the word "Holm" and
asserts the assertion set is a **subset** of `{per-Part reject, global reject}` — a
subset, not equality, because one sentence legitimately reports both families ("survives
per-Part; under the global family it does not").

Both narrowings are load-bearing and were chosen empirically, not by taste. The registry
uses "sobrevivir"/"survive" freely for masks, clips, mechanisms, tracks and files ("los
números solo sobreviven en el README", "the warm track survives THIS rig's ego-motion");
a looser pattern flags eleven claims, all eleven innocent. Past tenses are excluded
because a corrected caveat legitimately narrates its own history. As written it finds
**seven** real assertions across the registry, all consistent, zero false positives.

**Done-criterion, met:** the test passes on the corrected registry, and re-inserting the
old string makes it fail with
`prose says 'sobrevive' (survives=True) but Holm computes per-Part=False (p=0.05525), global=False (p=0.09887)`.
Verified by mutation, not by assertion.

## R-40 — Stale first-read surfaces — DONE P1 (2026-07-25)

`CLAUDE.md` still called Part V "paused at P5.20" (P5.21 ran 2026-07-24) and its Part VI
paragraph stopped at "**P6.2 is not blocked.**", never mentioning P6.2-DELIVERY,
-COUPLING, -SHOWCASE, EXP-1 or EXP-2. The three root ledger indexes agreed with it.
`PART6-PROGRAM` §5 still called the SHOWCASE flight half "BLOCKED on a host-GPU driver
reload" — it flew on 2026-07-24 (`bbe146d`). Both EXP READMEs opened with "**Status:**
PRE-REGISTERED (not yet run)" above their own filled Results sections, which is the
worst possible failure mode given `CLAUDE.md` tells a fresh session to "open this one
file".

All corrected, with the Part VI additions written to preserve the R-28 scope: every Part
VI result supports **maintain-and-deliver**, not select.

**One number was wrong in the source I briefed from, and is now fixed everywhere:**
P6.2-DELIVERY's `1.9e-06` had been labelled "deflated" in `PART6-PROGRAM` §5. It is not
deflated — the claim records `n_effective = n_rows = 25` ("25 semillas CARLA distintas
... sin subsecuencias tipo UAV123 `_s`"), and `1.907e-06` is the **per-Part Holm** value,
with `3.815e-05` global. The exact test is `9.537e-07`. Corrected in `PART6-PROGRAM` (both
the table cell and the section caption) and in `CLAUDE.md`. `README.md` states it
correctly.

## R-41 — `README.md` — DONE P1 (2026-07-25)

Two defects. The survivor count read "**Doce** sobreviven a la corrección de Holm por
Parte" against the report's "Sobreviven 11" (the R-39 drift, propagated); corrected to
**Once**. The other three numbers in that sentence (24, 10, and "diez en familia global")
were checked against the report's "Qué sobrevive" buckets and do reconcile, so they were
left alone.

Worse, "## En números" ended at the Part IV tracking ceiling — **the project's only
closed-loop result did not appear in the README at all.** Added P6.2-DELIVERY with its
scope caveat (ORACLE designation; control-coupling conditional on correct designation,
not grounding and delivery jointly) and its machine disclosure per I3, plus the
P6.2-SHOWCASE on-device counterpart explicitly marked as qualitative and outside the
Holm family.

## R-42 — Borrador citation hygiene — DONE P1 (2026-07-25)

Three defects in the chapter scaffolds, none of them prose:

1. cap08 carried **22 pseudo-citations** of the form `[cita @P6.2-DELIVERY-warm-vs-cold-closedloop]`.
   Those are registry claim ids, not bib keys — none is in `refs.bib`, so pandoc would
   have emitted broken citations or dumped the literal text into the PDF. Converted to
   the house form `` [claim `<id>`] ``. Every surviving `[cita @...]` in the borrador was
   then verified against `refs.bib`: ten distinct keys, all real.
2. cap01 said 12 survivors where cap03/08/09/10 said 11; corrected. cap07 repeated the
   stale P5.15 reading; corrected with the same m = 18 → m = 21 explanation as R-39.
   cap03's unresolved `[VERIFICAR ...]` note about which count is current is resolved.
3. **I8 violations** — cap10 cited `stats-report.md` by line twice and `00-esquema.md`
   by section-plus-lines; cap06 cited `00-esquema.md` "líneas 556-557". All four replaced
   with quoted-string anchors. `grep -rnE "líneas? [0-9]"` over the borrador is now empty.

`TFM-borrador.md` regenerated from the corrected scaffolds.

## R-43 — EXP-3's orphaned data — DONE P1 (2026-07-25)

EXP-3 ("click-to-ground-to-track") was pre-registered inside the EXP-2 campaign directory
as `README-exp3.md`, ran its acquire stage twice, and stopped. Its only outputs were
**gitignored**: `.gitignore`'s `experiments/*/runs/**` rule whitelists `results.json`,
and EXP-3 stopped *before* the score stage that would have written that name. Roughly
8.2 minutes of on-Orin q8_0 grounding existed nowhere in git.

Rescued with one narrowly-scoped re-include (`!experiments/2026-07-24-point-crop-select/runs/exp3/acquire*.json`)
— verified with `git add -A --dry-run` that exactly two files became trackable and the
`runs/**` guard is otherwise intact. The logs and the uncurated overlay PNGs were
deliberately **not** rescued: the logs are a strict subset of the JSON, and the PNGs are
non-systematic (5 FULL vs 1 OPT) and therefore not proof-grade.

`README-exp3.md` now says `STOPPED — PARTIALLY COMPLETE, NOT RUNNING`, records what ran
and what did not, states plainly that no claim was registered, marks the partial numbers
as **not a finding**, and annotates the two scripts its own command block references that
were never written (`make_proof_exp3.py`, `click_demo.py` — verified absent repo-wide).

## R-47 — EXP-3's acquire data contradicts EXP-2's crop elbow — RESOLVED P1 (2026-07-26T16:05Z)

**This is the one with research consequences, and it came out of the R-43 rescue.**

EXP-2's headline is a grounding-resolution elbow: a point-crop at 256 px out-grounds the
whole frame at 1024 (hit@0.5 0.769 vs 0.654). EXP-3 was pre-registered *on that
expectation*. On the CARLA bank it goes the other way, and not marginally:

| leg | 256 px crop (OPT) | 1024 crop (FULL) |
|---|---|---|
| rich caption, hit@0.5 | 2/25 | **14/25** |
| rich caption, mean IoU | 0.229 | **0.470** |
| generic caption, hit@0.5 | 3/25 | 5/25 |

Paired discordants on the rich leg: **12 favour FULL, 0 favour OPT**, at every altitude
from 40 to 120 m. The latency ordering is unchanged and large (OPT median ~1017 ms vs
FULL ~9063 ms, 8.9x).

**What to do.** Nothing is registered and nothing should be yet — this is half an
experiment, unaudited, and the caption knob is an unregistered post-hoc addition. But
before EXP-2's elbow is stated anywhere as generalising **beyond its own scene set**,
this has to be reconciled. The two runs differ in imagery (UAV123 vs CARLA), in caption
richness, and in altitude range, so the honest reading may simply be that the crop elbow
is scene-set-bound — which is itself a finding worth having, and one the thesis would
rather state than have an examiner discover.

### RESOLVED 2026-07-26T16:05Z — there is no contradiction; the arm names mislead

Reconciled from data already on disk (`runs/exp3/acquire.json`, `acquire_rich.json`), no
new runs. **The premise above is wrong, and it is wrong in the way `HANDOFF.md` I7 warns
about — "do not trust your first read of someone else's schema."** Three findings, in
order of how much they matter.

**1. EXP-3's `OPT`/`FULL` are not crop-vs-whole-frame. They are the same crop at two
upscale factors.** `select_exp3.py` varies exactly one thing per arm —
`select_p55.ROI_RES = cfg["ground_res"]` — and `ROI_RES` is documented in `roi_reanchor`
as "crop the deployed ROI window around the carry's current box, **resize long edge to
ROI_RES** (LANCZOS)". `ROI_MARGIN = 2.0` and `ROI_MIN_SIDE = 256` are untouched, and the
prior handed in is the degenerate click box `_center_box((cx, cy, cx, cy))`, so **both
arms crop the identical 256 px native window** around the click. The only difference:

| EXP-3 arm | native crop | `ROI_RES` | upscale |
|---|---|---|---|
| `OPT` | 256 px | 256 | **1.0x** (none) |
| `FULL` | 256 px | 1024 | **4.0x** LANCZOS |

"FULL" means full *resolution*, not full *frame*. Read that way, EXP-3 says: a 4x upscale
of a crop that carries no extra information still grounds better, because the upscale buys
visual tokens on target. That is not the elbow EXP-2 measured.

**2. EXP-3 never re-ran EXP-2's configuration, so the two cannot disagree.** EXP-2's `PT`
arm calls the same `roi_reanchor` but **never overrides `ROI_RES`**, so it inherits the
module default `ROI_RES = 512` — a 256 px crop upscaled **2x**. Its `NL` baseline is the
whole frame at `MAX_SIDE = 1024`. Lining all of it up on one axis, pixels-on-target fed to
the encoder, every result points the same way and none of them conflict:

| run | comparison | winner |
|---|---|---|
| EXP-2 | 256 px crop @512 (2x) vs whole frame @1024 | **the crop** (hit@0.5 0.769 vs 0.654) |
| EXP-3 | 256 px crop @1024 (4x) vs same crop @256 (1x) | **the upscale** |
| EXP-4 | native-1920 crop vs the 960 feed crop, both @512 | **the native crop** (b=8, c=0) |

EXP-3's `OPT` sits *below* EXP-2's operating point, not at it. EXP-3 tested a setting
EXP-2 never used, found it worse, and that was read as a contradiction. The deployed
`ORIN_GROUND_RES = 512` is EXP-2's measured point and is unaffected.

**3. The "12 discordants to 0" is a hit@0.5 artefact and does not survive the threshold
this repository actually operates at.** Part V/VI score delivered-PASS at IoU 0.25
everywhere else. Re-scored at 0.25 (same data, same pairing, `grounding.stats.mcnemar`):

| leg | thr | `OPT` | `FULL` | b (`OPT`-only) / c (`FULL`-only) | p |
|---|---|---|---|---|---|
| generic | 0.50 | 3/25 | 5/25 | 2 / 4 | 0.6875 |
| generic | 0.25 | 5/25 | 5/25 | 3 / 3 | 1.0 |
| rich | 0.50 | 2/25 | 14/25 | 0 / 12 | 4.883e-04 |
| rich | **0.25** | 13/25 | 16/25 | **1 / 4** | **0.375** |

Only the rich-caption/hit@0.5 cell is significant. At 0.25 it is a null, and with a generic
caption it is a null at both thresholds. So the effect is conditional on a strict box
threshold *and* a colour caption simultaneously; neither alone produces it.

**Mechanism correction, which changes a deployed comment.** `carla_debug_ui.py` justifies
its 512 with "rich-caption grounding wants the 1024 crop (256 starves colour on a nadir
car)". The data says otherwise: going generic to rich *more than doubles* what the 256
crop finds (5/25 to 13/25 at IoU 0.25). Colour is not starved — the rich caption is
working at 256. What 256 cannot do is draw a box tight enough to clear 0.5 (mean IoU 0.229
vs 0.470). The conclusion "prefer more resolution for rich captions" is right; the stated
reason is wrong, and it has been corrected in place.

**Consequences.**

- **EXP-2's elbow is not contradicted and does not need a scene-set caveat on this
  ground.** It remains bounded by its own scope for the ordinary reason (one scene set),
  but EXP-3 is not evidence against it.
- **Do not cite EXP-3 as "crop hurts on CARLA".** It measures the upscale knob. The
  correct one-liner is "at a fixed 256 px crop window, feeding it at 1024 beats feeding it
  at 256, at 8.9x the latency (median 9063 ms vs 1017 ms)".
- The latency ordering is unchanged and is the reason 1024 is not the default.
- R-47 no longer blocks anything. **Finishing EXP-3 is now optional** — candidate #2 in the
  slate below ("finish or kill EXP-3") loses its stated motivation, since the disagreement
  it was meant to resolve does not exist. Kill is the cheaper honest answer.

## R-44 — EXP-1/EXP-2 publish p-values outside the registry — **DONE** (demoted) P1

Both campaigns have full ledger rows and committed proof, and both publish inferential
numbers: EXP-1 "McNemar b=0 c=3 p=0.25", EXP-2 "b=1 c=3 p=0.625" and "b=0 c=2 p=0.5".
Neither is in `thesis/claims.json`, which `HANDOFF.md` calls the source of truth — so
they are invisible to `run_stats.py`, to the Holm family accounting, and to every
integrity test. EXP-1 even pre-registered an id it never landed
(`EXP1-track-res-noninferiority`).

Two defensible options, and it is the author's pick:

- **Register them.** Correct by I1, and it grows Part VI's family from m = 2 to m = 4,
  which by the R-39 mechanism tightens Holm on P6.2-DELIVERY. Worth checking that the
  flagship still survives before committing to this — it is not in danger at 9.5e-07,
  but the number moves and the thesis quotes it.
- **Demote them to engineering measurements** and strip the p-values from the ledger
  rows, keeping the elbows as descriptive operating-point selections. Both were run to
  *choose a resolution*, not to test a hypothesis, so this is not a dodge.

The one thing that is not acceptable is leaving published p-values outside the registry.

### DONE 2026-07-26T18:55Z — author picked *demote*

The second option, applied to **EXP-1, EXP-2 and EXP-6**. Each ledger row now carries an
explicit "engineering measurement, not a registered claim (R-44)" label naming what it is
*not* — not in `claims.json`, no Holm entry, no inferential result — and the inferential
numbers are **moved, not deleted**: they stay in the campaign READMEs, which `CLAUDE.md`
already makes the source of truth while the ledgers are rollups. Nothing measured was lost;
what was removed is a p-value appearing in a rollup where it read as a thesis-level test.

| ledger | what changed |
|---|---|
| `docs/results/part6-flight.md` | EXP-1: banner + `McNemar b=0 c=3 p=0.25 (n.s.)` becomes "3 of 38 clips lose PASS at 768 and none gain". EXP-2: banner + the `p (deflated 13 clips)` column dropped, `MISS` restated as a *design* verdict (b+c below the reachable floor 6). EXP-6: banner + the `p raw`/`p deflated` columns dropped, the CONTROL-2 row restated on effect size and PASS |
| `docs/questions/part6-flight.md` | the same three verdicts, same substitutions; EXP-6's "statistically indistinguishable" becomes "indistinguishable on its pre-registered bounds" (0.03 IoU, 1 PASS clip), which is what the gate actually said |
| `docs/decisions/part6-flight.md` | the two EXP-6 entries and the EXP-7 non-run entry stop quoting `deflated p=0.0918` / `p=0.566` and cite the effect size and discordant counts instead |
| `grounding/contract.py`, `runners/carla_debug_ui.py` | the `CARRY_CROP_SIDE` comments cited `deflated p=0.566`; now `d_IoU -0.002, d_PASS -1 of 38` |

*Why demote rather than register.* All three were run to pick an operating point — a carry
resolution, a grounding feed resolution, a carry mode — and each stopped as soon as the elbow
was located. None was pre-registered against a hypothesis in `claims.json`; EXP-2's design
could not reach alpha=0.05 at its n by construction (`min_discordant`=6 against b+c of 4 and
2), and EXP-6's primary stratum is at PASS ceiling in both arms with zero discordant pairs.
Registering results that were never powered would have grown Part VI's Holm family from m=2 to
m=4 and tightened the correction on P6.2-DELIVERY — paying a real cost on the flagship to
admit three numbers that cannot support a claim either way. That is the R-39 recurrence hazard
pointing the wrong way.

*Not done, deliberately.* **EXP-4 has the identical defect** — `p=0.0078` and `p=0.039` in
`docs/results/part6-flight.md`, plus `p=0.039`/`p=0.0029`/`p=0.0078` in its `docs/decisions`
entry, none of it in `claims.json` — and the same pick applies verbatim. The scope asked for was
EXP-1/EXP-2/EXP-6, so widening it silently would have been the wrong call; filed as **R-55**.
EXP-4 is the *same campaign* as EXP-6 (`experiments/2026-07-26-crop-mode/`), so until R-55 lands
that campaign's experiments are labelled inconsistently in the ledgers. EXP-5 needs nothing: it
publishes no p-value in any ledger and already says "not in `thesis/claims.json` and no Holm
correction — exploratory by pre-registration".

*No mechanical guard added.* The natural test — "a `p=` in a Part ledger must sit near a
registered claim id or an engineering label" — would fire on every Part I-V row too, so it
cannot be added without first classifying all of them. R-55 is the cheaper next step.

## R-46 — The "deployed" carry resolution is stated three ways — DONE P1

EXP-1's decision reads "Adopt SAM2 track-res 640 as the default carry resolution — the
measured elbow — keeping 1024 as a size-gated fallback". The code does not agree with
itself:

| file | says |
|---|---|
| `runners/carla_debug_ui.py` | 640 (the new decision) |
| `experiments/2026-07-24-p62-showcase/carry_ssh_bridge.py` | `default=1024` — "deployed default; EXP-1 sweeps 768" |
| `runners/p62_producers.py` | `CARRY_HZ = 2.69` — "R-16 on-device SAM2 solo rate @ image_size 1024" |
| `experiments/2026-07-01-temporal-acquire-carry/jetson_carry_service.py` | `default=640` (since 2026-07-02, for unrelated reasons) |

A future session reading any one of these gets a different answer to "what do we actually
deploy". Note the coupling: `CARRY_HZ` is a *measured* constant at 1024, so moving the
default to 640 without re-deriving it silently rate-caps the carry against the wrong
number. `README.md`'s "a la resolución que corre de verdad (1024) son **372 ms** por
paso" was left untouched pending this decision — it is still true of the 1024
configuration.

**Done-criterion:** one place defines the deployed resolution, every other site reads it
or cites it, and `CARRY_HZ` is re-derived at whatever that resolution is.

### DONE 2026-07-26T17:20Z

`grounding/contract.py` owns `CARRY_IMAGE_SIZE = 640`, `CARRY_FALLBACK_IMAGE_SIZE = 1024`
and `CARRY_HZ = 5.76` (EXP-1, Orin 15 W + jetson_clocks). It is the host because it exists
for exactly this failure mode and is stdlib-only, so the on-device service can read it
without torch.

| site | now |
|---|---|
| `runners/carla_debug_ui.py` | imports — `ORIN_CARRY_SIZE = CARRY_IMAGE_SIZE` |
| `runners/p62_producers.py` | imports `CARRY_HZ`; the retired 2.69 kept as `P62_ASRUN_CARRY_HZ` |
| `experiments/2026-07-25-handoff-latency/handoff_p67.py` | imports — `CARRY_SIZE = CARRY_IMAGE_SIZE` (was a 512 literal) |
| `experiments/2026-07-24-p62-showcase/carry_ssh_bridge.py` | cites; default 1024 to 640 (runs on the Orin, cannot import) |
| `experiments/2026-07-01-temporal-acquire-carry/jetson_carry_service.py` | cites; already 640 |
| `README.md` (es) | rewritten: 174 ms/paso at the deployed 640, 1024 named as the manual fallback |
| `experiments/2026-07-25-maintain-cost/README.md` | arm-C row no longer claims 512 is "what the panel actually runs" |

Two provenance notes that came out of this and matter more than the tidiness:

- **The coupling was live.** `CARRY_HZ` is a *measured* constant, so pairing R-16's 2.69
  (at 1024) with a 640 default rate-capped the replay carry at 2.5x slower than the
  hardware it was modelling. Re-derived at 640, from the same campaign as the 1024 figure
  it is compared against.
- **1024 is double-measured** — R-16 2.69 Hz, EXP-1 2.34 Hz, same box. Not reconciled here;
  both are cited where they appear, and the pair quoted together (5.76 / 2.34) is EXP-1's.

Two reproduction hazards, recorded rather than papered over: P6.2's published matrix ran
at 2.69, so reproducing it needs `carry_hz=P62_ASRUN_CARRY_HZ` passed explicitly; and
P6.7's published per-step terms were measured at 512, so a re-run today measures 640 (its
start-up terms, 4.95 s of the 6.15 s, are resolution-independent and do not move).

## R-52 — What does maintaining cost? — **DONE**, P6.6 run 2026-07-26

The author's own framing of warm-start is compute/timing efficiency, and the repository
has **no watt figure for it**. WARM burns SAM2 at 2.69 Hz on the Orin for the whole idle
window to save 4.85 s once. Over a 60 s window on a battery-limited airframe that trade
may be *negative*, and nothing here says either way. It is the sharpest unaddressed
criticism of the warm-start position — sharper than the N=1 one, because N=1 is a scope
statement while this is a missing measurement.

**Shape:** on-device only (`machine=jetson`), 15 W + `jetson_clocks`. Sample power with
`jtop`/`tegrastats` over three arms at matched wall-clock — idle baseline, maintain N=1 at
the deployed carry resolution, and a cold acquire — then report joules per delivered box
as a function of idle-window length, i.e. the window length at which maintaining costs
more energy than it saves. Report the thermal state too: sustained carry on this board is
as likely to be bounded by throttling as by watts.

**Why it is worth the afternoon:** it converts "compute efficient" from an assumption into
a curve with a crossover point, it is a *deployment* number rather than another accuracy
number, and it is the kind of measurement an edge-hardware thesis is expected to have and
this one currently does not.

**Landed 2026-07-25T18:06Z (`0a806bb`), execution deferred by the author:** the full
pre-registration is `experiments/2026-07-25-maintain-cost/README.md` — five arms
(`A0` idle-bare, `A1` idle-deployed with `llama-server` resident, `B` carry-640,
`C` carry-512, `D` ground), 300 s each, 3 repeats, order shuffled inside a repeat,
`tegrastats --interval 500` taking the **instant** mW, and one falsifiable gate
(**G1**: last-60 s carry rate within 10% of the first 60 s). `run_p66.py` and
`maintain_cost_dev.py` are committed and have **never been executed against the
device**; their pure parts are covered offline by `tests/test_p66.py`.
The ID is **P6.6**, left clear of R-45's proposed EXP-1/2/3 → P6.3/P6.4/P6.5 rename.
Estimates are recorded up front (maintain **+5 to +8 W** over idle, ~2-5% of a
150-400 W hover, G1 holds) so estimate-vs-actual is content either way.

**CLOSED 2026-07-26T16:20Z — the criticism is answered, and the answer is favourable.** Run
14:06Z-15:51Z, `machine=jetson-orin-nano`, 15 W + `jetson_clocks`, median of 3 repeats per arm.
**Maintaining costs +5.65 W** over an idle board (carry-640 10.842 W vs idle-deployed 5.193 W) =
**1.4-3.8% of a 150-400 W hover** (literature band, this project has no airframe). The crossover
the remediation asked for exists and is short: **break-even against one 4.85 s cold acquire is a
9.9 s idle window**, and past it warm is more energy for less staleness, bounded — 1.54x at 30 s,
1.92x at 120 s, asymptote 2.09x. So "over a 60 s window the trade may be negative" resolves to
1.77x the joules for 4.85 s of freshness on a ~5 W baseline, i.e. a rounding error against hover,
not a negative trade. **G1 passed 6/6 and the sign is up** (+0.17% to +0.53% over 300 s) while
`tj` soaks 57 to 65 C and flattens — the throttling half of the concern is measured and absent at
this window length; 300 s is the measured window, longer is extrapolation. Two extras: a resident
`llama-server` is **free** when idle (`A1 - A0 = -0.002 W`), so the maintain price is entirely
SAM2's; and carry power is **rail-bound, not work-bound** (512 runs 1.60x the rate at 0.15 W
*less*, both at `GR3D_FREQ` 99%, so J per carried frame falls 38%). Also corrected here: this
entry's own premise said "SAM2 at 2.69 Hz" — the deployed carry measures **6.27 Hz at 640** on
this board.

Not added to `thesis/claims.json`: a characterisation curve whose one pre-registered falsifiable
prediction passed is not a gated claim, and registering it would inflate the Holm family with a
non-claim. Ledgered under Part VI in all three docs; three figures under
`experiments/2026-07-25-maintain-cost/proof/`, reproducible by running `make_proof.py` with no
arguments. One repeat (`B_r2`) was contaminated by a host-side CARLA panel prewarming the Orin
and is excluded by name and re-run — see the DECISIONS entry.

## R-53 — The live panel cold-started a SAM2 bridge per designation (DONE)

P6.7 (2026-07-25) measured what that costs and what removing it buys, on the Orin, paired
over 25 CARLA clips: median `t_handoff` 6.311 s -> **0.515 s** at the deployed 4.85 s
grounding lag (12.3x; 6.148 s -> 0.299 s on an oracle click), 25/25 pairs concordant,
Wilcoxon p=1.228e-05. **80% of the 6.15 s is process start-up** (`import torch` + `sam2`
2.846 s, `from_pretrained` 1.800 s, first CUDA forward 0.670 s, `ssh` 0.301 s); only
0.361 s is catch-up. The residency risk was measured and is not real: a resident SAM2
costs the VLM **x1.000** (`ground_ms` 3791.1 -> 3791.2 ms, 25 paired requests), 0/50
`rc=-9`, `MemAvailable` floor 1315 MB.

**CLOSED 2026-07-25T20:20Z.** The campaign landed first
(`experiments/2026-07-25-handoff-latency/`, `P6.7-HANDOFF-warm-vs-cold-bridge` in
`claims.json`), then the code change on `main` as its own commit, per the infra/experiment
separation rule. `runners/carla_debug_ui.py` now keeps one session-scoped bridge
(`get_bridge` / `prewarm_bridge` / `bridge_io`), prewarms it at start-up beside
`get_backend()`, and re-`init`s per designation; `_stop_current()` no longer kills it and
the window-close path is the only reaper. Verified live, not by inspection: a `--pilot
copter --smoke` run designated `vehicle.nissan.micra` and the panel's own `catchup_s` read
**0.343 s** (`runs/p67-panel/trace-127/trace.jsonl`, `ev="live"`) against the 6.52 s median
of the 64 pre-change traces — same metric, same panel. `ui_bridge.err` from that run shows
one model load and two `init`s (prewarm + real seed), which is the residency working.
Written up in `runners/CARLA_DEBUG_UI_FINDINGS.md`. Not fixed by this and not claimed: the same run
drifted at 76 m from a 5x13 px VLM seed — grounding quality is a separate problem.

*R-46 datapoint (the "deployed" carry resolution is stated three different ways):* P6.7 is
a fourth statement — its matrix ran at `image_size=512`, while EXP-1 adopted **640** as the
measured default with 1024 as a size-gated fallback. P6.7 deliberately did not sweep
resolution (EXP-1 owns that knob), but that means the seam's per-step terms (`warmup_init`,
`drain`) are quoted at 512, not at the adopted 640. The start-up terms — 4.95 s of the
6.15 s — are resolution-independent, so the conclusion does not move; the sub-second WARM
figure would rise slightly at 640. Whoever closes R-46 should fix one number in one place
and make P6.7's harness read it. **Done 2026-07-26:** `handoff_p67.CARRY_SIZE` now reads
`grounding.contract.CARRY_IMAGE_SIZE`; the published numbers stay 512 and the file says so.

---

## R-54 — P5.20's owed on-device capacity gate — **DONE** (EXP-9, 2026-07-26T22:30Z)

P5.20 rejected `hiera-small` on 3090 replay and rejected `base_plus` **at design time, without
measuring it** ("undeployable on 8 GB"). Two things were owed: an on-device gate for small, and an
actual measurement for base_plus. EXP-9
([`experiments/2026-07-26-encoder-runtime-capacity/`](../../experiments/2026-07-26-encoder-runtime-capacity/README.md))
paid both, co-resident with the deployed `llama-server` at 15 W + `jetson_clocks`.

- **small:** fits (547 MB peak CUDA), clears 5 Hz (5.383), TensorRT-exported — and still does not
  win. Delta +0.0003 [−0.0046, +0.0036], p=0.987, b=2/c=0 against the **6** discordant pairs n=38
  needs. G3 is a keep-tiny. Recorded as **underpowered by construction, not equivalence** (I4).
- **base_plus:** the design-time rejection was **wrong on its stated reason**. It loads and steps
  with **1059 MB of board headroom**. It fails on **rate** — 4.14 Hz, under the ≥ 5 Hz gate.
- **Byproduct, and the more useful half:** the TensorRT fp16 encoder is adopted at 640 (+19.5 %,
  paired median IoU delta exactly 0.0000), and the pre-registered H1 arithmetic missing by 2.7x
  back-solves the encoder to **28.7 % of the 640 step**, which bounds INT8 to ~+5 % without running
  it. See the two EXP-9 entries in `docs/decisions/part6-flight.md`.

No claim registered — engineering measurement, R-44 standing, so `thesis/claims.json` and the Part VI
Holm family (m = 2) are **unchanged**.

Consequence for the slate below: "bigger SAM2" is now dead **on-device** as well as on replay, so
item 3's dead-lever warning applies with one fewer escape hatch. Nothing else on the slate moves.

---

