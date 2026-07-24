"""Proof figures for P6.2-SHOWCASE.

ondevice : the GPU-independent half — the deployed SAM2 carry run literally on the Orin over
           the jetson_carry_service socket, seeded by the oracle GT box, stepped over real
           UAV123 frames. Two figures from runs/p62_showcase/ondevice/{summary,boxes}.json:
             proof/ondevice_carry_midrun.png  — a mid-run overlay (Jetson-carried box on the car)
             proof/ondevice_carry_trace.png   — per-step IoU vs GT + on-device compute ms/step
flight   : (TODO) the closed-loop flight + parity + latency figs — blocked on the host GPU reload.
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


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "ondevice"
    run = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("runs/p62_showcase/ondevice")
    if mode == "ondevice":
        ondevice(run)
    else:
        raise SystemExit(f"mode {mode} not available (flight figs are GPU-blocked)")
