"""Level-1 real-video test of the anchor tier — the deployed VLM on genuine footage.

Runs the Phase-4 Qwen2-VL-2B Q8_0 grounding skill over a real aerial video, but ONLY
at the VLM's true on-Orin cadence (~1 anchor every ANCHOR_PERIOD_S ≈ 2.26 s, the T0/T4
measured period). Between anchors the last box is *held stale* and drawn on every played
frame, so the demo makes the cadence constraint visible: a fresh green box at each
anchor, then an orange held box the target visibly drifts away from until the next VLM
pass lands.

This is the honest "anchor on real video" — no tracker, no oracle, no permanence. The
20 Hz fast tier (which would hold the lock between anchors) is Level 2 (see
results/2026-06-25-system-demo/PLANNING-history.md); closed-loop following on
pre-recorded video is impossible (no actuation) and stays sim-only.

    source .venv-ft/bin/activate
    python -m grounding.deploy.video \
        --video clip.mp4 --caption "the white car near the building" \
        --out /tmp/anchor-on-video.gif

    python -m grounding.deploy.video --selfcheck   # offline: schedule math only

Output is an animated GIF (no live VLM needed to view). The model runs on the Orin via
`ssh jetson`, identical contract path to the eval (`GROUNDING_PROMPT` + `parse_bbox`).
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile

import cv2
from PIL import Image, ImageDraw, ImageFont

from grounding.contract import parse_bbox, COORD_SCALE
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.eval.backends import JetsonBackend

_REMOTE_MODELS = {"q8_0": "phase3-refdrone-1024-q8_0.gguf",
                  "f16": "phase3-refdrone-1024-f16.gguf"}
_REMOTE_MMPROJ = "mmproj-phase3-refdrone-1024-f16.gguf"
_TRAIN_MAX_SIDE = 1024
ANCHOR_PERIOD_S = 2.26  # measured on-Orin anchor period (T0/T4); the cadence we sample at

GREEN, ORANGE, CYAN, RED = (40, 190, 70), (240, 150, 40), (60, 180, 240), (230, 60, 60)


def _make_tracker():
    """Best per-frame visual tracker available. CSRT (contrib) >> MIL (base build).
    `.venv-ft` ships opencv-contrib-python so this picks CSRT; MIL is the fallback if
    only base opencv-python is present."""
    if hasattr(cv2, "TrackerCSRT_create"):
        return cv2.TrackerCSRT_create(), "CSRT"
    return cv2.TrackerMIL_create(), "MIL"


def _norm_to_xywh(box_norm, w, h):
    x1, y1, x2, y2 = (box_norm[0] / COORD_SCALE * w, box_norm[1] / COORD_SCALE * h,
                      box_norm[2] / COORD_SCALE * w, box_norm[3] / COORD_SCALE * h)
    return (float(x1), float(y1), float(max(1.0, x2 - x1)), float(max(1.0, y2 - y1)))


def _xywh_to_norm(xywh, w, h):
    x, y, bw, bh = xywh
    return [x / w * COORD_SCALE, y / h * COORD_SCALE,
            (x + bw) / w * COORD_SCALE, (y + bh) / h * COORD_SCALE]


def anchor_schedule(n_frames: int, fps: float, period_s: float, stride: int):
    """(played_indices, anchor_set): which frames to draw, and which trigger a VLM pass.

    Anchors land every `period_s` of *video time*; played frames are every `stride`-th
    frame (the GIF). Every anchor is forced into the played set so a fresh box is never
    skipped. Pure function — the one piece worth a self-check.
    """
    anchor_every = max(1, round(period_s * max(fps, 1e-6)))
    anchors = set(range(0, n_frames, anchor_every))
    played = sorted(set(range(0, n_frames, max(1, stride))) | anchors)
    return played, anchors


def _font(sz):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def _draw(frame_rgb, box_norm, caption, tag, col):
    """Draw the current box + a state label on one PIL frame."""
    img = Image.fromarray(frame_rgb)
    w, h = img.size
    d = ImageDraw.Draw(img)
    if box_norm is not None:
        x1, y1, x2, y2 = (box_norm[0] / COORD_SCALE * w, box_norm[1] / COORD_SCALE * h,
                          box_norm[2] / COORD_SCALE * w, box_norm[3] / COORD_SCALE * h)
        d.rectangle([x1, y1, x2, y2], outline=col, width=max(2, round(min(w, h) / 200)))
    d.text((6, 4), tag, fill=col, font=_font(16))
    d.text((6, h - 20), caption[:70], fill=(230, 230, 230), font=_font(13))
    return img


def _read_frames(path, fps_default=30.0):
    """BGR frame list + fps. Accepts a video file OR a directory of sorted jpg/png frames
    (VisDrone-VID is natively frame sequences — read them directly, no re-encode)."""
    if os.path.isdir(path):
        import glob
        files = sorted(glob.glob(os.path.join(path, "*.jpg"))
                       + glob.glob(os.path.join(path, "*.png")))
        if not files:
            raise RuntimeError(f"no .jpg/.png frames in directory: {path}")
        return [cv2.imread(f) for f in files], fps_default
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path} (headless opencv may lack an mp4 "
                           "decoder — pass a directory of extracted frames instead)")
    fps = cap.get(cv2.CAP_PROP_FPS) or fps_default
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    cap.release()
    return frames, fps


def render(video_path, caption, out_path, backend, stride=3, period_s=ANCHOR_PERIOD_S,
           track=False):
    """Anchor the VLM at the on-Orin cadence; between anchors either hold the box stale
    (Level 1) or, if `track`, let a fast visual tracker hold the lock (Level 2 — the real
    two-tier architecture: VLM seeds, tracker coasts, next VLM regrounds)."""
    frames_bgr, fps = _read_frames(video_path)
    n = len(frames_bgr)
    if n == 0:
        raise RuntimeError(f"no frames decoded from {video_path}")

    played, anchors = anchor_schedule(n, fps, period_s, stride)
    box = None
    last_anchor_t = 0.0
    tracker = tracker_name = None
    out_frames = []
    for fi in played:
        bgr = frames_bgr[fi]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = bgr.shape[:2]
        fresh = fi in anchors
        if fresh:
            tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            try:
                Image.fromarray(rgb).save(tf.name)
                tf.close()
                box = parse_bbox(backend.generate(tf.name, caption)) or box
            finally:
                os.unlink(tf.name)
            last_anchor_t = fi / fps
            print(f"  anchor @ frame {fi} (t={fi/fps:.2f}s) box={box}", flush=True)
            if track and box is not None:
                tracker, tracker_name = _make_tracker()
                tracker.init(bgr, tuple(map(int, _norm_to_xywh(box, w, h))))
            tag, col = f"ANCHOR — fresh VLM box ({tracker_name})" if track else "ANCHOR — fresh VLM box", GREEN
        elif track and tracker is not None:
            # ponytail: tracker updates on played (strided) frames only; feed every frame if drift shows.
            ok, xywh = tracker.update(bgr)
            if ok:
                box = _xywh_to_norm(xywh, w, h)
                tag, col = f"tracking ({tracker_name})  +{fi/fps - last_anchor_t:.1f}s since VLM", CYAN
            else:
                tag, col = f"LOST — awaiting re-anchor  +{fi/fps - last_anchor_t:.1f}s", RED
        else:
            tag = f"held stale +{fi/fps - last_anchor_t:.1f}s (no new VLM yet)"
            col = ORANGE
        out_frames.append(_draw(rgb, box, caption, tag, col))

    _save(out_frames, out_path, fps / max(1, stride))
    print(f"[video] {len(out_frames)} frames, {len(anchors)} anchors -> {out_path}", flush=True)
    return out_path


def _save(frames, out_path, out_fps):
    """.mp4 -> pipe raw RGB to ffmpeg (h264, full res, no 256-colour loss).
    Anything else -> animated GIF via PIL. mp4 is the quality path for committed clips."""
    if not out_path.lower().endswith(".mp4"):
        dur = round(1000 / max(out_fps, 1e-6))
        # disposal=2 (restore to background) clears each frame before the next; without
        # it PIL stores partial diffs and the moving box ghosts/smears across its trail.
        frames[0].save(out_path, save_all=True, append_images=frames[1:],
                       duration=dur, loop=0, optimize=False, disposal=2)
        return
    import subprocess
    w, h = frames[0].size
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", f"{out_fps:.4f}", "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         # even dims required by yuv420p; pad (no content loss) rather than crop
         "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-loglevel", "error", out_path],
        stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed writing {out_path}")


def _selfcheck():
    # 300 frames @ 30 fps = 10 s; 2.26 s period -> anchor every 68 frames -> 5 anchors.
    played, anchors = anchor_schedule(300, 30.0, 2.26, stride=3)
    assert sorted(anchors) == [0, 68, 136, 204, 272], sorted(anchors)
    assert anchors <= set(played), "every anchor must be played"
    assert all(p % 3 == 0 or p in anchors for p in played)
    # fps fallback / tiny clip must not divide-by-zero or drop the first anchor
    p2, a2 = anchor_schedule(1, 0.0, 2.26, stride=3)
    assert a2 == {0} and p2 == [0], (p2, a2)
    # coord round-trip: norm -> pixel xywh -> norm is identity
    rt = _xywh_to_norm(_norm_to_xywh([100, 200, 300, 500], 640, 480), 640, 480)
    assert max(abs(a - b) for a, b in zip(rt, [100, 200, 300, 500])) < 1e-6, rt
    name = _make_tracker()[1]
    assert name in ("CSRT", "MIL"), name
    # mp4 writer: 3 odd-sized frames must pad+encode to a non-empty file
    mf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    mf.close()
    try:
        _save([Image.new("RGB", (65, 49), (i, 0, 0)) for i in (10, 120, 230)], mf.name, 10.0)
        assert os.path.getsize(mf.name) > 0, "empty mp4"
    finally:
        os.unlink(mf.name)
    print(f"  selfcheck PASS  anchors {sorted(anchors)}  tracker={name}  mp4-writer ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", help="path to a real aerial video (mp4/avi/...)")
    ap.add_argument("--caption", help="referring phrase to ground")
    ap.add_argument("--out", default="/tmp/anchor-on-video.gif")
    ap.add_argument("--stride", type=int, default=3, help="play every Nth frame into the GIF")
    ap.add_argument("--track", action="store_true",
                    help="Level 2: seed a fast tracker from each VLM anchor and coast between "
                         "anchors (vs the default Level-1 stale-hold)")
    ap.add_argument("--period", type=float, default=ANCHOR_PERIOD_S,
                    help="anchor cadence in seconds (default = measured on-Orin period)")
    ap.add_argument("--quant", choices=list(_REMOTE_MODELS), default="q8_0")
    ap.add_argument("--remote-dir", default=_DEFAULT_REMOTE_DIR)
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--max-side", type=int, default=_TRAIN_MAX_SIDE)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args(argv)

    if args.selfcheck:
        print("video anchor-schedule self-check:")
        _selfcheck()
        return 0
    if not args.video or not args.caption:
        ap.error("need --video and --caption (or --selfcheck)")

    remote_model = f"{args.remote_dir}/{_REMOTE_MODELS[args.quant]}"
    remote_mmproj = f"{args.remote_dir}/{_REMOTE_MMPROJ}"
    print(f"[video] booting Jetson {args.quant} server...", flush=True)
    with JetsonBackend(remote_model, remote_mmproj,
                       ssh_host=args.ssh_host, max_side=args.max_side) as be:
        render(args.video, args.caption, args.out, be, args.stride, args.period, args.track)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
