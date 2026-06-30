"""
Stage 4 fine-tuning: RefCOCO→RefDrone curriculum for *aerial* grounding.

The thesis target domain is aerial / drone-view grounding on a Jetson Orin Nano.
The arc so far:

  * Stage 2 (FAILED, mode collapse): text-only LoRA directly on RefDrone. Root cause
    = ILL-POSED TARGET — RefDrone is mdetr-format, where each (image, caption) record
    maps to MANY boxes (mean 3.80). Stage 2 emitted each box as a separate sample with
    the same caption, so the marginal-mean box minimised the loss → collapse (IoU@0.25≈1%).
  * Stage 3 (PASS, but ground-level): corrected the objective on RefCOCO (well-posed:
    many-captions→one-box, large objects, 0–1000 coords). G2 IoU@0.25 = 82.5%. Proved the
    machinery + objective are sound — but RefCOCO is the WRONG domain (ground-level), and
    cross-domain aerial transfer measured at 2.0% (RQ-S3.4 floor).

Stage 4 = a CURRICULUM: init from the Stage 3 RefCOCO-merged weights (which already know
single-box grounding) and fine-tune on RefDrone — but only on the WELL-POSED SUBSET (the
captions that have exactly one box), the exact structural mirror of the Stage 3 fix. This
removes the ill-posed target that sank Stage 2 while staying in the aerial domain.

What's reused verbatim from run_stage3_finetune.py (the validated trainer):
  _resize_keep_aspect, _normalize_bbox, _collate_fn (label-masking), _parse_bbox, _iou,
  evaluate() (incl. the center_std mode-collapse sentinel), the resumable train() loop,
  the LoRA config (r=16, α=32, attention+MLP, vision frozen), GROUNDING_PROMPT (must stay
  identical to the probe + Phase C), COORD_SCALE=1000, IMAGE_SIZE=512, SEED=42.

What's new vs Stage 3:
  1. RefDroneWellPosedDataset — loads the mdetr JSON, groups annotations by image_id,
     keeps only captions with exactly ONE non-empty box, converts COCO xywh → xyxy.
  2. Curriculum init: --init-from ./smolvlm_ft3 (the Stage 3 merged checkpoint) as the
     base; a fresh LoRA adapter is trained on top. (Falls back to MODEL_ID for a
     from-scratch control arm.)
  3. Hyperparameters tuned for the small, well-initialised set: --epochs 3, --lr 1e-4
     (lower than Stage 3's 2e-4, so the curriculum init isn't clobbered).

Uses:  .venv-ft (torch 2.6.0+cu124, transformers 4.57.6, peft 0.19, datasets 5.0)
GPU:   RTX 3090 24 GB (local)
Run:   source .venv-ft/bin/activate && \
       python runners/run_stage4_finetune.py --init-from ./smolvlm_ft3 --epochs 3 --lr 1e-4

Key flags:
  --refdrone-json PATH  mdetr train JSON (default: auto-resolve from HF cache)
  --image-root PATH     VisDrone images root (default: data/VisDrone2019-DET/images)
  --init-from PATH      Curriculum base checkpoint (default: ./smolvlm_ft3; falls back to
                        base MODEL_ID if absent)
  --output-dir PATH     Where to save the merged checkpoint (default: ./smolvlm_ft4)
  --epochs INT          Training epochs (default: 3)
  --lr FLOAT            Learning rate (default: 1e-4)
  --max-samples INT     Cap training samples (default: 0 = all ~4101 well-posed)
  --dry-run             Load model + 1 forward pass, exit (no training)
  --eval-only PATH      Skip training; evaluate merged checkpoint at PATH vs val set
"""

import argparse
import csv
import glob
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
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nActivate: source .venv-ft/bin/activate")

# Reuse the validated Stage 3 scaffold verbatim (same dir).
sys.path.insert(0, str(Path(__file__).parent))
from run_stage3_finetune import (  # noqa: E402
    MODEL_ID, MAX_NEW_TOKENS, IMAGE_SIZE, COORD_SCALE, SEED,
    LORA_TARGET_MODULES, GROUNDING_PROMPT,
    _resize_keep_aspect, _normalize_bbox, _collate_fn,
    _parse_bbox, _iou, evaluate,
)

# ── Stage 4 specifics ──────────────────────────────────────────────────────────
DEFAULT_INIT_FROM = "./smolvlm_ft3"     # Stage 3 RefCOCO merged checkpoint (curriculum base)
DEFAULT_OUTPUT    = "./smolvlm_ft4"
STAGE4_RAW        = Path("experiments/stage4-refdrone-curriculum/raw")
HF_REFDRONE_GLOB  = ("/home/gara/.cache/huggingface/hub/"
                     "datasets--sunzc-sunny--RefDrone/snapshots/*/RefDrone_{split}_mdetr.json")
# mdetr split name → VisDrone image subdirectory
SPLIT_TO_IMGDIR = {"train": "train", "val": "val", "test": "test"}


def _resolve_refdrone_json(split: str, override: str = "") -> Path:
    if override:
        p = Path(override)
        if not p.exists():
            sys.exit(f"ERROR: --refdrone-json {p} does not exist")
        return p
    matches = glob.glob(HF_REFDRONE_GLOB.format(split=split))
    if not matches:
        sys.exit(f"ERROR: could not auto-resolve RefDrone {split} mdetr JSON in HF cache; "
                 f"pass --refdrone-json")
    return Path(sorted(matches)[0])


# ── dataset ─────────────────────────────────────────────────────────────────────

class RefDroneWellPosedDataset(Dataset):
    """
    RefDrone aerial referring-expression grounding, WELL-POSED SUBSET ONLY.

    The mdetr JSON has:
      images[]      : one record per referring expression — file_name, width, height,
                      caption, id.
      annotations[] : link by annotation.image_id == images[].id; carry bbox (COCO
                      xywh) and an `empty` flag (bbox==[0,0,0,0] for negatives).

    We group annotations by image_id and KEEP ONLY captions with exactly one non-empty
    box (the structural mirror of the Stage 3 well-posed fix: one caption → one box,
    deterministic). Multi-box captions (the Stage 2 ill-posed killer) and pure-empty /
    negative captions are dropped. The kept box is converted COCO xywh → xyxy and then
    normalized to 0–1000 ints, so the reused collate/eval code is untouched.

    Images live at <image_root>/<split_dir>/<file_name>.
    """

    def __init__(self, split: str, refdrone_json: Path, image_root: Path, processor,
                 max_samples: int = 0, image_size: int = IMAGE_SIZE, seed: int = SEED):
        self.processor  = processor
        self.image_size = image_size
        self.img_dir    = Path(image_root) / SPLIT_TO_IMGDIR[split]

        print(f"[dataset] loading RefDrone '{split}' mdetr from {refdrone_json}")
        data = json.loads(Path(refdrone_json).read_text())

        # group annotations by image_id
        anns_by_img = {}
        for a in data["annotations"]:
            anns_by_img.setdefault(a["image_id"], []).append(a)

        items = []
        n_multi = n_empty = n_missing = 0
        seen_missing = set()
        for img in data["images"]:
            anns = anns_by_img.get(img["id"], [])
            real = [a for a in anns if not a.get("empty", False)
                    and a["bbox"] != [0, 0, 0, 0]]
            if len(real) == 0:
                n_empty += 1
                continue
            if len(real) > 1:
                n_multi += 1                 # the Stage 2 ill-posed case — dropped
                continue
            cap = (img.get("caption") or "").strip()
            if not cap:
                n_empty += 1
                continue
            img_path = self.img_dir / img["file_name"]
            if not img_path.exists():
                n_missing += 1
                if len(seen_missing) < 5:
                    seen_missing.add(img["file_name"])
                continue
            x, y, w, h = real[0]["bbox"]      # COCO xywh
            bbox_xyxy = [x, y, x + w, y + h]
            nbbox = _normalize_bbox(bbox_xyxy, img["width"], img["height"])
            items.append({"img_path": img_path, "sentence": cap, "nbbox": nbbox})

        print(f"[dataset] {len(items)} well-posed (one-box) captions kept "
              f"({n_multi} multi-box dropped, {n_empty} empty/negative dropped, "
              f"{n_missing} image-not-found)")
        if seen_missing:
            print(f"[dataset] sample missing files: {sorted(seen_missing)}")

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
        return {"image": img, "prompt": prompt, "target_json": target_json}


# ── training loop ─────────────────────────────────────────────────────────────

def _load_base(init_from: str):
    """Load the curriculum base: --init-from checkpoint if present, else base MODEL_ID."""
    base = init_from
    if init_from and not Path(init_from).exists():
        print(f"[train] WARNING: --init-from {init_from} not found; "
              f"falling back to base {MODEL_ID} (from-scratch control)")
        base = MODEL_ID
    elif init_from:
        print(f"[train] curriculum init from {init_from}")
    else:
        base = MODEL_ID
        print(f"[train] from-scratch init from base {MODEL_ID}")
    model = SmolVLMForConditionalGeneration.from_pretrained(
        base, torch_dtype=torch.bfloat16, device_map=None,
    )
    return model


def train(args):
    accelerator = Accelerator(gradient_accumulation_steps=args.grad_accum)
    device = accelerator.device
    print(f"[train] device: {device} | effective batch: {args.batch * args.grad_accum}")

    print("[train] loading processor...")
    # processor always from base MODEL_ID (merged-checkpoint processor save has the
    # extra_special_tokens-as-list bug; the tokenizer/image-processor are identical)
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    print("[train] loading model...")
    model = _load_base(args.init_from)

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

    refdrone_train = _resolve_refdrone_json("train", args.refdrone_json)
    refdrone_val   = _resolve_refdrone_json("val", args.refdrone_val_json)

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
        print(f"[dry-run] resolved train JSON: {refdrone_train}")
        print(f"[dry-run] resolved val   JSON: {refdrone_val}")
        return

    # ── datasets ─────────────────────────────────────────────────────────────
    image_root = Path(args.image_root)
    train_ds = RefDroneWellPosedDataset("train", refdrone_train, image_root, processor,
                                        max_samples=args.max_samples)
    val_ds   = RefDroneWellPosedDataset("val", refdrone_val, image_root, processor,
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
    scheduler   = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(total_steps, 1))

    model, optimizer, train_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, scheduler
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    loss_csv_path = STAGE4_RAW / "train_loss.csv"
    iou_csv_path  = STAGE4_RAW / "eval_iou.csv"
    loss_csv_path.parent.mkdir(parents=True, exist_ok=True)

    loss_rows = [["epoch", "step", "loss", "lr", "elapsed_s"]]
    iou_rows  = [["epoch", "parse_rate", "iou@0.25", "mean_iou", "center_std"]]

    state_dir = output_dir / "accel_state"   # full accelerate state (model+opt+sched)
    meta_path = output_dir / "resume_meta.json"

    def save_checkpoint(epoch, batch_in_epoch, global_step, elapsed):
        """Persist a resumable mid-run checkpoint: accelerate state + adapter + meta."""
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
    resume_skip = 0
    elapsed_offset = 0.0
    global_step = 0
    if args.resume_from:
        print(f"[resume] loading accelerate state from {args.resume_from}", flush=True)
        accelerator.load_state(args.resume_from)
        rmeta = json.loads((Path(args.resume_from).parent / "resume_meta.json").read_text())
        start_epoch    = rmeta["epoch"]
        resume_skip    = rmeta["batch_in_epoch"]
        global_step    = rmeta["global_step"]
        elapsed_offset = rmeta["elapsed_s"]
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
                with open(loss_csv_path, "w", newline="") as f:
                    csv.writer(f).writerows(loss_rows)

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
    try:
        processor = AutoProcessor.from_pretrained(args.eval_only)
    except Exception as e:
        print(f"[eval-only] processor load from checkpoint failed ({e}); using base")
        processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = SmolVLMForConditionalGeneration.from_pretrained(
        args.eval_only, torch_dtype=torch.bfloat16
    ).to(device)

    refdrone_val = _resolve_refdrone_json("val", args.refdrone_val_json)
    val_ds = RefDroneWellPosedDataset("val", refdrone_val, Path(args.image_root),
                                      processor, max_samples=200)
    metrics = evaluate(model, processor, val_ds, device)
    print(f"[eval-only] n={metrics['n']}  parse_rate={metrics['parse_rate']:.1%}  "
          f"iou@0.25={metrics['iou@0.25']:.1%}  mean_iou={metrics['mean_iou']:.3f}  "
          f"center_std={metrics['center_std']:.1f}")
    for gt, resp in metrics["samples"]:
        print(f"    gt={gt}  pred={resp}")


# ── main ──────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--refdrone-json", default="",
                   help="mdetr train JSON (default: auto-resolve from HF cache)")
    p.add_argument("--refdrone-val-json", default="",
                   help="mdetr val JSON (default: auto-resolve from HF cache)")
    p.add_argument("--image-root", default="data/VisDrone2019-DET/images",
                   help="VisDrone images root containing train/ and val/")
    p.add_argument("--init-from", default=DEFAULT_INIT_FROM,
                   help="Curriculum base checkpoint (default: ./smolvlm_ft3; falls back "
                        "to base MODEL_ID if absent)")
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT,
                   help="Directory to save the merged fine-tuned checkpoint")
    p.add_argument("--epochs",     type=int,   default=3)
    p.add_argument("--batch",      type=int,   default=2)
    p.add_argument("--grad-accum", type=int,   default=8)
    p.add_argument("--lr",         type=float, default=1e-4)
    p.add_argument("--lora-rank",  type=int,   default=16)
    p.add_argument("--max-samples",type=int,   default=0,
                   help="Cap training samples (default 0 = all ~4101 well-posed)")
    p.add_argument("--save-every", type=int,   default=500,
                   help="Save a resumable mid-epoch checkpoint every N batches "
                        "(default 500; 0 = epoch-end only)")
    p.add_argument("--resume-from", metavar="STATE_DIR", default=None,
                   help="Resume training from an accelerate state dir written by --save-every")
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
