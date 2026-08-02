"""Is the arm's `conf` a usable presence signal, and what does abstention buy?

Three numbers, all threshold-free, because we do not know the operating point yet:

  * `presence_auc` -- ROC AUC of `conf` as a binary classifier of "GT present this frame". 0.5 is a
    coin flip. Rank-based, so the 2.4% prevalence of absent frames does not flatter it the way
    accuracy would (always-present already scores 97.6%).
  * `f_lt` -- VOT-LT F-score, `max over tau of 2PR/(P+R)`. Maximising over the threshold is why an
    UNCALIBRATED score is fine: only the ordering has to carry information.
  * `maxgm` -- OxUvA, `max over tau of sqrt((1-p) * TPR * ((1-p) * TNR + p))`, where p is the rate
    of frames the tracker declined to answer at all. Rewards abstaining over guessing, which is the
    axis `asym_b` fails on -- 2683 gap frames, 2683 answers.

Pre-registered read (2026-07-30, before looking): presence_auc >= 0.75 the surrogate is usable and
the re-detection state machine gets built on it; < 0.65 it is dead and we go to a cosine verifier
or to a tracker with a trained score head. Between, build the cosine verifier and compare.

Reported as the MEDIAN over sequences, not pooled: only 33 of 123 UAV123 sequences have any absent
frame and `bird1_3` alone holds 15% of them, so a pooled number is three clips wearing a trenchcoat.
The pooled figure is printed beside it, labelled.

    analysis/presence.py raw/asym-conf
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def roc_auc(y: np.ndarray, s: np.ndarray) -> float:
    """AUC via the rank identity (Mann-Whitney U). Ties get average rank, which is what makes a
    constant score come out at exactly 0.5 instead of 0 or 1."""
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), float)
    ranks[order] = np.arange(1, len(s) + 1)
    # average the ranks inside each tied group
    su = s[order]
    i = 0
    while i < len(su):
        j = i
        while j + 1 < len(su) and su[j + 1] == su[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    npos = int(y.sum())
    nneg = len(y) - npos
    if npos == 0 or nneg == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def sweep(present: np.ndarray, conf: np.ndarray, answered: np.ndarray, hit: np.ndarray) -> dict:
    """F-score and MaxGM over every threshold the data actually distinguishes.

    A frame counts as a prediction only if the arm answered AND conf >= tau. `hit` (IoU > 0) is what
    separates "predicted something and was right" from "predicted something anywhere", which is the
    difference between VOT-LT precision and a presence classifier.
    """
    taus = np.unique(np.concatenate([conf[np.isfinite(conf)], [np.inf]]))
    best_f, best_gm = 0.0, 0.0
    for t in taus:
        pred = answered & (conf >= t)
        tp = float((pred & hit).sum())
        if pred.sum() and present.sum():
            p, r = tp / pred.sum(), tp / present.sum()
            if p + r:
                best_f = max(best_f, 2 * p * r / (p + r))
        # OxUvA: rate of declined frames enters as p, so silence is neither a hit nor a miss
        pr = 1 - pred.mean()
        tpr = (pred & present).sum() / max(present.sum(), 1)
        tnr = (~pred & ~present).sum() / max((~present).sum(), 1)
        best_gm = max(best_gm, float(np.sqrt(pr * tpr * (pr * tnr + (1 - pr)))))
    return {"f_lt": best_f, "maxgm": best_gm}


def score_one(path: Path, gt: list) -> dict | None:
    res = json.loads(path.read_text())
    meta, rows = res["meta"], {r["i"]: r for r in res["rows"]}
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from render_overlay import iou

    conf = np.array([rows.get(i, {}).get("conf", None) or np.nan for i in range(len(gt))], float)
    if not np.isfinite(conf).any():
        return None  # arm has no presence signal; not the same as having a bad one
    present = np.array([g is not None for g in gt])
    answered = np.array([rows.get(i, {}).get("box") is not None for i in range(len(gt))])
    hit = np.array([bool(g is not None and rows.get(i, {}).get("box")
                         and iou(g, rows[i]["box"]) > 0) for i, g in enumerate(gt)])
    ok = np.isfinite(conf)
    out = {"arm": meta["arm"], "seq": meta["seq"], "gap": int((~present).sum()),
           "presence_auc": roc_auc(present[ok].astype(int), conf[ok]) if (~present[ok]).any()
           else float("nan")}
    out.update(sweep(present[ok], conf[ok], answered[ok], hit[ok]))
    # second, independent verifier: NCC against the frame-0 template. Scored the same way and on the
    # same frames, so the two AUCs are directly comparable -- which is the whole point of having it.
    cos = np.array([rows.get(i, {}).get("conf_cos", None) or np.nan for i in range(len(gt))], float)
    ok2 = np.isfinite(cos)
    out["cos_auc"] = (roc_auc(present[ok2].astype(int), cos[ok2])
                      if ok2.any() and (~present[ok2]).any() else float("nan"))
    return out


def thresholds(run_dir: Path) -> None:
    """Fit `tau_lo` / `tau_hi` for the long-term state machine, out of sample.

    `tau_lo` = the conf at 90% TPR (the 10th percentile over PRESENT frames): the machine only
    declares a loss when the score is clearly bad. `tau_hi` = the conf at 5% FPR (the 95th
    percentile over ABSENT frames): coming back needs strong evidence. Two thresholds because one
    oscillates on the boundary.

    Fitted on the even-indexed gap sequences, evaluated on the odd ones -- ~16/17 each. Small, but
    it is the difference between a threshold and a threshold chosen so the result comes out right.
    The eval half is printed because that, not all 33, is what the `asym_lt` run scores on.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import data

    gapped = []
    for p in sorted(run_dir.glob("*.json")):
        if p.stem == "manifest":
            continue
        seq = json.loads(p.read_text())["meta"]["seq"]
        gt = data.boxes(seq)
        if all(g is not None for g in gt):
            continue
        res = json.loads(p.read_text())
        rows = {r["i"]: r for r in res["rows"]}
        conf = np.array([rows.get(i, {}).get("conf", None) or np.nan for i in range(len(gt))], float)
        present = np.array([g is not None for g in gt])
        ok = np.isfinite(conf)
        gapped.append((seq, conf[ok], present[ok]))

    fit = [g for i, g in enumerate(gapped) if i % 2 == 0]
    ev = [g for i, g in enumerate(gapped) if i % 2 == 1]
    assert fit and ev, "need gap sequences on both sides of the split"
    c = np.concatenate([g[1] for g in fit])
    p_ = np.concatenate([g[2] for g in fit])
    tau_lo = float(np.percentile(c[p_], 10))
    tau_hi = float(np.percentile(c[~p_], 95))
    print(f"fit on {len(fit)} seqs ({p_.sum()} present, {(~p_).sum()} absent)")
    print(f"tau_lo = {tau_lo:.4f}   (conf at 90% TPR)")
    print(f"tau_hi = {tau_hi:.4f}   (conf at  5% FPR)")
    if tau_hi <= tau_lo:
        print("WARNING: tau_hi <= tau_lo, the two classes barely separate; hysteresis is a fiction")
    print(f"eval seqs ({len(ev)}): " + ",".join(g[0] for g in ev))


def paired(per: list[dict], ref: str) -> None:
    """Every other arm against `ref` on the sequences BOTH ran, Wilcoxon signed-rank.

    Medians of medians across arms mislead as soon as the sequence sets differ, and here they do:
    the `upscales` gate drops the six 720x480 `uav*` clips for an arm at 768, so a 33-sequence
    median gets compared against a 27-sequence one. The paired contrast is the only honest read.
    """
    from scipy.stats import wilcoxon

    by = {}
    for r in per:
        if r["gap"] > 0:
            by.setdefault(r["arm"], {})[r["seq"]] = r
    assert ref in by, f"{ref} not among {sorted(by)}"
    print(f"\npareado contra {ref} (solo secuencias con hueco que corrieron ambos brazos)")
    print(f"{'arm':13s} {'n':>3s} " + " ".join(f"{m:>11s} {'p':>7s}" for m in
                                               ("presence_auc", "f_lt", "maxgm")))
    for a in sorted(by):
        if a == ref:
            continue
        common = sorted(set(by[a]) & set(by[ref]))
        line = f"{a:13s} {len(common):3d} "
        for m in ("presence_auc", "f_lt", "maxgm"):
            d = np.array([by[a][s][m] - by[ref][s][m] for s in common])
            p = wilcoxon(d).pvalue if np.any(d) else 1.0
            line += f" {np.median(d):+11.3f} {p:7.4f}"
        print(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="+", help="one or more; results are pooled by arm")
    ap.add_argument("--thresholds", action="store_true",
                    help="fit the long-term tau_lo/tau_hi instead of scoring")
    ap.add_argument("--vs", metavar="ARM",
                    help="also print a paired Wilcoxon of every other arm against ARM")
    args = ap.parse_args()
    if args.thresholds:
        return thresholds(Path(args.run_dir[0]))
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import data

    per = []
    for d in args.run_dir:
        for p in sorted(Path(d).glob("*.json")):
            if p.stem == "manifest":
                continue
            r = score_one(p, data.boxes(json.loads(p.read_text())["meta"]["seq"]))
            if r:
                per.append(r)
    assert per, f"no arm in {args.run_dir} recorded a conf signal"

    # everything is medianed over the GAP sequences only. On a sequence with no absent frame an
    # always-answer tracker scores f_lt = 1 by construction, so pooling the other 90 in reports the
    # dataset's prevalence rather than the arm's behaviour.
    print(f"{'arm':11s} {'n':>3s} {'gap':>4s} {'presence_auc':>13s} {'cos_auc':>8s} {'f_lt':>7s} "
          f"{'maxgm':>7s} {'auc<0.5':>8s}")
    for a in sorted({r["arm"] for r in per}):
        g = [r for r in per if r["arm"] == a]
        gapped = [r for r in g if r["gap"] > 0]
        if not gapped:
            print(f"{a:11s} {len(g):3d}    0  (no gap sequence in this run)")
            continue
        auc = [r["presence_auc"] for r in gapped]
        print(f"{a:11s} {len(g):3d} {len(gapped):4d} {np.median(auc):13.3f} "
              f"{np.nanmedian([r['cos_auc'] for r in gapped]):8.3f} "
              f"{np.median([r['f_lt'] for r in gapped]):7.3f} "
              f"{np.median([r['maxgm'] for r in gapped]):7.3f} "
              f"{sum(1 for v in auc if v < 0.5):5d}/{len(auc):<3d}")
        w = sorted(gapped, key=lambda r: r["presence_auc"])[:5]
        print("    peores: " + ", ".join(f"{r['seq']} {r['presence_auc']:.2f}" for r in w))
        # A sequence's AUC rests on its ABSENT frames, and seven of the 33 have fewer than 25 --
        # uav6 has five. Gating at 25 barely moves the median (0.711 -> 0.715 on asym_b) and drops
        # two of the five inversions, which is the point: the surrogate is uniformly mediocre, not
        # good on some clips and broken on others. Printed rather than substituted, because the
        # ungated median is what the pre-registration named.
        big = [r for r in gapped if r["gap"] >= 25]
        if big and len(big) != len(gapped):
            b = [r["presence_auc"] for r in big]
            print(f"    huecos >= 25 fr: n={len(big)}  auc {np.median(b):.3f}  "
                  f"por debajo de 0.5: {sum(1 for v in b if v < 0.5)}")
    if args.vs:
        paired(per, args.vs)


def _check() -> None:
    """A perfect score, an inverted one and a constant one, since those are the three readings that
    decide the experiment and a sign slip between them is invisible in a plausible-looking 0.6."""
    y = np.array([1, 1, 1, 0, 0, 0])
    assert roc_auc(y, np.array([9.0, 8, 7, 3, 2, 1])) == 1.0
    assert roc_auc(y, np.array([1.0, 2, 3, 7, 8, 9])) == 0.0
    assert roc_auc(y, np.full(6, 5.0)) == 0.5
    # direction check: high conf on present frames must read ABOVE 0.5, not below
    present = np.array([True] * 3 + [False] * 3)
    assert roc_auc(present.astype(int), np.array([9.0, 8, 7, 3, 2, 1])) == 1.0
    print("presence OK")


if __name__ == "__main__":
    import sys
    if "--self-check" in sys.argv:
        _check()
    else:
        main()
