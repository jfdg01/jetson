"""Arm D driver — Florence-2-large. Separate from run_arm.py because Florence is an
encoder-decoder that loads via AutoModelForCausalLM(trust_remote_code=True), has no
chat template, and speaks native `<loc_N>` tokens (see florence_loc.py + its config).

Reuses the shared crash-resistance machinery from grounding.train.trainer
(_atomic_save_adapter / _append_csv / _load_split) and the scoring harness
(grounding.eval.harness.evaluate) verbatim: the FlorenceBackend below generates loc
tokens, parses them to a [0,100] box via florence_loc, and returns the box as the
terse-int string `"x1 y1 x2 y2"` — so contract.parse_bbox/iou score it identically to
every other arm (format-agnostic IoU@0.25, the RQ's comparison axis).

Stages mirror run_arm: train (lr sweep, per-epoch in-loop eval, DONE sentinel resume)
then eval (whole-frame re-score of the best merged checkpoint).

Usage:
  .venv-ft/bin/python experiments/2026-06-30-vlm-backbone-bakeoff/run_florence.py --arm florence2-large --dry-run
  .venv-ft/bin/python experiments/2026-06-30-vlm-backbone-bakeoff/run_florence.py --arm florence2-large --stage all
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))   # repo root, so `grounding` + florence_loc import
sys.path.insert(0, str(HERE))

import florence_loc  # noqa: E402  (sibling module: contract <-> <loc_N> bridge)
from grounding.eval.harness import evaluate  # noqa: E402
from grounding.train.trainer import _append_csv, _atomic_save_adapter, _load_split  # noqa: E402

import transformers  # noqa: E402
transformers.logging.set_verbosity_error()

LR_SWEEP = (1e-4, 2e-4, 4e-4)
FLORENCE_MAX_NEW_TOKENS = 64   # loc answer = phrase tokens + 4 <loc_N>; terse cap is too tight


def load_arm_config(arm: str):
    path = HERE / "configs" / f"{arm}.py"
    if not path.exists():
        raise SystemExit(f"no config for arm {arm!r}: {path} missing")
    spec = importlib.util.spec_from_file_location(f"arm_{arm}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.config


# ── Florence collate + eval backend ──────────────────────────────────────────

def _resize(img, image_size):
    from grounding.eval.backends import _resize_keep_aspect
    return _resize_keep_aspect(img, image_size)


class _FlorenceDataset:
    """GroundingSample -> (PIL image, referring caption, [0,100] bbox)."""

    def __init__(self, samples, image_size):
        self.samples = list(samples)
        self.image_size = image_size

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        from PIL import Image
        s = self.samples[idx]
        img = _resize(Image.open(s.image_path).convert("RGB"), self.image_size)
        return {"image": img, "caption": s.caption, "bbox": s.bbox}


def _florence_collate(batch, processor, dtype=None):
    """Task-token+caption input, `caption<loc_...>` decoder-label target.

    Florence phrase grounding: input text = TASK + referring expression; the answer
    repeats the phrase followed by its loc tokens. Labels are the tokenized answer
    with pad masked to -100 (Florence's forward builds the decoder shift itself).
    """
    prompts = [florence_loc.TASK + b["caption"] for b in batch]
    images = [b["image"] for b in batch]
    targets = [florence_loc.render_target(b["caption"], b["bbox"]) for b in batch]

    inputs = processor(text=prompts, images=images, return_tensors="pt", padding=True)
    # Florence's remote code doesn't cast pixel_values to the weight dtype (Qwen did
    # internally); with bf16 weights the DaViT conv gets float32 input and errors.
    if dtype is not None:
        inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
    labels = processor.tokenizer(
        targets, return_tensors="pt", padding=True, return_token_type_ids=False,
    ).input_ids
    labels[labels == processor.tokenizer.pad_token_id] = -100
    inputs["labels"] = labels
    return inputs


class FlorenceBackend:
    """harness.Backend: generate loc tokens -> [0,100] box -> terse-int string.

    Returning `"x1 y1 x2 y2"` lets grounding.eval.harness.evaluate score Florence
    with the same contract.parse_bbox/iou path as the other arms. Unparsed -> "".
    """

    name = "hf"

    def __init__(self, model, processor, *, device, max_side):
        self.model = model
        self.processor = processor
        self.device = device
        self.max_side = max_side

    def generate(self, image_path: str, caption: str) -> str:
        import torch
        from PIL import Image
        img = _resize(Image.open(image_path).convert("RGB"), self.max_side)
        inputs = self.processor(
            text=[florence_loc.TASK + caption], images=[img], return_tensors="pt",
        ).to(self.device)
        inputs["pixel_values"] = inputs["pixel_values"].to(self.model.dtype)
        with torch.no_grad():
            # use_cache=False: Florence's remote prepare_inputs_for_generation indexes the
            # legacy tuple KV-cache (past_key_values[0][0].shape) and AttributeErrors on the
            # Cache API transformers 4.57 passes. Uncached decode of <=64 tokens on a ~300M
            # decoder is a non-cost; caught by the CPU generate smoke, 2026-07-02.
            gen = self.model.generate(
                input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                max_new_tokens=FLORENCE_MAX_NEW_TOKENS, num_beams=1, do_sample=False,
                use_cache=False,
            )
        text = self.processor.batch_decode(gen, skip_special_tokens=False)[0]
        box = florence_loc.parse_bbox(self.processor, text)
        if box is None:
            return ""
        x1, y1, x2, y2 = (int(round(v)) for v in box)
        return f"{x1} {y1} {x2} {y2}"


# ── LoRA scoping: language model only (keep DaViT vision tower frozen) ────────

def _lm_lora_targets(model, suffixes):
    """Full module names of LM Linear layers to adapt.

    DaViT's MLP also uses fc1/fc2, so a bare suffix list would leak LoRA into the
    vision tower and break freeze_vision. Scope to the language_model subtree by
    matching full names — keeps the 'vision frozen' claim honest.
    """
    import torch.nn as nn
    want = set(suffixes)
    return [n for n, m in model.named_modules()
            if isinstance(m, nn.Linear) and "language_model" in n
            and n.split(".")[-1] in want]


# ── train ─────────────────────────────────────────────────────────────────────

def train(config, *, dry_run: bool = False) -> str:
    import torch
    from accelerate import Accelerator
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForCausalLM, AutoProcessor

    from grounding import manifest

    accelerator = Accelerator(gradient_accumulation_steps=config.grad_accum)
    device = accelerator.device
    eff_batch = config.batch_size * config.grad_accum
    print(f"[florence] device={device}  effective_batch={eff_batch}  "
          f"model={config.model_id}  res={config.image_size}", flush=True)

    processor = AutoProcessor.from_pretrained(config.model_id, trust_remote_code=True)
    torch_dtype = getattr(torch, {"bf16": "bfloat16", "fp16": "float16"}.get(
        config.precision, config.precision))
    # attn_implementation="eager": Florence's remote modeling file predates transformers'
    # sdpa-dispatch check (no `_supports_sdpa`), so the default sdpa path AttributeErrors.
    # eager is correct (just slower) — fine for FT accuracy; Jetson latency is a separate path.
    model = AutoModelForCausalLM.from_pretrained(
        config.model_id, torch_dtype=torch_dtype, trust_remote_code=True, device_map=None,
        attn_implementation="eager",
    )

    targets = _lm_lora_targets(model, config.lora.target_modules)
    if not targets:
        raise SystemExit("[florence] no language_model LoRA targets matched — check module names")
    lora_cfg = LoraConfig(
        r=config.lora.r, lora_alpha=config.lora.alpha, target_modules=targets,
        lora_dropout=config.lora.dropout, bias=config.lora.bias, task_type=TaskType.CAUSAL_LM,
    )

    out_dir = Path(config.output_dir)
    done_epochs = sorted(int(p.name[5:]) for p in out_dir.glob("epoch*")
                         if p.name[5:].isdigit()) if out_dir.exists() else []
    resume_epoch = done_epochs[-1] if done_epochs else 0
    if resume_epoch:
        adapter = out_dir / f"epoch{resume_epoch}"
        print(f"[florence] RESUME: epoch{resume_epoch} -> continuing from {resume_epoch + 1}", flush=True)
        model = PeftModel.from_pretrained(model, adapter, is_trainable=True)
    else:
        model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    print(f"[florence] loading data: {config.train_split} / {config.val_split}", flush=True)
    train_samples = _load_split(config.train_split, largest_box_aug=config.largest_box_aug, max_samples=0)
    val_samples = _load_split(config.val_split, largest_box_aug=config.largest_box_aug, max_samples=0)
    print(f"[florence] {len(train_samples)} train / {len(val_samples)} val", flush=True)

    train_ds = _FlorenceDataset(train_samples, config.image_size)

    def collate(b):
        return _florence_collate(b, processor, dtype=torch_dtype)

    if dry_run:
        print("[dry-run] 1 real batch + forward...", flush=True)
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
        filter(lambda p: p.requires_grad, model.parameters()), lr=config.lr, weight_decay=0.01)
    remaining = config.epochs - resume_epoch
    total_steps = max(1, len(train_loader) * remaining // config.grad_accum)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)
    model, optimizer, train_loader, scheduler = accelerator.prepare(
        model, optimizer, train_loader, scheduler)

    out_dir.mkdir(parents=True, exist_ok=True)
    loss_csv, iou_csv = out_dir / "train_loss.csv", out_dir / "eval_iou.csv"
    _append_csv(loss_csv, None, ["epoch", "global_step", "loss", "lr", "elapsed_s"])
    _append_csv(iou_csv, None, ["epoch", "parse_rate", "iou@0.25", "mean_iou", "center_std"])
    eval_history = []
    save_every = config.save_every or 300

    t0, global_step = time.time(), 0
    for epoch in range(resume_epoch + 1, config.epochs + 1):
        model.train()
        epoch_loss, n_batches = 0.0, 0
        for step, batch in enumerate(train_loader):
            with accelerator.accumulate(model):
                out = model(**batch)
                accelerator.backward(out.loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step(); scheduler.step(); optimizer.zero_grad()
                global_step += 1
            epoch_loss += out.loss.item(); n_batches += 1
            if step % 50 == 0:
                el, lr_now = time.time() - t0, scheduler.get_last_lr()[0]
                print(f"  E{epoch} step {step}/{len(train_loader)}  loss={out.loss.item():.4f}  "
                      f"lr={lr_now:.2e}  {el:.0f}s", flush=True)
                _append_csv(loss_csv, [epoch, global_step, f"{out.loss.item():.6f}",
                                       f"{lr_now:.2e}", f"{el:.1f}"])
            if step > 0 and step % save_every == 0 and accelerator.is_main_process:
                _atomic_save_adapter(accelerator.unwrap_model(model), None, out_dir / "latest")

        print(f"[epoch {epoch}] mean_loss={epoch_loss / max(n_batches, 1):.4f}  "
              f"({time.time()-t0:.0f}s)", flush=True)

        if accelerator.is_main_process:
            em = accelerator.unwrap_model(model); em.eval()
            backend = FlorenceBackend(em, processor, device=device, max_side=config.image_size)
            report = evaluate(backend, val_samples, limit=config.eval_n,
                              progress_every=max(1, config.eval_n // 5))
            print(f"[eval E{epoch}] n={report.n}  parse={report.parse_rate:.1%}  "
                  f"iou@0.25={report.iou_gate_pass_rate:.1%}  mean_iou={report.mean_iou:.3f}  "
                  f"center_std={report.center_std:.1f}", flush=True)
            _append_csv(iou_csv, [epoch, f"{report.parse_rate:.4f}",
                                  f"{report.iou_gate_pass_rate:.4f}", f"{report.mean_iou:.4f}",
                                  f"{report.center_std:.2f}"])
            eval_history.append({"epoch": epoch, **asdict(report)})
            _atomic_save_adapter(em, processor, out_dir / f"epoch{epoch}")
            print(f"[florence] epoch {epoch} adapter -> {out_dir / f'epoch{epoch}'}", flush=True)

    merged_path = ""
    if accelerator.is_main_process:
        print("[florence] merging LoRA -> base...", flush=True)
        merged = accelerator.unwrap_model(model).merge_and_unload()
        merged.save_pretrained(out_dir); processor.save_pretrained(out_dir)
        (out_dir / "DONE").write_text("merged\n")
        merged_path = str(out_dir)
        m = manifest.capture("train", config, extra={"merged_checkpoint": merged_path})
        run_dir = manifest.write(m, runs_dir=out_dir, results={
            "eval_history": eval_history, "final": eval_history[-1] if eval_history else {},
            "train_n": len(train_samples), "val_n": len(val_samples),
            "epochs": config.epochs, "effective_batch": eff_batch})
        print(f"[florence] merged -> {merged_path}  manifest -> {run_dir}", flush=True)
    return merged_path


def evaluate_only(ckpt: str, config):
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(ckpt, trust_remote_code=True)
    torch_dtype = getattr(torch, {"bf16": "bfloat16", "fp16": "float16"}.get(config.precision, config.precision))
    model = AutoModelForCausalLM.from_pretrained(
        ckpt, torch_dtype=torch_dtype, trust_remote_code=True,
        attn_implementation="eager").to(device).eval()
    val_samples = _load_split(config.val_split, largest_box_aug=config.largest_box_aug, max_samples=0)
    backend = FlorenceBackend(model, processor, device=device, max_side=config.image_size)
    report = evaluate(backend, val_samples, limit=config.eval_n,
                      progress_every=max(1, config.eval_n // 5))
    print(f"[eval-only] {ckpt}  n={report.n}  parse={report.parse_rate:.1%}  "
          f"iou@0.25={report.iou_gate_pass_rate:.1%}  mean_iou={report.mean_iou:.3f}  "
          f"center_std={report.center_std:.1f}", flush=True)
    return report


def _best_epoch_iou(csv_path: Path) -> float:
    if not csv_path.exists():
        return 0.0
    import csv as _csv
    with open(csv_path) as f:
        rows = list(_csv.DictReader(f))
    return max((float(r["iou@0.25"]) for r in rows), default=0.0)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", default="florence2-large")
    p.add_argument("--stage", choices=["train", "eval", "all"], default="all")
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--eval-ckpt", default=None)
    args = p.parse_args()

    base = load_arm_config(args.arm)
    lrs = [args.lr] if args.lr is not None else list(LR_SWEEP)

    if args.dry_run:
        train(replace(base, lr=lrs[0]), dry_run=True)
        return

    best = None
    if args.stage in ("train", "all"):
        for lr in lrs:
            cfg = replace(base, lr=lr, output_dir=f"{base.output_dir}/lr{lr:g}")
            out = Path(cfg.output_dir)
            if (out / "DONE").exists():
                iou = _best_epoch_iou(out / "eval_iou.csv")
                print(f"[florence] lr={lr:g} already DONE ({out}); skip, IoU@0.25={iou:.1%}", flush=True)
                if best is None or iou > best[0]:
                    best = (iou, lr, str(out))
                continue
            print(f"\n===== florence lr={lr:g} -> {cfg.output_dir} =====", flush=True)
            merged = train(cfg)
            iou = _best_epoch_iou(Path(cfg.output_dir) / "eval_iou.csv")
            print(f"[florence] lr={lr:g} best in-loop IoU@0.25={iou:.1%}", flush=True)
            if best is None or iou > best[0]:
                best = (iou, lr, merged)
        print(f"\n[florence] sweep winner: lr={best[1]:g}  IoU@0.25={best[0]:.1%}  ckpt={best[2]}", flush=True)

    if args.stage in ("eval", "all"):
        ckpt = args.eval_ckpt or (best[2] if best else None)
        if not ckpt:
            raise SystemExit("eval stage needs --eval-ckpt")
        print(f"\n[florence] whole-frame accuracy re-score: {ckpt}", flush=True)
        evaluate_only(ckpt, base)


if __name__ == "__main__":
    main()
