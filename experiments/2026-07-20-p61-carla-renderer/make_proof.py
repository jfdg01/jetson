#!/usr/bin/env python3
"""
make_proof.py -- P6.1 proof figures from runs/*/results.json.

    .venv-ft/bin/python experiments/2026-07-20-p61-carla-renderer/make_proof.py

Writes proof/pose-slaving-track.png. Reproducible from the committed results.json
alone -- it reads no frames and talks to no simulator.
"""
from pathlib import Path

import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
FIXED_DT = 0.05  # the simulated step the world was ticked at


def main():
    res = json.loads((HERE / "runs/g3-mavlink/results.json").read_text())
    pose = res["pose_track"]
    t = [i * FIXED_DT for i in range(len(pose))]
    north = [p[0] for p in pose]
    alt = [-p[2] for p in pose]
    hz = [1.0 / dt for dt in res["tick_dt"]]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

    ax1.plot(t, north, label="north (m)")
    ax1.plot(t, alt, label="altitude (m)")
    ax1.set_ylabel("position (m)")
    ax1.set_title("P6.1 G3 -- CARLA camera slaved to live ArduCopter SITL pose\n"
                  f"{res['town']}, {res['vehicles']} autonomous vehicles, "
                  f"nadir pitch {res['pitch_deg']:.0f} deg")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    # mark the frames that were captured AND opened -- the gate is the viewing,
    # not the writing, so the figure should say which ticks were actually checked
    for n in (len(pose) // 4, len(pose) // 2, len(pose) - 1):
        ax1.axvline(n * FIXED_DT, color="k", ls=":", lw=1)
        ax1.text(n * FIXED_DT, max(north) * 0.05, f" frame {n}", fontsize=8, rotation=90)

    ax2.plot(t[1:], hz, lw=0.8)
    ax2.axhline(20, color="tab:green", ls="--", label="20 Hz gate (P6.0 loop rate)")
    ax2.axhline(15, color="tab:red", ls="--", label="15 Hz floor")
    ax2.set_xlabel("simulated time (s)")
    ax2.set_ylabel("wall-clock tick rate (Hz)")
    ax2.set_ylim(0, max(hz) * 1.1)
    ax2.legend(loc="lower right")
    ax2.grid(alpha=0.3)
    ax2.set_title(f"mean {res['mean_hz']:.1f} Hz, "
                  f"{res['ticks_under_15hz']}/{len(hz)} ticks under 15 Hz")

    fig.tight_layout()
    out = HERE / "proof/pose-slaving-track.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=130)
    print("wrote", out)


if __name__ == "__main__":
    main()
