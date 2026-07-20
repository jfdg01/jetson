#!/usr/bin/env python3
"""Read a follow trace written by carla_debug_ui.py and say what happened.

    .venv-ft/bin/python runners/carla_trace.py runs/carla-ui/trace-1234/trace.jsonl

Prints the ground, every target switch (with the PNG that proves it), and the
frames where the box bloated -- the two failure modes seen so far: the mask
growing off the car onto scenery, and the track ending up on a different vehicle.
"""
import json
import sys
from pathlib import Path


def summarize(rows, tdir=Path(".")):
    out = []
    for r in rows:
        if r["ev"] == "ground":
            out.append(f"ground {r['caption']!r} on frame {r['seed_n']} "
                       f"in {r['vlm_s']}s -> {r['box']}")
        elif r["ev"] == "live":
            out.append(f"live at frame {r['n']} (catchup {r['catchup_s']}s)")
        elif r["ev"] == "switch":
            png = tdir / "switch-{}.png".format(r["n"])
            out.append(f"frame {r['n']}: actor {r['was']} -> {r['now']}  {png}")
        elif r["ev"] == "identity":
            out.append(f"frame {r['n']}: target identity = actor {r['actor']} "
                       f"({r['actor_type']})")
        elif r["ev"] == "drift":
            png = tdir / "drift-{}.png".format(r["n"])
            out.append(f"frame {r['n']}: DRIFT {r['held_s']}s -- want actor "
                       f"{r['want']}, got {r['got']} ({r['got_type']})  {png}")
        elif r["ev"] == "lost":
            out.append(f"frame {r['n']}: carry lost the mask")

    steps = [r for r in rows if r["ev"] == "step"]
    if steps:
        bloat = [r for r in steps if r["area_ratio"] > 2.0]
        if bloat:
            out.append(f"box bloat >2x seed on {len(bloat)}/{len(steps)} steps, "
                       f"first at frame {bloat[0]['n']} "
                       f"(area_ratio {bloat[0]['area_ratio']})")
        # rolling lock at the end is the honest one; cumulative hides late drift
        last = steps[-1]
        out.append(f"final rolling lock {last['lock60']}/60 over {len(steps)} steps")
    return out


def main(path):
    p = Path(path)
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    print("\n".join(summarize(rows, p.parent)))


def _selfcheck():
    rows = [
        {"ev": "ground", "caption": "the blue car", "seed_n": 10, "vlm_s": 4.5,
         "box": [1, 2, 3, 4]},
        {"ev": "live", "n": 30, "catchup_s": 1.2},
        {"ev": "step", "n": 31, "area_ratio": 1.0, "lock60": 60, "actor": 7},
        {"ev": "identity", "n": 31, "actor": 7, "actor_type": "vehicle.audi.tt"},
        {"ev": "switch", "n": 40, "was": 7, "now": 9},
        {"ev": "drift", "n": 65, "held_s": 5.2, "want": 7, "got": 9,
         "got_type": "vehicle.volkswagen.t2"},
        {"ev": "step", "n": 40, "area_ratio": 5.0, "lock60": 12, "actor": 9},
    ]
    s = "\n".join(summarize(rows))
    assert "actor 7 -> 9" in s, s
    assert "identity = actor 7" in s, s
    assert "DRIFT 5.2s -- want actor 7, got 9" in s, s
    assert "drift-65.png" in s, s
    assert "switch-40.png" in s, s
    assert "bloat >2x seed on 1/2" in s, s
    assert "final rolling lock 12/60" in s, s
    print("selfcheck ok")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        _selfcheck()
