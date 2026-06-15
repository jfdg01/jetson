# Toy NL-Command Demo System — 2026-06-15

**Status:** Complete (integration mechanics PASS; zero-shot grounding fails on aerial imagery as expected)

**Script:** `experiments/demo_nlcommand.py`

---

## What this is

A runnable end-to-end demo of the thesis concept: a natural language command +
a drone frame → structured drone action, with the VLM running on the Jetson
Orin Nano 8 GB. Built as a toy to validate the pipeline mechanics and to
establish what zero-shot SmolVLM-500M can and cannot do before Stage-2
fine-tuning.

---

## Pipeline

```
User NL command ──parse──► (verb, referent)
                                │
                    ┌───────────┴──────────────┐
               verb=TURN              verb=FOLLOW/ZOOM
                    │                           │
            yaw setpoint         image + referent → llama-server
            (no VLM call)             SmolVLM-500M Q8_0
                                        Jetson Orin Nano
                                           ~500–2000 ms
                                              │
                                       JSON bbox (or null)
                                              │
                                   FOLLOW → velocity setpoint
                                   ZOOM   → crop directive
```

**Command types supported:**

| Verb | Example | VLM used? | Output |
|---|---|---|---|
| FOLLOW / TRACK | "follow that white car" | Yes | `{vx_ms, vy_ms, yaw_rate_dps}` |
| ZOOM / FOCUS | "zoom on that red bird" | Yes | `{action: CROP_TO_BBOX, crop_px: {…}}` |
| TURN / ROTATE | "turn around the right corner" | **No** | `{yaw_rate_dps}` |

---

## Usage

```bash
source .venv/bin/activate

# TURN command — instant, no VLM
python experiments/demo_nlcommand.py \
    --image path/to/frame.jpg \
    --command "turn around the right corner"

# FOLLOW/ZOOM — starts VLM on Jetson, grounding call, then tears down
python experiments/demo_nlcommand.py \
    --image path/to/frame.jpg \
    --command "follow that white car" \
    --start-server

# Keep server running for multi-command testing (don't tear down between calls)
python experiments/demo_nlcommand.py \
    --image path/to/frame.jpg \
    --command "follow that white car" \
    --start-server --keep-server
# … then subsequent commands without --start-server (uses existing server + port-forward)
python experiments/demo_nlcommand.py \
    --image path/to/frame.jpg \
    --command "zoom on the red car"

# Save annotated image (requires Pillow: pip install Pillow)
python experiments/demo_nlcommand.py \
    --image path/to/frame.jpg \
    --command "follow that white car" \
    --out annotated.jpg
```

---

## Results — 2026-06-15 (Jetson Orin Nano 8 GB, 15 W, llama.cpp `57fe1f0`)

### TURN command (no VLM)

Works unconditionally — heuristic yaw-rate lookup, <1 ms, no Jetson call:

```
"turn around the right corner"  → yaw_rate_dps = 40.0  (parse_ok=true)
"turn left"                     → yaw_rate_dps = -20.0 (parse_ok=true)
```

### FOLLOW/ZOOM on VisDrone aerial frames (zero-shot SmolVLM-500M Q8_0)

| Command | Image | VLM latency | parse_ok | Notes |
|---|---|---|---|---|
| "follow that white car" | `0000001_05499_d_0000010.jpg` (1920×1080) | 534 ms | **false** | Model echoed template: `{"x1":.., "y1":.., "x2":.., "y2":..}` — no numbers |
| "zoom on that red bird"  | `0000026_00000_d_0000024.jpg` (1360×765)  | 2046 ms | **false** | Model returned whole-image bbox (degenerate, filtered) |

**Honest assessment:** Zero-shot SmolVLM-500M cannot ground specific objects in
nadir/aerial drone frames. This is consistent with Phase A results (0 % IoU@0.25
on VisDrone/RefDrone, 4 % parse). The pipeline *mechanics* work — the server
starts, receives the image, returns a response — but the grounding signal is
absent for aerial imagery zero-shot.

> **This is the expected and pre-registered outcome.** TURN commands provide the
> thesis demo with a reliably working action. FOLLOW/ZOOM demonstrate the VLM
> path end-to-end while being honest that zero-shot grounding fails on aerial
> imagery — the exact motivation for Stage-2 fine-tuning.

---

## Decisions

### 2026-06-15T12:00 — Toy demo scope: pipeline mechanics, honest grounding result

- **Decision:** Build the toy system as a thin orchestration layer (`demo_nlcommand.py`)
  over existing infrastructure (llama-server on Jetson, `run_grounding_probe.py` client
  helpers), not as a new campaign with full tegrastats/RESULTS.md measurement apparatus.
- **Alternatives considered:** (a) Run as a full measurement campaign with N-frame sweep,
  tegrastats, device rows — rejected because the toy's goal is *demonstration* and
  *pipeline validation*, not a new benchmark row. (b) Use a different image source
  (street-level, non-aerial) where zero-shot VLM would likely ground successfully —
  rejected because the thesis target is aerial drone imagery; showing success on
  non-aerial images would be misleading.
- **Reasoning:** The toy system's role is to validate the end-to-end pipeline mechanics
  and to show honestly what zero-shot SmolVLM does on the target input domain. Both goals
  are met: TURN commands work perfectly; FOLLOW/ZOOM calls reach the Jetson, get a
  response, and report grounding failure transparently. The failure is a documented
  finding that motivates Stage 2, not a bug.
- **Tradeoff / cost accepted:** The demo is not visually impressive for FOLLOW/ZOOM on
  aerial imagery until Stage-2 fine-tuning is done. The honest path.
- **Revisit when:** Stage-2 fine-tuned SmolVLM-500M is ready; replace the model GGUF path
  and re-run the demo — same commands, same pipeline, grounding quality improves.
