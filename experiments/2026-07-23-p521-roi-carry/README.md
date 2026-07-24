# P5.21 — ROI-crop re-anchor carry vs plain carry, paired

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md` (S1-S7). Tracked as **R-37** in
`thesis/REMEDIATION.md`. Wave B (real-imagery, no rig build). If this README and the program doc
disagree on the frozen gate, the program doc wins.

## Status / next step

- **DONE 2026-07-24. Verdict: TIE [measured negative] — ROI-carry does NOT beat plain SAM2 carry;
  it mildly regresses (26/34 vs 28/34), discordants run the wrong way (b=1, c=3), and the
  pre-registered drift-reinforcement failure fired (car10).** Closes the last non-capacity carry
  lever. No downstream experiment depends on this.

## Question

RQ-P5.21: does the ROI-crop + lanczos re-anchor carry (the lever adopted for anchor prefill on a
per-frame IoU argument) actually **beat plain SAM2 carry** as a paired outcome on hard sequences?
The lever was never tested as an outcome contrast — only as a prefill-cost / single-frame-IoU
argument. This closes the last non-capacity carry lever (bigger SAM2 is already dead, P5.20).

## Design (frozen)

- **Paired-binary, exact McNemar** (two-sided p<0.05), deflated, Part-V Holm.
- **Arm A = plain carry:** `StreamCarry` 1024-eager, GT frame-0 seed, `prune_after=32`.
- **Arm B = ROI-carry:** ROI-crop + lanczos re-anchor (`roi_reanchor`, ROI_MARGIN=2.0, ROI_RES=512,
  LANCZOS4), `prune_after=32`, memory flat.
- **Unit = one distinct UAV123 source sequence** (strip `_s`). **n >= 27** (clears 25 after
  deflation). Bank is pre-selected **hard-carry** sequences (fast / small target).
- **Per-seq PASS = final-frame track IoU >= 0.25 vs GT** (the carry survived to the end).

### FROZEN GATE (verbatim)

Reject H0(ROI-carry==plain-carry) at exact two-sided McNemar p<0.05, deflated, Part-V Holm. b+c >= 6
one-directional. **Two-outcome, both content:** win = a deployable carry lever; tie = a measured
negative that closes the last non-capacity carry lever. Directional expectation b(ROI-pass,
plain-fail) > c.

**Not a construction trap (S2):** a held-out pilot must show the plain-carry base rate strictly
between 0 and 1 (real headroom) *before* the gate is locked — otherwise the bank is too easy/hard to
separate the arms (the P5.3/P5.4/P5.5 failure). If the pilot shows plain carry already at ceiling on
these sequences, the bank is made harder before locking.

**Drift-reinforcement guard:** cropping around a *drifted* predicted box can reinforce the drift
(c>0). When the predicted box has clearly drifted (area-ratio / displacement heuristic), the crop is
clamped or skipped. Drift-reinforcement failures (ROI worse than plain) are reported as the negative,
not hidden.

## Command (intended)

```bash
# pilot: plain-carry base rate on the hard-carry bank (lock gate only if 0 < rate < 1)
.venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/pilot_p521.py --bank runs/p521/bank --arm plain
# paired matrix
.venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/carry_p521.py \
    --bank runs/p521/bank --arms plain,roi --prune-after 32 --out runs/p521
.venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/verdict_p521.py runs/p521
```

## Environment / versions

RTX-3090; Python 3.12 `.venv-ft` (`uv.lock`); SAM2 (hiera, TensorRT fp16 per E1, `prune_after=32`);
UAV123 hard-carry sequences. No VLM *acquire*: both arms seed the carry from GT frame-0. Arm B additionally re-anchors via an on-device VLM crop re-ground (JetsonBackend, Jetson Orin); Arm A never grounds. Pins ->
`runs/p521/env.json`.

## Reuse map

| Need | Symbol / file:line |
|---|---|
| stream-native carry | `experiments/2026-07-01-temporal-acquire-carry/stream_carry.py:65` `StreamCarry`, `.step` :102 |
| ROI re-anchor lever (exact) | `experiments/2026-07-14-select-generalization/select_p55.py:92` `roi_reanchor` (MARGIN 2.0, RES 512, LANCZOS) |
| coverage / final-IoU scoring | `experiments/2026-07-04-warm-start-acquire/replay_e24.py:153` `coverage_realtime` (or per-frame IoU) |
| verdict / classify | `experiments/2026-07-20-n25-select/verdict_p518.py:47` `classify` |
| stats | `grounding/stats.py` `mcnemar` :114 |

## Estimates (up front)

- Est plain carry 16-20/27, ROI-carry 20-24/27 on hard sequences (ROI re-anchor recovers small/fast
  targets the plain carry leaks). Est b~6-8, c~1-2 => reachable if the hard bank has headroom.
- **Risk:** the arms may tie (as select contracts repeatedly tied) if carry survives regardless on
  UAV123's slow two-candidate geometry (P5.15: two-candidate geometry dissolves by ~16 s). Mitigate
  by picking genuinely hard-carry sequences; if they tie, that is the measured negative closing the
  lever — still content.
- Runtime (est): pilot ~30 min; matrix ~1-2 h; verdict ~10 min.

## Results (RAN 2026-07-24)

| metric | plain | ROI | note |
|---|---|---|---|
| pilot base rate | 5/8 = 0.62 | (n/a) | **HEADROOM OK** (0<rate<1) — gate locked; held-out 8 |
| final-IoU PASS (/n) | 28/34 | 26/34 | matrix, hard-carry bank, distinct sources |
| McNemar b / c | — | b=1, c=3 | b=ROI-pass&plain-fail; **c>b: wrong direction** |
| deflated p, n_eff, Holm | — | p=0.625, n_eff=34 | b+c=4 < floor 6 — no test reaches α; Holm moot |
| drift-reinforcement failures | (n/a) | 1/3 c-side | **car10** (guard flagged); bike1, person15 unflagged |

**Verdict: TIE [measured negative — closes the last non-capacity carry lever].** The ROI-crop +
lanczos re-anchor was adopted (`293c83b`) on a *prefill-cost / single-frame-IoU* argument for cold
*acquire*; tested here for the first time as a paired *carry-outcome* contrast on hard sequences, it
does **not** beat plain SAM2 carry — it is net-negative (26 vs 28). The single b-side win (car14: ROI
re-anchor recovers a small car the plain carry lost) is outweighed by 3 c-side losses, one of which
is the pre-registered drift-reinforcement failure made concrete: on car10 the re-anchor cropped
around an already-drifted box, the on-device VLM grounded off-target, and the track was lost while
plain held (0.86). The lever helps *acquire prefill* (keep it there) but is not a carry improver.
Consistent with P5.15 (the carry is not the fragile part) and P5.20 (bigger SAM2 recovers nothing) —
the last non-capacity carry lever is now measured and closed.

**Proof (2):**
1. `proof/p521_drift_reinforcement.png` — the negative, viewed: plain HOLDS car10 (green GT + red
   pred overlap) | ROI drift-reinforced to track-loss (green GT only, no red) | car14 the one b-side
   win (ROI recovers a plain-lost car).
2. `proof/p521_per_seq_iou.png` — per-seq final-IoU plain-vs-ROI scatter; 30 on the tie diagonal,
   car14 above (ROI win), car10/bike1/person15 at y=0 (ROI drops), car9 below-diagonal (ROI degrades
   without flipping). `make_proof.py`, reproducible from `runs/p521/*/results.json`.

## As-run deviations from the pre-registration

- **Harness unified into `carry_p521.py` subcommands** (`pilot` / `matrix` / `verdict` + `--selftest`,
  10 pure-logic cases) — the pre-reg command block imagined separate `pilot_p521.py` /
  `verdict_p521.py` scripts. Same design, one file of record; redundant draft scripts deleted.
- **Carry rate-capped to the deployed rate (R-16): 2.69 Hz → process 1 in `CARRY_STRIDE=11` source
  frames**, not every frame. Full-frame carry would overstate carry robustness vs deployment and
  ceiling both arms (the P5.15 24/25 regime). Re-anchor every ~90 source frames = every 8 processed
  steps. This is the device-faithful path (`_run_seq`); `run_arm`/`--selftest` unchanged.
- **n = 34 distinct-base sequences, not 27.** After streaming 24 hard-carry sequences from the HF
  UAV123 tarball, 42 distinct real bases had frames locally; held out 8 for the pilot, ran the
  hardest 34 disjoint as the matrix (all distinct sources ⇒ deflation is a no-op, n_eff=34).
- **Bug fixed in the frozen harness's roi-arm import path:** `replay_e24` lives in
  `2026-07-04-warm-start-acquire`, not `2026-07-14-select-generalization`; the pre-reg only inserted
  the latter. The roi path was never exercised by `--selftest` (no Jetson), so it surfaced at first
  matrix launch. Both paths now on `sys.path`; imports smoke-tested before the run.
- **Machine (per the VLM-discipline rule):** Arm-B ROI re-anchor grounding ran on the **Jetson Orin
  Nano** (`JetsonBackend`, q8_0 `phase3-terse100eos-1024`) — the only grounding call, on-device. SAM2
  carry (device-independent, E1 mask-parity 1.000) ran on the 3090 capped at 220 W; no timing is
  claimed on-device. Both-arms PASS/McNemar is device-independent (final-frame IoU vs GT).
