# 2026-07-21 — Machine disclosure audit (R-1)

**Status:** COMPLETE 2026-07-21T18:05Z. Deliverable of remediation task **R-1** in
`thesis/REMEDIATION.md`. Unblocks **R-2** (`machine` field on all 65 claims), and
feeds **R-6**, **R-7**, **R-8**, **R-14**, **R-16**, **R-17**, **R-19**.

**What this is:** a documentation audit, not a measurement campaign. It answers one
question for all 76 experiment campaigns in `experiments/` — *which machine produced
each number, and does the campaign's own README say so?* — and then decides what, if
anything, has to be re-measured on the Jetson.

**Why it exists.** `README.md` says «Todo corre en la placa, sin nube». Part V ran its
tracker on an RTX 3090. Both facts are defensible; the gap between them was not
written down anywhere, which meant every downstream correction was guesswork about
what the claim even was.

**No pre-registration.** The per-experiment workflow requires the README before the
run, to stop the setup being shaped by the result. That protects measurements. This
campaign measures nothing — it reads files that were already frozen — so there is no
outcome to bias and nothing a pre-registration would have protected. Recorded here
rather than silently skipped.

---

## Method

A 5-agent parallel sweep over `experiments/`, one agent per Part-group, each reading
every campaign README plus, where the README was silent, the run scripts, `raw/`
artifacts and `runs/*.json` in that directory. Every row carries the quoted string it
was derived from.

- Driver: `Workflow` tool, run `wf_3704ea46-89b`, 5/5 agents, 0 errors, 98 tool calls,
  323,782 subagent tokens, ~237 s wall.
- Machine: RTX 3090 workstation (reading files; no compute measured).
- Raw result: `raw/machine-audit.json` — 76 rows, `{campaign, part, vlm_machine,
  other_compute_machine, evidence, confidence, note}`.
- Tables below are generated from that JSON by `make_tables.py`, so a later correction
  to one row cannot drift out of step with the view.

`confidence` grades **the README, not the truth**:

| Value | Meaning |
|---|---|
| `stated` | the campaign names its own host |
| `inferred` | the host is only reachable via code, a sibling doc, or an inheritance chain (« byte-identical to E19 ») |
| `unknown` | nothing in the campaign tree says |

Coverage: **61 stated, 9 inferred, 6 unknown**. VLM host: 47 Jetson, 7 both, 5 3090,
15 n/a (no VLM in the campaign), 2 unclear.

---

## Verdict on the two claims R-1 asked about

### A. «The deployed system runs on-device» — TRUE, confirmed, no port needed

The deployed stack is the VLM anchor plus the SAM2 carry, co-resident on the Orin.
E1 (`experiments/2026-07-02-carry-trt-export/`) measured exactly that:

> `| TRT encoder | 768 | 6.15 (p50 162.5) | **6.15** (p50 162.4, RAM 4980/7607) | 2a max-diff 3.1e-04, 2b mask IoU 1.000; on-device IoU@0.25 **1.000** / mean 0.826 | **PASS** |`

Co-resident with the VLM, 4980 MB of 7607 MB, mask parity 1.000 against the eager
reference. Part II Phase 4 separately scored the deployed Q8_0 GGUF on the Jetson
(62.6% IoU@0.25) and Part III T4 ran the anchor+carry loop on it. The claim stands as
written; it needed confirmation, and it has it.

**Caveat, and it is not small — see finding M1.** «Runs on-device» is confirmed *at
the operating point E1 measured*, which is image_size 768. It is **not** confirmed at
the 1024 that every Part IV/V campaign actually ran.

### B. «Every experiment ran on-device» — FALSE, and it should not be true

29 of 76 campaigns had no VLM on the Jetson: 15 have no VLM at all (SITL, renderer,
scene-generation and offline-CV work), 5 ran the VLM on the 3090 as a fidelity
reference, 7 split legs across both, 2 are unclear. Running an ablation on a
workstation is ordinary practice and often the *correct* choice — Part II Phase 0 used
HF bf16 on the 3090 precisely because it is the fidelity reference the quantised
on-device path is measured against.

The defect was never «work happened on the 3090». It is that **9 campaigns leave the
host inferable-only and 6 leave it unstated**, and that the rollups
(`README.md`, and the standing config line in `2026-07-14-autoresearch-run` that every
child cycle inherited) assert a single-machine reading the per-campaign records do not
support.

The concentration is not where it would be natural to guess, and
`proof/disclosure-by-part.png` is what corrected the first draft of this paragraph:
**Part I is 9/9 stated** — the device-benchmark campaigns name their board and power
mode because naming them was the point. The defect is instead in **Part III (4 of 11
`unknown`)**, where the work moved to SITL and kinematics and nobody wrote down a host
for code that ran no VLM, and in **Part IV (7 of 27 `inferred`)**, where the rig was
inherited by reference — «byte-identical to E19» — and the reference chain never
terminates in a machine.

Part II is a third pattern rather than a defect: 3 of its 5 campaigns ran the VLM on
the 3090 *on purpose*, because HF bf16 is the fidelity reference the quantised
on-device path is scored against.

The late Part V records are *good*: `2026-07-20-n25-select` echoes the measured
`nvpmodel -q` output back into its Results section, which is the strongest disclosure
form in the repo.

---

## Findings, ranked

### M1 — The emulated carry stride is optimistic, and its provenance is miscited *(new; load-bearing)*

Every rate-capped campaign from E18 onward runs SAM2 on the 3090 throttled to
**6.15 Hz**, described as «E1's measured co-resident TensorRT number on the Orin». The
throttle is a sound idea — emulate the device budget rather than confound the result
with a new on-device harness — but the number does not belong to the configuration it
is being applied to:

1. E1 measured 6.15 FPS at **image_size 768**, under `++model.image_size=768`.
2. E1 explicitly did **not** measure 1024, and said so: *«OP=1024 (768/640 acc FAIL) |
   full branch | ≥5 FPS @1024 (needs 1.9× — encoder must be ≥~2.5× faster)»*. Step 6
   was skipped because 768 cleared the gate.
3. Part IV/V carries run at **1024** — `SAM2VideoPredictor.from_pretrained(MODEL)` with
   no `image_size` override (`discover_p516.py:330`), i.e. the stock SAM2.1 1024, and
   the READMEs say «SAM2.1-hiera-tiny @1024» outright.
4. E18's own disclosure miscites the source resolution as *«6.15 FPS measured at
   640x480»*. 640 was a size E1 tested and rejected on accuracy; it is not where 6.15
   came from. Neither cited resolution is the one that ran.

**Consequence.** The emulation hands the carry more frames than the Orin would deliver
at that resolution. By E1's own arithmetic, 1024 needs ~1.9× the compute of 768, so the
true on-device stride is plausibly ~3 Hz — roughly half the emulated one. Direction of
the bias is knowable and uniform: **carry-dependent PASSes are optimistic, carry-
dependent FAILs are conservative.**

**The sharper way to say it: the deployed configuration and the evaluated
configuration are different sizes, and each borrowed the favourable half of the
other's measurement.** 768 is the *fast* size and 1024 the *accurate* one — and the
gap is real, not a rounding artefact: the statistical re-analysis
(`P3-carry-OP768-accuracy`) finds 1024 beats 768 on 55 tracks to 31 with 100 ties,
exact p = 0.014, so «768 is within 5 pp of 1024» was an effect-size bar and never a
claim of equality. E1 deployed 768 and measured its speed. Part IV/V evaluated 1024
and inherited 768's speed. Neither box ever ran the accurate size at a measured rate.

**Disposition: fold into the existing R-16**, do not open a new task. R-16 (SAM2
co-residency characterisation) was already scoped to measure what the co-resident
carry actually costs on 8 GB at 15 W, and already carries a sibling finding — that the
two-candidate `/2` assumption is optimistic by ~7% (2.87 Hz, not 3.075). M1 adds the
resolution axis it was missing: **the gate must run at image_size 1024, not 768**, or
it re-measures the wrong configuration a second time. E1's harness exists
(`export_encoder.py` + `jetson_trt_acc.py`). Until it runs, no carry-dependent PASS may
be described as an on-device *rate*.

### M2 — Part I Stage 3's −23 pp parity number confounds hardware with runtime

The result that motivated the entire Part II rebuild (HF 85% vs GGUF F16 62%, «bf16 →
llama.cpp runtime») subtracts a Jetson measurement from a 3090 one. The Jetson leg also
ran at *«15 W (default, not locked)»* — no `jetson_clocks`, unlike every other Jetson
campaign in the repo. The config table says «not the Jetson», which reads as a
3090-only campaign; the Jetson arms surface only in `train-log.md`.

**Disposition: MARK SUPERSEDED, do not re-measure.** Part II Phase 4 redid this
comparison properly and disclosed it (−2.7 pp HF bf16 → GGUF F16), and that is the
number Part II actually rests on. The −23 pp stays in the record with a superseding
note; an erased wrong number is worse than a corrected one. Feeds **R-7**.

### M3 — Part II Phase 2 chose the deployment resolution off-device with no rig line at all

`2026-06-17-phase2-resolution` has **no rig, host or power line anywhere**. The machine
is inferable only from `source .venv-ft/bin/activate` and «**Backend:** `HFBackend`
(bf16, the fidelity reference)». This is the sweep whose 4.1% → 38.7% ladder chose
`max_side=1024` as the **deployment** resolution — an off-device, off-runtime
measurement propagating straight into a shipped constant.

**Disposition: re-measure — already scheduled.** This is what **R-14** (ROI on-device
Q8_0 re-run) is for; R-14 is hereby scoped to include the resolution ladder, not just
ROI. Add the missing rig line under R-7 regardless.

**Disposition update (2026-07-21T20:21Z): DONE.** R-14 ran both arms in one Orin Q8_0
llama-server session on the deployed `phase3-terse100eos-1024` checkpoint —
`experiments/2026-07-21-roi-ondevice/`. Arm A (full-frame @1024) reproduced the published
63.10% on-device control **exactly**; arm B (ROI M=2.0 @512) landed 85.19%; paired McNemar
p=2.5e-14 deflated to 316 images. The registry gains
`P3-ROI-M2.0-512-ondevice` with `machine: jetson-orin-nano-8gb`, and it is the **fourth**
wholly-on-device claim (added to the ratchet in `tests/test_thesis_integrity.py`). This is a
genuine Orin end-to-end assignment: both arms are the Orin's own Q8_0 output, no 3090 arm is
subtracted. The cross-machine composite that this section flagged is now retired for the ROI
headline — the number is measured, not assembled.

**Fifth on-device claim (2026-07-22T22:40Z, R-13).** `P3-R13-owlv2-vs-vlm` is also assigned
`machine: jetson-orin-nano-8gb` and added to the ratchet. Both halves are the Orin's own
output: OWLv2 fp16 ran on the board (`experiments/2026-07-21-detector-baseline/`, 1317
forward passes, peak 415 MB) and the VLM comparator is R-14 arm A, itself measured on the
board in the session above and reused unchanged rather than re-run. **The runtimes differ** —
OWLv2 via transformers/PyTorch, the VLM via llama.cpp Q8_0 — so the *accuracy* comparison is
clean (same items, same `contract.py` path, same machine) while the 16.4x *latency* ratio
crosses two engines and is recorded in the claim's caveats as a system-level observation, not
a controlled efficiency measurement. That distinction is exactly the composite defect this
section exists to catch, so it is stated in the registry rather than left to the reader.

**Sixth on-device claim (2026-07-23T01:20Z, R-16).** `P4-R16-carry-rate-1024` is assigned
`machine: jetson-orin-nano-8gb` and added to the ratchet. This one is the least ambiguous of
the six: **there is no other machine in it to disclose.** Both halves are the board's own —
SAM2 2.1-hiera-tiny stepping on the Orin's iGPU and the deployed
`phase3-terse100eos-1024-q8_0` llama-server resident in the same 8 GB, contending for it.
The whole point of the campaign is the contention, which cannot be measured anywhere else
and cannot be assembled from two separate measurements; the OOM cell in particular exists
only on a machine where both halves are real at once.

The reason it belongs in this section anyway is the inverse defect. R-16 exists because
`CARRY_HZ = 6.15` — an honestly-measured *on-device* number from E1 — was reused across every
Part IV/V replay as though it described the deployed system, when it had been measured at
`image_size` 768 with a TensorRT encoder that the deployed stack does not use. So a claim can
carry the right machine label and still be a composite: **the machine is not the only thing a
number inherits from its measurement.** Configuration is the other one, and this ledger had no
column for it. The 2.30x correction is what that gap cost. Any future audit of this kind should
ask not only "which machine" but "which configuration, and is it the deployed one".

### M4 — P5.2, the flagship Part V generalization number, is an undisclosed composite

`2026-07-04-warm-start-generalization` (W 21/25 vs COLD 5/25). **The string «3090» does
not appear anywhere in the campaign**, yet the tracker half ran there. Its headline
line — «SAM2.1-tiny TRT fp16, mask gate app_tau 12.0, Jetson 15 W + jetson_clocks» —
reads as one on-device configuration. The host is reachable only by following «Reuses
the P5.1 rig unchanged» into P5.1.

Same shape, one or two inheritance hops deep: `2026-07-04-prompt-scoped-acquire` (E20),
`2026-07-04-coarse-to-fine-acquire` (E21, two hops), `2026-07-04-tolerant-cells` (E23).

**Disposition: disclose, do not re-measure** (see the re-measurement decision below).
Feeds **R-7**.

### M5 — `2026-07-02-follow-speed-ceiling`'s rig line is factually wrong

The README says the Jetson acquire was *«not booted»* and the run used a «local-VLM
path». There is no local-VLM code path in `phase3_sitl.py` at any revision; at the E2
commit (`646d5b9`) it unconditionally constructs `JetsonBackend(..., ssh_host="jetson")`
and prints «[3] booting Jetson q8_0 server…». `runs/speed-1.0/results.json` records
`n_acquire_attempts: 32`, so inference did run — on the Jetson. The campaign also has
no log in `raw/` or `runs/` (only `results.json` + `trial.csv`), so the rig is
unauditable from artifacts.

This is the only *wrong* machine statement found, as opposed to a missing one.
**Disposition: already tracked as R-17** («Fix the E2–E4 rig prose»), which found the
same contradiction from the code side and notes the prose is wrong *in our own
disfavour*. This audit adds the artifact-side confirmation (`n_acquire_attempts: 32`)
and the separate observation that the campaign has no log in `raw/` at all. The 2.5 m/s
follow ceiling itself is a 3090-carry SITL number, unaffected by which box ran the
anchor.

### M6 — `2026-07-20-p61-carla-renderer` describes a measurement that never ran

Its restriction line reads «the perception model is exercised on the 3090», but no
perception model ran: G6 is recorded **NOT RUN** in the results table and again in the
closing summary. A reader comes away believing a 3090-side VLM measurement exists.
Disclosure is otherwise strong here («Any latency figure from this campaign is
therefore a **3090 figure and is not a deployment number**»).

**Disposition:** one-line text correction under **R-7**. Same class as M5 and R-17:
prose asserting a leg the code or the results table contradicts.

### M7 — `2026-07-21-carla-gt-bank` has no README at all

Only `proof/`, an empty `raw/`, and `runs/`. No machine, no power mode, no config, no
date. The only evidence is indirect: `runs/night.log` invokes `runners/carla_gt_bank.py`
and logs «power limit 200.0 W» — a desktop-GPU knob, not an `nvpmodel` mode. No VLM ran.
The one total disclosure gap in the set.

**Disposition:** already tracked as **R-8** (merge or retire `experiment/carla-gt-bank`).
Retiring it also retires this gap.

### M8 — Part III T1/T2/T3 and `roi-shrink-spiral` name no host

Four `unknown` rows. Three of them (T1, T2, T3) ran no VLM and no pixels — T3's
97.6%/71.5% oracle-coverage headline is a workstation-side kinematic simulation with
«Gazebo + VLM + dual-branch baggage irrelevant» — so the missing host is a hygiene
defect, not a validity one. `2026-06-27-roi-shrink-spiral` is the exception worth
noting: it shipped `ROI_MIN_CROP=384` into the deploy path validated only by offline
self-checks, and says so («offline self-checks pass; on-device replay not yet run»).

**Disposition:** add rig lines under **R-7**. `ROI_MIN_CROP` gets covered by R-14's
on-device re-run.

### M9 — Incidental: a stale status line

`2026-07-17-bankv2-crossing` still reads «**Status:** PRE-REGISTERED, not yet run»
above a completed 2026-07-17T18:31Z run with a recorded NO verdict.
**Disposition:** **R-19** (stale-verdict sweep).

---

## The re-measurement decision

**Nothing in Part V is re-run on the Jetson, except that the carry cap itself gets
measured, one axis wider, under the existing R-16.** The rationale, because a decision without it is not documented:

**What the split actually is.** In every rate-capped Part IV/V campaign the VLM anchor
— the thing under test, and the thing that dominates the latency the arc is about — ran
on the Jetson at 15 W with `jetson_clocks`, over real SSH, with the real round trip in
the measured time. The 3090 half is SAM2 mask propagation and the replay harness. So
the headline latencies (~4.85 s cold acquire, 0.37–0.60 s grace delivery) are real
on-device wall time and do not need re-measuring.

**Why the emulation is faithful in kind.** The carry that ran on the 3090 is the same
model, the same weights, the same input frames as the one on the Orin. E1 verified that
the on-device TensorRT fp16 encoder produces masks at **IoU 1.000** parity with the
eager reference (max-diff 3.1e-04). So porting the carry on-device would not change
*which* masks come out — only *when*. That is precisely and only what the rate cap
emulates, which is why the emulation is validated rather than merely asserted.

**Where that argument stops, and it does stop.** It holds only if the emulated stride
matches the device stride. M1 shows it may be ~2× too fast at 1024. So:

- Every select verdict (P5.1–P5.20) keeps its accuracy interpretation, since mask
  identity is machine-invariant here.
- No carry-dependent PASS may be stated as an on-device *rate* until R-16 lands.
- R-16 is cheap and decisive. Re-running the twenty Part V campaigns on-device is
  neither: it would consume weeks of Orin time to re-derive numbers whose only
  machine-sensitive component is a single scalar that one gate can measure directly.

**The one arm that provably cannot run on the Jetson** is P5.20's `sam2.1-hiera-small`
(46M). Its campaign pre-registers that honestly, including that the 6.15 Hz budget «was
measured for *tiny*». Its verdict was **NO** — capacity is a dead lever — and the
direction of the bias is adverse to the arm: on-device it would run *slower*, so the NO
can only harden. **No re-measure**; the NO stands, with the caveat already in place.

Summary of dispositions:

| Action | Items |
|---|---|
| Re-measure on-device | **R-16** (existing, +1 axis): co-resident carry FPS at image_size **1024**, not 768. **R-14** (existing, rescoped): ROI + resolution ladder on-device Q8_0. |
| Mark superseded | M2 — Stage 3's −23 pp parity result. |
| Disclose / correct text only | M3 (missing rig line), M4 (P5.2 + 3 inheritance-chain campaigns), M6 (unrun measurement described), M8 (4 missing rig lines) — all under **R-7**. |
| Correct the rollup | **R-6** — `README.md`'s «Todo corre en la placa, sin nube». |
| Already tracked | M5 = **R-17**. M7 = **R-8**. M9 = **R-19**. |

---

## Per-Part machine table

Generated by `make_tables.py` from `raw/machine-audit.json`. «VLM ran on» is where
grounding inference executed; «none» means the campaign ran no VLM. Bold marks a
disclosure defect.

<!-- BEGIN GENERATED TABLES -->

### Part I — exploratory (device benchmarks + first fine-tune)

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-06-13-llamacpp-upper-bound` | Jetson | x86_64 workstation (ssh driver + parsers only); llama.cpp built and run on-device | stated |
| `2026-06-13-model-capability-sweep` | Jetson | x86_64 workstation (ssh driver + parsers.py timing parse); all 10 model runs on-device | stated |
| `2026-06-14-gemma-family-sweep` | Jetson | x86_64 workstation (ssh orchestration only); all G1-G5 arms on-device | stated |
| `2026-06-14-stage1-baseline` | Jetson | local x86_64 (Gazebo Harmonic renderer, ArduCopter/ArduRover SITL, ByteTrack, cascade PID,… | stated |
| `2026-06-14-vlm-feasibility` | Jetson | local Python urllib client driving the on-device `llama-server`; no other compute | stated |
| `2026-06-15-stage2-finetune` | both | rtx-3090 (LoRA fine-tune + in-loop eval); Phase C re-run's Gazebo/SITL on local x86_64 | stated |
| `2026-06-15-toy-demo` | Jetson | local x86_64 running `runners/demo_nlcommand.py` (NL parse, TURN heuristic, setpoint… | stated |
| `2026-06-16-stage3-refcoco-finetune` | both | rtx-3090 (LoRA training 50k samples + HF bf16 in-loop/probe eval); GGUF conversion via… | stated |
| `2026-06-17-stage4-refdrone-curriculum` | 3090 | rtx-3090 (curriculum LoRA train ~1 h + in-loop n=200 eval) | stated |

### Part II — v2 principled rebuild

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-06-17-phase0-backend-fidelity` | 3090 | rtx-3090 (HF bf16 arms) + the same box's CPU running a local `llama-server` for every GGUF arm | stated |
| `2026-06-17-phase1-dataset-audit` | none | local workstation CPU in `.venv-ft` (host not named); pure annotation statistics, no model… | stated |
| `2026-06-17-phase2-resolution` | 3090 | rtx-3090 (same box; `HFBackend` sweep is the only compute) | **inferred** |
| `2026-06-17-phase3-train` | 3090 | rtx-3090 (LoRA train ~1.8 h + authoritative n=439 full-val eval via `--eval-only`) | stated |
| `2026-06-18-phase4-export-deploy` | both | local 3090 box for the HF bf16 reference (carried from Phase 3) and the… | stated |

### Part II/III boundary

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-06-25-terse-output-retrain` | both | rtx-3090 (LoRA re-train + GGUF export, `.venv-ft`); jetson-orin-nano-8gb (Q8_0 val n=439 +… | stated |

### Part III — v3 object permanence

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-06-18-part3-charter` | none | none — planning document, nothing executed | stated |
| `2026-06-18-t0-cadence` | Jetson | rtx-3090 (ByteTrack T0b + analytic dynamics T0c/d) | stated |
| `2026-06-18-t1-temporal-contract` | none | unclear — `.venv-ft` + locally-available Gazebo Harmonic implies the RTX 3090 workstation, but… | **UNKNOWN** |
| `2026-06-24-t2-permanence` | none | unclear — `.venv-ft/bin/python runners/sitl/reid_policy.py`, no host named | **UNKNOWN** |
| `2026-06-24-t3-closed-loop` | none | unclear — kinematic A/B under `.venv-ft` plus live ArduCopter SITL under `.venv`, no host named | **UNKNOWN** |
| `2026-06-24-t4-deployment` | Jetson | jetson-orin-nano-8gb (ByteTrack timed on the Orin CPU; only `bytetrack.py` pushed to the device) | stated |
| `2026-06-25-roi-crop-anchor` | both | rtx-3090 (HF bf16 accuracy sweep + drift perturbation, `.venv-ft`); jetson-orin-nano-8gb… | stated |
| `2026-06-25-system-demo` | Jetson | rtx-3090 workstation (Gradio GUI, CSRT tracker from `.venv-ft` opencv-contrib, ffmpeg mp4… | stated |
| `2026-06-26-appearance-snr` | none | workstation CPU only (numpy + PIL); the README rules out both the 3090 GPU and the Jetson | stated |
| `2026-06-26-roi-demo-tab` | Jetson | rtx-3090 workstation (`grounding/deploy/gui.py`, `measure_cadence.py` driver, image transfer) | stated |
| `2026-06-27-roi-shrink-spiral` | **unclear** | unclear — offline `grounding/roi.py` self-checks, no host named | **UNKNOWN** |

### Part IV — v4 end-to-end workflow refinement

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-06-30-roi-sr-upscale` | 3090 | rtx-3090 (Swin2SR + HF bf16 spine, torch 2.6.0+cu124, `.venv-ft`) | stated |
| `2026-06-30-vlm-backbone-bakeoff` | both | rtx-3090 (all LoRA fine-tunes + GGUF export + HF n=200 evals); jetson-orin-nano-8gb (arm B… | stated |
| `2026-06-30-whole-frame-resolution` | Jetson | jetson-orin-nano-8gb (llama-server Q8_0 ngl=99); driver/harness on the workstation | stated |
| `2026-07-01-temporal-acquire-carry` | Jetson | both — SAM2 carry accuracy on rtx-3090 (Phase 0 + knee re-evals), SAM2 FPS/RAM on… | stated |
| `2026-07-02-carry-trt-export` | Jetson | split by step: RTX 3090 `.venv-ft` (ONNX export + fp32 graph parity, steps 1-2); Jetson Orin… | stated |
| `2026-07-02-follow-hardening` | Jetson | rtx-3090 (SITL + renderer + SAM2 StreamCarry @1024 + eval harness) | **inferred** |
| `2026-07-02-follow-speed-ceiling` | Jetson | rtx-3090 (ArduCopter SITL + renderer + SAM2 StreamCarry @1024 + PID/eval harness) | **inferred** |
| `2026-07-02-pursuit-chase` | Jetson | rtx-3090 (SITL + renderer + SAM2 StreamCarry @1024 + eval harness) | stated |
| `2026-07-02-twin-distractor` | Jetson | rtx-3090 (SITL + renderer + SAM2 StreamCarry @1024 + eval harness) | **inferred** |
| `2026-07-03-chase-acquire` | Jetson | rtx-3090 (SITL + renderer + SAM2 carry @1024 + eval harness) | stated |
| `2026-07-03-fast-follow-ceiling` | Jetson | rtx-3090 (SITL + renderer + SAM2 carry @1024 + eval harness) | stated |
| `2026-07-03-first-acquire` | Jetson | rtx-3090 (SITL + renderer + SAM2 StreamCarry @1024 + eval harness) | stated |
| `2026-07-03-identity-gate` | Jetson | rtx-3090 (SITL + renderer + SAM2 carry @1024 + eval harness; the appearance-template gate… | stated |
| `2026-07-03-late-command` | Jetson | rtx-3090 (SITL + renderer + SAM2 carry @1024 + eval harness) | stated |
| `2026-07-03-mask-hardening` | Jetson | rtx-3090 (SITL + StreamCarry @1024 + eval harness) | stated |
| `2026-07-03-mask-identity` | Jetson | rtx-3090 (SITL + renderer + SAM2 @1024 + eval harness; design-time probe also 3090) | stated |
| `2026-07-03-real-video-replay` | Jetson | rtx-3090 (UAV123 replay + SAM2.1-hiera-tiny StreamCarry @1024, artificially rate-capped to… | stated |
| `2026-07-03-reground-chase` | Jetson | rtx-3090 (SITL + SceneRenderer + StreamCarry SAM2 @1024 + eval harness) | stated |
| `2026-07-03-reground-gate` | Jetson | rtx-3090 (SITL + SAM2 carry @1024 + eval harness) | stated |
| `2026-07-03-reground-selfcorrect` | Jetson | rtx-3090 (SITL + SAM2 carry @1024) | stated |
| `2026-07-03-relock-rate` | Jetson | rtx-3090 (SITL + SceneRenderer + StreamCarry/SAM2 @1024) | stated |
| `2026-07-03-retarget-switch` | Jetson | rtx-3090 (SAM2 carry + SITL) | stated |
| `2026-07-04-coarse-to-fine-acquire` | Jetson | rtx-3090 (SAM2.1-hiera-tiny StreamCarry 6.15 Hz + replay harness) — inherited via E20→E19,… | **inferred** |
| `2026-07-04-cv-proposal-acquire` | none | rtx-3090 (offline Phase-0 prior audit; machine never named in the README) | **inferred** |
| `2026-07-04-motion-comp-acquire` | Jetson | rtx-3090 (SAM2.1-hiera-tiny @1024, rate-capped 6.15 Hz, replay harness) | stated |
| `2026-07-04-prompt-scoped-acquire` | Jetson | rtx-3090 (SAM2.1-hiera-tiny StreamCarry + replay harness) — inherited from E19, never named in… | **inferred** |
| `2026-07-04-tolerant-cells` | Jetson | rtx-3090 (SAM2 StreamCarry + replay harness, mirroring E20) — never named in this file | **inferred** |

### Part V — v5 anticipatory grounding

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-07-04-warm-start-acquire` | Jetson | rtx-3090 (SAM2.1-hiera-tiny StreamCarry, rate-capped 6.15 Hz + replay harness) | stated |
| `2026-07-04-warm-start-generalization` | Jetson | rtx-3090 (SAM2 carry rate-capped 6.15 Hz + replay harness) — inherited from P5.1, never named… | **inferred** |
| `2026-07-14-autoresearch-run` | none | unnamed host workstation (cron + flock + `claude -p` driver; no measurement legs) — presumed… | **UNKNOWN** |
| `2026-07-14-crop-select` | Jetson | rtx-3090 (SAM2 carry rate-capped 6.15 Hz; CLIP ViT-L/14 + ViT-B/32 secondary arm; harness) | stated |
| `2026-07-14-multi-candidate-select` | Jetson | rtx-3090 (SAM2.1-tiny carry, rate-capped to 6.15 Hz / 3.075 Hz per candidate) | stated |
| `2026-07-14-select-generalization` | Jetson | rtx-3090 (SAM2.1-tiny carry, sam2 1.1.0 / torch 2.6.0+cu124, rate-capped 6.15 Hz) | stated |
| `2026-07-17-bankv2-crossing` | none | rtx-3090 (Gazebo 8.14.0 crossing/occlusion bank build + integrity gates) | stated |
| `2026-07-17-bankv21-recal` | none | rtx-3090 workstation (Gazebo/gz sim 8.14.0 scene generation + recording; no model inference) | stated |
| `2026-07-17-kerbsafe-scenebank` | none | rtx-3090 (Gazebo 8.14.0 scene-bank build + GT recorder, stock clocks) | stated |
| `2026-07-17-scenegen-transport` | none | rtx-3090 (Gazebo 8.14.0 + gz-transport stress probe, driver 595.71.05) | stated |
| `2026-07-17-sim-scenegen` | none | rtx-3090 (Gazebo 8.14.0 headless EGL scene generator + gz-transport harness) | stated |
| `2026-07-17-simbank-select` | both | rtx-3090 (select harness + SAM2 carry bf16 + all scoring; Gazebo bank frames from disk) | stated |
| `2026-07-19-autodisc-select` | Jetson | rtx-3090 (SAM2 carry bf16, discovery scheduler, matrix harness, scoring) | stated |
| `2026-07-19-carry-horizon` | Jetson | rtx-3090 (SAM2 sam2.1-hiera-tiny bf16 carry + scoring; PLAIN arm entirely) | stated |
| `2026-07-19-realvid-dd-select` | Jetson | rtx-3090 (SAM2 carry, scoring, UAV123 frame decode) | stated |
| `2026-07-19-v2disc-select` | Jetson | rtx-3090 (bank frames, SAM2 carry, all scoring) | stated |
| `2026-07-20-bankv3-select` | Jetson | rtx-3090 (Gazebo Sim 8.14.0 headless bank render + SAM2 sam2.1-hiera-tiny bf16 carry + scoring) | stated |
| `2026-07-20-carry-capacity` | Jetson | rtx-3090 (SAM2 carry — hiera-tiny arm T vs hiera-small arm S — plus orchestration and scoring) | stated |
| `2026-07-20-late-entry-rescue` | Jetson | rtx-3090 (SAM2 sam2.1-hiera-tiny bf16 carry, rescue harness, scoring; consumes the P5.18 scene… | stated |
| `2026-07-20-n25-select` | Jetson | rtx-3090 (SAM2 sam2.1-hiera-tiny bf16 carry, UAV123 replay, harness, scoring) | stated |

### Part VI — v6 closed-loop flight

| Campaign | VLM ran on | Other compute | Disclosure |
|---|---|---|---|
| `2026-07-20-p60-flight-rig` | none | rtx-3090 (ArduCopter 4.6.3 SITL + Gazebo 8.14.0 pose-slaved renderer + ByteTrack + cascade PID… | stated |
| `2026-07-20-p61-carla-renderer` | none | rtx-3090 (CARLA 0.9.16 server Town10HD_Opt + ArduCopter 4.6.3 SITL + pose-slaved camera + full… | stated |
| `2026-07-21-carla-gt-bank` | **unclear** | rtx-3090 (inferred: CARLA 0.9.16 server on port 2100 driven by… | **UNKNOWN** |

<!-- END GENERATED TABLES -->

---

## Proof deliverables

- `proof/disclosure-by-part.png` — stacked bar, disclosure quality (stated / inferred /
  unknown) per Part across all 76 campaigns. Locates the defect: Part I is 9/9 stated,
  while Part III carries 4 `unknown` and Part IV carries 7 `inferred`. This figure
  falsified the first draft of the paragraph above it, which had asserted the opposite
  concentration — it earns its place in `proof/` for that reason. From `make_proof.py`,
  reproducible from `raw/machine-audit.json`.
- `proof/vlm-host-by-part.png` — same 76 campaigns by VLM host, which is the figure
  that answers claim B visually: the Jetson bar is the majority everywhere the VLM is
  in the loop, and the «none» bar is where the workstation-only work lives.
- `raw/machine-audit.json` — the 76-row audit itself, with a quoted evidence string per
  row. This is the input R-2 reads to fill `machine` on all 65 registry claims.

## Reproduce

```bash
.venv-ft/bin/python experiments/2026-07-21-machine-disclosure/make_tables.py
.venv-ft/bin/python experiments/2026-07-21-machine-disclosure/make_proof.py
```
