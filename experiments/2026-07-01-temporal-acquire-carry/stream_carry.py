"""Phase 3.0: frame-at-a-time SAM2 carry for the closed loop.

sam2==1.1.0 only propagates over a pre-loaded frame directory; a control loop
gets frames one at a time. StreamCarry reuses the batch path's own inner step
(`_run_single_frame_inference`) on a frame list that grows per step, so the
streaming output is the same computation as `propagate_in_video`, minus the
preloading. Memory older than PRUNE_AFTER frames is dropped (the model attends
to num_maskmem=7 recents + <=16 obj-ptr frames, so far-past entries are dead
weight that would otherwise grow unbounded in a long flight).

Parity gate (RQ pre-reg 3.0): per-frame mask-box IoU stream-vs-batch >= 0.99.

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/stream_carry.py \
        --clip <frames-dir> --box x1,y1,x2,y2 [--image-size N] [--cap 100]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from carry_eval import MODEL, iou, mask_to_box  # noqa: E402

IMG_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
IMG_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
PRUNE_AFTER = 100


class _FrameList:
    """Quacks like the preloaded images tensor; grows one frame at a time."""

    def __init__(self):
        self.frames: list[torch.Tensor | None] = []

    def append(self, t: torch.Tensor) -> None:
        self.frames.append(t)

    def __getitem__(self, i: int) -> torch.Tensor:
        return self.frames[i]

    def __len__(self) -> int:
        return len(self.frames)


class StreamCarry:
    """init from frame 0 + box, then step(frame) -> (mask, box) per live frame."""

    def __init__(self, predictor, first_frame: np.ndarray | str | Path, box,
                 prune_after: int = PRUNE_AFTER):
        self.p = predictor
        self.prune_after = prune_after
        # init_state via a one-frame temp dir: reuses the stock loader (jpg-only)
        # for frame 0. A path is symlinked (byte-identical to the batch reference);
        # a live ndarray is jpg-encoded once (q=95, no reference to diverge from).
        with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
            dst = Path(tmp) / "0000000.jpg"
            if isinstance(first_frame, (str, Path)):
                dst.symlink_to(Path(first_frame).resolve())
            else:
                Image.fromarray(first_frame).save(dst, quality=95)
            self.state = predictor.init_state(tmp, offload_video_to_cpu=True)
        imgs = _FrameList()
        imgs.append(self.state["images"][0].cpu().float())
        self.state["images"] = imgs
        predictor.add_new_points_or_box(
            self.state, frame_idx=0, obj_id=1, box=np.asarray(box, dtype=np.float32)
        )
        predictor.propagate_in_video_preflight(self.state)

    def _prep(self, frame: np.ndarray) -> torch.Tensor:
        # mirror sam2.utils.misc._load_img_as_tensor + load_video_frames normalization
        img = Image.fromarray(frame).resize((self.p.image_size, self.p.image_size))
        t = torch.from_numpy(np.asarray(img) / 255.0).permute(2, 0, 1).float()
        return (t - IMG_MEAN) / IMG_STD

    @torch.inference_mode()
    def step(self, frame: np.ndarray):
        """Carry onto one new frame. Returns (mask HxW bool, box or None)."""
        st = self.state
        idx = len(st["images"])
        st["images"].append(self._prep(frame))
        st["num_frames"] = idx + 1
        st["video_height"], st["video_width"] = frame.shape[:2]
        out_dict = st["output_dict_per_obj"][0]
        current_out, pred_masks = self.p._run_single_frame_inference(
            inference_state=st,
            output_dict=out_dict,
            frame_idx=idx,
            batch_size=1,
            is_init_cond_frame=False,
            point_inputs=None,
            mask_inputs=None,
            reverse=False,
            run_mem_encoder=True,
        )
        out_dict["non_cond_frame_outputs"][idx] = current_out
        st["frames_tracked_per_obj"][0][idx] = {"reverse": False}
        _, video_res_masks = self.p._get_orig_video_res_output(st, pred_masks)
        old = idx - self.prune_after
        if old > 0:  # keep frame 0 (cond); bound RAM for long flights
            out_dict["non_cond_frame_outputs"].pop(old, None)
            st["images"].frames[old] = None
        mask = (video_res_masks[0, 0] > 0.0).cpu().numpy()
        return mask, mask_to_box(mask)


def main() -> None:
    ap = argparse.ArgumentParser(description="parity check: stream vs batch propagate")
    ap.add_argument("--clip", required=True, help="frame dir (jpg/png, sorted)")
    ap.add_argument("--box", required=True, help="x1,y1,x2,y2 prompt on first frame")
    ap.add_argument("--image-size", type=int, default=None)
    ap.add_argument("--cap", type=int, default=100)
    args = ap.parse_args()

    from sam2.sam2_video_predictor import SAM2VideoPredictor

    box = [float(v) for v in args.box.split(",")]
    paths = sorted(Path(args.clip).glob("*.[jp][pn]g"))[: args.cap]
    over = [f"++model.image_size={args.image_size}"] if args.image_size else []
    predictor = SAM2VideoPredictor.from_pretrained(MODEL, hydra_overrides_extra=over)

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        # batch reference
        with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
            for i, p in enumerate(paths):
                (Path(tmp) / f"{i:07d}.jpg").symlink_to(p.resolve())
            state = predictor.init_state(tmp, offload_video_to_cpu=True)
            predictor.add_new_points_or_box(state, frame_idx=0, obj_id=1,
                                            box=np.asarray(box, dtype=np.float32))
            batch_boxes = {}
            for fidx, _ids, logits in predictor.propagate_in_video(state):
                batch_boxes[fidx] = mask_to_box((logits[0, 0] > 0.0).cpu().numpy())
            predictor.reset_state(state)

        # stream
        frames = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
        sc = StreamCarry(predictor, paths[0], box)
        t0 = time.time()
        stream_boxes = {0: batch_boxes[0]}
        for i, f in enumerate(frames[1:], start=1):
            _, stream_boxes[i] = sc.step(f)
        fps = (len(frames) - 1) / (time.time() - t0)

    ious = []
    for i in range(1, len(frames)):
        b, s = batch_boxes.get(i), stream_boxes.get(i)
        ious.append(1.0 if b is None and s is None else (iou(b, s) if b and s else 0.0))
    m = float(np.mean(ious))
    print(f"parity: mean IoU={m:.4f} min={min(ious):.4f} frames={len(ious)} stream_fps={fps:.1f}")
    assert m >= 0.99, f"parity FAIL: {m:.4f}"
    print("parity PASS")


if __name__ == "__main__":
    main()
