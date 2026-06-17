# Research Prompt: Prior-Art / "Has Someone Already Done This?" Search

**Purpose:** Feed this prompt into a deep-research LLM (Claude Opus with extended
thinking, Perplexity Deep Research, GPT Deep Research, etc.). Its goal is **not** a
broad academic survey — that already exists in this repo
([`research-prompt-drone-vlm.md`](research-prompt-drone-vlm.md), answered in
[`literature-sweep.md`](literature-sweep.md)). The goal here is narrow and
reuse-first: **find out whether someone has already done the specific thing we are
trying to build, so we can stand on their work instead of re-deriving it.**

Pursue the three objectives below **in strict priority order**. Spend the most effort
on Objective 1; only move to 2 if 1 yields no drop-in solution; only move to 3 if 2
yields no reusable checkpoint. Report findings per objective even if the answer is
"nothing exists" — a confirmed *absence* is a valuable result (it confirms the thesis
gap and tells us we must build, not borrow).

> **What we want out of this:** concrete, linkable artifacts we can clone, download,
> or fine-tune from — GitHub repos, Hugging Face model/dataset cards, project pages,
> papers *with released code/weights*. Prefer something runnable over something merely
> described. For every artifact: give the URL, the license, the last-updated date, and
> a one-line "why it does / doesn't fit our hardware."

---

## What we are building (the exact target)

A master's-thesis system: **natural-language-commanded drone object following**,
running **entirely on a Jetson Orin Nano 8 GB**. A user says *"follow the white car"*;
the on-device model takes a camera frame + the command and emits a **structured
grounding output** (a bounding box, normalized coordinates) that feeds a tracker /
flight controller. The model only needs to run at **0.5–3 Hz** (the autopilot holds
track between updates), so latency is forgiving but the **memory ceiling is hard**.

The narrow capability we need is **aerial / drone-viewpoint referring-expression
grounding**: NL phrase → one bounding box, on small top-down objects, on a model that
fits the budget below. That specific combination — *aerial grounding* × *sub-1B-or-
quantized VLM* × *Jetson-class edge* — is what we want to find prior art for.

---

## Hardware Context (measured on the target device — treat as ground truth)

**Device:** NVIDIA Jetson Orin Nano 8 GB Developer Kit (Tegra234 / Orin, Ampere,
1024 CUDA cores, compute capability **sm_87**, JetPack 6.2.2, CUDA 12.6, L4T R36.5.0).
**Memory:** 8 GB LPDDR5 **unified** CPU+GPU (7.4 GiB visible); after OS, budget
**~6–6.5 GB** for weights + KV cache. **No dedicated VRAM.**
**Power modes:** only **15 W** (default) and **7 W** — the 25 W "Super"/MAXN mode is
*not* enabled on this unit.
**Runtime:** llama.cpp commit `57fe1f0`, `llama-server` + Python urllib client, CUDA
`sm_87`. GGUF models, `mmproj` multimodal projector files. All numbers below at **15 W
locked** (`nvpmodel -m 0` + `jetson_clocks`).
**Practical ceiling:** ~6.4 GB resident. A 12B Gemma-3 hard-OOM'd at load
(`cudaMalloc` failed). Models above ~6.4 GB resident are non-starters without
aggressive partial offload.

### Measured VLM throughput on this device (llama-server, warm, N=5 frames)

`per_frame_ms = prompt_ms + predicted_ms` (CLIP encode is inside `prompt_ms`; wall-clock
residual ≤10 ms).

| Model | Params | img tokens | per_frame_ms | Hz | Peak RAM MB | Grounding quality (N=3 informal) |
|---|---|---|---|---|---|---|
| SmolVLM-256M-Instruct Q8_0 | 0.26 B | 64 (fixed) | **304 ± 65** | **3.29** | 1777 | poor (incoherent JSON, wrong targets) |
| SmolVLM-500M-Instruct Q8_0 | 0.50 B | 64 (fixed) | **338 ± 148** | **2.96** | 2241 | partial (sometimes right class) |
| Gemma-3-4B-it q4_0 | 4.0 B | 256 | **9576 ± 98** | **0.10** | 6414 (swap) | good (right class+colour, valid JSON) |
| Gemma-4-E2B-it q4_0 QAT | 5.1 B | 144 | **2035 ± 611** | **0.49** | 4616 | partial (right class, inconsistent) |
| Gemma-4-E4B-it q4_0 QAT | 8.0 B | 144 | **2963 ± 576** | **0.34** | 6444 (swap) | partial |

**Implications for what counts as "runs easily on the Orin Nano":**
- The **comfortable** envelope is a sub-1B VLM (SmolVLM-256M/500M): ~2–3 GB resident,
  3 Hz, no swap, leaves room for a tracker. These are weak grounders out-of-the-box.
- **Gemma-4-E2B** (4.6 GB, 0.49 Hz, no swap) is the largest model that fits without
  swap and is usable with command-rate decimation, but it is a reasoning model
  (`--reasoning off` mandatory) and grounds inconsistently zero-shot.
- Anything that swaps (Gemma-3-4B, Gemma-4-E4B at ~6.4 GB) is effectively non-real-time.
- **So the sweet spot we most want prior art for is a small (≤~1B, or ≤~2B quantized)
  VLM that has been *taught* aerial grounding** — i.e. someone who already closed the
  capability gap we're chasing.

---

## What we have already done (so you can target the gap, not repeat us)

Our own fine-tuning lineage on a SmolVLM-500M base (frozen SigLIP vision encoder, text-
backbone LoRA r=16 α=32, normalized **0–1000** integer coordinate bins à la
PaliGemma/Florence-2, GGUF Q8_0 export reusing the stock `mmproj`):

- **Stage 2 — FAILED (mode collapse).** Text-LoRA directly on RefDrone. Root cause:
  **ill-posed target** (RefDrone is mdetr-format, one caption → ~3.8 boxes). IoU@0.25 ≈ 1%.
- **Stage 3 — PASSED on ground-level.** Re-posed the objective on **RefCOCO**
  (many captions → one box, large objects, normalized coords). **RefCOCO IoU@0.25 = 82.5%**
  — proves the *machinery + coordinate protocol + GGUF export* are sound. But RefCOCO is
  ground-level; **cross-domain aerial transfer measured at only 2.0%.**
- **Stage 4 — in progress.** RefCOCO→RefDrone **curriculum** on the well-posed (one-box)
  RefDrone subset (4,101 train / 439 val). Open question / core difficulty: **VisDrone
  objects are 5–30 px native, i.e. 2–11 px after 512-px long-edge resize, fed through a
  *frozen* SigLIP encoder** — that tiny-object-through-frozen-vision bottleneck is the
  crux. Documented next levers if it stalls: higher input resolution, largest-box
  augmentation, vision-encoder LoRA.

**This is exactly why the prior-art search matters:** if someone has already trained a
small VLM that grounds tiny aerial objects (or already solved the frozen-vision /
resolution bottleneck), we can warm-start or drop it in instead of grinding through
Stage 4+. Frame your findings against this lineage — tell us what specifically would
let us skip or shortcut a stage.

---

# Objective 1 (HIGHEST PRIORITY) — Has anyone shipped an end-to-end aerial-grounding VLM that runs on Orin-Nano-class hardware?

Find any **complete, runnable system** that does NL-commanded grounding/detection/
following from a **drone/aerial viewpoint** on **edge hardware in our class** (Jetson
Orin Nano / NX / AGX, or comparable ≤8 GB unified-memory SoC; ideally something that
fits our ~6.4 GB ceiling and 0.5–3 Hz target).

Look specifically for:
- **GitHub projects / theses / product demos** of "talk to your drone" or "NL → track
  this object" that actually run on a Jetson (not on an A100 in the cloud). Hobbyist,
  industrial (Skydio-style autonomy), and academic demos all count.
- Anyone who reports **measured latency / memory on a Jetson** for an aerial-VLM
  grounding or referring task — so we can compare directly to our table above.
- Modular pipelines (VLM/grounder → tracker → controller) released as code, *and*
  end-to-end learned systems (image+NL → box/action) with weights.
- Work using the same runtime family we use: **llama.cpp / GGUF / mmproj** multimodal,
  or `ollama`, or TensorRT/`jetson-containers` VLM deployments on aerial tasks.

For each hit, state: does it run within our memory + rate budget? Is the code/weights
released and licensed for reuse? Could we run it **as-is**, or what would have to
change? **If nothing genuinely end-to-end-on-edge exists, say so explicitly** — that
confirms our thesis gap, and we then fall through to Objective 2.

---

# Objective 2 — Has anyone already trained a small, reusable model/checkpoint for aerial referring-expression grounding?

If no whole system exists, the next-best shortcut is a **released checkpoint** we can
deploy or warm-start from — ideally without re-training. Find:

- **Hugging Face / GitHub checkpoints** of small VLMs fine-tuned for **referring-
  expression grounding or open-vocabulary detection on aerial/UAV imagery** (VisDrone,
  DOTA, DIOR, xView, etc.). Class names: SmolVLM, PaliGemma / PaliGemma-2 (native
  `<locXXXX>` detection tokens), Florence-2, Idefics, Qwen2-VL / Qwen2.5-VL grounding,
  MiniCPM-V, Moondream, LLaVA-style, Grounding-DINO / YOLO-World (open-vocab detectors).
- **Specifically aerial grounding checkpoints** — anyone who published weights for
  NL→box on drone imagery. Even non-edge checkpoints matter: if the *weights* exist and
  the architecture can be **quantized to GGUF and fit our budget**, that's a warm-start.
- **PaliGemma-2-3B** fine-tunes for detection/grounding (its `<locXXXX>` scheme is
  closest to our normalized-bin target) — has anyone done aerial PaliGemma grounding,
  and does a 3B PaliGemma quantize into our ceiling?
- The **base small-VLM grounding checkpoints** themselves (e.g. SmolVLM/Florence-2
  grounding variants) and how their reported RefCOCO/aerial numbers compare to our
  Stage 3 RefCOCO 82.5% and our ~2% aerial floor.

For each checkpoint, report: base architecture & param count; what it was trained on;
**reported grounding accuracy (IoU / Acc@0.5) on aerial vs. ground benchmarks**;
license; **is it GGUF/llama.cpp-exportable, and what is its likely resident footprint
quantized?**; and concretely — **could we (a) run it on the Orin Nano, (b) warm-start
our Stage 4 from it, or (c) neither?** Flag anything that already solved the **tiny-
aerial-object / frozen-vision-encoder bottleneck** we hit (e.g. via high-res tiling or
a vision-encoder fine-tune).

---

# Objective 3 — What is the best dataset (or set of datasets) for this niche?

Only if Objectives 1–2 don't hand us a ready solution, we'll train it ourselves — so
find the **best fuel**. We need **(aerial image, NL referring expression, bounding box)**
triplets, ideally *well-posed* (one phrase → one box, matching our deployment contract
and avoiding the Stage 2 mode-collapse trap).

Survey and rank:
- **Aerial NL-grounding datasets:** RefDrone (we use the well-posed subset),
  **UAVNLT**, **AerialMind**, and any newer (2024–2026) aerial referring-expression or
  aerial visual-grounding datasets. For each: size, % one-box vs multi-box captions,
  image resolution, object pixel sizes, annotation format (mdetr/COCO/xyxy), license.
- **NL aerial tracking sets** usable as grounding (initial-frame referent → box):
  **TNL2K**, **UAVNLT**, plus tracking benchmarks (**UAV123, UAVDT, VisDrone-VID,
  DTB70**) that *lack* NL — note these as candidates for **auto-labeling**.
- **Auto-labeling recipes:** if annotated aerial NL data is thin, what's the best way to
  generate (image, NL, box) triplets from an unlabeled/detect-only aerial set (VisDrone-
  DET, DOTA, DIOR) — large-VLM captioning of GT boxes, template generation from class +
  attributes + position, etc.? Cite anyone who did this for aerial.
- **Ground-level grounding sets for curriculum/pretraining:** RefCOCO/+/g (we used
  RefCOCO), Visual Genome, GRIT — relevant only as the warm-start stage of a curriculum
  into aerial.

Output a **ranked recommendation**: which single dataset (or curriculum sequence) gives
the best shot at clearing a real aerial-grounding bar on a small VLM, the preprocessing
needed (well-posed filtering, resolution handling for tiny objects), and the license
posture for a thesis.

---

## Output format

Structure the answer as three sections matching Objectives 1 → 2 → 3, in that order.
Within each:

1. **Verdict first:** does a reusable artifact exist? (yes/partial/no) — one sentence.
2. **The artifacts:** a table — name · URL · type (system/checkpoint/dataset) · license ·
   last updated · **fits our hardware? (Y/N + why)** · reuse path (run as-is / warm-start /
   reference only).
3. **What it means for us:** 2–3 sentences relating it to our Stage 2→3→4 lineage and the
   hardware budget — specifically, *what stage or work it lets us skip.*

End with a short **"Fastest path to a working system"** recommendation that explicitly
chains the best findings across the three objectives (e.g. "deploy checkpoint X →
fine-tune on dataset Y → fall back to building Z").

**Honesty mandate:** prefer a confirmed "nothing exists here" over an inflated match.
If an artifact is cloud-only, abandoned, wrongly licensed, or won't fit ~6.4 GB, say so
plainly. A precise map of what is genuinely reusable vs. what we must build ourselves is
the whole point.
