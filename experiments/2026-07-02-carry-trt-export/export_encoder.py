"""E1 step 1-2: export the SAM2.1-tiny image encoder to ONNX + parity-gate it (3090).

Encoder-only export (memory attention stays PyTorch): the per-frame carry cost is the
ViT-Hiera forward on the full frame; the stateful memory bank is the known-hard part to
ONNX, so we leave it alone. `forward_image`'s high-res conv_s0/conv_s1 also stay in torch
(1x1 convs, negligible) and are re-applied in the monkeypatch.

    .venv-ft/bin/python experiments/2026-07-02-carry-trt-export/export_encoder.py \
        --image-size 768 --clip <M0205-dir> --box 496,69,577,110

Steps: (1) export enc<S>.onnx; (2a) ORT vs eager max-abs-diff on all 6 outputs (<1e-2);
(2b) batch-propagate parity with forward_image monkeypatched to ORT, mask-box IoU>=0.99.
ORT runs on CPU here (host is cu12, the gpu wheel wants cu13) -- this gates the ONNX graph's
fp32 correctness; the fp16/TensorRT accuracy is validated on-device in step 5.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "2026-07-01-temporal-acquire-carry"))
sys.path.insert(0, str(HERE.parents[1]))

from carry_eval import iou, mask_to_box  # noqa: E402

MODEL = "facebook/sam2.1-hiera-tiny"


class EncoderWrapper(nn.Module):
    """image_encoder -> flat 6-tuple (3 backbone_fpn + 3 vision_pos_enc), ONNX-friendly.

    vision_features is dropped: it is backbone_fpn[-1] byte-identical (asserted in demo),
    so the monkeypatch rebuilds it for free instead of exporting a 4th duplicate output.
    """

    def __init__(self, image_encoder: nn.Module):
        super().__init__()
        self.enc = image_encoder

    def forward(self, x):
        out = self.enc(x)
        f = out["backbone_fpn"]
        p = out["vision_pos_enc"]
        return f[0], f[1], f[2], p[0], p[1], p[2]


def load_predictor(image_size: int, model: str = MODEL):
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    over = [f"++model.image_size={image_size}"]
    return SAM2VideoPredictor.from_pretrained(model, hydra_overrides_extra=over).eval()


def export(predictor, image_size: int, out_path: Path) -> Path:
    dev = next(predictor.parameters()).device
    wrapper = EncoderWrapper(predictor.image_encoder).eval()
    dummy = torch.randn(1, 3, image_size, image_size, device=dev)
    names = ["fpn0", "fpn1", "fpn2", "pos0", "pos1", "pos2"]
    with torch.inference_mode():
        torch.onnx.export(
            wrapper, dummy, str(out_path),
            input_names=["x"], output_names=names,
            opset_version=17, dynamo=False,
        )
    return out_path


def _patched_forward_image(predictor, sess, dev):
    """Drop-in for predictor.forward_image: encoder via ORT, high-res convs in torch."""
    import onnxruntime as ort  # noqa: F401  (import guard: sess already built)

    def fwd(img_batch: torch.Tensor):
        outs = sess.run(None, {"x": img_batch.detach().cpu().float().numpy()})
        t = [torch.from_numpy(o).to(dev) for o in outs]
        bb = {"vision_features": t[2], "vision_pos_enc": [t[3], t[4], t[5]],
              "backbone_fpn": [t[0], t[1], t[2]]}
        # ponytail: mirror forward_image's high-res branch exactly (1x1 convs, torch-side)
        bb["backbone_fpn"][0] = predictor.sam_mask_decoder.conv_s0(bb["backbone_fpn"][0])
        bb["backbone_fpn"][1] = predictor.sam_mask_decoder.conv_s1(bb["backbone_fpn"][1])
        return bb

    return fwd


def _batch_boxes(predictor, paths, box):
    """Run the stock batch propagate, return {frame_idx: mask-box}. No autocast: fp32."""
    with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
        for i, p in enumerate(paths):
            (Path(tmp) / f"{i:07d}.jpg").symlink_to(Path(p).resolve())
        state = predictor.init_state(tmp, offload_video_to_cpu=True)
        predictor.add_new_points_or_box(state, frame_idx=0, obj_id=1,
                                        box=np.asarray(box, dtype=np.float32))
        boxes = {}
        for fidx, _ids, logits in predictor.propagate_in_video(state):
            boxes[fidx] = mask_to_box((logits[0, 0] > 0.0).cpu().numpy())
        predictor.reset_state(state)
    return boxes


def main() -> None:
    import onnxruntime as ort

    ap = argparse.ArgumentParser()
    ap.add_argument("--image-size", type=int, default=768)
    ap.add_argument("--clip", required=True, help="M0205 100-frame dir")
    ap.add_argument("--box", required=True, help="x1,y1,x2,y2 prompt on frame 0")
    ap.add_argument("--cap", type=int, default=100)
    ap.add_argument("--out", default=None)
    # EXP-9: the same export at 640 for sam2.1-hiera-small. Default keeps E1 reproducible.
    ap.add_argument("--model", default=MODEL)
    # EXP-9 (2026-07-26): ORT's graph optimizer MISCOMPILES the deeper hiera-small graph.
    # Measured on enc640_small.onnx, max-abs-diff vs eager on the three feature outputs:
    #   DISABLE_ALL 2.3e-04 | BASIC 8.3e-01 | ENABLE_ALL (the ORT default) 1.3e-02,
    # and the first export attempt read 1.6e+33. `onnx.checker` passes and ORT logs
    # "Error merging shape info for output '/enc/trunk/Concat_3_output_0' source:{4}
    # target:{5}. Falling back to lenient merge." -- i.e. the graph is sound and the
    # optimizer is not. tiny is unaffected either way (2.30e-04 vs 2.32e-04). So this
    # gate runs unoptimised where asked; the authoritative check is the ON-DEVICE
    # TensorRT-vs-eager mask parity (EXP-9 G1), which does not go through ORT at all.
    ap.add_argument("--ort-graph-opt", choices=["all", "disable"], default="all")
    a = ap.parse_args()

    S = a.image_size
    out_path = Path(a.out) if a.out else HERE / f"enc{S}.onnx"
    box = [float(v) for v in a.box.split(",")]
    paths = sorted(Path(a.clip).glob("*.[jp][pn]g"))[: a.cap]
    assert paths, f"no frames in {a.clip}"

    predictor = load_predictor(S, a.model)
    dev = next(predictor.parameters()).device

    print(f"[1] exporting {a.model} encoder @ {S} -> {out_path.name}")
    export(predictor, S, out_path)
    so = ort.SessionOptions()
    if a.ort_graph_opt == "disable":
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        print("    (ORT graph optimizer DISABLED -- see --ort-graph-opt)")
    sess = ort.InferenceSession(str(out_path), so, providers=["CPUExecutionProvider"])

    # 2a: raw-output max-abs-diff on a real frame
    print("[2a] output parity (ORT vs eager, fp32)")
    frame = np.asarray(Image.open(paths[0]).convert("RGB").resize((S, S))) / 255.0
    x = ((torch.from_numpy(frame).permute(2, 0, 1).float()
          - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1))
         / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1))[None].to(dev)
    with torch.inference_mode():
        eager = EncoderWrapper(predictor.image_encoder)(x)
    ort_out = sess.run(None, {"x": x.cpu().numpy()})
    diffs = [float(np.abs(e.cpu().numpy() - o).max()) for e, o in zip(eager, ort_out)]
    print("    max-abs-diff per output:", [f"{d:.2e}" for d in diffs])
    assert max(diffs) < 1e-2, f"output parity FAIL: {max(diffs):.2e}"
    print("    output parity PASS (<1e-2)")

    # 2b: end-to-end batch propagate, eager encoder vs ORT-monkeypatched encoder
    print("[2b] end-to-end mask parity (batch propagate, eager vs ORT encoder)")
    with torch.inference_mode():
        ref = _batch_boxes(predictor, paths, box)
        predictor.forward_image = _patched_forward_image(predictor, sess, dev)
        test = _batch_boxes(predictor, paths, box)
    ious = []
    for i in range(1, len(paths)):
        b, s = ref.get(i), test.get(i)
        ious.append(1.0 if b is None and s is None else (iou(b, s) if b and s else 0.0))
    m = float(np.mean(ious))
    print(f"    mask parity: mean IoU={m:.4f} min={min(ious):.4f} frames={len(ious)}")
    assert m >= 0.99, f"mask parity FAIL: {m:.4f}"
    print("    mask parity PASS (>=0.99)")
    print(f"DONE: {out_path} ready to scp to the Jetson for trtexec")


if __name__ == "__main__":
    main()
