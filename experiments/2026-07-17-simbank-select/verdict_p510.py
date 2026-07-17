"""P5.10 mechanical verdict. Reads runs/*/results.json, prints the per-cell
table, the RQ-P5.10a/b verdicts and the pre-registered interpretation branch.
No judgment calls: every rule here is a numeric comparison fixed in README.md
before the run.

    .venv-ft/bin/python experiments/2026-07-17-simbank-select/verdict_p510.py
    .venv-ft/bin/python experiments/2026-07-17-simbank-select/verdict_p510.py --selfcheck
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = [f"bank{i:02d}" for i in range(1, 13)]
LEGS = ("white", "blue")

# pre-registered thresholds (README.md "Verdict rules")
A_MIN_PER_LEG = 10          # RQ-P5.10a: DD passes >= 10/12 on EACH leg
B_MARGIN = 4                # RQ-P5.10b: DD_total >= RG_total + 4 (of 24)
RG_CEILING = 20             # interpretation only (not a gate): RG "near ceiling"


def collect(runs: Path):
    cells, missing = {}, []
    for clip in CLIPS:
        for leg in LEGS:
            f = runs / f"{clip}_{leg}" / "results.json"
            if f.exists():
                cells[f"{clip}_{leg}"] = json.loads(f.read_text())
            elif (runs / f"{clip}_{leg}.INFRA").exists():
                cells[f"{clip}_{leg}"] = None      # recorded infra loss
            else:
                missing.append(f"{clip}_{leg}")
    return cells, missing


def verdict(runs: Path) -> int:
    cells, missing = collect(runs)
    if missing:
        print(f"INCOMPLETE: {len(missing)} cells missing (no results.json, "
              f"no .INFRA marker): {', '.join(missing)}")
        return 2

    hdr = (f"{'cell':<14}{'DD':<6}{'dd_class':<14}{'ddIoU':<7}{'RG':<6}"
           f"{'rg_class':<16}{'vlm_on':<8}{'acq_s':<7}{'delivF':<8}"
           f"{'ddCov':<7}{'rgCov':<7}")
    print(hdr)
    dd_by_leg = {l: 0 for l in LEGS}
    rg_by_leg = {l: 0 for l in LEGS}
    infra = [k for k, v in cells.items() if v is None]
    dd_classes, rg_classes = {}, {}
    for key in sorted(cells):
        r = cells[key]
        if r is None:
            print(f"{key:<14}{'INFRA':<6}")
            continue
        dd, rg = r["dd"], r["rg"]
        leg = r["leg"]
        dd_by_leg[leg] += bool(dd["pass"])
        rg_by_leg[leg] += bool(rg["pass"])
        if not dd["pass"]:
            dd_classes[dd["fail_class"]] = dd_classes.get(dd["fail_class"], 0) + 1
        if not rg["pass"]:
            rg_classes[rg["fail_class"]] = rg_classes.get(rg["fail_class"], 0) + 1
        print(f"{key:<14}{('PASS' if dd['pass'] else 'FAIL'):<6}"
              f"{str(dd['fail_class']):<14}{dd['iou_named']:<7.3f}"
              f"{('PASS' if rg['pass'] else 'FAIL'):<6}"
              f"{str(rg['fail_class']):<16}{str(rg.get('vlm_on')):<8}"
              f"{rg['acquire_s']:<7.2f}{rg['deliver_frame']:<8}"
              f"{r['cov_dd']['frac_lock']:<7.3f}{r['cov_rg']['frac_lock']:<7.3f}")

    n_infra = len(infra)
    dd_total = sum(dd_by_leg.values())
    rg_total = sum(rg_by_leg.values())
    print(f"\nDD per leg: white {dd_by_leg['white']}/12, blue {dd_by_leg['blue']}/12"
          f"  -> DD_total {dd_total}/24")
    print(f"RG per leg: white {rg_by_leg['white']}/12, blue {rg_by_leg['blue']}/12"
          f"  -> RG_total {rg_total}/24")
    print(f"DD fail classes: {dd_classes or '{}'}  RG fail classes: {rg_classes or '{}'}")
    if n_infra:
        print(f"INFRA cells ({n_infra}, count as FAIL for both contracts): {infra}")
    if n_infra > 1:
        print("VERDICT: NO [infra] — more than 1 infra-lost cell (pre-registered cap)")
        return 1

    a = dd_by_leg["white"] >= A_MIN_PER_LEG and dd_by_leg["blue"] >= A_MIN_PER_LEG
    b = dd_total >= rg_total + B_MARGIN
    print(f"\nRQ-P5.10a (DD >= {A_MIN_PER_LEG}/12 on each leg): "
          f"{'YES' if a else 'NO'}")
    print(f"RQ-P5.10b (DD_total >= RG_total + {B_MARGIN}): "
          f"{'YES' if b else 'NO'} ({dd_total} vs {rg_total})")
    print(f"OVERALL RQ-P5.10: {'YES' if (a and b) else 'NO'} "
          f"(YES iff a AND b; the visual gate V is checked by the operator on "
          f"the overlay PNGs and can only downgrade this to NO)")

    print("\nPre-registered interpretation branches (the matching one applies):")
    marks = []
    marks.append(("1", a and b,
                  "contract-change validated on clean-attribute scenes at n=12; "
                  "next lever = unpark P5.6 (direct delivery on real UAV123)."))
    marks.append(("2", a and not b and rg_total >= RG_CEILING,
                  "RG near ceiling: the P5.3/4/5 select NOs are SCENE-bound "
                  "(UAV123 attribute murk), not contract-bound; DD's remaining "
                  "edge is latency only (0 s vs ~5 s acquire)."))
    marks.append(("3", a and not b and rg_total < RG_CEILING,
                  "DD clears the bar but the margin over RG is < 4: contracts "
                  "not separable on bank v1; harden the bank (crossings, longer "
                  "idle) before re-testing."))
    marks.append(("4", not a,
                  "DD itself fails on clean sim: carry-bound (ID switch/drift) "
                  "or stack-on-sim gap; select is blocked upstream of any "
                  "delivery contract."))
    for tag, hit, txt in marks:
        print(f"  [{'X' if hit else ' '}] branch {tag}: {txt}")
    return 0


def selfcheck() -> None:
    """Fabricated runs dirs exercise counting, thresholds, infra rules and the
    branch logic. Offline, no experiment data touched."""
    import tempfile

    def fake(runs, clip, leg, dd_pass, rg_pass, rg_class=None):
        d = runs / f"{clip}_{leg}"
        d.mkdir(parents=True)
        (d / "results.json").write_text(json.dumps({
            "leg": leg,
            "dd": {"pass": dd_pass, "fail_class": None if dd_pass else "CARRY_DRIFT",
                   "iou_named": 0.9 if dd_pass else 0.1},
            "rg": {"pass": rg_pass, "fail_class": rg_class, "vlm_on": "named",
                   "acquire_s": 4.8, "deliver_frame": 195},
            "cov_dd": {"frac_lock": 1.0}, "cov_rg": {"frac_lock": 1.0}}))

    with tempfile.TemporaryDirectory() as td:
        runs = Path(td)
        # branch 1: DD 24/24, RG 16/24 (8 NO_BOX fails)
        for i, clip in enumerate(CLIPS):
            for j, leg in enumerate(LEGS):
                rg_ok = not (i < 4)  # bank01-04 both legs fail RG
                fake(runs, clip, leg, True, rg_ok, None if rg_ok else "NO_BOX")
        assert verdict(runs) == 0
        print("--- selfcheck: branch-1 shape OK")

    with tempfile.TemporaryDirectory() as td:
        runs = Path(td)
        for clip in CLIPS[:-1]:
            for leg in LEGS:
                fake(runs, clip, leg, True, True)
        # one missing cell -> INCOMPLETE
        assert verdict(runs) == 2
        (runs / "bank12_white.INFRA").write_text("stub reason")
        (runs / "bank12_blue.INFRA").write_text("stub reason")
        # two infra cells -> NO [infra]
        assert verdict(runs) == 1
        print("--- selfcheck: INCOMPLETE + infra-cap OK")

    print("verdict_p510 selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        sys.exit(verdict(HERE / "runs"))
