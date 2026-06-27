"""Phase-0 eval runner — score one backend over a RefCOCO subset, write a manifest.

This is the thin CLI over the Phase-0 spine (`backends` + `harness`) used for the
backend-fidelity work. Every invocation emits a per-run manifest under `experiments/runs/<id>/`
(git SHA, pinned llama.cpp commit, lock sha256, config) plus the contract metrics,
so any number is traceable to exact code + deps + data.

The first use is the harness *self-check*: run the HF backend on the Stage-3 merged
checkpoint over the seed-42 RefCOCO val subset and confirm it reproduces the Part-I
in-domain number (~82.5% IoU@0.25) — proving the v2 contract path matches the
validated Part-I path before any cross-backend comparison.

Usage:
  source .venv-ft/bin/activate
  python -m grounding.eval.run --backend hf --model ./smolvlm_ft3 --n 100
"""

from __future__ import annotations

import argparse
from dataclasses import asdict

from grounding import manifest
from grounding.contract import IMAGE_SIZE
from grounding.eval.harness import evaluate


def _load_samples(args):
    if args.dataset == "refcoco":
        from grounding.data.refcoco import load_refcoco
        return load_refcoco(args.split, coco_root=args.coco_root, max_samples=args.n)
    if args.dataset == "refdrone":
        from grounding.data.refdrone import load_refdrone
        return load_refdrone(args.split, max_samples=args.n)
    raise SystemExit(f"unknown dataset '{args.dataset}'")


def _build_backend(args):
    if args.backend == "hf":
        from grounding.eval.backends import HFBackend
        return HFBackend(args.model, device=args.device, dtype=args.dtype,
                         max_side=args.max_side)
    if args.backend == "gguf":
        from grounding.eval.backends import GGUFBackend
        if not args.mmproj:
            raise SystemExit("--mmproj is required for the gguf backend")
        return GGUFBackend(args.model, args.mmproj, n_gpu_layers=args.ngl,
                           max_side=args.max_side)
    if args.backend == "jetson":
        from grounding.eval.backends import JetsonBackend
        if not args.mmproj:
            raise SystemExit("--mmproj (remote path) is required for the jetson backend")
        # On the Jetson we want full GPU offload by default; --ngl 0 stays CPU.
        ngl = args.ngl if args.ngl else 99
        return JetsonBackend(args.model, args.mmproj, n_gpu_layers=ngl,
                             max_side=args.max_side)
    raise SystemExit(f"backend '{args.backend}' not wired in run.py yet")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", default="hf", choices=["hf", "gguf", "jetson"])
    p.add_argument("--dataset", default="refcoco", choices=["refcoco", "refdrone"])
    p.add_argument("--model", required=True, help="checkpoint path or HF id (remote path for jetson)")
    p.add_argument("--split", default="validation",
                   help="dataset split (refcoco: validation; refdrone: val)")
    p.add_argument("--n", type=int, default=100, help="number of val samples (0 = all)")
    p.add_argument("--coco-root", default="data/coco")
    p.add_argument("--mmproj", default="",
                   help="mmproj GGUF (required for gguf/jetson; remote path for jetson)")
    p.add_argument("--ngl", type=int, default=0,
                   help="GPU layers (gguf: 0 = CPU; jetson: 0 -> full offload)")
    p.add_argument("--max-side", type=int, default=IMAGE_SIZE,
                   help="long-edge input resize (Phase-2 lever; Phase-3/4 used 1024)")
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--note", default="", help="free-text note saved into the manifest")
    args = p.parse_args()

    print(f"[run] loading {args.dataset} '{args.split}' subset (n={args.n or 'all'})...", flush=True)
    samples = _load_samples(args)
    print(f"[run] {len(samples)} samples; building {args.backend} backend "
          f"({args.model}) max_side={args.max_side}...", flush=True)

    backend = _build_backend(args)
    print("[run] evaluating...", flush=True)
    try:
        report = evaluate(backend, samples, progress_every=max(1, args.n // 10))
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()

    results = asdict(report)
    print(f"[run] DONE  n={report.n}  parse_rate={report.parse_rate:.1%}  "
          f"iou@0.25={report.iou_gate_pass_rate:.1%}  mean_iou={report.mean_iou:.3f}  "
          f"center_std={report.center_std:.1f}", flush=True)

    cfg = {
        "backend": args.backend,
        "dataset": args.dataset,
        "model": args.model,
        "split": args.split,
        "n": args.n,
        "max_side": args.max_side,
        "device": args.device,
        "dtype": args.dtype,
        "note": args.note,
    }
    if args.backend in ("gguf", "jetson"):
        cfg["mmproj"] = args.mmproj
        cfg["ngl"] = args.ngl
    m = manifest.capture("eval", cfg)
    run_dir = manifest.write(m, results=results)
    print(f"[run] manifest -> {run_dir}", flush=True)


if __name__ == "__main__":
    main()
