"""Proof figures for P6.2-SHOWCASE.

ondevice : the GPU-independent half — the deployed SAM2 carry run literally on the Orin over
           the jetson_carry_service socket, seeded by the oracle GT box, stepped over real
           UAV123 frames. Two figures from runs/p62_showcase/ondevice/{summary,boxes}.json:
             proof/ondevice_carry_midrun.png  — a mid-run overlay (Jetson-carried box on the car)
             proof/ondevice_carry_trace.png   — per-step IoU vs GT + on-device compute ms/step
flight   : the closed-loop flight half — SAM2 carry routed LITERALLY to the Orin over ssh-stdio
           while a copter flies its own control output (CARLA render, ArduCopter SITL). From
           runs/p62_showcase/{flight/rows.json, flight/results.json, _acq/parity.json}:
             proof/flight_follow_overlay.png — a viewed in-flight overlay (GT + delivered box)
             proof/flight_trace.png          — top: delivered-vs-GT IoU over the flight (prompt
                                               marked); bottom: on-device carry parity vs the 3090
                                               twin per step + the ssh round-trip ms
"""
import json
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
PROOF = HERE / "proof"


def ondevice(run: Path):
    PROOF.mkdir(exist_ok=True)
    summ = json.loads((run / "summary.json").read_text())
    ious = summ["ious"]
    ms = [m for m in json.loads((run / "boxes.json").read_text())["ms"] if m is not None]
    n = len(ious)

    # figure 1: the viewed mid-run overlay (look-at-it evidence)
    mid = run / "overlays" / f"s{n//2:03d}.jpg"
    shutil.copyfile(mid, PROOF / "ondevice_carry_midrun.png")

    # figure 2: IoU trace + on-device compute-rate trace
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)
    xs = list(range(n))
    ax1.plot(xs, ious, "-o", color="#1f9e5a", ms=4)
    ax1.axhline(0.25, ls="--", color="#b02020", lw=1, label="IoU floor 0.25")
    ax1.set_ylim(0, 1.02)
    ax1.set_ylabel("IoU vs GT")
    ax1.set_title(f"P6.2-SHOWCASE on-device carry (Jetson Orin, q8_0 rig) — {summ['clip']}: "
                  f"held {int(summ['held_frac']*n)}/{n}, median IoU {summ['median_iou']:.2f}")
    ax1.legend(loc="lower left", fontsize=8)
    ax1.grid(alpha=0.3)

    ax2.plot(xs, ms, "-o", color="#2060c0", ms=4)
    ax2.axhline(sum(ms)/len(ms), ls="--", color="#555", lw=1,
                label=f"mean {sum(ms)/len(ms):.0f} ms = {summ['carry_hz_ondevice']:.2f} Hz on-device")
    ax2.set_ylabel("on-device compute\nms / step")
    ax2.set_xlabel(f"carry step (stride {summ.get('stride', 11)} @ 30 fps)")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROOF / "ondevice_carry_trace.png", dpi=110)
    print(f"[proof] wrote {PROOF/'ondevice_carry_midrun.png'} and "
          f"{PROOF/'ondevice_carry_trace.png'}", flush=True)


def flight(run: Path):
    """run = runs/p62_showcase; expects flight/{rows,results}.json + _acq/parity.json."""
    PROOF.mkdir(exist_ok=True)
    res = json.loads((run / "flight" / "results.json").read_text())
    rows = json.loads((run / "flight" / "rows.json").read_text())
    parity = json.loads((run / "_acq" / "parity.json").read_text())
    tp = res["t_prompt"]

    # figure 1: a viewed in-flight overlay (the target driven through a curve, still tracked)
    ov = sorted((run / "flight").glob("overlay_*.png"))[-1]
    shutil.copyfile(ov, PROOF / "flight_follow_overlay.png")

    # figure 2 top: delivered-box IoU vs GT over the flight, prompt marked
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5.4))
    ts = [r["t"] for r in rows]
    iou = [r["lock_iou"] for r in rows]
    ax1.plot(ts, iou, "-", color="#1f9e5a", lw=1)
    ax1.axhline(0.25, ls="--", color="#b02020", lw=1, label="lock floor 0.25")
    ax1.axvline(tp, ls=":", color="#333", lw=1.2, label=f"operator prompt t={tp:.0f}s")
    ax1.set_ylim(0, 1.02); ax1.set_xlabel("flight time (s)"); ax1.set_ylabel("delivered IoU vs GT")
    ax1.set_title(f"P6.2-SHOWCASE closed-loop flight ({res['target_type'].split('.')[-1]}): "
                  f"post-prompt coverage {res['coverage']:.2f}, {res['genuine_lock_frames']}/"
                  f"{res['ticks']} lock frames — copter flies its own control output")
    ax1.legend(loc="upper left", fontsize=8); ax1.grid(alpha=0.3)

    # figure 2 bottom: on-device carry PARITY vs the 3090 twin + ssh round-trip, per step
    both = [r for r in parity if r["jetson"] and r["host"]]
    xs = list(range(len(both)))
    pio = [r["iou"] for r in both]
    med = sorted(pio)[len(pio)//2]
    ax2.plot(xs, pio, "-o", color="#2060c0", ms=3, label=f"Jetson vs 3090-twin IoU (median {med:.3f})")
    ax2.axhline(0.95, ls="--", color="#b02020", lw=1, label="parity gate 0.95")
    ax2.set_ylim(0.5, 1.02); ax2.set_ylabel("carry parity IoU")
    ax2.set_xlabel("on-device carry step (SAM2 on the Orin over ssh-stdio)")
    rtt = sorted(r["rtt_ms"] for r in parity)[len(parity)//2]
    ax2.set_title(f"carry runs LITERALLY on the Jetson: median round-trip {rtt:.0f} ms/step "
                  f"(~{1000/rtt:.1f} Hz), transport ~2 ms", fontsize=9)
    ax2.legend(loc="lower left", fontsize=8); ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROOF / "flight_trace.png", dpi=110)
    print(f"[proof] wrote {PROOF/'flight_follow_overlay.png'} and {PROOF/'flight_trace.png'}",
          flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "ondevice"
    default = {"ondevice": "runs/p62_showcase/ondevice", "flight": "runs/p62_showcase"}
    run = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(default.get(mode, ""))
    if mode == "ondevice":
        ondevice(run)
    elif mode == "flight":
        flight(run)
    else:
        raise SystemExit(f"unknown mode {mode}")
