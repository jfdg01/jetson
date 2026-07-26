*Stage of the MODE 2 campaign, split out of `README.md` on 2026-07-26 so a session
working one stage does not load the other four. The section number below is unchanged,
so existing "§8" citations still resolve. Campaign context, imagery decision, versions
and proof deliverables stay in `README.md`.*

## 8. EXP-6 — gated carry-crop test

**Re-pre-registered 2026-07-26T23:05Z, after EXP-5 and before any EXP-6 run.** The original
§8 (TREATMENT = "the EXP-5 winner", implicitly a crop+guard arm) is superseded, because
EXP-5's pre-registered treatment lost and the arm being carried forward is one EXP-5 was not
designed to promote. Both changes are declared, not smoothed over:

1. **TREATMENT is A4 — fixed 512 crop, dead-band re-centre, NO guard.** This is a **post-hoc
   arm promotion** off an exploratory pilot. It is why EXP-6 exists as a properly-powered
   confirmation rather than a formality, and it is why the §7 pilot carries no p-value.
2. **The guard (lever e) is dropped entirely** and shipped as a measured negative, not
   retried with a tuned `D_MAX`. EXP-5 showed the failure is structural — the veto freezes
   its own reference — so any threshold that fires at all latches. Re-tuning `D_MAX` would be
   fitting the pilot.

**RQ (EXP-6):** does a fixed native-resolution crop around the carried box beat plain
carry@640, and does it reach plain@1024's accuracy at >= 2x its throughput?

* **Arms:** CONTROL = plain@640 (deployed); **TREATMENT** = fixed 512-px crop, dead-band
  re-centre, no guard, @640; **CONTROL-2** = plain@1024 (the deployed size-gated fallback).
  Three arms, no guard arm — the guard's verdict is already recorded.
* **Primary metric: per-clip median IoU, Wilcoxon signed-rank, paired.** Not binary PASS —
  CONTROL already passes 32/38, so a PASS gate is ceiling-limited and would burn the run on
  an unreachable floor (the mistake §7's proceed gate made). Secondary: delivered-PASS
  (median IoU >= 0.25), exact McNemar.
* **n / unit:** **all 38 EXP-1 UAV123 clips**, unit = clip, same frozen seed boxes. No
  subsampling, so no selection-bias objection; 38 > the n>=25 floor.
* **Contamination stratum (new, forced by the promotion).** 12 of the 38 clips are the ones
  A4 was selected on in EXP-5, and they are the *hardest* 8 plus 4 easy — a biased subset in
  both directions. Pre-registered stratification is therefore **held-out 26 vs pilot 12**, and
  the **held-out 26 is the primary stratum**; it alone still clears n>=25. The pilot-12 is
  reported for completeness and is *not* what the verdict rests on. The tail-8 vs non-tail-30
  split is reported as a secondary descriptive cut.
* **Deflation:** UAV123 clips sharing a base sequence (`car1`/`car1_s`, `person1`/`person1_s`
  …) are one independent unit. Report raw n and deflated n; **cite the deflated p**.
* **Test:** Wilcoxon (primary, on the held-out 26); exact McNemar with `min_discordant = 6`
  (secondary); Holm within the Part VI family.
* **PASS gate (accuracy):** TREATMENT > CONTROL on the held-out 26, Wilcoxon p < 0.05
  deflated, effect not reversing on the pilot-12.
* **PASS gate (the one that decides shipping): throughput-matched parity vs CONTROL-2** —
  TREATMENT@640 within 0.03 median-of-median IoU of plain@1024, |PASS difference| <= 1 clip,
  at a measured on-device rate >= 2x (target >= 4.7 Hz vs 2.34 Hz). Report measured Hz for
  all three arms; a crop arm below ~4 Hz has spent the entire reason it exists. EXP-5 measured
  6.30 vs 2.34 Hz (2.7x) on 12 clips, so this gate is expected to hold — it is in the
  pre-registration to catch the case where it does not at scale.
* **Kill gate:** TIE or wrong direction vs CONTROL on the held-out 26 (P5.21's exact
  pattern), **or** TREATMENT loses to CONTROL-2 on accuracy without a >= 2x rate advantage ->
  kill. MODE 2 carry does not ship; plain carry + the size-gated 1024 fallback stays the only
  path, and the crop stays acquire-prefill-only exactly as P5.21 left it.
* **Small-frame caveat, pre-declared.** On 720x480 clips the window is `min(512, w, h) = 480`,
  which is barely a crop. `uav3` is such a clip and no crop arm moved it. Report the
  720x480 clips as a labelled subgroup rather than discovering them afterwards.
* **Visual:** per-clip IoU figure from `runs/exp6/results.json` via a committed
  `make_proof6.py`; overlays for the two largest wins and the largest loss, Read.
* **Code:** none beyond `run_exp5.py`'s crop wrapper with `guard: False`, run at gate scale.
  Reuse `run_exp1.py` staging.
* **Cost estimate.** ~1 day (114 clip-runs on-device ~= 3-4 hr; rest is scoring, proof,
  ledgers).
* **Estimate (pre-registered).** Median-of-median IoU: CONTROL 0.811, TREATMENT 0.845,
  CONTROL-2 0.816. PASS 32 / 35 / 36 of 38. Tail-8: 2 / 7 / 8. On the held-out 26 the effect
  should be **much smaller** than the pilot's — those clips are mostly at ceiling, where a
  crop has nothing to add — so Wilcoxon p ~ 0.05-0.30 and a real risk the primary stratum
  comes back a TIE while the tail cut is a clear win. Most likely honest verdict:
  **"throughput-matched parity with the 1024 fallback, tail-scoped win, not a blanket carry
  replacement."**

### Results (run 2026-07-26T23:40Z, `runs/exp6/`)

Ran as pre-registered: 3 arms x 38 clips = 114 clip-runs, same frozen `plan.json` staging as
EXP-1/EXP-5 (STRIDE=11, N_STEPS=24, ~264-frame window), SAM2 on the Orin over the ssh-stdio
bridge, `nvpmodel` 15W + `jetson_clocks`. CONTROL and TREATMENT share one `image_size=640`
bridge process; CONTROL-2 gets its own at 1024. Deterministic — a re-run reproduces the file.

| arm | median-of-median IoU | delivered PASS | tail-8 PASS | on-device Hz | lost steps |
|---|---|---|---|---|---|
| CONTROL plain@640 | 0.811 | 32/38 | 4/8 | 5.76 | 24 |
| **TREATMENT crop512@640** | **0.815** | **35/38** | **7/8** | **6.31** | 38 |
| CONTROL-2 plain@1024 | 0.817 | 36/38 | 8/8 | 2.34 | 31 |

**Strata, TREATMENT vs CONTROL** (Wilcoxon primary, deflated by base sequence; McNemar on
delivered-PASS secondary):

| stratum | n / n_eff | TRT | CTL | PASS | median diff | p raw | **p deflated** | McNemar |
|---|---|---|---|---|---|---|---|---|
| **held-out 26 (PRIMARY)** | 26 / 24 | 0.831 | 0.833 | 24 / 24 | **+0.0085** | 0.1208 | **0.0918** | b=0 c=0 |
| pilot 12 (contaminated) | 12 / 12 | 0.774 | 0.681 | 11 / 8 | +0.0735 | 0.01367 | 0.01367 | b=3 c=0, p=0.25 |
| all 38 (descriptive) | 38 / 36 | 0.815 | 0.811 | 35 / 32 | +0.0190 | 0.003965 | 0.002947 | b=3 c=0, p=0.25 |
| tail 8 | 8 / 8 | 0.703 | 0.223 | 7 / 4 | +0.0940 | 0.01562 | 0.01562 | b=3 c=0, p=0.25 |
| non-tail 30 | 30 / 28 | 0.853 | 0.834 | 28 / 28 | +0.0060 | 0.1128 | 0.0875 | b=0 c=0 |

**TREATMENT vs CONTROL-2** (the parity comparison): held-out 26 +0.0050 deflated p=0.566;
all 38 +0.0015 deflated p=0.6745; tail-8 +0.0080 p=0.945. Statistically indistinguishable
everywhere, at 2.7x the rate. That is the parity claim, and it is the one that ships.

**Gates, evaluated in code** (`runs/exp6/results.json` -> `gates`):

* **Accuracy gate: FAIL.** Held-out 26 is directionally right (+0.0085, 16 wins / 7 losses /
  3 ties, bootstrap CI [+0.0015, +0.024] excluding zero) and the pilot does not reverse it,
  but deflated p=0.0918 > 0.05. Not significant, so it is not claimed. The effect is real but
  tiny where it was measured: the held-out 26 sit at ceiling (both arms PASS 24/24, both at
  ~0.83), and a crop cannot improve a target the plain arm already holds at 0.83.
* **Throughput-matched parity gate: PASS** — d_IoU **-0.002**, d_PASS **-1** clip, rate
  **2.7x** (6.31 vs 2.34 Hz). Inside all three pre-registered bounds.
* **Kill gate: did not fire** — direction is not reversed and the rate advantage is present.

**The pre-registered estimate was almost exactly right.** PASS 32 / 35 / 36 predicted, 32 / 35
/ 36 measured. CONTROL 0.811 predicted, 0.811 measured; CONTROL-2 0.816 vs 0.817. Two misses:
TREATMENT's median-of-median came in 0.815, not the predicted 0.845 (the pilot's margin did
not survive contact with 26 ceiling clips — which the estimate itself warned about), and the
tail-8 CONTROL PASS was 4, not 2. The predicted p-range (0.05-0.30) and the predicted "TIE on
the primary while the tail is a clear win" both landed.

**`n_lost` is not a crop cost.** TREATMENT loses more steps (38 vs 24), but every one is
confined to `car11` / `uav3` / `uav8` — the three clips that score 0.000 in *all three* arms.
CONTROL {car11:2, uav3:10, uav8:12}, TREATMENT {car11:8, uav3:15, uav8:15}, CONTROL-2 {car11:8,
person21:1, uav3:7, uav8:15}. The crop never loses a target the plain arm holds; it loses
already-lost targets more completely.

**720x480 subgroup, as pre-declared:** `uav3` and `uav8`, the only two clips at that frame
size (the other 36 are 1280x720). The window is `min(512, 480) = 480`, i.e. barely a crop —
and both are 0.000 in both arms, so the subgroup is uninformative rather than negative.
`uav3` reaches 0.436 under CONTROL-2, so it is resolution-gated; a 480-px crop of a 480-px
frame cannot deliver that, only the 1024 fallback can. This is the size-gated-fallback
argument, measured.

**Cost, estimate vs actual.** Estimated ~3-4 hr of on-device time; actual **~12 min** total
(CONTROL ~180 s, TREATMENT 153 s, CONTROL-2 404 s). The estimate assumed 1024-arm timings
across all three arms; two of the three run at 640.

**Verdict: PARTIAL PASS — throughput-matched parity with the 1024 fallback, tail-scoped win,
not a blanket carry replacement.** Verbatim the pre-registered most-likely honest outcome.
The shipping gate passes: crop512@640 matches plain@1024's accuracy (d_IoU -0.002, d_PASS -1)
at 2.7x the on-device rate, so it is a strictly cheaper way to buy the fallback's accuracy.
The accuracy gate fails: against plain@640 on the held-out 26 the gain is +0.0085 at deflated
p=0.0918, a **bounded null on the ceiling clips**, not a win. Where the crop earns its keep is
the resolution-gated tail — 0.703 vs 0.223, PASS 7/4 — which is a descriptive secondary cut,
not a powered claim (n=8). Ship it as the size-gated path (crop512@640 replacing the 1024
fallback), not as the default carry.

### Proof

* `proof/exp6-arms.png` — all 38 clips sorted by CONTROL median IoU, three arms, `*` marking
  the 12 contaminated pilot clips. The resolution-gated tail collects on the left, where
  CONTROL's grey bars collapse and both TREATMENT and CONTROL-2 stand; the right two-thirds
  are the ceiling clips where all three arms are indistinguishable. Right panel: the parity
  gate, PASS.
* `proof/exp6-win.png` — `bike3` (delta +0.753), the largest TREATMENT win. CONTROL holds the
  cyclist at 0.71 on step 0 and is at **0.00 for steps 8, 15 and 23** — gone. TREATMENT's
  orange crop window follows the rider: 0.68, 0.50, 0.84, 0.92. The tail effect, in pixels.
* `proof/exp6-loss.png` — `car1_s` (delta -0.102), the largest TREATMENT loss, and the honest
  half. **Both arms hold the jeep for the whole window** (CONTROL 0.87/0.84/0.86/0.87,
  TREATMENT 0.86/0.78/0.75/0.76). The loss is mask tightness against the GT box convention,
  not a track loss — the crop's failure mode is a slightly worse box, never a dropped target.

---

