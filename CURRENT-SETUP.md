I want to update the VLM perfomance.

# The flow

1 — Frame in (video.py:170 _read_frames)
Video file or a dir of jpg/png frames. Kept at full native resolution on the host — the ROI crop needs original pixels; the full-frame path will downscale later.

2 — Anchor tier: build the image fed to the VLM (video.py:225 _anchor_box)
Two sub-modes depending on lock state:

- Cold acquire / post-loss re-acquire (no prior, or lost): the whole frame goes to the backend, which long-edge-resizes to max_side=1024, BILINEAR, downscale-only (backends.py:115 _resize_keep_aspect).
- ROI re-anchor (steady state, lock held): crop a square window M=4.0 × the last box, floored at 384 px (roi_window, video.py:68-75), then LANCZOS resize long-edge capped at 1024, not upscaled (crop_resize(..., upscale=False), roi.py:100). Prediction is mapped back to full-frame coords with map_to_full.

3 — Send to VLM (backends.py:24 _llama_server_chat)
Image → lossless PNG → base64 → POST /v1/chat/completions over an ssh tunnel to llama-server on the Orin (CUDA, -ngl 99, Q8_0, single slot, prompt cache off). Prompt is the verbatim contract (contract.py:48):

▎ Locate "{target}". Return the bounding box as four space-separated integers x1 y1 x2 y2, normalized from 0 to 100.
▎ Greedy (temperature=0), max_tokens=64, cache_prompt=False.

4 — What comes back / parse (contract.parse_bbox)
Raw text → 4 ints in 0–100 (COORD_SCALE=100) in crop coords → mapped to full-frame normalized coords. Parse-fail keeps the prior box (video.py:248).

5 — Fast tier: tracker coasts (video.py:352)
Between anchors a CSRT tracker (seeded from each anchor box, _make_tracker) holds the lock at frame rate. A reported loss latches lost=True, forcing the next anchor back to full-frame acquire.

6 — (SITL only) lock policy + fly (reid_policy.py, cascade_pid.py, offboard.py)
Re-ID appearance gate rejects distractors → box-center error → cascade PID → body-frame velocity+yaw_rate → NED rotation → SET_POSITION_TARGET_LOCAL_NED at 20 Hz. But fed by the oracle, not the VLM.

Where the lowest-hanging fruit is

The instrumented cost split already exists — _print_anchor_stats / generate_stats give you prefill / decode / transfer per call (backends.py:80-93). Use it; don't guess. Ranked by likely payoff:

1. The acquire wall, and a constant that lies. Vision tokens scale with fed area, and acquire feeds a full 1024 frame (~the slow tier). But ACQUIRE_PERIOD_S = 2.0 at video.py:61 contradicts its own docstring and every comment (which say ~4.8 s) — and the self-check passes 4.8 explicitly (video.py:443). So the demo default currently treats acquire == re-anchor. Either the constant is stale or the comments are. Resolve that before optimizing anything timed against it.
2. transfer_ms: PNG-over-ssh every frame. You re-encode lossless PNG + base64 + push it through the tunnel on every anchor (_llama_server_chat). transfer_ms = wall − prefill − decode is already measured — if it's non-trivial, this is free latency: the model runs locally on the Orin anyway, so the ssh tunnel is pure overhead. Running the loop on-device (no tunnel) or at least JPEG-vs-PNG is the cheap test.
3. cache_prompt=False (backends.py:70). Re-prefills the chat-template/system tokens every call. The image dominates so the win is small, but it's a one-flag experiment.
4. The real gap (not low-hanging, but the actual Part IV blocker): oracle → VLM in the loop. T3/T4 passed because perception was perfect and instant. The VLM is ~2–5 s/anchor and wrong sometimes. The closed loop has never seen VLM latency or parse-fails as control inputs. That's where "doesn't hold up end-to-end" lives — and no amount of anchor-tier tuning fixes a loop that's never been tested with the real detector's error/latency profile.
