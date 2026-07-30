"""What does abstention buy, replayed offline from a run that already happened.

`Dam4SamLtArm` wraps `Dam4SamArm` and calls `inner.step` on EVERY frame, including while lost, and
throws the result away. Nothing the wrapper decides ever reaches the tracker: no re-init, no memory
edit, no search-window move. So the wrapper's output is a pure function of the base arm's recorded
per-frame `(box, conf)` sequence -- which means running it on the Jetson would spend 1.7 GPU-hours
reproducing a number this file computes exactly, in a second, from `raw/`.

That is the whole point of the design. `AsymLtArm` is NOT simulable this way: its re-detector fires a
five-probe raster sweep that moves the search window, so the tracker's next input depends on the
state machine and the loop is closed. DAM4SAM sees the full frame, so there is no window to move.

What is simulated: the hysteresis machine (`tracking` -> `lost` after `k` consecutive frames under
`tau_lo`, back on one frame at or above `tau_hi`), and the metrics at ITS operating point -- a single
fixed threshold pair, not the max over tau that `presence.py` reports. The two are not the same
number and must not be compared naively: `presence.py --> maxgm` is an oracle upper bound over all
thresholds; `gm` here is what one fixed, out-of-sample threshold pair actually delivers. The gap
between them is the cost of not knowing tau in advance, and it is the honest number.

Thresholds are fitted on the even-indexed gap sequences and reported on the odd ones, same split as
`presence.py --thresholds`, for the same reason.

    analysis/lt_sim.py raw/dam-conf33 --arm dam4sam_t640
    analysis/lt_sim.py --self-check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))


def run_machine(conf: np.ndarray, tau_lo: float, tau_hi: float, k: int) -> np.ndarray:
    """Replay the state machine; returns the boolean mask of frames the arm ANSWERS on.

    Mirrors `Dam4SamLtArm.step` exactly, including the two details that are easy to get wrong: the
    `k` frames leading up to a declared loss are already emitted (hysteresis is retrospective, the
    arm cannot un-answer them), and a NaN conf falls through to answering rather than guessing.
    """
    out = np.ones(len(conf), bool)
    lost, low = False, 0
    for i, c in enumerate(conf):
        if not np.isfinite(c):
            continue  # no score this frame: fall through to the plain arm
        if lost:
            if c >= tau_hi:
                lost = False
            else:
                out[i] = False
            continue
        low = low + 1 if c < tau_lo else 0
        if low >= k:
            lost, low = True, 0
            out[i] = False
    return out


def point_metrics(present: np.ndarray, answered: np.ndarray, hit: np.ndarray) -> dict:
    """Metrics at ONE operating point, no max over tau.

    `gm` is `presence.sweep`'s variant with the silence rate substituted for OxUvA's mixing
    parameter, kept only so the numbers line up with what is already in the README. It is DEGENERATE
    for an arm that never abstains -- silence 0 makes it exactly 0 -- so it cannot rank a plain arm
    against an abstaining one.

    `gm_ox` is the published OxUvA MaxGM for a fixed policy: `max over p of sqrt((1-p) TPR
    ((1-p) TNR + p))`, where p mixes the policy with always-report-absent. Solving in u = 1-p gives
    u* = 1/(2(1-TNR)) clipped to 1, so TNR >= 0.5 collapses to sqrt(TPR TNR). That is the number to
    select and report on: a plain arm gets a real, non-zero score, and beating it means something.
    TPR requires a HIT, per OxUvA -- answering in the wrong place is not a true positive.
    """
    pred = answered
    tp = float((pred & hit).sum())
    p = tp / pred.sum() if pred.sum() else 0.0
    r = tp / present.sum() if present.sum() else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    pr = 1 - pred.mean()
    tpr_loc = tp / max(present.sum(), 1)
    tnr = (~pred & ~present).sum() / max((~present).sum(), 1)
    u = min(1.0, 1 / (2 * (1 - tnr))) if tnr < 1 else 1.0
    return {"f_lt": f,
            "gm": float(np.sqrt(pr * (pred & present).sum() / max(present.sum(), 1)
                                * (pr * tnr + (1 - pr)))),
            "gm_ox": float(np.sqrt(tpr_loc * u * (u * tnr + 1 - u))),
            "tpr": float(tpr_loc), "tnr": float(tnr),
            "silence": float(1 - pred.mean()),
            "gap_silence": float((~pred & ~present).sum() / max((~present).sum(), 1))}


def load(run_dir: Path, arm: str) -> list[tuple]:
    """(seq, conf, present, hit, answered_base) for every GAP sequence of `arm`, in name order."""
    import uav123
    from render_overlay import iou

    out = []
    for p in sorted(run_dir.glob("*.json")):
        if p.stem == "manifest":
            continue
        res = json.loads(p.read_text())
        if res["meta"]["arm"] != arm:
            continue
        gt = uav123.boxes(res["meta"]["seq"])
        present = np.array([g is not None for g in gt])
        if present.all():
            continue  # no absent frame: f_lt is 1 by construction, it measures nothing
        rows = {r["i"]: r for r in res["rows"]}
        conf = np.array([rows.get(i, {}).get("conf", None) or np.nan for i in range(len(gt))], float)
        base = np.array([rows.get(i, {}).get("box") is not None for i in range(len(gt))])
        hit = np.array([bool(g is not None and rows.get(i, {}).get("box")
                             and iou(g, rows[i]["box"]) > 0) for i, g in enumerate(gt)])
        out.append((res["meta"]["seq"], conf, present, hit, base))
    return out


def score(seqs: list[tuple], tau_lo: float, tau_hi: float, k: int) -> list[dict]:
    res = []
    for seq, conf, present, hit, base in seqs:
        ans = base & run_machine(conf, tau_lo, tau_hi, k)
        m = point_metrics(present, ans, hit)
        m["seq"] = seq
        res.append(m)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--arm", required=True)
    args = ap.parse_args()

    seqs = load(Path(args.run_dir), args.arm)
    assert seqs, f"no gap sequence for {args.arm} in {args.run_dir}"
    fit = [s for i, s in enumerate(seqs) if i % 2 == 0]
    ev = [s for i, s in enumerate(seqs) if i % 2 == 1]
    print(f"{args.arm}: {len(seqs)} gap seqs -> fit {len(fit)} / eval {len(ev)}")

    # Grid, not the two percentiles `presence.py --thresholds` prints: those are a defensible prior
    # (90% TPR / 5% FPR) but nothing says the OxUvA optimum sits there, and the grid is free here.
    c = np.concatenate([s[1][np.isfinite(s[1])] for s in fit])
    p_ = np.concatenate([s[2][np.isfinite(s[1])] for s in fit])
    los = np.percentile(c[p_], [2, 5, 10, 15, 20, 30])
    his = np.percentile(c[~p_], [70, 80, 90, 95, 98, 99])
    best = None
    for lo in los:
        for hi in his:
            if hi <= lo:
                continue
            for k in (1, 2, 3, 5, 8):
                g = float(np.median([m["gm_ox"] for m in score(fit, lo, hi, k)]))
                if best is None or g > best[0]:
                    best = (g, lo, hi, k)
    g, lo, hi, k = best
    print(f"fit best: tau_lo {lo:.3f}  tau_hi {hi:.3f}  k {k}   gm_ox(fit) {g:.3f}")

    cols = ("gm_ox", "gm", "f_lt", "tpr", "tnr", "silence", "gap_silence")
    print("\n" + f"{'':24s}" + "".join(f"{c[:8]:>9s}" for c in cols))
    for label, ss in (("fit", fit), ("EVAL (out of sample)", ev), ("all 33", seqs)):
        # -inf/-inf/k=1 is the plain arm: never under tau_lo, never lost. Same code path, so any bug
        # in `run_machine` hits both rows and the delta stays honest.
        for tag, r in ((f"{label} lt", score(ss, lo, hi, k)),
                       (f"{label} plain", score(ss, -np.inf, -np.inf, 1))):
            print(f"{tag:24s}" + "".join(f"{np.median([m[c] for m in r]):9.3f}" for c in cols))

    lt, pl = score(ev, lo, hi, k), score(ev, -np.inf, -np.inf, 1)
    d = [a["gm_ox"] - b["gm_ox"] for a, b in zip(lt, pl)]
    print(f"\npor secuencia (EVAL), delta gm_ox lt - plain: "
          f"gana {sum(1 for x in d if x > 0)}/{len(d)}, pierde {sum(1 for x in d if x < 0)}")
    for (a, b) in sorted(zip(lt, pl), key=lambda t: t[0]["gm_ox"] - t[1]["gm_ox"]):
        print(f"  {a['seq']:14s} {b['gm_ox']:.3f} -> {a['gm_ox']:.3f} "
              f"({a['gm_ox'] - b['gm_ox']:+.3f})  silencio en hueco {a['gap_silence']:.2f}  "
              f"f_lt {b['f_lt']:.3f} -> {a['f_lt']:.3f}")


def _check() -> None:
    """The state machine, on a trace where the right answer is written by hand."""
    #        0    1    2     3     4     5    6    7
    c = np.array([9.0, 0.0, 5.0, -2.0, -2.0, -2.0, 3.0, 9.0])
    a = run_machine(c, tau_lo=1.0, tau_hi=8.0, k=3)
    assert a[0] and a[1] and a[2], "one dip below tau_lo is not a loss"
    assert a[3] and a[4], "hysteresis: the k frames leading to the loss still emit"
    assert not a[5], "k consecutive frames under tau_lo declare lost"
    assert not a[6], "3.0 is between the thresholds: must not re-attach"
    assert a[7], "at or above tau_hi comes back"
    assert run_machine(c, -np.inf, -np.inf, 1).all(), "tau_lo -inf is the plain arm"
    assert run_machine(np.full(5, np.nan), 1.0, 8.0, 1).all(), "no score: fall through, do not abstain"

    # metrics: perfect abstention on a 2-present/2-absent trace scores 1 on f_lt
    m = point_metrics(np.array([1, 1, 0, 0], bool), np.array([1, 1, 0, 0], bool),
                      np.array([1, 1, 0, 0], bool))
    assert abs(m["f_lt"] - 1.0) < 1e-9 and m["gap_silence"] == 1.0, m
    assert abs(m["gm_ox"] - 1.0) < 1e-9, m  # TPR=TNR=1 must be a perfect 1, not the mixed bound
    # never abstaining: TNR = 0, so u* = 1/2 and gm_ox = sqrt(TPR/4). The degenerate `gm` is 0.
    n = point_metrics(np.array([1, 1, 0, 0], bool), np.ones(4, bool), np.array([1, 1, 0, 0], bool))
    assert n["gm"] == 0.0 and abs(n["gm_ox"] - 0.5) < 1e-9, n
    print("lt_sim OK")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _check()
    else:
        main()
