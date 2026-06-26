"""Level-1 real-video test of the anchor tier — the deployed VLM on genuine footage.

Runs the Phase-4 Qwen2-VL-2B Q8_0 grounding skill over a real aerial video, but ONLY
at the VLM's true on-Orin cadence — and that cadence is *two-tier*: the one-time
full-frame acquire is ~ACQUIRE_PERIOD_S (≈ 4.8 s wall), each subsequent ROI re-anchor is
~ANCHOR_PERIOD_S (≈ 2.0 s, the cheaper prefill lever). The schedule spaces the first
anchor by the slow acquire gap and the rest by the fast re-anchor gap. Between anchors the
last box is *held stale* and drawn on every played frame, so the demo makes the cadence
constraint visible: a fresh green box at each anchor, then an orange held box the target
visibly drifts away from until the next VLM pass lands.

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
import time

import cv2
from PIL import Image, ImageDraw, ImageFont

from grounding.contract import COORD_SCALE, parse_bbox
from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
from grounding.eval.backends import JetsonBackend
from grounding.roi import crop_resize, map_to_full, roi_window

# terse iter-2b anchor (2026-06-26): bare 0–100 ints, Orin Q8_0 63.1% (> JSON 62.6%),
# decode −45%. Must match the terse GROUNDING_PROMPT in contract.py — see
# results/2026-06-25-terse-output-retrain/.
_REMOTE_MODELS = {
    "q8_0": "phase3-terse100eos-1024-q8_0.gguf",
    "f16": "phase3-terse100eos-1024-f16.gguf",
}
_REMOTE_MMPROJ = "mmproj-phase3-terse100eos-1024-f16.gguf"
_TRAIN_MAX_SIDE = 1024
# Re-measured on-Orin 2026-06-26 (terse Q8_0, 15 W, incl. ssh transfer — the wall the demo
# blocks on per anchor; see results/2026-06-26-roi-demo-tab/measure_cadence.py). Two-tier:
# the steady-state cadence is the ROI re-anchor (~2.0 s); the one-time cold acquire / post-loss
# re-acquire is full-frame and ~2.4× slower (~4.8 s). The schedule spaces the first anchor by
# the slow acquire gap, the rest by the fast re-anchor gap. The old T0/T4 2.26 s was JSON @512
# server-side — it under-reported the GUI's real 1024 full-frame acquire by ~2×.
ANCHOR_PERIOD_S = 2.0  # ROI re-anchor wall — the repeating steady-state cadence
ACQUIRE_PERIOD_S = (
    2.0  # full-frame acquire wall — first anchor (and post-loss re-acquire)
)

# ROI re-anchor (results/2026-06-25-roi-crop-anchor): while the lock holds, re-anchor on a
# tight crop around the last box, upscaled to OUT_RES — 2.7× cheaper prefill AND +22.6 pp
# (super-resolution on the target). Cold acquire / re-acquire after a loss stays full-frame.
ROI_MARGIN = 4.0
ROI_OUT_RES = 1024

GREEN, ORANGE, CYAN, RED = (40, 190, 70), (240, 150, 40), (60, 180, 240), (230, 60, 60)


def _make_tracker():
    """Best per-frame visual tracker available. CSRT (contrib) >> MIL (base build).
    `.venv-ft` ships opencv-contrib-python so this picks CSRT; MIL is the fallback if
    only base opencv-python is present."""
    if hasattr(cv2, "TrackerCSRT_create"):
        return cv2.TrackerCSRT_create(), "CSRT"
    return cv2.TrackerMIL_create(), "MIL"


def _norm_to_xywh(box_norm, w, h):
    """Normalized 0–COORD_SCALE box → pixel (x,y,bw,bh), clamped inside the frame with a
    ≥1px size. CSRT resizes the init patch, so an empty / out-of-frame ROI makes OpenCV
    assert (`!ssize.empty()`); the model can emit a box on the border, so clamp here. Also
    orders the corners in case the box comes back reversed."""
    xs = sorted((box_norm[0], box_norm[2]))
    ys = sorted((box_norm[1], box_norm[3]))
    x1 = min(max(xs[0] / COORD_SCALE * w, 0.0), w - 1.0)
    y1 = min(max(ys[0] / COORD_SCALE * h, 0.0), h - 1.0)
    x2 = min(max(xs[1] / COORD_SCALE * w, x1 + 1.0), float(w))
    y2 = min(max(ys[1] / COORD_SCALE * h, y1 + 1.0), float(h))
    return (float(x1), float(y1), float(x2 - x1), float(y2 - y1))


def _xywh_to_norm(xywh, w, h):
    x, y, bw, bh = xywh
    return [
        x / w * COORD_SCALE,
        y / h * COORD_SCALE,
        (x + bw) / w * COORD_SCALE,
        (y + bh) / h * COORD_SCALE,
    ]


def anchor_schedule(
    n_frames: int, fps: float, acquire_s: float, reanchor_s: float, stride: int
):
    """(played_indices, anchor_set): which frames to draw, and which trigger a VLM pass.

    Two-tier cadence: the FIRST anchor is a full-frame acquire and opens an `acquire_s` gap
    (the slow ~4.8 s wall); every later anchor is a ROI re-anchor and opens the shorter
    `reanchor_s` gap (~2.0 s). Anchors land in *video time*; played frames are every
    `stride`-th, with every anchor forced played so a fresh box is never skipped. Pure
    function — the one piece worth a self-check.
    ponytail: assumes the lock holds — a mid-clip loss makes its re-acquire full-frame but
    keeps the reanchor_s gap; re-timing a dynamic loss isn't worth it for a demo GIF.
    """
    dur = n_frames / max(fps, 1e-6)
    anchors, t, first, last = [], 0.0, True, -1
    while t < dur:
        fi = round(t * fps)
        if fi >= n_frames:
            break
        if (
            fi <= last
        ):  # fps≈0 / sub-frame period: schedule can't advance, clip is one frame
            break
        anchors.append(fi)
        last = fi
        t = fi / max(fps, 1e-6) + (acquire_s if first else reanchor_s)
        first = False
    anchors = set(anchors or [0])  # always at least the first anchor
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
        x1, y1, x2, y2 = (
            box_norm[0] / COORD_SCALE * w,
            box_norm[1] / COORD_SCALE * h,
            box_norm[2] / COORD_SCALE * w,
            box_norm[3] / COORD_SCALE * h,
        )
        d.rectangle([x1, y1, x2, y2], outline=col, width=max(2, round(min(w, h) / 200)))
    d.text((6, 4), tag, fill=col, font=_font(16))
    d.text((6, h - 20), caption[:70], fill=(230, 230, 230), font=_font(13))
    return img


def _read_frames(path, fps_default=30.0, max_seconds=None):
    """BGR frame list + fps. Accepts a video file OR a directory of sorted jpg/png frames
    (VisDrone-VID is natively frame sequences — read them directly, no re-encode). Frames
    are kept at FULL resolution — the ROI re-anchor crops a tight window and upscales it, so
    it needs the original pixels (the full-frame anchor doesn't: the backend caps it to
    ≤1024). `max_seconds` stops decoding early.
    ponytail: memory is bounded by max_seconds, not resolution — a 4K clip is heavy; lower
    _TRACK_MAX_S (or add a decode-side long-edge cap) if a giant source OOMs the host."""
    if os.path.isdir(path):
        import glob

        files = sorted(
            glob.glob(os.path.join(path, "*.jpg"))
            + glob.glob(os.path.join(path, "*.png"))
        )
        if not files:
            raise RuntimeError(f"no .jpg/.png frames in directory: {path}")
        if max_seconds:
            files = files[: max(1, round(max_seconds * fps_default))]
        return [cv2.imread(f) for f in files], fps_default
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(
            f"could not open video: {path} (headless opencv may lack an mp4 "
            "decoder — pass a directory of extracted frames instead)"
        )
    fps = cap.get(cv2.CAP_PROP_FPS) or fps_default
    max_frames = round(max_seconds * fps) if max_seconds else None
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
        if max_frames and len(frames) >= max_frames:
            break
    cap.release()
    return frames, fps


def _generate_pil(backend, img, caption):
    """Run one VLM pass on a PIL image via a temp PNG. The backend long-edge-resizes to
    its max_side, but that is downscale-only, so a pre-sized ROI crop (≤ OUT_RES) is sent
    as-is — exactly the deploy path."""
    tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        img.save(tf.name)
        tf.close()
        return backend.generate(tf.name, caption)
    finally:
        os.unlink(tf.name)


def _anchor_box(backend, img, caption, prior, use_roi):
    """One anchor pass → new box (or `prior` on parse-fail). With `use_roi` and a `prior`,
    crops a ROI_MARGIN window around it, upscales to ROI_OUT_RES (cheaper prefill +
    super-res), and maps the prediction back — the deployed re-anchor path. Otherwise a
    full-frame acquire."""
    if use_roi and prior is not None:
        win = roi_window(prior, img.width, img.height, ROI_MARGIN)
        crop = crop_resize(img, win, ROI_OUT_RES)
        b = parse_bbox(_generate_pil(backend, crop, caption))
        return map_to_full(b, win, img.width, img.height) if b else prior
    return parse_bbox(_generate_pil(backend, img, caption)) or prior


def render(
    video_path,
    caption,
    out_path,
    backend,
    stride=3,
    period_s=ANCHOR_PERIOD_S,
    acquire_s=ACQUIRE_PERIOD_S,
    track=False,
    roi=True,
    max_seconds=None,
    on_anchor=None,
):
    """Anchor the VLM at the on-Orin cadence; between anchors either hold the box stale
    (Level 1) or, if `track`, let a fast visual tracker hold the lock (Level 2 — the real
    two-tier architecture: VLM seeds, tracker coasts, next VLM regrounds). With `roi` (the
    whole deployed system), re-anchors while locked crop to the last box (cheaper prefill +
    super-res); cold acquire and post-loss re-acquire stay full-frame. Cadence is two-tier
    too: the first anchor is spaced by `acquire_s` (slow full-frame), the rest by `period_s`
    (fast ROI re-anchor)."""
    frames_bgr, fps = _read_frames(video_path, max_seconds=max_seconds)
    n = len(frames_bgr)
    if n == 0:
        raise RuntimeError(f"no frames decoded from {video_path}")

    played, anchors = anchor_schedule(n, fps, acquire_s, period_s, stride)
    played_set = set(played)
    box = None
    lost = False  # tracker dropped the lock → next anchor must re-acquire full-frame
    last_anchor_t = 0.0
    tracker = tracker_name = None
    tag, col = "", ORANGE
    out_frames = []
    # Iterate EVERY frame so the tracker is fed continuously (CSRT drifts and reports a
    # spurious loss if it only sees strided frames — that latched `lost` and forced the
    # next periodic anchor to a needless full-frame re-acquire). Draw only on played frames.
    for fi in range(n):
        bgr = frames_bgr[fi]
        h, w = bgr.shape[:2]
        fresh = fi in anchors
        if fresh:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            # ROI re-anchor only while a lock is held; cold acquire & post-loss re-acquire
            # are full-frame (a crop can't re-find a target that left the window).
            use_roi = roi and box is not None and not lost
            img_pil = Image.fromarray(rgb)
            if on_anchor is not None:
                _fed = (
                    crop_resize(
                        img_pil,
                        roi_window(box, img_pil.width, img_pil.height, ROI_MARGIN),
                        ROI_OUT_RES,
                    )
                    if use_roi
                    else img_pil
                )
            _t0 = time.perf_counter()
            box = _anchor_box(backend, img_pil, caption, box, use_roi)
            if on_anchor is not None:
                on_anchor(fi, _fed, box, img_pil, time.perf_counter() - _t0)
            lost = False
            last_anchor_t = fi / fps
            mode = "ROI re-anchor" if use_roi else "full-frame acquire"
            print(
                f"  anchor @ frame {fi} (t={fi / fps:.2f}s) [{mode}] box={box}",
                flush=True,
            )
            if track and box is not None:
                tracker, tracker_name = _make_tracker()
                try:  # box is clamped, but guard CSRT against any remaining edge ROI
                    tracker.init(bgr, tuple(map(int, _norm_to_xywh(box, w, h))))
                except cv2.error:
                    tracker = None  # couldn't seed → fall back to stale-hold until next anchor
            label = f"ANCHOR — {mode} ({tracker_name})" if track else f"ANCHOR — {mode}"
            tag, col = label, GREEN
        elif track and tracker is not None:
            try:
                ok, xywh = tracker.update(bgr)
            except cv2.error:
                ok = False
            if ok:
                box = _xywh_to_norm(xywh, w, h)
                tag, col = (
                    f"tracking ({tracker_name})  +{fi / fps - last_anchor_t:.1f}s since VLM",
                    CYAN,
                )
            else:
                lost = True
                tag, col = (
                    f"LOST — awaiting re-anchor  +{fi / fps - last_anchor_t:.1f}s",
                    RED,
                )
        else:
            tag = f"held stale +{fi / fps - last_anchor_t:.1f}s (no new VLM yet)"
            col = ORANGE
        if fi in played_set:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            out_frames.append(_draw(rgb, box, caption, tag, col))

    _save(out_frames, out_path, fps / max(1, stride))
    print(
        f"[video] {len(out_frames)} frames, {len(anchors)} anchors -> {out_path}",
        flush=True,
    )
    return out_path


def _save(frames, out_path, out_fps):
    """.mp4 -> pipe raw RGB to ffmpeg (h264, full res, no 256-colour loss).
    Anything else -> animated GIF via PIL. mp4 is the quality path for committed clips."""
    if not out_path.lower().endswith(".mp4"):
        dur = round(1000 / max(out_fps, 1e-6))
        # disposal=2 (restore to background) clears each frame before the next; without
        # it PIL stores partial diffs and the moving box ghosts/smears across its trail.
        frames[0].save(
            out_path,
            save_all=True,
            append_images=frames[1:],
            duration=dur,
            loop=0,
            optimize=False,
            disposal=2,
        )
        return
    import subprocess

    w, h = frames[0].size
    p = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{w}x{h}",
            "-r",
            f"{out_fps:.4f}",
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            # even dims required by yuv420p; pad (no content loss) rather than crop
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-loglevel",
            "error",
            out_path,
        ],
        stdin=subprocess.PIPE,
    )
    for f in frames:
        p.stdin.write(f.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed writing {out_path}")


def _selfcheck():
    # 300 frames @ 30 fps = 10 s; first gap = 4.8 s acquire (144 frames), then 2.0 s
    # re-anchors (60 frames each): 0, 144, 204, 264 -> the two-tier cadence.
    played, anchors = anchor_schedule(300, 30.0, 4.8, 2.0, stride=3)
    assert sorted(anchors) == [0, 144, 204, 264], sorted(anchors)
    assert (sorted(anchors)[1] - sorted(anchors)[0]) > (
        sorted(anchors)[2] - sorted(anchors)[1]
    ), "first (acquire) gap must exceed the re-anchor gap"
    assert anchors <= set(played), "every anchor must be played"
    assert all(p % 3 == 0 or p in anchors for p in played)
    # fps fallback / tiny clip must not divide-by-zero or drop the first anchor
    p2, a2 = anchor_schedule(1, 0.0, 4.8, 2.0, stride=3)
    assert a2 == {0} and p2 == [0], (p2, a2)
    # coord round-trip: an in-frame norm box (0–COORD_SCALE) -> pixel xywh -> norm is identity
    box0 = [10, 20, 30, 40]
    rt = _xywh_to_norm(_norm_to_xywh(box0, 640, 480), 640, 480)
    assert max(abs(a - b) for a, b in zip(rt, box0)) < 1e-6, rt
    # border / reversed boxes must clamp to a valid in-frame ROI (never empty → CSRT-safe)
    for bad in (
        [0, 0, 0, 0],
        [COORD_SCALE, COORD_SCALE, COORD_SCALE, COORD_SCALE],
        [80, 80, 20, 20],
    ):  # zero-area, full-corner, reversed
        x, y, bw, bh = _norm_to_xywh(bad, 640, 480)
        assert (
            bw >= 1
            and bh >= 1
            and x >= 0
            and y >= 0
            and x + bw <= 640
            and y + bh <= 480
        ), (bad, (x, y, bw, bh))
    name = _make_tracker()[1]
    assert name in ("CSRT", "MIL"), name

    # _anchor_box: full-frame acquire sees the whole image; ROI re-anchor sees an OUT_RES
    # crop and maps the box back into the prior's window (no real model needed).
    class _Stub:
        def __init__(self, raw):
            self.raw, self.seen = raw, None

        def generate(self, path, _cap):
            self.seen = Image.open(path).size
            return self.raw

    img = Image.new("RGB", (640, 480))
    s0 = _Stub("10 20 30 40")
    assert _anchor_box(s0, img, "x", None, True) == [10, 20, 30, 40]
    assert s0.seen == (640, 480), s0.seen  # acquire = full frame
    s1 = _Stub("50 50 60 60")
    b = _anchor_box(s1, img, "x", [10, 20, 30, 40], True)
    assert max(s1.seen) == ROI_OUT_RES, s1.seen  # re-anchor sees the upscaled crop
    assert b is not None and all(0 <= v <= COORD_SCALE for v in b), b
    s2 = _Stub("garbage")  # parse-fail keeps the prior box
    assert _anchor_box(s2, img, "x", [10, 20, 30, 40], True) == [10, 20, 30, 40]
    # mp4 writer: 3 odd-sized frames must pad+encode to a non-empty file
    mf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    mf.close()
    try:
        _save(
            [Image.new("RGB", (65, 49), (i, 0, 0)) for i in (10, 120, 230)],
            mf.name,
            10.0,
        )
        assert os.path.getsize(mf.name) > 0, "empty mp4"
    finally:
        os.unlink(mf.name)
    print(f"  selfcheck PASS  anchors {sorted(anchors)}  tracker={name}  mp4-writer ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", help="path to a real aerial video (mp4/avi/...)")
    ap.add_argument("--caption", help="referring phrase to ground")
    ap.add_argument("--out", default="/tmp/anchor-on-video.gif")
    ap.add_argument(
        "--stride", type=int, default=3, help="play every Nth frame into the GIF"
    )
    ap.add_argument(
        "--track",
        action="store_true",
        help="Level 2: seed a fast tracker from each VLM anchor and coast between "
        "anchors (vs the default Level-1 stale-hold)",
    )
    ap.add_argument(
        "--no-roi",
        action="store_true",
        help="force every re-anchor full-frame (default: ROI-crop re-anchor while "
        "locked — the deployed prefill lever)",
    )
    ap.add_argument(
        "--period",
        type=float,
        default=ANCHOR_PERIOD_S,
        help="ROI re-anchor cadence in seconds (steady state; default = measured "
        "on-Orin period)",
    )
    ap.add_argument(
        "--acquire-period",
        type=float,
        default=ACQUIRE_PERIOD_S,
        help="full-frame acquire cadence in seconds (first anchor / post-loss "
        "re-acquire; default = measured on-Orin period)",
    )
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
    with JetsonBackend(
        remote_model, remote_mmproj, ssh_host=args.ssh_host, max_side=args.max_side
    ) as be:
        render(
            args.video,
            args.caption,
            args.out,
            be,
            args.stride,
            args.period,
            args.acquire_period,
            args.track,
            roi=not args.no_roi,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
