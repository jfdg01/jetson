"""P5.13 mechanical verdict. Reads runs/*/results.json, prints the per-cell
table, the RQ-P5.13a/b verdicts and the pre-registered interpretation branch.
No judgment calls: every rule here is a numeric comparison fixed in README.md
before the run.

    .venv-ft/bin/python experiments/2026-07-19-v2disc-select/verdict_p513.py
    .venv-ft/bin/python experiments/2026-07-19-v2disc-select/verdict_p513.py --selfcheck
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = [f"bank{i:02d}" for i in range(1, 13)]
LEGS = ("white", "blue")

# pre-registered thresholds (README.md "Verdict rules")
SEP_MARGIN = 4              # RQ-P5.13a: |DD_total - RG_total| >= 4 (of 24). SYMMETRIC
                            # on purpose: P5.13 predicts RG > DD (the crossing breaks
                            # the carry), the opposite direction to P5.10's DD-favouring
                            # B_MARGIN. The question is separation, not which side wins.
LEG_ASYM = 3                # RQ-P5.13b (diagnostic, non-gating): blue-leg DD minus
                            # white-leg DD >= 3 of 12 => the designed occlusion is what
                            # breaks the carry (white is the occluded target in 12/12).
CEILING = 20                # interpretation only (not a gate): "near ceiling" of 24


def decide(dd_total, rg_total, dd_by_leg):
    """Pure, testable. Returns (overall_yes, branch_tag)."""
    sep = abs(dd_total - rg_total) >= SEP_MARGIN
    if sep:
        return True, "1" if dd_total > rg_total else "2"
    return False, "3" if (dd_total >= CEILING and rg_total >= CEILING) else "4"


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

    overall, branch = decide(dd_total, rg_total, dd_by_leg)
    asym = dd_by_leg["blue"] - dd_by_leg["white"]
    print(f"\nRQ-P5.13a (|DD_total - RG_total| >= {SEP_MARGIN} of 24): "
          f"{'YES' if overall else 'NO'} "
          f"(DD {dd_total} vs RG {rg_total}, |diff| {abs(dd_total - rg_total)})")
    print(f"RQ-P5.13b (blue-leg DD - white-leg DD >= {LEG_ASYM} of 12; DIAGNOSTIC, "
          f"does NOT gate the overall verdict): "
          f"{'YES' if asym >= LEG_ASYM else 'NO'} "
          f"(blue {dd_by_leg['blue']}/12 - white {dd_by_leg['white']}/12 = {asym})")
    print(f"OVERALL RQ-P5.13: {'YES' if overall else 'NO'} "
          f"(YES iff a; the visual gate V is checked by the operator on "
          f"the overlay PNGs and can only downgrade this to NO)")

    print("\nPre-registered interpretation branches (the matching one applies):")
    marks = []
    marks.append(("1", branch == "1",
                  "DD > RG by >= 4: direct delivery beats prompt-time re-grounding "
                  "even through a designed crossing -- the carry survives occlusion "
                  "and the VLM re-ground is the weak link. Next lever = unpark P5.6 "
                  "(direct delivery on real UAV123)."))
    marks.append(("2", branch == "2",
                  "RG > DD by >= 4: the designed crossing BREAKS the carry and "
                  "prompt-time re-grounding repairs identity. First result favouring "
                  "RG; it inverts the Part V warm-start premise for occluded targets "
                  "and the next lever is a hybrid (carry + re-ground confirmation), "
                  "not more scene data."))
    marks.append(("3", branch == "3",
                  "No separation, both contracts >= 20/24: the bank still does not "
                  "discriminate. Check the two PRE-REGISTERED explanations in this "
                  "order -- (i) crossing-peak uniformity + constant z-order (P5.12 "
                  "audit: white-box centre y std 6.1 px, white nearer in 0/300 frames "
                  "in every clip), then (ii) bank05/bank06 weaker occlusion stress "
                  "(max GT-GT IoU 0.217/0.251 vs 0.352 for bank07). Do NOT derive a "
                  "third explanation post-hoc."))
    marks.append(("4", branch == "4",
                  "No separation, at least one contract < 20/24: the stack fails at "
                  "f150 for reasons upstream of the delivery contract (carry loss on "
                  "both, or VLM failure on both); diagnose the stack before re-asking "
                  "the contract question."))
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

    # pure threshold table (no files): every branch + both margin edges
    assert decide(24, 16, {"white": 12, "blue": 12}) == (True, "1")
    assert decide(16, 24, {"white": 4, "blue": 12}) == (True, "2")   # RG wins
    assert decide(24, 24, {"white": 12, "blue": 12}) == (False, "3")
    assert decide(22, 20, {"white": 10, "blue": 12}) == (False, "3")  # diff 2 < 4
    assert decide(12, 10, {"white": 5, "blue": 7}) == (False, "4")
    assert decide(20, 24, {"white": 8, "blue": 12}) == (True, "2")    # diff 4 == margin
    assert decide(21, 24, {"white": 9, "blue": 12}) == (False, "3")   # diff 3 < margin
    print("--- selfcheck: decide() branch table OK")

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

    print("verdict_p513 selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        sys.exit(verdict(HERE / "runs"))
