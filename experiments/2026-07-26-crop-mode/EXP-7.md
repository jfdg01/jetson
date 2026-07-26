*Stage of the MODE 2 campaign, split out of `README.md` on 2026-07-26 so a session
working one stage does not load the other four. The section number below is unchanged,
so existing "§9" citations still resolve. Campaign context, imagery decision, versions
and proof deliverables stay in `README.md`.*

## 9. EXP-7 — composed MODE 2, closed loop

Runs **only if EXP-4 and EXP-6 both pass**.

**RQ:** does MODE 2 (crop-ground + crop-carry) beat MODE 1 on delivered-PASS with the copter
flying its own control output?

* **Arms:** CONTROL = MODE 1 (`follow_click` + plain `orin_carry`, current deployed) vs
  TREATMENT = MODE 2 composed from EXP-4's and EXP-6's winners.
* **Metric:** delivered-PASS, identical definition to P6.2-DELIVERY. Secondary: acquire
  latency, on-device carry Hz.
* **n / unit:** **25 CARLA seeds**, unit = seed, paired, run live through the existing P6.2
  harness — **not a bank** (§10). Stratified to include >= 10 designations with native
  footprint < 80 px.
* **Deflation:** 25 independent CARLA seeds -> `n_effective = n_rows = 25`, same standing as
  P6.2-DELIVERY (explicitly not deflated).
* **Test:** exact McNemar; Holm per-Part and globally.
* **PASS / kill:** b >> c surviving Holm in both families, or record a bounded null in the
  P6.2-COUPLING style.
* **Scope caveat, carried forward verbatim:** grounding is held constant via **ORACLE
  designation** where required (G6: q8_0 is non-discriminative at 45 m nadir). Any claim is
  conditional on correct designation.
* **Code:** raise the crop source in `on_image` (`carla_debug_ui.py:2460-2470`) so
  `live["bgr"]` at 1920 reaches the crop path — **only if EXP-4 passed**; otherwise the crop
  stays on the 960 frame and `on_image` is untouched. Plus one `seg(...)` widget
  `normal | click-crop` in the `w3_src` designate row (~`:2090`), orthogonal to
  `designate` / `acquire`. MODE 2 composes only with `follow_click`; the caption-only
  `follow` button has no coordinate and stays MODE 1.
* **Cost estimate.** ~1-2 days.
* **Estimate (pre-registered).** TREATMENT 19/25 vs CONTROL 12/25 — high uncertainty, fully
  contingent on two upstream gates priced at roughly coin-flip each, so P(reaching EXP-7)
  ~ 0.25.

### Results — NOT RUN (2026-07-26T23:55Z)

**The entry gate did not fire, and the pre-registered response to that is not to run.** Both
upstream results are on record:

* **EXP-4 = MISS on its primary** (§6). C vs D b=1/c=0, below the 6-pair floor: lever (a'),
  the native-1920 plumbing, is retired. What survived is C vs A (b=8, c=0, p=0.0078) — the
  win is *magnification*, which the deployed 960 frame already supplies.
* **EXP-6 = PARTIAL PASS** (§8). The shipping/parity gate passes; the accuracy gate against
  plain@640 fails at deflated p=0.0918 on the held-out 26.

Neither is a pass in the sense §9 requires, and the composition makes that concrete rather
than merely procedural. **EXP-7's TREATMENT would be nearly identical to its CONTROL:**

| MODE 2 half | what EXP-4/EXP-6 leave of it | delta vs deployed CONTROL |
|---|---|---|
| crop-ground | EXP-4 retired the 1920 source; the crop stays on the 960 frame — which is `roi_reanchor`, **already live** at `carla_debug_ui.py:1901` | none |
| crop-carry | EXP-6: bounded null vs plain@640; a parity-and-2.7x replacement for the **1024 size-gated fallback** | fires only on the size-gated path |

So the pre-registered contrast has been emptied by its own upstream results: 25 live CARLA
seeds and ~1-2 days would be spent measuring the deployed system against itself plus a lever
that is a measured null on 24 of 26 held-out clips. The estimate priced P(reaching EXP-7)
~ 0.25 for exactly this reason.

**Verdict: NOT RUN — gate not met, and the composed contrast is empty by construction.**
Recorded as a pre-registered non-run, not a silent drop. What EXP-6 does authorize is a
**deploy change, not a campaign**: swap the size-gated 1024 carry fallback for crop512@640
(same accuracy, 2.7x the on-device rate). That is a UI/config edit backed by an n=38 parity
gate, and it needs no new imagery, no flight seeds and no new claim.

**What would reopen it.** A result that puts real magnification back on the table where the
deployed 960 path cannot reach — e.g. a designation task at a footprint the 960 frame
genuinely cannot resolve (S0's 40-px case, `s0-detail-headroom-40px.png`, is that regime).
EXP-7 as written is not that experiment; it would have to be re-pre-registered against a
contrast that is not already deployed.

---

