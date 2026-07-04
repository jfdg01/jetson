"""P5.2 matrix driver: run WARM/COLD/ORACLE over the frozen 25 clips.

Reads clips.json ([{"clip": "person1", "caption": "the person"}, ...]) and
reuses the P5.1 rig (replay_e24.run_matrix_clip) unchanged. One run dir per
leg; a crashed/hung leg is marked INVALID and the matrix continues (README
abort criteria). n=1 (P5.1 was bit-identical across reps).

    python run_matrix.py            # run the full matrix into runs/
    python run_matrix.py --clips person1 boat3   # subset (smoke)
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
E24 = HERE.parent / "2026-07-04-warm-start-acquire"
sys.path.insert(0, str(E24))
from replay_e24 import run_matrix_clip  # noqa: E402

DATA = HERE.parent / "2026-07-03-real-video-replay" / "data" / "UAV123"
LEGS = ("WARM", "COLD", "ORACLE")


def main() -> None:
    clips = json.loads((HERE / "clips.json").read_text())
    only = sys.argv[sys.argv.index("--clips") + 1:] if "--clips" in sys.argv else None
    if only:
        clips = [c for c in clips if c["clip"] in only]
    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    for c in clips:
        seq_dir = DATA / "data_seq" / "UAV123" / c["clip"]
        anno = DATA / "anno" / "UAV123" / f"{c['clip']}.txt"
        for leg in LEGS:
            out = runs / f"{leg}_{c['clip']}"
            if (out / "results.json").exists():
                print(f"[skip] {out.name} already done", flush=True)
                continue
            try:
                run_matrix_clip(leg, seq_dir, anno, c["caption"], out)
            except Exception:  # ponytail: one leg's crash must not sink the matrix
                out.mkdir(parents=True, exist_ok=True)
                (out / "results.json").write_text(json.dumps(
                    {"leg": leg, "clip": c["clip"], "INVALID": traceback.format_exc()}, indent=1))
                print(f"[INVALID] {leg} {c['clip']}\n{traceback.format_exc()}", flush=True)
    print(f"matrix done: {len(list(runs.glob('*/results.json')))} result files")


if __name__ == "__main__":
    main()
