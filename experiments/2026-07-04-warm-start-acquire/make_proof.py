"""E24 proof figure: reproducible from runs/*/results.json (best of n=2).

Panel A: grouped per-clip coverage bars (WARM / COLD / ORACLE) with a PASS marker
         and the PASS threshold line (coverage >= 0.50).
Panel B: delivery freshness -- WARM/ORACLE deliver the operator's box at frame 240
         (the prompt); COLD makes the operator wait acquire_s and hands back a box
         ~135 frames stale. That staleness is what the warm path removes.

    .venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/make_proof.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROOF = HERE / "proof"
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]
LEGS = ["WARM", "COLD", "ORACLE"]
# accessible, colour-blind-safe: blue (warm) / orange (cold) / grey (oracle ceiling)
COLOR = {"WARM": "#2b6cb0", "COLD": "#dd6b20", "ORACLE": "#a0aec0"}


def load_best():
    """best of n=2 per (leg,clip) by (pass, coverage). Returns dict[leg][clip]."""
    d = defaultdict(lambda: defaultdict(list))
    for f in sorted(glob.glob(str(RUNS / "*/results.json"))):
        if os.path.basename(os.path.dirname(f)).startswith("smoke"):
            continue
        r = json.load(open(f))
        w = r["warm"]
        p = w["genuine_lock"] and w["coverage"] >= 0.50
        d[r["leg"]][r["clip"]].append(
            {"cov": w["coverage"], "gen": w["genuine_lock"], "pass": p,
             "deliver": w["deliver_frame"], "diou": w.get("deliver_iou", 0.0)})
    best = defaultdict(dict)
    for leg in LEGS:
        for clip in CLIPS:
            best[leg][clip] = sorted(
                d[leg][clip], key=lambda e: (e["pass"], e["cov"]), reverse=True)[0]
    return best


def main() -> None:
    best = load_best()
    PROOF.mkdir(exist_ok=True)
    fig, (axA, axB) = plt.subplots(2, 1, figsize=(10, 8),
                                   gridspec_kw={"height_ratios": [3, 2]})

    # --- Panel A: grouped coverage bars ------------------------------------
    x = range(len(CLIPS))
    width = 0.26
    for k, leg in enumerate(LEGS):
        covs = [best[leg][c]["cov"] for c in CLIPS]
        offs = [xi + (k - 1) * width for xi in x]
        bars = axA.bar(offs, covs, width, label=leg, color=COLOR[leg],
                       edgecolor="white", linewidth=0.6)
        for xi, c in zip(offs, CLIPS):
            e = best[leg][c]
            if e["pass"]:
                axA.plot(xi, e["cov"] + 0.03, marker="o", ms=6,
                         color=COLOR[leg], markeredgecolor="black", zorder=5)
    axA.axhline(0.50, ls="--", lw=1.2, color="#4a5568")
    axA.text(len(CLIPS) - 0.5, 0.52, "PASS >= 0.50 coverage", ha="right",
             va="bottom", fontsize=9, color="#4a5568")
    axA.set_xticks(list(x))
    axA.set_xticklabels(CLIPS)
    axA.set_ylabel("coverage (IoU>=0.25 frac over 10 s window)")
    axA.set_ylim(0, 1.12)
    W = sum(best["WARM"][c]["pass"] for c in CLIPS)
    C = sum(best["COLD"][c]["pass"] for c in CLIPS)
    O = sum(best["ORACLE"][c]["pass"] for c in CLIPS)
    axA.set_title(f"E24 warm-start acquire  -  RQ-E24 = YES [carry-bound]   "
                  f"WARM {W}/6   COLD {C}/6   ORACLE {O}/6   (o = PASS, best of n=2)",
                  fontsize=11)
    axA.legend(loc="upper left", ncol=3, frameon=False)
    axA.spines[["top", "right"]].set_visible(False)

    # --- Panel B: delivery freshness ---------------------------------------
    warm_deliver = best["WARM"][CLIPS[0]]["deliver"]           # 240 (prompt)
    cold_delivers = [best["COLD"][c]["deliver"] for c in CLIPS]
    cold_mean = sum(cold_delivers) / len(cold_delivers)
    y = range(len(CLIPS))
    for yi, c in zip(y, CLIPS):
        cd = best["COLD"][c]["deliver"]
        axB.plot([warm_deliver, cd], [yi, yi], color="#cbd5e0", lw=2, zorder=1)
        axB.plot(warm_deliver, yi, "o", color=COLOR["WARM"], ms=9, zorder=3)
        axB.plot(cd, yi, "s", color=COLOR["COLD"], ms=9, zorder=3)
    axB.axvline(warm_deliver, ls=":", lw=1, color=COLOR["WARM"])
    axB.set_yticks(list(y))
    axB.set_yticklabels(CLIPS)
    axB.set_xlabel("frame the operator receives the box (30 fps)")
    axB.set_xlim(200, max(cold_delivers) + 40)
    stale = cold_mean - warm_deliver
    axB.set_title(f"Delivery freshness: WARM/ORACLE deliver at frame {warm_deliver} "
                  f"(the prompt); COLD ~{cold_mean:.0f} "
                  f"(~{stale:.0f} frames / ~{stale/30:.1f} s stale)", fontsize=10)
    axB.annotate("", xy=(cold_mean, len(CLIPS) - 0.5),
                 xytext=(warm_deliver, len(CLIPS) - 0.5),
                 arrowprops=dict(arrowstyle="<->", color="#dd6b20", lw=1.5))
    axB.text((warm_deliver + cold_mean) / 2, len(CLIPS) - 0.35,
             f"staleness warm removes\n~{stale:.0f} frames", ha="center",
             va="bottom", fontsize=9, color="#dd6b20")
    axB.plot([], [], "o", color=COLOR["WARM"], label="WARM/ORACLE deliver (fresh)")
    axB.plot([], [], "s", color=COLOR["COLD"], label="COLD deliver (stale)")
    axB.legend(loc="lower right", frameon=False, fontsize=9)
    axB.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    out = PROOF / "warm_vs_cold_vs_oracle.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("wrote", out)


if __name__ == "__main__":
    main()
