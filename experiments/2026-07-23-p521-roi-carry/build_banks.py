#!/usr/bin/env python3
"""Build P5.21 pilot + matrix banks from the hard-carry ranking and locally-present
frames. Pilot = held-out 8 (S2 base-rate gate); matrix = hardest disjoint distinct
bases, n>=27. Class-generic captions (no per-clip tuning -> no construction trap).

Run: .venv-ft/bin/python build_banks.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
SEQDIR = HERE.parents[1] / "experiments/2026-07-03-real-video-replay/data/UAV123/data_seq/UAV123"
PILOT = ["uav4", "car13", "uav5", "car11", "car15", "truck2", "wakeboard9", "wakeboard6"]

# class -> generic caption (matches R-36 / P5.16 vocabulary; strip trailing digits/underscore)
def caption_for(seq):
    stem = "".join(ch for ch in seq if not ch.isdigit()).rstrip("_")
    return {
        "car": "the car", "truck": "the truck", "bike": "the bicycle",
        "person": "the person", "group": "the person", "boat": "the boat",
        "uav": "the drone", "wakeboard": "the wakeboarder",
        "building": "the building", "bird": "the bird",
    }.get(stem, f"the {stem}")


def have(seq):
    d = SEQDIR / seq
    return d.is_dir() and len(list(d.glob("*.jpg"))) >= 100


def main():
    rank = json.loads((HERE / "hardcarry_ranking.json").read_text())["ranked_distinct"]
    # ranking is hardest-first, one row per distinct base
    pilot_set = set(PILOT)
    matrix, pilot = [], []
    for r in rank:
        seq = r["seq"]
        if not have(seq):
            continue
        entry = {"seq": seq, "caption": caption_for(seq)}
        if seq in pilot_set:
            pilot.append(entry)
        else:
            matrix.append(entry)
    # honor PILOT order for readability
    pilot.sort(key=lambda e: PILOT.index(e["seq"]))

    (HERE / "bank_pilot.json").write_text(json.dumps({"sequences": pilot}, indent=1))
    (HERE / "bank.json").write_text(json.dumps({"sequences": matrix}, indent=1))
    assert len(pilot) == 8, f"pilot must be 8 held-out, got {len(pilot)}"
    assert len(matrix) >= 27, f"matrix must be >=27 for the deflated gate, got {len(matrix)}"
    # disjoint
    assert not (set(e["seq"] for e in pilot) & set(e["seq"] for e in matrix))
    print(f"pilot  n={len(pilot):2}: {[e['seq'] for e in pilot]}")
    print(f"matrix n={len(matrix):2}: {[e['seq'] for e in matrix]}")
    print("captions (matrix):")
    for e in matrix:
        print(f"  {e['seq']:14} -> {e['caption']}")


if __name__ == "__main__":
    main()
