# DECISIONS — Part V (v5 Anticipatory grounding / warm-start acquire)

> Decision log for the warm-start / select-on-command reframe (v5). Index: [`../../DECISIONS.md`](../../DECISIONS.md).
> Per-experiment decisions also live in `experiments/<campaign>/README.md`. ★ = headline decision.
> **Append** — add each new decision at the bottom (chronological, oldest first; matches RESULTS/QUESTIONS).

---

<!-- append decisions below -->

### P5.1 — warm-start acquire (2026-07-04)

★ **Adopt warm-start (idle-window seed + select-on-command) as the Part V acquire path; retire the
cold blocking acquire for the mid-flight-prompt case.** P5.1 shows WARM 5/6 == ORACLE ceiling 5/6
vs COLD 1/6, and WARM==ORACLE with zero detection headroom lost. *Given up:* nothing on quality —
the real VLM seed matched GT; the cost is keeping a carry warm over the idle window (free compute,
the whole premise). *Why not push COLD harder:* Part IV (E18–E23) exhausted cold-acquire speedups;
warm-start sidesteps the ~4.5 s staleness entirely rather than shaving it.

- **Score the lock AT the prompt frame (t_p), not from t_lock over the whole clip.** This is what
  exposed car7's occlusion-at-prompt (E18-B's whole-clip coverage hid it). Keeps the metric honest
  about "is the target actually there when the operator asks?". *Given up:* comparability with the
  E18-B number — deliberate; the t_p-anchored metric is the point of Part V.
- **Froze t_p=8.0 s (single prompt time).** Simplifies the matrix and puts every clip in the
  `[ready-only]` regime (t_p > acquire). *Given up:* the early-prompt / cold-fallback regime
  (t_p < acquire) — a separate future experiment, not conflated here.
- **Single-salient-target clips only (selection is trivial).** P5.1 isolates seed-quality-at-t_p,
  not candidate disambiguation. The multi-candidate phrase-selector (twin-distractor) is the next
  experiment, kept out to avoid confounding the warm-vs-cold result.

### P5.2 — warm-start generalization + on-screen-speed sweep (2026-07-04)

★ **Reframe the warm-start mechanism: the win is delivery-lag removal, not motion-compensation.**
RQ-P5.2b measured the WARM−COLD gap vs on-screen speed and found it **flat** (Spearman ρ=−0.06;
gap large in every speed bin, slow +0.42 / med +0.76 / fast +0.62). The Part V premise assumed cold
staleness scales with target motion during the ~4.5 s acquire; it does not — COLD's ~135-frame
*delivery* lag sinks it broadly regardless of speed. *Consequence for Part V direction:* future
warm-start work should target seed quality and the early-prompt (t_p < acquire) fallback, NOT a
speed-adaptive acquire — there is no speed axis to adapt to. *Given up:* the speed-sweep thesis
figure as a positive result; kept as a clean documented negative (a wrong estimate is content).

- **Data-driven clip selection from GT (`profiles.py`), not eyeballed.** On-screen speed = median
  centroid displacement in %frame-diagonal/s, computed over consecutive valid GT frames; bins are
  the eligible-set tertiles. Makes the speed axis measured and reproducible. *Given up:* nothing —
  the alternative (hand-picking "fast-looking" clips) would have confounded the RQ-P5.2b axis.
- **Restrict to the 36 whole UAV123 sequences with their own frame dir; drop group/uav (segments)
  and truck/bird (no ≥700-frame clip).** The replay rig zips `sorted(*.jpg)` with anno 1:1 and
  cannot resolve frame-offset segments. *Given up:* two categories and the segment clips —
  a real dataset constraint, recorded not worked around; 5 categories still clears the ≥4 bar.
- **n=1 (P5.1 was bit-identical across reps).** Greedy decode + deterministic rig; n=2 bought
  nothing on P5.1's 36 legs. *Given up:* stochastic-variance measurement — none exists here.
- **Keep the 2 `[deliver-occluded]` clips (car7, person10) in the /25 denominator.** They fail
  `genuine_lock` on all legs (GT absent at deliver frame), so they are structural not detection
  misses; kept for P5.1 comparability and reported flagged with window coverage. *Given up:* a
  flattering 21/23; the honest denominator is /25 = 21/25, with the /23=91% stated alongside.

### P5.3 — multi-candidate select-on-command (2026-07-14)

★ **Late-binding IoU-match chosen over crop-scoring for the first select test — and the FAIL now
promotes crop-scoring to the next deep-research target.** P5.3 selected candidates by firing the
deployed phrase-grounding VLM on the prompt frame and matching its (stale) box by IoU to the
carried candidate boxes, then delivering the matched track's live box. *Why chosen:* it reuses only
deployed, already-validated components (the Part II RefDrone-fine-tuned VLM is a referring-expression
model by lineage; the IoU match is `replay_source.iou` + existing carry) — no new method, no new
citation, runnable immediately. *Rejected:* CLIP crop-text similarity / VLM multiple-choice over the
candidate crops — lower-latency and they score the *carried candidates directly* (no free-frame
grounding), but neither is grounded in repo code or cited work, so each needs a deep-research cycle
first. *Outcome / consequence:* P5.3 FAILED on the match mechanism (NO_MATCH 4/7 non-passes — the
VLM's prompt-frame box misses both carried candidates), exactly the pre-registered trigger to
promote the crop-scoring family. *Given up (for now):* sub-acquire-latency selection; the next
Part V select experiment should be a deep-research cycle on crop-scoring, landing SOURCES citations
before designing.

- **Oracle-seeded 2-candidate set (target = GT[f0], distractor = hand box), enumeration out of
  scope.** Candidate *discovery/maintenance* over the idle window is charter backlog item 2; P5.3
  isolates the *select* stage given a known candidate set, justified by P5.1/P5.2 where WARM matched
  ORACLE. *Given up:* end-to-end realism — but it cleanly separates "can the phrase pick the right
  carried track" from "can we find the candidates", so the NO_MATCH finding is unambiguously a
  grounding-accuracy result, not a seeding artifact.
- **Car scenes only; person/K>2 dropped.** The downloaded UAV123 person subset has no ≥8 s
  co-visible same-class distractor pair (person13/person20 ~5-6 s); K>2 is future work. *Given up:*
  category breadth for the select test — recorded as a negative curation result, not worked around.
- **Same-frame delivery for all legs (WSEL/SWAP/CSEL all deliver at prompt+acquire).** Differs from
  P5.1's earlier warm delivery — deliberately removes the delivery-lag advantage so P5.3 measures
  *only* the late-binding select claim (delivery-lag removal already proven in P5.1/P5.2). *Given
  up:* showing warm's full end-to-end win again; kept the experiment a clean single-variable test.

### P5.4 — ROI-constrained select-on-command (2026-07-14)

- **ROI-constrained late-binding select over CLIP crop-scoring as the gating mechanism.** P5.3
  pre-registered CLIP crop-scoring as the next deep-research target; a deep-research cycle was run
  this cycle (ReCLIP IPS, red-circle visual prompting -> SOURCES) and then a design-time pilot
  *falsified* CLIP as a gate on 16-100 px aerial crops: vanilla IPS is size-biased (picked the
  larger silver target for "the black car" at 0.963) and the best of 5 variants (circlectx, red
  ellipse + 2.5x context, ViT-L/14) reached only 5/6 with near-tie margins. *Chosen instead:*
  reuse the deployed Part III ROI-crop lever (validated, +22.6pp, ~2.0s) to constrain *where the
  VLM looks*, keeping the P5.3 IoU-match unchanged. *Given up:* pre-registering a verdict on CLIP
  crop-scoring — demoted to a recorded non-gating secondary arm (`clip_select`, 7/10) so the
  crop-scoring question is settled as documented evidence, not a burned cycle on a predictable FAIL.
- **In-run outcome: the ROI pivot is a latency win but not a select win.** Post-hoc, the ROI crop
  cut acquire ~2.3x (2.08s) but left the VSEL verdict at 3/5 (identical to P5.3). The two select
  failures survive cropping — an in-crop third object (NO_MATCH by construction of the union window)
  and a sub-resolution target the upscale can't rescue. *Recorded for the next cycle:* cropping to
  the candidate union does not fix grounding when a distractor sits *between* the carries; the next
  lever must either (a) crop per-candidate (single-carry windows, disambiguating by which crop the
  phrase scores highest — closer to the falsified CLIP arm but with the ROI upscale) or (b) accept
  the VLM grounding ceiling and change the contract. Do NOT re-propose union-crop select.

### P5.5 — Maintained-candidate select-on-command (2026-07-14)

- **Fuse idle-window maintenance (loop-focus dir 2) with unique captions over a maintenance-only
  t_p sweep.** The P5.5 audit re-diagnosed P5.3's "match-bound" fails as 2 distractor-carry-drift cells
  + 2 caption cells + 1 resolution cell; a maintenance-only sweep could not touch the caption cells, so
  both levers were tested in one matrix with an M attribution arm. *Given up:* a clean t_p (4/8/16/30s)
  sweep — deferred because scene-set expansion was data-starved (an exhaustive UAV123 contact-sheet
  survey, committed under `curation/`, found exactly one extra clean co-visible same-class pair,
  car9:560), so a speed/idle-length sweep had too few scenes to be meaningful.
- **Accept-without-IoU-floor re-anchor rule; distractor-only maintenance.** The idle ROI re-anchor
  reseeds the SAM2 carry with no IoU floor vs the prior box (a drifted carry must not veto its own fix);
  the GT-oracle-seeded target carry is never re-anchored (single-factor discipline — target carries
  never drifted in P5.1/P5.3/P5.4). *Given up:* symmetric maintenance and a drift-guard on the reseed —
  both would confound the single-lever read.
- **In-run outcome: maintenance helps but does not clear the bar; the caption lever is falsified.**
  Post-hoc, re-anchor fired/accepted (`[True, True]`) in all 16 cells and flipped WSEL 3/5 -> 4/5,
  SWAP 2/5 -> 3/5, yet two SWAP carries (car10:240, car7:460) still fail carry-drift NO_MATCH after two
  accepted re-anchors, and M == MC proves captions bought nothing. *Recorded for the next cycle:* the
  select bottleneck is the carried-box vs full-frame-VLM-box agreement at the prompt — three levers
  (P5.3 match, P5.4 crop, P5.5 maintenance+caption) have now failed to clear >= 4/5 on both legs. Do NOT
  re-propose caption rewriting or union-crop select as a select-fix. The remaining untested direction is
  changing the delivery contract (deliver the carried track directly, bypassing the prompt-time
  full-frame re-grounding) rather than trying to make the VLM re-ground onto the carry.

### P5.7 — Simulator scene-generator capability gate (2026-07-17)

- **Stopped the matrix after two fresh-session failures on the first run, instead of continuing with
  B/C/D.** The pre-registered abort rule (INVALID -> re-run once with a fresh server -> fails again ->
  record `infra` FAIL and stop) was applied literally. Continuing was tempting — three more runs might
  have produced a completing clip — but the failure is a **per-call** flake (~0.42%/call, ESTIMATE
  n=2): each further run had ~13% odds of finishing, so B/C/D would most likely have burned ~12 min to
  produce three more INVALID dirs and no gate reading. *Given up:* any G1/G2/G3/G5 measurement this
  cycle, and the planned A-vs-D G4a pair. *Bought:* an early, cheap, correctly-diagnosed stop, plus
  the salvage below.
- **Root-caused the failure rather than reporting "flaky sim", but did NOT fix it.** The evidence
  (server alive at both crashes, identical `RecvSrvRequest() ... Host unreachable` in both server logs,
  two *different* services hit, crash ~5 s after the last frame = the CLI's 5000 ms timeout) locates the
  fault in per-frame `gz service` CLI subprocess churn (~480 ephemeral transport nodes per run), not in
  the scene, the render path, or a service handler. Fixing it (persistent transport node / batched
  stepping / retry-on-timeout) is a **design change and Fable's call** — the executor role is to run the
  matrix, not redesign it, so it is flagged with the diagnosis attached and left unimplemented. *Given
  up:* a same-day green matrix. *Bought:* the next cycle starts from a named cause and a decision, not a
  re-run of an unrunnable matrix.
- **Killed the gz server by process group, not by the pid file — applies to every future sim campaign.**
  The pre-registered `kill $(cat gz_$RUN.pid)` kills only the `nohup` **bash wrapper**; the real server
  is its ruby child (verified: wrapper 28988 -> server 28991, shared PGID), which survives as an orphan.
  That would silently break the "fresh server session per run" property G4a's cross-session claim rests
  on, and the stale server keeps answering on the camera topic, so the next run would *look* fine. Used
  `kill -- -<pgid>` + verified `pgrep -af select_arena` empty before each launch. Relatedly, step 0's
  `pkill -f "gz sim"` self-matches under this harness (the launching shell's own command line contains
  the string) and can kill its own wrapper — matched on `select_arena.sdf` instead. Mechanism only; no
  design or code was changed.
- **Left `make_proof.py` untouched and added `make_proof_infra.py` for the negative result.** The
  pre-registered proof script requires all 4 runs' `results.json` + overlays and cannot run; it stays
  valid for the post-fix re-run, so editing it to limp through a failed matrix would have destroyed a
  working asset. *Given up:* the pre-registered deliverable list (overlay grid / determinism / clip).
  *Bought:* the deliverables that match what actually happened, from the artifacts that do exist.
- **Recorded the cross-session determinism probe as NON-GATING, despite it being the cycle's best
  news.** 108/108 byte-identical frames across two fresh sessions (mean |diff| = 0.000000 vs a 2.0
  gate) answers the pre-registered open risk favourably, but the runs are INVALID, no finalize ran, the
  GT half of G4a is uncheckable and it covers 108/240 frames — so it is documented as a probe and
  explicitly **not** a G4a pass, in the README, the figure title, and the ledgers. *Given up:* claiming
  a gate. *Bought:* the claim stays true if the post-fix run disagrees.

### P5.8 — Scene-generator transport fix (persistent requester) (2026-07-17)

- **Persistent gz-transport requester node over CLI + retry-on-timeout** (design decision, Fable;
  vindicated by the run). P5.7's per-frame `gz service` CLI calls spawned ~480 ephemeral transport
  nodes/run and died twice inside ~240 calls with the server alive. The fix replaces them with **one
  persistent pybind requester `Node` in a dedicated no-subscriber `proxy` child process** (JSON-lines
  over pipes, auto-restart on hang). *Rationale:* under the cumulative-degradation reading of the
  P5.7 data (two suspiciously-similar times-to-failure, ~254 and ~216 calls, which a memoryless
  0.42%/call model fits poorly), retrying through *more* ephemeral nodes attacks the symptom while
  feeding the cause; eliminating the churn attacks the cause. *Given up:* nothing — retry was kept as
  a safety net (below). *Bought:* completion 0/2 -> **4/4 at 240/240**, throughput 1.48 -> **8.34 fps
  (5.6x)**, and **0 failures across 1920 gating calls**. The result also **falsifies the memoryless
  model** (which predicted <13% chance any single run finishes) and supports the cumulative-degradation
  amendment — worth carrying into any future gz-transport work: **do not put ephemeral service nodes
  in a per-frame loop.**
- **Reply-lost-aware step retry, with G1 as the double-step tripwire** (design decision, Fable;
  never exercised). `set_pose_vector`/`create` are idempotent and retry x3; `world control` is **not**
  — a lost *reply* is not an unexecuted step, so the layer waits `RESPONSE_LOST_WAIT_S` = 3 s for the
  frame before re-issuing, and counts `response_lost` separately. *Rationale:* a blind step retry
  would silently double-advance sim time and corrupt GT. The tripwire is G1's exact-40 ms stamp check
  — a double-step shows an 80 ms jump and fails the run rather than passing quietly. *Given up:* up to
  3 s of latency per lost reply. *Bought:* a safety net that cannot corrupt the clip it protects.
  **Actual: it never fired** (retries 0, lost 0, restarts 0 on all 4 runs) — the primary fix was
  sufficient, and the net's cost was zero.
- **`killserver` process-group scan replacing the pid-file teardown** (design decision, Fable;
  load-bearing for G4a). P5.7's `nohup ... & echo $!` recorded the **bash wrapper** PID, not the real
  (ruby child) server — killing it **orphaned a live server that still answered on the topic**,
  silently faking the fresh session that G4a's cross-session claim rests on; `pkill -f "gz sim"`
  self-matches its own launching shell. `killserver` scans /proc, kills by process group, excludes
  itself/ancestors/own group, and **verifies `remaining: 0`**. *Given up:* the convenience of a pid
  file. *Bought:* G4a means what it says. **Actual: all 4 teardowns printed `remaining: 0`** (pgids
  42448 / 42828 / 43255 / 43678), so every run genuinely had a fresh session — without which the
  byte-identical G4a result would be unfalsifiable.
- **Executor call: recorded V as PASS-with-caveat for seed101_A/D rather than a V FAIL.** The blue
  distractor spawns near the median kerb (lat y = 0.596) and clips into it, rendering by f0180 as two
  disconnected blue blobs with the mid-body sunk below the kerb surface. *Why not FAIL:* the
  pre-registered V FAIL list is box floating off / lagging / wildly mis-sized, one car, same-coloured
  cars, or a dead feed — none hold; the box bounds the full 3D model and tracks the car, so the defect
  is **scene geometry, not GT projection**, and G2 passes (pur1 = 0.472 vs a 0.30 gate). *Why not a
  silent pass:* it is a real defect — **a half-sunk distractor is not a fair grounding target** — so it
  is recorded in the README, both ledgers, and the proof-grid caption, and flagged as fix-before-use.
  *Given up:* a clean binary. *Bought:* the caveat survives into the next cycle instead of being
  rounded away. (V did not decide this verdict — the matrix is NO on G4b regardless.)
- **Executor call: diagnosed G4b as mis-calibrated but did NOT change the threshold, the seeds, or any
  code.** The gate failed at 0.216 m < 1.0 m, and the diagnosis is quantitative: GT reproduces
  `author_scenario()` exactly (not a transport artefact), target f0 spreads ~8 m x 7 m over 120 seeds
  (the generator diversifies), yet only **74.6% of 2000 random 3-seed triples pass** (median
  min-pairwise 1.52 m, p10 0.59 m) — with 3 seeds there are 3 pairs, so near-collisions are a birthday
  effect and **G4b has a ~25% false-failure rate on an arbitrary triple**; {101, 202, 303} landed in
  it. *Rationale:* re-picking seeds or widening the threshold after seeing the result is exactly the
  post-hoc move pre-registration exists to prevent — the executor runs the matrix and reports, the
  designer rules on gate definitions. *Given up:* a YES this cycle that would have been unearned.
  *Bought:* the verdict stays honest, and the next cycle gets a measured false-failure rate to design
  against (widen target spawn / pre-screen the triple / measure trajectory divergence rather than a
  single f0 point) instead of a hunch.

### P5.9 — kerb-safe scene bank (2026-07-17)

★ **Ship the redefined G4b (whole-scenario divergence ≥ 1.0 m) and retire the old min-pairwise
target-f0-distance statistic** — designer's ruling (Fable), executed and empirically corroborated
this cycle. The run gave decisive independent evidence: under the OLD statistic the 15-seed bank
scores **0.135 m** (pair 1,12) — it would have *failed the retired 1.0 m gate outright* — while the
NEW statistic scores 1.36 m. Seeds 1 and 12 place their targets 13.5 cm apart at f0 yet diverge 1.36
m over the whole scenario: the single-frame coincidence between otherwise-diverging trajectories that
the old point-stat false-failed on (measured 25% false-failure rate, P5.8). *Given up:* sensitivity
to two seeds coinciding at one instant. *Bought:* a gate that measures "is this a generator, not a
replayer" directly, plus a faithfulness cross-check (recorded GT reproduces `author_scenario` within
1e-3 m, True over all 16 runs). Honesty note carried from pre-reg: the redefinition retroactively
flips P5.8's failing gate — disclosed, deliberate, grounded in third-party-checkable measurement.

- **Executor call: report the old G4b statistic as a non-gating diagnostic rather than suppress it.**
  0.135 m is an eye-catching number that superficially reads as "the bank is not diverse". Kept it in
  Results because it is the strongest available evidence *for* the redefinition once you look at the
  scenario-wide divergence — hiding it would be the dishonest move. *Given up:* a cleaner-looking
  ledger. *Bought:* the reviewer can check the redefinition's premise against a real number.
- **G6 (rendered-integrity gate) adopted as a standing gate for the scene generator** — this cycle
  its first live run: 16/16 PASS, min p10 0.9967 (margin +0.047), 0 cells in the [0.95,0.99) watch
  band, and it separates cleanly from the P5.8 clip (0.666). It caught the P5.8 defect class by
  construction (p10 + tail, not median — the clip's median was 0.999). *Given up:* nothing measurable;
  it adds one per-frame connected-component computation. *Bought:* the anti-clipping regression is now
  mechanical, not eyes-only. V still gates (it is the whole point of the arc), but G6 now backs it.
- **No V-vs-G6 disagreement to reconcile, and no code touched.** The executor ran the matrix as
  written, opened all 28 required overlays, and confirmed V and G6 agree. The one finding worth a note
  — the marginal p10 migrated from the blue distractor (P5.8) to the white target (self-occlusion, not
  clipping) — is recorded, not acted on. *Rationale:* executor runs and reports; design changes are
  the designer's call. The bank is declared usable for the parked P5.6 select experiment next cycle.

### P5.10 — select on the scene bank (2026-07-17)

- **A/B-on-bank chosen over running the parked P5.6 verbatim on UAV123, and over hardening the bank
  first.** The SIMULATOR steer directs building on the just-delivered P5.9 sim; the paired A/B on
  n=12 with exact dual per-frame GT is strictly stronger evidence than P5.6's n=5 with one
  hand-annotated distractor frame, and only the sim A/B can answer the scene-bound-vs-contract-bound
  attribution question that P5.3/4/5's three NOs left open. *Given up:* a direct real-video
  measurement this cycle (P5.6 stays the designated follow-up, `experiment/direct-delivery-select`).
  *Bought:* controlled attribution — carries, VLM and scenes no longer vary together. **Outcome
  note:** the A/B could not separate the contracts because bank v1 is too easy (both at ceiling); the
  attribution it *did* deliver is that the old RG contract is not scene-murk-proof-fragile on clean
  attribute scenes, so the P5.3/4/5 NOs are scene-bound — which is exactly the question the cycle
  existed to answer, even though RQ-b came back NO.
- **Dominance delivery rule (IoU_named ≥ 0.25 AND IoU_named > IoU_other) over the strict P5.6-shape
  variant (IoU_other < 0.25).** Robust to any GT-GT overlap; on this bank GT-GT IoU = 0.000 so the
  two coincide and both were recorded (strict_ok true on all 24). *Given up:* nothing on this bank.
  *Bought:* a rule that stays correct if a future bank v2 introduces crossings/occlusion.
- **t_p = 3.0 s (prompt f75) forced by clip length.** The bank is 240 frames at 25 fps = 9.6 s; P5.6's
  8 s idle window does not fit. *Given up:* long-idle carry-drift stress (the P5.5 surviving failure
  mode is under-exercised at 3 s) — recorded as a bank-v2 trigger. *Bought:* the experiment fits the
  delivered dataset without recalibrating the kerb-safe corridor (which caps clip length).
- **Idle ROI re-anchor maintenance dropped, keeping each cell single-factor.** With a 3 s window the
  P5.6 maintenance offsets (+3 s/+5.5 s) have no room to act; dropping it makes the *contract* the
  only difference between the DD and RG legs. *Given up:* any maintenance benefit (none available at
  3 s). *Bought:* a clean single-factor A/B.
- **Executor note (no code touched):** ran the matrix as written, opened the 16 required sample
  overlays, confirmed V PASS and no V-vs-script disagreement. The pre-registered sim-gap NO_BOX sweep
  did not fire (VLM grounded all 24 Gazebo renders) — reported faithfully as the valid branch-2
  result, not treated as a bug; no prompts or code were tweaked to "fix" it. sam2_model recorded from
  results.json as `sam2.1-hiera-tiny` (the method text's `sam2-hiera-small` is a doc mismatch, not
  re-run). Matrix wall ~2.75 min vs the 15–35 min estimate (warm Jetson, 4.37 s/call).

### P5.11 — bank v2 designed-crossing build gate (2026-07-17)

- **Reported NO faithfully rather than nudge the failing gates to pass (executor discipline).** The
  mechanical verdict came back NO on G4b (seed diversity 0.77 m < 1.0) and 3/12 bank cells (G6c
  n_clear<60 ×7, G8b bdom<0.55 ×3). No code, threshold, or scene param was touched to lift the
  count. *Given up:* a passing v2 bank this cycle. *Bought:* an honest calibration signal — the
  gates were byte-frozen with the pre-reg specifically so the executor cannot tune them, and the
  right response to "the population doesn't match the single-probe calibration" is a new
  pre-registration, not a same-cycle tweak.
- **Diagnosed the NO as integrity-threshold-bound, not render-bound, via the mandatory visual gate.**
  Opened all 12 crossing-peak overlays + 3 post-prompt + 2 gate mid-run + the montage with the Read
  tool: every crossing is a genuine designed occlusion (blue occluder in front of intact white,
  overlapping GT boxes), G9=12/12, zero render defects. So the failing cells are *valid occlusions
  the gates reject*, not defects the gates caught. This flips the follow-up from "fix the generator"
  to "recalibrate the gates to the seed population + add a seed-diversity constraint to the offline
  screen + re-derive G8b for shallow-occlusion seeds." *Given up:* nothing. *Bought:* the next
  pre-reg targets the real cause instead of re-authoring a working scene generator.
- **Executor note (no code touched):** ran the 16-run matrix exactly as pre-registered (`--profile
  v2` on every record, one fresh gz server per run, killserver remaining:0 before+after each),
  0 INFRA / 0 INCOMPLETE / 0 reruns, 13.6 min wall. Did not merge, push, or touch main. The
  pre-registered P5.12 v2-discrimination A/B is blocked until a v2.1 bank passes this gate.

### P5.12 — bank v2.1 recalibrated build gate (2026-07-19)

- **Kept bank05 (seed 6, bdom 0.488) and bank06 (seed 14) in the bank despite them being visibly
  the two weakest occlusions.** Both pass every pre-registered gate; the visual gate confirmed both
  are genuine occlusions (white's lower body hidden behind blue, contiguous bodies, correct z-order)
  rather than defects. **Why:** the pre-registration's binding rule is that *no threshold may move
  during or after the run* — and dropping a gate-passing, visually-confirmed cell because the
  operator judged it "weak" is the same threshold-fitting the campaign was designed to avoid, just
  applied by eye instead of by number. The gate is the authority; the eye can only downgrade a
  *defect*, and there was none. **Given up:** the bank carries two cells with below-average
  occlusion stress and a fragmented occlusion window. Recorded explicitly in the README and the
  ledgers so that if P5.13's contracts fail to separate, these two cells are the first place to
  look — rather than the finding being silently absorbed into a "the bank was fine" claim.
- **`make_proof.py`'s stale `p511_*` output filenames: logged by the executor, fixed at audit.** The
  three proof PNGs are P5.12 content (titles and data correct) but were written as
  `p511_occlusion_montage.png` etc., because the script is a retarget of P5.11's. **Why the executor
  left it:** the executor role does not modify committed core code mid-campaign, and a rename mid-run
  would break the pre-registered reproducibility chain from `runs/*/results.json` to the committed
  figures. **Why the orchestrator then fixed it before merging:** P5.11's `proof/` contains three
  PNGs with byte-identical names, so a thesis citation of `p511_occlusion_montage.png` is ambiguous
  between two campaigns with opposite verdicts (3/12 vs 12/12). Renamed to `p512_*` with the script
  and all ledger references updated; figure content unchanged. **Given up:** nothing material — the
  division of labour held (executor logged rather than silently patched), which is what made the
  wart visible at audit. Documented rather than silently fixed, so the
  discrepancy is on the record instead of being a future reader's puzzle.

### P5.13 — v2 discrimination A/B: DD vs RG on the bank v2.1 crossing bank (2026-07-19)

- **Replaced P5.10's directional margin `DD_total >= RG_total + 4` with a symmetric
  `|DD_total - RG_total| >= 4`.** **Why:** P5.10's threshold could only fire if direct delivery won,
  which was the experimenter's expectation at the time. P5.13's own pre-registered prediction ran the
  *opposite* way (RG > DD, because DD must carry identity through the designed crossing while RG sees
  a clean scene at f150), and a threshold that can only fire in the expected direction is not a test —
  it is a confirmation. The magnitude (4 of 24) was carried forward unchanged from the P5.11 and P5.12
  pre-registrations specifically so that the bar was not being moved at the same time as its shape.
  **Given up:** a directional threshold would have been marginally more sensitive to the one
  hypothesis actually under test; the symmetric version spends that sensitivity on being falsifiable
  in both directions. In the event this mattered less than expected — the observed margin was 1, far
  from either edge — but the prediction *was* wrong (DD went 24/24), which is exactly the case the
  symmetric form was chosen to cover.
- **Moved the prompt frame from P5.10's f75 (t=3.0 s) to f150 (t=6.0 s).** **Why:** bank v2.1's
  crossings peak between f56 and f94, so f75 lands *inside* the occlusion window. Grading both
  contracts mid-occlusion would make a null uninterpretable — a contract failure would be
  indistinguishable from "we asked at the worst possible moment". f150 is after every crossing and
  every clip is separated by then (GT-GT IoU <= 0.084), which is the intended design: **the carry must
  survive the crossing, the VLM sees a clean scene.** **Given up:** the overrun ceiling tightens from
  6.56 s to 5.96 s, and `cov_*` window shrinks 165 -> 150 frames so raw coverage `n` is not comparable
  to P5.10's (compare `frac_lock` only). Both consequences were pre-registered as non-bugs; neither
  bit (measured acquire 4.34-4.38 s, no `OVERRUN`).
- **Kept `select_p513.py` a forward copy of the byte-frozen `select_p510.py` with only four
  constants changed** (`N_FRAMES` 240->300, prompt 3.0 s/f75 -> 6.0 s/f150, bank path, and the
  mechanical selfcheck/preflight literals). No new fail classes, no new scoring rules. **Why:** so a
  P5.13-vs-P5.10 delta is attributable to the bank and the prompt frame and *not* to the grader. This
  is what makes "P5.10 got 24/24 vs 24/24, P5.13 got 24/24 vs 23/24" a comparable pair of numbers
  rather than two unrelated runs. **Given up:** the chance to fix things noticed since P5.10 —
  notably that `DELIVERY_DRIFT` charges a mid-carry mask leak to the RG contract purely because RG
  delivers 109 frames later than DD. That asymmetry is real, it produced the run's only failure
  (`bank09_white`), and it is recorded rather than patched mid-campaign.
- **Did not widen the bank before running.** **Why:** n=12 is what P5.12 validated, and the
  pre-registration names in advance which explanations to check if the contracts fail to separate;
  adding clips before knowing which explanation holds is guessing. **Given up:** statistical power. In
  the event the result was not power-limited — DD had *zero* fails of 24, which no plausible sample
  size rescues into a separation.
- **Branch-3 explanations honoured as pre-registered, with no third one added.** Branch 3 fired, and
  the two named explanations were checked in the frozen order: (i) crossing-peak uniformity +
  constant z-order (white is the nearer car in 0/300 frames in every clip — the bank never renders
  the target in front), then (ii) bank05/bank06's weaker occlusion stress. The evidence points at (i)
  and not (ii), because the two weakest-crossing clips passed identically to the strongest.
  **Why this is a decision and not just a result:** the temptation at a null is to invent a better
  post-hoc story, and the P5.12 audit pre-committed against exactly that. **Given up:** any
  post-hoc explanation that might be true but was not named in advance — it can be proposed as a new
  pre-registration, not as a reading of this run.

## P5.14 — realvid-dd-select

- **Overrode the standing "harden the bank to v2" steer and unparked P5.6 on real UAV123.**
  **Why:** the steer deferred P5.6 "unless the audit overrides", and the picked direction had been
  executed to completion — bank v2.1 built and validated (P5.12 YES), the discrimination A/B run on
  it (P5.13) — returning a second consecutive DD==RG ceiling tie (24/24 vs 24/24 on v1, then 24/24
  vs 23/24 on v2.1 with the single discordant cell attributable to carry decay, not contract). Four
  cycles of scene-data work had produced no contract separation, while the separation already
  existed in *recorded* real-video results (RG measured WSEL 3–4/5, SWAP 2–3/5 on these exact
  scenes in P5.3/P5.5). **Given up:** the sim arc's momentum, and the chance that a third bank
  would finally separate the contracts. **Vindicated in the event:** the shadow re-ground
  disagreed with DD on 4/12 real-video cells — the separation the banks could not manufacture.
  **R-5 qualifier (2026-07-21):** the separation is one-sided by construction (DD's caption binding
  cannot mis-select), so what the move actually bought was a *measurable failure rate for the
  re-ground contract on real imagery*, which is still exactly what the sim banks could not produce.
- **Rejected bank v3 (the competing candidate) this cycle, but pre-named its mandatory gates.**
  **Why:** a third bank cycle needed re-authored trajectories and a recalibrated kerb-safe corridor
  — a multi-session build before any contract evidence arrives — with a demonstrated risk of a third
  ceiling tie, since SAM2 and the fine-tuned VLM are simply strong on clean 25 fps renders.
  **Given up:** the controlled, GT-for-free setting that a sim provides. **Carried forward as
  binding on any future sim-bank pre-registration** (so they cannot be reinvented post-hoc): a
  **minimum post-prompt target displacement** gate over the delivery window (P5.13's delivery lag
  was free because the target moved <16 px in 109 frames), **z-order variation** (in bank v2.1 the
  target was the nearer car in 0/300 frames of every clip), and **crossing-peak diversity**.
- **Imported the parked P5.6 rig byte-unchanged rather than rewriting it, and kept its frozen
  thresholds.** **Why:** the bar (WSEL >= 4/5, SWAP >= 4/5 strengthened) was pre-registered
  2026-07-14, four campaigns before the sim results that motivated unparking; re-authoring the rig
  or re-deriving the thresholds now would make the YES unfalsifiable — "the bar moved after we saw
  the data" is the exact criticism a positive result invites. **Given up:** tidier code and the
  `p56` lineage labels leaking into P5.14 output (`verdict_p56.py` prints `RQ-P5.6a/b`); the
  provenance section documents the equivalence instead of renaming. **Only new code:**
  `dump_frames_p514.py`, which closes the rig's pre-"Look at it" gap (it wrote only `overlay.mp4`,
  which the Read tool cannot open).
- **Kept the strengthened SWAP rule even though it is harder than every historical bar.**
  **Why:** the old off-target-only rule passes any box that misses the target, including one on
  empty road — it would have scored `car7:460` a pass on a junk carry. Reporting the weak rule as a
  non-gating diagnostic (6/6 weak vs 5/6 strong) makes the flattery visible instead of inheriting
  it. **Given up:** comparability with the historical SWAP numbers at face value; the pass grid
  carries an explicit note that the DD row is scored under the stricter rule.
- **Did not rescue the marginal cell or rerun anything.** `car9:560` SWAP passed at 0.2843 against a
  0.25 floor and `car7:460` failed outright; both stand as first-scored, per the pre-registered
  "never rerun a scored cell" rule. **Why:** n=1 deterministic replay, and a rerun after seeing the
  margin is selection. **Given up:** a tighter estimate of where the carry sits on that cell —
  recorded instead as the named risk that a small carry regression flips a second cell.

## P5.15 — carry-horizon (2026-07-19)

- **Measured carry survival instead of re-running the DD select at a long idle.** **Why:** the
  competing candidate (P5.14's WSEL/SWAP legs at t_p = 16/24 s) was rejected *by looking* at the
  actual prompt frames: two cells exceed their clip length (`car7:460` needs f1240 of 1033,
  `car10:615@24s` f1635 of 1405), and in the rest the hand-annotated distractor has left the FOV
  or is no longer re-identifiable by 16–24 s. **Finding worth carrying forward: UAV123's
  two-candidate geometry dissolves within ~16 s** — long-idle *select* cannot be tested honestly
  on this dataset, but long-idle *carry* can, since every clip has per-frame GT for its single
  target. **Given up:** a direct long-idle test of the winning P5.14 contract.
- **Kept the P5.5 re-anchor accept rule verbatim (no IoU floor) even though it lost clips.**
  **Why:** the arm is a controlled test of the *deployed* lever; adding a floor mid-run would
  measure a lever that does not exist and would have hidden the identity-swap failure mode.
  **Given up:** a flattering MAINT number. What we got instead is the first evidence that the
  deployed lever is a liability past ~8 s of idle, which is a deployment-relevant negative.
- **Did not gate on RQ-b despite MAINT losing.** **Why:** the ceiling rule (PLAIN@24s >= 22 ->
  N/A) was frozen before the run precisely so a lever could not be scored on a saturated
  baseline; it fired, so the MAINT result is reported as a non-gating diagnostic. **Given up:**
  claiming a measured "re-anchor harms" verdict at gating strength — it needs its own
  pre-registration on a set where PLAIN is not saturated.
- **Carry-health gate should key on box area, not colour.** **Why:** over 150 horizon points
  `area_ratio` separates alive from dead (median 1.039 vs 0.163) while `hist_corr` is flat
  (0.742 both) and is undefined when the box vanishes. **Given up:** the appearance-similarity
  health signal, which several earlier proposals assumed would work.

### P5.16 — autodisc-select (2026-07-19T15:03Z)

- **Attacked the seed oracle rather than the P5.15 re-anchor finding or a third sim bank.**
  **Why:** P5.14's first select YES seeded both carries from ground truth (target from
  `gt[f0]`, distractor from a hand box) — the largest unearned assumption in the Part V
  headline — and P5.15 had just shown the carry survives 24 s idle unmaintained, so a seed
  planted early in the idle window would still be alive at the prompt. **Given up:** (a) a
  carry-health-gate / IoU-floored re-anchor fix for P5.15's identity-swap finding — low
  leverage, the mechanism is already measured and the unmaintained carry needs no maintenance
  at these horizons; (b) sim bank v3 with z-order/displacement gates — third rejection of the
  sim fork, since two banks in a row tied the contracts (P5.10, P5.13) while real video
  separated them for free (P5.14). The bank-v3 gates stay carried forward, unexecuted.
- **Changed exactly one factor (seed provenance) and imported everything else byte-identical.**
  **Why:** the whole value of the run is attributing any delta to the oracle; re-tuning
  delivery, captions or maintenance at the same time would have made a 1-cell flip
  uninterpretable. **Given up:** obvious co-improvements (e.g. a retry budget, an identity
  constraint on re-anchor) that would have made the numbers look better without being
  attributable.
- **Kept caption→candidate binding as string equality on the two known phrases.** **Why:**
  free-phrase binding is a separate factor and mixing it in would confound the seed-provenance
  question. **Given up:** testing the operator-facing language surface; that is now the natural
  next cycle, and `car7:460` says referring-expression *disambiguation* is where it will bite.
- **Discovery accept rule uses no ground truth at all** — parseable + in-frame + IoU < 0.5 vs
  the other carry (a distinctness guard), with rejection requeuing the caption at the back and
  an in-flight-at-prompt call discarded. **Why:** any GT-derived accept test would smuggle the
  oracle back in through the side door and invalidate the experiment. **Given up:** the ability
  to reject a wrong-object discovery — which is precisely how `car7:460` failed, and that
  failure is the honest cost of the rule.

### P5.17 bankv3-select (2026-07-20)

- **Built a third sim bank (v3) rather than accepting the P5.13 tie at face value.** **Why:**
  the P5.13 audit had a specific, testable explanation for the tie — the post-crossing segment
  was near-static, so the target moved <16 px over the 109-frame delivery lag and RG's lag was
  *free*. That is a bank defect, not a finding, and closing the sim fork without fixing it
  would have been closing it on a confound. **Given up:** ~44 min of wall-clock and one loop
  cycle that could have gone to a real-video lever. **Verdict on the decision:** worth it — the
  tie reproduced at n = 56 with the defect provably removed (median ZOH IoU 0.08 vs 0.79), so
  the close-out is now attributable instead of confounded.
- **Pre-registered a health floor and four exhaustive interpretation branches before the run.**
  **Why:** a tie is only informative if "tie with both arms healthy" (branch 3, close the fork)
  is distinguished up front from "tie because the stack failed on both" (branch 4, diagnose the
  stack) — deciding that after seeing 56/56 vs 55/56 would be post-hoc. **Given up:** the
  freedom to reinterpret a surprising result; branch 3 fired as written and was applied
  verbatim.
- **Closed the sim fork for select questions; kept the bank for stack questions.** **Why:**
  three banks in a row tie the delivery contracts while real UAV123 video separated them for
  free (P5.14), and the mechanism is now visible — RG's VLM grounds the named car on 56/56
  clean renders but disagreed on 4/12 real frames, so what DD actually buys is immunity to
  *real-imagery* grounding fragility, which a clean render cannot exhibit by construction.
  **Given up:** the deterministic, GT-exact, cheap-to-scale test-bed for every future select
  lever; those must now be paid for in real-video annotation. The generator, its offline screen
  and the 28 pinned seeds stay committed and reusable for carry/mask/tracker questions.
- **Charged the one `s103` renderer stall to the pre-registered infra rule (retry once with a
  fresh server) instead of the INFRA budget.** **Why:** the rule was written before the run
  precisely for this known gz-transport flake; consuming budget for a first retry would have
  made the >3 INFRA allowance unreachable in practice. **Given up:** nothing measurable — the
  retry produced a clip that passes all 10 build gates and G4a determinism.

## P5.18 — n25-select (2026-07-20)

- **Re-powered the existing P5.16 claim instead of testing a new lever.** **Why:** P5.14/P5.16
  are the load-bearing Part V select YESes and both gated on n=5 per leg, which the standing
  sample-size rule calls an anecdote; a claim that cannot survive its own re-measurement is not
  thesis-grade, and the pipeline was frozen byte-identical so the scene set is the single factor.
  **Given up:** a cycle's GPU time that could have tested a new lever — and the answer was that
  the SWAP half of the claim does not survive, which retroactively justifies the spend.
  **Vindicated:** the rule caught a real 0.80 -> 0.65 optimism gap on its first application.
- **Ran the GT-free (P5.16) variant rather than the GT-seeded (P5.14) one.** **Why:** P5.16
  showed the seed oracle is worth ~1 cell in 12, and the GT-free pipeline is the deployable one,
  so it is the one worth powering. **Given up:** direct comparability with P5.14's exact numbers.
- **Kept the SWAP failure as a select failure rather than re-scoping the leg.** **Why:** 3 of the
  5 SWAP-only failures are late-entry discovery — the distractor is not in frame when the idle
  window opens — and it is tempting to call those "out of scope" and re-gate on scenes where both
  candidates are present at discovery. That would be scoring the pipeline on the scenes it
  happens to win. Late entry is the *normal* case for an operator who names an object that flies
  into view; excluding it would make the metric describe a world the drone does not fly in.
  **Given up:** a verdict that would have read YES. Recorded as the honest NO instead.
- **Retained SWAP person20:1050 as a pass despite a loose delivered box.** **Why:** the
  pre-registered downgrade condition was specific ("a green box *centred on the woman*"); the box
  fully encloses the backpack man and its centre falls inside his hand box, it is merely loose
  enough to absorb an adjacent overlapping pedestrian. Downgrading on a rule the cell does not
  meet would be as much a scoring error as missing one. **Given up:** nothing — the cell does not
  change the branch (SWAP 16/26 would also be a NO); the looseness is recorded as a caveat.
- **Named the residual carry weakness as imagery-specific, not category-general.** **Why:** all
  four WSEL failures are cars and non-car WSEL is 16/16 — the failing clips are small
  low-contrast sedans on shadow-banded palm roads, where SAM2 has least appearance signal.
  **Given up:** the simpler "carry is getting weaker at longer idle" story, which the data does
  not support (bike1, person and wakeboard all hold at the same idle window).

### P5.19 late-entry-rescue (2026-07-20)

- **Fixed the named P5.18 mechanism (late-entry discovery integrity) rather than the larger
  carry-drift family.** **Why:** the misaligned guard was a *provable harness bug* with a visually
  confirmed recovery ceiling (+4), near-zero predicted regression risk, and a clean paired design
  at n=26 in ~30 min. Fixing it first also *decontaminates* the carry-drift measurement, since
  wrong-seed cells were being charged to the drift bucket. **Given up:** a cycle spent on
  mechanism (b), the bigger family (8 of 13 leg-failures) — deferred, and now cleanly isolated.
- **Bundled grace with aligned dedup instead of shipping dedup alone.** **Why:** schedule
  arithmetic predetermined dedup-only to a NO — the 13 s idle window fits only 2 completed VLM
  slots, so any post-reject retry is still in flight at the prompt and P5.16 discards it. Dedup
  alone converts wrong deliveries into honest `discovery-failed`: same FAIL count, better buckets,
  no recovery. Grace is what makes the RQ live, and both patches are the same mechanism (late-entry
  discovery integrity), so the A/B stays single-factor. **Given up:** the cleaner one-patch
  attribution — mitigated by per-flip mechanism attribution in `verdict.json` (2 grace, 1 dedup).
- **Counted the two wrong grace deliveries as FAIL and reported grace precision as 2/4.** **Why:**
  the strengthened SWAP rule already scores them FAIL on the geometry, but the *interesting* fact
  is not the count — it is that a wrong grace produces a tight, high-IoU box on the wrong object
  (0.865, 0.679) rather than abstaining. In deployment there is no GT to catch that, so it is a
  silent failure, and reporting only "SWAP 20/26, +3" would have hidden it. **Given up:** a
  cleaner-looking YES narrative.
- **Reported the non-gating control regression (car3:200 PASS -> FAIL) prominently.** **Why:** it
  falsifies an explicit pre-registered estimate ("regression floor ~0"), and a control cell
  regressing is precisely what a reader needs to weigh a result that lands exactly on its bar.
  **Given up:** nothing — it is non-gating and does not move the branch.
- **Retained SWAP person20:1050 as a pass despite a loose delivered box** (consistent with the
  identical P5.18 call). **Why:** the box is on the named distractor and off the target, which is
  the pre-registered rule; it merely merges an adjacent overlapping pedestrian. Downgrading on a
  rule the cell meets would be a scoring error. **Given up:** nothing — recorded as a caveat.
- **Named the aligned guard's own limitation rather than claiming the fix is complete.** **Why:**
  the guard compares the VLM box against *carried* boxes, not GT; the pre-registration's +4 ceiling
  used a GT proxy. When the carry has already drifted, an aligned guard still sees no overlap and
  admits the duplicate (`bike1:450`). So dedup quality is bounded by carry quality. **Given up:**
  the tidier claim that discovery integrity is now solved — it is bounded by the same constraint
  that owns the residual failures.

## P5.20 carry-capacity (2026-07-20)

- **Probed carry *capacity* first, ahead of ROI-zoom carry, a higher carry rate, and an
  area-ratio abstain gate.** **Why:** P5.19 left carry quality owning 8 of the 10 residual
  failures, and a checkpoint swap is the only one of the four that is a genuine single-factor A/B
  with zero new code — it either removes "just use a bigger tracker" from the board or hands back
  a lever for free. The other three each need new machinery, and running them first would leave
  the cheap null untested underneath. **Given up:** a cycle that could have produced a positive
  result; the ROI-zoom carry lever is now the standing next candidate, unblocked by this NO.
- **Bought replication in the same run rather than as a separate cycle.** **Why:** P5.19 cleared
  its bar *exactly* (SWAP 20/26 vs bar 20), which is indistinguishable from a lucky roll without a
  re-run — and any capacity result read against a baseline that might itself be noise would be
  uninterpretable. Making the baseline arm a full re-run of P5.19's config gave both answers for
  one matrix. It paid: 0 cell-level flips. **Given up:** ~26 min of GPU (free — it fit inside the
  1 h target) and the option of spending arm T on a third checkpoint.
- **Rejected `hiera-base-plus` / `hiera-large` as the capacity arm.** **Why:** neither can be
  co-resident with the q8_0 VLM on an 8 GB Orin Nano, so a YES on either would be undeployable and
  therefore not thesis content for this system. `hiera-small` is the largest checkpoint that could
  actually ship. **Given up:** the chance that capacity helps only at a much larger size — but
  that finding would be unusable here anyway, and the observed *regression* direction argues
  against it.
- **Pre-registered a MIN_SEP of +3 and honoured it at delta -1 without re-reading the threshold.**
  **Why:** a paired 52-cell A/B has real cell-level noise (the arms differ by tiny IoU jitter on
  identical failures); a delta of -1 is inside that noise and must be reported as
  *indistinguishable*, not as "capacity hurts". Hence branch 3 with **no** `[capacity-hurts]`
  sub-tag, even though the sole flip was a regression. **Given up:** a more dramatic headline that
  the data does not support.
- **Reported the single flip as a regression, prominently, despite it being 1 cell of 52.**
  **Why:** it is the only place capacity changed anything, and the mechanism is informative —
  hiera-small's mask **bloated** across two vehicles (iou_d 0.9714 -> 0.2314) on a small aerial
  target. A reader deciding whether to revisit capacity later needs to know the one observed
  effect pointed the wrong way. **Given up:** nothing; it is charged symmetrically by the paired
  design.
- **Retained `S/DSC_SWAP_person20_1050` as a pass despite a looser box than T's** (iou_d 0.3293 vs
  0.6412), consistent with the identical P5.18/P5.19 calls. **Why:** the box is on the named
  distractor and off the target, which is the frozen IoU@0.25 rule; it merely leaks onto an
  adjacent pedestrian. Downgrading a cell that meets the rule — in the direction that would make
  the capacity arm look worse — would be a scoring error even though it disfavours the hypothesis.
  **Given up:** nothing; recorded as an audited caveat.
- **Deferred the TensorRT/co-residency question rather than answering it.** **Why:** the
  pre-registration made deployment of hiera-small contingent on a follow-up E1-style export + FPS
  gate. Gate a failed, so that work is correctly never done — but the record must say the capacity
  arm was evaluated **only** for accuracy under equal-stride emulation, not for on-device
  feasibility. **Given up:** an on-device number for hiera-small, which no longer has a use.

### R-36 / REG — powered select negative + grounding isolation (pre-registered 2026-07-23T23:05Z)

Records: `experiments/2026-07-23-r36-maintain-vs-select/README.md`,
`experiments/2026-07-23-reg-grounding-isolation/README.md`. Part of the closed-loop significance
slate (`experiments/PART6-PROGRAM-warm-start-significance.md`).

- ★ **R-36 becomes a PAIRED maintain-vs-select McNemar, superseding the original single-arm SWAP
  rate.** **Why:** the thesis defends *maintain beats select*, not "select fails" in isolation — the
  paired WSEL-vs-SWAP contrast is the claim that matters and is strictly more powerful (McNemar on
  discordant pairs vs a one-sample proportion against 0.8). **Given up:** the simpler single-arm
  design named in the REMEDIATION R-36 stub. **Recorded because** it changes what number the chapter
  reports, so the change is a decision, not a detail.
- **R-36's reachability is disclosed up front, not discovered post-run.** The committed 13-clip SWAP
  data is b=3, c=0, p=0.25 — three discordant pairs short of the six McNemar needs, so R-36 requires
  >=12 NEW distinct SWAP-hard clips and is over-provisioned to n~30 (projected b~7, marginal). **The
  miss branch is pre-registered:** b<6 or two-directional -> "select fails but is not
  separable-from-maintain at this n." **Why recorded:** so a tie is read as the powered ceiling of a
  known negative, never as a gate chosen after seeing p (the P5.3/P5.4/P5.5 unreachable-gate scar).
- **REG is declared a DEPENDENT decomposition of R-36, inside the same Part-V Holm family — not
  independent confirmation.** **Why:** REG re-grounds the same clips/frames R-36 uses; treating it
  as a second independent test would spend alpha twice on correlated data (multiplicity p-hacking).
  **Given up:** the appearance of a second confirming result. **Kept:** an honest attribution of
  whether the residual select failure is a grounding asymmetry or lives downstream — piloted first,
  because P5.18's 0.65 distractor rate is end-to-end and confounded.

### P5.21 — ROI-carry lever tested as an outcome (pre-registered 2026-07-23T23:05Z)

Record: `experiments/2026-07-23-p521-roi-carry/README.md`.

- **The ROI-crop re-anchor is finally tested as plain-vs-ROI carry *survival*, not prefill cost.**
  **Why:** the lever was adopted on a per-frame-IoU / prefill-cost argument (ROI-crop overnight,
  2026-06-26) and never as a paired outcome; with bigger-SAM2 dead (P5.20), it is the last
  non-capacity carry lever and deserves a powered verdict. **Pilot-gated (headroom check before the
  gate is locked)** so it does not repeat the construction trap. **Given up:** nothing — a tie is
  the measured negative that closes the lever, still content.
