#!/usr/bin/env python3
"""Assemble the R-36 paired maintain-vs-select bank.

R-36 pairs, per distinct UAV123 base capture, the maintain arm (WSEL) against the
name-the-distractor arm (SWAP). The bank is:

  - the 13 P5.18 clips, COLLAPSED to one scene per clip by a pre-committed BLIND
    rule (smallest f0 == first onset), and REUSED cell-for-cell -- P5.18/P5.19/P5.20
    established this discovery harness is deterministic (P5.20 replicated P5.19 with
    0 flips), so re-running the same clips would reproduce identical pass/fail. The
    committed DSC_ result dirs are copied into runs/r36/ unchanged.
  - the 2 NEW usable clips found by hand-curating 10 fresh candidates (boat2,
    person13). The OTHER 8 (car14, car17, person6, car1_s, person18, person1_s,
    car4_s, boat3) are single-target: no co-visible same-class distractor exists at
    both the seed and prompt frames, so no SWAP scene can be built from them. That
    8/10 scarcity is R-36's headline finding, recorded in the README.

Both new clips carry WEAK distractors (boat2: distant ambiguous marina-yacht
cluster; person13: distractor only partially visible at f0) -- they are run for the
record and a with/without sensitivity, NOT to manufacture significance.

Writes:
  runs/r36/bank/scenes_r36.json        all 15 scenes (verdict_r36 reads this)
  runs/r36/bank/scenes_r36_new.json    the 2 new scenes only (discover_p516 runs this)
  runs/r36/DSC_{WSEL,SWAP}_<clip>_<f0> reused P5.18 first-onset cells (copied)
"""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
P518 = HERE.parents[0] / "2026-07-20-n25-select"
OUT = HERE / "runs" / "r36"
BANK = OUT / "bank"

NEW_SCENES = [
    {"clip": "boat2", "f0": 202, "t_p": 8.0,
     "target_caption": "the white motorboat with the canopy in the open water",
     "distractor_caption": "the large white yacht docked at the marina by the tower",
     "distractor_gt_prompt": [607, 155, 640, 177], "gating": True,
     "note": "NEW R-36. WEAK distractor: distant (~300px above target) ambiguous "
             "marina-yacht cluster (one of ~4 similar), ~40px. Human-viewed "
             "zoom_boat2_442. Run for sensitivity, not to claim significance."},
    {"clip": "person13", "f0": 244, "t_p": 8.0,
     "target_caption": "the person in the teal-and-white striped shirt",
     "distractor_caption": "the person in the green shirt",
     "distractor_gt_prompt": [360, 300, 408, 412], "gating": True,
     "note": "NEW R-36. WEAK distractor: only legs visible at f0 (cut at top edge), "
             "absent at ds=94, full body by prompt; identity inferred by radial "
             "growth. Run for sensitivity, not to claim significance."},
]


def main() -> None:
    p518 = json.loads((P518 / "scenes_p518.json").read_text())["scenes"]
    clips = sorted({s["clip"] for s in p518})
    first_onset = []
    for clip in clips:
        f0 = min(s["f0"] for s in p518 if s["clip"] == clip)
        first_onset.append(next(s for s in p518 if s["clip"] == clip and s["f0"] == f0))
    assert len(first_onset) == 13, len(first_onset)

    BANK.mkdir(parents=True, exist_ok=True)
    (BANK / "scenes_r36.json").write_text(json.dumps(
        {"comment": "R-36 bank: 13 P5.18 first-onset (reused) + 2 new weak (boat2, person13)",
         "scenes": first_onset + NEW_SCENES}, indent=1))
    (BANK / "scenes_r36_new.json").write_text(json.dumps(
        {"comment": "R-36 new clips only; run with discover_p516 --matrix",
         "scenes": NEW_SCENES}, indent=1))

    # reuse: copy the 13 first-onset DSC cells from P5.18 (deterministic harness)
    copied = 0
    for s in first_onset:
        for leg in ("WSEL", "SWAP"):
            src = P518 / "runs" / f"DSC_{leg}_{s['clip']}_{s['f0']}"
            dst = OUT / f"DSC_{leg}_{s['clip']}_{s['f0']}"
            if not (src / "results.json").exists():
                raise SystemExit(f"missing P5.18 cell {src}")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            copied += 1
    print(f"bank: 13 reused + 2 new = 15 scenes; copied {copied} P5.18 cells into {OUT}")
    print(f"next: discover_p516 --matrix {BANK/'scenes_r36_new.json'} --out {OUT} --legs WSEL,SWAP")


if __name__ == "__main__":
    main()
