"""E19 proof-clip builder (run after the matrix; picks reps by results).

Three thesis clips (README definition of done, item 6):
  1. car3 before/after: E18 A (stale acquire FAIL) stacked over the E19 arm run.
  2. car7 REGROUND story: the E19 run of car7, whichever way it went.
  3. FLOW-vs-BUF comparison on one clip where they diverge (stacked), if any.

Overlays are mp4v at native res; proof clips are h264-recompressed and scaled
to keep the committed files small (E18 convention: 2-16 MB per clip).

    .venv-ft/bin/python experiments/2026-07-04-motion-comp-acquire/make_proof.py \
        --car3-run flow_car3_r1 --car7-run buf_car7_r1 \
        --diverge-clip car14 --diverge-flow flow_car14_r1 --diverge-buf buf_car14_r1
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
    ap.add_argument("--car3-run", required=True, help="E19 run dir name for the car3 before/after")
    ap.add_argument("--car7-run", required=True, help="E19 run dir name for the car7 REGROUND story")
    ap.add_argument("--diverge-clip", help="clip where flow/buf diverge (optional)")
    ap.add_argument("--diverge-flow", help="flow run dir name for the divergence pair")
    ap.add_argument("--diverge-buf", help="buf run dir name for the divergence pair")
    args = ap.parse_args()

    PROOF.mkdir(exist_ok=True)
    stacked(E18_RUNS / "A_car3_r1" / "overlay.mp4",
            HERE / "runs" / args.car3_run / "overlay.mp4",
            PROOF / "car3_E18_vs_E19.mp4",
            "E18 A (no MC) - stale acquire, genuine_lock FALSE",
            f"E19 {args.car3_run} - motion-compensated acquire")
    single(HERE / "runs" / args.car7_run / "overlay.mp4",
           PROOF / f"car7_{args.car7_run.split('_')[0]}_REGROUND.mp4",
           f"E19 {args.car7_run} - occlusion + REGROUND under MC")
    if args.diverge_clip:
        stacked(HERE / "runs" / args.diverge_flow / "overlay.mp4",
                HERE / "runs" / args.diverge_buf / "overlay.mp4",
                PROOF / f"{args.diverge_clip}_flow_vs_buf.mp4",
                f"E19 {args.diverge_flow} (NCC shift)",
                f"E19 {args.diverge_buf} (replay-buffer catch-up)")
    print("proof clips written to", PROOF)


if __name__ == "__main__":
    main()
