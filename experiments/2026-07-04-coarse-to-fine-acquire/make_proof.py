"""E21 proof-clip builder (run after the matrix; pick reps by results).

Thesis clips (README definition of done), both E20-operator vs E21-automated so the
one variable on screen is who supplies the hint:
  1. a correct-cell clip where the automation's extra coarse pass still costs the win:
     E20 cell (operator hint, genuine PASS) over E21 c2f (correct coarse cell, but the
     ~1 s coarse pass re-opens staleness and the genuine lock is lost).
  2. the most instructive failure: a WRONG coarse cell (the automated analogue of
     E20's wrong-hint probe) -- E20 cell (operator hint, PASS) over E21 c2f
     (coarse voted the wrong cell -> hallucinate + gate poison, cov 0.00).

Overlays are mp4v at native res; proof clips are h264-recompressed and scaled to keep
the committed files small (E18/E19/E20 convention).

    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/make_proof.py \
        --flip-clip car9 --flip-e20-run cell_car9_r1 --flip-c2f-run c2f_car9_r1 \
        --wrong-clip car10 --wrong-e20-run cell_car10_r1 --wrong-c2f-run c2f_car10_r1
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
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
    ap.add_argument("--flip-clip", required=True, help="correct-cell clip for the before/after")
    ap.add_argument("--flip-e20-run", required=True, help="E20 cell run dir name")
    ap.add_argument("--flip-c2f-run", required=True, help="E21 c2f run dir name (same clip)")
    ap.add_argument("--wrong-clip", required=True, help="wrong-coarse-cell clip")
    ap.add_argument("--wrong-e20-run", required=True, help="E20 cell run dir name (wrong clip)")
    ap.add_argument("--wrong-c2f-run", required=True, help="E21 c2f run dir name (wrong clip)")
    args = ap.parse_args()

    PROOF.mkdir(exist_ok=True)
    # 1. correct coarse cell, but the extra pass still costs the genuine lock
    stacked(E20_RUNS / args.flip_e20_run / "overlay.mp4",
            HERE / "runs" / args.flip_c2f_run / "overlay.mp4",
            PROOF / f"{args.flip_clip}_E20cell_vs_E21c2f.mp4",
            f"E20 {args.flip_e20_run} - OPERATOR center hint, genuine PASS",
            f"E21 {args.flip_c2f_run} - AUTOMATED correct cell, ~1s coarse re-opens staleness (lock lost)")
    # 2. wrong coarse cell = the automated [prior-wrong] analogue of E20's wrong probe
    stacked(E20_RUNS / args.wrong_e20_run / "overlay.mp4",
            HERE / "runs" / args.wrong_c2f_run / "overlay.mp4",
            PROOF / f"{args.wrong_clip}_E20cell_vs_E21c2f_wrongcell.mp4",
            f"E20 {args.wrong_e20_run} - OPERATOR center hint, PASS cov 1.00",
            f"E21 {args.wrong_c2f_run} - AUTOMATED coarse voted wrong cell: hallucinate + gate poison, cov 0.00")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
