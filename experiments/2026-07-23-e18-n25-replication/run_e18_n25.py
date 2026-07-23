"""R-34 driver: run E18's leg A (COLD) and leg B (ORACLE) over the frozen P5.2a
25-clip bank, at frame-0 onset, on the real stack. Reuses replay_e18 unchanged
(the P5.2a pattern of driving a frozen harness over a clip list).

    python run_e18_n25.py                 # full matrix into runs/
    python run_e18_n25.py --clips car3    # subset (smoke)

Leg B (oracle, no Jetson) runs first for every clip, then leg A (Jetson). A
crashed/hung leg is marked INVALID and the matrix continues; results.json
already present is skipped (resumable across the 5 h token window).
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
E18 = HERE.parent / "2026-07-03-real-video-replay"
sys.path.insert(0, str(HERE))
from replay_e18_clean import run_clean  # noqa: E402

DATA = E18 / "data" / "UAV123"
LEGS = ("ORACLE", "COLD")  # ORACLE (cheap, no Jetson) first, then COLD (Jetson)


def main() -> None:
    clips = json.loads((HERE / "clips.json").read_text())
    only = sys.argv[sys.argv.index("--clips") + 1:] if "--clips" in sys.argv else None
    if only:
        clips = [c for c in clips if c["clip"] in only]
    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    for leg in LEGS:  # all B, then all A: one Jetson boot phase, not interleaved
        for c in clips:
            seq_dir = DATA / "data_seq" / "UAV123" / c["clip"]
            anno = DATA / "anno" / "UAV123" / f"{c['clip']}.txt"
            out = runs / f"{leg}_{c['clip']}"
            if (out / "results.json").exists():
                print(f"[skip] {out.name} already done", flush=True)
                continue
            try:
                run_clean(leg, seq_dir, anno, c["caption"], out)
            except Exception:  # ponytail: one leg's crash must not sink the matrix
                out.mkdir(parents=True, exist_ok=True)
                (out / "results.json").write_text(json.dumps(
                    {"leg": leg, "clip": c["clip"], "INVALID": traceback.format_exc()}, indent=1))
                print(f"[INVALID] {leg} {c['clip']}\n{traceback.format_exc()}", flush=True)
    print(f"matrix done: {len(list(runs.glob('*/results.json')))} result files")


if __name__ == "__main__":
    main()
