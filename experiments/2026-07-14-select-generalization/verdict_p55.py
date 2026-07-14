"""P5.5 mechanical verdict from runs/*/results.json -- no judgment calls.

Prints the per-cell table, the failure classification, and the RQ verdicts:

  RQ-P5.5a: MC WSEL PASS count over the 5 gating scenes >= 4 -> YES else NO
  RQ-P5.5b: MC SWAP PASS count over the 5 gating scenes >= 4 -> YES else NO
  Overall : YES iff both.

Failure classification (mechanical, per non-passing cell):
  carry-drift    : reason contains NO_MATCH AND the distractor candidate box
                   at the prompt is displaced vs its last accepted anchor
                   (seed box, or the last accepted re-anchor box): centre
                   shift > 0.25 of the anchor diagonal OR area ratio outside
                   [0.4, 2.5] -- the P5.4 carry_disp lesson: displacement
                   alone missed the shrinking-van drift, so area is checked
                   too. Also: distractor candidate None at prompt.
  match/grounding: reason contains NO_MATCH, distractor not displaced.
  grounding      : selection made but wrong (selection_correct false /
                   wrong track for the leg).
  carry          : selection correct but lock/coverage/deliver_iou failed,
                   or track lost.
  infra          : acquire returned no box / deliver past clip end.

Usage:
  .venv-ft/bin/python experiments/2026-07-14-select-generalization/verdict_p55.py \
      [--runs experiments/2026-07-14-select-generalization/runs]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATING = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
          ("car9", 560)]
THRESH = 4  # PASS count needed per leg over the 5 gating scenes


def displaced(anchor, at_prompt) -> bool:
    if at_prompt is None:
        return True
    ax1, ay1, ax2, ay2 = anchor
    bx1, by1, bx2, by2 = at_prompt
    diag = math.hypot(ax2 - ax1, ay2 - ay1)
    dc = math.hypot((bx1 + bx2 - ax1 - ax2) / 2, (by1 + by2 - ay1 - ay2) / 2)
    a_area = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    b_area = max(1.0, (bx2 - bx1) * (by2 - by1))
    ratio = b_area / a_area
    return dc > 0.25 * diag or not (0.4 <= ratio <= 2.5)


def classify(r: dict) -> str:
    sc, meta = r["score"], r["meta"]
    reason = sc.get("reason") or ""
    if "no box" in reason or "past clip end" in reason:
        return "infra"
    if "NO_MATCH" in reason:
        anchor = r["scene"]["distractor_box"]
        for ra in meta.get("reanchor", []):
            if ra.get("accepted"):
                anchor = ra["new_box"]
        at_prompt = (meta.get("cand_at_prompt") or {}).get("distractor")
        return "carry-drift" if displaced(anchor, at_prompt) else "match/grounding"
    if sc.get("selection") is not None and not sc.get("selection_correct"):
        return "grounding"
    return "carry"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(HERE / "runs"))
    args = ap.parse_args()
    runs = sorted(Path(args.runs).glob("*/results.json"))
    if not runs:
        raise SystemExit(f"no results.json under {args.runs}")

    rows = []
    for p in runs:
        r = json.loads(p.read_text())
        s = r["scene"]
        rows.append({
            "cell": p.parent.name, "arm": r.get("arm", "?"), "leg": r["leg"],
            "sid": (s["clip"], s["f0"]), "pass": r["pass"],
            "sel": r["score"].get("selection"),
            "acq": r["score"].get("acquire_s"),
            "reanchor": [ra.get("accepted") for ra in
                         r["meta"].get("reanchor", [])],
            "fail_class": None if r["pass"] else classify(r),
            "reason": r["score"].get("reason"),
        })

    print(f"{'cell':<22} {'pass':<5} {'sel':<11} {'acq_s':>6} "
          f"{'reanchor':<14} fail_class / reason")
    print("-" * 100)
    for w in rows:
        extra = "" if w["pass"] else \
            f"{w['fail_class']}: {w['reason'] or 'wrong selection'}"
        print(f"{w['cell']:<22} {str(w['pass']):<5} {str(w['sel']):<11} "
              f"{str(w['acq']):>6} {str(w['reanchor']):<14} {extra}")

    def count(arm, leg):
        got = {w["sid"]: w["pass"] for w in rows
               if w["arm"] == arm and w["leg"] == leg and w["sid"] in
               [tuple(g) for g in GATING]}
        missing = [g for g in GATING if tuple(g) not in got]
        return sum(got.values()), missing

    a, miss_a = count("MC", "WSEL")
    b, miss_b = count("MC", "SWAP")
    va = "YES" if a >= THRESH else "NO"
    vb = "YES" if b >= THRESH else "NO"
    if miss_a or miss_b:
        print(f"\nINCOMPLETE: missing gating cells WSEL={miss_a} SWAP={miss_b}"
              " -- verdict not final")
    print(f"\nRQ-P5.5a (MC WSEL >= {THRESH}/5 gating): {a}/5 -> {va}")
    print(f"RQ-P5.5b (MC SWAP >= {THRESH}/5 gating): {b}/5 -> {vb}")
    print(f"OVERALL: {'YES' if va == vb == 'YES' else 'NO'}")

    ms = [w for w in rows if w["arm"] == "M"]
    if ms:
        print("\nM-arm attribution (non-gating; compare cell-for-cell vs MC "
              "and vs the P5.3 baseline in the README):")
        for w in ms:
            print(f"  {w['cell']}: pass={w['pass']} sel={w['sel']} "
                  f"{'' if w['pass'] else w['reason']}")


if __name__ == "__main__":
    main()
