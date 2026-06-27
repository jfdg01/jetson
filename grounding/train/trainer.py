"""Config-driven LoRA training loop with in-loop eval (Phase 3).

One loop for all v2 runs, driven entirely by `TrainConfig`. Uses `grounding.data`
for samples, the contract's `IMAGE_SIZE`/resolution lever for the input transform,
and `grounding.eval.harness` for the per-epoch contract metrics — so training-time
and eval-time scoring are *identical* (the same `contract.parse_bbox` →
`contract.iou` path the thesis reports everywhere). Gate (standing target): aerial
IoU@0.25 ≥ 20%, center_std non-degenerate, parse_rate ≥ 90%.

This replaces the per-stage script forks (`run_stage2/3/4_finetune.py`). The
training mechanics (LoRA targets, prompt-masked collate, AdamW + cosine, per-epoch
adapter save + final merge) are lifted verbatim-in-behaviour from the validated
Part-I `run_stage3_finetune.py` (Stage-3 RefCOCO PASS), with three deliberate
changes for v2:

  1. **Generic model class.** `AutoModelForImageTextToText` instead of the
     SmolVLM-specific class, so the Phase-0c spine (Qwen2-VL-2B) loads unchanged.
     Qwen2-VL's vision tower uses `qkv`/`proj` module names, so targeting the LLM
     `q_proj/.../down_proj` names naturally leaves the vision encoder frozen — the
     `freeze_vision` intent is satisfied by construction (LoRA freezes all base
     weights anyway).
  2. **Canonical data + scoring.** Samples come from `grounding.data.load_refdrone`
     (the Phase-1 well-posed subset) and in-loop eval goes through
     `grounding.eval.harness.evaluate`, not a private copy — no train/eval drift.
  3. **Simpler checkpointing.** Per-epoch adapter save + final merge + incremental
     loss CSV (the user authorised CPU/disk and "the simpler approach"); the
     legacy full accelerate-state mid-epoch resume is dropped.

Every run writes a `kind="train"` manifest (git SHA, lockfile sha, config, results)
under `experiments/runs/<id>/` via `grounding.manifest`.

Run:  source .venv-ft/bin/activate && python -m grounding.train.trainer [opts]
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Sequence

from grounding.train.config import TrainConfig


# ── data ────────────────────────────────────────────────────────────────────

def _load_split(spec: str, *, largest_box_aug: bool, max_samples: int):
    """Resolve a "<source>:<split>" spec to canonical `GroundingSample`s.

    Only the sources needed by v2 are wired in. RefDrone is the aerial Phase-3
    target; RefCOCO is available for a control / warm-start curriculum.
    """
    source, _, split = spec.partition(":")
    if not split:
        raise ValueError(f"split spec must be '<source>:<split>', got {spec!r}")
    if source == "refdrone":
        from grounding.data.refdrone import load_refdrone
        return load_refdrone(split, largest_box_aug=largest_box_aug,
                             max_samples=max_samples)
    if source == "refcoco":
        from grounding.data.refcoco import load_refcoco
        return load_refcoco(split, max_samples=max_samples)
    raise ValueError(f"unknown dataset source {source!r} in spec {spec!r}")


class _GroundingDataset:
    """Canonical `GroundingSample`s → (image, prompt, target_json) for the collate.

    Mirrors Part-I `RefCOCODataset.__getitem__`: load the image, downscale the long
    edge to `image_size` (metric-safe — boxes are normalized to the original image),
    format the verbatim `GROUNDING_PROMPT`, and render the target as the exact JSON
    the parser expects.
    """

    def __init__(self, samples: Sequence, image_size: int):
        self.samples = list(samples)
        self.image_size = image_size

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        from PIL import Image

        from grounding.contract import GROUNDING_PROMPT
        from grounding.eval.backends import _resize_keep_aspect

        s = self.samples[idx]
        img = Image.open(s.image_path).convert("RGB")
        img = _resize_keep_aspect(img, self.image_size)
        x1, y1, x2, y2 = s.bbox
        return {
            "image": img,
            "prompt": GROUNDING_PROMPT.format(target=s.caption),
            # terse contract: four space-separated ints (no JSON) — see contract.py
            "target_json": f"{x1} {y1} {x2} {y2}",
        }


def _collate_fn(batch, processor):
    """Tokenize a batch: image + prompt → input_ids/pixel_values/labels.

    Lifted from `run_stage3_finetune._collate_fn`: build the full (prompt+target)
    text and a prompt-only text, then mask the prompt span and padding with -100 so
    the loss supervises only the target JSON.
    """
    prompts = [b["prompt"] for b in batch]
    images = [b["image"] for b in batch]
    target_jsons = [b["target_json"] for b in batch]

    messages = [
        [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": p}]}]
        for p in prompts
    ]
    texts = [processor.apply_chat_template(m, add_generation_prompt=True) for m in messages]
    # Append the turn-end token so the model is SUPERVISED to stop (Qwen eos=<|im_end|>).
    # Without it, only formats whose closing char (}/]) the pretrained prior already ends
    # a turn on will stop; bare-int terse targets ramble to the token cap (2026-06-26 fix).
    eos = processor.tokenizer.eos_token
    full_texts = [t + tj + eos for t, tj in zip(texts, target_jsons)]

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


# ── in-loop eval backend ──────────────────────────────────────────────────────

class _LiveBackend:
    """Wrap the in-training model so `harness.evaluate` scores it identically to HF.

    The generate path is byte-for-byte the `eval.backends.HFBackend.generate` path
    (PIL load → long-edge resize → `GROUNDING_PROMPT` → chat template → greedy
    decode → decode new tokens only), but it runs against the *live* (unwrapped)
    PEFT model instead of a reloaded checkpoint, so per-epoch eval is free.
    """

    name = "hf"

    def __init__(self, model, processor, *, device, max_side: int):
        self.model = model
        self.processor = processor
        self.device = device
        self.max_side = max_side

    def generate(self, image_path: str, caption: str) -> str:
        import torch
        from PIL import Image

        from grounding.contract import GROUNDING_PROMPT, MAX_NEW_TOKENS
        from grounding.eval.backends import _resize_keep_aspect

        img = Image.open(image_path).convert("RGB")
        img = _resize_keep_aspect(img, self.max_side)
        prompt = GROUNDING_PROMPT.format(target=caption)
        messages = [{"role": "user", "content": [
            {"type": "image"}, {"type": "text", "text": prompt},
        ]}]
        text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=[text], images=[img], return_tensors="pt").to(self.device)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
        new_tokens = out[0, inputs["input_ids"].shape[1]:]
        return self.processor.decode(new_tokens, skip_special_tokens=True)


# ── training loop ──────────────────────────────────────────────────────────────

def train(config: TrainConfig, *, dry_run: bool = False) -> str:
    """Run a full LoRA fine-tune; return the merged-checkpoint output path."""
    import torch
    from accelerate import Accelerator
    from peft import LoraConfig, TaskType, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForImageTextToText, AutoProcessor

    from grounding import manifest
    from grounding.eval.harness import evaluate

    accelerator = Accelerator(gradient_accumulation_steps=config.grad_accum)
    device = accelerator.device
    eff_batch = config.batch_size * config.grad_accum
    print(f"[train] device={device}  effective_batch={eff_batch}  "
          f"model={config.model_id}  res={config.image_size}", flush=True)

    print("[train] loading processor + model...", flush=True)
    processor = AutoProcessor.from_pretrained(config.model_id)
    torch_dtype = getattr(torch, {"bf16": "bfloat16", "fp16": "float16"}.get(
        config.precision, config.precision))
    model = AutoModelForImageTextToText.from_pretrained(
        config.model_id, torch_dtype=torch_dtype, device_map=None,
    )

    # LoRA on the text backbone (attention + MLP). Targeting these LLM module names
    # leaves the vision tower (Qwen2-VL: qkv/proj) untouched, so freeze_vision holds.
    present = {n.split(".")[-1] for n, _ in model.named_modules()}
    for t in config.lora.target_modules:
        if t not in present:
            print(f"[train] WARNING: LoRA target '{t}' not found in model modules", flush=True)
    lora_cfg = LoraConfig(
        r=config.lora.r,
        lora_alpha=config.lora.alpha,
        target_modules=config.lora.target_modules,
        lora_dropout=config.lora.dropout,
        bias=config.lora.bias,
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # ── data ─────────────────────────────────────────────────────────────────
    print(f"[train] loading data: {config.train_split} / {config.val_split}", flush=True)
    train_samples = _load_split(config.train_split,
                                largest_box_aug=config.largest_box_aug, max_samples=0)
    val_samples = _load_split(config.val_split,
                              largest_box_aug=config.largest_box_aug, max_samples=0)
    print(f"[train] {len(train_samples)} train / {len(val_samples)} val samples", flush=True)

    train_ds = _GroundingDataset(train_samples, config.image_size)

    def collate(b):
        return _collate_fn(b, processor)

    if dry_run:
        print("[dry-run] building 1 real batch + 1 forward pass...", flush=True)
        batch = collate([train_ds[i] for i in range(min(config.batch_size, len(train_ds)))])
        model.to(device)
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.no_grad():
            out = model(**batch)
        print(f"[dry-run] loss={out.loss.item():.4f}  PASS", flush=True)
        return ""

    train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True,
                              collate_fn=collate, num_workers=0)

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=config.lr, weight_decay=0.01,
    )
    total_steps = max(1, len(train_loader) * config.epochs // config.grad_accum)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    model, optimizer, train_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, scheduler)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    loss_csv = output_dir / "train_loss.csv"
    iou_csv = output_dir / "eval_iou.csv"
    loss_rows = [["epoch", "global_step", "loss", "lr", "elapsed_s"]]
    iou_rows = [["epoch", "parse_rate", "iou@0.25", "mean_iou", "center_std"]]
    eval_history: List[dict] = []

    t0 = time.time()
    global_step = 0
    for epoch in range(1, config.epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for step, batch in enumerate(train_loader):
            with accelerator.accumulate(model):
                out = model(**batch)
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
            n_batches += 1
            if step % 50 == 0:
                elapsed = time.time() - t0
                lr_now = scheduler.get_last_lr()[0]
                print(f"  E{epoch} step {step}/{len(train_loader)}  "
                      f"loss={loss_val:.4f}  lr={lr_now:.2e}  {elapsed:.0f}s", flush=True)
                loss_rows.append([epoch, global_step, f"{loss_val:.6f}",
                                  f"{lr_now:.2e}", f"{elapsed:.1f}"])
                with open(loss_csv, "w", newline="") as f:
                    csv.writer(f).writerows(loss_rows)
            if config.save_every and step > 0 and (step + 1) % config.save_every == 0:
                if accelerator.is_main_process:
                    accelerator.unwrap_model(model).save_pretrained(output_dir / "latest")

        mean_loss = epoch_loss / max(n_batches, 1)
        print(f"[epoch {epoch}] mean_loss={mean_loss:.4f}  ({time.time()-t0:.0f}s)", flush=True)

        if accelerator.is_main_process:
            eval_model = accelerator.unwrap_model(model)
            eval_model.eval()
            backend = _LiveBackend(eval_model, processor, device=device,
                                   max_side=config.image_size)
            report = evaluate(backend, val_samples, limit=config.eval_n,
                              progress_every=max(1, config.eval_n // 5))
            print(f"[eval E{epoch}] n={report.n}  parse={report.parse_rate:.1%}  "
                  f"iou@0.25={report.iou_gate_pass_rate:.1%}  "
                  f"mean_iou={report.mean_iou:.3f}  "
                  f"center_std={report.center_std:.1f}", flush=True)
            iou_rows.append([epoch, f"{report.parse_rate:.4f}",
                             f"{report.iou_gate_pass_rate:.4f}", f"{report.mean_iou:.4f}",
                             f"{report.center_std:.2f}"])
            with open(iou_csv, "w", newline="") as f:
                csv.writer(f).writerows(iou_rows)
            eval_history.append({"epoch": epoch, **asdict(report)})

            ckpt = output_dir / f"epoch{epoch}"
            eval_model.save_pretrained(ckpt)
            processor.save_pretrained(ckpt)
            print(f"[train] epoch {epoch} adapter -> {ckpt}", flush=True)

    merged_path = ""
    if accelerator.is_main_process:
        print("[train] merging LoRA adapter into base weights...", flush=True)
        merged = accelerator.unwrap_model(model).merge_and_unload()
        merged.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)
        merged_path = str(output_dir)
        print(f"[train] merged checkpoint -> {merged_path}", flush=True)

        final = eval_history[-1] if eval_history else {}
        m = manifest.capture("train", config, extra={"merged_checkpoint": merged_path})
        run_dir = manifest.write(m, results={
            "eval_history": eval_history,
            "final": final,
            "train_n": len(train_samples),
            "val_n": len(val_samples),
            "epochs": config.epochs,
            "effective_batch": eff_batch,
        })
        print(f"[train] manifest -> {run_dir}", flush=True)

    return merged_path


def evaluate_only(checkpoint: str, config: TrainConfig):
    """Re-evaluate a merged checkpoint with the same harness used in-loop."""
    from grounding.eval.backends import HFBackend
    from grounding.eval.harness import evaluate

    val_samples = _load_split(config.val_split,
                              largest_box_aug=config.largest_box_aug, max_samples=0)
    backend = HFBackend(checkpoint, max_side=config.image_size)
    report = evaluate(backend, val_samples, limit=config.eval_n,
                      progress_every=max(1, config.eval_n // 5))
    print(f"[eval-only] {checkpoint}  n={report.n}  parse={report.parse_rate:.1%}  "
          f"iou@0.25={report.iou_gate_pass_rate:.1%}  mean_iou={report.mean_iou:.3f}  "
          f"center_std={report.center_std:.1f}", flush=True)
    return report


def _parse_args():
    import argparse

    c = TrainConfig()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-id", default=c.model_id)
    p.add_argument("--train-split", default=c.train_split)
    p.add_argument("--val-split", default=c.val_split)
    p.add_argument("--image-size", type=int, default=c.image_size,
                   help="input long-edge resize (Phase-2 chosen resolution)")
    p.add_argument("--largest-box-aug", action="store_true", default=c.largest_box_aug,
                   help="Phase-1 lever: expand budget to largest-box-per-caption")
    p.add_argument("--epochs", type=int, default=c.epochs)
    p.add_argument("--lr", type=float, default=c.lr)
    p.add_argument("--batch-size", type=int, default=c.batch_size)
    p.add_argument("--grad-accum", type=int, default=c.grad_accum)
    p.add_argument("--eval-n", type=int, default=c.eval_n)
    p.add_argument("--save-every", type=int, default=c.save_every)
    p.add_argument("--output-dir", default=c.output_dir)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--eval-only", metavar="CHECKPOINT", default=None)
    return p.parse_args()


def main():
    args = _parse_args()
    config = TrainConfig(
        model_id=args.model_id,
        train_split=args.train_split,
        val_split=args.val_split,
        image_size=args.image_size,
        largest_box_aug=args.largest_box_aug,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        eval_n=args.eval_n,
        save_every=args.save_every,
        output_dir=args.output_dir,
    )
    if args.eval_only:
        evaluate_only(args.eval_only, config)
    else:
        train(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
