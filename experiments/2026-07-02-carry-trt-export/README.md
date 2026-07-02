# E1 — Carry operating point: SAM2 encoder TensorRT export (+ EdgeTAM fallback)

**Pre-registered:** 2026-07-02T10:51Z (planning session; executor fills Results only — the design
below is frozen). **Status:** COMPLETE 2026-07-02T14:52Z — **RQ-E1 = YES**. TRT fp16 encoder lifts
768 carry 4.89 → 6.15 FPS co-resident (clears the ≥5 gate), IoU@0.25 unchanged (1.000, mean IoU
0.826 vs 0.821 eager — fp16 does not degrade), mask parity 1.000. EdgeTAM fallback NOT needed.

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

- Export + parity: 1–2 h. Engine + integration: 1–3 h. **ACTUAL: ~1 h total** (export+parity ~15
  min, engine build ~4 min, integration+bench ~30 min). Faster than estimated — no export op
  failures (opset-17 direct export worked first try, no dynamo/rewrites), TRT Python API binding
  torch tensors avoided the ORT-wheel hunt.
- ESTIMATE speedup: encoder ~70–75% of 204.5 ms p50 @768; 2× fp16 encoder → ~130 ms → **~7.5 FPS**.
  **ACTUAL: 162.4 ms → 6.15 FPS** — the encoder DID roughly halve (trtexec median GPU compute
  65.1 ms vs eager encoder est. ~150 ms, ~2.3×), but the per-frame saving was ~42 ms not ~75 ms:
  the retained torch memory-attention + the TRT stream sync (default-stream `execute_async_v3`)
  eat into it. Still a comfortable gate PASS (6.15 ≥ 5, +26% over eager 4.89).
- ESTIMATE EdgeTAM: not reached — SAM2+TRT cleared the gate at 768, so step 6 was skipped.

## Installs (per working-agreement)

- **3090 `.venv-ft`:** `onnx==1.22.0`, `onnxruntime==1.27.0` (CPU) via `uv pip install` — host
  parity only needs fp32 ONNX-graph correctness; the gpu wheel wanted CUDA 13 (host is cu124), so
  CPU ORT was the lazy-correct path (fp16/TensorRT accuracy is validated on-device instead).
- **Jetson `~/sam2-bench/.venv`:** no pip install — symlinked the system TensorRT 10.3.0 python
  bindings (`/usr/lib/python3.10/dist-packages/tensorrt`) into the venv site-packages. Exposes only
  `tensorrt` (numpy stays pinned 1.26.4, no shadowing); reuses the JetPack TRT that built the plan.

## Results

| step | size | FPS solo | FPS co-res | parity/acc | verdict |
|---|---|---|---|---|---|
| eager baseline | 768 | 4.89 (parent) | 4.89 (p50 204.6 ms) | IoU@0.25 1.000 / mean 0.821 (M0205 win) | reference |
| TRT encoder | 768 | 6.15 (p50 162.5) | **6.15** (p50 162.4, RAM 4980/7607) | 2a max-diff 3.1e-04, 2b mask IoU 1.000; on-device IoU@0.25 **1.000** / mean 0.826 (Δ +0.006, IoU@0.25 Δ 0.00 pp) | **PASS** |
| EdgeTAM (if run) | — | — | — | not needed (SAM2+TRT cleared the gate) | skipped |

trtexec enc768.plan (fp16, workspace 2048): median GPU compute **65.12 ms**, 15.07 qps. Raw:
`raw/trtexec_enc768.log`, `raw/boxes_trt.json`; metrics `runs/bench.json`.

## Deviation from frozen plan (recorded, not silent)

Step 4 said "Plan A (less code): onnxruntime-gpu TensorrtExecutionProvider". **Used Plan B instead**
(TensorRT Python API + torch-tensor bindings), for three reasons found at execution: (1) the Jetson
venv had *neither* onnxruntime nor tensorrt — Plan A needed a wheel hunt on the jetson-ai-lab index;
(2) system TensorRT 10.3.0 was already present (built the plan), so Plan B added zero dependencies;
(3) ORT's numpy `sess.run` I/O forces a host round-trip per frame, defeating the latency goal —
binding torch `data_ptr()` keeps everything on-GPU. Integration point unchanged (one `forward_image`
monkeypatch behind `--trt-encoder`, in `jetson_carry_bench.py`; `jetson_percept.py` gets the same
patch when 3b re-runs).

## Definition of done

- [x] README filled (estimate-vs-actual, installs, deviation).
- [x] RESULTS/QUESTIONS rows in `docs/{results,questions}/part4-end-to-end.md`.
- [x] DECISIONS entry (variant + export path — closes parent open decisions #1/#2).
- [n/a] SOURCES.md — EdgeTAM not used, no new source.
- [x] commit.
