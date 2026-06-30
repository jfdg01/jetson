# SOURCES

External papers, models, and datasets we cite or use. One entry per source:
the link, and **what we used it for** (so it can be cited in the thesis later).
Append; don't overwrite. Newest at the bottom of each section.

## Models

- **Swin2SR** — `caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr`
  https://huggingface.co/caidas/swin2SR-realworld-sr-x4-64-bsrgan-psnr ·
  paper: https://arxiv.org/abs/2209.11345 (Conde et al., ECCV 2022 AIM workshop) ·
  HF docs: https://huggingface.co/docs/transformers/model_doc/swin2sr
  *Used for:* candidate learned super-resolution upscaler for the ROI-crop lever —
  tested against classical interpolation (LANCZOS/BICUBIC) to see if it lifts grounding
  IoU on tiny aerial targets. Chosen because it targets **compressed-JPEG** SR (matches
  VisDrone's degradation) and the PSNR weight is conservative (less hallucination than a
  GAN-SR), which matters for localization. ONNX export exists for an eventual Jetson path.
  *Outcome (2026-06-30, [`experiments/2026-06-30-roi-sr-upscale/`](experiments/2026-06-30-roi-sr-upscale/README.md)):*
  **rejected** — on oracle 400² crops it was the worst of three upscalers
  (78.6% IoU@0.25, below even no-upscale 78.8%) and cost +1331 ms/crop; classical
  bicubic/lanczos win for free. Kept as a negative thesis result.

## Papers / surveys

- **Advancing Image Super-resolution Techniques in Remote Sensing: A Comprehensive Survey**
  https://arxiv.org/pdf/2505.23248
  *Used for:* landscape scan of remote-sensing SR (June 2026) when choosing an SR model —
  established that niche RS-SR is mostly diffusion/Mamba research code (too slow / packaging
  friction for our Jetson budget), justifying the choice of a general but degradation-matched
  model (Swin2SR).

- **Small Object Detection: A Comprehensive Survey on Challenges, ...**
  https://arxiv.org/pdf/2503.20516
  *Used for:* background on small/tiny-object detection in aerial imagery; supports the
  framing that few-pixel targets are the binding constraint our preprocessing levers attack.

- **EDiffSR: An Efficient Diffusion Probabilistic Model for Remote Sensing Image Super-Resolution**
  https://arxiv.org/pdf/2310.19288
  *Used for:* representative of the diffusion-based RS-SR branch we considered and rejected
  for deployment (multi-step sampling can't meet the ~2 s anchor budget); kept as offline-only
  reference.

## Datasets

- **RefDrone** — `sunzc-sunny/RefDrone` (referring expressions over VisDrone images)
  https://huggingface.co/datasets/sunzc-sunny/RefDrone
  *Used for:* the aerial grounding target domain (caption → box). Well-posed single-box
  subset is the supervision; images are VisDrone2019-DET frames.
