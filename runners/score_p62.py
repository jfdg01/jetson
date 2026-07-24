#!/usr/bin/env python3
"""score_p62.py -- P6.2 flight scoring + inferential stats (DELIVERY + COUPLING).

What it does
------------
Consumes the per-flight `runs/<id>/rows.json` written by `run_p62_flight.py` (one row
per control tick: `i, t, gt, deliver, lock_iou, on_target, on_other`) across the WARM
and COLD arms, and turns them into the two frozen P6.2 verdicts:

- **P6.2-DELIVERY** (paired-binary, exact McNemar): per-flight FOLLOW PASS =
  (1) genuine_lock at delivery (delivered box IoU>=0.25 vs the target `actor_box` at
  the delivery frame) AND (2) post-prompt coverage>=0.5 (driven-track IoU>=0.25 over
  the post-prompt window) AND (3) no identity swap (never `on_other`). Pairs WARM vs
  COLD by scenario, runs the exact McNemar via `Claim`/`evaluate` deflated to distinct
  CARLA scenarios, plus the co-primary WARM Wilson 95% interval.
- **P6.2-COUPLING** (paired-continuous, Wilcoxon + bootstrap CI, NO deflation):
  per-seed mean post-prompt follow-error (px) of the warm track, COUPLED vs DECOUPLED,
  through `grounding.stats.paired_continuous` (which refuses cluster deflation -- S3).
- **Descriptive companions (non-inferential, never in any Holm family):** P6.3-LAT
  delivery-latency distribution WARM vs COLD; P6.2-CEILING WARM-vs-oracle follow-error
  bootstrap gap. Reported as distributions / bounded gaps, never as a verdict p.

Frozen gates read from: experiments/2026-07-23-p62-delivery/README.md,
experiments/2026-07-23-p62-coupling/README.md, and
experiments/PART6-PROGRAM-warm-start-significance.md sec.2.2. If they disagree, the
program doc wins.

Machine of every number (R-2 discipline)
-----------------------------------------
Everything HERE (FOLLOW-PASS predicate, McNemar b/c, Wilcoxon, Wilson, bootstrap) is
pure host arithmetic over rows.json -- no device. The rows themselves were produced by
the closed-loop flight: CARLA render + SAM2 carry + PID on the **RTX-3090 host**, the
WARM/COLD VLM acquire on the **Jetson Orin Nano** -> the produced claims register as
`machine="both"`. This script adds no device number; it only aggregates.

Honesty caveat (S5, inherited)
------------------------------
A CARLA PASS licenses a control-coupling claim only ("warm-start delivers a followable
lock the controller can hold, where cold delivers stale"); it does NOT license a
real-imagery perception claim -- that authority stays with Part V / E18-n25 (P5.17:
sim grounds too cleanly).

Run it for real (deferred -- needs the flight matrix on disk)
-------------------------------------------------------------
    .venv-ft/bin/python runners/score_p62.py --runs runs/p62_delivery --overlay --stats
    .venv-ft/bin/python runners/score_p62.py --coupling \
        --coupled runs/p62_delivery --decoupled runs/p62_coupling --wilcoxon --bootstrap 10000

    # pure-logic check (no runs dir, no scipy-heavy data, no device):
    .venv-ft/bin/python runners/score_p62.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from grounding.stats import (  # the stats engine -- reused, not reimplemented
    Claim,
    deflate_to_effective,
    discordant_counts,
    evaluate,
    paired_continuous,
    wilson_ci,
)

IOU_THRESH = 0.25       # lock threshold (E18/P5 convention)
COV_THRESH = 0.5        # post-prompt coverage floor (frozen gate)
ARMS = {"warm", "cold", "coupled", "decoupled", "oracle"}


# --------------------------------------------------------------------------
# per-flight predicates (the load-bearing logic; all covered by --selftest)
# --------------------------------------------------------------------------

def _delivery_row(rows):
    """The first tick at which a box actually reaches the control loop (`deliver`
    not None). For WARM this is ~t_prompt (acquire 0.00 s); for COLD it is ~4.85 s
    later. None if the arm never delivered a box in the whole flight."""
    for r in rows:
        if r.get("deliver") is not None:
            return r
    return None


def follow_pass(rows, *, iou_thresh: float = IOU_THRESH, cov_thresh: float = COV_THRESH):
    """Frozen per-flight FOLLOW PASS predicate -- all three clauses, ANDed.

    Returns (passed, info). info carries each clause so the target-exits-frame cost
    (a COLD failure mode, not just staleness) is auditable per flight.

    1. genuine_lock at delivery : `lock_iou` at the delivery row >= iou_thresh.
    2. post-prompt coverage     : fraction of post-PROMPT GT-present ticks with
                                  `lock_iou` >= iou_thresh must be >= cov_thresh.
    3. no identity swap         : no post-prompt tick has `on_other` True.

    Scoring window (frozen gate = "post-prompt follow window"): if the rows carry the
    per-tick `post_prompt` flag (written by fly_once from t>=t_prompt), clauses 2+3 run
    over that window -- symmetric across arms and, crucially, it INCLUDES COLD's blind
    hover gap (prompt -> ~4.85 s acquire, no box) as coverage-0 ticks, which is the
    staleness cost the experiment measures. Legacy rows without the flag fall back to the
    post-delivery window (oracle-screen flights, synthetic selftest data).

    A flight that never delivers a box in the window fails (never_delivered).
    """
    windowed = [r for r in rows if r.get("post_prompt")] if any("post_prompt" in r for r in rows) else None
    search = windowed if windowed is not None else rows   # first delivered box in the scoring window
    d = _delivery_row(search)
    if d is None:
        return False, {"reason": "never_delivered", "delivered": False,
                       "genuine_lock": False, "coverage": 0.0, "no_swap": True,
                       "target_in_frame_at_delivery": None}

    genuine_lock = float(d.get("lock_iou") or 0.0) >= iou_thresh
    target_in_frame = d.get("gt") is not None

    # post-prompt window (frozen gate) if flagged, else legacy post-delivery
    post = windowed if windowed is not None else [r for r in rows if r["i"] >= d["i"]]
    scored = [r for r in post if r.get("gt") is not None]
    coverage = (sum(1 for r in scored if float(r.get("lock_iou") or 0.0) >= iou_thresh)
                / len(scored)) if scored else 0.0
    no_swap = not any(bool(r.get("on_other")) for r in post)

    passed = bool(genuine_lock and coverage >= cov_thresh and no_swap)
    info = {
        "delivered": True,
        "delivery_i": d["i"], "delivery_iou": round(float(d.get("lock_iou") or 0.0), 4),
        "genuine_lock": bool(genuine_lock),
        "coverage": round(coverage, 4),
        "no_swap": bool(no_swap),
        "target_in_frame_at_delivery": bool(target_in_frame),
        "reason": None if passed else _fail_reason(genuine_lock, coverage, no_swap,
                                                   cov_thresh, target_in_frame),
    }
    return passed, info


def _fail_reason(genuine_lock, coverage, no_swap, cov_thresh, target_in_frame):
    if not genuine_lock:
        return "no_lock_at_delivery" + ("" if target_in_frame else " (target_left_frame)")
    if coverage < cov_thresh:
        return f"coverage {coverage:.2f}<{cov_thresh}"
    if not no_swap:
        return "identity_swap"
    return "unknown"


def follow_error_px(row):
    """Center-to-center pixel distance between the delivered/driven box and GT for
    one tick. None if either box is absent (that tick contributes no error sample)."""
    d, g = row.get("deliver"), row.get("gt")
    if d is None or g is None:
        return None
    dcx, dcy = (d[0] + d[2]) / 2.0, (d[1] + d[3]) / 2.0
    gcx, gcy = (g[0] + g[2]) / 2.0, (g[1] + g[3]) / 2.0
    return math.hypot(dcx - gcx, dcy - gcy)


def per_flight_follow_error(rows):
    """Mean post-prompt follow-error (px) for one flight -- the P6.2-COUPLING unit.
    None if the flight never delivered / has no scorable ticks."""
    d = _delivery_row(rows)
    if d is None:
        return None
    errs = [e for r in rows if r["i"] >= d["i"]
            for e in (follow_error_px(r),) if e is not None]
    return float(sum(errs) / len(errs)) if errs else None


def delivery_latency_s(rows):
    """Wall seconds from flight/prompt start (`rows[0].t`) to first delivered box.
    WARM ~0.00 s (track already exists); COLD ~4.85 s. None if never delivered."""
    if not rows:
        return None
    t0 = float(rows[0].get("t") or 0.0)
    d = _delivery_row(rows)
    return None if d is None else float(d.get("t") or 0.0) - t0


# --------------------------------------------------------------------------
# flight discovery (arm + scenario per runs/<id> subdir)
# --------------------------------------------------------------------------

def _flight_rows(flight_dir: Path):
    p = flight_dir / "rows.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _arm_scenario(flight_dir: Path):
    """(arm, scenario) for a flight dir. Prefers explicit results.json fields; falls
    back to the `<arm>_<scenario>` dir-name convention (e.g. warm_seed03)."""
    arm = scen = None
    rj = flight_dir / "results.json"
    if rj.exists():
        try:
            r = json.loads(rj.read_text())
            arm = (r.get("arm") or "").lower() or None
            scen = r.get("scenario") if r.get("scenario") is not None else r.get("seed")
            scen = None if scen is None else str(scen)
        except Exception:
            pass
    if arm is None or scen is None:
        parts = flight_dir.name.split("_", 1)
        if len(parts) == 2 and parts[0].lower() in ARMS:
            arm = arm or parts[0].lower()
            scen = scen or parts[1]
    return arm, scen


def load_arm(runs_dir, aliases) -> dict:
    """{scenario: [rows, ...]} for the flights whose arm is in `aliases` (a set/list
    of arm names -- e.g. coupled reuses the WARM flights, so aliases=('coupled',
    'warm')). Reps under one scenario accumulate into the list."""
    aliases = {a.lower() for a in ([aliases] if isinstance(aliases, str) else aliases)}
    out: dict[str, list] = {}
    root = Path(runs_dir)
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        arm, scen = _arm_scenario(d)
        if arm not in aliases or scen is None:
            continue
        rows = _flight_rows(d)
        if rows is not None:
            out.setdefault(scen, []).append(rows)
    return out


def _arm_pass_map(flights: dict) -> dict:
    """{scenario: 0|1} FOLLOW-PASS per scenario. Reps (noise band) collapse by strict
    majority -> keeps the scenario as ONE cluster (S1), never inflating n."""
    out = {}
    for scen, runs in flights.items():
        votes = [1 if follow_pass(r)[0] else 0 for r in runs]
        out[scen] = 1 if sum(votes) * 2 > len(votes) else 0
    return out


# --------------------------------------------------------------------------
# P6.2-DELIVERY: paired exact McNemar (deflated to distinct scenarios) + Wilson
# --------------------------------------------------------------------------

def score_delivery(runs_dir) -> dict:
    warm = load_arm(runs_dir, "warm")
    cold = load_arm(runs_dir, "cold")
    warm_pass = _arm_pass_map(warm)
    cold_pass = _arm_pass_map(cold)

    b, c, n_paired = discordant_counts(warm_pass, cold_pass)
    # Distinct CARLA scenarios == the paired scenario keys (S1: one gating cell per
    # distinct seed, reps already collapsed). n_effective == n_rows here, so the
    # deflation in evaluate() is the identity -- but the machinery is wired so a
    # future rep-inflated bank cannot silently over-count.
    paired_scen = sorted(set(warm_pass) & set(cold_pass))
    n_distinct = len(paired_scen)

    claim = Claim(
        id="P6.2-DELIVERY", part="VI",
        headline="closed-loop WARM maintain-and-deliver vs COLD blocking acquire",
        design="paired-binary", verdict="TBD",
        n_rows=n_paired, n_effective=n_distinct,
        independence_note=("one gating flight per arm per distinct CARLA seed; distinct "
                           "seeds are independent generative draws (S1), so n_effective "
                           "== paired scenario count"),
        data_status="per_item", scene_set=str(runs_dir),
        machine="both",
        counts={"b": b, "c": c, "n": n_paired},
        caveats=("S5: CARLA PASS licenses a control-coupling claim only, not a "
                 "real-imagery perception claim (authority stays with Part V / E18-n25)."),
    )
    outcome = evaluate(claim)

    # co-primary descriptive C1: WARM absolute lock rate + Wilson, over ITS OWN n.
    warm_k = sum(warm_pass.values())
    n_warm = len(warm_pass)
    warm_wilson = wilson_ci(warm_k, n_warm) if n_warm else None

    # target-exits-frame: the headline COLD cost (not just staleness)
    cold_exit = sum(1 for scen in cold
                    for info in (follow_pass(cold[scen][0])[1],)
                    if info.get("target_in_frame_at_delivery") is False)

    return {
        "experiment": "P6.2-DELIVERY",
        "n_warm": n_warm, "n_cold": len(cold_pass), "n_paired": n_paired,
        "warm_pass": warm_k, "cold_pass": sum(cold_pass.values()),
        "mcnemar_b": b, "mcnemar_c": c, "discordant": b + c,
        "n_effective": n_distinct,
        "p_value": outcome.p_value,
        "reachable": outcome.could_ever_reach_alpha,
        "reading": outcome.reading,
        "warm_wilson95": warm_wilson,
        "cold_target_exits_frame": cold_exit,
        "surprise_branch": ("COLD>=10/25: loop did NOT amplify delivery-lag beyond replay"
                            if sum(cold_pass.values()) >= 10 else None),
        "per_scenario": {scen: {"warm": warm_pass.get(scen), "cold": cold_pass.get(scen)}
                         for scen in sorted(set(warm_pass) | set(cold_pass))},
    }


# --------------------------------------------------------------------------
# P6.2-COUPLING: Wilcoxon + bootstrap on per-seed follow-error (NO deflation)
# --------------------------------------------------------------------------

def score_coupling(coupled_dir, decoupled_dir, *, n_boot: int = 10000) -> dict:
    coupled = load_arm(coupled_dir, ("coupled", "warm"))   # coupled == the WARM flights
    decoupled = load_arm(decoupled_dir, "decoupled")
    scen = sorted(set(coupled) & set(decoupled))

    pairs = []
    for s in scen:
        cx = per_flight_follow_error(coupled[s][0])
        dx = per_flight_follow_error(decoupled[s][0])
        if cx is not None and dx is not None:
            pairs.append((s, cx, dx))

    if not pairs:
        return {"experiment": "P6.2-COUPLING", "n_pairs": 0,
                "note": "no scenario has both a coupled and a decoupled follow-error"}

    x = [c for _, c, _ in pairs]   # coupled per-seed error
    y = [d for _, _, d in pairs]   # decoupled per-seed error
    # NO cluster deflation (S3): Wilcoxon keeps n_effective == n_rows; paired_continuous
    # refuses deflation by construction. Call it directly on the per-seed values.
    r = paired_continuous(x, y, alternative="two-sided")
    return {
        "experiment": "P6.2-COUPLING",
        "n_pairs": len(pairs),
        "coupled_mean_err_px": round(sum(x) / len(x), 2),
        "decoupled_mean_err_px": round(sum(y) / len(y), 2),
        "wilcoxon_p": r.get("p_value"),
        "median_paired_diff_px": r.get("median_diff"),
        "ci95_median_diff_px": r.get("ci95_median_diff"),
        "note": r.get("note"),
        "per_seed": [{"scenario": s, "coupled": round(c, 2), "decoupled": round(d, 2)}
                     for s, c, d in pairs],
    }


# --------------------------------------------------------------------------
# descriptive companions (NON-inferential -- never a verdict p, no Holm)
# --------------------------------------------------------------------------

def _quantile(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    idx = q * (len(s) - 1)
    lo, hi = int(math.floor(idx)), int(math.ceil(idx))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (idx - lo)


def latency_distribution(runs_dir) -> dict:
    """P6.3-LAT (descriptive): delivery-latency distribution WARM vs COLD -- report
    the distribution + jitter band, NOT a signed-rank p (the E20 false-precision
    lesson)."""
    out = {"experiment": "P6.3-LAT", "inferential": False}
    for arm in ("warm", "cold"):
        lats = [lat for runs in load_arm(runs_dir, arm).values()
                for lat in (delivery_latency_s(runs[0]),) if lat is not None]
        out[arm] = {
            "n": len(lats),
            "median_s": round(_quantile(lats, 0.5), 3) if lats else None,
            "p10_s": round(_quantile(lats, 0.10), 3) if lats else None,
            "p90_s": round(_quantile(lats, 0.90), 3) if lats else None,
            "jitter_band_s": (round(_quantile(lats, 0.90) - _quantile(lats, 0.10), 3)
                              if lats else None),
        }
    return out


def ceiling_gap(runs_dir, *, n_boot: int = 10000) -> dict:
    """P6.2-CEILING (descriptive): WARM vs oracle-GT-driven per-seed follow-error, a
    bounded gap + bootstrap CI against the control ceiling. Reported as a gap, never a
    tautological verdict p. Skipped if no oracle arm is present."""
    warm = load_arm(runs_dir, "warm")
    oracle = load_arm(runs_dir, "oracle")
    scen = sorted(set(warm) & set(oracle))
    pairs = []
    for s in scen:
        w = per_flight_follow_error(warm[s][0])
        o = per_flight_follow_error(oracle[s][0])
        if w is not None and o is not None:
            pairs.append((w, o))
    if not pairs:
        return {"experiment": "P6.2-CEILING", "inferential": False,
                "note": "no oracle arm on this matrix; gap not computable"}
    x = [w for w, _ in pairs]
    o = [o for _, o in pairs]
    r = paired_continuous(x, o, alternative="two-sided")   # reused ONLY for the boot CI
    return {
        "experiment": "P6.2-CEILING", "inferential": False,
        "n_pairs": len(pairs),
        "warm_mean_err_px": round(sum(x) / len(x), 2),
        "oracle_mean_err_px": round(sum(o) / len(o), 2),
        "median_gap_px": r.get("median_diff"),
        "ci95_gap_px": r.get("ci95_median_diff"),
        "note": "bounded gap vs the oracle-driven ceiling; NOT an inferential verdict",
    }


def write_pass_figure(delivery: dict, out_path) -> None:
    """--overlay: per-scenario FOLLOW-PASS bar figure WARM vs COLD (numbers are the
    point -> a figure, per DoD-7). matplotlib guarded so --selftest stays pure."""
    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    per = delivery["per_scenario"]
    scen = sorted(per)
    xs = range(len(scen))
    fig, ax = plt.subplots(figsize=(max(6, len(scen) * 0.4), 3))
    ax.bar([x - 0.2 for x in xs], [per[s]["warm"] or 0 for s in scen], 0.4, label="WARM")
    ax.bar([x + 0.2 for x in xs], [per[s]["cold"] or 0 for s in scen], 0.4, label="COLD")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(scen, rotation=90, fontsize=6)
    ax.set_ylabel("FOLLOW PASS")
    ax.set_title(f"P6.2-DELIVERY  WARM {delivery['warm_pass']}/{delivery['n_warm']} vs "
                 f"COLD {delivery['cold_pass']}/{delivery['n_cold']}  "
                 f"(b={delivery['mcnemar_b']}, c={delivery['mcnemar_c']}, p={delivery['p_value']})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(str(out_path), dpi=120)
    plt.close(fig)
    print(f"[score_p62] wrote {out_path}")


# --------------------------------------------------------------------------
# self-test (pure logic; no runs dir, no device)
# --------------------------------------------------------------------------

def selftest() -> None:
    gt = [0.0, 0.0, 10.0, 10.0]
    box = [0.0, 0.0, 10.0, 10.0]

    def row(i, gt_box, deliver, iou_v, on_other=False, on_target=True):
        return {"i": i, "t": round(i * 0.05, 3), "gt": gt_box, "deliver": deliver,
                "lock_iou": iou_v, "on_target": on_target, "on_other": on_other}

    # a passing flight: no box for 5 ticks, delivered @ i=5 with a good lock, held after
    good = [row(i, gt, None, 0.0, on_target=False) for i in range(5)]
    good += [row(i, gt, box, 0.9) for i in range(5, 20)]
    ok, info = follow_pass(good)
    assert ok, info
    assert info["genuine_lock"] and info["coverage"] == 1.0 and info["no_swap"], info
    assert info["delivery_i"] == 5, info

    # clause 1: bad lock AT delivery -> FAIL even if it recovers later
    bad_deliver = [row(i, gt, None, 0.0, on_target=False) for i in range(5)]
    bad_deliver += [row(5, gt, box, 0.1)] + [row(i, gt, box, 0.9) for i in range(6, 20)]
    p1, i1 = follow_pass(bad_deliver)
    assert (not p1) and i1["reason"].startswith("no_lock_at_delivery"), i1

    # clause 2: locks at delivery but drifts -> coverage < 0.5 -> FAIL
    low_cov = [row(i, gt, None, 0.0, on_target=False) for i in range(5)]
    low_cov += [row(5, gt, box, 0.9)] + [row(i, gt, box, 0.1) for i in range(6, 20)]
    p2, i2 = follow_pass(low_cov)
    assert (not p2) and i2["coverage"] < 0.5 and i2["reason"].startswith("coverage"), i2

    # clause 3: identity swap after delivery -> FAIL
    swap = [row(i, gt, None, 0.0, on_target=False) for i in range(5)]
    swap += [row(5, gt, box, 0.9)]
    swap += [row(i, gt, box, 0.9, on_other=True, on_target=False) for i in range(6, 20)]
    p3, i3 = follow_pass(swap)
    assert (not p3) and i3["reason"] == "identity_swap", i3

    # never delivered -> FAIL, and target-exits-frame variant marked
    p4, i4 = follow_pass([row(i, gt, None, 0.0, on_target=False) for i in range(10)])
    assert (not p4) and i4["reason"] == "never_delivered", i4

    # target left frame at COLD delivery (gt None at delivery) -> no-lock reason names it
    exit_frame = [row(i, gt, None, 0.0, on_target=False) for i in range(5)]
    exit_frame += [row(5, None, box, 0.0)] + [row(i, None, box, 0.0) for i in range(6, 20)]
    p5, i5 = follow_pass(exit_frame)
    assert (not p5) and i5["target_in_frame_at_delivery"] is False, i5
    assert "target_left_frame" in i5["reason"], i5

    # --- post-prompt windowing (frozen gate): the flag switches clauses 2+3 to t>=t_prompt ---
    def prow(i, gt_box, deliver, iou_v, pp, on_other=False, on_target=True):
        return {"i": i, "t": round(i * 0.05, 3), "post_prompt": pp, "gt": gt_box,
                "deliver": deliver, "lock_iou": iou_v, "on_target": on_target, "on_other": on_other}

    # WARM-style: delivers from idle (pre-prompt), holds through the post-prompt window -> PASS,
    # and the pre-prompt ticks are EXCLUDED (coverage is 1.0 over the 10 post-prompt ticks only).
    warm_pp = [prow(i, gt, box, 0.9, i >= 10) for i in range(20)]
    okw, iw = follow_pass(warm_pp)
    assert okw and iw["coverage"] == 1.0 and iw["delivery_i"] == 10, iw

    # COLD-style: blind (no box) for the first half of the post-prompt window, catches up late.
    # coverage counts the blind gap as 0 -> 4/14 = 0.286 < 0.5 -> FAIL (the staleness penalty).
    cold_pp = [prow(i, gt, None, 0.0, True, on_target=False) for i in range(10)]
    cold_pp += [prow(i, gt, box, 0.9, True) for i in range(10, 14)]
    okc, ic = follow_pass(cold_pp)
    assert (not okc) and abs(ic["coverage"] - round(4 / 14, 4)) < 1e-9 and ic["reason"].startswith("coverage"), ic

    # COLD that never delivers in the post-prompt window -> never_delivered (blind the whole time)
    blind = [prow(i, gt, box, 0.9, False) for i in range(10)]        # all pre-prompt deliveries
    blind += [prow(i, gt, None, 0.0, True, on_target=False) for i in range(10, 20)]
    okb, ib = follow_pass(blind)
    assert (not okb) and ib["reason"] == "never_delivered", ib

    # follow_error_px: center distance, None-safe
    assert follow_error_px({"deliver": box, "gt": gt}) == 0.0
    assert follow_error_px({"deliver": None, "gt": gt}) is None
    assert abs(follow_error_px({"deliver": [10, 0, 20, 10], "gt": gt}) - 10.0) < 1e-9

    # per_flight_follow_error + delivery_latency_s
    assert per_flight_follow_error(good) == 0.0
    assert abs(delivery_latency_s(good) - 0.25) < 1e-9   # first deliver at i=5 -> t=0.25
    assert delivery_latency_s([row(i, gt, None, 0.0, on_target=False) for i in range(3)]) is None

    # --- McNemar b/c tally + Claim/evaluate wiring ---
    warm_pass = {"s1": 1, "s2": 1, "s3": 0, "s4": 1, "s5": 1}
    cold_pass = {"s1": 0, "s2": 0, "s3": 0, "s4": 1, "s5": 0}
    b, c, n = discordant_counts(warm_pass, cold_pass)   # s1,s2,s5 warm>cold; s3,s4 concordant
    assert (b, c, n) == (3, 0, 5), (b, c, n)

    claim = Claim(id="P6.2-DELIVERY-selftest", part="VI", headline="",
                  design="paired-binary", verdict="TBD", n_rows=n, n_effective=n,
                  independence_note="", data_status="per_item",
                  counts={"b": b, "c": c, "n": n})
    o = evaluate(claim)
    assert abs(o.p_value - 0.25) < 1e-9, o.p_value            # mcnemar(3,0) two-sided
    assert o.could_ever_reach_alpha is False, "n=5 paired cannot reach alpha (S2)"

    # a reachable/significant case exercises the same wiring at the target n
    reach = Claim(id="reach", part="VI", headline="", design="paired-binary",
                  verdict="TBD", n_rows=26, n_effective=26, independence_note="",
                  data_status="per_item", counts={"b": 6, "c": 0, "n": 26})
    o2 = evaluate(reach)
    assert abs(o2.p_value - 2 * 0.5 ** 6) < 1e-9 and o2.could_ever_reach_alpha, o2.p_value

    # deflation machinery is wired (identity when n_effective == den; shrinks otherwise)
    assert deflate_to_effective(6, 26, 26) == (6, 26)
    assert deflate_to_effective(12, 24, 12) == (6, 12)

    # --- Wilson wiring (co-primary WARM lock rate) ---
    lo, hi = wilson_ci(4, 5)
    assert 0.0 < lo < hi < 1.0, (lo, hi)

    # --- Wilcoxon / paired_continuous wiring (COUPLING), NO deflation ---
    coupled = [40.0, 45.0, 50.0, 55.0, 60.0, 42.0]
    decoupled = [30.0, 32.0, 35.0, 38.0, 40.0, 31.0]
    r = paired_continuous(coupled, decoupled, alternative="two-sided")
    assert r["p_value"] == r["p_value"], "expected a real p, not NaN"
    assert r["median_diff"] > 0 and "ci95_median_diff" in r, r
    # all-zero-difference guard -> no test
    z = paired_continuous([1.0, 2.0], [1.0, 2.0])
    assert z["p_value"] != z["p_value"] and "no test possible" in z["note"], z

    # _arm_pass_map majority-collapse of reps keeps a scenario as ONE cluster
    reps = {"s1": [good, good], "s2": [bad_deliver]}
    m = _arm_pass_map(reps)
    assert m == {"s1": 1, "s2": 0}, m

    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="P6.2 flight scoring + stats")
    ap.add_argument("--selftest", action="store_true", help="pure-logic check; no runs/device")
    # DELIVERY
    ap.add_argument("--runs", help="runs dir with warm_*/cold_* flight subdirs")
    ap.add_argument("--stats", action="store_true", help="run the McNemar + Wilson report")
    ap.add_argument("--overlay", action="store_true", help="write the FOLLOW-PASS bar figure")
    # COUPLING
    ap.add_argument("--coupling", action="store_true", help="score the coupled-vs-decoupled arm")
    ap.add_argument("--coupled", help="runs dir for the coupled arm (= the WARM flights)")
    ap.add_argument("--decoupled", help="runs dir for the decoupled arm")
    ap.add_argument("--wilcoxon", action="store_true", help="(coupling) run the signed-rank test")
    ap.add_argument("--bootstrap", type=int, default=10000, help="(coupling) bootstrap resamples")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if args.coupling:
        if not args.coupled or not args.decoupled:
            ap.error("--coupling needs --coupled and --decoupled")
        out = score_coupling(args.coupled, args.decoupled, n_boot=args.bootstrap)
        print(json.dumps(out, indent=2))
        return

    if not args.runs:
        ap.error("need --runs (or --coupling, or --selftest)")
    delivery = score_delivery(args.runs)
    report = {"delivery": delivery,
              "P6.3-LAT": latency_distribution(args.runs),
              "P6.2-CEILING": ceiling_gap(args.runs)}
    print(json.dumps(report, indent=2))
    if args.overlay:
        write_pass_figure(delivery, Path(args.runs) / "p62_follow_pass.png")
    if args.stats:
        d = delivery
        print(f"\n[P6.2-DELIVERY] WARM {d['warm_pass']}/{d['n_warm']} vs "
              f"COLD {d['cold_pass']}/{d['n_cold']}  b={d['mcnemar_b']} c={d['mcnemar_c']}  "
              f"p={d['p_value']}  n_eff={d['n_effective']}  reachable={d['reachable']}")
        print(f"  reading: {d['reading']}")
        print(f"  WARM Wilson95: {d['warm_wilson95']}   COLD target-exits-frame: "
              f"{d['cold_target_exits_frame']}")


if __name__ == "__main__":
    main()
