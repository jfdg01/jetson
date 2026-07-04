# PART V PROPOSAL: anticipatory grounding / warm-start acquire (draft 2026-07-04T16:05Z)

Parked idea, not yet a Part. Origin: after the acquire-latency arc closed
(E18->E22, `experiments/HANDOFF-acquire-arc.md`), the operator reframed the whole
problem. This file records the reframe and the proposed first experiments so it is
not lost. Promote to a real Part V (with the three ledger scaffolds) only when work
actually starts.

## The reframe (operator's insight, 2026-07-04)

Part IV's entire acquire-latency arc assumed **frame 0 == prompt arrival**: the
prompt lands cold, a ~4.85 s blocking VLM acquire runs, and it lands STALE because
the target moved ~146 frames during it (E18). That assumption is FALSE for the real
use case. A drone is already flying; its video has been streaming to the operator
for **seconds** before the operator types anything. That pre-prompt window is **free
compute** -- the VLM slot sits idle between commands.

So the right problem is not "make the cold acquire faster" (E20-E22, all
capped/failed) but "make acquire WARM": use the idle pre-prompt stream to already
know what's on screen and where, so that when the operator speaks we **select**, not
acquire.

Why this is promising and not just another lever: E18's B-oracle (carry seeded
correctly and currently) was **6/6**. Carry is essentially perfect once seeded right
and fresh; the whole arc's failure was seeding under time pressure. Anticipatory
grounding seeds continuously -> the hypothesis is it approaches the 6/6 oracle
instead of E20's 3/6.

## Operator's proposed mechanism, and the one change to make

**Proposed:** a second VLM periodically describes the scene in text ("red car, left;
blue car, center"); at prompt time, ground the operator's phrase against that text
index.

**Problem with the text form:** "left / center / right" IS the 3x3 cell, and E20
proved the cell is not tight enough -- its residual FAILs were target-size bound
(arrival IoU ~0 at coverage 0.98+). A text index throws away the pixel box and hands
back exactly the coarseness that capped E20. It re-derives E20 with extra steps.

**The change: keep geometry, do not round-trip through prose.**
- The periodic pass emits **boxes + labels**, not prose -- a running candidate set
  with real coordinates.
- **SAM2 carries each candidate** (already co-resident at 6.15 Hz), so candidates are
  live locked tracks that are CURRENT at prompt time, not stale snapshots.
- At prompt time you **select**, not acquire: match the operator's phrase to the
  best existing track. No cold VLM pass, no staleness -- the box is already locked
  and already at "now."
- The language layer still matters, but only for phrase->track matching, riding on
  top of real boxes.

## Mechanism options (lazy-first)

1. **Reuse the one Qwen instance in idle time (laziest, no new model).** Between
   commands, periodically ask the EXISTING VLM for boxes+labels of salient objects;
   SAM2 carries them; bind on prompt. No new dependency, fits 8 GB because it is the
   same resident model doing multiple-choice in dead time. Pre-register this FIRST.
2. **Cheap always-on detector + VLM-as-selector.** A class-agnostic proposal net
   keeps candidate boxes continuously; the VLM is invoked ONCE at prompt time to pick
   which crop matches the phrase (multiple-choice over ~5 crops, not full-frame
   grounding). Stronger, but adds a detector -- probably Part V phase 2.
3. **Text index** -- keep only as the matching representation attached to option-1
   boxes, never as the primary output.

## Validation (the rig change that tests the whole reframe)

Extend the E18 replay to pick a **prompt-arrival time t_p > 0**. Warm-start machinery
runs over [0, t_p]; the prompt is issued at t_p; score the lock with the same E18
scorer. Same UAV123 clips, same metric -- the only new variable is "prompt does not
arrive at frame 0." One change, tests the entire premise.

## Cost caveat to check in Phase 0

Co-resident thermal/memory on the 8 GB board with a periodic extra VLM pass. Reusing
the single Qwen instance (option 1) sidesteps a second resident model, so it is
likely fine, but Phase 0 must measure it before the matrix.

## Relation to the closed acquire arc

The acquire arc concluded the operator hint (E20) is the only working sub-2s acquire,
and it stays [hint-fragile]. Anticipatory grounding sidesteps the hint entirely: if
we already track every salient object, the operator's phrase is a SELECTOR over warm
tracks, not a spatial prior for a cold crop. The two open acquire-arc levers
(M-margin ROI crop; convergence-scored lock) become moot if select-on-command works.

## Status / next action

Draft only. Before promoting to Part V: finish the final Part IV experiment
(E23 tolerant cells, `experiments/2026-07-04-tolerant-cells/`), then pre-register
Part V phase 0 (option 1 warm-start select-on-command) on a t_p>0 replay and add the
three `docs/{results,questions,decisions}/part5-*.md` scaffolds + root index rows.
