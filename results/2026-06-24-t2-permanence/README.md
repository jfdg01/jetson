# T2 — Permanence mechanism (Part III)

**Status:** ✅ **GATE PASS** (2026-06-24) — within the separable regime (appearance
SNR ≳ 1). **Branch:** `v3/object-permanence`.
**Prereq:** T1 (data & temporal contract) gate PASS — scored clip set + §6 metrics +
memoryless baseline (`results/2026-06-18-t1-temporal-contract/`, DECISIONS 2026-06-18T15:30).

T2 attacks **constraint #2 (identity through absence / object permanence)**: the T1
memoryless ByteTrack re-acquires by *nearest-to-last-position*, so after the white van
is occluded it re-locks the nearest same-class **decoy** (identity purity 0.725, 1 ID
switch, 1 of 2 re-acquisitions failed, oracle-coverage 0.575). The fix is an
**appearance memory**: store the target's descriptor at acquisition, match on it at
re-acquisition, and **refuse to lock** when no candidate matches the memory (wait for a
future VLM re-anchor) rather than grabbing the decoy.

## Mechanism (`experiments/sitl/reid_policy.py`)

`score_clip_reid(clip_dir, snr)` replaces only the re-acquisition rule of the T1
baseline; everything else (tracker, §6 assembly) is shared:

1. **Acquire** the target on its first locked-on-acquisition frame and store its
   appearance descriptor as `mem`.
2. **Re-acquire** (lock lost) by **minimum descriptor distance to `mem`**, gated:
   accept only if `|obs − mem| < GATE`; otherwise **refuse** (`locked = None`) and wait.
3. **Refine** `mem` with a slow EMA while the lock is on the true target.

### No pixels yet → appearance is modelled, tied to the range frontier

T1 deferred RGB rendering (the gate scores *boxes*, not pixels). So appearance is a
per-instance scalar descriptor; distinct vehicles sit at evenly-spaced descriptor values
(van vs decoy *are* different objects), and the **observation noise scales with crop
size**: `std = SIGMA0 / (snr · √(area/AREA_REF))`. Smaller crop (longer range) → noisier
descriptor. The single `snr` knob therefore *is* the **T0d separability-vs-range
frontier** — it is the variable the mechanism's benefit depends on, made explicit instead
of assumed away.

> `ponytail:` scalar descriptor + crop-size noise is the lazy stand-in for a real
> appearance embedding. Upgrade path: when T2+ renders crops, swap `_observe` for an
> embedding distance keyed off the same manifests — the policy and gate are unchanged.

## Result — beats the memoryless baseline (the T1 bar)

`crossing_occlusion` (all four stressors), scored by the §6 suite. Reproduce:
`.venv-ft/bin/python experiments/sitl/reid_policy.py --score <clip_dir> --snr <S>`.

| policy | identity purity | ID switches | re-acq failed | oracle-coverage | SOT success | following err (px) |
|---|---|---|---|---|---|---|
| memoryless baseline (T1) | 0.725 | 1 | 1 | 0.575 | 0.827 | 67.7 |
| **re-ID, snr = 8** | **1.000** | **0** | **0** | **0.695** | **1.000** | **0.13** |
| re-ID, snr = 2 | 1.000 | 0 | 0 | 0.695 | 1.000 | 0.13 |
| re-ID, snr = 1.2 | 1.000 | 0 | 0 | 0.695 | 1.000 | 0.13 |
| re-ID, snr = 0.8 | 0.751 | 1 | 1 | 0.575 | 0.827 | 67.7 |
| re-ID, snr = 0.4 | 0.751 | 1 | 1 | 0.575 | 0.827 | 67.7 |

**Reading:**
- Above the knee (**snr ≳ 1**) the appearance gate **fully resolves constraint #2**:
  identity purity 0.725 → **1.000**, ID switches 1 → **0**, failed re-acquisitions 1 →
  **0**, following error 67.7 → **0.13 px**.
- `oracle-coverage` rises 0.575 → **0.695**, which is the **ceiling** for this clip:
  0.695 = 139/200 = the *visible-frame fraction* (44 occluded + 17 out-of-frame frames
  can never be covered). The re-ID policy now covers **every frame the target is
  on-screen**.
- The knee at snr ≈ 1 is where the descriptor noise std (`SIGMA0 = 0.5` at the reference
  crop) reaches the `GATE` (= half the van/decoy gap): below it the gate can no longer
  separate van from decoy and the policy **degrades to the baseline** (0.751 purity) — an
  honest, separability-dependent result, not a uniform win.
- Control clip `clean_follow` stays perfect (purity 1.0, coverage 1.0): the mechanism
  adds nothing where there is no occlusion to recover from — no regression.

## Gate (charter / CLAUDE.md)

> T2 — permanence mechanism: add identity-through-absence. **Gate: beat
> memoryless-ByteTrack ID-switch / re-acq.**

**Met** (snr ≳ 1): ID switches 1 → 0, failed re-acq 1 → 0, identity purity 0.725 → 1.000,
coverage 0.575 → 0.695 (visible-frame ceiling). The benefit is explicitly bounded by the
appearance-SNR / range frontier (the T0d variable), which the experiment *measures*
rather than hides.

## Verification

```
.venv-ft/bin/python experiments/sitl/reid_policy.py    # reproducibility, beats-baseline, frontier
.venv-ft/bin/python experiments/sitl/clip_recorder.py  # baseline + refactored §6 assembly
make test                                               # §6 contract locks (T1b) — 59 passed
```
All green (2026-06-24).

## Decisions

### 2026-06-24 — appearance-memory re-ID with an explicit SNR/range knob (T2)

- **Decision:** Solve object permanence with a stored **appearance descriptor** matched at
  re-acquisition behind a **refuse-to-lock gate**, and model appearance as a scalar whose
  observation noise scales with crop size, exposing one `snr` knob = the T0d
  separability-vs-range frontier. Reuse the T1 tracker and §6 metric assembly unchanged
  (factored `assemble_scores` out of `clip_recorder.score_clip`).
- **Alternatives considered:** (a) **VLM re-verification** of each re-acquisition crop —
  deferred: it is the *other* permanence lever but needs rendered crops + an on-Orin VLM
  call inside the cadence budget (T3/T4 territory); the appearance gate is the cheap,
  renderer-free slice that already clears the gate. (b) **Render RGB now and use a real
  embedding** — rejected for the same reason T1 deferred rendering: it adds a heavy,
  non-deterministic dependency before it is load-bearing; the scalar+noise stand-in
  isolates the *mechanism* (memory + gate) from the *encoder*, and the `snr` knob makes
  the range dependence a measured variable rather than a hidden constant. (c) **Motion-only
  re-ID** (Kalman gating, no appearance) — rejected: it is exactly the baseline that fails,
  because both vehicles share the crossing region.
- **Tradeoff:** the win is **conditional on separability** (snr ≳ 1); below the knee the
  policy is no better than memoryless. Accepted and reported as the headline frontier, not
  smoothed over — it is the quantitative statement of *when* appearance memory helps.
- **Revisit when:** T2+ renders crops (swap `_observe` for an embedding distance off the
  same manifests) and/or T3 adds VLM re-verification as the second permanence lever for the
  low-SNR regime where appearance alone collapses.
