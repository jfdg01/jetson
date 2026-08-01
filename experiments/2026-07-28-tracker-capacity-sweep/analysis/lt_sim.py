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


def run_machine_rel(conf: np.ndarray, a: float, b: float, k: int, w: int, freeze: bool) -> np.ndarray:
    """Same machine, but the threshold is relative to the arm's OWN logits instead of a constant.

    A global tau assumes `object_score_logits` is calibrated across sequences. It is not: five of the
    six worst losses have presence_auc >= 0.86, so the ordering inside the clip is fine and only the
    cut point is wrong. So take mu/sigma over the last `w` frames the machine believes are on-target
    and cut at `mu - a sigma` (lose) / `mu - b sigma` (come back), b <= a.

    Causal by construction -- it only ever looks at frames already emitted -- which is what makes it
    deployable, not just a better offline fit. The first `w` frames always answer: the operator just
    designated the target, so it is present, and that is the same assumption the tracker's own init
    makes. `freeze` keeps that designation window as the reference forever instead of sliding it;
    sliding adapts to illumination drift, freezing cannot be dragged down by a slow failure.
    """
    out = np.ones(len(conf), bool)
    buf: list[float] = []
    lost, low = False, 0
    for i, c in enumerate(conf):
        if not np.isfinite(c):
            continue  # no score this frame: fall through to the plain arm
        if len(buf) < w:
            buf.append(c)
            continue
        m, s = float(np.mean(buf)), float(np.std(buf)) + 1e-6
        if lost:
            if c >= m - b * s:
                lost = False
            else:
                out[i] = False
                continue
        else:
            low = low + 1 if c < m - a * s else 0
            if low >= k:
                lost, low = True, 0
                out[i] = False
                continue
        if not freeze:
            buf.append(c)
            del buf[0]
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


def score(seqs: list[tuple], machine) -> list[dict]:
    """`machine` maps a conf trace to the mask of frames it answers on -- either `run_machine`
    partially applied or `run_machine_rel`, so both policies go through the same metric code."""
    res = []
    for seq, conf, present, hit, base in seqs:
        m = point_metrics(present, base & machine(conf), hit)
        m["seq"] = seq
        res.append(m)
    return res


PLAIN = lambda c: run_machine(c, -np.inf, -np.inf, 1)  # noqa: E731 -- never lost, i.e. no LT at all


def rel_cands() -> list[tuple]:
    """The relative-threshold grid. `w` in frames at ~30 fps, so 30 is one second of designation
    and 300 ten -- long enough to span a slow appearance change."""
    return [(f"rel a {a:.1f} b {b:.1f} k {k} w {w} {'fijo' if fz else 'movil'}",
             (lambda a=a, b=b, k=k, w=w, fz=fz: (lambda c: run_machine_rel(c, a, b, k, w, fz)))())
            for a in (1.0, 1.5, 2.0, 3.0, 4.0) for b in (0.0, 1.0, 2.0) if b <= a
            for k in (1, 2, 3, 5) for w in (30, 100, 300) for fz in (True, False)]


def cv(seqs: list[tuple]) -> None:
    """Leave-one-sequence-out over the relative grid: does the fitted (a,b,k,w) survive resampling?

    The deployed `dam4sam_lt` constants come from ONE even/odd split of these same sequences, so the
    reported out-of-sample number is a sample of size one from the distribution of splits. LOO gives
    the other 32: each fold selects on 32 sequences and scores the held-out one, so every sequence is
    out-of-sample exactly once and the spread of selected constants is visible instead of assumed.

    Only the relative machine is cross-validated. The fixed grid's thresholds are percentiles of the
    fit fold's own logits, so a shared grid would leak the held-out sequence into the candidate set;
    the relative grid is scale-free constants and leaks nothing.

    The cache is what makes this cheap: 360 candidates x 33 sequences of state machine, once, and
    every fold is then a median over columns.
    """
    cands = rel_cands()
    g = np.array([[m["gm_ox"] for m in score(seqs, mach)] for _, mach in cands])  # cand x seq
    plain = np.array([m["gm_ox"] for m in score(seqs, PLAIN)])
    n = len(seqs)
    print(f"LOO sobre {len(cands)} candidatos relativos, {n} secuencias con hueco\n")

    picks, held = [], []
    for j in range(n):
        other = [i for i in range(n) if i != j]
        best = int(np.argmax(np.median(g[:, other], axis=1)))
        picks.append(cands[best][0])
        held.append(g[best, j] - plain[j])
    import collections
    print("constantes elegidas por fold:")
    for name, c in collections.Counter(picks).most_common():
        print(f"  {c:2d}/{n}  {name}")

    from scipy.stats import wilcoxon
    p = lambda x: wilcoxon(x).pvalue if np.any(x) else 1.0  # noqa: E731
    d = np.array(held)
    print(f"\nLOO fuera de muestra contra plain: gana {int((d > 0).sum())}/{n}  "
          f"mediana {np.median(d):+.3f}  media {np.mean(d):+.3f}  peor {d.min():+.3f}  "
          f"p {p(d):.4f}")

    order = np.argsort(d)
    print("\npeores y mejores folds (secuencia, delta, constantes que eligieron las otras 32):")
    for j in list(order[:4]) + list(order[-3:]):
        print(f"  {seqs[j][0]:14s} {d[j]:+.3f}  {picks[j]}")

    # the deployed constants, scored on every sequence, as the thing LOO is judging
    dep = next(m for nm, m in cands if nm == "rel a 4.0 b 2.0 k 1 w 300 movil")
    dd = np.array([m["gm_ox"] for m in score(seqs, dep)]) - plain
    print(f"desplegado (a 4.0 b 2.0 k 1 w 300 movil), en las {n}: gana "
          f"{int((dd > 0).sum())}/{n}  mediana {np.median(dd):+.3f}  media {np.mean(dd):+.3f}  "
          f"peor {dd.min():+.3f}  p {p(dd):.4f}")
    # how far the deployed pick is from each fold's own optimum, in ranks
    rank = np.median(g, axis=1).argsort()[::-1].tolist()
    dep_i = [i for i, (nm, _) in enumerate(cands) if nm == "rel a 4.0 b 2.0 k 1 w 300 movil"][0]
    print(f"rango del desplegado por mediana global: {rank.index(dep_i) + 1}/{len(cands)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--cv", action="store_true", help="leave-one-sequence-out over the rel grid")
    args = ap.parse_args()

    seqs = load(Path(args.run_dir), args.arm)
    assert seqs, f"no gap sequence for {args.arm} in {args.run_dir}"
    if args.cv:
        return cv(seqs)
    fit = [s for i, s in enumerate(seqs) if i % 2 == 0]
    ev = [s for i, s in enumerate(seqs) if i % 2 == 1]
    print(f"{args.arm}: {len(seqs)} gap seqs -> fit {len(fit)} / eval {len(ev)}")

    # Grid, not the two percentiles `presence.py --thresholds` prints: those are a defensible prior
    # (90% TPR / 5% FPR) but nothing says the OxUvA optimum sits there, and the grid is free here.
    c = np.concatenate([s[1][np.isfinite(s[1])] for s in fit])
    p_ = np.concatenate([s[2][np.isfinite(s[1])] for s in fit])
    los = np.percentile(c[p_], [2, 5, 10, 15, 20, 30])
    his = np.percentile(c[~p_], [70, 80, 90, 95, 98, 99])
    cands = [(f"fijo lo {lo:.3f} hi {hi:.3f} k {k}",
              (lambda lo=lo, hi=hi, k=k: (lambda c: run_machine(c, lo, hi, k)))())
             for lo in los for hi in his if hi > lo for k in (1, 2, 3, 5, 8)]
    # Relative: cut at mu - a sigma over the last `w` on-target frames.
    cands += rel_cands()

    def pick(pool):
        return max(pool, key=lambda t: np.median([m["gm_ox"] for m in score(fit, t[1])]))

    fixed = pick([t for t in cands if t[0].startswith("fijo")])
    rel = pick([t for t in cands if t[0].startswith("rel")])
    cols = ("gm_ox", "gm", "f_lt", "tpr", "tnr", "silence", "gap_silence")
    for name, _ in (fixed, rel):
        print(f"fit best {name}")
    print("\n" + f"{'':26s}" + "".join(f"{c[:8]:>9s}" for c in cols))
    for label, ss in (("fit", fit), ("EVAL (fuera de muestra)", ev), ("todas 33", seqs)):
        # `PLAIN` is the same code path with the thresholds at -inf, so any bug in `run_machine` hits
        # the baseline row too and the delta stays honest.
        for tag, mach in ((f"{label} fijo", fixed[1]), (f"{label} rel", rel[1]),
                          (f"{label} plain", PLAIN)):
            r = score(ss, mach)
            print(f"{tag:26s}" + "".join(f"{np.median([m[c] for m in r]):9.3f}" for c in cols))

    for label, ss in (("EVAL", ev), ("todas 33", seqs)):
        pl = score(ss, PLAIN)
        for name, mach in (fixed, rel):
            d = [a["gm_ox"] - b["gm_ox"] for a, b in zip(score(ss, mach), pl)]
            print(f"{label:9s} {name:34s} gana {sum(1 for x in d if x > 0):2d}/{len(d)}  "
                  f"mediana {np.median(d):+.3f}  media {np.mean(d):+.3f}  "
                  f"peor {min(d):+.3f}  d f_lt {np.median([a['f_lt'] - b['f_lt'] for a, b in zip(score(ss, mach), pl)]):+.3f}")

    lt, pl = score(ev, rel[1]), score(ev, PLAIN)
    print("\npor secuencia (EVAL), umbral relativo contra plain:")
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

    # relative: the same trace shifted by +1000 must give the SAME mask. That invariance to absolute
    # scale is the entire reason this variant exists.
    r = np.concatenate([10.0 + np.arange(30) % 3, [0.0, 0.0, 0.0], np.full(5, 11.0)])
    ma = run_machine_rel(r, a=2.0, b=1.0, k=1, w=30, freeze=True)
    assert ma[:30].all(), "the designation window always answers"
    assert not ma[30:33].any(), "a collapse far under mu - 2 sigma is a loss"
    assert ma[33:].all(), "back over mu - 1 sigma re-attaches"
    assert (run_machine_rel(r + 1000, 2.0, 1.0, 1, 30, True) == ma).all(), "must be scale-invariant"
    assert run_machine_rel(np.full(40, 5.0), 2.0, 1.0, 1, 30, True).all(), "constant conf: never lost"

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
