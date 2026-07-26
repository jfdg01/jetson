# EXP-8 — SAM2 memory-horizon levers (num_maskmem / obj-ptrs / ring), on Jetson

**Status:** PRE-REGISTERED 2026-07-26T18:47Z. Not run.
**Verdict:** TBD.
**Part:** VI (perception-stack, on-device). **Machine:** `jetson` (SAM2 runs on the Orin; the 3090 is NOT used).
**Power mode:** 15 W + `jetson_clocks` (the only real mode on this board — no MAXN_SUPER).
**Owner claim id (planned):** `EXP8-memory-horizon-elbow` — registered as an **engineering
measurement**, not a thesis claim (same standing as EXP-1/EXP-2/EXP-6 after R-44).

## Premise (the user's question, and why it is open)

User, 2026-07-26: *"there are levers I don't recall documenting: have we found the elbow of
n recent frames and up to m object pointers? and their performance cost?"*

Answer: **no.** Grep of the whole repo finds `num_maskmem` and `max_obj_ptrs_in_encoder` in
exactly one place — a docstring in `stream_carry.py:7-9` — and **zero** measurements. Every
carry knob we have swept is spatial (`image_size`, EXP-1) or spatial-crop (EXP-6). The
*temporal* horizon of the tracker has never been touched. EXP-1 found the resolution elbow;
this is the same question one axis over.

It matters because carry **drift** owns 8 of P5.19's 10 residual failures, and drift is a
memory phenomenon: the tracker re-anchors on whatever it remembers. P5.20 killed the
*capacity* lever (a bigger SAM2 recovered 0 cells) — capacity and horizon are different
axes, and the horizon one is untested.

### What the levers actually are (verified in the installed `sam2` package)

| Lever | Where | Stock | What it controls |
|---|---|---|---|
| `num_maskmem` (K) | `configs/sam2.1/sam2.1_hiera_t.yaml:87` | 7 | memory-bank slots: the conditioning frame + the K−1 most recent frames' mask-memory tensors |
| `max_obj_ptrs_in_encoder` (M) | `modeling/sam2_base.py:67` (default) | 16 | how many recent frames contribute a 256-d **object pointer** to memory attention |
| `PRUNE_AFTER` (P) | ours, `stream_carry.py:46` | 100 (32 in newer campaigns) | how many past frames' outputs + input tensors the streaming ring retains |

`memory_temporal_stride_for_eval=1` and `only_obj_ptrs_in_the_past_for_eval: true`, so at
eval the K−1 non-conditioning slots are literally frames n−1 … n−(K−1), and the pointers are
frames n−1 … n−(M−1). **Effective horizon at the deployed 640 / 5.76 Hz: ~1.0 s dense
(6 mask-memory frames) + ~2.8 s sparse (15 pointers)**, plus frame 0 forever. That is much
shorter than `PRUNE_AFTER=100` implies (17 s at 5.76 Hz).

### The internal contradiction this experiment resolves

`stream_carry.py:7-9` says far-past ring entries are *"dead weight"*. `D-R16.2`
(`docs/decisions/part4-end-to-end.md:682`) declined to shorten `PRUNE_AFTER` on the opposite
rationale — that the ring is *"a memory horizon, not just a buffer"* and shortening it would
change how long SAM2 can re-find an occluded target. Both cannot be true. The mechanics above
say the docstring is right and D-R16.2's rationale is wrong; Stage 0 below settles it
bit-exactly, for free.

## Hypotheses

- **H1 (ring, sharp and falsifiable):** `PRUNE_AFTER` is behaviourally inert above an exact
  boundary. At step n the model reads frames {n−15 … n−1} ∪ {0}; the ring pops j ≤ n−1−P, so
  **P ≥ 15 is bit-identical to P = 100** and **P ≤ 14 changes the output**. Predicting the
  boundary exactly is the test — a boundary anywhere else means the horizon arithmetic above
  is wrong, which invalidates the framing of H2/H3.
- **H2 (dense memory):** carry IoU is flat in K down to some elbow (guess K = 3–4) and
  collapses below it; the cost saved is memory-attention tokens, which at 640 is a small
  share of a 174 ms step (EXP-1 showed ≤512 is *overhead*-bound, so the encoder is not the
  only cost). Expected: **little or no rate win, and no IoU win** — the honest prior is that
  this is a null, like P5.15/P5.20/P5.21.
- **H3 (pointers):** M is nearly free in compute (256-d vectors), so the only reason to move
  it is accuracy. If longer sparse memory helps drift, M = 32 wins; if the tracker is
  re-anchoring on stale appearance, M = 4 wins. A flat curve says memory horizon is not the
  drift axis and closes the question.

## Constraints discovered while designing this (they shape the arms)

1. **K cannot be set through hydra.** `maskmem_tpos_enc` is a learned `nn.Parameter` sized
   `(num_maskmem, 1, 1, mem_dim)` (`sam2_base.py:133`) and `build_sam.py:167` loads the
   checkpoint with a strict `load_state_dict`, so `++model.num_maskmem=k` hard-fails on shape
   mismatch. **Workaround:** build at the native 7, then set `predictor.num_maskmem = k`
   after load.
2. **That workaround is index-correct.** The temporal-position embedding for a memory entry
   is indexed `num_maskmem - t_pos - 1` (`sam2_base.py:582`), which for the non-conditioning entries equals
   `t_rel - 1` (t_rel = 1 is the previous frame). The embedding slot is bound to *recency*,
   not to a buffer position, so lowering K post-load drops the oldest recency classes and
   leaves slots 0…K−2 attached to exactly the recency they were trained on. No re-indexing.
3. **K is downward-only.** K > 7 would index untrained embeddings. Sweep K ∈ {1 … 7} only.
   K = 1 = conditioning frame + pointers, no dense recent memory at all.
4. **M ≥ 2, hard floor.** The pointer sine embedding normalizes by
   `t_diff_max = min(num_frames, M) - 1` (`sam2_base.py:629`). M = 1 divides by zero.
5. **M is a confound as well as a lever.** Because M sets that normalizer, changing M
   *rescales the temporal encoding of every pointer*, not only how many there are. An M-arm
   is therefore "M pointers, off-distribution encoding", and M = 32 is doubly
   off-distribution (trained at 16). Recorded here, restated on any M verdict.
6. **On the 25-frame carry window, P never fires above 24.** N_STEPS=24 means indices 0…24,
   so P = 32 and P = 100 prune nothing. P is therefore **held at 32 in Stages 1–2** (no
   confound) and gets its own long-run stage.

## Arms

Baseline everywhere = the deployed config: `image_size=640` (EXP-1), K=7, M=16, P=32,
`facebook/sam2.1-hiera-tiny`, eager torch bf16, no TensorRT.

**Stage 0 — ring identity (cheap, gates D-R16.2).** 3 clips, `N_STEPS=120 @ STRIDE=2` so the
ring actually fires. P ∈ {8, 14, **15**, 16, 32, 100}. Compare **mask bits**, not IoU, against
P = 100. Prediction: {15, 16, 32, 100} byte-identical, {8, 14} not.

**Stage 1 — one-at-a-time sweeps (the elbow).** Full clip bank, N_STEPS=24, P=32.

| Arm | K | M | Note |
|---|---|---|---|
| `base` | 7 | 16 | deployed; the shared baseline for both sweeps |
| `K5` `K4` `K3` `K2` `K1` | 5,4,3,2,1 | 16 | dense-memory sweep |
| `M8` `M4` `M2` | 7 | 8,4,2 | pointer sweep, downward |
| `M32` | 7 | 32 | exploratory, doubly off-distribution (constraint 5) |

10 arms. No full factorial (6×4 = 24 arms is ~2 h of Orin time to answer a question one-at-a-
time already answers).

**Stage 2 — interaction + resolution transfer, only if Stage 1 finds a non-null.** The
best K and best M combined vs `base`, and the same pair at `image_size=1024`, to check the
elbow does not move with resolution. ≤4 arms. **Skipped entirely if Stage 1 is flat** — that
null is the result.

## Data

The EXP-1 bank, unchanged, so the numbers are directly comparable: UAV123 clips with a
contiguous GT window, **38 clips staged on host** (`bike1 bike3 car10-18 car1_s car2-9
truck2/3 wakeboard2-9` and the rest of the contiguous set), n ≥ 25 satisfied. Per clip:
seed = GT at the first frame with contiguous GT; carry `N_STEPS=24 @ STRIDE=11` (~8.8 s of
video). Clips are the unit of analysis, independent — **no deflation**.

**Scope caveat on units:** the levers are counted in *steps*, and at STRIDE=11 one step is
0.37 s of video, so K=7 spans ~2.2 s here vs ~1.0 s at the deployed 5.76 Hz. The elbow is
reported in steps; the conversion to seconds is carry-rate dependent and stated with it.

## Method / commands

Same shape as EXP-1: host stages (UAV123 GT is host-side) → frames streamed as JPEG over the
ssh-stdio bridge → carry runs **on the Orin** → host scores against GT.

```bash
# host: stage (reuses the EXP-1 plan format)
.venv-ft/bin/python experiments/2026-07-26-carry-memory-horizon/run_exp8.py stage --out runs/exp8

# Orin: ring identity, 3 clips x 120 steps, mask hashes
.venv-ft/bin/python experiments/2026-07-26-carry-memory-horizon/run_exp8.py ring --out runs/exp8

# Orin: the 10 Stage-1 arms
.venv-ft/bin/python experiments/2026-07-26-carry-memory-horizon/run_exp8.py carry --out runs/exp8 \
    --arms base,K5,K4,K3,K2,K1,M8,M4,M2,M32

# host: score + paired stats + figures + look-at-it overlays
.venv-ft/bin/python experiments/2026-07-26-carry-memory-horizon/run_exp8.py score --out runs/exp8
```

**Code to write after this pre-registration** (all small, all on the branch):

- `run_exp8.py` — fork of `2026-07-24-resolution-decoupled-carry/run_exp1.py` (294 lines,
  stage/carry/score already there); the arm identifier becomes `size:K:M:P` instead of a bare
  size, plus the `ring` subcommand and the re-find metric.
- `carry_ssh_bridge.py` on the Orin gains three flags: `--num-maskmem` (applied **post-load**
  per constraint 1), `--max-obj-ptrs` (hydra override, safe), `--prune-after` (passed to
  `StreamCarry(..., prune_after=)`, which already accepts it).
- The bridge reports `torch.cuda.max_memory_allocated()` and `ru_maxrss` per clip in the
  init ack, so memory is measured rather than derived.

## Metrics & statistics

Per clip, per arm: per-step IoU vs GT, `median_iou`, `held_frac` (steps with IoU ≥ 0.25),
`final_iou`, on-device `median_ms` / `carry_hz`, peak CUDA bytes, peak RSS.

- **Primary (accuracy):** paired **Wilcoxon signed-rank** on per-clip `median_iou`
  (arm − `base`) with the 95% CI of the paired median delta, per arm. Non-inferior if the CI
  excludes a 0.05 regression (the EXP-1 band).
- **Secondary:** per-clip PASS = `median_iou ≥ 0.25`; **McNemar exact two-sided** vs `base`.
  Report `min_discordant_for_significance` (needs b+c ≥ 6) so an underpowered tie is labelled
  as one, not as a null. `grounding/stats.py`.
- **Horizon-specific (the metric a mean IoU would hide):** **re-find rate** — of the steps
  where the carried box is lost (empty mask or IoU < 0.25), the fraction where the track
  returns to IoU ≥ 0.25 within 5 steps. This is exactly what D-R16.2 feared losing, so it is
  measured, not assumed. Reported per arm with its Wilson CI.
- **Cost:** median ms/step and peak CUDA MB per arm, and for the ring stage the retained-frame
  arithmetic checked against measured RSS. Derivation to check (**estimate**): `_prep` keeps a
  float32 3×S×S CPU tensor per retained frame = 4.9 MB at S=640, 12.6 MB at S=1024, so
  P: 100→16 should free ~410 MB at 640 / ~1.06 GB at 1024 per tracked candidate. If that
  holds it is the real content of the R-16 OOM at N=2, which was attributed to the ring
  without this decomposition.
- **Multiplicity:** Stage 1 is 9 comparisons against a shared baseline. Holm within the
  EXP-8 family; the family is registered in `thesis/claims.json` alongside the claim.

## Gates

- **G1 (ring):** bit-identity boundary lands exactly at P = 15 → adopt **P = 16** everywhere
  and supersede D-R16.2 with measured evidence (with the freed memory quantified). Boundary
  elsewhere → the horizon arithmetic is wrong; stop and re-derive before reading H2/H3.
- **G2 (K):** adopt the smallest K whose IoU delta CI excludes −0.05 **and** whose re-find
  rate is non-inferior **and** which buys ≥5% median ms or ≥5% peak MB. No measurable saving
  → keep K = 7 and record "the dense-memory lever is free but pointless", which is the
  answer to the user's question.
- **G3 (M):** M = 32 adopted only if it *wins* accuracy (CI excludes 0) and survives Holm —
  and the verdict carries the off-distribution caveat (constraint 5). A flat M curve closes
  the sparse-horizon question.
- **Stage 2 runs only if G2 or G3 fires.**

## Look-at-it (mandatory)

The scorer draws GT (green) + carried box (cyan) on the real frame for every step. Before any
verdict: open with the Read tool (a) a mid-run overlay for a sample of clips at `base` and at
the most aggressive surviving arm, and (b) **every clip where an arm flips PASS→FAIL vs
`base`** — a horizon lever is supposed to fail by drifting, and drift is a thing you look at,
not a number. Mechanical asserts in the scorer: mid overlay <99% one colour (failed render);
carried boxes not byte-identical across steps (dead feed); for the ring stage, the identity
comparison is on mask bytes so a silently-empty mask cannot masquerade as agreement. No frame
captured → INVALID.

## Proof deliverables (`proof/`, committed, from `make_proof.py` on `runs/exp8/results.json`)

1. `horizon_elbow.png` — twin-axis: median-of-median IoU and on-device ms/step vs K, and the
   same vs M. The elbow figure, EXP-1's `elbow_iou_hz.png` one axis over.
2. `ring_identity.png` — mask-agreement fraction vs P with the predicted step at 15, plus
   measured peak RSS. Numbers are the point, so: figure.
3. `refind_and_drift.png` **or** `drift_<clip>.mp4` — whichever the result calls for: a figure
   of per-arm re-find rate if the levers are flat, a clip of the carry drifting at the arm
   that breaks if one of them is not. Behaviour is the point in the second case, so: clip.

## Estimates (mark actuals on completion)

- **Stage 0:** 6 arms × 3 clips × 120 steps × ~174 ms ≈ 6 min carry + overhead → **~10 min**.
- **Stage 1:** 10 arms × 38 clips × 24 steps × ~174 ms ≈ 26 min carry; EXP-1's overhead ratio
  (init, JPEG, ssh framing, service restart per arm) roughly doubles it → **~50–70 min**.
- **Stage 2 (conditional):** ≤4 arms, 1024 is 3.7× slower per step → **~30 min** if it runs.
- **Total: ~1.5 h**, ~2 h if Stage 2 fires.
- **Expected IoU:** K flat from 7 down to ~3, losing <0.02; K ≤ 2 loses 0.05–0.15. M flat
  across 2…32 within ±0.02. All estimates.
- **Expected rate:** K = 1 buys **<10%** of the step at 640 (memory cross-attention is a
  minority of a step that EXP-1 showed is partly overhead-bound); M buys ~0. Estimate — if
  K = 1 buys ≥25% the cost model above is wrong and that is worth recording.
- **Expected memory:** K barely moves peak CUDA (mask memory is 40×40×64 bf16 ≈ 205 KB per
  slot at 640); the ring is where the megabytes are. Estimate.
- **Most likely overall outcome, stated up front so a null is not spun:** H1 confirmed
  (a real, free win: shorter ring, ~410 MB back, D-R16.2 superseded), H2 and H3 both flat
  (the memory horizon is not the drift axis). That is a publishable negative — it removes two
  levers from the drift search and joins P5.15 / P5.20 / P5.21 in bounding what carry tuning
  can do.

## Results (TBD)

| Arm | K | M | median-of-median IoU | Δ vs base [CI95] | mean held_frac | PASS/38 | McNemar b/c, p | re-find | ms/step | peak CUDA MB |
|---|---|---|---|---|---|---|---|---|---|---|
| `base` | 7 | 16 | | — | | | — | | | |
| | | | | | | | | | | |

**Ring identity (Stage 0):**

| P | mask-identical vs P=100 | median_iou | peak RSS MB |
|---|---|---|---|
| | | | |

## Status / next step

PRE-REGISTERED, not run. Next: write `run_exp8.py` + the three bridge flags, push the bridge
to `~/sam2-bench/` on the Orin, run Stage 0 (10 min, settles G1 and D-R16.2 on its own), then
Stage 1. Ledger rows (RESULTS / QUESTIONS / DECISIONS, Part VI) and `proof/` on completion.
