---
title: Dataset Survey — Is RefDrone the Right Choice?
subtitle: Referring-expression grounding for low-altitude drone imagery
author: Javier F. Dibo Gómez
comment: 2026-06-30T20:10Z
locale: en
---

## 1. Question and scope

While a fine-tune was already running on **RefDrone**, the question arose late:
should we have surveyed for a better dataset first? This document records a
three-lane deep search to answer it.

The task being served:

- **Referring expression comprehension / visual grounding** — natural-language
  phrase to bounding box.
- **Domain:** low-altitude drone / UAV imagery (oblique follow-drone view).
- **Model + target:** small VLM (Qwen2-VL-2B) deployed on a Jetson Orin Nano.
- **Part III extension:** persistent moving-target tracking (temporal).

Verdict up front: **RefDrone is the correct primary choice** for single-frame
NL to bbox at drone altitude. It is essentially the only open, human-refined,
drone-view referring-expression bbox dataset with generic categories. The real
gap is temporal — RefDrone cannot serve Part III's tracking.

## 2. RefDrone profile

### 2.1 What it is

- Built on **VisDrone2019-DET** imagery; retains VisDrone's train/val/test splits.
- 8,536 images, 17,900 referring expressions, 63,679 object instances, **10
  categories** (inherited from VisDrone).
- Expressions are **GPT-4o-generated** via a multi-agent pipeline (RDAgent /
  RDAnnotator), with human verification. Average 9.0 words, average 3.8 targets
  per expression.
- **License:** CC BY 4.0. Annotations on GitHub/HF (MDETR JSON); images must be
  pulled separately from VisDrone.
- Recent and niche: paper Feb 2025 (v2 Nov 2025), ~44 GitHub stars, no Papers
  With Code leaderboard.

### 2.2 The protocol mismatch (important)

RefDrone is a **multi-target / no-target** benchmark: one expression maps to
**0 to 242 boxes**, scored **F1 at IoU >= 0.5** (instance-level). It is *not*
classic one-phrase-to-one-box REC.

<!-- caption: Published RefDrone benchmark numbers vs. our internal protocol -->

| Protocol | Metric | Best reported | Source |
|---|---|---|---|
| RefDrone published (multi-target) | F1 @ IoU>=0.5 | 34.44 (NGDINO-B) | paper Table 2 |
| RefDrone published (VLMs) | F1 @ IoU>=0.5 | 14.14 (Qwen-VL) | paper Table 2 |
| Human / RDAnnotator ceiling | F1 @ IoU>=0.5 | 58.14 | paper |
| Our v2 pipeline (single-box) | IoU @ 0.25 | 62.6 | repo, Part II |

Consequence: our **62.6% IoU@0.25 single-box** result is measured on a
**different, easier protocol** than the published leaderboard and is **not
directly comparable** to the 34.44 F1 SOTA. This divergence must be documented
explicitly in the thesis.

### 2.3 Difficulty and quality

- **Genuinely hard, not saturated:** SOTA (34.44 F1) sits ~24 points below the
  human ceiling; off-the-shelf VLMs collapse (LLaVA-v1.5 6.0, MiniGPT-v2 4.97).
- Annotation pipeline: ~42% of GPT-4o drafts accepted directly, ~47% minor
  refinement, ~11% full re-annotation — i.e. ~58% needed human edits.
- No reported label-noise complaints; open GitHub issues are usage questions.

### 2.4 License chain caveat

RefDrone is CC BY 4.0 but **reuses VisDrone2019-DET imagery**, which is
**CC BY-NC-SA 3.0 (academic only)**. Fine for a thesis; verify the
redistribution chain before any non-academic use.

## 3. Competitive landscape — single-frame grounding

Every strong alternative is **satellite / high-altitude** — wrong viewpoint and
object scale for a follow-drone. They are useful as auxiliary training, not as a
domain-matched replacement.

<!-- caption: Aerial referring-expression / grounding datasets vs. RefDrone -->

| Dataset | Year | Domain | Task | Size | Notes |
|---|---|---|---|---|---|
| **RefDrone** | 2025 | Drone (low-alt) | REC bbox, multi-target | 8.5k img / 17.9k expr / 10 cat | Baseline. On-task. CC BY 4.0. |
| OPT-RSVG | 2024 | Satellite | REC bbox | 25.5k img / 49k pairs | Largest RS REC; aux pretrain. |
| VRSBench | 2024 | Satellite | caption+VQA+grounding | 29.6k img / 52k refs | Human-verified; high quality. |
| DIOR-RSVG | 2023 | Satellite | REC bbox | 17.4k img / 38.3k expr | Standard RSVG baseline. |
| RRSIS-D | 2024 | Satellite | RES (mask) | 17.4k triplets | Segmentation, off-task. |
| RefSegRS | 2023 | Aerial | RES (mask) | 4.4k triplets | Small, template language. |
| GeoText-1652 | 2024 | Drone+sat | retrieval / region-text | ~100k pairs | Building geolocalization, niche. |

Key finding: **RefDrone is the unique open, human-refined, drone-altitude,
multi-category REC-bbox dataset.** No better-matched replacement exists.

## 4. The real gap — temporal / tracking (Part III)

RefDrone is single-frame with no track-IDs, so it cannot support persistent
moving-target tracking. Two paths fill this gap.

<!-- caption: Candidates to fill RefDrone's temporal gap -->

| Option | Provides | Catch |
|---|---|---|
| **AerialMind** (AAAI 2025) | UAV bbox + track-IDs + referring expressions; 93 seq / 24.6k expr / 293.1k instances / ~46M boxes; extends **VisDrone + UAVDT** | **Verified released** (2026-06-30T17:07Z): HF `shawnliang0420/AerialMind` (24.5 GB) + Baidu. License chain caveat — see §5.1. |
| **VisDrone-MOT + RDAgent** | Same domain as RefDrone; tracks/occlusion/classes; mint expressions with RefDrone's own generator | You build it, but reuse known tooling; full provenance control |
| WebUAV-3M | NL + tracks, CC0, 4.5k videos / 3.3M frames | NL is one global phrase per clip, single-target |
| UAVNLT | Ready NL-to-track | Vehicle-only, single-target, small |

Motion/relational flavor for Part III expressions: **MOR-UAV** (moving-vs-static
labels), **Stanford Drone** (trajectories/interactions), **Okutama-Action**
(action verbs).

## 5. Recommendation

- **Part II (single-frame NL to bbox):** keep RefDrone as the headline benchmark.
  Optionally add OPT-RSVG / VRSBench as auxiliary fine-tuning data; report
  DIOR-RSVG for comparability with the RSVG literature.
- **Part III (tracking + language):** evaluate **AerialMind** first — **verified
  released and on-task** (2026-06-30T17:07Z; AAAI peer-reviewed, RMOT with track-IDs,
  extends the same VisDrone base we already build on). Falls back to augmenting
  **VisDrone-MOT** with the RDAgent expression generator only if the license chain
  (§5.1) blocks thesis use, which it should not.
- **Do not interrupt the current run** — none of this invalidates it. This is a
  next-round decision.

### 5.1 Open verification items

- ~~AerialMind data-release status and license — confirm before committing effort.~~
  **Resolved 2026-06-30T17:07Z.** Release: **public** — HF `shawnliang0420/AerialMind`
  (24.5 GB, 21 downloads/mo) + Baidu (`pwd=869n`); GitHub `shawnliang420/AerialMind`
  (mind the `0`: HF org is `shawnliang0420`, GitHub is `shawnliang420`). The arXiv-HTML
  "download coming soon" text is **stale** — the live README (pushed 2026-02-08) says
  "Dataset Now Publicly Available". License: **inconsistent metadata** — paper states
  CC BY 4.0, HF tags **MIT**, GitHub has **no LICENSE file**. Binding constraint is the
  upstream chain: imagery derives from **VisDrone (CC BY-NC-SA 3.0, academic-only)** +
  **UAVDT**, which the downstream MIT/CC-BY tag does **not** override. Verdict: **fine
  for the thesis, not for non-commercial-violating use** — identical to RefDrone §2.4.
  **Pulled local 2026-06-30T17:13Z** → `data/AerialMind/` (gitignored): `expression.zip`,
  `labels_with_ids.zip` (MOT track-IDs), `image_02.zip` (frames). Held for a future
  Part III/IV campaign; not yet extracted or wired to a loader. HF README is empty —
  layout reference is the GitHub README, not HF.
- VisDrone CC BY-NC-SA chain into RefDrone's CC BY 4.0 — confirm for thesis use.
- UAVNLT exact size (source page returned 403 during search).

## 6. Sources

- RefDrone — arXiv 2502.00392 · github.com/sunzc-sunny/refdrone
- DIOR-RSVG — arXiv 2210.12634 · OPT-RSVG — github.com/like413/OPT-RSVG
- VRSBench — arXiv 2406.12384 · RRSIS-D — arXiv 2312.12470
- RefSegRS — arXiv 2306.08625 · GeoText-1652 — arXiv 2311.12751
- AerialMind — arXiv 2511.21053 · WebUAV-3M — arXiv 2201.07425
- UAVNLT — MDPI Electronics 13(9):1706 · UAVDT — arXiv 1804.00518
- VisDrone — arXiv 2001.06303 · aiskyeye.com/data-protection
- MOR-UAV — arXiv 2008.01699 · Okutama-Action — arXiv 1706.03038
