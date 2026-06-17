"""RefCOCO → canonical schema adapter.

RefCOCO is the in-domain/warm-start corpus (Stage 3 produced the G2-PASS
checkpoint from it). This adapter loads the HF dataset `jxu124/refcoco`
(annotations only) + local COCO train2014 images and emits canonical
`GroundingSample`s with boxes already normalized to 0–`COORD_SCALE` via
`grounding.contract.normalize_bbox`.

Read-only / inference-only. The flatten + deterministic seed-42 shuffle + cap
logic is lifted **verbatim in behaviour** from the validated Part-I trainer
`experiments/legacy/run_stage3_finetune.py::RefCOCODataset` so that
`load_refcoco("validation", max_samples=N)` yields the *same* subset that
produced the Part-I in-domain numbers — this is what lets the Phase-0 harness
self-check reproduce ~82.5% IoU@0.25 on `smolvlm_ft3`.

NOTE on phase ordering: this adapter is implemented during Phase 0 (it is needed
to give the fidelity harness a real eval set) but is strictly read-only — it does
not compute the Phase-1 audit statistics (box-per-caption / object-size
distributions). `data/audit.py` adds those on top at Phase 1 startup. See
DECISIONS.md (Part II).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

from grounding.contract import SEED, normalize_bbox
from grounding.data.schema import GroundingSample

REFCOCO_HF_ID = "jxu124/refcoco"
DEFAULT_COCO_ROOT = Path("data/coco")


def load_refcoco(
    split: str = "validation",
    *,
    coco_root: str | Path = DEFAULT_COCO_ROOT,
    max_samples: int = 0,
    seed: int = SEED,
) -> List[GroundingSample]:
    """Return RefCOCO `split` as canonical single-box `GroundingSample`s.

    Each HF row is one referring-expression group: a single `bbox` (XYXY pixels)
    with multiple `captions` all describing that box. We expand each caption into
    its own sample (many captions → one box, which is well-posed). Coordinates are
    normalized to 0–`COORD_SCALE`. Rows whose image is not present locally are
    skipped.

    `max_samples > 0` caps the (deterministically shuffled) result so a subset is
    representative rather than alphabetical; `seed` controls that shuffle.
    """
    from datasets import load_dataset  # local import: keep module torch/datasets-free at import

    coco_root = Path(coco_root)
    ds = load_dataset(REFCOCO_HF_ID, split=split)

    samples: List[GroundingSample] = []
    missing = 0
    for row in ds:
        fname = row["image_path"].split("/")[-1]   # COCO_train2014_<id>.jpg
        img_path = coco_root / "train2014" / fname
        if not img_path.exists():
            missing += 1
            continue
        info = json.loads(row["raw_image_info"])
        W, H = int(info["width"]), int(info["height"])
        nbbox = normalize_bbox(row["bbox"], W, H)
        for cap in row["captions"]:
            cap = (cap or "").strip()
            if not cap:
                continue
            samples.append(GroundingSample(
                image_path=str(img_path),
                caption=cap,
                bbox=nbbox,
                img_w=W,
                img_h=H,
                source="refcoco",
            ))

    if missing and missing > 0.5 * (missing + len(ds)):
        raise FileNotFoundError(
            f"{missing} refs have no image under {coco_root}/train2014/. "
            f"Did COCO train2014 finish downloading/extracting?"
        )

    rng = random.Random(seed)
    rng.shuffle(samples)
    if max_samples:
        samples = samples[:max_samples]
    return samples
