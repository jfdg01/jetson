"""P5.14 visual-verification frame dump (CLAUDE.md "Look at it" rule).

The frozen P5.6 rig (select_p56.py, unchanged) writes one overlay.mp4 per
cell but no PNGs. An agent cannot Read an mp4, so this script extracts two
inspectable frames per cell for the mandatory visual gate:

  runs/<cell>/viz_early.png  -- 25% into the overlay clip (post-delivery,
                                early coverage; NOT frame 0)
  runs/<cell>/viz_late.png   -- 75% into the overlay clip (late coverage)

Cheap mechanical asserts (per CLAUDE.md): a frame that is > 99% one colour
is a failed render, not a night scene; early/late byte-identical is a dead
feed, not a still camera. Either condition raises and names the cell.

Usage (after the matrix):
  .venv-ft/bin/python experiments/2026-07-19-realvid-dd-select/dump_frames_p514.py
Exit 0 and per-cell "OK" lines = frames written and healthy.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def grab(cap: cv2.VideoCapture, idx: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if not ok or frame is None:
        raise RuntimeError(f"cannot read frame {idx}")
    return frame


def health(frame: np.ndarray, name: str) -> None:
    # >99% one colour = failed render (histogram over 8x8x8 quantized colours)
    q = (frame // 32).reshape(-1, 3)
    _, counts = np.unique(q, axis=0, return_counts=True)
    frac = counts.max() / q.shape[0]
    if frac > 0.99:
        raise RuntimeError(f"{name}: {frac:.3f} of pixels one colour -> failed render")


def main() -> None:
    cells = sorted(p for p in RUNS.glob("DD_*") if (p / "overlay.mp4").exists())
    if not cells:
        raise SystemExit(f"no runs/DD_*/overlay.mp4 under {RUNS} -- run the matrix first")
    bad = 0
    for cell in cells:
        cap = cv2.VideoCapture(str(cell / "overlay.mp4"))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if n < 4:
            print(f"{cell.name}: FAIL overlay has {n} frames"); bad += 1; continue
        try:
            early = grab(cap, n // 4)
            late = grab(cap, (3 * n) // 4)
            health(early, f"{cell.name}/viz_early")
            health(late, f"{cell.name}/viz_late")
            if np.array_equal(early, late):
                raise RuntimeError(f"{cell.name}: early==late byte-identical -> dead feed")
        except RuntimeError as e:
            print(f"{cell.name}: FAIL {e}"); bad += 1; continue
        finally:
            cap.release()
        cv2.imwrite(str(cell / "viz_early.png"), early)
        cv2.imwrite(str(cell / "viz_late.png"), late)
        print(f"{cell.name}: OK ({n} overlay frames; wrote viz_early.png f{n//4}, "
              f"viz_late.png f{(3*n)//4})")
    if bad:
        sys.exit(f"{bad} cell(s) failed frame health -- those cells are INVALID pending inspection")
    print(f"dump_frames_p514 OK ({len(cells)} cells)")


if __name__ == "__main__":
    main()
