"""E20 proof-clip builder (run after the matrix; pick reps by results).

Thesis clips (README definition of done): at minimum
  1. one flipped clip: E18 A (full-frame stale acquire, genuine_lock FALSE) stacked
     over the E20 cell run (scoped acquire) -- the before/after.
  2. the wrong-probe behaviour (car10 mis-hinted "top left").
Optionally a third: a cell-vs-cellbuf comparison on a clip where they diverge.

Overlays are mp4v at native res; proof clips are h264-recompressed and scaled to
keep the committed files small (E18/E19 convention).

    .venv-ft/bin/python experiments/2026-07-04-prompt-scoped-acquire/make_proof.py \
        --flip-clip car14 --flip-run cell_car14_r1 --wrong-run wrong_car10_r1 \
        [--diverge-clip car7 --diverge-cell cell_car7_r1 --diverge-cellbuf cellbuf_car7_r1]
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
E18_RUNS = HERE.parents[0] / "2026-07-03-real-video-replay" / "runs"
PROOF = HERE / "proof"


def sh(*args):
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], check=True)


def single(src: Path, out: Path, label: str):
    sh("ffmpeg", "-y", "-v", "error", "-i", src,
       "-vf", f"scale=960:-2,drawtext=text='{label}':x=10:y=h-40:fontsize=24:"
              "fontcolor=white:box=1:boxcolor=black@0.5",
       "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-an", out)


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
    ap.add_argument("--flip-clip", required=True, help="clip for the before/after")
    ap.add_argument("--flip-run", required=True, help="E20 cell run dir name")
    ap.add_argument("--wrong-run", required=True, help="wrong-probe run dir name")
    ap.add_argument("--diverge-clip")
    ap.add_argument("--diverge-cell")
    ap.add_argument("--diverge-cellbuf")
    args = ap.parse_args()

    PROOF.mkdir(exist_ok=True)
    stacked(E18_RUNS / f"A_{args.flip_clip}_r1" / "overlay.mp4",
            HERE / "runs" / args.flip_run / "overlay.mp4",
            PROOF / f"{args.flip_clip}_E18_vs_E20cell.mp4",
            "E18 A (full-frame ~4.85s) - stale acquire, genuine_lock FALSE",
            f"E20 {args.flip_run} - prompt-scoped cell-crop acquire")
    single(HERE / "runs" / args.wrong_run / "overlay.mp4",
           PROOF / f"{args.wrong_run}_wrongprobe.mp4",
           f"E20 {args.wrong_run} - deliberately wrong hint 'top left' (car10 is center)")
    if args.diverge_clip:
        stacked(HERE / "runs" / args.diverge_cell / "overlay.mp4",
                HERE / "runs" / args.diverge_cellbuf / "overlay.mp4",
                PROOF / f"{args.diverge_clip}_cell_vs_cellbuf.mp4",
                f"E20 {args.diverge_cell} (cell)",
                f"E20 {args.diverge_cellbuf} (cell + buf catch-up)")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
