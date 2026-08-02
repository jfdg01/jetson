#!/usr/bin/env python3
"""Render one GT-overlay clip per TLP sequence on disk, whole sequence, fast-forwarded.

TLP is 245k frames over the 18 sequences downloaded so far -- 2.3 h of video at real time. Each
clip is instead strided down to ~`--target` drawn frames, so the whole sequence still passes but in
half a minute. `render_overlay.py --stride` prefers an absent frame inside each stride group, so a
gap shorter than the stride still shows up instead of being skipped over.

    analysis/render_tlp_all.py                 # -> proof/tlp_gt__<Seq>.mp4 + .mid.png
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data  # noqa: E402

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=900, help="drawn frames per clip (30 s at 30 fps)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--out", default=str(HERE.parent / "proof"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seqs = data.sequences("tlp")
    assert seqs, "no TLP sequences on disk"
    for seq in seqs:
        n = len(data.boxes(seq))
        stride = max(1, round(n / args.target))
        mp4 = out / f"tlp_gt__{seq}.mp4"
        print(f"{seq:16s} {n:6d} fr  stride {stride:3d}  -> {mp4.name}", flush=True)
        subprocess.run(
            [sys.executable, str(HERE / "render_overlay.py"), "--seq", seq,
             "--stride", str(stride), "--scale", str(args.width), "--out", str(mp4)],
            check=True, stdout=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
