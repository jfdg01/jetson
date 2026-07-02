# E1 — Carry operating point: SAM2 encoder TensorRT export (+ EdgeTAM fallback)

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only — the design
below is frozen). **Status:** NOT STARTED — trigger conditions in
`../2026-07-01-temporal-acquire-carry/RUNBOOK.md` Step D.

## Research question

**RQ-E1:** Can a TensorRT fp16 export of the SAM2.1-tiny *image encoder* (memory attention stays
PyTorch) lift Jetson carry FPS enough that an accuracy-passing image size clears the ≥5 FPS
co-resident gate — without breaking mask parity (IoU ≥ 0.99 vs eager on the M0205 100-frame
window)?

Resolves the parent campaign's two open decisions: #1 tracker variant (SAM2 vs EdgeTAM) and
#2 export path (TensorRT vs ONNX Runtime).

## Trigger and target (from the OP rule)

| Parent outcome | This campaign | Target |
|---|---|---|
| OP=640 passed both gates | NOT TRIGGERED — write one line here and stop | — |
| OP=768 (acc PASS, 4.89 FPS) | light branch | ≥5 FPS @768 (needs only ~3% — any speedup wins) |
| OP=1024 (768/640 acc FAIL) | full branch | ≥5 FPS @1024 (needs 1.9× — encoder must be ≥~2.5× faster; if TRT falls short, EdgeTAM step 6) |

## Why encoder-only

Per-frame carry cost is encoder-dominated (ViT-Hiera forward on the full frame each frame; memory
attention operates on small feature maps). Exporting only `predictor.image_encoder` avoids ONNX-ing
the stateful memory bank — the known-hard part. Given up: end-to-end engine (more speedup,
weeks of risk).

## Plan (frozen)

Work on host 3090 for steps 1–2 (`.venv-ft`), Jetson for 3–5. Raw logs → `raw/`, metrics →
`runs/`. Document every install here (name, version, why).

1. **Export wrapper (3090).** `export_encoder.py` in this dir: load the tiny predictor exactly as
   `carry_eval.py` does, wrap `image_encoder` in a small `nn.Module` whose forward returns the
   flattened tuple (3 backbone_fpn tensors + 3 vision_pos_enc tensors). `torch.onnx.export`,
   opset 17, fixed input `(1,3,S,S)` float32, S = OP. Known pitfall: Hiera windowed attention may
   hit unsupported ops.
   `ADVISOR (if export errors): "torch.onnx.export of the SAM2.1 hiera-tiny image_encoder at
   opset 17 fails with <error>. Known workarounds before I try dynamo export or op rewrites?"`
2. **Parity (3090).** (a) `onnxruntime-gpu`: max-abs-diff on all 6 outputs vs eager fp32,
   accept < 1e-2. (b) End-to-end: monkeypatch `predictor.forward_image` to rebuild the
   backbone_out dict from ORT outputs; run the existing M0205 100-frame stream-vs-eager check,
   gate **IoU ≥ 0.99**. FAIL → stop, advisor.
3. **Engine build (Jetson).** scp the .onnx; `/usr/src/tensorrt/bin/trtexec --onnx=enc<S>.onnx
   --fp16 --saveEngine=enc<S>.plan --memPoolSize=workspace:2048`. Record trtexec's reported
   latency (= encoder ms budget). Engines are device-specific: never copy .plan files between
   machines.
4. **Runtime integration (Jetson).** Plan A (less code): `onnxruntime-gpu` with
   TensorrtExecutionProvider inside `~/sam2-bench/.venv` — wheel from the
   `pypi.jetson-ai-lab.io/jp6/cu126` index (same index that fixed torch; pin what works, document
   it). Plan B if no working wheel: TensorRT Python API (system bindings — recreate venv with
   `--system-site-packages`) + manual engine execution. Either way the integration point is one
   monkeypatch of `forward_image` in `jetson_carry_bench.py` / `jetson_percept.py` (flag
   `--trt-encoder <path>`).
5. **Re-bench + accuracy proxy (Jetson).** `jetson_carry_bench.py --image-size <OP> --tag trt-<OP>`
   solo and co-resident. Then the fp16 accuracy proxy: M0205 100-frame IoU vs GT, must be within
   1 pp of eager on the same window (full 186-track re-eval only if adopting for the thesis
   number). Gate: **co-resident FPS ≥ 5 at an ACC_PASS size**.
6. **Fallback (only if step 5 misses the gate): EdgeTAM.** facebookresearch/EdgeTAM (RepViT-M1
   encoder, SAM2-style API — verify the API against the repo before coding; add to SOURCES.md).
   Bench with `jetson_carry_bench.py` adapted (predictor construction differs), accuracy with
   `carry_eval.py` adapted on the 3090 (same 186 tracks, same ACC_PASS ≥ 0.799 rule).
   `ADVISOR (before starting step 6): "TensorRT @<S> reached <x> FPS, gate needs 5. About to
   fall back to EdgeTAM — sanity-check the integration plan: <paste plan>."`

## Config

3090 host: `.venv-ft` (torch 2.6). Jetson: Orin Nano 8 GB, 15 W (`sudo nvpmodel -m 1` — verify
with `sudo nvpmodel -q`), jetson_clocks on, JetPack 6/cu126, torch 2.8.0, venv `~/sam2-bench/.venv`.
Co-resident VLM: Qwen2-VL-2B Q8_0 llama-server (boot line in the parent campaign README, Phase 2
config).

## Estimates (mark actuals vs these)

- Export + parity: 1–2 h. Engine + integration: 1–3 h.
- ESTIMATE speedup: encoder is ~70–75% of the 204.5 ms p50 @768; a 2× fp16 encoder gives
  ~130 ms → **~7.5 FPS @768** (gate PASS with margin). @1024 (373 ms p50): ~230 ms → ~4.3 FPS —
  still short of 5, which is why the full branch carries the EdgeTAM fallback.
- ESTIMATE EdgeTAM: 2–4× tiny's throughput at equal size; accuracy vs our 0.849 baseline unknown —
  that uncertainty is the reason SAM2+TRT is tried first.

## Results (TBD)

| step | size | FPS solo | FPS co-res | parity/acc | verdict |
|---|---|---|---|---|---|
| eager baseline | | | | | |
| TRT encoder | | | | | |
| EdgeTAM (if run) | | | | | |

## Definition of done

README filled (incl. estimate-vs-actual), RESULTS/QUESTIONS rows in
`docs/{results,questions}/part4-end-to-end.md`, DECISIONS entry (variant + export path — closes
parent open decisions #1/#2), SOURCES.md if EdgeTAM used, commit.
