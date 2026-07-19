"""P5.6 mechanical verdict from runs/*/results.json -- no judgment calls.

Prints the per-cell table, the failure classification, the non-gating
diagnostics (weak-rule SWAP comparison, shadow re-ground table, latency),
and the RQ verdicts:

  RQ-P5.6a: DD WSEL PASS count over the 5 gating scenes >= 4 -> YES else NO
  RQ-P5.6b: DD SWAP PASS count over the 5 gating scenes >= 4 -> YES else NO
            (SWAP PASS = strengthened rule: delivered box IoU < 0.25 vs
             target GT AND >= 0.25 vs the hand distractor GT at the prompt)
  Overall : YES iff both.

Failure classification (mechanical, per non-passing cell):
  lost-track       : reason contains "track lost" or "past clip end".
  carry-off-object : SWAP delivered box off the distractor hand GT
                     (deliver_iou_distractor < 0.25) -- the carry wandered
                     off the named object; also WSEL delivered box off the
                     target GT at deliver (no genuine_lock).
  on-target        : SWAP delivered box ON the target GT (deliver_iou >=
                     0.25) -- the distractor carry converged onto the target.
  coverage         : WSEL genuine lock but coverage < 0.5.
  infra            : anything else (should not occur).

Usage:
  .venv-ft/bin/python experiments/2026-07-14-direct-delivery-select/verdict_p56.py \
      [--runs experiments/2026-07-14-direct-delivery-select/runs]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATING = [("car10", 240), ("car10", 615), ("car9", 300), ("car7", 460),
          ("car9", 560)]
THRESH = 4  # PASS count needed per leg over the 5 gating scenes


def classify(r: dict) -> str:
    sc = r["score"]
    reason = sc.get("reason") or ""
    if "track lost" in reason or "past clip end" in reason:
        return "lost-track"
    if r["leg"] == "SWAP":
        if (sc.get("deliver_iou") or 0.0) >= 0.25:
            return "on-target"
        if (sc.get("deliver_iou_distractor") or 0.0) < 0.25:
            return "carry-off-object"
        return "infra"
    # WSEL
    if not sc.get("genuine_lock"):
        return "carry-off-object"
    if sc.get("coverage", 0.0) < 0.5:
        return "coverage"
    return "infra"


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
        sh = r["meta"].get("shadow") or {}
        rows.append({
            "cell": p.parent.name, "leg": r["leg"],
            "sid": (s["clip"], s["f0"]), "pass": r["pass"],
            "weak": r.get("swap_weak_pass"),
            "d_iou": r["score"].get("deliver_iou"),
            "d_iou_dist": r["score"].get("deliver_iou_distractor"),
            "cov": r["score"].get("coverage"),
            "reanchor": [ra.get("accepted") for ra in
                         r["meta"].get("reanchor", [])],
            "shadow_sel": sh.get("selected"),
            "shadow_s": sh.get("acquire_s"),
            "fail_class": None if r["pass"] else classify(r),
            "reason": r["score"].get("reason"),
        })

    print(f"{'cell':<22} {'pass':<5} {'weak':<5} {'d_iou':>6} {'d_dist':>6} "
          f"{'cov':>6} {'reanchor':<14} fail_class / reason")
    print("-" * 100)
    for w in rows:
        extra = "" if w["pass"] else f"{w['fail_class']}: {w['reason'] or ''}"
        print(f"{w['cell']:<22} {str(w['pass']):<5} {str(w['weak']):<5} "
              f"{str(w['d_iou']):>6} {str(w['d_iou_dist']):>6} "
              f"{str(w['cov']):>6} {str(w['reanchor']):<14} {extra}")

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
    print(f"\nRQ-P5.6a (DD WSEL >= {THRESH}/5 gating): {a}/5 -> {va}")
    print(f"RQ-P5.6b (DD SWAP >= {THRESH}/5 gating, strengthened): "
          f"{b}/5 -> {vb}")
    print(f"OVERALL: {'YES' if va == vb == 'YES' else 'NO'}")

    # ---- non-gating diagnostics --------------------------------------------
    swaps = [w for w in rows if w["leg"] == "SWAP"]
    if swaps:
        weak = sum(1 for w in swaps if w["weak"])
        strong = sum(1 for w in swaps if w["pass"])
        print(f"\nWeak-rule SWAP (old P5.3/P5.5 off-target-only rule, "
              f"non-gating): {weak}/{len(swaps)} vs strengthened "
              f"{strong}/{len(swaps)} -- the gap is what the old rule "
              "flattered.")

    print("\nShadow re-ground (what the P5.5 contract would have selected at "
          "the prompt; non-gating):")
    for w in rows:
        agree = ("agree" if w["shadow_sel"] ==
                 ("target" if w["leg"] == "WSEL" else "distractor")
                 else "DISAGREE")
        print(f"  {w['cell']:<22} shadow_sel={str(w['shadow_sel']):<11} "
              f"({agree}) shadow_acquire_s={w['shadow_s']}")

    sh_s = [w["shadow_s"] for w in rows if w["shadow_s"] is not None]
    if sh_s:
        print(f"\nLatency: direct delivery acquire_s = 0.00 for all cells "
              f"(by construction) vs shadow full-frame re-ground mean "
              f"{sum(sh_s) / len(sh_s):.2f}s over {len(sh_s)} cells.")

    ctl = [w for w in rows if w["sid"] == ("car3", 200)]
    if ctl:
        print("\ncar3:200 control (non-gating; P5.3/P5.4/P5.5 WSEL always "
              "failed 'resolution-bound' -- predicted to FLIP under DD):")
        for w in ctl:
            print(f"  {w['cell']}: pass={w['pass']} "
                  f"{'' if w['pass'] else w['reason'] or w['fail_class']}")


if __name__ == "__main__":
    main()
