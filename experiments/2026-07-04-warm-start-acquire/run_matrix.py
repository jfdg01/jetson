"""E24 matrix driver: 6 clips x {ORACLE, COLD, WARM} x n=2, snapshotting each run
to its own runs/<leg>_<clip>_r<rep> dir. Each run is wrapped in try/except so one
crash marks that leg INVALID and the matrix continues (README abort criteria).
Order: ORACLE (no VLM) then COLD then WARM (README run-order).

    .venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/run_matrix.py
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay_e24 import run_matrix_clip  # noqa: E402

E18 = HERE.parents[1] / "experiments" / "2026-07-03-real-video-replay"
DATA = E18 / "data" / "UAV123"

CAPTIONS = {"car3": "the red car", "car7": "the silver car", "car9": "the white car",
            "car10": "the red car", "car14": "the red car", "car18": "the red car"}
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]
LEGS = ["ORACLE", "COLD", "WARM"]
REPS = [1, 2]


def main() -> None:
    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    t0 = time.time()
    done, invalid = 0, []
    total = len(LEGS) * len(CLIPS) * len(REPS)
    for leg in LEGS:
        for clip in CLIPS:
            for rep in REPS:
                out = runs / f"{leg}_{clip}_r{rep}"
                if (out / "results.json").exists():
                    print(f"[skip] {out.name} already done", flush=True)
                    done += 1
                    continue
                seq = DATA / "data_seq" / "UAV123" / clip
                anno = DATA / "anno" / "UAV123" / f"{clip}.txt"
                print(f"\n===== [{done+1}/{total}] {leg} {clip} r{rep} "
                      f"(elapsed {time.time()-t0:.0f}s) =====", flush=True)
                try:
                    run_matrix_clip(leg, seq, anno, CAPTIONS[clip], out,
                                    t_p=8.0, cover_s=10.0, fps=30.0, clip=True)
                except Exception:
                    invalid.append(out.name)
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "INVALID.txt").write_text(traceback.format_exc())
                    print(f"[INVALID] {out.name}\n{traceback.format_exc()}", flush=True)
                done += 1
    (runs / "MATRIX_DONE.txt").write_text(
        f"done={done} invalid={invalid} elapsed_s={time.time()-t0:.0f}\n")
    print(f"\n===== MATRIX DONE: {done}/{total} runs, "
          f"invalid={invalid}, {time.time()-t0:.0f}s =====", flush=True)


if __name__ == "__main__":
    main()
