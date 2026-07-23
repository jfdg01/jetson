"""Score the E18-n25 matrix: paired ORACLE-vs-COLD PASS, exact McNemar, R-29 ICC
deflation to distinct source clips, Part-IV Holm. Prints a markdown block + the
claims.json fields. Pure read of runs/*/results.json — safe to re-run.

    python score.py            # print report
    python score.py --json     # dump machine-readable dict for claims registration
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
CLIPS = json.loads((HERE / "clips.json").read_text())

# Source-video clustering (R-29): _s variants share the raw sequence with the base.
# UAV123's *_s clips are sub-sequences cut from the same capture. Collapse each into
# its base for the ICC cluster id; everything else is its own cluster.
def source_of(clip: str) -> str:
    return clip[:-2] if clip.endswith("_s") else clip


def class_of(clip: str) -> str:
    base = clip[:-2] if clip.endswith("_s") else clip
    stem = base.rstrip("0123456789")
    return {"bike": "cyclist", "wakeboard": "wakeboarder"}.get(stem, stem)


def passed(d: dict) -> bool:
    s = d.get("score") or {}
    return bool(s.get("genuine_lock")) and float(s.get("coverage") or 0.0) >= 0.50


def load(leg: str, clip: str):
    p = RUNS / f"{leg}_{clip}" / "results.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact binomial McNemar over n=b+c discordant pairs, p=0.5."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def icc1_upper(groups: list[list[int]]) -> tuple[float, float, float]:
    """ICC(1) one-way random effects + its upper 95% bound (Searle), over 0/1
    outcomes grouped by source clip. Returns (point, upper95, n0). Singletons
    contribute to the grand mean but not to within-group variance."""
    groups = [g for g in groups if g]
    k = len(groups)
    N = sum(len(g) for g in groups)
    if k < 2 or N == k:  # no replication anywhere -> no clustering info
        return 0.0, 0.0, 1.0
    grand = sum(sum(g) for g in groups) / N
    ssb = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups)
    ssw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
    dfb, dfw = k - 1, N - k
    msb = ssb / dfb
    msw = ssw / dfw if dfw else 0.0
    # n0: average group size correction for unequal sizes
    n0 = (N - sum(len(g) ** 2 for g in groups) / N) / (k - 1)
    def icc_from_F(F):
        return max(0.0, (F - 1.0) / (F + n0 - 1.0)) if (F + n0 - 1.0) > 0 else 0.0
    F = msb / msw if msw > 0 else float("inf")
    point = 1.0 if math.isinf(F) else icc_from_F(F)
    # upper 95% bound: F_obs / F_crit(0.975 lower tail) per Searle 1971
    from statistics import NormalDist  # only stdlib; approximate F crit via… fallback
    # Exact F quantile needs scipy; use it if present, else conservative point=upper.
    try:
        from scipy.stats import f as fdist  # type: ignore
        Fl = fdist.ppf(0.025, dfb, dfw)
        Fu_ratio = F / Fl if math.isfinite(F) else float("inf")
        upper = 1.0 if math.isinf(Fu_ratio) else icc_from_F(Fu_ratio)
    except Exception:
        upper = 1.0 if math.isinf(F) else min(1.0, icc_from_F(F) * 1.5)
    return point, min(1.0, upper), n0


def main() -> None:
    rows = []
    for c in CLIPS:
        clip = c["clip"]
        o, cd = load("ORACLE", clip), load("COLD", clip)
        rows.append({
            "clip": clip, "class": class_of(clip), "source": source_of(clip),
            "O": o, "C": cd,
            "O_pass": passed(o) if o and "INVALID" not in o else None,
            "C_pass": passed(cd) if cd and "INVALID" not in cd else None,
        })

    complete = [r for r in rows if r["O_pass"] is not None and r["C_pass"] is not None]
    o_pass = sum(r["O_pass"] for r in complete)
    c_pass = sum(r["C_pass"] for r in complete)
    b = sum(1 for r in complete if r["O_pass"] and not r["C_pass"])  # O>C
    cc = sum(1 for r in complete if r["C_pass"] and not r["O_pass"])  # C>O
    p_raw = mcnemar_exact(b, cc)

    # R-29 deflation on the discordant structure: cluster the paired *difference*
    # (O_pass - C_pass in {-1,0,1}) by source; ICC upper bound -> design effect.
    by_src: dict[str, list[int]] = {}
    for r in complete:
        by_src.setdefault(r["source"], []).append(int(r["O_pass"]) - int(r["C_pass"]))
    icc, icc_u, n0 = icc1_upper(list(by_src.values()))
    n_rows = len(complete)
    n_src = len(by_src)
    deff = 1.0 + (n0 - 1.0) * icc_u
    n_eff = round(n_rows / deff) if deff > 0 else n_rows
    n_eff = max(n_src, min(n_rows, n_eff))  # never below collapse floor, never above n
    # deflate the discordant counts proportionally, then re-test
    scale = n_eff / n_rows if n_rows else 1.0
    b_def, c_def = round(b * scale), round(cc * scale)
    p_def = mcnemar_exact(b_def, c_def)
    p_holm = min(1.0, p_def * 4)  # Part-IV family ~4 primary claims (Holm worst case)

    out = {
        "o_pass": o_pass, "c_pass": c_pass, "n": n_rows, "n_src": n_src,
        "b_O>C": b, "c_C>O": cc, "p_raw": p_raw,
        "icc_point": round(icc, 4), "icc_upper95": round(icc_u, 4), "n0": round(n0, 3),
        "deff": round(deff, 4), "n_eff": n_eff, "collapsed_floor": n_src,
        "b_def": b_def, "c_def": c_def, "p_deflated": p_def, "p_holm_partIV": p_holm,
        "incomplete": [r["clip"] for r in rows if r["O_pass"] is None or r["C_pass"] is None],
    }
    if "--json" in sys.argv:
        print(json.dumps({"summary": out, "rows": [
            {k: r[k] for k in ("clip", "class", "source", "O_pass", "C_pass")} for r in rows
        ]}, indent=2))
        return

    print(f"# E18-n25 scoring  ({n_rows}/25 complete)\n")
    print("| clip | class | O | C | O gl/cov | C gl/cov | C mean_iou | disc |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        o, cd = r["O"], r["C"]
        def cell(d, isp):
            if d is None:
                return "…"
            if "INVALID" in d:
                return "INVALID"
            s = d["score"]
            return f"{'Y' if isp else 'n'} {s['genuine_lock']}/{s['coverage']}"
        cdi = ""
        if cd and "INVALID" not in cd:
            cdi = f"{cd['score'].get('mean_iou', '-')}"
        disc = ""
        if r["O_pass"] is not None and r["C_pass"] is not None:
            disc = "O>C" if (r["O_pass"] and not r["C_pass"]) else ("C>O" if (r["C_pass"] and not r["O_pass"]) else "=")
        print(f"| {r['clip']} | {r['class']} | {'Y' if r['O_pass'] else ('n' if r['O_pass'] is not None else '…')} "
              f"| {'Y' if r['C_pass'] else ('n' if r['C_pass'] is not None else '…')} "
              f"| {cell(o, r['O_pass'])} | {cell(cd, r['C_pass'])} | {cdi} | {disc} |")
    print()
    for k, v in out.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
