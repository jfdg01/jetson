"""
Stage 2 post-training pipeline: GGUF export → Jetson transfer → Phase A probe → Phase C re-run.

Run after run_stage2_finetune.py has produced a merged checkpoint at --ft-dir.

Steps:
  1. Convert merged HF checkpoint → GGUF Q8_0 (locally, using llama.cpp 57fe1f0)
  2. SCP GGUF to Jetson ~/smolvlm_ft_q8_0.gguf
  3. Verify GGUF loads on Jetson (llama-cli smoke test)
  4. Run Phase A grounding probe on Jetson with fine-tuned model
  5. Run Phase C Branch-2 re-run on Jetson with fine-tuned model

Usage:
  source .venv-ft/bin/activate
  python experiments/run_stage2_export.py [--ft-dir ./smolvlm_ft] [--dry-run]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

LLAMA_CPP_LOCAL   = Path("/tmp/llama.cpp-57fe1f0")
CONVERT_SCRIPT    = LLAMA_CPP_LOCAL / "convert_hf_to_gguf.py"
JETSON_HOST       = "jetson"
JETSON_GGUF_PATH  = "/home/jfdg/models/smolvlm_ft_q8_0.gguf"
# mmproj reused from original S2 (vision encoder was frozen during fine-tuning)
JETSON_MMPROJ_PATH = "/home/jfdg/models/mmproj-SmolVLM-500M-Instruct-f16.gguf"
JETSON_LLAMA_CLI  = "/home/jfdg/llama.cpp/build/bin/llama-cli"

REFDRONE_VAL_JSON = Path.home() / ".cache/huggingface/hub/datasets--sunzc-sunny--RefDrone/snapshots"
VISDRONE_VAL_IMAGES = Path("/home/gara/jetson/data/VisDrone2019-DET/images/val")


def run(cmd, check=True, capture=False, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture, text=True, **kw)


def step1_convert(ft_dir: Path, gguf_out: Path, dry_run: bool):
    print("\n=== Step 1: HF → GGUF Q8_0 (local) ===")
    if not CONVERT_SCRIPT.exists():
        sys.exit(f"ERROR: {CONVERT_SCRIPT} not found. Clone llama.cpp 57fe1f0 to /tmp/llama.cpp-57fe1f0")
    if not ft_dir.exists():
        sys.exit(f"ERROR: merged checkpoint not found at {ft_dir}")

    cmd = [
        sys.executable, str(CONVERT_SCRIPT),
        "--outtype", "q8_0",
        "--outfile", str(gguf_out),
        str(ft_dir),
    ]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(str(c) for c in cmd)}")
        return
    run(cmd)
    size_mb = gguf_out.stat().st_size / 1e6
    print(f"GGUF written: {gguf_out}  ({size_mb:.0f} MB)")


def step2_scp(gguf_out: Path, dry_run: bool):
    print(f"\n=== Step 2: SCP GGUF to {JETSON_HOST}:{JETSON_GGUF_PATH} ===")
    cmd = ["scp", str(gguf_out), f"{JETSON_HOST}:{JETSON_GGUF_PATH}"]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return
    run(cmd)
    print("Transfer complete.")


def step3_verify(dry_run: bool):
    print(f"\n=== Step 3: Verify GGUF loads on Jetson ===")
    # Text-only load check (no image needed — just confirms the GGUF is valid)
    smoke_cmd = (
        f"{JETSON_LLAMA_CLI} --model {JETSON_GGUF_PATH} "
        f"--mmproj {JETSON_MMPROJ_PATH} -n 4 -p 'hello' 2>&1 | tail -8"
    )
    cmd = ["ssh", JETSON_HOST, smoke_cmd]
    if dry_run:
        print(f"[dry-run] would run smoke test on Jetson")
        return
    result = run(cmd, check=False, capture=True)
    print(result.stdout[-600:] if result.stdout else "(no output)")
    if result.returncode != 0:
        print(f"WARNING: llama-cli returned {result.returncode} — check GGUF validity")
    else:
        print("GGUF loads OK on Jetson.")


def _find_refdrone_json() -> Path:
    """Locate RefDrone_val_mdetr.json in HF cache."""
    snapshots = sorted(REFDRONE_VAL_JSON.iterdir())
    if not snapshots:
        sys.exit("ERROR: RefDrone not in HF cache. Run: "
                 "python -c \"from datasets import load_dataset; load_dataset('sunzc-sunny/RefDrone')\"")
    return snapshots[-1] / "RefDrone_val_mdetr.json"


def step4_phase_a(dry_run: bool):
    print("\n=== Step 4: Phase A grounding probe (fine-tuned model, runs locally) ===")
    refdrone_json = _find_refdrone_json()
    # run_grounding_probe.py runs locally and SSHes to Jetson internally
    cmd = [
        sys.executable, "experiments/run_grounding_probe.py",
        "--refdrone-ann",    str(refdrone_json),
        "--visdrone-images", str(VISDRONE_VAL_IMAGES),
        "--vlm-model",       JETSON_GGUF_PATH,
        "--mmproj-model",    JETSON_MMPROJ_PATH,
        "--n-sample",        "50",
        "--seed",            "42",
    ]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return
    run(cmd)


def step5_phase_c(dry_run: bool):
    print("\n=== Step 5: Phase C Branch-2 re-run (fine-tuned model, runs locally) ===")
    # run_phase_c.py runs locally and SSHes to Jetson for llama-server
    cmd = [
        sys.executable, "experiments/run_phase_c.py",
        "--vlm-model", JETSON_GGUF_PATH,
    ]
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}")
        return
    run(cmd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ft-dir", default="./smolvlm_ft",
                   help="Path to merged fine-tuned HF checkpoint (output of run_stage2_finetune.py)")
    p.add_argument("--gguf-out", default="./smolvlm_ft_q8_0.gguf",
                   help="Local path for the output GGUF file")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--from-step", type=int, default=1, choices=[1, 2, 3, 4, 5],
                   help="Resume from this step (skip earlier steps)")
    args = p.parse_args()

    ft_dir   = Path(args.ft_dir)
    gguf_out = Path(args.gguf_out)

    if args.from_step <= 1:
        step1_convert(ft_dir, gguf_out, args.dry_run)
    if args.from_step <= 2:
        step2_scp(gguf_out, args.dry_run)
    if args.from_step <= 3:
        step3_verify(args.dry_run)
    if args.from_step <= 4:
        step4_phase_a(args.dry_run)
    if args.from_step <= 5:
        step5_phase_c(args.dry_run)

    print("\n=== Export pipeline complete ===")


if __name__ == "__main__":
    main()
