"""EXP-6 -- gated carry-crop test (lever b at scale), ON THE ORIN.

The confirmation run for the arm EXP-5 promoted post-hoc. Three arms over ALL 38 clips of
EXP-1's frozen plan -- same seed frame, same seed box, same stride -- so the only thing that
moves between arms is what SAM2 is fed.

    CONTROL     plain whole frame @640                      (deployed)
    TREATMENT   fixed 512-px dead-band crop window @640      (EXP-5's A4, no guard)
    CONTROL-2   plain whole frame @1024                      (deployed size-gated fallback)

No guard arm: EXP-5 shipped the guard as a measured negative (the veto freezes its own
reference, so any threshold that fires at all latches). See README section 8.

Carry runs on the Jetson via the ssh-stdio bridge; this host holds UAV123 + GT, crops,
streams JPEGs, remaps and scores. NO torch/SAM2 here, NO 3090. machine=jetson.

The carry loop, crop geometry and bridge framing are EXP-5's, imported rather than copied --
identical mechanism is the point of a confirmation run.

    .venv-ft/bin/python run_exp6.py selfcheck
    .venv-ft/bin/python run_exp6.py carry --out runs/exp6
    .venv-ft/bin/python run_exp6.py score --out runs/exp6
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
from curate_p518 import frame  # noqa: E402
from grounding.stats import discordant_counts, mcnemar, paired_continuous  # noqa: E402
from run_exp5 import EXP1, _draw, _run_clip, iou  # noqa: E402
from run_exp5 import CLIPS as PILOT  # noqa: E402
from run_exp5 import TAIL  # noqa: E402

ARMS = {
    "CONTROL": {"size": 640, "crop": None, "guard": False},
    "TREATMENT": {"size": 640, "crop": "fixed", "guard": False},
    "CONTROL2": {"size": 1024, "crop": None, "guard": False},
}
BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"

PASS_IOU = 0.25          # delivered-PASS, the Part V/VI carry threshold
PARITY_IOU = 0.03        # accuracy parity band vs CONTROL-2
PARITY_PASS = 1          # clips
PARITY_RATE = 2.0        # x, TREATMENT Hz / CONTROL-2 Hz
SMALL_FRAME = (720, 480)  # the crop is min(512, w, h) = 480 here, i.e. barely a crop


def base_seq(clip: str) -> str:
    """UAV123 clips sharing a base sequence are ONE independent unit (car3 / car3_s)."""
    return clip[:-2] if clip.endswith("_s") else clip


# ---- carry ---------------------------------------------------------------------
def _plan(out: Path):
    plan = json.loads((EXP1 / "plan.json").read_text())
    assert len(plan) == 38, f"expected the 38-clip EXP-1 plan, got {len(plan)}"
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    return plan


def carry(out: Path, arms: list[str]) -> None:
    plan = _plan(out)
    for size in sorted({ARMS[a]["size"] for a in arms}):
        todo = [a for a in arms if ARMS[a]["size"] == size
                and not (out / f"carry_{a}.json").exists()]
        if not todo:
            continue
        log = open(out / f"bridge_{size}.err", "ab")
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE.format(size=size)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            for arm in todo:
                cfg, res, t0 = ARMS[arm], {}, time.time()
                for i, entry in enumerate(plan):
                    res[entry["clip"]] = _run_clip(proc, entry, cfg, None)
                    ms = [m for m in res[entry["clip"]]["ms"] if m]
                    print(f"[carry] {arm} [{i + 1}/{len(plan)}] {entry['clip']} "
                          f"median_ms={np.median(ms):.0f}", flush=True)
                (out / f"carry_{arm}.json").write_text(json.dumps(res, indent=1))
                print(f"[carry] {arm} done in {time.time() - t0:.0f}s", flush=True)
        finally:
            proc.stdin.close()
            proc.wait()
            log.close()


# ---- score ---------------------------------------------------------------------
def _stratum(per, clips, a, b):
    """Wilcoxon on the paired per-clip median IoU, raw and deflated by base sequence."""
    clips = list(clips)
    xa = [per[c][a]["median_iou"] for c in clips]
    xb = [per[c][b]["median_iou"] for c in clips]
    raw = paired_continuous(xa, xb, alternative="two-sided")

    groups: dict[str, list[str]] = {}
    for c in clips:
        groups.setdefault(base_seq(c), []).append(c)
    ga = [float(np.mean([per[c][a]["median_iou"] for c in g])) for g in groups.values()]
    gb = [float(np.mean([per[c][b]["median_iou"] for c in g])) for g in groups.values()]
    defl = paired_continuous(ga, gb, alternative="two-sided")

    pa = {c: int(per[c][a]["median_iou"] >= PASS_IOU) for c in clips}
    pb = {c: int(per[c][b]["median_iou"] >= PASS_IOU) for c in clips}
    nb, nc, npair = discordant_counts(pa, pb)
    return {
        "n": len(clips), "n_effective": len(groups),
        "median_iou_a": round(float(np.median(xa)), 3),
        "median_iou_b": round(float(np.median(xb)), 3),
        "wilcoxon_raw": raw, "wilcoxon_deflated": defl,
        "pass_a": sum(pa.values()), "pass_b": sum(pb.values()),
        "mcnemar": {"b": nb, "c": nc, "n_paired": npair,
                    "p_value": mcnemar(nb, nc) if (nb + nc) else 1.0},
    }


def score(out: Path) -> None:
    plan = json.loads((out / "plan.json").read_text())
    arms = [a for a in ARMS if (out / f"carry_{a}.json").exists()]
    by_arm = {a: json.loads((out / f"carry_{a}.json").read_text()) for a in arms}
    clips = [e["clip"] for e in plan]

    per, sizes = {}, {}
    for entry in plan:
        clip = entry["clip"]
        img = frame(clip, entry["seed"])
        sizes[clip] = [int(img.shape[1]), int(img.shape[0])]
        row = {}
        for a in arms:
            cr = by_arm[a][clip]
            ious = [iou(b, st["gt"]) for b, st in zip(cr["boxes"], entry["steps"])]
            ms = [m for m in cr["ms"] if m]
            row[a] = {
                "median_iou": round(float(np.median(ious)), 3),
                "final_iou": round(ious[-1], 3),
                "held_frac": round(float(np.mean([i >= PASS_IOU for i in ious])), 3),
                "hz": round(1000.0 / float(np.median(ms)), 2) if ms else None,
                "n_lost": int(sum(b is None for b in cr["boxes"])),
                "ious": [round(i, 3) for i in ious],
            }
        per[clip] = row

    held = [c for c in clips if c not in PILOT]
    small = [c for c in clips if tuple(sizes[c]) == SMALL_FRAME]
    strata = {
        "held_out_26": held, "pilot_12": [c for c in clips if c in PILOT],
        "all_38": clips, "tail_8": TAIL, "non_tail_30": [c for c in clips if c not in TAIL],
        "small_frame": small,
    }
    tests = {}
    for name, cs in strata.items():
        if not cs:
            continue
        tests[name] = {
            "treatment_vs_control": _stratum(per, cs, "TREATMENT", "CONTROL"),
            "treatment_vs_control2": _stratum(per, cs, "TREATMENT", "CONTROL2"),
        }

    summ = {}
    for a in arms:
        med = [per[c][a]["median_iou"] for c in clips]
        summ[a] = {
            "median_of_median_iou": round(float(np.median(med)), 3),
            "pass": int(sum(v >= PASS_IOU for v in med)),
            "tail_pass": int(sum(per[c][a]["median_iou"] >= PASS_IOU for c in TAIL)),
            "hz_median": round(float(np.median([per[c][a]["hz"] for c in clips
                                                if per[c][a]["hz"]])), 2),
            "n_lost": sum(per[c][a]["n_lost"] for c in clips),
        }

    # --- the pre-registered gates, evaluated in code so the verdict is not a reading ---
    hp = tests["held_out_26"]["treatment_vs_control"]
    rate = summ["TREATMENT"]["hz_median"] / summ["CONTROL2"]["hz_median"]
    d_iou = summ["TREATMENT"]["median_of_median_iou"] - summ["CONTROL2"]["median_of_median_iou"]
    d_pass = summ["TREATMENT"]["pass"] - summ["CONTROL2"]["pass"]
    pilot_dir = tests["pilot_12"]["treatment_vs_control"]["wilcoxon_raw"]["median_diff"]
    gates = {
        "accuracy": {
            "direction": hp["wilcoxon_raw"]["median_diff"] > 0,
            "p_deflated": hp["wilcoxon_deflated"]["p_value"],
            "pilot_not_reversing": pilot_dir >= 0,
            "pass": bool(hp["wilcoxon_raw"]["median_diff"] > 0
                         and hp["wilcoxon_deflated"]["p_value"] < 0.05
                         and pilot_dir >= 0),
        },
        "throughput_matched_parity": {
            "d_median_iou_vs_control2": round(d_iou, 3),
            "d_pass_vs_control2": d_pass,
            "rate_x": round(rate, 2),
            "pass": bool(abs(d_iou) <= PARITY_IOU and abs(d_pass) <= PARITY_PASS
                         and rate >= PARITY_RATE),
        },
        "kill": {
            "pass": bool(hp["wilcoxon_raw"]["median_diff"] <= 0
                         or (d_iou < -PARITY_IOU and rate < PARITY_RATE)),
        },
    }

    res = {"n_clips": len(plan), "arms": arms, "clips": clips, "frame_sizes": sizes,
           "strata": {k: v for k, v in strata.items()}, "per_clip": per,
           "summary": summ, "tests": tests, "gates": gates,
           "constants": {"pass_iou": PASS_IOU, "parity_iou": PARITY_IOU,
                         "parity_pass": PARITY_PASS, "parity_rate": PARITY_RATE}}
    (out / "results.json").write_text(json.dumps(res, indent=1))

    # two largest wins + the largest loss vs CONTROL, chosen by the numbers
    delta = sorted(clips, key=lambda c: per[c]["TREATMENT"]["median_iou"]
                   - per[c]["CONTROL"]["median_iou"])
    _overlays(out, plan, by_arm, [delta[-1], delta[-2], delta[0]], ["CONTROL", "TREATMENT"])

    print(f"\n[score] n={len(clips)}  held-out={len(held)}  pilot={len(PILOT)}  "
          f"small-frame={len(small)}")
    print(f"{'arm':>10} | {'med IoU':>7} | {'PASS':>5} | {'tail':>4} | {'Hz':>5} | {'lost':>4}")
    for a in arms:
        s = summ[a]
        print(f"{a:>10} | {s['median_of_median_iou']:>7.3f} | {s['pass']:>2}/{len(clips):<2} | "
              f"{s['tail_pass']:>1}/{len(TAIL):<2} | {s['hz_median']:>5} | {s['n_lost']:>4}")
    for name in ("held_out_26", "pilot_12", "all_38", "tail_8", "non_tail_30", "small_frame"):
        if name not in tests:
            continue
        t = tests[name]["treatment_vs_control"]
        print(f"\n[{name}] n={t['n']} n_eff={t['n_effective']}  "
              f"TREATMENT {t['median_iou_a']} vs CONTROL {t['median_iou_b']}  "
              f"PASS {t['pass_a']}/{t['pass_b']}")
        print(f"  Wilcoxon raw p={t['wilcoxon_raw']['p_value']:.4g} "
              f"median_diff={t['wilcoxon_raw']['median_diff']:+.4f} | "
              f"deflated p={t['wilcoxon_deflated']['p_value']:.4g} | "
              f"McNemar b={t['mcnemar']['b']} c={t['mcnemar']['c']} "
              f"p={t['mcnemar']['p_value']:.4g}")
    print(f"\n[gates] accuracy={gates['accuracy']['pass']} "
          f"parity={gates['throughput_matched_parity']['pass']} "
          f"kill={gates['kill']['pass']}  "
          f"(rate {gates['throughput_matched_parity']['rate_x']}x, "
          f"d_IoU {gates['throughput_matched_parity']['d_median_iou_vs_control2']:+.3f}, "
          f"d_PASS {gates['throughput_matched_parity']['d_pass_vs_control2']:+d})")


def _overlays(out: Path, plan, by_arm, clips, arms):
    """A carry claim is a claim about pixels; these are the pixels."""
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    by_clip = {e["clip"]: e for e in plan}
    for clip in clips:
        entry = by_clip[clip]
        n = len(entry["steps"])
        for arm in arms:
            cr = by_arm[arm][clip]
            for frac in (0.0, 0.25, 0.5, 1.0):
                j = min(n - 1, int(round(frac * (n - 1))))
                st = entry["steps"][j]
                img = frame(clip, st["frame"])
                _draw(img, st["gt"], (0, 200, 0), "GT")
                w = cr["wins"][j]
                if (w[2] - w[0]) < img.shape[1]:
                    _draw(img, w, (0, 140, 255), "crop")
                _draw(img, cr["boxes"][j], (255, 255, 0),
                      f"{arm} IoU={iou(cr['boxes'][j], st['gt']):.2f}")
                p = ovr / f"{clip}_{arm}_{int(frac * 100):03d}.jpg"
                cv2.imwrite(str(p), img)
                assert float((img == img[0, 0]).all(axis=2).mean()) < 0.99, \
                    f"{p} is >99% one colour -- failed render"
    print(f"[score] overlays for {clips} x {arms} -> {ovr}", flush=True)


def selfcheck() -> None:
    """The parts EXP-6 adds on top of EXP-5's (already self-checked) carry loop:
    the stratification, the base-sequence deflation and the gate arithmetic."""
    assert base_seq("car3_s") == "car3" and base_seq("car3") == "car3"
    assert base_seq("car10") == "car10" and base_seq("person1_s") == "person1"

    plan = json.loads((EXP1 / "plan.json").read_text())
    clips = [e["clip"] for e in plan]
    assert len(clips) == 38
    held = [c for c in clips if c not in PILOT]
    assert len(held) == 26, len(held)
    assert not set(held) & set(PILOT)
    assert len({base_seq(c) for c in held}) == 24, "expected 2 base-sequence collisions"

    # deflation must collapse a duplicated clip, not count it twice
    per = {c: {"TREATMENT": {"median_iou": 0.5}, "CONTROL": {"median_iou": 0.4}}
           for c in ("car3", "car3_s", "boat2")}
    st = _stratum(per, ["car3", "car3_s", "boat2"], "TREATMENT", "CONTROL")
    assert st["n"] == 3 and st["n_effective"] == 2, st
    assert abs(st["wilcoxon_raw"]["median_diff"] - 0.1) < 1e-9

    # a guard-free arm must never veto: cfg has no guard, so d_max is unused
    assert all(not c["guard"] for c in ARMS.values())
    print("exp6 self-check passed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["carry", "score", "selfcheck"])
    ap.add_argument("--out", default=str(HERE / "runs" / "exp6"))
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    if a.mode == "selfcheck":
        selfcheck()
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "carry":
        arms = [x.strip() for x in a.arms.split(",") if x.strip()]
        assert all(x in ARMS for x in arms), f"unknown arm in {arms}"
        carry(out, arms)
    else:
        score(out)


if __name__ == "__main__":
    main()
