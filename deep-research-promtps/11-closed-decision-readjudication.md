# DR-11 — Re-adjudicating a closed model bake-off: fundamental limit or premature closure?

## Context (assume no prior knowledge)
For a UAV natural-language grounding thesis on a **Jetson Orin Nano 8 GB**, I selected my
grounding vision-language model — **Qwen2-VL-2B-Instruct (Q8_0)** — via a fine-tuning bake-off that
I **early-stopped**. I now worry I dismissed competitors on thin evidence and am building the rest
of the thesis on that unexamined call. I want the external literature to tell me, per competitor,
whether my rejection reflects a *fundamental* limitation others confirm, or a **harness / recipe /
data artifact** I would likely fix if I ran it properly.

**My regime (important — competitors were judged inside it):** referring-expression grounding on
drone imagery, coordinates emitted as text ("terse int" strings), LoRA fine-tune of the language
subtree with the vision tower frozen, and a heavy **ROI-crop + LANCZOS-upscale-to-512px**
preprocessing step (crop the region, upscale, then ground). Metric = IoU@0.25.

**What actually happened in the bake-off (the thin part):**
- **Qwen2.5-VL-3B** — "collapsed to ~33% IoU@0.25" *in my ROI-crop regime*. I read this as a loss;
  it may be a preprocessing/coordinate-format mismatch specific to that model.
- **PaliGemma2-3B** — ran, lost.
- **SmolVLM2-500M** — LoRA fine-tune **capacity-collapsed** (boxes became near-constant guesses;
  loss trained fine but center_std tiny). Read as too small.
- **Florence-2-large** — driver written but **never run** (cancelled at early-stop). Zero data.
- **InternVL3-2B** — loser arm, blocked.

## Research question
For small (≤3 B) grounding/referring VLMs — specifically **Qwen2.5-VL-3B, PaliGemma2, Florence-2,
InternVL 2.5/3.x, SmolVLM2** — what does the 2024–2026 literature and practitioner experience say
about (a) the **correct fine-tuning + inference recipe** for referring-expression grounding, and
(b) known **failure/collapse modes** that mimic "this model is bad" but are actually recipe bugs —
so I can tell which of my rejections were premature?

## Sub-questions to cover
- **Coordinate representation** per model: does each expect normalized 0–1000 vs pixel vs special
  location tokens (PaliGemma `<locNNNN>`, Florence loc-tokens, Qwen absolute vs normalized)? A
  format mismatch would produce exactly a "33% collapse" — is that the likely cause for Qwen2.5-VL-3B?
- **Crop-and-upscale preprocessing**: do these models tolerate / benefit from ROI-crop+upscale, or
  do some (e.g. PaliGemma fixed 448, Qwen dynamic-resolution) get *hurt* by it? Is my regime
  quietly biased toward the one model I kept?
- **LoRA scope & capacity**: recommended target modules, rank, LR for grounding fine-tunes on each;
  is SmolVLM2-500M's capacity-collapse a known small-model issue or an under-tuned LoRA?
- **Florence-2 for referring grounding**: reported referring/grounding numbers and edge-deployment
  reports — was it worth running, or safely skippable?
- **Fair-comparison protocol**: what minimum recipe (format, resolution, LoRA config, eval) makes a
  small-grounding-VLM bake-off *fair*, so I can state which arms were genuinely beaten vs
  under-implemented.
- **Methodological**: guidance on when early-stopping a comparison is safe vs when it bakes in a
  confound (a competitor killed before its correct recipe was found).

## Constraints / priorities
- Target metric is **localization** (IoU@0.25 on referring), not VQA/caption quality.
- Deployability on 8 GB Orin Nano matters, but this prompt is about **fair adjudication first** —
  was each arm given its best shot before I closed the bake-off?
- Prioritise concrete recipes, coordinate-format docs, and reproduction reports over leaderboards.

## Desired output
A per-model verdict: **"fairly beaten"** vs **"likely premature — here's the recipe/format fix to
retest"**, each with the specific coordinate-format / preprocessing / LoRA correction to try and a
citation. End with a minimal fair-bake-off protocol I could re-run to settle the incumbent choice
with confidence. Be willing to conclude some rejections were correct — the goal is calibrated, not
contrarian.
