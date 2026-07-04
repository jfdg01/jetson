"""E23 proof-clip builder (run after the matrix; pick reps by results).

Thesis deliverables (with proof/cell_sweep.png from phase0.py):
  1. one fuzz-sensitive flipped clip: E18 A (full-frame stale acquire, genuine_lock
     FALSE) stacked over the E23 tol run (worst-case FUZZED hint cropped by the HW*
     tolerant cell) -- the before/after.
  2. a single E23 tol clip on the other fuzz-sensitive clip, captioned with its fuzzed
     hint, showing the casual phrase still locks.

Overlays are mp4v at native res; proof clips are h264-recompressed + scaled small.

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/make_proof.py \
        --flip-clip car14 --flip-run tol_car14_r1 --flip-fuzzed "top left" \
        --single-clip car9 --single-run tol_car9_r1 --single-fuzzed "middle left"
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
       "-vf", f"scale=960:-2,drawtext=text='{label}':x=10:y=h-40:fontsize=22:"
              "fontcolor=white:box=1:boxcolor=black@0.5",
       "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-an", out)


def stacked(top: Path, bottom: Path, out: Path, top_label: str, bottom_label: str):
    sh("ffmpeg", "-y", "-v", "error", "-i", top, "-i", bottom,
       "-filter_complex",
       f"[0:v]scale=960:-2,drawtext=text='{top_label}':x=10:y=h-40:fontsize=22:"
       "fontcolor=white:box=1:boxcolor=black@0.5[a];"
       f"[1:v]scale=960:-2,drawtext=text='{bottom_label}':x=10:y=h-40:fontsize=22:"
       "fontcolor=white:box=1:boxcolor=black@0.5[b];"
       "[a][b]vstack=inputs=2:shortest=1",
       "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-an", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flip-clip", required=True)
    ap.add_argument("--flip-run", required=True)
    ap.add_argument("--flip-fuzzed", required=True)
    ap.add_argument("--single-clip", required=True)
    ap.add_argument("--single-run", required=True)
    ap.add_argument("--single-fuzzed", required=True)
    args = ap.parse_args()

    PROOF.mkdir(exist_ok=True)
    stacked(E18_RUNS / f"A_{args.flip_clip}_r1" / "overlay.mp4",
            HERE / "runs" / args.flip_run / "overlay.mp4",
            PROOF / f"{args.flip_clip}_E18_vs_E23tol.mp4",
            "E18 A (full-frame ~4.85s) - stale acquire, genuine_lock FALSE",
            f"E23 {args.flip_run} - fuzzed '{args.flip_fuzzed}' HW*=0.38 tolerant cell")
    single(HERE / "runs" / args.single_run / "overlay.mp4",
           PROOF / f"{args.single_clip}_E23tol_fuzzed.mp4",
           f"E23 {args.single_run} - casual fuzzed hint '{args.single_fuzzed}', "
           "HW*=0.38 cell still locks")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
