"""cv2 stand-in for SAM2's missing `_C.get_connected_componnets` CUDA kernel.

The PyPI `sam2` wheel ships `csrc/connected_components.cu` uncompiled, so
`sam2.utils.misc.get_connected_components` raises ImportError and SAM2 silently
skips its hole-filling post-process (`fill_hole_area=8` in the sam2.1 HF configs).
Importing this module patches in an opencv implementation of the same contract.

ponytail: CPU round-trip per frame, ~0.2 ms at 1024x1024 masks. Compile the CUDA
kernel (`SAM2_BUILD_CUDA=1`) only if that ever shows up in a latency budget.
"""

import cv2
import numpy as np
import torch


def get_connected_components(mask):
    """(N,1,H,W) binary mask -> (labels, per-pixel component area), 8-connectivity."""
    arr = mask.to(torch.uint8).cpu().numpy()
    labels = np.zeros(arr.shape, dtype=np.int32)
    counts = np.zeros(arr.shape, dtype=np.int32)
    for n in range(arr.shape[0]):
        for c in range(arr.shape[1]):
            num, lab, stats, _ = cv2.connectedComponentsWithStats(arr[n, c], connectivity=8)
            labels[n, c] = lab
            counts[n, c] = stats[:, cv2.CC_STAT_AREA][lab] * (lab > 0)
    dev = mask.device
    return torch.from_numpy(labels).to(dev), torch.from_numpy(counts).to(dev)


def patch():
    from sam2.utils import misc

    misc.get_connected_components = get_connected_components


patch()


if __name__ == "__main__":
    # 5x5 square with a 1-px hole, plus a separate 2-px blob
    m = torch.zeros(1, 1, 10, 10, dtype=torch.uint8)
    m[0, 0, 1:6, 1:6] = 1
    m[0, 0, 3, 3] = 0
    m[0, 0, 8, 8:10] = 1
    labels, counts = get_connected_components(m)
    assert labels[0, 0, 1, 1] != 0 and labels[0, 0, 8, 8] != 0
    assert labels[0, 0, 1, 1] != labels[0, 0, 8, 8], "separate blobs share a label"
    assert counts[0, 0, 1, 1] == 24, counts[0, 0, 1, 1]  # 25 - 1 hole
    assert counts[0, 0, 8, 8] == 2
    assert counts[0, 0, 0, 0] == 0 and labels[0, 0, 0, 0] == 0, "background not zeroed"

    # end to end: the hole must actually get filled through SAM2's own code path
    from sam2.utils.misc import fill_holes_in_mask_scores

    scores = torch.where(m.bool(), 1.0, -1.0)
    filled = fill_holes_in_mask_scores(scores, max_area=8)
    assert filled[0, 0, 3, 3] > 0, "1-px hole not filled"
    assert filled[0, 0, 0, 0] < 0, "background wrongly filled"
    print("ok")
