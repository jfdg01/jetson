"""RQ4 — robustness of the ROI win to a drifted prior (3090, .venv-ft, repo root).

The accuracy sweep used a GT-centered (oracle) crop. A real re-anchor uses the
tracker's last box, which drifts. Offset the crop center by shift·box_size (random
direction, seeded) and re-measure at the deploy-candidate resolution (512), for the
tight winner M=2.0 and the more-forgiving M=3.0. shift=0 controls are already in
sweep_summary.json (M2@512=85.2%, M3@512=82.7%). Dumps perturb_summary.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from grounding.roi import run_grid

MODEL = "./runs/v2/phase3-refdrone-1024"
COMBOS = [(2.0, 512), (3.0, 512)]
SHIFTS = [0.25, 0.5, 1.0]
HERE = Path(__file__).resolve().parent


def main():
    rows = []
    for sh in SHIFTS:
        res = run_grid(MODEL, "val", COMBOS, n=0, shift=sh,
                       note=f"roi drift shift={sh}")
        for r in res:
            rows.append({"shift": sh, "margin": r["margin"], "out_res": r["out_res"],
                         "iou25": r["iou_gate_pass_rate"], "mean_iou": r["mean_iou"],
                         "parse": r["parse_rate"], "n": r["n"], "run_dir": r["run_dir"]})
            print(f"[drift] shift={sh} M={r['margin']} res={r['out_res']} "
                  f"iou@0.25={r['iou_gate_pass_rate']:.1%}", flush=True)
    (HERE / "perturb_summary.json").write_text(json.dumps(rows, indent=2))
    print(f"[drift] DONE → {HERE/'perturb_summary.json'}", flush=True)


if __name__ == "__main__":
    main()
