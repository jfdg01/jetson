"""E21 proof-clip builder (run after the matrix; pick reps by results).

Thesis clips (README definition of done): at minimum
  1. one E20-flipped clip: E20 cell (operator hint) stacked over the E21 c2f run
     (automated coarse hint) -- the automation before/after, same crop mechanism.
  2. the most instructive failure: a clip whose coarse cell went WRONG if one occurs
     (the automated analogue of E20's wrong-hint probe), else the residual size-bound
     FAIL (E18 A stale vs E21 c2f) that automation still cannot rescue.

Overlays are mp4v at native res; proof clips are h264-recompressed and scaled to keep
the committed files small (E18/E19/E20 convention).

    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/make_proof.py \
        --flip-clip car14 --e20-run cell_car14_r1 --c2f-run c2f_car14_r1 \
        --fail-clip car3 --fail-c2f-run c2f_car3_r1
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18_RUNS = REPO / "experiments" / "2026-07-03-real-video-replay" / "runs"
E20_RUNS = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire" / "runs"
PROOF = HERE / "proof"


def sh(*args):
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True)


def stacked(top: Path, bottom: Path, out: Path, top_label: str, bottom_label: str):
    sh("ffmpeg", "-y", "-v", "error", "-i", top, "-i", bottom,
       "-filter_complex",
       f"[0:v]scale=960:-2,drawtext=text='{top_label}':x=10:y=h-40:fontsize=24:"
       "fontcolor=white:box=1:boxcolor=black@0.5[a];"
       f"[1:v]scale=960:-2,drawtext=text='{bottom_label}':x=10:y=h-40:fontsize=24:"
       "fontcolor=white:box=1:boxcolor=black@0.5[b];"
       "[a][b]vstack=inputs=2:shortest=1",
       "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-an", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flip-clip", required=True, help="E20-flipped clip for the before/after")
    ap.add_argument("--e20-run", required=True, help="E20 cell run dir name")
    ap.add_argument("--c2f-run", required=True, help="E21 c2f run dir name (same clip)")
    ap.add_argument("--fail-clip", required=True, help="clip for the instructive failure")
    ap.add_argument("--fail-c2f-run", required=True, help="E21 c2f run dir name (fail clip)")
    args = ap.parse_args()

    PROOF.mkdir(exist_ok=True)
    # 1. automation before/after: E20 operator hint over E21 automated coarse hint
    stacked(E20_RUNS / args.e20_run / "overlay.mp4",
            HERE / "runs" / args.c2f_run / "overlay.mp4",
            PROOF / f"{args.flip_clip}_E20cell_vs_E21c2f.mp4",
            f"E20 {args.e20_run} - OPERATOR cell hint",
            f"E21 {args.c2f_run} - AUTOMATED coarse->cell hint (no operator)")
    # 2. the instructive residual failure: E18 A stale vs E21 c2f
    stacked(E18_RUNS / f"A_{args.fail_clip}_r1" / "overlay.mp4",
            HERE / "runs" / args.fail_c2f_run / "overlay.mp4",
            PROOF / f"{args.fail_clip}_E18_vs_E21c2f.mp4",
            f"E18 A_{args.fail_clip}_r1 - full-frame ~4.85s stale acquire",
            f"E21 {args.fail_c2f_run} - c2f acquire (residual size-bound miss)")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
