#!/usr/bin/env python3
"""P6.6 proof figures, reproducible from runs/<id>/results.json + tegrastats.log.

    .venv-ft/bin/python experiments/2026-07-25-maintain-cost/make_proof.py \
        --run experiments/2026-07-25-maintain-cost/runs/p66_maintain_cost

Writes the three pre-registered figures into proof/ (or --out). Every number on
them comes off results.json; the only external constant is the hover-power band,
which is literature and is labelled as such on the figure.
"""
import argparse
import gzip
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_p66 as R  # parse_tegrastats / window / integrate / rate_in

# Small-copter hover draw. Literature range, NOT measured here -- it only sets the
# width of the shaded band on fig 3, never a headline number.
HOVER_W = (150.0, 400.0)
COLD_ACQUIRE_S = 4.85          # Part IV / P6.2: the cold blocking acquire
LABEL = {"A0": "A0 idle, bare", "A1": "A1 idle, deployed", "B": "B carry 640",
         "C": "C carry 512", "D": "D ground (q8_0 acquires)"}
COLOR = {"A0": "#888888", "A1": "#4c72b0", "B": "#dd8452", "C": "#55a868",
         "D": "#c44e52"}


def load(runs, exclude=()):
    """Merge one or more run dirs into (res, samples, by_arm).

    Several dirs because an arm can be re-run on its own; each dir carries its own
    tegrastats anchor, and sample times are device unix so they merge directly.
    `exclude` drops records by `<run dir>:<tag>` (substring match) -- an arm that ran
    with something else on the device is not a measurement of that arm.
    """
    res, samples, by_arm, dropped = None, [], {}, []
    for run in runs:
        run = Path(run)
        r = json.loads((run / "results.json").read_text())
        res = res or r
        # the committed trace is gzipped -- 3.3 MB of text compresses 12x, and the raw
        # .log is what the driver writes, so accept either
        ts, tsgz = run / "tegrastats.log", run / "tegrastats.log.gz"
        trace = (ts.read_text() if ts.exists()
                 else gzip.decompress(tsgz.read_bytes()).decode() if tsgz.exists() else None)
        if trace:
            samples += R.parse_tegrastats(trace, r["anchor"], r["anchor_unix"])
        for rec in r["records"]:
            rec["tag_full"] = f"{run.name}:{rec['tag']}"
            if any(e in rec["tag_full"] for e in exclude):
                dropped.append(rec["tag_full"])
                continue
            by_arm.setdefault(rec["arm_id"], []).append(rec)
    samples.sort(key=lambda s: s["t"])
    if dropped:
        print("excluded:", ", ".join(dropped))
    return res, samples, by_arm


def med_w(recs):
    return st.median(r["power"]["vdd_in_mean_w"] for r in recs)


def fig_power(res, samples, by_arm, out):
    """VDD_IN over time, arms overlaid, idle floor drawn, maintain delta annotated."""
    fig, ax = plt.subplots(figsize=(9, 4.6))
    floor = med_w(by_arm["A0"]) if "A0" in by_arm else None
    for arm in [a for a in LABEL if a in by_arm]:
        w_arm = med_w(by_arm[arm])
        # delta lives in the legend, not as an annotation on the trace -- at 5 arms the
        # right-edge labels land on top of each other and on the legend box.
        tag = f"{LABEL[arm]}  {w_arm:.2f} W"
        if floor is not None and arm not in ("A0",):
            tag += f"  ({w_arm - floor:+.2f})"
        for i, rec in enumerate(by_arm[arm]):
            t0 = rec.get("t_steady_unix", rec["t_start_unix"])
            w = R.window(samples, t0, rec["t_end_unix"])
            if not w:
                continue
            ax.plot([s["t"] - t0 for s in w], [s["vdd_in_mw"] / 1000 for s in w],
                    color=COLOR[arm], lw=0.9, alpha=0.75 if i == 0 else 0.35,
                    label=tag if i == 0 else None)
    if floor is not None:
        ax.axhline(floor, color="k", ls=":", lw=1.2)
        ax.annotate(f"idle floor {floor:.2f} W", (2, floor), xytext=(2, floor + 0.35),
                    fontsize=8)
    ax.set_xlabel("seconds into steady window")
    ax.set_ylabel("VDD_IN instant power (W)")
    ax.set_title(f"P6.6 maintain cost, Orin Nano 15 W + jetson_clocks  "
                 f"({res['seconds']:.0f} s arms x {res['repeats']} repeats)")
    # the band between the idle floor and the carry plateau is the one empty stretch
    ax.legend(fontsize=8, loc="center left")
    ax.margins(y=0.12)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "power-by-arm.png", dpi=140)
    plt.close(fig)


def fig_decay(res, samples, by_arm, out):
    """G1: achieved Hz in 30 s bins, tj on the twin axis. A decay is a shape."""
    carry = [a for a in ("B", "C") if a in by_arm]
    if not carry:
        return False
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax2 = ax.twinx()
    bin_s, secs = 30.0, res["seconds"]
    edges = [i * bin_s for i in range(int(secs // bin_s))]
    top = 0.0
    for arm in carry:
        for i, rec in enumerate(by_arm[arm]):
            hz = [R.rate_in(rec["steps"], e, e + bin_s) for e in edges]
            top = max(top, max(hz))
            ax.plot([e + bin_s / 2 for e in edges], hz, color=COLOR[arm], lw=1.4,
                    marker="o", ms=3, alpha=0.9 if i == 0 else 0.4,
                    label=(f"{LABEL[arm]}  G1 {rec['g1']['hz_first_60s']:.2f} -> "
                           f"{rec['g1']['hz_last_60s']:.2f} Hz "
                           f"({rec['g1']['delta_frac'] * 100:+.1f}%, "
                           f"{'PASS' if rec['g1']['pass'] else 'FAIL'})")
                          if i == 0 else None)
            t0 = rec.get("t_steady_unix", rec["t_start_unix"])
            w = R.window(samples, t0, rec["t_end_unix"])
            ax2.plot([s["t"] - t0 for s in w], [s.get("tj_c") for s in w],
                     color=COLOR[arm], ls="--", lw=0.8, alpha=0.35)
    ax.set_ylim(0, top * 1.3)   # 0 baseline: flat has to read as flat, not as noise
    # the dashed tj curves live on the right axis and would otherwise read as rates
    ax.plot([], [], color="k", ls="--", lw=0.8, alpha=0.5, label="dashed: tj, right axis")
    ax.set_xlabel("seconds into steady window")
    ax.set_ylabel("achieved carry rate (Hz, 30 s bins)")
    ax2.set_ylabel("tj (C, dashed)")
    ax.set_title("P6.6 G1: does the carry rate hold over a 300 s maintain window")
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "carry-rate-decay.png", dpi=140)
    plt.close(fig)
    return True


def fig_price(res, samples, by_arm, out):
    """Energy to deliver one box, warm vs cold, as a function of idle-window length.

    Warm pays carry power for the whole idle window and delivers at t=0 staleness.
    Cold pays idle power over the window, then a blocking acquire at ground power --
    cheaper in joules, later by COLD_ACQUIRE_S. The crossing is the honest answer to
    "what does maintaining cost": the idle window at which maintain has spent as much
    as one cold acquire.
    """
    if "A1" not in by_arm or "B" not in by_arm:
        return False
    p_idle, p_carry = med_w(by_arm["A1"]), med_w(by_arm["B"])
    p_ground = med_w(by_arm["D"]) if "D" in by_arm else None
    ts = list(range(0, 121))
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11, 4.4))

    ax.plot(ts, [p_carry * t for t in ts], color=COLOR["B"],
            label=f"warm: maintain at {p_carry:.2f} W, 0 s stale")
    if p_ground is not None:
        cold = [p_idle * t + p_ground * COLD_ACQUIRE_S for t in ts]
        ax.plot(ts, cold, color=COLOR["D"],
                label=f"cold: idle {p_idle:.2f} W + {COLD_ACQUIRE_S} s at "
                      f"{p_ground:.2f} W, {COLD_ACQUIRE_S} s stale")
        be = p_ground * COLD_ACQUIRE_S / (p_carry - p_idle)
        ax.axvline(be, color="k", ls=":", lw=1.2)
        ax.annotate(f"break-even {be:.1f} s idle window", (be, ax.get_ylim()[1] * 0.5),
                    xytext=(be + 3, ax.get_ylim()[1] * 0.5), fontsize=8)
    else:
        ax.plot(ts, [p_idle * t for t in ts], color=COLOR["A1"],
                label=f"cold: idle {p_idle:.2f} W (arm D not in this run)")
    ax.set_xlabel("idle window before the operator's prompt (s)")
    ax.set_ylabel("energy to deliver one box (J)")
    ax.set_title("What maintain-and-deliver costs")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    delta = p_carry - p_idle
    lo, hi = 100 * delta / HOVER_W[1], 100 * delta / HOVER_W[0]
    hovers = [HOVER_W[0] + i * (HOVER_W[1] - HOVER_W[0]) / 50 for i in range(51)]
    bx.plot(hovers, [100 * delta / h for h in hovers], color=COLOR["B"], lw=2)
    for h, pct in ((HOVER_W[0], hi), (HOVER_W[1], lo)):
        bx.annotate(f"{pct:.1f}% at {h:.0f} W", (h, pct), fontsize=8,
                    xytext=(6 if h == HOVER_W[0] else -6, 6), textcoords="offset points",
                    ha="left" if h == HOVER_W[0] else "right")
    bx.set_xlabel("copter hover draw (W) -- literature range, not measured here")
    bx.set_ylabel("maintain delta as % of hover")
    bx.set_title(f"maintain costs +{delta:.2f} W = {lo:.1f}-{hi:.1f}% of hover")
    bx.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "maintain-price.png", dpi=140)
    plt.close(fig)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=None,
                    help="run dir; repeatable, later dirs add arms/repeats")
    ap.add_argument("--exclude", action="append", default=[],
                    help="drop a record by '<run dir>:<tag>' substring")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    runs = args.run or [HERE / "runs" / "p66_maintain_cost", HERE / "runs" / "p66_b_clean"]
    out = Path(args.out) if args.out else HERE / "proof"
    out.mkdir(parents=True, exist_ok=True)
    res, samples, by_arm = load(runs, args.exclude or ["p66_maintain_cost:B_r2"])
    assert samples, "no tegrastats samples -- figures 1 and 2 would be empty"
    print(f"arms {sorted(by_arm)}  samples {len(samples)}")
    for arm in sorted(by_arm):
        print(f"  {arm}: {med_w(by_arm[arm]):.3f} W median of {len(by_arm[arm])}")
    fig_power(res, samples, by_arm, out)
    print(f"wrote {out / 'power-by-arm.png'}")
    for name, ok in (("carry-rate-decay.png", fig_decay(res, samples, by_arm, out)),
                     ("maintain-price.png", fig_price(res, samples, by_arm, out))):
        print(f"wrote {out / name}" if ok else f"skipped {name} (arms missing)")


if __name__ == "__main__":
    main()
