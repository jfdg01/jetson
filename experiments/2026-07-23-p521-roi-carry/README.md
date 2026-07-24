# P5.21 — ROI-crop re-anchor carry vs plain carry, paired

**Pre-registered 2026-07-23T23:05Z (Madrid). Frozen before any run. Self-contained handoff.**
Spine: `experiments/PART6-PROGRAM-warm-start-significance.md` (S1-S7). Tracked as **R-37** in
`thesis/REMEDIATION.md`. Wave B (real-imagery, no rig build). If this README and the program doc
disagree on the frozen gate, the program doc wins.

## Status / next step

- **PRE-REGISTERED, NOT RUN.** Next: run the held-out pilot to confirm plain-carry headroom (gate
  is locked only after the pilot), then the paired matrix on the hard-carry bank.

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

## Results (TBD)

| metric | plain | ROI | note |
|---|---|---|---|
| pilot base rate | | (n/a) | lock gate only if 0<rate<1 |
| final-IoU PASS (/n) | | | |
| McNemar b / c | | | b=ROI-pass&plain-fail |
| deflated p, n_eff, Holm | | | |
| drift-reinforcement failures | (n/a) | | c-side, reported |

**Verdict:** TBD. **Proof (>=2):** (1) a plain-drifts vs ROI-holds overlay clip on one hard-carry
sequence; (2) per-seq final-IoU plain-vs-ROI figure (`make_proof.py`).
