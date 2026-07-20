"""P6.0 proof deliverables — rebuild everything in proof/ from raw/.

    .venv-ft/bin/python experiments/2026-07-20-p60-flight-rig/make_proof.py

Three deliverables:
  1. camera-before-after.png  — the sky-camera bug, then the fix (both frames
     are real renders captured by cam_probe, not mockups)
  2. tracker-id-churn.png     — the ByteTrack re-find bug: pixel error and
     track-id growth over the same 40 s closed-loop flight, before and after
     the round-1b fix (numbers are the point, so this one is a figure)
  3. midrun-frame.png         — the mid-run frame from the post-fix closed-loop
     run, copied out of raw/ (the "look at it" artifact)
"""
import csv
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
RAW, PROOF = HERE / "raw", HERE / "proof"
PRE = RAW / "phase-c-20260720T105344-run1.csv"    # G3 before the tracker fix
POST = RAW / "phase-c-20260720T110444-run1.csv"   # G3 after,  same config


def _load(path: Path):
    rows = list(csv.DictReader(path.open()))
    return {k: np.array([float(r[k]) for r in rows])
            for k in ("t_s", "pix_err_vs_oracle", "track_id", "loop_dt_ms")}


def camera_before_after() -> None:
    """Side-by-side of the same camera at pitch -pi/2 (sky) and +pi/2 (nadir)."""
    before = cv2.cvtColor(cv2.imread(str(RAW / "cam-probe-sky-pitch-minus-halfpi.png")),
                          cv2.COLOR_BGR2RGB)
    after = cv2.cvtColor(cv2.imread(str(RAW / "cam-probe-fixed-pitch-plus-halfpi.png")),
                         cv2.COLOR_BGR2RGB)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, img, title in (
        (axes[0], before, "BEFORE  pitch = -pi/2  (camera aimed at the SKY)"),
        (axes[1], after, "AFTER  pitch = +pi/2  (nadir: ground + target rover)"),
    ):
        _, counts = np.unique(img.reshape(-1, 3), axis=0, return_counts=True)
        dom = counts.max() / counts.sum()
        ax.imshow(img)
        ax.set_title(f"{title}\ndominant colour {dom:.1%} · mean {img.mean():.0f} "
                     f"· std {img.std():.1f}", fontsize=9)
        ax.axis("off")
    fig.suptitle("P6.0 G2 — Gazebo downward_cam, phase_c world, gz 8.14.0 headless ogre2\n"
                 "the BEFORE frame is what Phase C Branch-2's VLM was grounding in "
                 "(5426ed0 .. 2026-07-20)", fontsize=10)
    fig.tight_layout()
    fig.savefig(PROOF / "camera-before-after.png", dpi=130)
    plt.close(fig)


def tracker_id_churn() -> None:
    """Pixel error + track-id growth, same 40 s flight, before/after round 1b."""
    pre, post = _load(PRE), _load(POST)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.5, 6.4), sharex=True)

    for d, label, colour in ((pre, "before fix", "tab:red"),
                             (post, "after fix", "tab:blue")):
        e = d["pix_err_vs_oracle"]
        a1.plot(d["t_s"], e, lw=0.9, color=colour,
                label=f"{label} — mean {e.mean():.1f} px")
        a2.plot(d["t_s"], d["track_id"], lw=1.2, color=colour,
                label=f"{label} — {int(d['track_id'].max())} ids")

    a1.set_ylabel("track vs oracle (px)")
    a1.set_title("P6.0 G3 — same 40 s closed-loop flight, 1 Hz oracle detections at 20 Hz\n"
                 "ByteTrack round-1b re-find: a lost track could only be recovered by a\n"
                 "LOW-score detection, so every score=1.0 injection spawned a fresh id",
                 fontsize=10)
    a1.legend(fontsize=8)
    a1.grid(alpha=0.3)

    a2.set_ylabel("track id in use")
    a2.set_xlabel("t (s)")
    a2.legend(fontsize=8)
    a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROOF / "tracker-id-churn.png", dpi=130)
    plt.close(fig)

    for d, label in ((pre, "pre "), (post, "post")):
        hz = 1000.0 / d["loop_dt_ms"][1:]
        print(f"  {label}: mean_px_err={d['pix_err_vs_oracle'].mean():5.1f}  "
              f"ids={int(d['track_id'].max()):2d}  mean_hz={hz.mean():.2f}  "
              f"ticks<15Hz={(hz < 15).sum()}")


if __name__ == "__main__":
    PROOF.mkdir(exist_ok=True)
    camera_before_after()
    tracker_id_churn()
    src = RAW / "phase-c-20260720T110444-run1-midrun.png"
    (PROOF / "midrun-frame.png").write_bytes(src.read_bytes())
    print(f"wrote {len(list(PROOF.iterdir()))} files to {PROOF}")
