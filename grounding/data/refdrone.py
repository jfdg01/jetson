"""RefDrone (aerial) → canonical schema adapter (Phase 1).

The aerial target domain. Part I established the *well-posed subset* (one caption
→ one box; multi-box and empty/negative captions dropped) as the only tractable
supervision — that filter lives here and its effect is reported by `audit.py`.
The largest-box-augmentation lever (Stage 4 next-step #1) is a constructor flag.

Two views are exposed:

* `load_refdrone_raw(split)` → `RawRecord`s — one record per *referring
  expression* (caption) with ALL of its real (non-empty) boxes attached. This is
  the **pre-filter** view the audit consumes to recover the box-per-caption
  distribution (the Stage-2 ill-posedness sentinel). It applies NO well-posed
  filter beyond dropping empty/negative boxes.
* `load_refdrone(split, ...)` → canonical single-box `GroundingSample`s — the
  well-posed subset only, mirroring the Part-I
  `run_stage4_finetune.RefDroneWellPosedDataset` filter *verbatim in behaviour*.

The mdetr JSON has:
  images[]      : one record per referring expression — file_name, width, height,
                  caption, id.
  annotations[] : link by annotation.image_id == images[].id; carry bbox (COCO
                  xywh) and an `empty` flag (bbox==[0,0,0,0] for negatives).
"""

from __future__ import annotations

import glob
import json
import random
from pathlib import Path
from typing import Dict, List

from grounding.contract import SEED, normalize_bbox
from grounding.data.schema import GroundingSample, RawRecord

# Local mirror of the HF dataset snapshot (sunzc-sunny/RefDrone). The annotations
# directory is the authoritative source; fall back to the HF cache glob if absent.
DEFAULT_ANNOT_DIR = Path("/home/gara/refdrone-annotations")
HF_REFDRONE_GLOB = (
    "/home/gara/.cache/huggingface/hub/"
    "datasets--sunzc-sunny--RefDrone/snapshots/*/RefDrone_{split}_mdetr.json"
)
DEFAULT_IMAGE_ROOT = Path("data/VisDrone2019-DET/images")
# mdetr split name → VisDrone image subdirectory
SPLIT_TO_IMGDIR = {"train": "train", "val": "val", "test": "test"}


def _resolve_refdrone_json(split: str, annot_dir: Path = DEFAULT_ANNOT_DIR) -> Path:
    """Locate the mdetr JSON for `split`: local annot dir first, then HF cache."""
    local = annot_dir / f"RefDrone_{split}_mdetr.json"
    if local.exists():
        return local
    matches = glob.glob(HF_REFDRONE_GLOB.format(split=split))
    if not matches:
        raise FileNotFoundError(
            f"could not resolve RefDrone {split} mdetr JSON at {local} "
            f"nor in HF cache ({HF_REFDRONE_GLOB.format(split=split)})"
        )
    return Path(sorted(matches)[0])


def _group_real_boxes(data: dict) -> Dict[int, List[List[float]]]:
    """image_id → list of real (non-empty) boxes in COCO xywh."""
    by_img: Dict[int, List[List[float]]] = {}
    for a in data["annotations"]:
        if a.get("empty", False) or a["bbox"] == [0, 0, 0, 0]:
            continue
        by_img.setdefault(a["image_id"], []).append(a["bbox"])
    return by_img


def load_refdrone_raw(
    split: str,
    *,
    annot_dir: str | Path = DEFAULT_ANNOT_DIR,
) -> List[RawRecord]:
    """Pre-filter view: one `RawRecord` per non-empty-caption referring expression.

    Each record carries ALL of the caption's *real* boxes (COCO xywh → XYXY pixel),
    so the audit can recover the true box-per-caption distribution. No well-posed
    (one-box) filter is applied here; empty/negative boxes are dropped, and
    captions with zero real boxes or an empty caption string are excluded (they
    carry no localizable target). Image presence on disk is NOT required — this is
    a pure annotation-distribution view.
    """
    annot_dir = Path(annot_dir)
    path = _resolve_refdrone_json(split, annot_dir)
    data = json.loads(path.read_text())
    real_by_img = _group_real_boxes(data)

    records: List[RawRecord] = []
    for img in data["images"]:
        cap = (img.get("caption") or "").strip()
        if not cap:
            continue
        boxes_xywh = real_by_img.get(img["id"], [])
        if not boxes_xywh:
            continue  # pure-empty / negative caption: no localizable target
        boxes_xyxy = [[x, y, x + w, y + h] for (x, y, w, h) in boxes_xywh]
        records.append(RawRecord(
            caption=cap,
            boxes_xyxy=boxes_xyxy,
            img_w=int(img["width"]),
            img_h=int(img["height"]),
            source="refdrone",
        ))
    return records


def load_refdrone(
    split: str,
    *,
    largest_box_aug: bool = False,
    image_root: str | Path = DEFAULT_IMAGE_ROOT,
    annot_dir: str | Path = DEFAULT_ANNOT_DIR,
    max_samples: int = 0,
    seed: int = SEED,
) -> List[GroundingSample]:
    """Return RefDrone `split` as canonical well-posed single-box samples.

    Mirrors Part-I `RefDroneWellPosedDataset` verbatim in behaviour: group real
    boxes by image, keep only captions with **exactly one** real box (multi-box =
    the Stage-2 ill-posed killer, dropped), require a non-empty caption and the
    image present on disk, convert COCO xywh → XYXY → normalize 0–`COORD_SCALE`,
    then deterministic seed-42 shuffle + optional cap.

    largest_box_aug: if True, keep multi-box captions too but supervise the single
    largest-area box (the pre-registered Stage-4 data-scaling lever).
    """
    image_root = Path(image_root)
    annot_dir = Path(annot_dir)
    img_dir = image_root / SPLIT_TO_IMGDIR[split]

    path = _resolve_refdrone_json(split, annot_dir)
    data = json.loads(path.read_text())
    real_by_img = _group_real_boxes(data)

    samples: List[GroundingSample] = []
    n_multi = n_empty = n_missing = 0
    for img in data["images"]:
        cap = (img.get("caption") or "").strip()
        boxes = real_by_img.get(img["id"], [])
        if not boxes:
            n_empty += 1
            continue
        if not cap:
            n_empty += 1
            continue
        if len(boxes) > 1 and not largest_box_aug:
            n_multi += 1  # ill-posed: dropped
            continue
        img_path = img_dir / img["file_name"]
        if not img_path.exists():
            n_missing += 1
            continue
        if len(boxes) == 1:
            x, y, w, h = boxes[0]
        else:  # largest_box_aug: supervise the largest-area box
            x, y, w, h = max(boxes, key=lambda b: b[2] * b[3])
        bbox_xyxy = [x, y, x + w, y + h]
        nbbox = normalize_bbox(bbox_xyxy, int(img["width"]), int(img["height"]))
        samples.append(GroundingSample(
            image_path=str(img_path),
            caption=cap,
            bbox=nbbox,
            img_w=int(img["width"]),
            img_h=int(img["height"]),
            source="refdrone",
        ))

    rng = random.Random(seed)
    rng.shuffle(samples)
    if max_samples:
        samples = samples[:max_samples]
    return samples
