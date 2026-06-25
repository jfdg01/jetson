# Whole-system interactive demo (Part III)

**Built:** 2026-06-25. **Branch:** `v3/object-permanence`. **Rebuilt 2026-06-25T13:00**
(see `DECISIONS.md`): the original static 4-tab page was retired in favour of a **live
2-tab `grounding/deploy/gui.py`**.

```bash
source .venv-ft/bin/activate
python -m grounding.deploy.gui            # boots the Orin server, serves http://127.0.0.1:8000
```

## The three tabs
1. **Manual grounding** — the VLM in isolation. Pick a RefDrone preset (varied target
   sizes) or upload an image, type a phrase → one box, **live on the deployed Qwen2-VL-2B
   Q8_0** on the Orin (`ssh jetson`). The single-frame anchor tier, by hand.
2. **Tracking on video** — the **two-tier architecture** on real aerial footage: a fresh
   VLM anchor (~every 2.26 s, the measured on-Orin cadence) seeds a fast tracker that
   **coasts** between anchors; the next anchor regrounds. Three pre-rendered clips
   (`clips/*.mp4`), each with **real Orin VLM passes** on VisDrone-VID.

   | clip | caption | seq |
   |---|---|---|
   | `clips/black-suv.mp4` | the black SUV in the middle of the road | `uav0000182_00000_v` |
   | `clips/green-bus.mp4` | the green bus | `uav0000305_00000_v` |
   | `clips/yellow-taxi.mp4` | the yellow taxi | `uav0000339_00001_v` |

3. **Live tracking (your video)** — same pipeline, *your* clip: upload a short aerial
   video + a phrase → it runs the real two-tier pass on the Orin and returns an
   annotated **mp4** (full-res h264, one box/frame). Slow (~15-30 s/clip — a few ssh
   VLM passes), single-user.

   Box colours (tabs 2-3): **green** = fresh VLM box · **cyan** = tracker coasting ·
   **orange/red** = stale / lost. Tracker is **CSRT** (`.venv-ft` ships
   `opencv-contrib-python`); `video.py:_make_tracker()` falls back to MIL if only base
   opencv is present.

## The honest seam (do NOT fake it)
The real VLM anchor runs only on real aerial frames (Orin). Tab 2's clips ARE real on
both tiers — real Orin VLM anchors + a real visual tracker coasting on real VisDrone
frames. What does *not* exist on real video is **closed-loop following** (Level 3): a
pre-recorded clip has no actuation to close the loop on — it stays sim-only (the T3
result, in `results/2026-06-24-t3-closed-loop/`). Permanence A/B (T2) and closed-loop
(T3) keep their own canonical GIFs in their own result folders; they are no longer
embedded in this viewer.

## Regenerating the clips
`--out *.mp4` renders the annotated frames **straight to h264 at full source resolution**
(`video.py:_save()` pipes raw RGB to ffmpeg) — no GIF intermediate, so no 256-colour
quantisation. (Pass `--out *.gif` for the old animated-GIF path; the live-upload tab uses
that for an inline preview.)
```bash
source .venv-ft/bin/activate          # needs the Orin reachable (ssh jetson), VisDrone frames on disk
for s in "uav0000182_00000_v:the black SUV in the middle of the road:black-suv" \
         "uav0000305_00000_v:the green bus:green-bus" \
         "uav0000339_00001_v:the yellow taxi:yellow-taxi"; do
  IFS=: read seq cap name <<<"$s"
  python -m grounding.deploy.video \
    --video data/VisDrone2019-VID/VisDrone2019-VID/images/val/$seq \
    --caption "$cap" --track --out results/2026-06-25-system-demo/clips/$name.mp4
done
python -m grounding.deploy.video --selfcheck   # offline schedule + coord-roundtrip + tracker + mp4-writer check
```

VisDrone frames are fetched via `remotezip` HTTP range-requests from the HF re-host
`lanlanlan23/VisDrone2019` (`VisDrone2019-VID.zip`); they are gitignored-scale (not
committed). The clips are ~3–5 MB mp4 each (full-res h264, vs a ~40 MB GIF), small enough
to commit.
