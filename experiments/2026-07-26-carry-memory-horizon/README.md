# EXP-8 — SAM2 memory-horizon levers (num_maskmem / obj-ptrs / ring), on Jetson

**Status:** DONE 2026-07-26T22:35Z. Stage 0 + Stage 1 run; Stage 2 vacuous, not run (see gates).
**Verdict:** **H1 CONFIRMED at the predicted frame, H2 NO, H3 NO.** The ring was the only real
lever: `PRUNE_AFTER=100` was holding 85 frames the model provably never reads, and dropping it to
a derived 16 returns **~670 MB of host RAM** with **bit-identical** output (360/360 steps sha1-equal,
boundary measured at exactly the predicted P=15). Neither memory-horizon lever is worth pulling:
**M is inert on every axis** (2…32, all p ≥ 0.26, zero PASS flips, zero discordant pairs, ±0.6 ms) —
the sparse object-pointer horizon is not doing work at this timescale; **K is real but a bad trade**
— monotone, statistically detectable, and it never once wins a clip (`b=0` in all five arms), buying
at most **11.2% of the step for −7.3% median IoU and −4 PASS clips** at K=1. Against the resolution
lever measured in EXP-1 (2.46× rate for −0.6% IoU) that exchange rate is not close. **Keep K=7, M=16;
adopt the derived ring.** The memory horizon is not the drift axis — EXP-8 joins P5.15/P5.20/P5.21
in bounding what carry tuning can do.
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

**Code written for this campaign** (as-built, 2026-07-26T19:10Z):

- `run_exp8.py` — fork of `2026-07-24-resolution-decoupled-carry/run_exp1.py`; arms are named
  (`base`, `K5`…`K1`, `M8`…`M2`, `M32`) instead of bare sizes, plus the `ring` subcommand, the
  re-find metric, Holm over the arm family, and a look-at-it pass that overlays **every**
  PASS-flip clip on top of the 3-clip sample.
- `experiments/2026-07-24-p62-showcase/carry_ssh_bridge.py` gained four flags, all defaulting
  to 0/off so every pre-EXP-8 caller (the live CARLA panel, EXP-1/2/6 replays) is
  **bit-identical**: `--num-maskmem` and `--max-obj-ptrs` (both applied **post-load** as
  attributes — `predictor.num_maskmem` / `predictor.max_obj_ptrs_in_encoder` are read at
  runtime in `sam2_base.py:540,588`, so no hydra override and no strict-load failure),
  `--prune-after` (into `StreamCarry(..., prune_after=)`, which already accepted it), and
  `--mask-hash` (sha1 of the video-res mask per step, for the Stage-0 bit-identity test).
  The step reply also gained `cuda_mb` / `rss_mb` (peak reset at each `init`), so memory is
  measured, not derived. Deployed to `~/sam2-bench/` on the Orin.

**Run hygiene:** a stale `carry_ssh_bridge.py` from an earlier CARLA-panel session was found
resident on the Orin (36 min idle, holding VRAM) and killed ~1 min into the first ring arm.
The `ringP8` arm's first clip therefore ran under contention — noted, and its timing is
excluded from any rate comparison (the ring stage's numbers of interest are mask identity and
RSS, not ms).

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

All four delivered, from `make_proof.py` on `runs/exp8/{results,ring,plan}.json` + `carry_*.json`.

1. **`ring_identity.png`** — Stage 0. Left: % of steps whose video-resolution mask is sha1-identical
   to the unbounded `P=100` ring, vs P, with the predicted boundary (15) and the measured one
   overlaid — they coincide. Right: what the retained frames cost, plotted as **RSS growth over the
   run** (the ring's own cost) with peak RSS shown faded behind it, because peak carries a
   per-process baseline that has nothing to do with the ring. Config: 3 clips × 120 steps @ stride 2,
   K=7, M=16, `image_size=640`, Orin 15 W + `jetson_clocks`.
2. **`horizon_elbow.png`** — Stage 1, the elbow figure (EXP-1's `elbow_iou_hz.png` one axis over).
   Median-of-median IoU and on-device ms/step vs K (left, M=16 held) and vs M (right, K=7 held),
   n=38 clips. **Both panels share one ms axis on purpose**: autoscaled, the M panel's 0.6 ms of
   run-to-run noise fills the frame and reads as a dramatic effect; on K's real scale it is the flat
   line it actually is. Shows K's shallow latency slope against a nearly-flat accuracy curve, and M
   inert on both axes.
3. **`refind_by_arm.png`** — Stage 1. Per-arm re-find rate (fraction of lost steps recovered within
   5 steps) with Wilson CI95 and the raw n/N on each bar. The metric D-R16.2 specifically feared
   losing; no arm's CI falls below base's. Note K1's higher rate sits on a nearly double-sized
   denominator — it loses more often, not less.
4. **`drift_building3.mp4`** — Stage 1, behaviour rather than numbers, so a clip. Side-by-side
   `base` / `K5` / `K1` on the same frames of `building3`, GT green, carry cyan, per-panel live IoU.
   Watch the K5 panel bleed off the small target building onto the adjacent mosque while base holds.

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

## Results

### Stage 1 sweep — **H2 NO, H3 NO**

Run 2026-07-26T20:05Z–21:58Z on the Orin, 15 W + `jetson_clocks`, `image_size=640`,
`PRUNE_AFTER=32`, 38 UAV123 clips × 24 steps @ stride 11, one service restart per arm.
Δ is **arm − base** on per-clip `median_iou` (negative = the shorter horizon is worse), Wilcoxon
signed-rank + bootstrap CI95, Holm over the 9-comparison EXP-8 family. McNemar is exact two-sided
on PASS (`median_iou ≥ 0.25`); **b = clips that flip PASS→FAIL, c = clips that flip FAIL→PASS**.

| Arm | K | M | median-of-median IoU | Δ vs base [CI95], p (Holm) | mean held_frac | PASS/38 | McNemar b/c, p | re-find | ms/step | peak CUDA MB |
|---|---|---|---|---|---|---|---|---|---|---|
| `base` | 7 | 16 | 0.811 | — | 0.859 | 32/38 | — | 3/129 (2.3%) | 173.4 | 506.7 |
| `K5` | 5 | 16 | 0.779 | −0.0035 [−0.0087, 0.0000], p=0.0087 (Holm 0.059, keep) | 0.842 | 31/38 | b=1/c=0, p=1 | 5/144 (3.5%) | 166.5 | 506.7 |
| `K4` | 4 | 16 | 0.777 | −0.0029 [−0.0119, 0.0000], p=0.0084 (Holm 0.059, keep) | 0.838 | 31/38 | b=1/c=0, p=1 | 12/148 (8.1%) | 163.8 | 506.7 |
| `K3` | 3 | 16 | 0.773 | −0.0021 [−0.0174, 0.0000], p=0.0116 (Holm 0.059, keep) | 0.833 | 31/38 | b=1/c=0, p=1 | 9/152 (5.9%) | 161.2 | 506.7 |
| `K2` | 2 | 16 | 0.767 | −0.0076 [−0.0250, 0.0000], p=0.0025 (Holm 0.020, **reject**) | 0.820 | 31/38 | b=1/c=0, p=1 | 5/164 (3.0%) | 156.4 | 506.7 |
| `K1` | 1 | 16 | 0.752 | −0.0175 [−0.0321, −0.0049], p=2.0e-05 (Holm 1.8e-04, **reject**) | 0.728 | **28/38** | b=4/c=0, p=0.125 | 27/248 (10.9%) | **153.9** | 506.7 |
| `M8` | 7 | 8 | 0.802 | 0.0000 [−0.0006, 0.0000], p=0.259 (Holm 1, keep) | 0.856 | 32/38 | b=0/c=0, undefined | 6/131 (4.6%) | 174.0 | 506.7 |
| `M4` | 7 | 4 | 0.824 | 0.0000 [−0.0008, +0.0006], p=0.86 (Holm 1, keep) | 0.855 | 32/38 | b=0/c=0, undefined | 7/132 (5.3%) | 173.8 | 506.7 |
| `M2` | 7 | 2 | 0.807 | +0.0001 [−0.0004, +0.0023], p=0.896 (Holm 1, keep) | 0.849 | 32/38 | b=0/c=0, undefined | 3/138 (2.2%) | 173.6 | 506.7 |
| `M32` | 7 | 32 | 0.810 | 0.0000 [0.0000, 0.0000], p=0.748 (Holm 1, keep) | 0.859 | 32/38 | b=0/c=0, undefined | 3/129 (2.3%) | 174.0 | 506.7 |

**Peak CUDA is 506.7 MB in every single arm, to the decimal.** Neither lever buys one byte of
device memory — as estimated (a mask-memory slot at 640 is ~205 KB; the megabytes were always in
the host-side ring, which is Stage 0's finding).

**M is inert (H3 NO).** Every M arm is a null on the continuous metric (p ≥ 0.259) and has **zero
discordant pairs** — not one clip changes PASS status anywhere from M=2 to M=32, so McNemar is
undefined rather than non-significant. The only clip that moves at all is `car13` (0.639 at base to
0.475 at M=2), and the overlay shows why: it is a ~10 px target at high nadir where the carry box
and GT coincide at that scale, so the change is mask-boundary jitter on a handful of pixels, not a
lost track. M=32 does not win (CI [0.0000, 0.0000]), so **G3 does not fire**. Caveat as
pre-registered (constraint 5): M > 16 is off-distribution for the trained pointer embedding, and
this measures it as *harmless*, not as *tested at its design point*.

**K is real, monotone, and a bad trade (H2 NO).** K is not flat — it is the one lever that moves
the continuous metric, and it moves it in one direction: `b=0` in **all five** K arms, i.e. a
shortened dense memory **never once wins a clip**. But the effect is tiny where it is significant
and catastrophic where it is not. K=5…K=2 each cost exactly one clip (`building3`) and buy
4–10% of the step; K=1 costs **four** clips and 13 points of held_frac. Per-clip, the K family is a
cliff and not a slope: `car7` is perfect through K=2 (0.894…0.903) then hits **exactly 0.000** at
K=1, and `car13`/`truck3` do the same.

Three distinct failure mechanisms, all verified by opening the overlay (not inferred from the number):

- **Mask leak onto a neighbour** — `building3` at K=5: the carry box has bled off the small target
  building onto the adjacent mosque (`held_frac` 0.96 at base to 0.29 at K5).
- **Identity swap onto a same-class distractor** — `car7` at K=1: the box has jumped to a *different*
  silver car entering the roundabout while GT stays on the original. Disjoint boxes, hence IoU
  exactly 0.000. This is precisely what the 7-frame dense memory is paying for.
- **Mask collapse to empty** — `car13` and `truck3` at K=1: GT is on the target and there is **no
  carried box at all**. Both are tiny high-nadir targets.

None of the three is drift. The pre-registration expected a horizon lever to "fail by drifting";
it does not — it fails by losing the object's identity outright.

**Re-find is non-inferior everywhere**, which is the specific fear D-R16.2 recorded. K=1's rate is
*higher* than base (10.9%, Wilson CI [7.6, 15.4] vs base 2.3% [0.8, 6.6]) — but on a nearly
double-sized denominator: it enters the lost state far more often and recovers from those shallow
losses, which is not the same as tracking better. No arm's re-find CI falls below base's.

### Gates

- **G1 (ring): FIRED, ADOPTED.** Boundary at exactly P=15 as predicted. `PRUNE_AFTER` 100 to a
  derived 16, D-R16.2's rationale superseded by measurement, ~670 MB freed. Landed in
  `stream_carry.py:read_window` with `tests/test_stream_carry_window.py`.
- **G2 (K): FIRED ON THE LETTER, NOT ADOPTED — the gate was mis-specified, and it is recorded here
  rather than quietly retuned.** K=1 satisfies all three pre-registered conditions: its CI
  [−0.0321, −0.0049] excludes −0.05; its re-find is non-inferior; it buys 11.2% of median ms (≥5%).
  Adopting it anyway would ship a config that **loses four clips outright**, three of them to
  total loss. The flaw is that the −0.05 margin was written against *median-of-median IoU*, a
  statistic that is by construction insensitive to a minority of clips going to zero — the median
  clip barely moves while the tail dies. PASS is the metric the deployment cares about and it was
  not in the gate. **Decision: keep K=7.** Recording the gate as fired-and-rejected, with the
  reason, is the honest version; silently rewriting the threshold after seeing the data is not.
- **G3 (M): DID NOT FIRE.** M=32 does not win accuracy (CI [0.0000, 0.0000], p=0.748). Flat M
  curve; the sparse-horizon question is closed. Keep M=16.
- **Stage 2: NOT RUN, vacuous.** The pre-registration gates Stage 2 on "G2 or G3 fires". G2 fired
  on the letter, but since nothing was adopted, the interaction cell Stage 2 would test (best K ×
  best M) *is* `base` at K=7/M=16 — already measured, twice. Running it would re-measure the
  baseline at 1024 and answer no open question. Deviation from pre-registration, stated rather
  than skipped.

### Estimate vs actual

| Quantity | Estimated | Actual |
|---|---|---|
| Stage 0 runtime | ~10 min | ~11 min |
| Stage 1 runtime | ~50–70 min | **~30 min** (~175 s/arm; the overhead-doubling assumption was too pessimistic) |
| Stage 2 runtime | ~30 min if it fires | not run (vacuous) |
| K IoU: flat 7→~3 losing <0.02 | estimate | **correct** (−0.0021…−0.0035, but *detectably* non-zero, which was not expected) |
| K ≤ 2 loses 0.05–0.15 | estimate | **too pessimistic on the median** (−0.008 at K2, −0.018 at K1) and **too optimistic on the tail** (K1 loses 4 clips outright) |
| M flat across 2…32 within ±0.02 | estimate | **correct**, and tighter than estimated (±0.0001) |
| K=1 buys <10% of the step | estimate | **11.2%** — marginally over, cost model essentially right |
| K barely moves peak CUDA | estimate | **correct to the decimal**: 506.7 MB in all 10 arms |
| Ring cost | ~4.9 MB/frame | **8.1 MB/frame** (~670 MB freed, not ~410 MB) |
| "Most likely outcome: H1 confirmed, H2 and H3 both flat" | pre-stated | **H1 and H3 as predicted; H2 half-wrong** — K is not flat, it is a real monotone effect that is simply not worth its price. Recorded because a pre-stated expectation that misses is content. |

### Ring identity — Stage 0, **H1 CONFIRMED at the predicted frame**

Run 2026-07-26T19:06Z on the Orin, 15 W + `jetson_clocks`, `image_size=640`, K=7, M=16,
3 clips × 120 steps @ stride 2 (`bike1`, `bike3`, `boat2`), sha1 of the video-resolution mask
per step, 360 comparisons per row.

| P | mask-identical vs P=100 | median_iou | RSS growth over the run | peak RSS | peak CUDA | ms/step |
|---|---|---|---|---|---|---|
| 8 | 12.50% | 0.910 | 31.2 MB | 1274.5 MB† | 505.3 MB | 175.2 |
| 14 | 21.94% | 0.908 | 194.8 MB | 2013.5 MB | 505.3 MB | 172.8 |
| **15** | **100%** | 0.909 | 164.3 MB | 2016.8 MB | 505.3 MB | 173.0 |
| 16 | 100% | 0.909 | 182.3 MB | 2045.7 MB | 505.3 MB | 172.8 |
| 32 | 100% | 0.909 | 341.8 MB | 2172.9 MB | 509.6 MB | 172.9 |
| 100 (deployed) | 100% | 0.909 | 853.3 MB | 2844.7 MB | 529.6 MB | 173.8 |

† `ringP8` ran first and its process baseline was 1243 MB of RSS at step 0 against ~1822 MB
for every other arm — a 580 MB offset present *before* the ring filled, so its **peak** is not
comparable across arms (see Run hygiene). Its **growth** is, and is the smallest, as expected.
This is why the table and the figure lead with growth: peak RSS carries a per-process baseline,
growth is the ring's own cost.

**Read of Stage 0:**

- H1 predicted the identity boundary at **P ≥ 15** from the arithmetic alone (at step *n* the
  model reads {*n*−15 … *n*−1} ∪ {0}; `StreamCarry` has popped {*j* ≤ *n*−1−P}; identity needs
  *n*−1−P < *n*−15). Measured lowest identical P = **15**, to the frame, with all 360 steps
  bit-identical — and identity collapses to 21.9% one frame below. A pre-registered point
  prediction landing exactly is the strongest form this result could take.
- Everything the ring holds above 15 frames is **provably** dead weight — not "approximately
  equivalent", *bit-identical output*. `PRUNE_AFTER = 100` retains 85 such frames.
- Marginal cost of a retained frame: (853.3 − 164.3) MB / 85 frames = **8.1 MB/frame** at
  `image_size=640`. Estimate-vs-actual: I predicted ~4.9 MB/frame from the retained float32
  3×640×640 input tensor alone, so ~410 MB freed; the measured cost is **1.65× that**, the
  balance being the retained `non_cond_frame_outputs` entry (maskmem features + pos-enc +
  pred_masks + obj_ptr) and allocator slack. **P = 100 → 16 returns ~670 MB of host RAM**
  (growth 853.3 → 182.3), on a board with 8 GB shared between CPU and GPU.
- The saving is **steady-state, not a leak bound**: at P the ring saturates at P frames, so
  this is the flat cost a long flight pays forever.
- Accuracy is flat at 0.908–0.910 across *every* P, including P = 8 where only 12.5% of steps
  are bit-identical. Rate is flat at ~173 ms. So the ring buys nothing below the horizon either
  — it is not a speed/accuracy knob at all, in either direction.
- This **refutes the rationale of `D-R16.2`** (`docs/decisions/part4-end-to-end.md:682`, "a
  memory horizon, not just a buffer" — that shortening the ring would shorten how long SAM2 can
  re-find an occluded target). Above 15 the ring is not a horizon; SAM2's own horizon is
  `max_obj_ptrs_in_encoder`, and the ring cannot extend it. **G1 satisfied.**
- Benign warning present identically in every arm, so no confound: SAM2 skips
  `fill_holes_in_mask_scores` because the `_C` CUDA extension is not compiled in the Orin venv
  (`sam2_video_predictor.py:786`).

## Status / next step

**DONE.** Stage 0 and Stage 1 run on the Orin, scored, figures + clip committed under `proof/`,
ledger rows appended (RESULTS / QUESTIONS `RQ-EXP-8` / DECISIONS, Part VI). The one adopted change
(`PRUNE_AFTER` to a derived 16) is live in `stream_carry.py` and covered by
`tests/test_stream_carry_window.py`.

Follow-ups this campaign deliberately does **not** claim, for whoever picks it up:

- The ~670 MB freed is measured as host RSS on the bench harness, not as headroom recovered in a
  full flight process. Nothing here shows a workload that previously OOMed now fits.
- K was swept only at `image_size=640`. The K/resolution interaction is exactly the Stage 2 cell
  that went vacuous; if a future campaign needs the last 10% of the step, K at 1024 is unmeasured.
- The three K=1 failure mechanisms (leak / identity swap / mask collapse) are each observed on one
  or two clips. They explain the numbers; they are not themselves powered results.
