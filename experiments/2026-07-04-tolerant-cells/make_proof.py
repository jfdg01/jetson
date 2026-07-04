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
    # RQ-E23 = NO (REGRESSIVE): captions show the fix FAILING, not a positive flip.
    PROOF.mkdir(exist_ok=True)

    # 1. The regression: E18 full-frame LOCKED car10 (genuine, cov 1.00); the E23
    #    worst-case fuzzed 'top center' tolerant cell grounds the WRONG red car (cov 0.00).
    stacked(E18_RUNS / "A_car10_r1" / "overlay.mp4",
            HERE / "runs" / "tol_car10_r1" / "overlay.mp4",
            PROOF / "car10_E18_vs_E23tol_regression.mp4",
            "E18 A full-frame (~4.85s) - LOCKED car10 (genuine, cov 1.00)",
            "E23 tol fuzzed 'top center' HW*=0.38 - grounds the WRONG car (cov 0.00)")

    # 2. Staleness unchanged: E23 tol car9 tracks (cov 0.99) but the ~2.8s acquire still
    #    lands after the arrival frame -> genuine_lock FALSE, same binder as E18.
    single(HERE / "runs" / "tol_car9_r1" / "overlay.mp4",
           PROOF / "car9_E23tol_stale.mp4",
           "E23 tol fuzzed 'middle left' HW*=0.38 - cov 0.99 but genuine_lock FALSE "
           "(arrival-frame stale, E18 binder unchanged)")

    # 3. The lone survivor: E18 A car14 stale (genuine FALSE) -> E23 tol locks it
    #    (genuine, cov 0.92, acq 2.1s). The mechanism isn't universally broken.
    single(HERE / "runs" / "tol_car14_r1" / "overlay.mp4",
           PROOF / "car14_E23tol_survivor.mp4",
           "E23 tol fuzzed 'top left' HW*=0.38 - lone survivor, locks (genuine, acq 2.1s)")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
