"""E23 matrix driver (13 runs): smoke (car10 x1) then tol (6 clips x n=2) at HW*.

Each config is a fresh subprocess of replay_e23.py (per-run isolation + Jetson
self-boot, matching the E18/E19/E20 convention). Captions are frozen from E18; the
fuzzed WORST-CASE hint is computed by replay_e23 from the frame-0 GT (cells.worst_hint
at tau); this driver only asserts the worst-hint table matches Phase-0 and passes HW*.

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/run_matrix.py [--smoke-only]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = str(REPO / ".venv-ft" / "bin" / "python")
SCRIPT = str(HERE / "replay_e23.py")
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
DATA = E18 / "data" / "UAV123"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
import cells                                                          # noqa: E402
from replay_source import load_uav123_gt                             # noqa: E402

HW_STAR = 0.38   # Phase-0: smallest HW with 6/6 worst-case containment
TAU = 0.10

# frozen from E18 (identical captions to E20)
CAPTIONS = {
    "car3": "the red car", "car9": "the white car", "car14": "the red car",
    "car18": "the red car", "car7": "the silver car", "car10": "the red car",
}
# worst-case fuzzed hints -- from Phase-0 (asserted below against cells.worst_hint)
WORST = {
    "car3": "center", "car7": "top center", "car9": "middle left",
    "car10": "top center", "car14": "top left", "car18": "top center",
}
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]


def seq_dir(clip):
    return DATA / "data_seq" / "UAV123" / clip


def anno(clip):
    return DATA / "anno" / "UAV123" / f"{clip}.txt"


def assert_worst():
    """Guard: the hardcoded WORST table must equal cells.worst_hint on frame-0 GT."""
    for clip in CLIPS:
        gt = load_uav123_gt(anno(clip))
        paths = sorted(seq_dir(clip).glob("*.jpg"))
        h, w = cv2.imread(str(paths[0])).shape[:2]
        got = cells.worst_hint(gt[0], w, h, TAU)
        assert got == WORST[clip], (clip, got, WORST[clip])
    print(f"[matrix] worst-hint table verified vs cells.worst_hint (tau={TAU}, "
          f"HW*={HW_STAR})", flush=True)


def run(clip, out_name):
    out = HERE / "runs" / out_name
    print(f"\n=== {out_name} (tol clip={clip} hw={HW_STAR} fuzzed={WORST[clip]!r}) ===",
          flush=True)
    cmd = [PY, SCRIPT, "--mc", "none", "--hw", str(HW_STAR), "--tau", str(TAU),
           "--clip", clip, "--caption", CAPTIONS[clip], "--out", str(out)]
    subprocess.run(cmd, check=True)


def main():
    assert_worst()
    smoke_only = "--smoke-only" in sys.argv
    run("car10", "smoke_tol_car10")                              # plumbing smoke
    if smoke_only:
        return
    for clip in CLIPS:                                           # tol arm at HW*
        for rep in (1, 2):
            run(clip, f"tol_{clip}_r{rep}")


if __name__ == "__main__":
    main()
