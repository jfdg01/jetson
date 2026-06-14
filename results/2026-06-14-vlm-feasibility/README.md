# Campaign: VLM Feasibility for Drone Vision Commands (Jetson Orin Nano 8 GB)

**Date (protocol drafted):** 2026-06-14  
**Status:** 📋 **Pre-registration** — design fixed before data collection.  
**Builds on:**
- [`results/2026-06-13-model-capability-sweep.md`](../2026-06-13-model-capability-sweep.md) — text-only throughput baseline across the 0.5–8 B size range.
- [`results/2026-06-14-gemma-family-sweep/`](../2026-06-14-gemma-family-sweep/) — Gemma-family deep dive (G1–G4 on device, text weights and throughput already measured).
**Operator:** automated over `ssh jetson` (user `jfdg`); measurement tool is `llama-server` + Python urllib client (not `llama-bench` — confirmed no image support; not `llama-mtmd-cli` — can't do multi-frame warm measurement; see §12 decisions).

---

## 1. Motivation & scope

The text-only campaigns established that the Orin Nano can sustain 12–104 tok/s decode
across the 0.27–8 B parameter range. The thesis application is drone navigation: given a
camera frame and a natural-language command such as *"follow that white car"*, the system
must produce a structured flight instruction. This requires **visual grounding** — the
ability to locate a referent object in an image — which text-only LLMs cannot provide.

This campaign asks: **can a vision-language model (VLM) running entirely on the Orin Nano
meet the latency and capability requirements of a drone command loop?**

The campaign simultaneously resolves the architectural fork introduced at the start of
the vision work:
- **Option A — end-to-end VLM**: camera frame + query → VLM → command.
- **Option B — decomposed**: a fast YOLO-class detector handles visual grounding; the LLM
  only parses intent.

The decision criterion is empirical: **measured per-frame latency vs. the required control
rate.** That rate is not necessarily "every camera frame" — a high-level re-targeting
command at 0.5–2 Hz (with the drone's own controller holding between updates) may be
viable even at 1–2 s/frame. We state this explicitly so we don't write off end-to-end
VLMs prematurely.

---

## 2. Research questions

- **RQ-V1 — Per-frame latency.** What is the wall-clock latency for one vision inference
  cycle (CLIP encode + prefill + command decode) for each VLM on the Orin Nano? How does
  it compare to the 0.5–2 Hz required control rate?
- **RQ-V2 — Vision overhead.** For the Gemma-3-4B and Gemma-4-E2B/E4B models, where text
  weights are already measured, what is the incremental cost of adding the vision encoder
  (mmproj)? This is the cleanest text-vs-vision comparison in the thesis: same backbone,
  same weights, same device.
- **RQ-V3 — Memory budget.** How does the mmproj fit on top of the existing weight + KV
  budget? Does adding vision tip any model over the swap/OOM boundary?
- **RQ-V4 — Capability threshold.** At what model size does VLM object grounding become
  reliable enough to support "follow that white car" semantics? Can the smallest models
  that meet the latency target also ground the referent?
- **RQ-V5 — Image token scaling.** How does image resolution (and the resulting image-token
  count from tiling) affect CLIP encode time and prefill time? Where is the latency cliff?

---

## 3. Hypotheses (stated up front, to be confirmed or falsified)

- **H-V1.** CLIP encode time (mmproj) is roughly constant across text-backbone sizes (it
  depends only on the vision encoder architecture and image resolution, not LLM size).
  Per-frame latency therefore grows mainly with backbone prefill time, which scales
  predictably from the text-only measurements.
- **H-V2.** The 256–500 M SmolVLM models will meet the 2 Hz (500 ms) control rate target;
  the 4–8 B Gemma models will fall in the 1–5 s range and may require command-rate
  decimation to be useful.
- **H-V3.** SmolVLM-256M is too weak to reliably ground specific object attributes (colour,
  class) in real aerial/traffic images. Grounding quality improves with backbone size; the
  3–4 B tier is the likely capability threshold.
- **H-V4.** The mmproj adds 200–400 MB to the resident memory footprint, which is
  manageable for models up to Gemma-3-4B but may push Gemma-4-E4B into swap territory.

---

## 4. Per-frame latency definition and measurement source

> **Methodology verified 2026-06-14** via smoke tests on SmolVLM-256M Q8_0. See §12 for
> decisions. The formula and instrument below supersede the draft version.

### 4.1 Measurement instrument

**`llama-server`** (not `llama-bench` — confirmed no image support; not `llama-mtmd-cli`
— can't do multi-frame in one process cleanly). Protocol:

1. Start `llama-server -m <model> --mmproj <mmproj> -ngl 99 --port 8080`
2. Wait for `/health` to return `ok`
3. Send a **throwaway warmup request** (any image + short prompt, `max_tokens: 5`) to
   trigger CUDA graph compilation
4. For each of N measurement frames: POST to `/v1/chat/completions` with `cache_prompt: false`
   and a different image per frame; record `timings` from `__verbose` in response

Setting `cache_prompt: false` ensures each request processes the full prompt from scratch
(no cross-request KV cache reuse), which is the correct model for drone use where every
frame is a new image.

### 4.2 Per-frame formula

```
per_frame_ms = timings.prompt_ms + timings.predicted_ms
```

**Verified:** for SmolVLM-256M, `prompt_ms + predicted_ms ≈ wall-clock` (≤10 ms residual
across 6 measurements). This confirms that `timings.prompt_ms` **includes CLIP encode
time** — it is not a separate addend. The llama.cpp server starts the prompt timer before
multimodal content is processed.

| Term | Source field | Notes |
|---|---|---|
| `prompt_ms` | `__verbose.timings.prompt_ms` | CLIP encode + LLM prefill of all prompt tokens (image + text) |
| `predicted_ms` | `__verbose.timings.predicted_ms` | Token decode time |
| `prompt_n` | `__verbose.timings.prompt_n` | Total prompt tokens (image tokens + text tokens) |
| `predicted_n` | `__verbose.timings.predicted_n` | Tokens generated |
| `image_tokens` | `prompt_n` minus text-only token count | Derived; verify against server log `n_tokens_batch` |

**Do NOT add a separate CLIP encode term** — it is inside `prompt_ms`. Do NOT use
`llama_perf_context_print: total time` (CLI-only, different accounting).

### 4.3 Cold vs warm; what each measures

| State | How to achieve | What it measures |
|---|---|---|
| **Cold** (first frame after load) | First real request, no warmup request | Includes ~190ms CUDA graph compilation (measured on SmolVLM-256M) |
| **Warm** (steady-state) | After warmup request, subsequent `cache_prompt: false` requests | True per-frame latency; CUDA graphs compiled and reused |

**Report warm** as the headline metric. Report cold as a footnote for cold-start
characterisation (relevant for drone power-off → power-on latency).

Warm–cold delta for SmolVLM-256M: 532ms (cold wall-clock, CLI) vs ~350ms (warm, server)
≈ ~180ms CUDA graph compilation penalty on first frame.

### 4.4 SmolVLM resolution note (and why tiling matters for Gemma)

SmolVLM-256M resizes all inputs to a fixed internal resolution: **64 image tokens
regardless of input size** (verified at 500×500, 1280×640, 2875×1500). Its latency is
therefore resolution-agnostic — no tiling, no per-slice overhead.

Gemma-3 and Gemma-4 use **pan-and-scan tiling**: high-resolution inputs are split into
multiple slices, each producing its own set of image tokens. The tiling behavior for
Gemma models at 1280×720 is unverified; probe `n_tokens_batch` in server log on first run
of V3/V4 and record the actual token count.

---

## 5. Model list

Ordered by size. The Gemma text-vs-vision contrast is the spine of this campaign —
**text weights are already on device for V3, V4, V5**; only the mmproj needs downloading.

| Unit | Model | Params | Vision encoder | Text weights | mmproj needed | Source |
|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M-Instruct Q8_0 | 0.26 B | SigLIP-400M (64 tokens/slice) | download | download | `ggml-org/SmolVLM-256M-Instruct-GGUF` (not gated) |
| V2 | SmolVLM-500M-Instruct Q8_0 | 0.50 B | SigLIP-400M | download | download | `ggml-org/SmolVLM-500M-Instruct-GGUF` (not gated) |
| V3 | Gemma-3-4B-it q4_0 | 4.0 B | SigLIP (256 tokens/img) | **on device** `gemma-3-4b-it-q4_0.gguf` | `mmproj-model-f16.gguf` | `ggml-org/gemma-3-4b-it-GGUF` (gated, HF token needed) |
| V4 | Gemma-4-E2B-it q4_0 QAT | 5.1 B | SigLIP Matryoshka | **on device** `gemma-4-E2B_q4_0-it.gguf` | `mmproj-gemma-4-E2B-it-Q8_0.gguf` | `ggml-org/gemma-4-E2B-it-GGUF` (gated, HF token needed) |
| V5 | Gemma-4-E4B-it q4_0 QAT | 8.0 B | SigLIP Matryoshka | **on device** `gemma-4-E4B_q4_0-it.gguf` | `mmproj-gemma-4-E4B-it-Q8_0.gguf` | `ggml-org/gemma-4-E4B-it-GGUF` (gated, HF token needed) |

**V5 (Gemma-4-E4B) is a stretch goal.** At 8 B + mmproj it may OOM or swap heavily.
It runs only if V4 loads cleanly with headroom. A load failure is a valid negative result
and must be recorded.

Gemma-4 image-token count may differ from Gemma-3's 256 — the Matryoshka encoding can
vary with resolution. Probe this explicitly from the log lines on first run.

---

## 6. Test image set

**Fixed and committed before any run** — the images are a controlled variable.
Three images committed at `results/2026-06-14-vlm-feasibility/test-images/`:

| ID | Filename | Resolution | Description |
|---|---|---|---|
| `img-1` | `highway-with-firetruck.jpg` | 768×432 | Highway crash scene; firetruck + multiple vehicles |
| `img-2` | `multiple-collision.jpg` | 347×280 | Multi-vehicle collision, mixed vehicle types and colours |
| `img-3` | `white-van-crash.jpeg` | 480×270 | Crash scene with prominent white van — primary grounding target |

**Deviation from pre-registration:** original spec called for three images named
`car-ground/car-aerial/cars-ambiguous` at 1280×720. User provided crash-scene images at
three different native resolutions (768×432, 347×280, 480×270). The white vehicle referent
is clearly present in `img-3`. No aerial POV image was available; this limits the
realism of the grounding evaluation. The three native resolutions (rather than fixed
320×240/640×480/1280×720 rescales) serve the Gemma tiling probe (RQ-V5) more authentically.

Warmup request uses `img-1` (largest, most complex — harshest warmup). Measurement frames
cycle through all three images in order (`img-1`, `img-2`, `img-3`, repeat) with
`cache_prompt: false` per request.

---

## 7. Benchmark protocol (per unit)

**Tool:** `llama-server` + Python `urllib` client (stdlib, no pip deps). `ffmpeg` must be
installed on the Jetson (`sudo apt install -y ffmpeg`) — required for server image decoding.

```bash
# Step 1: start server (one-time per model)
~/llama.cpp/build/bin/llama-server \
  -m ~/models/<text_model>.gguf \
  --mmproj ~/models/<mmproj>.gguf \
  -ngl 99 --port 8080 -v \
  > /tmp/vlm-server.log 2>&1 &

# Wait for ready
until curl -s http://localhost:8080/health | grep -q ok; do sleep 1; done

# Step 2: run measurement via Python (see experiments/run_vlm_campaign.py)
# The script:
# 1. Sends a warmup request (throwaway, max_tokens=5, any image)
# 2. Sends N=5 measurement requests with DIFFERENT images (cache_prompt=false)
# 3. Reports prompt_ms, predicted_ms, per_frame_ms, image tokens from __verbose.timings
# 4. Also runs tegrastats in background for power/RAM

killall llama-server
```

**Prompt (fixed across all models and units):**
```
You are a drone flight controller. What object should the drone follow in this image?
Reply in JSON: {"action": "follow", "target": "<object description>"}
```

**Prompt design rationale:** Structured JSON output produces a realistic ~20–30 token
decode. Fixed text controls cross-model prompt token count differences.

---

## 8. Controlled variables

| Variable | Value | Rationale |
|---|---|---|
| Runtime | llama.cpp `57fe1f0`, `llama-server` + Python urllib, CUDA `sm_87` | Same binary; `libmtmd.so` confirmed present; ffmpeg installed on Jetson (required for image decoding) |
| Power mode | 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) | Consistent with all prior campaigns |
| GPU offload | `-ngl 99` (full, for both LM and mmproj) | Default for this device; mmproj offload on by default in mtmd |
| Test image | `car-ground.jpg`, 1280×720 | Fixed; resolution probed separately in §11 |
| Output length | `-n 30` | ~20-token structured command; consistent across models |
| Passes | 2; report warm (pass 2) | Eliminates CUDA graph compilation from the headline number |

---

## 9. Dependent variables (measured)

> **Note:** source fields updated 2026-06-14 to match verified llama-server methodology (§4.2).
> Original draft listed CLI log-scraping fields (`clip_encode_ms` from log lines, `n_slices`
> from log). Those fields are replaced by the server `timings` JSON block.

| Metric | Source | Notes |
|---|---|---|
| `prompt_ms` | `response.__verbose.timings.prompt_ms` | CLIP encode + LLM prefill — combined; CLIP is *inside* this (verified §4.2) |
| `predicted_ms` | `response.__verbose.timings.predicted_ms` | Token decode time |
| `prompt_n` | `response.__verbose.timings.prompt_n` | Total prompt tokens (image tokens + text tokens) |
| `predicted_n` | `response.__verbose.timings.predicted_n` | Tokens generated |
| **`per_frame_ms`** | **Derived: `prompt_ms + predicted_ms`** | **Headline metric (verified §4.2; wall-clock residual ≤10 ms)** |
| **`per_frame_hz`** | **Derived: `1000 / per_frame_ms`** | **vs 0.5–2 Hz drone control rate** |
| `image_tokens` | Server log (`-v`): max `n_tokens_batch` value | Proxy for image token count; probe Gemma tiling from first-run log |
| `peak_ram_mb` | `tegrastats` | Including mmproj; note tegrastats may under-count mmap'd weights |
| `mean_power_w` | `tegrastats` (active window) | During warm inference; compare to text-only baseline |
| `load_s` | Wall-clock to first `/health ok` | Server startup time; amortised across frames at deployment |
| **Capability** | `response.choices[0].message.content` | Model's JSON output; score: correct / partial / incorrect grounding |

---

## 10. Capability evaluation protocol

The timing run's model output itself serves as the capability sample. No separate
capability pass is run. For each unit, from the warm pass:

1. Record the exact JSON output.
2. Score grounding: **correct** = identifies target vehicle class and colour; **partial** =
   identifies class but wrong/missing colour or describes background; **incorrect** = wrong
   object or hallucinated scene.
3. Run all three test images and record three scores.
4. Note any refusals, hallucinations, or structural errors (invalid JSON).

This is not a rigorous capability benchmark (N=3 images, no statistical power) — it is
a coarse threshold check: "good enough to ground the referent?" A follow-up capability
campaign would sample more images and adversarial cases.

---

## 11. Sub-probes

### §11.1 Resolution / tiling cost (RQ-V5)

**SmolVLM units (V1, V2): SKIPPED.** Confirmed resolution-agnostic — fixed 64 image tokens
at any input size (verified on V1 at 500×500, 1280×640, 2875×1500; see §4.4 and §12).

**Gemma units (V3, V4, V5):** the three test images have three distinct native resolutions
(768×432, 347×280, 480×270), providing a natural tiling probe without artificial rescaling.
For each Gemma unit, from the server log (`-v` output), record:
- `image_tokens` (max `n_tokens_batch` per request) for each image
- `prompt_ms` per image
- `per_frame_ms` per image

Compare across images to characterise tiling cost as a function of resolution.

### §11.2 Vision overhead vs text baseline (RQ-V2)
For V3/V4/V5 (Gemma models), compare directly against the existing text-only numbers:

| Model | Text tg128 (tok/s) | Text pp512 (tok/s) | Vision prompt_eval_tps | Vision per_frame_ms |
|---|---|---|---|---|
| Gemma-3-4B | 12.15 (G2) | 502 (G2) | (measured) | (measured) |
| Gemma-4-E2B | 20.44 (G3) | 701 (G3) | (measured) | (measured) |
| Gemma-4-E4B | 11.42 (G4) | 362 (G4) | (measured) | (measured) |

---

## 12. Decisions log

Record campaign-specific decisions here as they arise. Cross-cutting decisions go in root
`DECISIONS.md`.

### 2026-06-14 — Measurement instrument: llama-server, not llama-mtmd-cli

- **Decision:** Use `llama-server` + Python urllib client as the timing instrument.
- **Alternatives considered:** (a) `llama-mtmd-cli --perf -v` per-frame; (b) `llama-server`.
- **Reasoning:** `llama-mtmd-cli` cannot do multi-frame in one process (each `-p` call
  is a single shot; chat mode with `--image` flags doesn't emit per-turn timings cleanly).
  Two separate CLI processes each pay the CUDA graph compilation penalty (~180ms for
  SmolVLM-256M), so there is no way to get a warm-state measurement from the CLI.
  `llama-server` keeps the model loaded, and `cache_prompt: false` in the API request
  forces a full prefill (no cross-request KV reuse), correctly modeling the per-frame cost.
- **Tradeoff:** llama-server adds a small JSON serialization overhead (measured <10ms);
  acceptable. Requires `ffmpeg` on the Jetson for image decoding from base64 buffers
  (`sudo apt install -y ffmpeg` — done 2026-06-14).

### 2026-06-14 — timings.prompt_ms includes CLIP encode; no separate CLIP term

- **Decision:** Treat `timings.prompt_ms` (from `__verbose` in server response) as the
  combined CLIP-encode + LLM-prefill time. Do not add a separate CLIP encode term.
- **Reasoning:** Empirically verified: `prompt_ms + predicted_ms ≈ wall-clock` (≤10ms
  residual). The server starts the prompt timer before multimodal content is processed,
  so CLIP encoding is accounted for within `prompt_ms`. The CLI `llama_perf_context_print`
  is a different code path (excludes CLIP); the two sources cannot be mixed.

### 2026-06-14 — SmolVLM RQ-V5 sub-probe skipped (resolution-agnostic)

- **Decision:** Skip the resolution/tiling sub-probe (§11.1) for SmolVLM units.
- **Reasoning:** Smoke tested SmolVLM-256M Q8_0 at 500×500, 1280×640, and 2875×1500.
  All produced exactly 64 LM-side image tokens (`n_tokens_batch=64`) and nearly identical
  `prompt_ms` (~190ms). SmolVLM resizes to a fixed internal size — no tiling. The tiling
  sub-probe is relevant only for Gemma-3/4 models (pan-and-scan), whose behaviour at
  1280×720 is unverified and must be probed on first run.

---

## 13. Results

*(to be filled in post-run)*

### Summary table

| Unit | Model | Params | n_slices | img_tokens | CLIP encode ms | Prompt eval ms | Decode ms | **per_frame_ms** | **Hz** | Peak RAM MB | Mean W | Grounding |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M Q8_0 | 0.26B | — | — | — | — | — | — | — | — | — | — |
| V2 | SmolVLM-500M Q8_0 | 0.50B | — | — | — | — | — | — | — | — | — | — |
| V3 | Gemma-3-4B q4_0 | 4.0B | — | — | — | — | — | — | — | — | — | — |
| V4 | Gemma-4-E2B q4_0 QAT | 5.1B | — | — | — | — | — | — | — | — | — | — |
| V5 | Gemma-4-E4B q4_0 QAT | 8.0B | — | — | — | — | — | — | — | — | — | — |
