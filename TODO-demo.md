# Thesis demo (professor) — runbook

**Two separate demos**, both showing the on-Orin Part III system. Built 2026-06-25.

## Demo 1 — interactive grounding (live, on the Orin)
`grounding/deploy/gui.py` — browser GUI, inference runs on the deployed Qwen2-VL-2B
Q8_0 over `ssh jetson`. Now has **one-click RefDrone presets** (no file-hunting mid-demo):
`motorbike-small`, `bus-midlane`, `bus-intersection`, `pedestrians-red`, `car-large`
(varied target sizes; real RefDrone val frames + their referring captions).

```bash
source .venv-ft/bin/activate
python -m grounding.deploy.gui          # open http://127.0.0.1:8000
```
Click a preset → image + caption load → **Run** → predicted box drawn live. Upload your
own image too. CLI single-shot equivalent: `python -m grounding.deploy.demo --preset bus-midlane`.

Record: screen-capture the browser while driving presets (first query pays model-load;
the rest are fast). Captions aren't pre-scored — the box you see is the live model output.

## Demo 2 — object permanence (memoryless vs re-ID)
`experiments/sitl/permanence_viz.py` — deterministic side-by-side animation from the T1
`crossing_occlusion` clip. Memoryless ByteTrack steals the lock onto the decoy (red
"WRONG"); appearance re-ID refuses ("SEARCHING…") and re-locks the true target (green).

```bash
.venv-ft/bin/python experiments/sitl/permanence_viz.py            # → results/2026-06-24-t2-permanence/permanence.gif
.venv-ft/bin/python experiments/sitl/permanence_viz.py --selfcheck  # asserts it tells the true T2 story
```
Output is an animated GIF (PIL only, no ffmpeg). mp4: `ffmpeg -i permanence.gif permanence.mp4`.
Deterministic → identical on dev box or Orin (Orin would need PIL installed; not required).
Headline it reproduces: memoryless purity 0.72 / 1 ID-switch vs re-ID purity 1.00 / 0.

## On-Orin constraints (unchanged)
No camera, no on-device SITL; Part III clips are kinematic (labels only). Demo 1 is the
genuine on-Orin VLM; Demo 2 is a deterministic sim artifact.
