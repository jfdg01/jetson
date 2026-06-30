"""
Stage 3 G3 / RQ-S3.3 — GGUF Q8_0 export-parity check (HF bf16 vs GGUF Q8_0).

Pre-registration (experiments/stage3-refcoco-finetune/README.md): "Does the grounding
skill survive GGUF Q8_0 export?  ΔIoU@0.25 ≤ 5pp HF vs GGUF Q8_0."

Why this script exists
----------------------
The export-pipeline Phase A probe (run_grounding_probe.py) only runs on *aerial*
RefDrone/VisDrone, where the fine-tuned model sits at the ~2 % IoU noise floor
(cross-domain collapse, see G4). At that floor a 5 pp parity gate is statistically
meaningless. G3 must be measured *in-domain*, on RefCOCO val, where the skill is
real (HF = 82.5 %), so that the only variable between the two arms is the weight
representation: HF bf16 (transformers) vs GGUF Q8_0 (llama.cpp on the Jetson).

Method — paired, identical samples
----------------------------------
We build ONE RefCOCO validation subset (the exact deterministic seed-42 shuffle the
trainer's evaluate() uses, so dataset[0..N-1] are the same items) and push every
sample through BOTH arms:

  * HF arm   : the merged checkpoint (smolvlm_ft3) in bf16, greedy decode, locally
               — reuses run_stage3_finetune.evaluate() verbatim.
  * GGUF arm : the Q8_0 GGUF on the Jetson via llama-server (-ngl 99), querying the
               same image (resized identically) + the same unified prompt.

Both arms use the SAME parser (_parse_bbox) and the SAME IoU in normalized 0–1000
space against the SAME ground-truth box, so ΔIoU@0.25 is apples-to-apples. The only
residual non-isolated difference is each runtime's own image preprocessing (the
SmolVLM processor vs llama.cpp's clip) — which is itself part of "does the exported
artifact still work", so the gate is a *behavioural* parity check, not bit-exactness.

Usage:
  source .venv-ft/bin/activate
  python runners/run_stage3_g3_parity.py [--n-sample 100] [--dry-run]
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

# GGUF/Jetson server helpers come from the (stdlib-only) probe module.
sys.path.insert(0, str(Path(__file__).parent))
import run_grounding_probe as probe  # noqa: E402
from run_grounding_probe import (  # noqa: E402
    ModelSpec, start_server, stop_server,
    _build_payload, _post, _response_text, _img_b64, _img_mime,
)

# Dataset + metric helpers come from the trainer (pulls in torch/transformers).
import run_stage3_finetune as ft  # noqa: E402
from run_stage3_finetune import RefCOCODataset, _parse_bbox, _iou, evaluate  # noqa: E402

JETSON_GGUF_PATH   = "/home/jfdg/models/smolvlm_ft3_q8_0.gguf"
JETSON_MMPROJ_PATH = "/home/jfdg/models/mmproj-SmolVLM-500M-Instruct-f16.gguf"
GATE_PP            = 5.0   # ΔIoU@0.25 ≤ 5 percentage points = PASS
STAGE3_RAW = Path(__file__).parent.parent / "experiments/stage3-refcoco-finetune/raw"


def gguf_arm(val_ds, n: int, dry_run: bool, gguf_path: str = JETSON_GGUF_PATH,
             quant: str = "Q8_0") -> dict:
    """Push the same N val items through the Jetson GGUF server; return metrics + rows."""
    # Point the probe's server helper at the already-on-device fine-tuned GGUF.
    spec = ModelSpec(
        unit_id="G3", name="SmolVLM-500M-ft3", params_b=0.50, quant=quant,
        gguf_file=Path(gguf_path).name,
        mmproj_file="mmproj-SmolVLM-500M-Instruct-f16.gguf",
        hf_repo_text="", hf_repo_mmproj="",
        expected_mb_text=0, expected_mb_mmproj=0, is_gated=False,
    )
    pf, load_failed, load_s = start_server(spec, gguf_path, JETSON_MMPROJ_PATH, dry_run)
    if not dry_run and load_failed:
        stop_server(pf)
        sys.exit("ERROR: Jetson llama-server did not become healthy (likely OOM).")

    rows = []  # (idx, gt, pred, iou)
    parsed = iou25 = 0
    total_iou = 0.0
    try:
        for i in range(n):
            item = val_ds[i]
            gt = json.loads(item["target_json"])["bbox"]
            prompt = item["prompt"]
            # Save the identically-resized image (PNG = lossless) so the GGUF arm
            # sees the same pixels the HF arm saw, then b64 it to llama-server.
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                item["image"].save(tmp.name)
                if dry_run:
                    print(f"  [dry-run] would send sample {i}: {prompt[:70]}…")
                    continue
                payload = _build_payload(
                    _img_b64(Path(tmp.name)), _img_mime(Path(tmp.name)),
                    prompt, max_tokens=64,
                )
                raw = _post(payload, timeout=120)
            text = _response_text(raw)
            pred = _parse_bbox(text)
            iou_v = _iou(pred, gt) if pred is not None else 0.0
            if pred is not None:
                parsed += 1
                total_iou += iou_v
                if iou_v >= 0.25:
                    iou25 += 1
            rows.append((i, gt, pred, iou_v))
            if i % 10 == 0 or i == n - 1:
                print(f"  {i+1}/{n}  gt={gt} pred={pred} iou={iou_v:.3f}")
    finally:
        stop_server(pf)

    if dry_run:
        return {"n": n, "parse_rate": 1.0, "iou@0.25": 0.0, "mean_iou": 0.0, "rows": []}
    return {
        "n": n,
        "parse_rate": parsed / n,
        "iou@0.25": iou25 / n,
        "mean_iou": total_iou / max(parsed, 1),
        "rows": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ft-dir", default="./smolvlm_ft3")
    p.add_argument("--coco-root", default="data/coco")
    p.add_argument("--n-sample", type=int, default=100)
    p.add_argument("--gguf-path", default=JETSON_GGUF_PATH,
                   help="On-device GGUF to query (default = Q8_0 export)")
    p.add_argument("--quant", default="Q8_0", help="Quant label for reporting")
    p.add_argument("--tag", default="", help="Suffix for output artifacts (e.g. 'f16')")
    p.add_argument("--skip-hf", action="store_true",
                   help="Skip the HF bf16 arm; reuse a prior run's HF numbers from g3_parity.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    import torch
    from transformers import SmolVLMForConditionalGeneration, AutoProcessor

    ft_dir = Path(args.ft_dir)
    if not ft_dir.exists():
        sys.exit(f"ERROR: merged checkpoint not found at {ft_dir}")

    # One shared val subset — identical deterministic items for both arms.
    try:
        processor = AutoProcessor.from_pretrained(str(ft_dir))
    except Exception:
        processor = AutoProcessor.from_pretrained(ft.MODEL_ID)
    val_ds = RefCOCODataset("validation", Path(args.coco_root), processor,
                            max_samples=max(200, args.n_sample))
    n = min(args.n_sample, len(val_ds))
    print(f"[g3] paired parity on {n} RefCOCO val samples (seed {ft.SEED})\n")

    # ── GGUF arm first (Jetson) ──
    print(f"=== GGUF {args.quant} arm (Jetson llama-server) === [{args.gguf_path}]")
    gguf = gguf_arm(val_ds, n, args.dry_run, gguf_path=args.gguf_path, quant=args.quant)

    # ── HF arm (local bf16) ──
    print("\n=== HF bf16 arm (local) ===")
    if args.dry_run:
        hf = {"n": n, "parse_rate": 1.0, "iou@0.25": 0.0, "mean_iou": 0.0}
    elif args.skip_hf:
        prior = json.loads((STAGE3_RAW / "g3_parity.json").read_text())
        hf = {"parse_rate": prior["hf"]["parse_rate"], "iou@0.25": prior["hf"]["iou@0.25"],
              "mean_iou": prior["hf"]["mean_iou"]}
        print(f"  HF (reused from g3_parity.json): iou@0.25={hf['iou@0.25']:.1%} "
              f"mean_iou={hf['mean_iou']:.3f}")
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SmolVLMForConditionalGeneration.from_pretrained(
            str(ft_dir), torch_dtype=torch.bfloat16).to(device).eval()
        hf = evaluate(model, processor, val_ds, device, n_samples=n)
        print(f"  HF: parse={hf['parse_rate']:.1%} iou@0.25={hf['iou@0.25']:.1%} "
              f"mean_iou={hf['mean_iou']:.3f}")

    if args.dry_run:
        print("\n[dry-run] complete.")
        return

    # ── verdict ──
    delta_pp = abs(hf["iou@0.25"] - gguf["iou@0.25"]) * 100
    verdict = "PASS" if delta_pp <= GATE_PP else "FAIL"
    print("\n" + "=" * 60)
    print(f"  G3 / RQ-S3.3 export parity (n={n}, RefCOCO val)")
    print(f"  HF bf16   IoU@0.25 = {hf['iou@0.25']:.1%}  parse={hf['parse_rate']:.1%}  mean_iou={hf['mean_iou']:.3f}")
    print(f"  GGUF {args.quant} IoU@0.25 = {gguf['iou@0.25']:.1%}  parse={gguf['parse_rate']:.1%}  mean_iou={gguf['mean_iou']:.3f}")
    print(f"  ΔIoU@0.25 = {delta_pp:.1f} pp   (gate ≤ {GATE_PP:.0f} pp)  →  {verdict}")
    print("=" * 60)

    # ── raw artifacts ──
    STAGE3_RAW.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    summary = {
        "date": time.strftime("%Y-%m-%d"),
        "n": n, "seed": ft.SEED, "gate_pp": GATE_PP, "quant": args.quant,
        "hf": {k: hf[k] for k in ("parse_rate", "iou@0.25", "mean_iou")},
        "gguf": {k: gguf[k] for k in ("parse_rate", "iou@0.25", "mean_iou")},
        "delta_iou25_pp": delta_pp, "verdict": verdict,
    }
    (STAGE3_RAW / f"g3_parity{suffix}.json").write_text(json.dumps(summary, indent=2))
    with (STAGE3_RAW / f"g3_parity_gguf{suffix}.jsonl").open("w") as f:
        for idx, gt, pred, iou_v in gguf["rows"]:
            f.write(json.dumps({"i": idx, "gt": gt, "pred": pred, "iou": iou_v}) + "\n")
    print(f"\nSaved: {STAGE3_RAW/('g3_parity'+suffix+'.json')}")


if __name__ == "__main__":
    main()
