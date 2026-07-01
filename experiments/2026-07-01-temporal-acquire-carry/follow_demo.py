"""Demo of the new architecture: ACQUIRE once (VLM) -> CARRY (SAM2 memory) -> REGROUND on loss.

Offline Level-1 demo on a real AerialMind sequence with a real referring expression and a
real occlusion event. The VLM (deployed Q8_0 on the Jetson, the measured acquire path)
grounds the caption once; SAM2 carries the target by memory at frame rate; an empty-mask
streak re-invokes the VLM. Honesty: measured acquire wall is displayed, GT box is drawn
faint, and every event (acquire/loss/re-ground/recovery) lands in the banner + a JSON log.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/follow_demo.py \
        --seq M0205 --caption "Commercial truck" --start 395 --n-frames 320 \
        --out demo-m0205.mp4                      # jetson VLM acquire (default)
    ... --backend oracle                          # GT-box acquire (no Jetson needed)
    ... --selfcheck                               # loss-gate logic only, no GPU

Retarget ("follow the blue car" ... "switch to the white car"): a mid-video caption
switch = a fresh ACQUIRE with the new caption + SAM2 memory reset (cached frames kept):

    ... --seq M0205 --caption "Black car invading other lanes" --start 1 \
        --n-frames 440 --gt-tid 22 --retarget "220:4:The parked taxi"
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from aerialmind import Box, load_sequences  # noqa: E402
from carry_eval import MODEL, iou, mask_to_box  # noqa: E402
from grounding.contract import COORD_SCALE, parse_bbox  # noqa: E402
from grounding.deploy.video import _save  # noqa: E402
from grounding.manifest import capture, write as write_manifest  # noqa: E402

GREEN, CYAN, ORANGE, RED, GREY = (
    (40, 200, 80), (60, 190, 240), (245, 160, 40), (235, 60, 60), (200, 200, 200))


class LossGate:
    """Fire REGROUND after `n` consecutive absent frames; hysteresis: after firing,
    stay quiet until the target is seen again (one re-ground per loss episode)."""

    def __init__(self, n: int):
        self.n, self.streak, self.armed = n, 0, True

    def update(self, present: bool) -> bool:
        if present:
            self.streak, self.armed = 0, True
            return False
        self.streak += 1
        if self.armed and self.streak >= self.n:
            self.armed = False
            return True
        return False


def _selfcheck() -> None:
    g = LossGate(3)
    seen = [g.update(p) for p in
            [1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]]
    #             ^fire@idx4      ^reset  ^fire@idx10 (re-armed by the 1)
    assert seen == [False] * 4 + [True] + [False] * 5 + [True, False], seen
    assert g.streak == 4 and not g.armed
    print("  selfcheck PASS  loss-gate fire/hysteresis/re-arm")


def vlm_acquire(backend, frame_path: str, caption: str, w: int, h: int):
    """One full-frame VLM grounding pass -> (pixel box | None, wall_s)."""
    t0 = time.time()
    raw = backend.generate(frame_path, caption)
    wall = time.time() - t0
    b = parse_bbox(raw)
    if b is None:
        return None, wall
    return (b[0] / COORD_SCALE * w, b[1] / COORD_SCALE * h,
            b[2] / COORD_SCALE * w, b[3] / COORD_SCALE * h), wall


class OracleBackend:
    """GT-box acquire for GPU-only smoke runs; mimics the VLM contract."""

    def __init__(self, track):
        self.track = track

    def acquire(self, frame_num: int, w: int, h: int):
        # nearest labeled frame at/after the request
        cands = [n for n in sorted(self.track.boxes) if n >= frame_num]
        return (self.track.boxes[cands[0]], 0.05) if cands else (None, 0.05)


def _draw_frame(img, mask, box, gt, caption, tag, col, events_line):
    from PIL import ImageDraw, ImageFont

    if mask is not None and mask.any():
        overlay = np.array(img)
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * np.array(GREEN)).astype(np.uint8)
        from PIL import Image
        img = Image.fromarray(overlay)
    d = ImageDraw.Draw(img)
    lw = max(2, round(min(img.size) / 220))
    if gt is not None:
        d.rectangle(gt, outline=GREY, width=1)
    if box is not None:
        d.rectangle(box, outline=col, width=lw)
    try:
        f16, f12 = (ImageFont.truetype("DejaVuSans-Bold.ttf", s) for s in (16, 12))
    except OSError:
        f16 = f12 = ImageFont.load_default()
    d.text((6, 4), tag, fill=col, font=f16)
    d.text((6, 24), events_line, fill=(235, 235, 235), font=f12)
    d.text((6, img.size[1] - 18), f'"{caption}"  (grey = GT)', fill=GREY, font=f12)
    return img


def run_demo(args) -> dict:
    import torch
    from PIL import Image
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    seq = next(s for s in load_sequences() if s.name == args.seq)
    frames = [n for n in seq.frame_nums if n >= args.start][: args.n_frames]
    gt_track = seq.tracks().get(args.gt_tid) if args.gt_tid else None

    retarget = None  # (frame_num, gt_track_b, caption_b)
    if args.retarget:
        rf, rtid, rcap = args.retarget.split(":", 2)
        retarget = (int(rf), seq.tracks().get(int(rtid)), rcap)
        assert frames[0] < retarget[0] <= frames[-1], "retarget frame outside clip"

    def cap_gt(n: int):  # active (caption, gt_track) at frame n
        if retarget and n >= retarget[0]:
            return retarget[2], retarget[1]
        return args.caption, gt_track

    # -- acquire backend
    if args.backend == "oracle":
        assert gt_track, "--backend oracle needs --gt-tid"
        tr_by_cap = {args.caption: gt_track}
        if retarget:
            tr_by_cap[retarget[2]] = retarget[1]
        acquire = lambda fn, cap: OracleBackend(tr_by_cap[cap]).acquire(  # noqa: E731
            fn, seq.width, seq.height)
        be_ctx = None
    else:
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend

        print("[demo] booting Jetson q8_0 server...", flush=True)
        be_ctx = JetsonBackend(
            f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
            f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
            ssh_host=args.ssh_host, max_side=1024)
        be = be_ctx.__enter__()
        acquire = lambda fn, cap: vlm_acquire(  # noqa: E731
            be, str(seq.frame_path(fn)), cap, seq.width, seq.height)

    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    events, out_frames, per_frame = [], [], {}
    try:
        with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp, \
                torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            for i, n in enumerate(frames):
                (Path(tmp) / f"{i:07d}.jpg").symlink_to(seq.frame_path(n))
            state = predictor.init_state(tmp, offload_video_to_cpu=True)

            # ACQUIRE
            box0, wall0 = acquire(frames[0], args.caption)
            if box0 is None:
                raise RuntimeError("acquire parse-fail on the first frame")
            gt0 = gt_track.boxes.get(frames[0]) if gt_track else None
            events.append({"event": "ACQUIRE", "frame": frames[0],
                           "wall_s": round(wall0, 2), "box": box0,
                           "iou_vs_gt": round(iou(box0, gt0), 3) if gt0 else None})
            print(f"[demo] ACQUIRE @ {frames[0]}  wall={wall0:.2f}s  "
                  f"iou_vs_gt={events[-1]['iou_vs_gt']}", flush=True)
            predictor.add_new_points_or_box(state, frame_idx=0, obj_id=1,
                                            box=np.array(box0))

            gate = LossGate(args.loss_n)
            ridx = frames.index(retarget[0]) if retarget else None
            cur, t_carry, n_carry = 0, 0.0, 0
            while cur < len(frames):
                interrupt = None  # "REGROUND" | "RETARGET"
                t0 = time.time()
                for fidx, _ids, logits in predictor.propagate_in_video(
                        state, start_frame_idx=cur):
                    mask = (logits[0, 0] > 0.0).cpu().numpy()
                    box = mask_to_box(mask)
                    per_frame[frames[fidx]] = (mask, box)
                    n_carry += 1
                    if ridx is not None and fidx >= ridx:
                        cur, interrupt, ridx = fidx, "RETARGET", None
                        break
                    if gate.update(box is not None):
                        cur, interrupt = fidx, "REGROUND"
                        break
                t_carry += time.time() - t0
                if interrupt is None:
                    break
                if interrupt == "RETARGET":
                    # new lock: drop SAM2 memory/objects (cached frames kept), fresh gate
                    predictor.reset_state(state)
                    gate = LossGate(args.loss_n)
                cap, gt = cap_gt(frames[cur])
                rbox, rwall = acquire(frames[cur], cap)
                gtb = gt.boxes.get(frames[cur]) if gt else None
                events.append({"event": interrupt, "frame": frames[cur],
                               "wall_s": round(rwall, 2), "box": rbox, "caption": cap,
                               "iou_vs_gt": round(iou(rbox, gtb), 3)
                               if rbox and gtb else None})
                print(f"[demo] {interrupt} @ {frames[cur]}  wall={rwall:.2f}s  "
                      f"box={'ok' if rbox else 'PARSE-FAIL'}", flush=True)
                if rbox is not None:
                    predictor.add_new_points_or_box(state, frame_idx=cur, obj_id=1,
                                                    box=np.array(rbox))
                elif interrupt == "RETARGET":
                    raise RuntimeError("retarget acquire parse-fail — no object to carry")
                # REGROUND parse-fail: keep carrying; hysteresis re-fires next episode
            carry_fps = n_carry / t_carry if t_carry else 0.0
    finally:
        if be_ctx is not None:
            be_ctx.__exit__(*sys.exc_info())

    # -- render + score
    ious, absent, was_lost = [], 0, False
    ev_by_frame = {e["frame"]: e for e in events}
    short = {"ACQUIRE": "A", "REGROUND": "RG", "RETARGET": "RT"}
    ev_line = ", ".join(short[e["event"]] + "@" + str(e["frame"]) for e in events)
    for n in frames:
        mask, box = per_frame.get(n, (None, None))
        caption, gtt = cap_gt(n)
        gt = gtt.boxes.get(n) if gtt else None
        if gt is not None:
            ious.append(iou(box, gt) if box else 0.0)
        if box is None:
            absent += 1
        e = ev_by_frame.get(n)
        if e:
            tag, col = (f"{e['event']} — VLM {e['wall_s']}s wall", GREEN)
            was_lost = e["event"] == "REGROUND" and e["box"] is None
        elif box is None:
            tag, col, was_lost = "LOST — carrying on memory", RED, True
        elif was_lost:
            tag, col, was_lost = "RE-ASSOCIATED (SAM2 memory)", ORANGE, False
        else:
            tag, col = f"CARRY (SAM2 @ {carry_fps:.0f} FPS on 3090)", CYAN
        img = Image.open(seq.frame_path(n)).convert("RGB")
        line = f"frame {n} | acquire {events[0]['wall_s']}s | events: {ev_line}"
        out_frames.append(_draw_frame(img, mask, box, gt, caption, tag, col, line))

    _save(out_frames, args.out, args.fps)
    summary = {
        "seq": args.seq, "caption": args.caption, "frames": [frames[0], frames[-1]],
        "backend": args.backend, "events": events, "carry_fps": round(carry_fps, 1),
        "mean_iou_vs_gt": round(float(np.mean(ious)), 3) if ious else None,
        "iou_at_25": round(float(np.mean([v >= 0.25 for v in ious])), 3) if ious else None,
        "pred_absent_frac": round(absent / len(frames), 3),
        "out": args.out,
    }
    out_dir = HERE / "runs"
    m = capture("follow-demo", vars(args) | {"model": MODEL})
    run_dir = write_manifest(m, runs_dir=str(out_dir), results=summary)
    (Path(run_dir) / "events.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seq", default="M0205")
    ap.add_argument("--caption", default="Commercial truck")
    ap.add_argument("--start", type=int, default=395)
    ap.add_argument("--n-frames", type=int, default=320)
    ap.add_argument("--gt-tid", type=int, default=25,
                    help="GT track id for the honesty overlay (0 = none)")
    ap.add_argument("--loss-n", type=int, default=75,
                    help="absent-frame streak before REGROUND (~3 s at 25 fps; longer "
                         "than a typical occlusion so SAM2 memory gets first shot)")
    ap.add_argument("--retarget", default=None, metavar="FRAME:TID:CAPTION",
                    help='mid-video caption switch, e.g. "220:4:The parked taxi" '
                         "(TID = GT track of the new target, for the honesty overlay)")
    ap.add_argument("--backend", choices=["jetson", "oracle"], default="jetson")
    ap.add_argument("--ssh-host", default="jetson")
    ap.add_argument("--fps", type=float, default=25.0, help="render fps (ESTIMATE)")
    ap.add_argument("--out", default="/tmp/follow-demo.mp4")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    run_demo(args)


if __name__ == "__main__":
    main()
