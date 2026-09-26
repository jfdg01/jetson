# SPEC — TFM document

Working spec for the thesis document. Agreed with the author on 2026-08-27 in a
`/grill-with-docs` session. This file is an engineering artifact, not thesis text, so it is
written in English. Everything it describes is written in Spanish.

Status: **agreed, not started.** No chapter exists yet.

## Problem Statement

The experimental programme is closed. The supervisor approved the work and no further
experiment will run. What remains is a written document that a tribunal can read.

The evidence is complete and the text does not exist. `experiments/` holds 102 campaigns,
55 `proof/` directories, 165 committed PNG files and 77 committed MP4 files. The largest
single campaign, `2026-07-28-tracker-capacity-sweep`, holds 28 log entries, 2322 runs and
about 63.7 h of device time. None of it is a document.

Three earlier attempts exist on disk and none of them is usable. `borrador/borrador/`
holds ten chapter scaffolds with 287 paragraph specs and zero prose. `borrador/TFM-borrador.md`
assembles those scaffolds. `tesis/tesis.md` holds finished prose for two experiments out of
102. The author has not read the first two and treats all three as dead.

The author also does not hold the repository in his head. Most of the work was produced by
agents under a pre-registration rule, so the record is complete and the author's memory of it
is not. The document therefore has a second job beyond the tribunal: it is how the author
reads his own project back.

## Solution

One Spanish document of thirteen chapters, written from the per-experiment records, under
150 pages, in plain markdown with no template. The author applies the visual style himself
and produces the PDF.

The work runs iteratively. The first pass writes the important developments only. Later
passes add the negative results and the minor positives.

Three decisions stay open by the author's choice, because each depends on reading he has not
done. They block no chapter that this spec schedules:

1. The central claim of the thesis, which fixes chapter 1 and chapter 13.
2. The depth of chapter 3, the state of the art.
3. Whether the metric definitions live in the glossary or in chapter 4.

The chapter order does not depend on the central claim, so the arc chapters proceed while
those stay open. Chapter 1 and chapter 13 are written last.

### Table of contents

```
1.  Introduccion
2.  Glosario y vocabulario
3.  Estado del arte
4.  Plataforma, metodo y metricas
5.  Parte I   — la placa y los modelos base
6.  Parte II  — grounding de un solo fotograma
7.  Parte III — permanencia del objeto
8.  Parte IV  — el arco de latencia de adquisicion
9.  Parte V   — grounding anticipatorio (warm start)
10. Parte VI  — lazo cerrado en vuelo
11. Parte VII — catalogo de seguidores y punto de operacion
12. Amenazas a la validez
13. Conclusiones
```

Chapter 11 is the July to August tracker capacity sweep. The repository never gave it a Part
number and `CLAUDE.md` stops at Part VI. This document gives it one.

The written titles carry full Spanish diacritics. They appear unaccented in this code block
only because the block is verbatim ASCII.

### Order of work

Chapter 2, the glossary, comes first. It depends on no verdict, no central claim and no
statistic, every later chapter consumes its terms, and it is the shortest path for the author
to see what the repository contains. The arc chapters follow. Chapter 1, chapter 3 and
chapter 13 come last.

## User Stories

1. As the author, I want one markdown file at the end, so that I can apply my own style and
   produce the PDF without fighting a template.
2. As the author, I want the document written in Spanish castellano with full diacritics, so
   that it is submittable as written.
3. As the author, I want the document under 150 pages, so that a tribunal reads all of it.
4. As the author, I want to work on one chapter at a time in its own file, so that an edit
   touches one file and a diff stays readable.
5. As the author, I want a single command that assembles the chapters into the deliverable,
   so that the one-file requirement costs me no manual work.
6. As the author, I want the build to fail when the assembled file is stale, so that I never
   hand in a version that misses a chapter I wrote.
7. As the author, I want a glossary near the start, so that a term means one thing across
   thirteen chapters.
8. As the author, I want the glossary to be exhaustive across concepts, metrics, models,
   datasets and hardware, so that no chapter uses a name the reader has not met.
9. As the author, I want the glossary grouped into blocks, so that `CARLA` does not sit next
   to `carry` and create the confusion the glossary exists to remove.
10. As the author, I want an explicit `no es` line on every overloaded term, so that the two
    meanings of `carry` and the two meanings of `crop` cannot silently merge.
11. As the author, I want each experiment described by what was done and what came out, so
    that the page budget goes to findings and not to command blocks.
12. As the author, I want a footnote under every claim that points at its campaign directory,
    so that I can reach the raw record while I read my own thesis.
13. As the author, I want plain prose where the result is obvious, so that a sentence such as
    "this model loses the cars" does not carry a p-value it does not need.
14. As the author, I want statistics only where a result escapes intuition, so that the
    inferential machinery is visible exactly where it does work.
15. As the author, I want every number to carry its unit and its `n`, so that a number stays
    meaningful after somebody quotes it out of context.
16. As the author, I want the decimal point everywhere, so that the text agrees with the raw
    records and no conversion introduces a typo.
17. As the author, I want technical terms kept in English, so that the vocabulary matches the
    field and no invented Spanish equivalent obscures the intent.
18. As the author, I want pure impersonal Spanish, so that the register is uniform and the
    document never implies a second author.
19. As the author, I want tables and figures placed as I write, so that a chapter is finished
    when I finish it and no visual pass is owed later.
20. As the author, I want every figure produced by a committed script, so that a figure can be
    regenerated when a number changes.
21. As the author, I want the figure script to reject a blank PNG, so that a silent render
    failure cannot reach the document.
22. As the author, I want the PNG files committed, so that my own style pass builds without
    running any Python.
23. As the author, I want behaviour shown as a three-frame strip of before, event and after,
    so that a finding that only a video proves still reaches a PDF.
24. As the author, I want a disclosure section about the agent-assisted method, so that a
    tribunal reads it from me in chapter 4 and never discovers it by accident.
25. As the author, I want the pre-registration rule described beside that disclosure, so that
    the method reads as a control and not as an excuse.
26. As the author, I want the machine split stated where it happens, so that a number measured
    on an RTX 3090 is never read as a Jetson number.
27. As the author, I want the negative results named inside the comparisons that need them,
    so that a chapter has no hole where a killed lever used to be.
28. As the author, I want the remaining negative results added in a later pass, so that the
    first pass finishes while the important developments are still fresh.
29. As the author, I want to read the arc chapters before I choose the central claim, so that
    the claim follows the evidence instead of the evidence following the claim.
30. As a tribunal member, I want a glossary before the state of the art, so that I can read
    chapter 3 without a search engine.
31. As a tribunal member, I want each result to name its sample size and its protocol, so that
    I can judge how far it generalises.
32. As a tribunal member, I want the threats to validity in one chapter, so that I can see what
    the author knows is weak.
33. As a future reader with the repository, I want the footnote pointers to resolve, so that
    I can open the campaign that produced any number I doubt.
34. As the supervisor, I want the tracking work to hold a chapter of its own, so that the
    emphasis he asked for is visible in the table of contents.
35. As the agent writing this, I want the settled decisions in one file, so that a session with
    no context can continue the document without a second interview.

## Implementation Decisions

### Sources of truth

- `experiments/<campaign>/README.md` and its `notes/` are the source for every number, every
  verdict and every negative result. `CLAUDE.md` already declares the per-experiment record as
  the source of truth and the ledgers as rollups.
- `docs/questions/part{1-6}-*.md` supplies the settled research questions per arc, and is the
  entry point for chapters 5 to 10.
- `borrador/` prose is dead and is not read. The two computed artifacts inside it,
  `borrador/claims.json` and `borrador/stats-report.md`, are read **as a number lookup only**,
  because they hold the only Holm-corrected p-values in the repository. They never supply text.
- `tesis/` stays untouched. `tesis/CLAUDE.md` declares that directory read-only, and this work
  does not need it. One exception is a code import, described below.

### Layout

- `documento/capitulos/NN-<slug>.md`, one file per chapter, thirteen files.
- `documento/tfm.md`, the assembled deliverable. Generated, never hand edited.
- `documento/figuras/`, the figure code, one module per chapter plus the shared style.
- `documento/refs.bib`, the bibliography, seeded from `SOURCES.md`.
- `documento/build.py`, the single entry point. Described under Testing Decisions.
- `documento/SPEC.md`, this file.

### Writing rules

- Spanish castellano, full diacritics in every line, including table captions and figure
  captions.
- Pure impersonal voice. `se midio`, never `medimos` and never `medi`.
- Decimal point in every number, in prose and in tables alike. Units with a space and the
  correct symbol: `67 °C`, `15 W`, `159.4 ms`, `2.69 Hz`.
- Technical terms stay in English and are never translated. `grounding`, `tracking`,
  `warm start`, `crop`, `prompt`, `KV cache`.
- Every number that has a unit carries it. A number in a table carries its unit in the column
  header instead.
- An estimate is marked as an estimate and never presented as a measurement.
- No command blocks in the body. The exact command lives in the campaign record, and the
  footnote points there.

### Glossary, chapter 2

- Four blocks, alphabetical inside each block: concepts, metrics, models and software,
  datasets and hardware.
- An entry carries the term, a definition, and the arc that produced it.
- An entry carries an explicit `no es` line when the repository overloads the term. Two are
  known already. `carry` names the warm start buffer in Part V and a frame rate in the retired
  `CARRY_HZ`. `crop` names the acquire prefill window and the tracker input window.
- Contested terms are surfaced to the author as they appear. He settles them and the rest of
  the document inherits the decision.

### Traceability

- A footnote under the claim, carrying the campaign path and, where the campaign has one, the
  note number. Example target: `experiments/2026-07-28-tracker-capacity-sweep/notes/19`.
- An appendix table with one row per campaign is deferred to a later pass.

### Statistics

- Prose carries the result. A statistic appears when the result escapes intuition and when the
  registry already computed one.
- Where a statistic appears it names its `n`, its test and its Holm status.
- A verdict is never restated from memory. It is read from the campaign record, and its
  corrected p-value is read from `borrador/claims.json`.

### Figures and visual evidence

- Figures come from committed code in `documento/figuras/`, following the existing decorator
  pattern: a module per chapter, one function per figure, decorated with the figure id.
- The shared style module is imported from `tesis/figuras/estilo.py`, 125 lines, which already
  rejects a PNG under 60000 bytes as a failed render. Importing it is a read, and the
  read-only rule on `tesis/` holds.
- PNG files are committed under `documento/figuras/`, contrary to the older rule that kept
  them out of git, because the author runs the style pass himself and a missing file breaks it.
- A finding that only a clip proves appears as a three-frame strip: before, event, after. The
  caption names the source clip so a reader with the repository can open it. A GIF is kept
  beside the clip for the markdown and web reading, and never used as the PDF evidence,
  because a PDF has no animation.

### Disclosure

- Chapter 4 carries a section on the agent-assisted method: what the agents did, what the
  author decided, and how the pre-registration rule kept the setup from being shaped by the
  result.
- The machine split is stated inline wherever it applies and again in chapter 12. The audit in
  `experiments/2026-07-21-machine-disclosure/` found that `README.md` claimed everything ran
  on the board while Part V ran its tracker on an RTX 3090.

### Deferred

- The central claim, and with it chapter 1 and chapter 13.
- The depth of chapter 3, which stays a stub carrying its four section headings and the three
  confirmed literature gaps from note 5 of the tracker sweep.
- Whether the metric definitions live in the glossary or in chapter 4.

## Testing Decisions

A document has no unit tests, and inventing a framework for it would be waste. What it has is
a set of properties a script can check, and the repository already holds prior art for exactly
this: `borrador/borrador/assemble.py` concatenates chapter files and supports `--check`, and
`tests/test_thesis_integrity.py` asserts it is not stale.

**One seam.** `documento/build.py` assembles and validates. `--check` exits non-zero and
changes nothing. Two make targets wrap it, `make doc` and `make doc-check`. One seam, not
four, because every property below reads the same assembled text.

What a good check is here: it tests a property of the output that a reader would notice, never
the wording. It never asserts a sentence exists.

Checks, in the order they earn their place:

1. **Staleness.** The committed `documento/tfm.md` equals a fresh assembly of
   `documento/capitulos/*.md`. Direct prior art in `assemble.py --check`.
2. **Footnote targets resolve.** Every campaign path cited in a footnote exists on disk. This
   is the check that rots fastest, because a campaign directory can be renamed.
3. **Referenced images exist.** Every image path in the assembled document resolves, and every
   PNG under `documento/figuras/` passes the blank-render size floor already encoded in
   `estilo.py`.
4. **Decimal point.** No number in prose or in a table uses a decimal comma. Code blocks, file
   paths and flags are exempt, because they are verbatim.
5. **Glossary coverage.** Every term declared in chapter 2 is used at least once outside it.
   This finds a glossary that has drifted ahead of the text. The reverse direction, every
   English term used being declared, is left out of the first pass, because it produces false
   positives on ordinary words and would need a stoplist nobody maintains.

Not checked, deliberately: page count, prose quality, citation correctness against the primary
source, and voice. A page count depends on the author's own style pass, and the rest are
judgements a script cannot make.

**A known red suite.** `tests/test_thesis_integrity.py` currently errors on every test. It
resolves `thesis/claims.json` and `thesis/borrador/assemble.py`, and that directory was renamed
to `borrador/`. `make borrador` and `make borrador-check` are broken for the same reason. This
is a stale path, not a lost invariant, and it is out of scope here. `documento/build.py` gets
its own test file so the new work is not blocked behind that repair.

## Out of Scope

- The 200 km/h steer, the September airframe choice, and everything in
  `borrador/SCOPE-2026-07-27-supervisor-steer.md`. The author excluded it.
- Any new experiment. The programme is closed.
- Rescuing, editing or deleting `borrador/` and `tesis/`. They stay on disk, unread.
- Repairing `tests/test_thesis_integrity.py` and the two broken make targets. Reported, not
  fixed here.
- The five unmerged branches. The author said to leave them alone.
- Pushing the 132 local commits that `main` holds and `origin/main` does not.
- A university template, a cover page, a declaration of authorship, and any style beyond plain
  markdown. The author applies those himself.
- An English abstract. Spanish only, for now.
- An appendix table of all 102 campaigns. Deferred to a later pass.

## Further Notes

The document has a reader the usual thesis does not: its own author, reading the project back.
That is why chapter 2 comes first and why every claim carries a footnote to its campaign. Both
choices cost pages and both pay for themselves in the author's reading time.

The tracker sweep corrects itself in public across its 28 notes. Note 12 overturns note 11,
note 22 overturns note 21, and notes 27 and 28 narrow the scope of notes 25 and 26. That chain
is evidence of method, and chapter 11 keeps it instead of reporting only the final table.

One claim needs care in chapter 11. The author's summary is that DAM4SAM is the best model the
project obtained. The campaign record supports a narrower sentence: DAM4SAM at 960 px is the
highest quality tracker measured on this board, and it wins on re-acquire after an occlusion
by +0.011 and +0.016 IoU at K = 60, both surviving Holm, but its advantage over the deployed
cropped operating point exists only at 960 px, costs 2.6x the latency, and disappears at 640 px
and 768 px. Chapter 11 states the narrow version.

The largest measured effects in that campaign change no model. A first-order hold on the
consumer of the boxes buys +0.069 median paired mIoU over 155 pairs at zero device cost, and
AsymTrack-B under pause buys up to +0.168 at 3.4x less cost. Whether that becomes the central
claim is one of the three open decisions.
