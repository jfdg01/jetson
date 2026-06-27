# VLM Feasibility — Jetson Orin Nano 8 GB

**Date:** 2026-06-14 · **Status:** COMPLETE (frozen)  
**Builds on:** [model-capability-sweep](../2026-06-13-model-capability-sweep.md) · [gemma-family-sweep](../2026-06-14-gemma-family-sweep/)

**Question:** Can a VLM running entirely on the Orin Nano meet the latency and grounding requirements of a drone command loop (0.5–2 Hz)?  
**Decision fork:** end-to-end VLM (camera → VLM → command) vs. decomposed (YOLO grounding + LLM intent). Criterion: empirical latency vs. control rate.

---

## Methodology

**Instrument:** `llama-server` + Python urllib client. `llama-bench` has no image support; `llama-mtmd-cli` can't do multi-frame warm measurement (each call pays CUDA graph compilation ~180 ms). Server keeps model loaded; `cache_prompt: false` forces full prefill per frame — correct model for drone use.

**Per-frame formula:** `per_frame_ms = timings.prompt_ms + timings.predicted_ms`  
`prompt_ms` **includes CLIP encode** (verified: residual vs. wall-clock ≤10 ms). Do NOT add a separate CLIP term.

**Cold vs. warm:** first frame includes ~180 ms CUDA graph compilation. Report **warm** (after throwaway warmup request) as headline. Cold reported as footnote.

**SmolVLM resolution:** fixed 64 image tokens regardless of input size (verified at 500×500, 1280×640, 2875×1500) — resolution-agnostic, no tiling. Gemma-3/4 use pan-and-scan tiling; token count probed from server log.

**Controlled variables:**

| Variable | Value |
|---|---|
| Runtime | llama.cpp `57fe1f0`, CUDA `sm_87` |
| Power mode | 15 W locked (`nvpmodel -m 0` + `jetson_clocks`) |
| GPU offload | `-ngl 99` (full, text + mmproj) |
| Prompt | `"You are a drone flight controller. What object should the drone follow in this image? Reply in JSON: {"action": "follow", "target": "<object description>"}"` |
| Output length | `max_tokens=50` (V1–V3), `--reasoning off` for V4–V5 |
| Passes | N=5; warm (after throwaway warmup) |

**Test images** (committed to `test-images/`):

| ID | File | Resolution |
|---|---|---|
| img-1 | `highway-with-firetruck.jpg` | 768×432 |
| img-2 | `multiple-collision.jpg` | 347×280 |
| img-3 | `white-van-crash.jpeg` | 480×270 |

No aerial POV available — limits grounding realism. Three distinct resolutions serve as natural Gemma tiling probe.

---

## Models

| Unit | Model | Params | Vision encoder | Text weights |
|---|---|---|---|---|
| V1 | SmolVLM-256M-Instruct Q8_0 | 0.26B | SigLIP-400M (64 tok) | downloaded |
| V2 | SmolVLM-500M-Instruct Q8_0 | 0.50B | SigLIP-400M (64 tok) | downloaded |
| V3 | Gemma-3-4B-it q4_0 | 4.0B | SigLIP (256 tok) | on device (G2) |
| V4 | Gemma-4-E2B-it q4_0 QAT | 5.1B | SigLIP Matryoshka | on device (G3) |
| V5 | Gemma-4-E4B-it q4_0 QAT | 8.0B | SigLIP Matryoshka | on device (G4) |

---

## Results

### Summary

| Unit | Model | img_tokens | prompt_ms | decode_ms | **per_frame_ms** | **Hz** | Peak RAM MB | Mean W | Grounding |
|---|---|---|---|---|---|---|---|---|---|
| V1 | SmolVLM-256M Q8_0 | 64 | 195±9 | 108±64 | **304±65** | **3.29** | 1777 | 6.6 | poor — incoherent JSON, wrong targets |
| V2 | SmolVLM-500M Q8_0 | 64 | 222±5 | 104±149 | **338±148** | **2.96** | 2241 | 7.2 | partial — sometimes correct object class |
| V3 | Gemma-3-4B q4_0 | 256 | 7390±13 | 2190±106 | **9576±98** | **0.10** | 6414 ⚠swap | 9.7 | good — correct class+colour, valid JSON |
| V4 | Gemma-4-E2B q4_0† | 144 | 799±214 | 1236±539 | **2035±611** | **0.49** | 4616 | 8.2 | partial — correct class, inconsistent colour |
| V5 | Gemma-4-E4B q4_0† | 144 | 1051±289 | 1817±394 | **2963±576** | **0.34** | 6444 ⚠swap | 8.8 | partial — correct class, inconsistent targets |

*† re-run with `--reasoning off` — see negative result below. N=5 warm frames, 15 W locked.*

---

### V1 — SmolVLM-256M Q8_0

**Run:** 2026-06-14T19:33 UTC  
SHA256 text: `2a31195d…` · mmproj: `0802360a…` · Load: 3 s

| prompt_n | predicted_n | idle W | peak W | peak °C |
|---|---|---|---|---|
| 113 | 16 | 5.18 | 9.43 | 53.8 |

**Capability (N=5):**
- [img-1] "The drone should follow the topmost vehicle, the one that has the white object." ❌
- [img-2] `"follow"` (no target) ❌
- [img-3] "The drone should follow the bus as it approaches the intersection." ❌ (wrong vehicle)
- [img-1] "follow the structure of the traffic lane" ❌
- [img-2] returned template JSON unchanged ❌

---

### V2 — SmolVLM-500M Q8_0

**Run:** 2026-06-14T19:34 UTC  
SHA256 text: `9d4612de…` · mmproj: `4b2fca92…` · Load: 3 s

| prompt_n | predicted_n | idle W | peak W | peak °C |
|---|---|---|---|---|
| 113 | 9 | 5.19 | 10.54 | 54.3 |

**Capability (N=5):**
- [img-1] `"truck", "yellow car"` ❌ (not JSON)
- [img-2] `{"action": "follow", "target": "a black car in traffic"}` ✓ class
- [img-3] `"0"` ❌
- [img-1] `{"type": "vehicle", "image": "yellow truck"}` ✓ class
- [img-2] `"people"` ❌

---

### V3 — Gemma-3-4B q4_0

**Run:** 2026-06-14T19:34 UTC  
SHA256 text: `76aed0a8…` · mmproj: `8c0fb064…` · Load: 12 s

| prompt_n | predicted_n | idle W | peak W | peak °C |
|---|---|---|---|---|
| 303 | 27 | 5.25 | 12.38 | 59.1 |

**Capability (N=5):** all valid JSON, correct class+colour
- [img-1] `{"action": "follow", "target": "red fire truck"}` ✓✓
- [img-2] `{"action": "follow", "target": "the white police car"}` ✓✓
- [img-3] `{"action": "follow", "target": "van"}` ✓ class
- [img-1] `{"action": "follow", "target": "the red fire truck"}` ✓✓
- [img-2] `{"action": "follow", "target": "white police car"}` ✓✓

**Note:** 6414 MB peak (swap hit). At 0.10 Hz — far below usable control rate even with decimation.

---

### V4 — Gemma-4-E2B q4_0 QAT

#### Initial run (thinking-on) — **INVALID**

**Run:** 2026-06-14T19:36 UTC · `max_tokens=50`  
**Finding:** Gemma-4 is a thinking model. All 50 tokens consumed by `reasoning_content`; `content` empty — no JSON produced. Latency (3286±220 ms, 0.30 Hz) measures "thinking until token budget exhausted", not a VLM command cycle. img_tokens=144, RAM=4616 MB, no swap.

**Decision — re-run with `--reasoning off`:** For drone command generation, latency is binding. Thinking mode adds hundreds of ms per frame; a controller cannot wait. `--reasoning off` gives correct deployment latency. Thinking-on numbers retained as negative result.

#### Re-run (`--reasoning off`) — **CANONICAL**

**Run:** 2026-06-14T19:42 UTC  
SHA256 text: `3646b4c1…` · mmproj: `8a82e0fd…` · Load: 12 s

| prompt_n | predicted_n | idle W | peak W | peak °C |
|---|---|---|---|---|
| 106 | 26 | 5.21 | 11.59 | 58.3 |

**Capability (N=5):**
- [img-1] target: "The drone should follow the line of the road/pavement" ❌
- [img-2] `{"action": "follow", "target": "the white car in the foreground"}` ✓ class
- [img-3] `{"action": "follow", "target": "the road"}` ❌
- [img-1] `{"action": "follow", "target": "the airplane"}` ❌ (hallucination)
- [img-2] `{"action": "follow", "target": "The white car in the middle lane"}` ✓✓

---

### V5 — Gemma-4-E4B q4_0 QAT

#### Initial run (thinking-on) — **INVALID**

**Run:** 2026-06-14T19:38 UTC · Same issue as V4. Latency: 5359±274 ms, 0.19 Hz. img_tokens=144, RAM=6444 MB, no swap.

#### Re-run (`--reasoning off`) — **CANONICAL**

**Run:** 2026-06-14T19:43 UTC  
SHA256 text: `e8b6a059…` · mmproj: `51d4b7fd…` · Load: 18 s

| prompt_n | predicted_n | idle W | peak W | peak °C |
|---|---|---|---|---|
| 106 | 22 | 5.17 | 12.34 | 59.6 |

**Capability (N=5):**
- [img-1] `{"action": "follow", "target": "The red and white bus on the road"}` ✓ class
- [img-2] `{"action": "follow", "target": "car"}` ✓ class
- [img-3] `{"action": "follow", "target": "the red and white vehicle in the middle of the street"}` ✓ class (colour wrong)
- [img-1] `{"action": "follow", "target": "the red and white vehicle in the center-right of the image"}` ✓ class
- [img-2] `{"action": "follow", "target": "the vehicles on the road"}` ❌ (generic)

**Note:** 6444 MB peak (swap hit). Loaded without OOM (85% of 7607 MB budget). Stretch goal confirmed feasible but swapping.

---

## Conclusions

- **SmolVLM (V1/V2)** meets the latency target (3 Hz) but grounding quality is too poor for reliable drone commands. 64 image tokens is insufficient — can't resolve colour or specific vehicle type.
- **Gemma-3-4B (V3)** has reliable grounding (correct class+colour) but 0.10 Hz is unusable. 256 image tokens + 4B prefill at Q4 too slow.
- **Gemma-4-E2B (V4)** is the best trade-off: 0.49 Hz (~0.5 Hz target, just at boundary), 4616 MB RAM, partial grounding. Thinking must be disabled.
- **Gemma-4-E4B (V5)** is slower (0.34 Hz) and swaps — worse than V4 in every dimension.
- **Architecture decision:** end-to-end VLM is borderline only with V4 (reasoning off). The 0.49 Hz result motivates the Part II decomposed approach (fast grounding model + lightweight LLM) or fine-tuning a smaller VLM for structured output.
