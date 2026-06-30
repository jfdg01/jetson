"""
Stage 3 fine-tuning: SmolVLM-500M-Instruct on RefCOCO referring-expression grounding.

This is the *corrected* fine-tuning run after Stage 2 (RefDrone) failed with mode
collapse (IoU@0.25 = 1%). See experiments/stage3-refcoco-finetune/README.md for the
full diagnosis and rationale. Key changes vs Stage 2:

  1. Dataset: RefCOCO (single-instance referring expressions, large objects) instead
     of RefDrone (multi-instance tiny objects, one caption → ~3.8 boxes = ill-posed).
     Each RefCOCO ref has multiple captions all describing the SAME box, so expanding
     captions → samples is well-posed (many captions → one box, the inverse of the
     RefDrone bug).
  2. Coordinates: normalized 0-1000 integer bins (resolution-independent, the
     PaliGemma/Florence convention) instead of raw resized pixels.
  3. LoRA: attention + MLP (q,k,v,o,gate,up,down) instead of attention-only, for more
     adaptation capacity. Vision encoder stays FROZEN (preserves mmproj GGUF reuse).
  4. Prompt: a single unified prompt string shared verbatim with the grounding probe
     and Phase C, so train/inference never diverge.

Uses:  .venv-ft (torch 2.6.0+cu124, transformers 4.57.6, peft 0.19, datasets 5.0)
GPU:   RTX 3090 24 GB (local)
Run:   source .venv-ft/bin/activate && python runners/run_stage3_finetune.py [opts]

Key flags:
  --coco-root PATH      Root containing train2014/ (default: data/coco)
  --output-dir PATH     Where to save the merged checkpoint (default: ./smolvlm_ft3)
  --epochs INT          Training epochs (default: 1)
  --batch INT           Per-device batch size (default: 2)
  --grad-accum INT      Gradient accumulation steps (default: 8; eff. batch = batch*grad_accum)
  --lr FLOAT            Learning rate (default: 2e-4)
  --lora-rank INT       LoRA rank r (default: 16)
  --max-samples INT     Cap training caption-box pairs (default: 50000; 0 = all ~120k)
  --dry-run             Load model + 1 batch, do 1 forward pass, exit (no training)
  --eval-only PATH      Skip training; evaluate merged checkpoint at PATH vs val set
"""

import argparse
import csv
import json
import random
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
    from datasets import load_dataset
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nActivate: source .venv-ft/bin/activate")

# ── constants ─────────────────────────────────────────────────────────────────
MODEL_ID        = "HuggingFaceTB/SmolVLM-500M-Instruct"
REFCOCO_HF_ID   = "jxu124/refcoco"
MAX_NEW_TOKENS  = 64          # response cap for eval calls
IMAGE_SIZE      = 512         # resize long edge before model (coords are normalized, so safe)
COORD_SCALE     = 1000        # normalized coordinate range [0, COORD_SCALE]
SEED            = 42

# LoRA on text backbone attention AND MLP for more adaptation capacity.
# Vision encoder (SigLIP) deliberately left frozen → mmproj GGUF stays reusable.
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",       # attention
    "gate_proj", "up_proj", "down_proj",          # MLP
]

# UNIFIED prompt — must match run_grounding_probe.py and run_phase_c.py verbatim.
GROUNDING_PROMPT = (
    'Locate "{target}". Return the bounding box as JSON '
    '{{"bbox": [x1, y1, x2, y2]}} with integer coordinates normalized from 0 to 1000.'
)


# ── dataset ───────────────────────────────────────────────────────────────────

def _resize_keep_aspect(img: PILImage.Image, max_side: int) -> PILImage.Image:
    w, h = img.size
    scale = max_side / max(w, h)
    if scale >= 1.0:
        return img
    return img.resize((int(w * scale), int(h * scale)), PILImage.BILINEAR)


def _normalize_bbox(bbox_xyxy, img_w, img_h, scale=COORD_SCALE):
    """[x1,y1,x2,y2] in pixels → integer coords normalized to [0, scale]."""
    x1, y1, x2, y2 = bbox_xyxy
    nx1 = round(x1 / img_w * scale)
    ny1 = round(y1 / img_h * scale)
    nx2 = round(x2 / img_w * scale)
    ny2 = round(y2 / img_h * scale)
    clamp = lambda v: max(0, min(scale, v))
    return [clamp(nx1), clamp(ny1), clamp(nx2), clamp(ny2)]


class RefCOCODataset(Dataset):
    """
    RefCOCO referring-expression grounding from the HF dataset `jxu124/refcoco`
    (annotations only) + local COCO train2014 images.

    Each HF row is one referring expression group:
      bbox            : [x1, y1, x2, y2] in original-image pixels (XYXY)
      captions        : list[str]  — multiple phrases, all for the SAME bbox
      image_path      : "coco/train2014/COCO_train2014_<id>.jpg"
      raw_image_info  : JSON string with width/height

    We expand each caption into its own training sample (many captions → one box,
    which is well-posed — the inverse of the RefDrone one-caption→many-boxes bug).
    Coordinates are normalized to 0-1000 so they are resolution-independent.

    Images live at <coco_root>/train2014/COCO_train2014_<id>.jpg.
    """

    def __init__(self, hf_split: str, coco_root: Path, processor,
                 max_samples: int = 0, image_size: int = IMAGE_SIZE,
                 seed: int = SEED):
        self.processor  = processor
        self.image_size = image_size
        self.coco_root  = Path(coco_root)

        print(f"[dataset] loading RefCOCO '{hf_split}' from {REFCOCO_HF_ID}")
        ds = load_dataset(REFCOCO_HF_ID, split=hf_split)

        # Flatten: one (image, caption, bbox) per sample.
        items = []
        missing = 0
        seen_missing = set()
        for row in ds:
            rel = row["image_path"]            # coco/train2014/COCO_train2014_*.jpg
            fname = rel.split("/")[-1]
            img_path = self.coco_root / "train2014" / fname
            if not img_path.exists():
                missing += 1
                if fname not in seen_missing and len(seen_missing) < 5:
                    seen_missing.add(fname)
                continue
            info = json.loads(row["raw_image_info"])
            W, H = info["width"], info["height"]
            nbbox = _normalize_bbox(row["bbox"], W, H)
            for cap in row["captions"]:
                cap = (cap or "").strip()
                if not cap:
                    continue
                items.append({
                    "img_path": img_path,
                    "sentence": cap,
                    "nbbox":    nbbox,
                })

        print(f"[dataset] {len(items)} caption-box pairs "
              f"({missing} refs skipped: image not found)")
        if missing:
            print(f"[dataset] sample missing files: {sorted(seen_missing)}")
            if missing > 0.5 * (missing + len(ds)):
                raise FileNotFoundError(
                    f"{missing} refs have no image under {self.coco_root}/train2014/. "
                    f"Did COCO train2014 finish downloading/extracting?"
                )

        # Deterministic shuffle then cap (so the subset is representative, not the
        # first-N alphabetical images).
        rng = random.Random(seed)
        rng.shuffle(items)
        if max_samples:
            items = items[:max_samples]
        self.items = items
        print(f"[dataset] using {len(self.items)} samples")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx]
        img = PILImage.open(item["img_path"]).convert("RGB")
        img = _resize_keep_aspect(img, self.image_size)   # coords normalized → resize is safe

        prompt = GROUNDING_PROMPT.format(target=item["sentence"])
        target_json = json.dumps({"bbox": item["nbbox"]})

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

    messages = [
        [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": p}]}]
        for p in prompts
    ]
    texts = [
        processor.apply_chat_template(m, add_generation_prompt=True)
        for m in messages
    ]
    full_texts = [t + tj for t, tj in zip(texts, target_jsons)]

    inputs = processor(
        text=full_texts, images=images, return_tensors="pt",
        padding=True, truncation=True, max_length=1280,
    )
    prompt_inputs = processor(
        text=texts, images=images, return_tensors="pt",
        padding="longest", truncation=True, max_length=1280,
    )
    labels = inputs["input_ids"].clone()
    prompt_len = prompt_inputs["input_ids"].shape[1]
    labels[:, :prompt_len] = -100              # mask prompt; supervise only the target
    labels[labels == processor.tokenizer.pad_token_id] = -100
    inputs["labels"] = labels
    return inputs


# ── evaluation ────────────────────────────────────────────────────────────────

def _parse_bbox(text: str):
    """Extract [x1,y1,x2,y2] from model output; return None if unparseable."""
    import re
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
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return inter / (area_a + area_b - inter)


def evaluate(model, processor, dataset, device, n_samples: int = 200) -> dict:
    """Greedy decode on up to n_samples; parse rate + IoU@0.25 in normalized space.

    Also tracks prediction *spread* (std of predicted box centers) so mode collapse
    — the Stage 2 failure mode — is caught explicitly: a collapsed model has
    near-zero center spread.
    """
    model.eval()
    n = min(n_samples, len(dataset))
    parsed = 0; iou25 = 0; total_iou = 0.0
    cx_list = []; cy_list = []
    samples = []
    with torch.no_grad():
        for i in range(n):
            item = dataset[i]
            img  = item["image"]
            prompt = item["prompt"]
            gt_bbox = json.loads(item["target_json"])["bbox"]

            messages = [[{"role": "user", "content": [
                {"type": "image"}, {"type": "text", "text": prompt}
            ]}]]
            text = processor.apply_chat_template(messages[0], add_generation_prompt=True)
            inputs = processor(text=[text], images=[img], return_tensors="pt").to(device)
            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
            new_tokens = out[0, inputs["input_ids"].shape[1]:]
            response = processor.decode(new_tokens, skip_special_tokens=True)

            bbox = _parse_bbox(response)
            if i < 8:
                samples.append((gt_bbox, response.strip()[:80]))
            if bbox is not None:
                parsed += 1
                cx_list.append((bbox[0] + bbox[2]) / 2)
                cy_list.append((bbox[1] + bbox[3]) / 2)
                iou_val = _iou(bbox, gt_bbox)
                total_iou += iou_val
                if iou_val >= 0.25:
                    iou25 += 1

    import statistics as st
    cx_std = st.pstdev(cx_list) if len(cx_list) > 1 else 0.0
    cy_std = st.pstdev(cy_list) if len(cy_list) > 1 else 0.0
    return {
        "n": n,
        "parse_rate": parsed / n,
        "iou@0.25": iou25 / n,
        "mean_iou": total_iou / max(parsed, 1),
        "center_std": (cx_std + cy_std) / 2,   # mode-collapse sentinel (low = collapsed)
        "samples": samples,
    }


# ── training loop ─────────────────────────────────────────────────────────────

def train(args):
    accelerator = Accelerator(gradient_accumulation_steps=args.grad_accum)
    device = accelerator.device
    print(f"[train] device: {device} | effective batch: {args.batch * args.grad_accum}")

    print("[train] loading processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("[train] loading model...")
    model = SmolVLMForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, device_map=None,
    )

    lm_layer_names = {n.split(".")[-1] for n, _ in model.named_modules()}
    for target in LORA_TARGET_MODULES:
        if target not in lm_layer_names:
            print(f"[train] WARNING: LoRA target '{target}' not found in model modules")

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
        print("[dry-run] building 1 real batch via processor and doing forward pass...")
        import numpy as np
        dummy_img = PILImage.fromarray(np.zeros((64, 64, 3), dtype=np.uint8))
        msgs = [[{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": GROUNDING_PROMPT.format(target="car")}
        ]}]]
        text = processor.apply_chat_template(msgs[0], add_generation_prompt=True)
        target = json.dumps({"bbox": [100, 200, 500, 600]})
        inputs = processor(text=[text + target], images=[dummy_img], return_tensors="pt")
        prompt_inputs = processor(text=[text], images=[dummy_img], return_tensors="pt")
        labels = inputs["input_ids"].clone()
        labels[:, :prompt_inputs["input_ids"].shape[1]] = -100
        inputs["labels"] = labels
        inputs = {k: v.to(device) for k, v in inputs.items()}
        model.to(device)
        with torch.no_grad():
            out = model(**inputs)
        print(f"[dry-run] loss = {out.loss.item():.4f}  PASS")
        return

    # ── datasets ─────────────────────────────────────────────────────────────
    coco_root = Path(args.coco_root)
    train_ds = RefCOCODataset("train", coco_root, processor, max_samples=args.max_samples)
    val_ds   = RefCOCODataset("validation", coco_root, processor,
                              max_samples=min(200, args.max_samples or 200))

    def collate(batch):
        return _collate_fn(batch, processor)

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              collate_fn=collate, num_workers=0)

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=0.01,
    )
    total_steps = len(train_loader) * args.epochs // args.grad_accum
    scheduler   = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    model, optimizer, train_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, scheduler
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    loss_csv_path = Path("experiments/stage3-refcoco-finetune/raw/train_loss.csv")
    iou_csv_path  = Path("experiments/stage3-refcoco-finetune/raw/eval_iou.csv")
    loss_csv_path.parent.mkdir(parents=True, exist_ok=True)

    loss_rows = [["epoch", "step", "loss", "lr", "elapsed_s"]]
    iou_rows  = [["epoch", "parse_rate", "iou@0.25", "mean_iou", "center_std"]]

    state_dir = output_dir / "accel_state"   # full accelerate state (model+opt+sched)
    meta_path = output_dir / "resume_meta.json"

    def save_checkpoint(epoch, batch_in_epoch, global_step, elapsed):
        """Persist a resumable mid-run checkpoint: accelerate state + adapter + meta.

        A hardware blink (e.g. the CUDA 'unspecified launch failure' that killed the
        first Stage 3 run at step 17450/25000) then costs <= --save-every batches, not
        the whole epoch. The adapter copy under latest/ is directly GGUF-exportable."""
        accelerator.wait_for_everyone()
        accelerator.save_state(str(state_dir))
        if accelerator.is_main_process:
            adapter_dir = output_dir / "latest"
            accelerator.unwrap_model(model).save_pretrained(adapter_dir)
            meta = {"epoch": epoch, "batch_in_epoch": batch_in_epoch,
                    "global_step": global_step, "elapsed_s": elapsed,
                    "max_samples": args.max_samples, "epochs": args.epochs}
            meta_path.write_text(json.dumps(meta, indent=2))
            with open(loss_csv_path, "w", newline="") as f:
                csv.writer(f).writerows(loss_rows)
            print(f"[ckpt] saved resumable state @ E{epoch} batch {batch_in_epoch} "
                  f"(global_step {global_step}) -> {state_dir}", flush=True)

    # ── resume (optional) ──────────────────────────────────────────────────────
    start_epoch = 1
    resume_skip = 0          # batches to skip in the first (resumed) epoch
    elapsed_offset = 0.0     # so reported wall-clock continues across the crash
    global_step = 0
    if args.resume_from:
        print(f"[resume] loading accelerate state from {args.resume_from}", flush=True)
        accelerator.load_state(args.resume_from)
        rmeta = json.loads((Path(args.resume_from).parent / "resume_meta.json").read_text())
        start_epoch    = rmeta["epoch"]
        resume_skip    = rmeta["batch_in_epoch"]
        global_step    = rmeta["global_step"]
        elapsed_offset = rmeta["elapsed_s"]
        # carry forward whatever loss history already exists on disk
        if loss_csv_path.exists():
            with open(loss_csv_path) as f:
                rows = list(csv.reader(f))
            if len(rows) > 1:
                loss_rows = rows
        print(f"[resume] continuing at E{start_epoch} batch {resume_skip} "
              f"(global_step {global_step}, {elapsed_offset:.0f}s already elapsed)", flush=True)

    t0 = time.time() - elapsed_offset

    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        epoch_loss = 0.0; n_batches = 0
        if epoch == start_epoch and resume_skip > 0:
            epoch_loader = accelerator.skip_first_batches(train_loader, resume_skip)
            step_offset  = resume_skip
        else:
            epoch_loader = train_loader
            step_offset  = 0
        for step_i, batch in enumerate(epoch_loader):
            step = step_i + step_offset
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
            epoch_loss += loss_val; n_batches += 1
            if step % 50 == 0:
                elapsed = time.time() - t0
                lr_now  = scheduler.get_last_lr()[0]
                print(f"  E{epoch} step {step}/{len(train_loader)}  "
                      f"loss={loss_val:.4f}  lr={lr_now:.2e}  {elapsed:.0f}s", flush=True)
                loss_rows.append([epoch, global_step, f"{loss_val:.6f}",
                                  f"{lr_now:.2e}", f"{elapsed:.1f}"])
                # flush CSV incrementally so progress survives a crash
                with open(loss_csv_path, "w", newline="") as f:
                    csv.writer(f).writerows(loss_rows)

            # mid-epoch resumable checkpoint (next batch index = step + 1)
            if args.save_every and step > 0 and (step + 1) % args.save_every == 0:
                save_checkpoint(epoch, step + 1, global_step, time.time() - t0)

        mean_loss = epoch_loss / max(n_batches, 1)
        print(f"[epoch {epoch}] mean_loss={mean_loss:.4f}  ({time.time()-t0:.0f}s total)", flush=True)

        if accelerator.is_main_process:
            eval_model = accelerator.unwrap_model(model)
            metrics = evaluate(eval_model, processor, val_ds, device)
            print(f"[eval E{epoch}] parse_rate={metrics['parse_rate']:.1%}  "
                  f"iou@0.25={metrics['iou@0.25']:.1%}  mean_iou={metrics['mean_iou']:.3f}  "
                  f"center_std={metrics['center_std']:.1f}", flush=True)
            for gt, resp in metrics["samples"]:
                print(f"    gt={gt}  pred={resp}", flush=True)
            iou_rows.append([epoch, f"{metrics['parse_rate']:.4f}",
                             f"{metrics['iou@0.25']:.4f}", f"{metrics['mean_iou']:.4f}",
                             f"{metrics['center_std']:.2f}"])
            with open(iou_csv_path, "w", newline="") as f:
                csv.writer(f).writerows(iou_rows)

            ckpt_dir = output_dir / f"epoch{epoch}"
            eval_model.save_pretrained(ckpt_dir)
            processor.save_pretrained(ckpt_dir)
            print(f"[train] epoch {epoch} adapter checkpoint saved to {ckpt_dir}", flush=True)

    if accelerator.is_main_process:
        print("[train] merging LoRA adapter into base weights...")
        merged = accelerator.unwrap_model(model).merge_and_unload()
        merged.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)
        print(f"[train] merged checkpoint saved to {output_dir}")
        with open(loss_csv_path, "w", newline="") as f:
            csv.writer(f).writerows(loss_rows)
        with open(iou_csv_path, "w", newline="") as f:
            csv.writer(f).writerows(iou_rows)
        print(f"[train] logs written to {loss_csv_path}, {iou_csv_path}")


# ── eval-only mode ────────────────────────────────────────────────────────────

def eval_only(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[eval-only] loading merged checkpoint from {args.eval_only}")
    # load processor from base MODEL_ID (merged-checkpoint processor save has the
    # extra_special_tokens-as-list bug; weights are fine)
    try:
        processor = AutoProcessor.from_pretrained(args.eval_only)
    except Exception as e:
        print(f"[eval-only] processor load from checkpoint failed ({e}); using base")
        processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = SmolVLMForConditionalGeneration.from_pretrained(
        args.eval_only, torch_dtype=torch.bfloat16
    ).to(device)

    coco_root = Path(args.coco_root)
    val_ds = RefCOCODataset("validation", coco_root, processor, max_samples=200)
    metrics = evaluate(model, processor, val_ds, device)
    print(f"[eval-only] n={metrics['n']}  parse_rate={metrics['parse_rate']:.1%}  "
          f"iou@0.25={metrics['iou@0.25']:.1%}  mean_iou={metrics['mean_iou']:.3f}  "
          f"center_std={metrics['center_std']:.1f}")
    for gt, resp in metrics["samples"]:
        print(f"    gt={gt}  pred={resp}")


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coco-root", default="data/coco",
                   help="Root containing train2014/ (COCO 2014 images)")
    p.add_argument("--output-dir", default="./smolvlm_ft3",
                   help="Directory to save the merged fine-tuned checkpoint")
    p.add_argument("--epochs",     type=int,   default=1)
    p.add_argument("--batch",      type=int,   default=2)
    p.add_argument("--grad-accum", type=int,   default=8)
    p.add_argument("--lr",         type=float, default=2e-4)
    p.add_argument("--lora-rank",  type=int,   default=16)
    p.add_argument("--max-samples",type=int,   default=50000,
                   help="Cap caption-box pairs (default 50000 ~10h; 0 = all ~120k)")
    p.add_argument("--save-every", type=int,   default=1000,
                   help="Save a resumable mid-epoch checkpoint every N batches "
                        "(default 1000 ~27min; 0 = epoch-end only)")
    p.add_argument("--resume-from", metavar="STATE_DIR", default=None,
                   help="Resume training from an accelerate state dir "
                        "(e.g. ./smolvlm_ft3/accel_state) written by --save-every")
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
