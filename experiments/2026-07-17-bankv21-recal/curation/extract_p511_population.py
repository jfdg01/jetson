#!/usr/bin/env python
"""Extract the P5.12 calibration population from the recorded P5.11 runs.

The P5.11 bank (12 recorded cells + the seed-1 probe) is the calibration set
for the two recalibrated floors: every one of these clips was opened with the
Read tool during the P5.11 visual gate and confirmed a genuine designed
occlusion with ZERO render defects (P5.11 README, Results), so their metric
values are the observed range of CORRECT renders:

  - G6c white n_clear: population 23..119 (the old floor 60, set from the
    single probe's 80, sits above 7 of 12 valid cells).
  - G8b blue-dominance median: population 0.487..0.700 (the old floor 0.55,
    set from the single probe's 0.687, classifies 3 visually-valid shallow
    occlusions as failures; a real z-order defect drives this toward ~0).

P5.11 frames live only on the workstation (runs/ media are gitignored), so
this script must run where those runs exist; the JSON it writes is committed
as the byte-frozen provenance the P5.12 floors were derived from.

Run (from repo root, once, at design time):
    .venv-ft/bin/python experiments/2026-07-17-bankv21-recal/curation/extract_p511_population.py
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P511 = HERE.parent.parent / "2026-07-17-bankv2-crossing"

spec = importlib.util.spec_from_file_location("verdict_p511", P511 / "verdict_p511.py")
vd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vd)

cells = []
for run, seed in vd.BANK_RUNS:
    g = vd.grade_run(run, seed, is_bank=True)
    assert g is not None, f"{run}: P5.11 run data missing on this machine"
    cells.append({"run": run, "seed": seed, "n_clear": g["n_clear"],
                  "n_occ": g["n_occ"], "bdom": g["bdom"],
                  "wfrag_p10": g["wfrag_p10"], "xpeak_f": g["xpeak_f"],
                  "old_g6c_pass": bool(g["g6c"]), "old_g8_pass": bool(g["g8"])})

out = {
    "source": "P5.11 experiments/2026-07-17-bankv2-crossing/runs/bank01..bank12",
    "visual_status": "all 12 crossing-peak overlays opened with the Read tool "
                     "in P5.11: genuine designed occlusions, 0 render defects",
    "probe_seed1": {"n_clear": 80, "bdom": 0.687, "wfrag_p10": 0.995},
    "cells": cells,
    "derived_floors": {
        "g6c_n_clear": {"old": 60, "new": 40,
                        "population": sorted(c["n_clear"] for c in cells)},
        "g8b_bdom": {"old": 0.55, "new": 0.40,
                     "population": sorted(c["bdom"] for c in cells)},
    },
}
path = HERE / "p511_population.json"
path.write_text(json.dumps(out, indent=2) + "\n")
print(f"wrote {path}")
for c in cells:
    print(c)
