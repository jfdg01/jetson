"""Scoring + proof figures for P6.7 (the handoff seam).

Reads runs/p67/matrix/results.json (and, if present, runs/p67/jump/results.json and
runs/p67/residency/results.json), applies the FROZEN gates from the README, and writes:

  proof/stage-budget.png   -- where the ~6.5 s goes: the COLD start-up decomposed into
                                ssh_spawn / import / weights / warmup_init / drain, with
                                the WARM bar beside it. The figure the complaint asks for.
  proof/paired-handoff.png   -- per-clip paired t_handoff, COLD vs WARM, both lags, with
                                medians and the Wilcoxon p (G1).
  proof/quality-paired.png  -- per-clip paired post-live median IoU (G2) + box_frac, so a
                                latency win that cost the track would be visible.
  proof/seam-COLD.png /      -- the viewed overlays: same designation instant, the frame the
  proof/seam-WARM.png           tracker first goes live on in each arm (I5).

  .venv-ft/bin/python experiments/2026-07-25-handoff-latency/make_proof.py
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402

HERE = Path(__file__).resolve().parent
PROOF = HERE / "proof"
STAGES = ["ssh_spawn", "import", "weights", "warmup_init", "drain"]
STAGE_C = ["#7a7a7a", "#c46b1e", "#b02020", "#2f6fb0", "#1f9e5a"]
G1_MEDIAN = 1.0      # WARM median t_handoff, seconds
G2_SLACK = 0.02      # WARM median IoU may sit at most this far below COLD's


def load(p: Path):
    return json.loads(p.read_text())


def pair(cells, lag, key):
    """Per-clip (cold, warm) for one metric at one lag; drops clips missing either side."""
    idx = {(c["clip"], c["arm"]): c for c in cells if c["lag_s"] == lag}
    clips = sorted({c["clip"] for c in cells})
    out = []
    for name in clips:
        a, b = idx.get((name, "COLD")), idx.get((name, "WARM"))
        if a is None or b is None:
            continue
        if a.get(key) is None or b.get(key) is None:
            continue
        out.append((name, a[key], b[key]))
    return out


def wilcox(rows):
    """Two-sided Wilcoxon on the paired differences; None if nothing discordant.

    Default method on purpose, NOT method="exact": thesis/claims.json is scored by
    grounding/stats.py::paired_continuous, which uses the default, and a figure that
    disagreed with the registry would be a second number for the same test. The two
    differ here — one pair of clips shares an identical |difference| at lag 4.85 s, and
    that tie sends scipy to the normal approximation (1.228e-05 rather than the exact
    5.96e-08 floor). The registry's value is the conservative one; quote it.
    """
    d = np.array([w - c for _, c, w in rows], dtype=float)
    if not len(d) or not np.any(d != 0):
        return None, len(d)
    return float(wilcoxon(d, alternative="two-sided").pvalue), len(d)


# ---- figures -----------------------------------------------------------------
def fig_stages(cells, lags):
    cold = [c for c in cells if c["arm"] == "COLD"]
    warm = [c for c in cells if c["arm"] == "WARM"]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    labels, bars = [], []
    for arm, cs in (("COLD", cold), ("WARM", warm)):
        for lag in lags:
            sel = [c for c in cs if c["lag_s"] == lag]
            if not sel:
                continue
            labels.append(f"{arm}\nlag {lag:g} s")
            bars.append([float(np.median([c["stages"].get(s, 0.0) for c in sel]))
                         for s in STAGES])
    x = np.arange(len(labels))
    bot = np.zeros(len(labels))
    for si, (s, col) in enumerate(zip(STAGES, STAGE_C)):
        v = np.array([b[si] for b in bars])
        ax.bar(x, v, 0.6, bottom=bot, color=col, label=s)
        bot += v
    for xi, tot in zip(x, bot):
        ax.text(xi, tot + 0.12, f"{tot:.2f} s", ha="center", fontsize=9)
    ax.axhline(G1_MEDIAN, ls="--", lw=1, color="#b02020")
    ax.text(len(labels) - 0.45, G1_MEDIAN + 0.08, "G1 = 1.0 s", color="#b02020",
            fontsize=8, ha="right")
    ax.set_xticks(x, labels)
    ax.set_ylabel("median seconds, designation to live tracker")
    ax.set_title("P6.7 -- where the handoff time goes (Jetson Orin Nano, SAM2 @512)")
    ax.legend(fontsize=8, ncol=3, loc="upper center")
    ax.set_ylim(0, max(bot) * 1.30)
    fig.tight_layout()
    fig.savefig(PROOF / "stage-budget.png", dpi=150)
    plt.close(fig)


def fig_paired(cells, lags, stats):
    fig, axes = plt.subplots(1, len(lags), figsize=(5.0 * len(lags), 4.4), squeeze=False)
    for ax, lag in zip(axes[0], lags):
        rows = pair(cells, lag, "t_handoff")
        for i, (_, c, w) in enumerate(rows):
            ax.plot([0, 1], [c, w], "-", color="#bbbbbb", lw=0.8, zorder=1)
        ax.scatter([0] * len(rows), [r[1] for r in rows], s=22, color="#b02020",
                   zorder=2, label="COLD")
        ax.scatter([1] * len(rows), [r[2] for r in rows], s=22, color="#1f9e5a",
                   zorder=2, label="WARM")
        mc = np.median([r[1] for r in rows]) if rows else float("nan")
        mw = np.median([r[2] for r in rows]) if rows else float("nan")
        ax.axhline(G1_MEDIAN, ls="--", lw=1, color="#444")
        st = stats["G1"][str(lag)]
        ax.set_title(f"lag {lag:g} s  |  median {mc:.2f} s -> {mw:.2f} s\n"
                     f"n={st['n']}, Wilcoxon p={st['p']:.2g}" if st["p"] is not None
                     else f"lag {lag:g} s  |  median {mc:.2f} s -> {mw:.2f} s")
        ax.set_xticks([0, 1], ["COLD", "WARM"])
        ax.set_xlim(-0.4, 1.4)
        ax.set_ylabel("t_handoff (s)")
        ax.set_yscale("log")
    fig.suptitle("P6.7 -- designation to live tracker, paired per CARLA clip (n=25)")
    fig.tight_layout()
    fig.savefig(PROOF / "paired-handoff.png", dpi=150)
    plt.close(fig)


def fig_quality(cells, lags, stats):
    fig, axes = plt.subplots(2, len(lags), figsize=(6.2 * len(lags), 6.6), squeeze=False)
    for j, lag in enumerate(lags):
        for i, key in enumerate(("median_iou", "box_frac")):
            ax = axes[i][j]
            rows = pair(cells, lag, key)
            x = np.arange(len(rows))
            ax.bar(x - 0.2, [r[1] for r in rows], 0.4, color="#b02020", label="COLD")
            ax.bar(x + 0.2, [r[2] for r in rows], 0.4, color="#1f9e5a", label="WARM")
            ax.set_xticks(x, [r[0].replace("clip", "") for r in rows], fontsize=7)
            ax.set_ylabel(key)
            ax.set_ylim(0, 1.02)
            if i == 0:
                st = stats["G2"][str(lag)]
                ax.set_title(f"lag {lag:g} s  |  post-live median IoU  "
                             f"(n={st['n']} paired of 25)", fontsize=10)
                ax.legend(fontsize=8, loc="lower right")
            else:
                ax.set_title("fraction of post-live steps with a box at all", fontsize=10)
    fig.suptitle("P6.7 -- G2: does the fast handoff cost track quality?")
    fig.tight_layout()
    fig.savefig(PROOF / "quality-paired.png", dpi=150)
    plt.close(fig)


def fig_jump(jump_cells):
    """RQ-P6.7e: the catch-up policy is a trade, and this is the curve.

    Same WARM bridge, same 4.85 s lag, only `CATCHUP_JUMP` moves. Left axis is the cost
    of catching up, right axis is what catching up that way does to the track.
    """
    by = {}
    for c in jump_cells:
        by.setdefault(c["jump"], []).append(c)
    js = sorted(by)
    x = np.arange(len(js))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    t = [float(np.median([c["t_handoff"] for c in by[j]])) for j in js]
    ax.bar(x - 0.2, t, 0.4, color="#2f6fb0", label="t_handoff (s)")
    ax.set_ylabel("median t_handoff (s)", color="#2f6fb0")
    ax.set_xticks(x, [("every frame" if j == 1 else "jump to live" if j >= 999
                       else f"{j} (deployed)") for j in js])
    ax.axhline(G1_MEDIAN, ls="--", lw=1, color="#b02020")
    ax2 = ax.twinx()
    keep = [sum(1 for c in by[j] if (c.get("median_iou") or 0) >= 0.25) / len(by[j])
            for j in js]
    ax2.bar(x + 0.2, keep, 0.4, color="#1f9e5a", label="clips with median IoU >= 0.25")
    ax2.set_ylabel("fraction of 25 clips still on target", color="#1f9e5a")
    ax2.set_ylim(0, 1.05)
    for xi, (a, b) in enumerate(zip(t, keep)):
        ax.text(xi - 0.2, a, f"{a:.2f}", ha="center", va="bottom", fontsize=9)
        ax2.text(xi + 0.2, b, f"{b:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("CATCHUP_JUMP")
    ax.set_title("P6.7 RQ-e -- catching up fast vs catching up intact (WARM, lag 4.85 s)")
    fig.tight_layout()
    fig.savefig(PROOF / "jump-tradeoff.png", dpi=150)
    plt.close(fig)


def loss_frames(matrix_dir: Path, cells, lag):
    """Copy the FIRST discordant clip (WARM on target, COLD not) at `lag`.

    Deterministic rule, alphabetical, no eyeballing: this is one of the b=8 pairs behind the
    unanticipated track-loss finding, not a hand-picked worst case. Returns the clip name.
    """
    idx = {(c["clip"], c["arm"]): c for c in cells if c["lag_s"] == lag}
    on = lambda c: (c.get("median_iou") or 0) >= 0.25
    for name in sorted({c["clip"] for c in cells}):
        a, b = idx.get((name, "COLD")), idx.get((name, "WARM"))
        if not (a and b and a.get("ok") and b.get("ok")) or on(a) or not on(b):
            continue
        pa = matrix_dir / f"{name}-COLD-lag{lag:g}-j{a['jump']}" / "seam-live.png"
        pb = matrix_dir / f"{name}-WARM-lag{lag:g}-j{b['jump']}" / "seam-live.png"
        if pa.exists() and pb.exists():
            shutil.copyfile(pa, PROOF / "loss-COLD.png")
            shutil.copyfile(pb, PROOF / "loss-WARM.png")
            return name
    return None


def seam_frames(matrix_dir: Path, cells, lag):
    """Copy one COLD and one WARM go-live overlay for the SAME clip -- the I5 evidence."""
    idx = {(c["clip"], c["arm"]): c for c in cells if c["lag_s"] == lag}
    for name in sorted({c["clip"] for c in cells}):
        a, b = idx.get((name, "COLD")), idx.get((name, "WARM"))
        if not (a and b and a.get("ok") and b.get("ok")):
            continue
        pa = matrix_dir / f"{name}-COLD-lag{lag:g}-j{a['jump']}" / "seam-live.png"
        pb = matrix_dir / f"{name}-WARM-lag{lag:g}-j{b['jump']}" / "seam-live.png"
        if pa.exists() and pb.exists():
            shutil.copyfile(pa, PROOF / "seam-COLD.png")
            shutil.copyfile(pb, PROOF / "seam-WARM.png")
            return name
    return None


# ---- scoring -----------------------------------------------------------------
def score(cells, lags):
    out = {"G1": {}, "G2": {}, "n_cells": len(cells)}
    for lag in lags:
        rows = pair(cells, lag, "t_handoff")
        p, n = wilcox(rows)
        med_w = float(np.median([r[2] for r in rows])) if rows else None
        med_c = float(np.median([r[1] for r in rows])) if rows else None
        out["G1"][str(lag)] = {
            "n": n, "p": p, "median_cold_s": med_c, "median_warm_s": med_w,
            "speedup": (med_c / med_w) if med_w else None,
            "pass": bool(med_w is not None and med_w <= G1_MEDIAN
                         and p is not None and p < 0.05),
        }
        q = pair(cells, lag, "median_iou")
        pq, nq = wilcox(q)
        mc = float(np.median([r[1] for r in q])) if q else None
        mw = float(np.median([r[2] for r in q])) if q else None
        sw = pair(cells, lag, "swaps")
        bf = pair(cells, lag, "box_frac")
        out["G2"][str(lag)] = {
            "n": nq, "p": pq, "median_iou_cold": mc, "median_iou_warm": mw,
            "swaps_cold": sum(r[1] for r in sw), "swaps_warm": sum(r[2] for r in sw),
            "box_frac_cold": float(np.median([r[1] for r in bf])) if bf else None,
            "box_frac_warm": float(np.median([r[2] for r in bf])) if bf else None,
            "pass": bool(mw is not None and mc is not None and mw >= mc - G2_SLACK
                         and sum(r[2] for r in sw) <= sum(r[1] for r in sw)
                         and (not bf or np.median([r[2] for r in bf])
                              >= np.median([r[1] for r in bf]))),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("runs/p67"),
                    help="campaign dir holding matrix/ residency/ jump/")
    ap.add_argument("--matrix", type=Path)
    ap.add_argument("--residency", type=Path)
    ap.add_argument("--jump", type=Path)
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    args.matrix = args.matrix or args.run / "matrix"
    args.residency = args.residency or args.run / "residency" / "results.json"
    args.jump = args.jump or args.run / "jump" / "results.json"

    if args.selfcheck:
        cells = []
        for i in range(25):
            cells += [{"clip": f"c{i}", "arm": "COLD", "lag_s": 0.0, "jump": 12,
                       "t_handoff": 6.0 + i * 0.01, "median_iou": 0.5, "box_frac": 0.9,
                       "swaps": 1, "stages": {s: 1.0 for s in STAGES}, "ok": True},
                      {"clip": f"c{i}", "arm": "WARM", "lag_s": 0.0, "jump": 12,
                       "t_handoff": 0.3, "median_iou": 0.8, "box_frac": 1.0,
                       "swaps": 0, "stages": {"warmup_init": 0.1, "drain": 0.2}, "ok": True}]
        s = score(cells, [0.0])
        assert s["G1"]["0.0"]["n"] == 25 and s["G1"]["0.0"]["pass"], s["G1"]
        assert s["G1"]["0.0"]["p"] < 1e-4, s["G1"]
        assert s["G2"]["0.0"]["pass"], s["G2"]
        # a WARM arm that wins on speed but loses the track must FAIL G2
        for c in cells:
            if c["arm"] == "WARM":
                c["median_iou"] = 0.1
        assert not score(cells, [0.0])["G2"]["0.0"]["pass"]
        # and one with no discordant pairs must not claim a p-value
        assert wilcox([("a", 1.0, 1.0), ("b", 2.0, 2.0)])[0] is None
        print("selfcheck OK")
        return

    PROOF.mkdir(exist_ok=True)
    m = load(args.matrix / "results.json")
    cells = [c for c in m["cells"] if c.get("t_handoff") is not None]
    lags = sorted({c["lag_s"] for c in cells})
    stats = score(cells, lags)

    fig_stages(cells, lags)
    fig_paired(cells, lags, stats)
    fig_quality(cells, lags, stats)
    seam = seam_frames(args.matrix, cells, lags[-1])
    stats["seam_clip"] = seam
    stats["loss_clip"] = loss_frames(args.matrix, cells, lags[0])

    if args.residency.exists():
        r = load(args.residency)
        stats["G3"] = {k: r[k] for k in ("median_baseline_ms", "median_resident_ms",
                                         "ratio", "latency_pass", "memory", "G3_pass")}
    if args.jump.exists():
        j = load(args.jump)
        fig_jump(j["cells"])
        by = {}
        for c in j["cells"]:
            by.setdefault(c["jump"], []).append(c)
        stats["RQe"] = {str(k): {
            "n": len(v),
            "median_t_handoff": float(np.median([c["t_handoff"] for c in v])),
            "median_steps_to_live": float(np.median([c["steps_to_live"] for c in v])),
            "median_iou": float(np.median([c["median_iou"] for c in v
                                           if c.get("median_iou") is not None] or [np.nan])),
            "on_target_clips": sum(1 for c in v if (c.get("median_iou") or 0) >= 0.25),
            "swaps": sum(c.get("swaps") or 0 for c in v),
        } for k, v in sorted(by.items())}

    (HERE / "scores.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))
    print(f"\nfigures -> {PROOF}")


if __name__ == "__main__":
    main()
