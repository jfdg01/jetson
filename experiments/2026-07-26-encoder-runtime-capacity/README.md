# EXP-9 — encoder runtime (eager bf16 vs TensorRT fp16) x capacity (tiny vs small), on Jetson

**Status:** PRE-REGISTERED 2026-07-26T20:38Z. Not yet run.
**Verdict:** TBD.
**Part:** VI (perception-stack, on-device). **Machine:** `jetson` (Orin Nano 8 GB; SAM2 runs on the
Orin, the 3090 is NOT used — I3).
**Power mode:** 15 W + `jetson_clocks` (the only real mode on this board — no MAXN_SUPER).
**Owner claim id (planned):** `EXP9-encoder-runtime-capacity` — registered as an **engineering
measurement, not a thesis claim** (R-44 standing, same as EXP-1/EXP-2/EXP-6/EXP-8). p-values stay
in this README and do **not** enter `thesis/claims.json`, so this campaign does **not** re-run Holm
over Part VI's published claims (the standing cost R-39 exists to catch).

## Premise (the user's question, and what is actually open)

User, 2026-07-26: *"we have run some tests of the sam2 model, now we have a bit more (600 MB) ram to
work with … should we try small now that we have some more room? pull the lever you recommended
first?"*

The 600 MB is real and EXP-8 is where it came from: `PRUNE_AFTER=100` was holding 85 frames the
model provably never reads, and the derived ring returned **~670 MB of host RAM with bit-identical
output**. The question is what to spend it on.

**Two candidate levers, and they are not equally open.**

### Capacity (`hiera-small`) is mostly answered — but its on-device gate was never paid

P5.20 (`experiments/2026-07-20-carry-capacity/`) already ran `facebook/sam2.1-hiera-small`:
108 cells, equal-stride, **T (tiny) 42 vs S (small) 41** — the bigger model recovered **zero** cells
and landed a hair *worse*. Its own line writes off the next step up: *"hiera-base-plus / large
(80.8 M / 224.4 M) — no plausible Jetson co-residency; small is the largest defensible step."*

But P5.20 ran **on the RTX 3090**, in the **select** framing, at emulated equal stride. It recorded
a follow-up it never paid:

> *"hiera-small requires a follow-up E1-style TensorRT export + co-resident FPS gate"*

and `docs/results/part5-anticipatory.md` confirms that debt was *"never incurred"* because capacity
was killed on accuracy first. So what the 600 MB reopens is **fit and rate on-device** — not *does
capacity help*, which is answered NO twice (P5.20 directly; EXP-8's PASS→FAIL taxonomy indirectly,
since its failures are **mask leak onto a neighbour** and **identity swap onto a same-class
distractor**, neither of which a fatter encoder addresses).

### The genuinely unpulled lever is the TensorRT encoder at 640

E1 (2026-07-02, `experiments/2026-07-02-carry-trt-export/`) exported the SAM2.1-tiny ViT-Hiera image
encoder to **TensorRT fp16, encoder-only** — memory attention and the two high-res 1x1 convs stay
PyTorch. Result: **4.89 → 6.15 FPS co-resident at `image_size` 768, mask parity IoU 1.000**.

`enc768.onnx` and `enc768.plan` are still on the Orin at `~/sam2-bench/`. **The engine was never
re-exported at 640** — the resolution EXP-1 measured as the elbow and R-46 adopted as the deployed
carry. EXP-8's own config line confirms what runs today: *"eager torch bf16, no TensorRT"*, at
**173.4 ms/step = 5.77 Hz**. A known-parity-safe speedup is sitting unpulled at the deployed
resolution.

### Why both, in one 2x2, rather than in sequence

The interaction cell is the only one that could change the deployed config. If `small` costs rate
(it will — more parameters at the same resolution), TensorRT fp16 is exactly the thing that could
pay for it. Running them sequentially measures neither the interaction nor the deployable
combination. Four arms cost ~50 min of Orin time (EXP-8 ran ten arms in ~2 h), so the factorial is
affordable and the sequential version saves nothing worth having.

## What the levers are (verified in the installed `sam2` package and on the Orin)

| Lever | Where | Stock | What it controls |
|---|---|---|---|
| model id | `stream_carry.py:38` (`MODEL`) | `facebook/sam2.1-hiera-tiny` (38.9 M) | encoder capacity; `sam2.1-hiera-small` is 46 M, the smallest step in the family |
| encoder runtime | `carry_ssh_bridge.py`, unpatched | eager torch bf16 | `predictor.forward_image`; E1's `make_trt_forward_image` swaps the ViT-Hiera forward for a TensorRT fp16 engine and re-applies `conv_s0`/`conv_s1` in torch |
| `image_size` | `++model.image_size` | **640** (EXP-1 elbow, R-46) | held fixed in every arm — this campaign does not re-sweep resolution |

Held fixed at the adopted config everywhere: `image_size=640`, K=7, M=16 (EXP-8: keep both),
`PRUNE_AFTER=32` (EXP-8 Stage-1 value; on a 24-step window P never fires above 24, so 32 prunes
nothing and cannot confound — same reasoning EXP-8 recorded, restated here because it is the
condition under which these numbers are comparable to EXP-8's).

## Hypotheses

**H1 — the TensorRT fp16 encoder lifts the carry rate at 640, at parity.** Predicted **YES**.

Pre-registered arithmetic, so a miss is diagnostic rather than a shrug. E1 measured the encoder at
~150 ms of a 204 ms step at 768 (**73.5 %** of the step) and 65 ms in fp16 TRT (**2.31x**). Encoder
cost scales with pixel count, so at 640 the encoder should be `150 * (640/768)^2 = 104 ms` of
EXP-8's measured 173.4 ms step (**60 %**), leaving 69.4 ms of non-encoder work. Applying the same
2.31x:

```
step_trt  ~=  104/2.31 + 69.4  =  45 + 69.4  =  114 ms   ->  8.75 Hz   (+52 % vs 5.77 Hz)
```

Cross-check against EXP-8, which is the only other decomposition of this step we have: K=1 removed
six of seven mask-memory slots for 19.5 ms, i.e. memory attention is ~11 % of the step. Encoder 60 %
+ memory attention ~20 % (all seven slots) + ~20 % decoder/mask/JPEG-decode closes plausibly.

**If the measured gain is under +25 %, the encoder-share model is wrong** and that is the finding —
it would mean the 640 step is far more overhead-bound than E1's 768 numbers imply, which also
retro-bounds how much *any* encoder-side lever (including INT8) can ever buy.

**H2 — `hiera-small` does not beat `hiera-tiny` on carry accuracy.** Predicted **NO** (null).
P5.20's prior, plus EXP-8's failure taxonomy pointing at association rather than capacity. Expect
`b ~= c ~= 0..2` on PASS flips and a Wilcoxon that does not survive Holm.

**H3 — `hiera-small` co-resides with the deployed VLM on 8 GB.** Predicted **YES**, marginally.
Descriptive census, not a test. Measured, not derived: the bridge already reports `cuda_mb` and
`rss_mb` per step (EXP-8 added them). Recorded for `base_plus` too — P5.20 wrote it off *before*
the ring returned 670 MB, so the write-off deserves one measurement rather than an inherited
assumption.

**H4 — capacity on the same-class-distractor stratum.** Predicted **NO**, and declared
**descriptive, not confirmatory**, before the run.

This is the one place a bigger encoder has a mechanism: EXP-8's residual failures are mask leak and
identity swap onto same-class distractors, and discriminating a target from a near-identical
neighbour is a feature-quality problem. Clips are labelled for same-class-distractor presence
**before any arm runs**, the labels are frozen in `raw/strata.json`, and the readout is a subgroup
of a bank of 38 — it will land under n=25 and is therefore **not** inferential (I4). Saying so now
is what stops it becoming a post-hoc fishing expedition; it earns its place as the pre-specified
place to *look*, not as a place to claim.

## Gates (pre-registered decision rules)

- **G1 (H1 parity, blocking for `trt`/`small_trt`):** end-to-end mask parity of the TRT-patched
  encoder vs the eager reference must be **mean IoU >= 0.99** on the ONNX parity clip before any
  TRT arm is scored. E1 got 1.000 at 768. Below 0.99 -> the TRT arms are reported as **INVALID**,
  not as a rate win.
- **G2 (H1 adoption):** adopt TRT fp16 at 640 as the deployed carry iff parity holds **and** the
  median step rate improves by **>= 15 %** **and** the arm is **non-inferior on accuracy**, defined
  as the bootstrap CI95 lower bound on the paired median IoU delta > **-0.05** *and* PASS not down
  by more than 1 clip. PASS is in the gate on purpose: EXP-8's G2 fired on the letter for K=1
  because it was written against median-of-median IoU alone and was blind to a minority of clips
  collapsing. Same mistake, not repeated.
- **G3 (H2 adoption):** adopt `hiera-small` iff it **wins** — Wilcoxon surviving Holm over this
  campaign's family **and** `c > b` on McNemar — **and** it fits co-resident **and** it clears the
  same >= 5 Hz co-resident rate gate E1 was built to clear. All four. A tie is a keep-tiny.
- **G4 (Stage 2, INT8):** runs **only if** a capacity arm wins G3 but misses the rate leg, i.e. only
  if there is a model worth making cheaper. If capacity is null again, INT8 has no job and Stage 2
  is a **planned skip, not dropped scope**. Recorded now so the skip is a gate firing, not a
  silently narrowed campaign.

## Arms

Baseline everywhere = the deployed config: `image_size=640`, K=7, M=16, P=32,
`facebook/sam2.1-hiera-tiny`, eager torch bf16, no TensorRT. This is EXP-8's `base` arm, so its
numbers (median-of-median IoU 0.811, 32/38 PASS, 173.4 ms, peak CUDA 506.7 MB) are the expected
reproduction and a built-in sanity check on the harness.

**Stage 0 — memory census (cheap, gates nothing, informs G3/G4).** Load-and-step each of
{tiny, small, base_plus} at 640, solo and co-resident with the deployed `llama-server`, and record
peak CUDA + peak RSS + host free/available. Three clips, not the full bank.

**Stage 1 — the 2x2.** Full 38-clip bank, `N_STEPS=24 @ STRIDE=11`, P=32, one bridge per arm.

| Arm | Model | Encoder runtime | Note |
|---|---|---|---|
| `base` | `sam2.1-hiera-tiny` | eager bf16 | deployed; shared baseline; reproduces EXP-8 `base` |
| `trt` | `sam2.1-hiera-tiny` | TensorRT fp16 (`enc640.plan`) | the unpulled E1 lever at the adopted resolution |
| `small` | `sam2.1-hiera-small` | eager bf16 | pays P5.20's owed on-device gate |
| `small_trt` | `sam2.1-hiera-small` | TensorRT fp16 (`enc640_small.plan`) | the only cell that could beat `base` on both axes |

4 arms. Full factorial for once, because it is only four cells and the interaction is the point.

**Stage 2 — INT8.** Gated by G4. Not run unless G4 fires.

## Data

**The EXP-1/EXP-8 bank, unchanged**, so the numbers are directly comparable to both: UAV123 clips
with a contiguous GT window, **38 clips staged on host**, n >= 25 satisfied. Per clip: seed = GT at
the first frame with a contiguous window, carry `N_STEPS=24 @ STRIDE=11` (~264 frames, ~8.8 s of
video). **Clips are the unit of analysis and are independent — no deflation** (I2: `n_effective` =
`n_rows` = 38).

Same scope caveat EXP-8 recorded and this campaign inherits: at STRIDE=11 one step is 0.37 s of
video, so the carry runs faster than real time per step; the *rate* numbers are per-step compute on
the Orin, not a real-time-following claim.

## Method / commands

Host stages the bank (UAV123 GT is host-side), frames stream as JPEG over the ssh-stdio bridge, the
carry runs **on the Orin**, the host scores against GT. Identical shape to EXP-1/EXP-8.

```bash
# host: export the two ONNX encoders at 640 + ONNX-level parity gate (3090/host, CPU ORT)
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py export \
    --out runs/exp9

# Orin: build the two TensorRT fp16 engines from the ONNX (trtexec 10.3.0, already installed)
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py engines \
    --out runs/exp9

# host: stage the bank (reuses the EXP-1/EXP-8 plan format)
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py stage --out runs/exp9

# Orin: Stage 0 memory census, solo and co-resident
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py census --out runs/exp9

# Orin: G1 on-device mask parity gate (TRT vs eager, both models)
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py parity --out runs/exp9

# Orin: the 4 Stage-1 arms
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py carry --out runs/exp9 \
    --arms base,trt,small,small_trt

# host: score + paired stats + figures + look-at-it overlays
.venv-ft/bin/python experiments/2026-07-26-encoder-runtime-capacity/run_exp9.py score --out runs/exp9
```

**Code written for this campaign** (as-built timestamps filled at run):

- `run_exp9.py` — fork of `2026-07-26-carry-memory-horizon/run_exp8.py`; arms are
  `(model, trt_plan)` pairs instead of `(K, M)`, plus the `export` / `engines` / `census` / `parity`
  subcommands. Same bank, same seed policy, same bridge framing, same stats module.
- `carry_ssh_bridge.py` gains **`--model`** and **`--trt-encoder`**, both defaulting to the current
  behaviour (`stream_carry.MODEL`, no patch), so every pre-EXP-9 caller — the live CARLA panel,
  EXP-1/2/6/8 replays — stays **bit-identical**. Same discipline EXP-8 used for its four flags.
- The TRT engine path reuses E1's `make_trt_forward_image` from `jetson_carry_bench.py`, already on
  the Orin. No new inference code.

## Metrics & statistics

Per clip: `median_iou` over the 24 steps, `held_frac` (fraction of steps with IoU >= 0.25),
`median_ms`, `hz`, `peak_cuda_mb`, `peak_rss_mb`, and EXP-8's re-find metric (a lost step counts as
re-found if IoU >= 0.25 within the next 5 steps).

- **PASS** = `median_iou >= 0.25`, the EXP-1/EXP-8 definition, kept for comparability.
- **Continuous:** Wilcoxon signed-rank on per-clip `median_iou`, arm vs `base`, with a bootstrap
  CI95 on the median paired difference (`grounding/stats.py:paired_continuous`).
- **Binary:** exact two-sided McNemar on PASS. **b = clips that flip PASS->FAIL vs base,
  c = clips that flip FAIL->PASS.** Zero discordant pairs is reported as *undefined*, not as
  non-significant (I4 — EXP-8's M arms are the precedent).
- **Multiplicity:** Holm over this campaign's 3-comparison family (`trt`, `small`, `small_trt`,
  each vs `base`). This family is **local to EXP-9** and does not join a Part VI Holm family,
  because the campaign registers as an engineering measurement (R-44) and publishes no claim.
- **Look at it (I5):** the score pass writes overlays for a 3-clip sample **plus every PASS-flip
  clip**, with the mechanical asserts EXP-8 used — a frame >99 % one colour fails the render, and a
  carried box identical at every step fails as a dead feed. Frames get opened with the Read tool
  before any verdict is written here.

## Risks / things that could go wrong (pre-registered)

1. **`hiera-small` is not cached on the Orin.** Only `models--facebook--sam2.1-hiera-tiny` and
   OWLv2 are in `~/.cache/huggingface/hub`. Needs a ~180 MB download; 127 G free on `/`, so disk is
   not the constraint, network is. Retry once, then stop and record.
2. **`base_plus` may not load at all** co-resident. That is a Stage-0 *result*, not a failure —
   record the OOM and move on.
3. **`maskmem_tpos_enc` / strict load.** EXP-8 learned that K is a post-load attribute because the
   trained parameter is sized 7. Nothing here touches K, but the `--model` swap must not silently
   inherit a tiny-shaped assumption: the bridge logs the loaded model id and its K/M so every arm's
   config is in `bridge_<arm>.err`.
4. **ONNX export at 640 for `hiera-small` may not be a drop-in.** The `EncoderWrapper` flattens
   `backbone_fpn` + `vision_pos_enc` to a 6-tuple; if small's FPN has a different arity the export
   asserts rather than producing a wrong engine.
5. **Box contention.** A resident `carry_ssh_bridge.py` from the live CARLA UI was found running at
   GR3D 99 % at 2026-07-26T20:36Z and killed **with the user's explicit confirmation** ("kill it i
   was using the ui"). Any arm that runs under contention has its timing excluded, as EXP-8 did for
   `ringP8`. `llama-server` stays **up** throughout — it is the deployed co-resident condition and
   removing it would make the memory census fiction.
6. **`trtexec` build time and transient VRAM.** Engines get built with the carry down. TRT 10.3.0
   is already present, so no new dependency.

## Estimates (up front, marked as estimates)

- **Expected runtime:** ~50 min of Orin time for the four Stage-1 arms (EXP-8: ten arms in ~2 h),
  plus ~20-30 min for the two ONNX exports and two `trtexec` builds, plus ~10 min for the census.
  Call it **~1.5 h end to end**. Estimate.
- **Expected rate:** `base` reproduces EXP-8 at ~173 ms. `trt` ~114 ms (8.75 Hz) per the H1
  arithmetic. `small` ~1.3-1.5x `base`'s step (more params, same resolution) ~= 225-260 ms
  (~4 Hz, i.e. **below E1's >= 5 Hz co-resident gate**). `small_trt` ~150-170 ms — the interesting
  cell, because it would put small back over the gate. All estimates.
- **Expected accuracy:** all four arms within +/-0.02 median-of-median IoU of each other; PASS
  32/38 +/- 1. `trt` parity-identical by construction (E1 got 1.000). Estimates.
- **Expected memory:** peak CUDA ~507 MB for tiny (EXP-8 measured it in all ten arms to the
  decimal), ~600-650 MB for small. Host RSS is where the model size actually shows. Estimate.
- **Most likely overall outcome, stated up front so a null is not spun:** **H1 YES** (a real,
  parity-free rate win at the deployed resolution — the lever that should have been pulled at R-46),
  **H2 NO** (capacity dead for the third time), **H3 YES-marginal**, **H4 NO**. That combination is
  a useful result: it adopts one lever, closes P5.20's owed on-device gate, and bounds the encoder
  share of the step so that any future encoder-side lever (INT8 included) can be priced without
  running it.

## Build log — deviations from the pre-registration, all recorded *before* any arm ran

Kept separate from Results on purpose: these are changes to the setup made between writing the
pre-registration and launching the sweep. Both are dated 2026-07-26T20:48Z and neither could have
been informed by an arm result, because no arm had run.

### D1 — the H4 strata split is 26/12, not the "both under n=25" the pre-registration assumed

`_stratum()` derives the label from the clip name only. The first implementation stripped digits
(`car10` -> `car`) but not UAV123's `_s` variant suffix, so `car1_s`, `car3_s`, `car4_s` and
`person1_s` — same subject class, same scene family — landed in `distractor_free`. Fixed before
any arm ran; the split moved from dense 22 / free 16 to **dense 26 / free 12**.

**H4 stays declared descriptive, not confirmatory.** The dense stratum now clears n=25 on paper,
and promoting it to inferential *after* seeing that number is exactly the post-hoc move the
pre-registration set out to prevent. The free stratum is n=12 regardless, so the contrast — which
is the actual quantity of interest — is bounded by 12 either way. The pre-registered sentence
"it will land under n=25" is **wrong as written**; the conclusion it justified is not.

### D2 — ONNX Runtime's graph optimizer miscompiles the hiera-small encoder graph

Risk 4 was pre-registered as *"ONNX export at 640 for `hiera-small` may not be a drop-in"*. It was
not a drop-in, but not for the predicted reason (FPN arity). The export itself is fine; **E1's
gate 2a is what broke**, and it broke in the tool, not in the graph.

First attempt, `enc640_small.onnx`, max-abs-diff vs eager on the three feature outputs:

```
fpn0 1.62e+33   fpn1 7.08e-01   fpn2 3.08e+00      pos0/1/2 5.96e-08
```

`1.62e+33` is not a numerical-precision failure, it is garbage. `onnx.checker.check_model` passes.
ORT logs, at session build:

```
[W:onnxruntime:, graph.cc:122 MergeShapeInfo] Error merging shape info for output.
'/enc/trunk/Concat_3_output_0' source:{4} target:{5}. Falling back to lenient merge.
```

Sweeping ORT's optimization level against the same graph and the same frame isolates it:

| `graph_optimization_level` | fpn0 | fpn1 | fpn2 |
|---|---|---|---|
| `ORT_DISABLE_ALL` | 2.32e-04 | 1.81e-04 | 4.59e-04 |
| `ORT_ENABLE_BASIC` | 1.21e-01 | 8.27e-01 | 2.45e+00 |
| `ORT_ENABLE_ALL` (ORT's default) | 6.47e-03 | 8.00e-03 | 1.30e-02 |

Unoptimised, small matches eager to **2.32e-04** — the same order as tiny's 2.30e-04. The optimizer
is what corrupts it, and the corruption is not even monotone in the level. It is depth-triggered,
not config-triggered: tiny and small have identical `window_spec (8, 4, 14, 7)`, identical
`global_att_blocks` structure and identical `pos_embed` shape, and differ only at 12 vs 16 blocks.

**Consequence, and why this does not weaken the campaign.** ORT is a *proxy* gate — a host-side
check that the exported graph is sound. TensorRT parses the ONNX with its own builder and never
touches ORT's optimizer, so an ORT optimizer bug says nothing about the engine that will actually
run. `export_encoder.py` gains `--ort-graph-opt {all,disable}`, defaulting to `all` so E1 stays
reproducible byte-for-byte; EXP-9 passes `disable` for **both** models so the two exports are gated
identically rather than each on its own terms.

Re-run with the optimizer off, **both** models clear both of E1's gates:

| Model | ONNX max-abs-diff (worst of 6) | End-to-end mask parity (batch propagate, 99 frames) |
|---|---|---|
| tiny @640 | 2.85e-04 | mean IoU **1.0000**, min 1.0000 |
| small @640 | 4.59e-04 | mean IoU **1.0000**, min 1.0000 |

The authoritative gate remains **G1, on-device TensorRT-vs-eager end-to-end mask parity**, which
goes through neither ORT nor the host. G1 is unchanged by this.

### D3 — the census is co-resident only; the solo column is not measured

The pre-registered census table asked for solo **and** co-resident peaks. Measuring solo means
stopping `llama-server` on the Orin, and the pre-registration also states, in the risk list, that
`llama-server` **stays up throughout** because it is the deployed co-resident condition. Those two
lines contradict each other. The risk-list constraint wins, for two reasons: the question H3 exists
to answer is *"does a bigger SAM2 fit next to the deployed VLM"*, for which co-resident **is** the
condition and solo is decoration; and the service is the one the user's live UI talks to. The solo
column is **not run**, not "pending" — the table is amended rather than left half-empty, so nobody
later reads a blank cell as a lost measurement.

### D4 — TensorRT writes to the bridge's stdout, which is the protocol channel

Not on the risk list, and it should have been. `carry_ssh_bridge.py` speaks a framed protocol
(4-byte big-endian length + pickle) over the ssh stdio pipe, so **stdout must carry replies and
nothing else** — the file docstring has said so since P6.7. TensorRT's Python logger writes to
fd 1, and it does it at the **first `enqueueV3`**, not at deserialize:

```
[07/26/2026-21:38:03] [TRT] [W] Using default stream in enqueueV3() may lead to perf...
```

The host then read `b'[07/'` as a frame length — `1529886511` bytes — and blocked forever on a
read that could never be satisfied. Both ends sat at **0% CPU and 0% GPU** with no error on either
side, no traceback, and a well-formed log ending in an ordinary post-processing warning. The first
G1 attempt hung ~30 min before it was noticed. A load-only probe came back clean, which is exactly
why the first diagnosis (a print at engine deserialize) was wrong: the contamination only appears
once real inference starts.

Two fixes, both in `experiments/2026-07-24-p62-showcase/carry_ssh_bridge.py`:

1. At startup, `dup(1)` the real stdout to a private fd and `dup2(2, 1)`. The protocol writes to
   the saved fd; every stray print from any library lands in the stderr log the host already
   captures. Fixed at the transport, so it holds for the next library that does this too.
2. `faulthandler.register(signal.SIGUSR1)` — `kill -USR1 <pid>` dumps every thread's Python stack
   into that same log. A protocol where both ends block on a read needs this; py-spy is not an
   option here, since attaching to a non-child needs root and only `nvpmodel`/`jetson_clocks` are
   NOPASSWD on this box.

Both are backward-compatible and were verified against a live TRT bridge (init ack + 3 steps,
boxes returned) before G1 was restarted. Nothing about the engines, the plan bank or the gates
changed — this was a transport bug, not a result.

### D5 — G1 FAILED as pre-registered, and G1 was the wrong instrument

**As specified, G1 fails both engines**, and that is recorded as the result, not explained away:

| Engine | mean IoU over 3 clips x 24 steps | min | Gate (>= 0.99) |
|---|---|---|---|
| `enc640.plan` (tiny) | 0.8427 | 0.00 | **FAIL** |
| `enc640_small.plan` (small) | 0.9866 | 0.75 | **FAIL** |

G1 compares two **24-step recursive carries**. That is not a measure of engine fidelity: step
`t`'s mask becomes step `t+1`'s memory, so one differing pixel is fed back and compounds. The
pre-registration never specified the control that separates the two, so `diag_g1.py` was written
to supply it (`runs/exp9/diag_g1.json`):

| Comparison | mean IoU | min | **step-1 IoU** |
|---|---|---|---|
| tiny **eager-vs-eager (control)** | **1.0000** | 1.0000 | 1.0000 |
| tiny eager-vs-TRT | 0.8427 | 0.0000 | **1.0000** |
| small **eager-vs-eager (control)** | **1.0000** | 1.0000 | 1.0000 |
| small eager-vs-TRT | 0.9866 | 0.7500 | **0.9949** |

Two things follow. The carry is **exactly deterministic** — re-running eager reproduces itself to
1.0000, so the instrument is sound and every bit of divergence is attributable to the runtime swap,
not to noise. And at **step 1, before any state exists, the engines agree with eager at 1.0000
(tiny) and 0.9949 (small)** — they are faithful; the recursion amplifies. Per-clip, the entire tiny
failure is **one clip**: `bike3` bifurcates at step 1 and ends at 0.0 (one runtime loses the target,
the other holds it), while `bike1` and `boat2` sit at ~1.0 for the full 24 steps.

Which runtime is *right* on `bike3` is a **ground-truth** question, and G1 never asks it — it only
asks whether two runs agree. So the TRT arms are run under an explicit, recorded override
(`--g1-override`, reason stored in `runs/exp9/carry_override.json`) rather than dropped on a gate
that measured the wrong quantity. **G2 is not relaxed**: adoption still requires non-inferiority
against ground truth (CI95 lower bound on the paired median-IoU delta > -0.05, PASS not down more
than one clip) plus the >= 15% rate win. If fp16 genuinely degrades the carry, G2 is where it shows
up, measured against GT instead of against another approximation.

What should have been pre-registered: a **state-free** fidelity gate (step-1 mask parity) as the
blocking engine check, with recursive-trajectory agreement reported as a descriptive diagnostic.
Noted for any future runtime-swap experiment.

## Results

Run 2026-07-26T20:44Z–22:02Z. Jetson Orin Nano 8 GB, **15 W + `jetson_clocks`**, JetPack 6.x /
TensorRT 10.3.0, co-resident with the deployed `llama-server` throughout. Host: 3090 box, `.venv-ft`.
38 UAV123 clips, 24 steps @ stride 11, `image_size=640`, K=7 M=16 P=32.

Raw lives in `runs/exp9/` (gitignored, includes the ONNX/plan binaries and 20 overlay JPEGs); the
small artifacts every number here is computed from are committed under `raw/`: `results.json`,
`census.json`, `parity.json`, `diag_g1.json`, `strata.json` (the frozen H4 labels),
`carry_override.json`, `export.json`, `engines.json`, plus the three run logs.

### Stage 0 — memory census (co-resident only — see D3)

| Model | Params | Peak CUDA MB | Peak RSS MB | median ms/step | Host available MB during | Loads? |
|---|---|---|---|---|---|---|
| tiny | 38.9 M | 505.3 | 1899.2 | 163.3 | 1407 | **yes** |
| small | 46 M | 545.4 | 1944.5 | 176.2 | 1353 | **yes** |
| base_plus | 80.8 M | 758.7 | 2180.4 | 241.8 | 1059 | **yes** |

**H3 = YES, and wider than predicted.** All three load and step next to the VLM, `base_plus`
included — the model P5.20 wrote off *before* the EXP-8 ring returned 670 MB. It leaves 1059 MB of
board headroom, so the thing that rules it out is not memory but **rate: 241.8 ms = 4.14 Hz, under
E1's >= 5 Hz co-resident gate.** small costs tiny +40 MB CUDA / +45 MB RSS and +12.9 ms — cheaper
than the estimated 600-650 MB.

### G1 — TRT mask parity

| Engine | image_size | ONNX max-abs-diff (opt off, D2) | On-device 24-step mean IoU | min IoU | **step-1 IoU** | Gate (>= 0.99) |
|---|---|---|---|---|---|---|
| `enc640.plan` (tiny) | 640 | 2.85e-04 | 0.8427 | 0.00 | 1.0000 | **FAIL** |
| `enc640_small.plan` (small) | 640 | 4.59e-04 | 0.9866 | 0.75 | 0.9949 | **FAIL** |

Control (`diag_g1.py`): eager-vs-eager is **exactly 1.0000** on both models. Full reading in **D5** —
the gate as written scores 24-step recursive-trajectory agreement, not engine fidelity, and the TRT
arms ran under a recorded `--g1-override` (`runs/exp9/carry_override.json`) with **G2 unrelaxed**.

Export/build cost, for anyone repeating this: ONNX 66.4 s / 104.2 MB (tiny), 73.8 s / 131.4 MB
(small); `trtexec --fp16` 169.9 s and 176.3 s on the Orin.

### Stage 1 — the 2x2

| Arm | Model | Runtime | median-of-median IoU | Δ vs base [CI95], Wilcoxon p (Holm) | mean held_frac | PASS/38 | McNemar b/c, p | re-find (refound/lost) | ms/step | Hz | speedup | peak CUDA MB | peak RSS MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `base` | tiny | eager bf16 | 0.811 | — | 0.859 | 32 | — | 3/129 | 173.7 | 5.757 | 1.00x | 506.7 | 2056.2 |
| `trt` | tiny | TRT fp16 | **0.815** | 0.0000 [0.0000, +0.0007], p=0.098 (0.294) | 0.860 | 32 | 0/0, undefined | 2/128 | **145.4** | **6.879** | **1.195x** | **439.5** | 2331.6 |
| `small` | small | eager bf16 | 0.798 | +0.0003 [−0.0046, +0.0036], p=0.987 (1.00) | 0.879 | **34** | 2/0, p=0.50 | **16/110** | 185.8 | 5.383 | 0.935x | 547.0 | 2125.0 |
| `small_trt` | small | TRT fp16 | 0.800 | +0.0002 [−0.0040, +0.0036], p=0.961 (1.00) | 0.878 | **34** | 2/0, p=0.50 | **17/111** | 152.4 | 6.561 | 1.14x | 465.8 | 2315.6 |

`base` reproduces EXP-8 to the third decimal (0.811 / 32 PASS / 506.7 MB; 173.7 vs 173.4 ms) — the
harness sanity check passes, so the deltas above are the runtime and capacity swaps and nothing else.

**All three arms are non-inferior** (CI95 lower bound > −0.05 on every one). No Wilcoxon survives
Holm; none was expected to, and `min_discordant` for a significant McNemar at n=38 is **6**, against
an observed maximum of 2 — so the small arms' 2-clip PASS gain is **underpowered by construction**,
not a measured tie (I4).

The one place the arms genuinely separate is **re-find**: small recovers a lost target on
**16/110** lost steps vs tiny's **3/129**, a ~6x better recovery rate with non-overlapping CI95
(0.092-0.223 vs 0.008-0.066). That is the mechanism behind both PASS flips, and it is a real
behavioural difference even though the PASS count that follows from it is not powered.

**Memory, honestly.** `trt` cuts peak CUDA by 67.2 MB but adds 275.4 MB of host RSS (the TRT runtime
plus the deserialized engine). On the Orin's **unified** memory these two counters overlap in ways
these numbers cannot separate, and **no board-level `free -m` sample was taken during Stage 1** — the
census (Stage 0) is eager-only. So: peak CUDA down, host RSS up, board-level net **not measured**.
Anyone adopting TRT into a memory-tight deployment should re-run the census with `--trt-encoder`.

### H4 — same-class-distractor stratum (descriptive, not inferential — see D1)

| Stratum | n | base | trt | small | small_trt |
|---|---|---|---|---|---|
| distractor-dense | 26 | 21 PASS / 0.830 | 21 / 0.831 | **23** / 0.818 | **23** / 0.820 |
| distractor-free | 12 | 11 PASS / 0.758 | 11 / 0.764 | 11 / 0.767 | 11 / 0.763 |

**Both PASS flips (`person21`, `uav3`) land in the dense stratum**, which is where H4 pre-specified
that a capacity win would show if it existed. Directionally consistent with the mechanism; **+2 on
n=26 is not evidence** and is not claimed as any. `inferential: false` is recorded in
`results.json`. **H4 = NO as a verdict, "look here again with a bank built for it" as a note.**

### Gate outcomes

| Gate | Fired? | Consequence |
|---|---|---|
| G1 parity >= 0.99 | **NO** (0.8427 / 0.9866) | Instrument, not engines — see D5. TRT arms run under recorded override; G2 untouched |
| G2 TRT adoption (`trt`) | **YES** (1.195x >= 1.15, non-inferior, PASS 32=32) | **Adopt TRT fp16 as the deployed carry encoder at 640** |
| G2 TRT adoption (`small_trt`) | **NO** (1.14x, hairline under 1.15) | Not adopted — but it is not the deployed model anyway; G3 is its gate |
| G3 small adoption | **NO** — needs all four: Wilcoxon-Holm reject (no), `c > b` (no, b=2 c=0), fits (yes), >= 5 Hz (yes, 5.38) | **Keep tiny.** Capacity dead for the third time (P5.20, EXP-9 eager, EXP-9 TRT) |
| G4 INT8 (Stage 2) | **NO** — fires only if a capacity arm wins G3 | **Planned skip, not dropped scope**, exactly as pre-registered |

Note on G3's shape: it demanded a **Wilcoxon IoU win**, and small's actual signal is a **PASS/re-find
win**. So G3 fails on the letter and would have failed on a fairer reading too (b=2 < the 6 discordant
pairs needed). Stating it because the gate was mis-aimed, not because the arm secretly won.

### Estimate vs actual

| Quantity | Estimate | Actual | Note |
|---|---|---|---|
| `trt` rate gain (H1) | **+52 %** (114 ms, 8.75 Hz) | **+19.5 %** (145.4 ms, 6.88 Hz) | **MISS — fires the pre-registered "under +25 % -> the encoder-share model is wrong" branch** |
| `small` rate | ~225-260 ms (~4 Hz, under the gate) | **185.8 ms, 5.38 Hz** | MISS — small is cheaper than assumed and *clears* the 5 Hz gate |
| `small` peak CUDA | 600-650 MB | **547.0 MB** | MISS, low |
| Accuracy spread | all arms within ±0.02 | 0.798-0.815, spread **0.017** | HIT |
| PASS | 32/38 ± 1 | 32 / 32 / 34 / 34 | HIT |
| End-to-end runtime | ~1.5 h | **~1 h 18 min** | HIT, and that includes the ~30 min D4 deadlock; the four Stage-1 arms took **~16 min**, not the estimated ~50 |
| Overall | H1 YES, H2 NO, H3 YES-marginal, H4 NO | **H1 YES-but-small, H2 NO, H3 YES-comfortable, H4 NO** | direction right on all four; the H1 *magnitude* is the finding |

**What the H1 miss buys.** Solve the pre-registered arithmetic backwards. A 2.31x encoder speedup
that yields only 28.3 ms of a 173.7 ms step means the encoder is `28.3 / (1 - 1/2.31) = 49.9 ms`
— **28.7 % of the 640 step, not the 60 % predicted from E1's 768 numbers.** The encoder share does
not scale with pixel count the way the estimate assumed; at 640 the step is overhead-bound
(memory attention, decoder, JPEG decode, protocol) far more than encoder-bound.

That **retro-bounds every future encoder-side lever without running it**: even a *free* encoder caps
the step at 123.8 ms (8.1 Hz, **+40 % over base and only +18 % over the adopted `trt` arm**), and
INT8 over fp16 — optimistically another 1.5x on the already-21.6 ms TRT encoder — buys 7.2 ms,
i.e. 138.2 ms, **+5 % over `trt`**. G4 was already a planned skip on the
capacity branch; this makes it a skip on the value branch too. **The encoder is no longer where the
carry's time is.** Anything that wants a materially faster carry at 640 has to attack memory
attention or the per-step overhead, and EXP-8 already showed the memory ring is worth ~19.5 ms.

## Proof deliverables

Figures are rebuilt from `runs/exp9/*.json` by the committed `make_proof.py`
(`.venv-ft/bin/python make_proof.py --run runs/exp9`). Overlays are copied from
`runs/exp9/overlays/`, written by `run_exp9.py score`.

1. **`rate-vs-iou.png`** — the four arms on the rate/accuracy plane, with base's IoU line, the G2
   non-inferiority floor (−0.05) and E1's 5 Hz co-resident gate drawn in. Shows the campaign's whole
   result in one frame: `trt` moves right at the same height (the win), `small`/`small_trt` move
   sideways (the null). Run: all four Stage-1 arms, 38 clips.
2. **`per-clip-delta.png`** — per-clip paired median-IoU delta vs `base`, sorted by base IoU. The
   guard against a median hiding a minority collapse: every arm sits on zero except `uav3` (+0.56)
   and `person21` (+0.28) for both small arms, and `person18` (−0.13) for `small_trt`. `trt` is flat
   on all 38, which is the visual form of its 0.0000 [0.0000, +0.0007] delta.
3. **`memory-census.png`** — Stage 0. Peak CUDA and host RSS per model (left), and board occupancy
   against the Orin's 7607 MB with `llama-server` up (right). This is the H3 answer: `base_plus`
   fits with 1059 MB to spare, so the reason to reject it is rate, not memory.
4. **`uav3_mid_base.jpg` / `uav3_mid_small.jpg`** and **`person21_mid_base.jpg` /
   `person21_mid_small.jpg`** — the two PASS-flip clips, mid-carry (step 12 of 24), GT vs carried
   box. Both are small distant targets: `base` has drifted onto a same-class distractor while
   `small` still holds the GT target. **Opened with the Read tool before this section was written**
   (I5) — the flips are genuine target-vs-distractor cases, not a scoring artifact.

## Status / next step

**COMPLETE.** Verdicts: **H1 YES but bounded (+19.5 %, not +52 %)**, **H2 NO**, **H3 YES**,
**H4 NO (descriptive)**. Adopted: **TensorRT fp16 encoder at 640 for the deployed carry** (G2). Not
adopted: `hiera-small` (G3), `base_plus` (rate). Stage 2 / INT8: **planned skip** via G4, now with a
measured ceiling of **+5 % over the adopted `trt` arm** (see the H1 back-solve above) rather than an
assumption.

Deployment note: adoption means the live carry must pass `--trt-encoder enc640.plan`, and the engine
is **shape-baked at 640** — the size-gated 1024 fallback EXP-1 kept for small/distant targets has
**no engine** and stays on the eager path until one is built.

**Deployed 2026-07-26T23:40Z** in `runners/carla_debug_ui.py`: the panel's bridge command is now
built by `_bridge_cmd(size)`, which appends `--trt-encoder` from `CARRY_TRT_PLANS = {640:
"enc640.plan"}` and appends nothing at any other size, so the 1024 fallback keeps working on the
eager path. Verified live — the spawned bridge reports `image_size=640, K=7 M=16 P=stock
enc=enc640.plan, ready`. **`runners/run_p62_flight.py` is deliberately left on the eager encoder**:
it is the frozen P6.2 showcase runner and its published median-IoU-0.960 parity number was measured
with that encoder; changing its config would invalidate a recorded result.

Registers as an **engineering measurement, not a thesis claim** (R-44), same as EXP-1/2/6/8: the
p-values above live in this README and in `runs/exp9/results.json`, and **not** in
`thesis/claims.json`.
