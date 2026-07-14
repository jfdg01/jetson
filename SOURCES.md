# SOURCES

External papers, models, and datasets we cite or use. One entry per source:
the link, and **where it was used** (experiment/Part). No descriptions —
the per-experiment README is the source of truth. Append; newest at the bottom.

## Models

- **Swin2SR** — `caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr`
  https://huggingface.co/caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr ·
  https://arxiv.org/abs/2209.11345
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **InternVL3-2B** — `OpenGVLab/InternVL3-2B-hf`
  https://huggingface.co/OpenGVLab/InternVL3-2B-hf
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm A

- **Qwen2.5-VL-3B-Instruct** — `Qwen/Qwen2.5-VL-3B-Instruct`
  https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm B

- **PaliGemma2-3B (pt-448)** — `google/paligemma2-3b-pt-448`
  https://huggingface.co/google/paligemma2-3b-pt-448
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm C

- **Florence-2-large** — `microsoft/Florence-2-large`
  https://huggingface.co/microsoft/Florence-2-large
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm D (cancelled un-run)

- **SmolVLM2-500M-Video-Instruct** — `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`
  https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct
  → [`experiments/2026-06-30-vlm-backbone-bakeoff/`](experiments/2026-06-30-vlm-backbone-bakeoff/README.md) arm E

- **CLIP ViT-L/14 + ViT-B/32** — `openai/clip-vit-large-patch14` · `openai/clip-vit-base-patch32`
  https://huggingface.co/openai/clip-vit-large-patch14 ·
  https://huggingface.co/openai/clip-vit-base-patch32
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) P5.4
  crop-scoring pilot + recorded secondary arm (design-time pilot found vanilla crop scoring
  size-biased on 16-100 px aerial crops)

## Papers / surveys

- **Advancing Image Super-resolution Techniques in Remote Sensing: A Comprehensive Survey**
  https://arxiv.org/pdf/2505.23248
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **Small Object Detection: A Comprehensive Survey on Challenges, ...**
  https://arxiv.org/pdf/2503.20516
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **EDiffSR: An Efficient Diffusion Probabilistic Model for Remote Sensing Image Super-Resolution**
  https://arxiv.org/pdf/2310.19288
  → [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)

- **ReCLIP: A Strong Zero-Shot Baseline for Referring Expression Comprehension**
  (Subramanian et al., ACL 2022) · arXiv 2204.05991
  https://arxiv.org/abs/2204.05991
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) — the
  IPS proposal-scoring method (crop + Gaussian-blur sigma=100 isolation, summed CLIP logits)
  piloted for P5.4 candidate select; falsified at design time on small aerial crops.

- **What does CLIP know about a red circle? Visual prompt engineering for VLMs**
  (Shtedritski et al., ICCV 2023) · arXiv 2304.06712
  https://arxiv.org/abs/2304.06712
  → [`experiments/2026-07-14-crop-select/`](experiments/2026-07-14-crop-select/README.md) — the
  red-circle visual prompt behind the pilot-winning `circlectx` variant (P5.4 secondary arm).

## Datasets

- **RefDrone** — `sunzc-sunny/RefDrone`
  https://huggingface.co/datasets/sunzc-sunny/RefDrone
  → Part II / Part III grounding eval

- **AerialMind** (AAAI 2025) — `shawnliang0420/AerialMind` · arXiv 2511.21053
  https://huggingface.co/datasets/shawnliang0420/AerialMind ·
  https://github.com/shawnliang420/AerialMind
  → [`docs/dataset-survey-refdrone.md`](docs/dataset-survey-refdrone.md) §4 — candidate
  Part III/IV temporal (RMOT) dataset. Academic-only (VisDrone NC-SA chain).
- **SAM2.1 (hiera-tiny)** — `facebook/sam2.1-hiera-tiny` · `sam2==1.1.0` ·
  https://github.com/facebookresearch/sam2 — zero-shot memory-carry tier of the temporal
  acquire-carry campaign (video predictor: box prompt → per-frame mask propagation).

- **UAV123** — aerial single-object-tracking benchmark (Mueller et al., ECCV 2016) ·
  https://cemse.kaust.edu.sa/ivul/uav123 · mirror
  https://huggingface.co/datasets/xche32/UAV123
  → [`experiments/2026-07-03-real-video-replay/`](experiments/2026-07-03-real-video-replay/README.md)
  — real-footage GT (per-frame `x,y,w,h`, 30 fps) for the E18 wall-clock replay scoring.
