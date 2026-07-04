"""P5.2 clip profiler: turn UAV123 GT boxes into a category x speed grid.

The Part V focus is on-screen target speed (how fast the box moves across the
frame) because that is what makes a blocking acquire land stale. Speed is
directly measurable from the GT annotations, so clip selection is data-driven,
not eyeballed:

  on-screen speed = median centroid displacement between consecutive valid
                    frames, normalised to %frame-diagonal per second
                    (scale-invariant: a big slow truck and a tiny fast bird
                    are comparable) -> the axis we bin on.
  object size     = median box area as %frame.
  length          = valid-frame count (needs >= MIN_FRAMES for the P5.1
                    t_p=8s + acquire + 10s-cover schedule to fit).

UAV123 anno = one line per frame "x,y,w,h" (top-left + wh, comma-sep); an
absent/occluded frame is "NaN,NaN,NaN,NaN". Frame is 1280x720.

    python profiles.py <anno_dir>   # print the grid; also writes profiles.json
    python profiles.py --selfcheck
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from statistics import median

W, H, FPS = 1280, 720, 30.0
DIAG = (W * W + H * H) ** 0.5           # 1468.6 px
MIN_FRAMES = 700                        # ~23 s: t_p 8s + acquire ~4.5s + cover 10s
# speed bins in %diag/s, set from the observed UAV123 distribution (see profile run)
SLOW, FAST = 3.0, 8.0                   # <3 slow, 3-8 med, >8 fast (provisional; retune on real data)


def category_of(name: str) -> str:
    """car1_s -> car, person14 -> person, group1_1 -> group, uav3 -> uav."""
    return re.match(r"[a-zA-Z]+", name).group(0)


def parse_anno(path: Path) -> list[tuple[float, float, float, float] | None]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[,\s]+", line)
        try:
            x, y, w, h = (float(p) for p in parts[:4])
            out.append(None if (w <= 0 or h <= 0 or x != x) else (x, y, w, h))  # x!=x catches NaN
        except (ValueError, IndexError):
            out.append(None)
    return out


def profile(name: str, boxes: list) -> dict:
    valid = [b for b in boxes if b is not None]
    sizes = [100.0 * w * h / (W * H) for (_, _, w, h) in valid]
    # centroid speed between CONSECUTIVE valid frames only (skip gaps)
    speeds = []
    prev = None
    for b in boxes:
        if b is None:
            prev = None
            continue
        cx, cy = b[0] + b[2] / 2, b[1] + b[3] / 2
        if prev is not None:
            d = ((cx - prev[0]) ** 2 + (cy - prev[1]) ** 2) ** 0.5
            speeds.append(100.0 * d / DIAG * FPS)   # %diag per second
        prev = (cx, cy)
    return {
        "seq": name,
        "category": category_of(name),
        "n_valid": len(valid),
        "n_total": len(boxes),
        "size_pct": round(median(sizes), 3) if sizes else 0.0,
        "speed_pct_s": round(median(speeds), 2) if speeds else 0.0,
        "eligible": len(valid) >= MIN_FRAMES,
    }


def speed_bin(s: float) -> str:
    return "slow" if s < SLOW else ("fast" if s > FAST else "med")


def scan(anno_dir: Path) -> list[dict]:
    profs = [profile(p.stem, parse_anno(p)) for p in sorted(anno_dir.glob("*.txt"))]
    for p in profs:
        p["speed_bin"] = speed_bin(p["speed_pct_s"])
    return profs


def selfcheck() -> None:
    assert category_of("car1_s") == "car"
    assert category_of("person14") == "person"
    assert category_of("group1_2") == "group"
    # a box moving 14.686 px/frame = 1% diag/frame -> 30% diag/s; static -> 0
    static = [(100, 100, 50, 50)] * 800
    p = profile("car9", static)
    assert p["category"] == "car" and p["speed_pct_s"] == 0.0 and p["eligible"], p
    assert abs(p["size_pct"] - 100 * 2500 / (W * H)) < 1e-3, p   # size_pct is rounded to 3dp
    moving = [(100 + i * 14.686, 100, 50, 50) for i in range(800)]  # 1%diag/frame
    pm = profile("boat1", moving)
    assert abs(pm["speed_pct_s"] - 30.0) < 0.1, pm            # 1%/frame * 30fps = 30%/s
    assert speed_bin(1.0) == "slow" and speed_bin(5.0) == "med" and speed_bin(12.0) == "fast"
    # gaps (None) must not create a giant fake jump
    withgap = [(0, 0, 10, 10), None, (500, 500, 10, 10), (505, 500, 10, 10)]
    pg = profile("x1", withgap)
    assert len(withgap) == 4 and pg["n_valid"] == 3, pg
    print("profiles selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
        sys.exit()
    anno_dir = Path(sys.argv[1])
    profs = scan(anno_dir)
    out = anno_dir.parent / "profiles.json"
    out.write_text(json.dumps(profs, indent=1))
    elig = [p for p in profs if p["eligible"]]
    print(f"{len(profs)} sequences, {len(elig)} eligible (>= {MIN_FRAMES} valid frames)\n")
    print(f"{'seq':14} {'cat':10} {'frames':>7} {'size%':>7} {'speed%/s':>9} {'bin':>5}")
    for p in sorted(elig, key=lambda p: (p["category"], p["speed_pct_s"])):
        print(f"{p['seq']:14} {p['category']:10} {p['n_valid']:7d} {p['size_pct']:7.2f} "
              f"{p['speed_pct_s']:9.2f} {p['speed_bin']:>5}")
    from collections import Counter
    print("\ncategory x speed_bin counts (eligible):")
    grid = Counter((p["category"], p["speed_bin"]) for p in elig)
    cats = sorted({p["category"] for p in elig})
    print(f"{'':10} {'slow':>5} {'med':>5} {'fast':>5}")
    for c in cats:
        print(f"{c:10} " + " ".join(f"{grid.get((c,b),0):5d}" for b in ("slow", "med", "fast")))
    print(f"\nwrote {out}")
