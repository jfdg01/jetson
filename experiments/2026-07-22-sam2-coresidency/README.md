# R-16 — What a 2B VLM plus a promptable video tracker actually cost, co-resident, on 8 GB at 15 W

**Status:** COMPLETE · **Opened:** 2026-07-22T23:05Z · **Closed:** 2026-07-23T01:20Z · **Branch:** `main`
**Part:** IV. The registry id is `P4-R16-carry-rate-1024` and all three ledger rows were appended
under Part IV, so Part IV is the filing. An earlier draft of this line said Part III on the reasoning
that the campaign is device characterisation re-measuring a constant every Part IV/V campaign
consumed; that reasoning survives as a *writing* note, not a filing one — the thesis text belongs in
the object-permanence chapter next to E1, which is the number R-16 corrects, while the ledger entry
stays in Part IV. One campaign, one filing, stated once.
**Machine:** Jetson Orin Nano 8 GB, 15 W + `jetson_clocks`. Every number here is on-device. · **Task:** R-16

## Why this exists (context to start cold)

The select arc's VLM half has always been real: `evaluate_roi` is backend-agnostic and
`JetsonBackend` genuinely boots `llama-server` over `ssh jetson`, so every P5.16/P5.18/P5.19
discovery call was on-device inference. **The one simulated component in the whole arc is the
SAM2 carry**, rate-capped to a hardcoded constant — `replay_e18.py:46` `CARRY_HZ = 6.15`, and
`select_p53.py:84` `CAND_HZ = CARRY_HZ / 2.0`.

That constant has two problems, and the second is much larger than the first:

1. **The `/2` for two candidates is optimistic.** Two independent SAM2 states do not run at half
   the single-state rate; they run slower than that.
2. **The 6.15 Hz was measured at `image_size` 768 with a TensorRT encoder, and the campaigns that
   consume it run the carry at the stock SAM2.1 `image_size` 1024 in eager PyTorch**
   (`SAM2VideoPredictor.from_pretrained`, no override). E1 recorded that 1024 "needs 1.9x" and
   never gated it; E18 miscites the cap's provenance as "640x480". So the deployed size and the
   evaluated size differ, and **each borrowed the favourable half of the other's measurement** —
   768 is the fast one, 1024 the accurate one (`P3-carry-OP768-accuracy`, exact p = 0.014).

**This campaign is not here to rescue the select result.** That result is not there to be rescued
(R-5). Re-measuring a dead claim on the right hardware buys nothing. It is here because the
device characterisation is a first-class result in its own right, and it is publishable whichever
way the numbers fall: *what does a 2B VLM plus a promptable video tracker actually cost,
co-resident, on 8 GB at 15 W?* That is the question the thesis premise ("it runs on the board")
rests on, and it has never been answered as a measurement.

**Everything below is measured fresh.** A prior audit session left bench numbers on the board
(`~/sam2-bench/bench_*.json`) suggesting solo-1024 runs at 2.68 FPS. Those are second-hand, from
a session never repeated, and REMEDIATION explicitly requires re-measurement before publication.
They are used here only to size the estimates — never quoted as results.

## The gate, and why it comes first

`multi_carry_bench.py` offers a `bat` mode: instead of N independent SAM2 states, one state
carrying N `obj_id`s. The encoder then runs **once** per frame and only memory-attention plus the
mask decoder repeat per object. If that is free, it is the whole ballgame for multi-candidate
carry — the prior audit measured `tick = 70 + 92n` ms batched against `162n` separate.

**But it is only a valid lever if the masks are the same.** SAM2 has two cross-object mechanisms
that exist precisely because objects in one state can interact:

```
sam2_video_predictor.py:26    non_overlap_masks=False
sam2_base.py:63               non_overlap_masks_for_mem_enc=False
```

Both default `False` and `sam2.1_hiera_t.yaml` overrides neither, so on a reading of the source
the batched masks should be identical. **A reading of the source is not a measurement.** If
either constraint is live — or if any other batch-level coupling exists — then a batched carry
tracks something different from what every Part IV/V campaign tracked, the speedup is not
comparable, and the lever dies. So the parity test gates everything downstream.

**G0 — batched/separate mask parity.** Same clip, same boxes, `image_size` 1024, n=2 and n=3.
Per object, per frame, IoU between the batched mask and the separate-state mask.

- **PASS:** median per-object mask IoU >= 0.99 **and** no single frame below 0.95.
- **FAIL:** anything less. Batching is then reported as a *different tracker*, not a faster one,
  and M2's `bat` arm becomes a curiosity rather than a deployment option.

## Design

**Clip:** `~/sam2-bench/clip`, 100 frames (`0000395.jpg`…), a 1024x540 aerial night intersection.
Three boxes picked in the prior session **by looking at frame `0000400.jpg`** — 1 = dark car (the
E1 box), 2 = blue car right of it, 3 = black SUV lower centre. The frame is re-opened and the
boxes re-drawn as this campaign's first proof deliverable, because a box list nobody rendered is
a hypothesis (the "look at it" rule).

**Unit of measurement:** one *tick* = every candidate advances one frame. `per_cand_hz` is what
`CAND_HZ` in the harness models, so it is the number the correction applies to. First 5 ticks
dropped as warm-up; median reported, not mean.

**Matrix.** All at 15 W + `jetson_clocks`, `facebook/sam2.1-hiera-tiny`, bf16 autocast,
`offload_video_to_cpu=True` (what the harness does).

| id | what varies | why |
|---|---|---|
| **M1** rate decomposition | n=1 x {768 eager, 768 TRT, 1024 eager, 1024 TRT*} | splits the 6.15 Hz → deployed-rate drop into **size** vs **runtime**. Without this the correction is one number with two causes. |
| **M2** candidate scaling | n=1,2,3 x {sep, bat} at 1024 | the `/N` assumption, and what batching buys if G0 passed |
| **M3** co-residency under real load | 1024 sep n=1, with llama-server (a) absent (b) idle-resident (c) **serving real grounding calls** | E1's "co-residency costs 0 FPS" was measured against an *idle* server. Both directions are recorded: SAM2's tick **and** the VLM's wall latency. |
| **M4** memory ceiling | `MemAvailable` + swap at every cell above | the prior audit's claim is that **memory, not rate, is the binding constraint**. This tests it. |

*The 1024 TRT cell needs an encoder plan that does not exist — `enc768.plan` is built for 768.
**That is itself a finding**: the TensorRT speedup which justified the published 6.15 Hz is not
available at the size the campaigns actually deploy unless someone exports a 1024 plan. Exporting
one (ONNX + `trtexec`) is attempted as a stretch arm; if it costs more than ~40 min it is dropped
and recorded as NOT RUN with the reason, not silently omitted.

**What is deliberately not done.** No Part V select result is re-run. No claim in `claims.json`
gets its verdict changed by this campaign — what changes is the *stated cost* of the deployed
system, and any published number that was generated under an optimistic stride gets a caveat
pointing here, not a new p-value.

## Research questions (pre-registered)

- **RQ-R16.0 (gate):** does a batched N-`obj_id` SAM2 state track the same masks as N separate
  states at `image_size` 1024? **Test:** per-object per-frame mask IoU, thresholds above.
- **RQ-R16.1 (the correction):** what is the real per-candidate carry rate at the **deployed**
  `image_size` 1024, and by what factor does it differ from the `CARRY_HZ = 6.15` constant every
  Part IV/V campaign emulated? **Decomposed** into size and runtime by M1.
- **RQ-R16.2 (scaling):** is per-candidate rate `rate(1)/N`, better, or worse? The harness assumes
  exactly `/N`.
- **RQ-R16.3 (the binding constraint):** co-resident on 8 GB, does the system run out of **rate**
  or out of **memory** first, and at what N?
- **RQ-R16.4 (co-residency, honestly):** under *real* grounding load rather than an idle server,
  what does each half cost the other — SAM2's tick, and the VLM's latency tail?

## Estimates (pre-registered — record divergence)

| quantity | estimate | basis |
|---|---|---|
| G0 gate | **PASS** | both non-overlap flags default `False`; but this is a source reading, which is exactly what a gate is for |
| M1 768 TRT n=1 | 6.0-6.3 Hz | should reproduce E1's 6.15 |
| M1 1024 eager n=1 | 2.4-2.9 Hz | prior audit's 2.68, treated as an estimate |
| **CARRY_HZ correction factor** | **2.0-2.6x optimistic** | if both of the above land |
| M2 per-cand at n=2, sep | 1.2-1.5 Hz | roughly `rate(1)/2`, slightly worse |
| M2 batched advantage at n=2 | 1.3-1.6x over sep | encoder amortised once |
| M3 SAM2 tick under real VLM load | within 5% of solo | E1 found SAM2 immune; expected to hold |
| M3 VLM tail under SAM2 load | **2-3x worse max** | the prior audit's 1513→3367 ms, treated as an estimate |
| M4 binding constraint | **memory** | 4.25 GB server + ~675 MB/state on 7.6 GB total |
| total runtime | 2-3 h incl. the TRT stretch arm | ~15 bench cells at 100 frames |

**Prediction worth writing down because it may be wrong:** the headline correction is roughly
**2.3x**, not the ~7% the `/2`-assumption story implies — because the dominant error is the
768-vs-1024 size mismatch, not the multi-candidate division. If instead 1024 eager lands near
6 Hz, then the deployed configuration was fine all along and this campaign's contribution is a
clean co-residency characterisation with no correction attached. The estimate most likely to be
embarrassing is the batched-advantage one: it assumes the encoder is the dominant cost at 1024,
and at that size memory attention over a 100-frame ring may well dominate instead.

## Commands

```bash
ssh jetson 'sudo nvpmodel -m 1 && sudo jetson_clocks'   # 15 W, see note below
# G0 parity gate
scp experiments/2026-07-22-sam2-coresidency/parity_gate.py jetson:~/sam2-bench/
ssh jetson 'cd ~/sam2-bench && .venv/bin/python parity_gate.py --frames clip --n 2 --image-size 1024'
# M1/M2/M4 -- one process per cell, so max_memory_allocated/MemAvailable start clean
scp experiments/2026-07-22-sam2-coresidency/carry_bench.py jetson:~/sam2-bench/
ssh jetson 'cd ~/sam2-bench && TQDM_DISABLE=1 .venv/bin/python carry_bench.py \
    --frames clip --n 2 --mode sep --image-size 1024 --out m12.jsonl'
# M3 -- deployed StreamCarry co-resident with the deployed VLM under real grounding load.
# run_m3.py restarts llama-server before EVERY cell; see the Results note on why.
scp experiments/2026-07-22-sam2-coresidency/{cores_bench.py,run_m3.py} jetson:~/sam2-bench/
# the carry under test is the DEPLOYED StreamCarry, copied unmodified -- verified by md5
# e2b1fdb09f6ab4e16c20b47b80f6aa41 on both sides, so M3 measures the real thing
scp experiments/2026-07-01-temporal-acquire-carry/stream_carry.py jetson:~/sam2-bench/
ssh jetson 'cd ~/sam2-bench && .venv/bin/python run_m3.py --out m3-clean.jsonl'
# figures (host, from the pulled raw/)
.venv-ft/bin/python experiments/2026-07-22-sam2-coresidency/make_proof.py
```

**Two scars worth keeping.** `pkill -f llama-server` matches *your own ssh command line* if it
contains that string — it killed the session mid-run; use `pkill -f "build/bin/llama[-]server"`.
And `GroundingLoad` originally stored its stop flag in `self._stop`, which is a real
`threading.Thread` internal that `join()` calls — the carry finished all 99 ticks and then the
process died with `TypeError: 'Event' object is not callable`, losing the reporting but not the
work. The first pass at M3 read that as an OOM kill; it was not.

**Power mode note:** this board has **no MAXN_SUPER** — only 15 W (`-m 1`) and 7 W. Every number
in this repo is 15 W + `jetson_clocks`; "MAXN" in older notes is a mislabel.

## Results

Run 2026-07-22T23:20Z-2026-07-23T01:05Z on `ssh jetson` (Orin Nano 8 GB, 15 W + `jetson_clocks`),
torch 2.8.0, `facebook/sam2.1-hiera-tiny`. Raw JSONL in `raw/`; every table below is generated
from those files and `proof/` is rebuilt from them by `make_proof.py`.

### G0 - parity gate

| n | object | median mask IoU | min mask IoU | frames | px (sep / bat) | verdict |
|---|---|---|---|---|---|---|
| 2 | 1 | 1.000 | 1.000 | 100 | 1793 / 1793 | PASS |
| 2 | 2 | 1.000 | 1.000 | 100 | 1199 / 1199 | PASS |
| 3 | 1 | 1.000 | 1.000 | 100 | 1793 / 1793 | PASS |
| 3 | 2 | 1.000 | 1.000 | 100 | 1199 / 1199 | PASS |
| 3 | 3 | 1.000 | 1.000 | 100 | 3749 / 3749 | PASS |

**G0 verdict: PASS**, and stronger than the gate asked for. The criterion was median IoU >= 0.99 /
min >= 0.95; the measurement is IoU **exactly 1.000 on every one of the 500 object-frames**, with
identical pixel counts and no empty-mask disagreements. Batching N objects into one SAM2 state is
not an approximation of N separate states at `image_size` 1024 - it is bit-for-bit the same masks.
The speed lever measured in M2 is therefore a pure speed lever, and nothing downstream has to
carry an "but is it still the same tracker" caveat.

### M1 - rate decomposition, n=1

| config | image_size | encoder | tick ms (p50) | per-cand Hz | CUDA peak MB | MemAvailable after state |
|---|---|---|---|---|---|---|
| E1 reproduction | 768 | TRT fp16 | 161.5 | **6.190** | 533 | 4173 |
| size ablation | 768 | eager | 203.9 | 4.906 | 612 | 4340 |
| **deployed** | **1024** | **eager** | **372.1** | **2.688** | 725 | 3839 |
| stretch | 1024 | TRT fp16 | NOT RUN | - | - | - |

The stretch arm is **NOT RUN**: the `enc768.plan` on the board is built for a 768 input and cannot
serve 1024, and building a 1024 plan is a TensorRT engine build, not a bench cell. It is left
undone deliberately - it would measure a configuration that has never been deployed, whereas every
other row here measures one that has.

**The correction is 6.190 / 2.688 = 2.30x**, and it decomposes cleanly:

- **1.83x from image size** (768 -> 1024, eager throughout: 4.906 -> 2.688 Hz)
- **1.26x from the runtime** (TRT -> eager at 768: 6.190 -> 4.906 Hz)

E1's own notes carried an unused remark that 1024 would need ~1.9x; that is the 1.83x measured
here. The E1 reproduction is exact - 6.190 Hz against E1's published 6.15 - so the gap is not
drift in the board or the install, it is that **6.15 Hz was measured on a configuration that was
never deployed**: the deployed grounding stack runs SAM2 at `image_size` 1024 with the eager
encoder.

### M2 - candidate scaling at 1024

| n | mode | tick ms (p50) | per-cand Hz | measured / `n x rate(1)` | CUDA peak MB | state cost MB |
|---|---|---|---|---|---|---|
| 1 | sep | 372.1 | 2.688 | - | 725 | 1488 |
| 2 | sep | 743.2 | 1.346 | **0.999x** (744.2 predicted) | 868 | 2611 |
| 3 | sep | 1111.6 | 0.900 | **0.996x** (1116.3 predicted) | 1012 | 3837 |
| 2 | bat | 541.9 | 1.845 | 1.37x faster than sep | 801 | 1516 |
| 3 | bat | 711.9 | 1.405 | 1.56x faster than sep | 879 | 1504 |

**The harness's `/N` assumption is correct.** This corrects R-16's own task description, which
recorded that two states run "at 2.87 Hz per candidate, not 3.075" - i.e. that the division was
itself pessimistic. At the deployed 1024 the measurement is 743.2 ms against a predicted
2 x 372.1 = 744.2 ms, within 0.14%. The entire error in `CAND_HZ` is the **768-vs-1024 size
mismatch**, not the division by N.

Batched tick fits `tick ~= 202 + 170n` ms against separate's `~= 372n`: a fixed ~202 ms encoder
pass shared across objects, plus ~170 ms per object of memory attention and mask decoding. So
batching is worth 1.37x at n=2 and 1.56x at n=3 and grows with N - for free, per G0.

### M4 - where the memory goes

| arm | frames materialised | state cost MB (2 candidates) | MB / frame / state |
|---|---|---|---|
| sep | 25 | 1016 | - |
| sep | 100 | 2814 | **12.0** |
| bat | 25 | 609 | - |
| bat | 100 | 1516 | 12.1 |

The O(N) memory term is **the video, not the model**: 12.0 MB per frame per state against the
12.58 MB an `float32` 1024x1024x3 frame occupies. Tick time was unaffected by the 25-vs-100 frame
change (743.2 vs 742.6 ms), so the M1/M2 rate numbers are not contaminated by this.

This matters because `StreamCarry`'s ring is sized in **frames** (`PRUNE_AFTER = 100`), not bytes.
Moving the deployed `image_size` from 768 to 1024 multiplied that ring by 1.78x in bytes with
nobody editing a constant, and M3 below is where that bill arrives.

### M3 - co-residency under real load

Deployed server: `phase3-terse100eos-1024-q8_0.gguf` + `mmproj-...-f16.gguf`, `-ngl 99 -c 4096
-np 1 --cache-ram 0 --no-cache-idle-slots`, resident RSS 3.72 GB. Load arm = the deployed terse
grounding payload posted continuously from a background thread. **Every cell restarts the server
first** (`run_m3.py`) - the first pass ran cells back to back and a cell that OOM-kills leaves
~800 MB of swap occupied, which is fatal for a comparison whose answer is itself a swap number.

Server alone under the same load, no SAM2: **VLM wall p50 3753 ms**, MemAvailable floor 2274 MB.

| cell | tick p50, no server | tick p50, under load | carry cost | VLM wall p50 | swap consumed |
|---|---|---|---|---|---|
| n=1, 1024, ring 100 | 422.3 ms (2.368 Hz) | 979.2 ms (1.021 Hz) | **2.32x** | 7298 ms | **+2923 MB** |
| n=1, 1024, ring 32 | 419.7 ms (2.383 Hz) | 930.7 ms (1.074 Hz) | **2.22x** | 8129 ms | +140 MB |
| n=1, 768, ring 100 | 240.0 ms (4.166 Hz) | 549.4 ms (1.820 Hz) | **2.29x** | 7454 ms | +701 MB |
| n=2, 1024, ring 100 | 825.5 ms (1.211 Hz) | **OOM-KILLED** | - | - | - |
| n=2, 1024, ring 32 | 819.7 ms (1.220 Hz) | 1850.4 ms (0.540 Hz) | **2.26x** | 8379 ms | +1287 MB |

Two findings, and they point in opposite directions.

**E1's "co-residency costs 0 FPS" is falsified.** E1 measured against an *idle* resident server,
which tests memory only. Against a server actually serving grounding calls the carry pays a
strikingly uniform **~2.3x** - 2.32x, 2.22x, 2.29x, 2.26x across every size, ring length and
candidate count measured. The VLM pays too: 3753 -> 7298-8379 ms, roughly **2x**. Neither half is
immune; they split one board's memory bandwidth and one iGPU.

**The ring length, not the rate, is what decides whether the system runs at all.** At the deployed
`PRUNE_AFTER = 100`, two candidates plus the VLM under load is **OOM-killed** - it does not run.
At `PRUNE_AFTER = 32` the identical workload survives at 0.540 Hz per candidate. The lever costs
nothing in rate (2.383 vs 2.368 Hz with no server; the two are within noise) and removes 2.8 GB of
swap thrash (+140 MB vs +2923 MB from the same clean start). The intermediate readings say the
same thing: the n=1 ring-100 cell survives only by paging 2.9 GB to swap, and its tail is where
that shows - p90 1179.2 ms against ring 32's 989.0 ms.

**Answers.**

- **RQ-R16.0 (gate): YES, exactly.** Mask IoU 1.000 on all 500 object-frames at n=2 and n=3;
  batching is bit-identical, not approximate.
- **RQ-R16.1 (the correction): 2.30x optimistic**, decomposing as 1.83x image size x 1.26x
  TensorRT. The deployed per-candidate rate at 1024 is **2.688 Hz**, not 6.15.
- **RQ-R16.2 (scaling): exactly `rate(1)/N`** for separate states (within 0.14% at n=2, 0.4% at
  n=3). The `/N` assumption in the harness was right; R-16's own premise that it was pessimistic
  was wrong. Batching beats it by 1.37x (n=2) / 1.56x (n=3).
- **RQ-R16.3 (binding constraint): MEMORY, at N=2**, and the estimate that it would be memory is
  confirmed. Two candidates at the deployed ring length do not fit beside the VLM at all. Rate
  degrades gracefully; memory does not degrade, it kills the process.
- **RQ-R16.4 (co-residency honestly): ~2.3x on the carry, ~2x on the VLM**, both ways, uniform
  across configurations.

### Estimate vs actual

| quantity | estimate | actual | verdict |
|---|---|---|---|
| G0 gate | PASS | PASS, IoU 1.000 exactly | right, and stronger |
| M1 768 TRT n=1 | 6.0-6.3 Hz | 6.190 Hz | right |
| M1 1024 eager n=1 | 2.4-2.9 Hz | 2.688 Hz | right |
| **CARRY_HZ correction** | **2.0-2.6x** | **2.30x** | **right** |
| M2 per-cand n=2 sep | 1.2-1.5 Hz, "slightly worse" than `/2` | 1.346 Hz, exactly `/2` | rate right, **"slightly worse" wrong** |
| M2 batched advantage n=2 | 1.3-1.6x | 1.37x | right |
| M3 SAM2 tick under load | within 5% of solo | **2.3x worse** | **wrong, and it was the interesting one** |
| M3 VLM tail under SAM2 load | 2-3x worse max | ~2x p50 | right |
| M4 binding constraint | memory | memory, at N=2 | right |
| total runtime | 2-3 h | ~1.8 h (stretch arm dropped) | right |

The pre-registered prediction - "the headline correction is roughly **2.3x**, dominated by the
768-vs-1024 size mismatch rather than the `/2` assumption" - is exactly what happened, including
the reasoning. The estimate flagged as most likely to be embarrassing (the batched advantage,
which assumed the encoder dominates at 1024) landed at 1.37x inside its 1.3-1.6x band.

The one badly wrong estimate is **M3's "within 5% of solo"**, taken on faith from E1. It is 2.3x.
That estimate was wrong for the same reason the number it trusted was wrong: E1 measured an idle
server, and this campaign exists because inherited numbers were carrying configurations with them.

## Proof deliverables

Built by `make_proof.py` from `raw/*.jsonl` + `raw/frame0400.jpg`; all four opened and checked.

1. `proof/boxes-on-frame.png` - the three bench boxes drawn on frame 0400 of the board's clip
   (1024x540 aerial night intersection). The "look at it" deliverable: every number here is
   conditioned on these being real objects, and they are - a dark car behind the railing, a blue
   car right of it, a black SUV lower-centre. Config: all cells, `parity_gate.py` / `carry_bench.py`
   / `cores_bench.py` share this `BOXES` constant.
2. `proof/rate-decomposition.png` - left: the inherited 6.15 Hz against the deployed 2.69 Hz with
   the two contributions separated. Right: the consequence in the Part IV/V replays - they sampled
   each candidate every 10th frame (`select_p53.py:84`, `CAND_HZ = 6.15/2`, asserted at line 473)
   where the board allows every 22nd. Config: M1 + M2 sep n=2, 1024 eager.
3. `proof/scaling-and-batching.png` - left: separate vs batched tick against N, the `/N` line and
   the shared-encoder line. Right: state-creation cost at 25 vs 100 materialised frames, showing
   the O(N) term is the video at 12.0 MB/frame/state. Config: M2 + M4, 1024 eager.
4. `proof/coresidency.png` - left: each cell against **its own** no-server baseline (an n=2 bar
   against an n=1 baseline would bill N-scaling to co-residency), showing the uniform ~2.3x.
   Middle: swap consumed, where the ring lever is visible and nowhere else. Right: `MemAvailable`
   per round for the two n=2 cells - the ring-100 run dies at round 44 and prints nothing, so the
   sidecar trace is the only evidence it ran. Config: M3, all cells, clean start per cell.

## Status / next step

**COMPLETE 2026-07-23T01:20Z.** Gate PASS, M1/M2/M3/M4 all measured, four proof figures built and
opened, ledger rows appended under Part III, registry claim `P3-R16-carry-rate-1024` added.

Two things this campaign hands to whoever picks up Part V or VI:

1. **`CARRY_HZ = 6.15` is wrong for the deployed system and must not be reused.** The correct
   per-candidate figure at `image_size` 1024 is 2.688 Hz solo, 1.346 Hz at two candidates, and
   **0.540 Hz at two candidates with the VLM actually serving**. Any new replay harness starts
   from those, and the Part IV/V results generated at stride 10 carry the caveat recorded in
   `thesis/claims.json`, not a re-run.
2. **`PRUNE_AFTER = 100` does not fit on the board at 1024.** Two candidates plus the VLM under
   load is OOM-killed at the deployed ring length and runs fine at 32. This is a one-constant fix
   in `StreamCarry` with no measured rate cost, and it is a **prerequisite for P6.2** - closed-loop
   select-and-follow needs at least two carried candidates co-resident with the grounding server,
   which is exactly the cell that dies today. Deliberately **not** applied here: changing a
   deployed constant is a code change with its own gate (does a 32-frame memory horizon still
   re-find a target after occlusion?), and P5.15's carry-horizon result is the evidence base for
   that question, not this campaign.
