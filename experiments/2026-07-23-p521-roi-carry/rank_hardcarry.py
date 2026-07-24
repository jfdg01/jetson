#!/usr/bin/env python3
"""Rank UAV123 real sequences by carry-hardness from local GT (frames not needed).

Hard-carry = target moves far relative to its own size between carry steps
(SAM2 loses it) AND/OR is small AND/OR leaves the frame (None spans). We only
have GT locally for all 123; frames for ~21. This ranks so we know which to
stream-download. Scale-invariant metrics (disp / target-size) need no frame dims.

Run: .venv-ft/bin/python rank_hardcarry.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
ANNO = REPO / "experiments/2026-07-03-real-video-replay/data/UAV123/anno/UAV123"
SEQDIR = REPO / "experiments/2026-07-03-real-video-replay/data/UAV123/data_seq/UAV123"
FPS, CARRY_HZ = 30.0, 2.69
STRIDE = max(1, round(FPS / CARRY_HZ))     # 11 -- R-16 corrected rate


def load_gt(path):
    rows = []
    for ln in path.read_text().strip().splitlines():
        p = ln.replace(",", " ").split()
        try:
            x, y, w, h = (float(v) for v in p[:4])
            rows.append(None if math.isnan(x) or w <= 0 or h <= 0 else (x, y, x + w, y + h))
        except ValueError:
            rows.append(None)
    return rows


def center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def diag(b):
    return math.hypot(b[2] - b[0], b[3] - b[1])


def hardness(gt):
    """Return (score, feats). Higher score = harder carry."""
    n = len(gt)
    valid = [b for b in gt if b is not None]
    if len(valid) < 20:
        return None
    none_frac = 1 - len(valid) / n
    # displacement over one carry stride, normalized by target diagonal
    rel_disp = []
    sizes = []
    for i in range(0, n - STRIDE, STRIDE):
        a, b = gt[i], gt[i + STRIDE]
        if a is None or b is None:
            continue
        ca, cb = center(a), center(b)
        d = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
        rel_disp.append(d / max(1.0, diag(a)))
        sizes.append(diag(a))
    if not rel_disp:
        return None
    rel_disp.sort()
    med_rel = rel_disp[len(rel_disp) // 2]
    p90_rel = rel_disp[min(len(rel_disp) - 1, int(0.9 * len(rel_disp)))]
    mean_size = sum(sizes) / len(sizes)         # px diagonal; smaller = harder
    # small-target proxy: 1280x720 typical -> diag ~1469; smallness in [0,1]
    smallness = max(0.0, 1 - mean_size / 1469)
    # combined: motion dominates (drives SAM2 loss), + smallness + occlusion
    score = med_rel + 0.5 * p90_rel + 0.6 * smallness + 0.8 * none_frac
    return score, {
        "n": n, "valid": len(valid), "none_frac": round(none_frac, 3),
        "med_rel_disp": round(med_rel, 3), "p90_rel_disp": round(p90_rel, 3),
        "mean_size_px": round(mean_size, 1), "smallness": round(smallness, 3),
        "score": round(score, 3),
    }


def base(name):
    """distinct source: strip _s synthetic and _<n> temporal split suffix."""
    b = name[:-2] if name.endswith("_s") else name
    parts = b.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        b = parts[0]
    return b


def main():
    have = {d.name for d in SEQDIR.iterdir() if d.is_dir()
            and len(list(d.glob("*.jpg"))) >= 100}
    rows = []
    for txt in sorted(ANNO.glob("*.txt")):
        name = txt.stem
        if name.endswith("_s"):                 # synthetic CG -- exclude (real-imagery Wave B)
            continue
        r = hardness(load_gt(txt))
        if r is None:
            continue
        score, feats = r
        rows.append({"seq": name, "base": base(name), "have_frames": name in have, **feats})
    rows.sort(key=lambda r: -r["score"])
    # keep hardest per distinct base
    seen, distinct = set(), []
    for r in rows:
        if r["base"] in seen:
            continue
        seen.add(r["base"])
        distinct.append(r)
    out = {"stride": STRIDE, "carry_hz": CARRY_HZ, "n_ranked": len(rows),
           "n_distinct_base": len(distinct), "have_local": sorted(have),
           "ranked_distinct": distinct}
    (HERE / "hardcarry_ranking.json").write_text(json.dumps(out, indent=1))
    print(f"ranked {len(rows)} real seqs, {len(distinct)} distinct bases; "
          f"stride={STRIDE}")
    print(f"{'seq':14} {'have':4} {'score':6} {'med_rel':7} {'p90_rel':7} {'small':6} {'none'}")
    for r in distinct[:40]:
        print(f"{r['seq']:14} {'Y' if r['have_frames'] else '.':4} "
              f"{r['score']:<6.3f} {r['med_rel_disp']:<7} {r['p90_rel_disp']:<7} "
              f"{r['smallness']:<6} {r['none_frac']}")


if __name__ == "__main__":
    main()
