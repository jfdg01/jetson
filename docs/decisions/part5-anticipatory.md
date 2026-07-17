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
