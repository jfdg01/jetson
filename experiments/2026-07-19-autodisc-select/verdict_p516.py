"""P5.16 mechanical verdict from runs/DSC_*/results.json -- no judgment calls.

Prints the per-cell table, the discovery log summary, the failure
classification, the oracle-delta vs the frozen P5.14 (DD, oracle-seeded)
row, the non-gating diagnostics, and the RQ verdicts:

  RQ-P5.16a: DSC WSEL PASS count over the 5 gating scenes >= 4 -> YES else NO
  RQ-P5.16b: DSC SWAP PASS count over the 5 gating scenes >= 4 -> YES else NO
             (strengthened rule, unchanged from P5.14: delivered box IoU
              < 0.25 vs target GT AND >= 0.25 vs the hand distractor GT at
              the prompt)
  Overall  : YES iff both (and the visual gate in the README does not
             downgrade -- that part is Opus opening the PNGs, not this
             script).

Failure classification (mechanical, per non-passing cell):
  discovery-fail   : reason startswith "discovery-failed" (a caption was
                     never grounded by the prompt).
  lost-track       : reason contains "track lost" or "past clip end".
  off-distractor   : SWAP delivered box off the distractor hand GT
                     (deliver_iou_distractor < 0.25) -- wrong-object
                     discovery OR carry drift; also WSEL delivered box off
                     the target GT (no genuine_lock) -> "off-target".
  on-target        : SWAP delivered box ON the target GT (deliver_iou >=
                     0.25) -- duplicate slipped the IOU_SAME guard or the
                     carry converged.
  coverage         : WSEL genuine lock but coverage < 0.5.
  infra            : anything else (should not occur).

Usage:
  .venv-ft/bin/python experiments/2026-07-19-autodisc-select/verdict_p516.py \
      [--runs experiments/2026-07-19-autodisc-select/runs]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATING = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
          ("car9", 560)]
THRESH = 4  # PASS count needed per leg over the 5 gating scenes

# Frozen P5.14 oracle-seeded per-cell outcomes (from the committed
# experiments/2026-07-19-realvid-dd-select record; runs/** is gitignored so
# the row is hardcoded here for the oracle-delta table).
P514 = {
    ("WSEL", "car10", 240): True,  ("SWAP", "car10", 240): True,
    ("WSEL", "car10", 615): True,  ("SWAP", "car10", 615): True,
    ("WSEL", "car9", 300):  True,  ("SWAP", "car9", 300):  True,
    ("WSEL", "car7", 460):  True,  ("SWAP", "car7", 460):  False,
    ("WSEL", "car9", 560):  True,  ("SWAP", "car9", 560):  True,
    ("WSEL", "car3", 200):  True,  ("SWAP", "car3", 200):  True,
}


def classify(r: dict) -> str:
    sc = r["score"]
    reason = sc.get("reason") or ""
    if reason.startswith("discovery-failed"):
        return "discovery-fail"
    if "track lost" in reason or "past clip end" in reason:
        return "lost-track"
    if r["leg"] == "SWAP":
        if (sc.get("deliver_iou") or 0.0) >= 0.25:
            return "on-target"
        if (sc.get("deliver_iou_distractor") or 0.0) < 0.25:
            return "off-distractor"
        return "infra"
    if not sc.get("genuine_lock"):
        return "off-target"
    if sc.get("coverage", 0.0) < 0.5:
        return "coverage"
    return "infra"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(HERE / "runs"))
    args = ap.parse_args()
    runs = sorted(Path(args.runs).glob("DSC_*/results.json"))
    if not runs:
        raise SystemExit(f"no DSC_*/results.json under {args.runs}")

    rows = []
    for p in runs:
        r = json.loads(p.read_text())
        s = r["scene"]
        sh = r["meta"].get("shadow") or {}
        disc = r["meta"].get("discovery", [])
        rows.append({
            "cell": p.parent.name, "leg": r["leg"],
            "sid": (s["clip"], s["f0"]), "pass": r["pass"],
            "weak": r.get("swap_weak_pass"),
            "d_iou": r["score"].get("deliver_iou"),
            "d_iou_dist": r["score"].get("deliver_iou_distractor"),
            "cov": r["score"].get("coverage"),
            "disc": [(e["cand"][0].upper(), e["outcome"]) for e in disc],
            "n_calls": len(disc),
            "seed_iou": next((e.get("seed_iou_gt") for e in disc
                              if e["outcome"] == "accepted"
                              and e["cand"] == "target"), None),
            "done_f": r["meta"].get("discovery_done_frame"),
            "reanchor": [ra.get("accepted", ra.get("skipped"))
                         for ra in r["meta"].get("reanchor", [])],
            "shadow_sel": sh.get("selected"),
            "shadow_s": sh.get("acquire_s"),
            "fail_class": None if r["pass"] else classify(r),
            "reason": r["score"].get("reason"),
            "wall": r.get("wall_s"),
        })

    print(f"{'cell':<24} {'pass':<5} {'weak':<5} {'d_iou':>6} {'d_dist':>6} "
          f"{'cov':>6} {'seedIoU':>7} {'calls':>5} {'done_f':>6} "
          f"fail_class / reason")
    print("-" * 108)
    for w in rows:
        extra = "" if w["pass"] else f"{w['fail_class']}: {w['reason'] or ''}"
        print(f"{w['cell']:<24} {str(w['pass']):<5} {str(w['weak']):<5} "
              f"{str(w['d_iou']):>6} {str(w['d_iou_dist']):>6} "
              f"{str(w['cov']):>6} {str(w['seed_iou']):>7} "
              f"{w['n_calls']:>5} {str(w['done_f']):>6} {extra}")

    print("\nDiscovery call log per cell (cand-initial, outcome):")
    for w in rows:
        print(f"  {w['cell']:<24} {w['disc']}  reanchor={w['reanchor']}")

    def count(leg):
        got = {w["sid"]: w["pass"] for w in rows
               if w["leg"] == leg and w["sid"] in
               [tuple(g) for g in GATING]}
        missing = [g for g in GATING if tuple(g) not in got]
        return sum(got.values()), missing

    a, miss_a = count("WSEL")
    b, miss_b = count("SWAP")
    va = "YES" if a >= THRESH else "NO"
    vb = "YES" if b >= THRESH else "NO"
    if miss_a or miss_b:
        print(f"\nINCOMPLETE: missing gating cells WSEL={miss_a} SWAP={miss_b}"
              " -- verdict not final")
    print(f"\nRQ-P5.16a (DSC WSEL >= {THRESH}/5 gating): {a}/5 -> {va}")
    print(f"RQ-P5.16b (DSC SWAP >= {THRESH}/5 gating, strengthened): "
          f"{b}/5 -> {vb}")
    print(f"OVERALL (before visual gate): "
          f"{'YES' if va == vb == 'YES' else 'NO'}")

    # ---- oracle delta: P5.14 (oracle seeds) vs P5.16 (VLM discovery) ------
    print("\nOracle delta (P5.14 oracle-seeded pass vs P5.16 discovered pass; "
          "the cost of removing the seed oracle):")
    flips = 0
    for w in rows:
        key = (w["leg"], *w["sid"])
        old = P514.get(key)
        mark = "" if old == w["pass"] else (
            "  <-- LOST to discovery" if old and not w["pass"]
            else "  <-- GAINED (unexpected)")
        if old != w["pass"]:
            flips += 1
        print(f"  {w['cell']:<24} P5.14={str(old):<5} P5.16={str(w['pass']):<5}"
              f"{mark}")
    print(f"  flips: {flips}/{len(rows)}")

    # ---- non-gating diagnostics -------------------------------------------
    swaps = [w for w in rows if w["leg"] == "SWAP"]
    if swaps:
        weak = sum(1 for w in swaps if w["weak"])
        strong = sum(1 for w in swaps if w["pass"])
        print(f"\nWeak-rule SWAP (non-gating): {weak}/{len(swaps)} vs "
              f"strengthened {strong}/{len(swaps)}")

    print("\nShadow re-ground (non-gating):")
    for w in rows:
        agree = ("agree" if w["shadow_sel"] ==
                 ("target" if w["leg"] == "WSEL" else "distractor")
                 else "DISAGREE")
        print(f"  {w['cell']:<24} shadow_sel={str(w['shadow_sel']):<11} "
              f"({agree}) shadow_acquire_s={w['shadow_s']}")

    ctl = [w for w in rows if w["sid"] == ("car3", 200)]
    if ctl:
        print("\ncar3:200 control (non-gating; passed under P5.14 oracle "
              "seeds -- pre-registered prediction: WSEL flips back to FAIL "
              "under discovery):")
        for w in ctl:
            print(f"  {w['cell']}: pass={w['pass']} "
                  f"{'' if w['pass'] else w['reason'] or w['fail_class']}")

    walls = [w["wall"] for w in rows if w["wall"]]
    if walls:
        print(f"\nWall: mean {sum(walls)/len(walls):.0f}s/cell, "
              f"max {max(walls):.0f}s, total {sum(walls)/60:.1f} min")


if __name__ == "__main__":
    main()
