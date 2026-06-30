"""
Stage 2 fine-tuning: SmolVLM-500M-Instruct on RefDrone + VisDrone aerial grounding data.

Uses:  .venv-ft (torch 2.6.0+cu124, transformers 5.12, peft 0.19, datasets 5.0)
GPU:   RTX 3090 24 GB (local)
Run:   source .venv-ft/bin/activate && python runners/run_stage2_finetune.py [opts]

Key flags:
  --visdrone-dir PATH   Root of VisDrone 2019-DET (contains images/train/, images/val/)
  --output-dir PATH     Where to save the merged checkpoint (default: ./smolvlm_ft)
  --epochs INT          Training epochs (default: 3)
  --batch INT           Per-device batch size (default: 2)
  --grad-accum INT      Gradient accumulation steps (default: 8; effective batch = batch*grad_accum)
  --lr FLOAT            Learning rate (default: 2e-4)
  --lora-rank INT       LoRA rank r (default: 16)
  --max-samples INT     Cap training samples (0 = all; useful for --dry-run smoke test)
  --dry-run             Load model + 1 batch, do 1 forward pass, exit (no training)
  --eval-only PATH      Skip training; evaluate merged checkpoint at PATH vs val set
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

# ── runtime check ────────────────────────────────────────────────────────────
try:
    import torch
    from transformers import SmolVLMForConditionalGeneration, AutoProcessor
    from peft import LoraConfig, get_peft_model, TaskType
    from PIL import Image as PILImage
    from torch.utils.data import Dataset, DataLoader
    from accelerate import Accelerator
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nActivate: source .venv-ft/bin/activate")

# ── constants ─────────────────────────────────────────────────────────────────
MODEL_ID        = "HuggingFaceTB/SmolVLM-500M-Instruct"
REFDRONE_HF_ID  = "sunzc-sunny/RefDrone"
MAX_NEW_TOKENS  = 64          # response cap for eval calls
IMAGE_SIZE      = 512         # resize long edge to this before model
LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]  # LLaMA text backbone

GROUNDING_PROMPT = (
    "Locate the {target} in this aerial image. "
    'Return the bounding box as JSON: {{"bbox": [x1, y1, x2, y2]}} '
    "where coordinates are in pixels."
)


# ── dataset ───────────────────────────────────────────────────────────────────

def _resize_keep_aspect(img: PILImage.Image, max_side: int) -> PILImage.Image:
    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return img
    return img.resize((int(w * scale), int(h * scale)), PILImage.BILINEAR)


def _xywh_to_xyxy(bbox, img_w, img_h):
    """RefDrone bbox: [x, y, w, h] in pixels → [x1, y1, x2, y2] clamped."""
    x, y, w, h = bbox
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(img_w, x + w), min(img_h, y + h)
    return [int(x1), int(y1), int(x2), int(y2)]


def _load_refdrone_mdetr_json(json_path: Path) -> list[dict]:
    """
    Parse a RefDrone MDETR-format JSON file into a flat list of
    {'file_name', 'caption', 'bbox_xywh'} dicts, one per (image, annotation) pair.
    Empty annotations (bbox=[0,0,0,0] or empty=True) are skipped.

    RefDrone MDETR schema (COCO-style):
      images[i]: {id, file_name, caption, ...}
      annotations[i]: {image_id, bbox [x,y,w,h] in pixels, empty: bool, ...}
    Multiple annotations can share the same image_id (multiple objects per caption).
    """
    with open(json_path) as f:
        data = json.load(f)

    # build image_id → image record map
    img_by_id = {img["id"]: img for img in data["images"]}

    items = []
    for ann in data["annotations"]:
        if ann.get("empty", False):
            continue
        bbox = ann["bbox"]
        if bbox == [0, 0, 0, 0]:
            continue
        img = img_by_id.get(ann["image_id"])
        if img is None:
            continue
        items.append({
            "file_name": img["file_name"],
            "caption":   img["caption"],
            "bbox_xywh": bbox,
        })
    return items


class RefDroneDataset(Dataset):
    """
    Loads RefDrone annotations from the MDETR JSON files (downloaded to HF cache
    by `datasets.load_dataset("sunzc-sunny/RefDrone")`) and matches images from
    a local VisDrone 2019-DET directory.

    RefDrone MDETR JSON format (COCO-style):
      images[i]: {id, file_name, caption, ...}
      annotations[i]: {image_id, bbox [x,y,w,h] in pixels, empty: bool, ...}

    Annotation JSON files are at:
      ~/.cache/huggingface/hub/datasets--sunzc-sunny--RefDrone/snapshots/<hash>/
        RefDrone_train_mdetr.json, RefDrone_val_mdetr.json

    Images are at: <visdrone_dir>/images/train/ and images/val/
    Filename: <file_name from annotation> (e.g. 0000109_01140_d_0000063.jpg)
    """

    HF_CACHE_ROOT = Path.home() / ".cache/huggingface/hub/datasets--sunzc-sunny--RefDrone"

    def __init__(self, hf_split: str, visdrone_dir: Path, processor,
                 max_samples: int = 0, image_size: int = IMAGE_SIZE,
                 refdrone_json: Path | None = None):
        self.processor  = processor
        self.image_size = image_size

        # locate MDETR JSON
        if refdrone_json is None:
            snapshots = sorted((self.HF_CACHE_ROOT / "snapshots").iterdir())
            if not snapshots:
                raise FileNotFoundError(
                    f"RefDrone not in HF cache at {self.HF_CACHE_ROOT}. "
                    f"Run: python -c \"from datasets import load_dataset; "
                    f"load_dataset('sunzc-sunny/RefDrone', split='train')\" to trigger download."
                )
            snap = snapshots[-1]
            json_name = f"RefDrone_{hf_split}_mdetr.json"
            refdrone_json = snap / json_name

        print(f"[dataset] loading RefDrone '{hf_split}' from {refdrone_json}")
        raw_items = _load_refdrone_mdetr_json(refdrone_json)
        print(f"[dataset] {len(raw_items)} non-empty annotations")

        # map VisDrone image root (train→images/train, val→images/val)
        img_dir = visdrone_dir / "images" / hf_split

        self.items = []
        missing = 0
        for row in raw_items:
            img_path = img_dir / row["file_name"]
            if not img_path.exists():
                missing += 1
                continue
            self.items.append({
                "img_path":  img_path,
                "sentence":  row["caption"],
                "bbox_xywh": row["bbox_xywh"],
            })
            if max_samples and len(self.items) >= max_samples:
                break

        print(f"[dataset] {len(self.items)} samples loaded, {missing} images not found")
        if missing > 0.1 * max(len(self.items) + missing, 1):
            print(f"[dataset] WARNING: {missing/(len(self.items)+missing):.0%} images missing — "
                  f"check --visdrone-dir has images/{hf_split}/ matching RefDrone filenames")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx]
        img = PILImage.open(item["img_path"]).convert("RGB")
        orig_w, orig_h = img.size

        img = _resize_keep_aspect(img, self.image_size)
        new_w, new_h = img.size

        # scale bbox to resized image coordinates
        scale_x = new_w / orig_w
        scale_y = new_h / orig_h
        x, y, w, h = item["bbox_xywh"]
        bbox = _xywh_to_xyxy(
            [x * scale_x, y * scale_y, w * scale_x, h * scale_y],
            new_w, new_h
        )

        prompt = GROUNDING_PROMPT.format(target=item["sentence"])
        target_json = json.dumps({"bbox": bbox})

        return {
            "image":       img,
            "prompt":      prompt,
            "target_json": target_json,
        }


def _collate_fn(batch, processor):
    """Tokenize a batch: image + prompt → input_ids, pixel_values, labels."""
    prompts      = [b["prompt"] for b in batch]
    images       = [b["image"] for b in batch]
    target_jsons = [b["target_json"] for b in batch]

    # Build chat-format messages the same way run_phase_c uses the model
    messages = [
        [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": p}]}]
        for p in prompts
    ]
    texts = [
        processor.apply_chat_template(m, add_generation_prompt=True)
        for m in messages
    ]

    # Append target response so the model trains on the answer
    full_texts = [t + tj for t, tj in zip(texts, target_jsons)]

    # max_length must accommodate image tokens: SmolVLM uses ~1136 tokens for 1 image
    # + text prompt (~50 tokens) + target JSON (~30 tokens) → use 1280 to be safe
    inputs = processor(
        text=full_texts,
        images=images,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=1280,
    )

    # Labels = input_ids with prompt tokens masked as -100
    # Find where the prompt ends (apply_chat_template output without target)
    prompt_inputs = processor(
        text=texts,
        images=images,
        return_tensors="pt",
        padding="longest",
        truncation=True,
        max_length=1280,
    )
    labels = inputs["input_ids"].clone()
    # mask everything up to (and including) the prompt portion
    prompt_len = prompt_inputs["input_ids"].shape[1]
    labels[:, :prompt_len] = -100   # mask prompt; only supervise target
    labels[labels == processor.tokenizer.pad_token_id] = -100

    inputs["labels"] = labels
    return inputs


# ── evaluation ────────────────────────────────────────────────────────────────

def _parse_bbox(text: str):
    """Extract [x1,y1,x2,y2] from model output; return None if unparseable."""
    import re
    # try strict JSON first
    m = re.search(r'\{[^{}]*"bbox"\s*:\s*\[([^\]]+)\][^{}]*\}', text)
    if m:
        try:
            vals = [float(v.strip()) for v in m.group(1).split(",")]
            if len(vals) == 4:
                return [int(v) for v in vals]
        except ValueError:
            pass
    return None


def _iou(a, b):
    """IoU of two [x1,y1,x2,y2] boxes."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return inter / (area_a + area_b - inter)


def evaluate(model, processor, dataset, device, n_samples: int = 200) -> dict:
    """Run greedy decoding on up to n_samples and compute parse rate + IoU@0.25."""
    model.eval()
    n = min(n_samples, len(dataset))
    parsed = 0; iou25 = 0; total_iou = 0.0
    with torch.no_grad():
        for i in range(n):
            item = dataset[i]
            img  = item["image"]
            prompt = item["prompt"]
            gt_json = item["target_json"]
            gt_bbox = json.loads(gt_json)["bbox"]

            messages = [[{"role": "user", "content": [
                {"type": "image"}, {"type": "text", "text": prompt}
            ]}]]
            text = processor.apply_chat_template(messages[0], add_generation_prompt=True)
            inputs = processor(text=[text], images=[img], return_tensors="pt").to(device)

            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
            # decode only the new tokens
            new_tokens = out[0, inputs["input_ids"].shape[1]:]
            response = processor.decode(new_tokens, skip_special_tokens=True)

            bbox = _parse_bbox(response)
            if bbox is not None:
                parsed += 1
                iou_val = _iou(bbox, gt_bbox)
                total_iou += iou_val
                if iou_val >= 0.25:
                    iou25 += 1

    parse_rate = parsed / n
    iou25_rate = iou25 / n
    mean_iou   = total_iou / max(parsed, 1)
    return {"n": n, "parse_rate": parse_rate, "iou@0.25": iou25_rate, "mean_iou": mean_iou}


# ── training loop ─────────────────────────────────────────────────────────────

def train(args):
    accelerator = Accelerator(gradient_accumulation_steps=args.grad_accum)
    device = accelerator.device
    print(f"[train] device: {device} | effective batch: {args.batch * args.grad_accum}")

    # ── model + processor ────────────────────────────────────────────────────
    print("[train] loading processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("[train] loading model...")
    model = SmolVLMForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map=None,  # let accelerate handle placement
    )

    # Print layer names so we can verify LoRA targets exist
    lm_layer_names = {n.split(".")[-1] for n, _ in model.named_modules()}
    for target in LORA_TARGET_MODULES:
        if target not in lm_layer_names:
            print(f"[train] WARNING: LoRA target '{target}' not found in model modules")

    # ── LoRA ─────────────────────────────────────────────────────────────────
    lora_cfg = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_rank * 2,
        target_modules=LORA_TARGET_MODULES,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    if args.dry_run:
        # Forward pass with a real (tiny) image via processor — validates model + LoRA + processor
        print("[dry-run] building 1 real batch via processor and doing forward pass...")
        import numpy as np
        dummy_img = PILImage.fromarray(np.zeros((64, 64, 3), dtype=np.uint8))
        msgs = [[{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": "Locate the car."}
        ]}]]
        text = processor.apply_chat_template(msgs[0], add_generation_prompt=True)
        target = '{"bbox": [10, 20, 50, 60]}'
        full_text = text + target
        inputs = processor(text=[full_text], images=[dummy_img], return_tensors="pt")
        prompt_inputs = processor(text=[text], images=[dummy_img], return_tensors="pt")
        labels = inputs["input_ids"].clone()
        labels[:, :prompt_inputs["input_ids"].shape[1]] = -100
        inputs["labels"] = labels
        inputs = {k: v.to(device, dtype=torch.bfloat16 if v.dtype == torch.float32 else v.dtype)
                  for k, v in inputs.items()}

        model.to(device)
        with torch.no_grad():
            out = model(**inputs)
        print(f"[dry-run] loss = {out.loss.item():.4f}  PASS")
        return

    # ── datasets ─────────────────────────────────────────────────────────────
    vd_dir = Path(args.visdrone_dir)
    train_ds = RefDroneDataset("train", vd_dir, processor,
                               max_samples=args.max_samples)
    val_ds   = RefDroneDataset("val",   vd_dir, processor,
                               max_samples=min(200, args.max_samples or 200))

    def collate(batch):
        return _collate_fn(batch, processor)

    # num_workers=0: processor can't be pickled across worker processes reliably
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              collate_fn=collate, num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=1, shuffle=False,
                              collate_fn=collate, num_workers=0)

    # ── optimizer ─────────────────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=0.01,
    )
    total_steps = len(train_loader) * args.epochs // args.grad_accum
    scheduler   = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    model, optimizer, train_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, scheduler
    )

    # ── logging ───────────────────────────────────────────────────────────────
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    loss_csv_path = Path("experiments/stage2-finetune/raw/train_loss.csv")
    iou_csv_path  = Path("experiments/stage2-finetune/raw/eval_iou.csv")
    loss_csv_path.parent.mkdir(parents=True, exist_ok=True)

    loss_rows = [["epoch", "step", "loss", "lr", "elapsed_s"]]
    iou_rows  = [["epoch", "parse_rate", "iou@0.25", "mean_iou"]]

    t0 = time.time()
    global_step = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_batches  = 0

        for step, batch in enumerate(train_loader):
            with accelerator.accumulate(model):
                out  = model(**batch)
                loss = out.loss
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

            loss_val = loss.item()
            epoch_loss += loss_val
            n_batches  += 1

            if step % 50 == 0:
                elapsed = time.time() - t0
                lr_now  = scheduler.get_last_lr()[0]
                print(f"  E{epoch} step {step}/{len(train_loader)}  "
                      f"loss={loss_val:.4f}  lr={lr_now:.2e}  {elapsed:.0f}s", flush=True)
                loss_rows.append([epoch, global_step, f"{loss_val:.6f}",
                                  f"{lr_now:.2e}", f"{elapsed:.1f}"])

        mean_loss = epoch_loss / max(n_batches, 1)
        print(f"[epoch {epoch}] mean_loss={mean_loss:.4f}  ({time.time()-t0:.0f}s total)", flush=True)

        # per-epoch eval + checkpoint
        if accelerator.is_main_process:
            eval_model = accelerator.unwrap_model(model)
            metrics = evaluate(eval_model, processor, val_ds, device)
            print(f"[eval E{epoch}] parse_rate={metrics['parse_rate']:.1%}  "
                  f"iou@0.25={metrics['iou@0.25']:.1%}  mean_iou={metrics['mean_iou']:.3f}", flush=True)
            iou_rows.append([epoch, f"{metrics['parse_rate']:.4f}",
                             f"{metrics['iou@0.25']:.4f}", f"{metrics['mean_iou']:.4f}"])

            # save per-epoch checkpoint (unmerged LoRA adapter)
            ckpt_dir = output_dir / f"epoch{epoch}"
            eval_model.save_pretrained(ckpt_dir)
            processor.save_pretrained(ckpt_dir)
            print(f"[train] epoch {epoch} adapter checkpoint saved to {ckpt_dir}", flush=True)

    # ── save ─────────────────────────────────────────────────────────────────
    if accelerator.is_main_process:
        print("[train] merging LoRA adapter into base weights...")
        merged = accelerator.unwrap_model(model).merge_and_unload()
        merged.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)
        print(f"[train] merged checkpoint saved to {output_dir}")

        # write CSVs
        with open(loss_csv_path, "w", newline="") as f:
            csv.writer(f).writerows(loss_rows)
        with open(iou_csv_path, "w", newline="") as f:
            csv.writer(f).writerows(iou_rows)
        print(f"[train] logs written to {loss_csv_path}, {iou_csv_path}")


# ── eval-only mode ────────────────────────────────────────────────────────────

def eval_only(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[eval-only] loading merged checkpoint from {args.eval_only}")
    processor = AutoProcessor.from_pretrained(args.eval_only)
    model = SmolVLMForConditionalGeneration.from_pretrained(
        args.eval_only, torch_dtype=torch.bfloat16
    ).to(device)

    vd_dir = Path(args.visdrone_dir)
    val_ds = RefDroneDataset("val", vd_dir, processor, max_samples=200)
    metrics = evaluate(model, processor, val_ds, device)
    print(f"[eval-only] n={metrics['n']}  parse_rate={metrics['parse_rate']:.1%}  "
          f"iou@0.25={metrics['iou@0.25']:.1%}  mean_iou={metrics['mean_iou']:.3f}")


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--visdrone-dir", default="data/VisDrone2019-DET",
                   help="Root of VisDrone 2019-DET dataset (contains images/train/, images/val/)")
    p.add_argument("--output-dir", default="./smolvlm_ft",
                   help="Directory to save the merged fine-tuned checkpoint")
    p.add_argument("--epochs",     type=int,   default=3)
    p.add_argument("--batch",      type=int,   default=2)
    p.add_argument("--grad-accum", type=int,   default=8)
    p.add_argument("--lr",         type=float, default=2e-4)
    p.add_argument("--lora-rank",  type=int,   default=16)
    p.add_argument("--max-samples",type=int,   default=0,
                   help="Cap dataset size (0 = all). Use e.g. 64 for a smoke test.")
    p.add_argument("--dry-run",    action="store_true",
                   help="Load model, run 1 forward pass, exit (verify setup)")
    p.add_argument("--eval-only",  metavar="CHECKPOINT_DIR", default=None,
                   help="Evaluate a merged checkpoint on val set; skip training")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.eval_only:
        eval_only(args)
    else:
        train(args)
