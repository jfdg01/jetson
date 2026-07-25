"""Runs ON THE JETSON. One arm of P6.6: hold a SAM2 carry (or nothing) for N seconds
while `tegrastats` logs power beside it, and report the achieved step rate over time.

Frames come from the device's own disk (`~/sam2-bench/clip`), NOT from the host: in a
real deployment they come from the on-board camera, so putting the ssh transport inside
the measured loop would charge network and JPEG-encode cost to the maintain.

  cd ~/sam2-bench && ./.venv/bin/python -u maintain_cost_dev.py --arm carry \
      --image-size 640 --seconds 300 --out /tmp/p66_carry640.json

The clip is looped for the whole window, so the carry's box wanders once it wraps. That
is deliberate: this measures COST and RATE, not tracking accuracy.
"""
import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _seed_box(shape, frac=0.25):
    """A centred box covering `frac` of each side. No GT is needed to measure watts, and
    inventing one would invite the number being read as a tracking result."""
    h, w = shape[:2]
    return (w * (0.5 - frac / 2), h * (0.5 - frac / 2),
            w * (0.5 + frac / 2), h * (0.5 + frac / 2))


def run_carry(clip_dir, image_size, seconds, prune_after):
    import cv2
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    from stream_carry import MODEL, StreamCarry

    paths = sorted(Path(clip_dir).glob("*.jpg"))
    assert paths, f"no frames in {clip_dir}"
    frames = [cv2.imread(str(p)) for p in paths]
    assert all(f is not None for f in frames), "a frame failed to decode"

    t0 = time.time()
    over = [f"++model.image_size={image_size}"] if image_size != 1024 else []
    predictor = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)
    load_s = time.time() - t0

    steps = []          # (wall_clock_offset_s, step_ms)
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        carry = StreamCarry(predictor, frames[0], _seed_box(frames[0].shape),
                            prune_after=prune_after)
        start = time.time()
        i = 0
        while time.time() - start < seconds:
            i += 1
            t = time.time()
            carry.step(frames[i % len(frames)])
            steps.append((round(t - start, 3), round((time.time() - t) * 1000, 1)))
    return {"load_s": round(load_s, 2), "n_steps": len(steps), "steps": steps,
            "n_frames_in_clip": len(frames), "image_size": image_size,
            "prune_after": prune_after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("idle", "carry"), required=True)
    ap.add_argument("--image-size", type=int, default=640)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--prune-after", type=int, default=100,
                    help="SAM2 memory ring; 100 is the deployed value (R-16)")
    ap.add_argument("--clip", default=str(HERE / "clip"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    t_start = time.time()
    if args.arm == "idle":
        # No perception. The point of this arm is the floor the others subtract.
        time.sleep(args.seconds)
        rec = {"n_steps": 0, "steps": []}
    else:
        rec = run_carry(args.clip, args.image_size, args.seconds, args.prune_after)
    rec.update(arm=args.arm, seconds=args.seconds,
               wall_s=round(time.time() - t_start, 2),
               t_start_unix=round(t_start, 3), t_end_unix=round(time.time(), 3))
    Path(args.out).write_text(json.dumps(rec))
    hz = rec["n_steps"] / max(rec["wall_s"], 1e-9)
    print(f"[dev] arm={args.arm} steps={rec['n_steps']} wall={rec['wall_s']}s "
          f"rate={hz:.2f} Hz", flush=True)


if __name__ == "__main__":
    main()
