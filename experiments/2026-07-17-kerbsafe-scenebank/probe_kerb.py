#!/usr/bin/env python
"""P5.9 design-time probe: map rendered-car integrity over (s, lat) on the
select_arena straight, to calibrate kerb-safe lateral spawn bands.

Motivation (P5.8): seed 101's blue distractor rode lat ~= 4.6-5.2 m and clipped
into the median kerb at s >~ 40 m, rendering as two disconnected blobs
(runs/seed101_A/overlay_f0180.png). The safe corridor is a function of BOTH
s (along-track) and lat (cross-track) because the physical kerbs are not exactly
parallel to ROAD_HEADING=145 deg. This probe drives one blue car over a
(s, lat) grid with the camera at a run-like oblique standoff, and measures:

  - npx_ratio: car-colour pixel count / per-station max (occlusion -> drop)
  - frag:      largest-connected-component fraction of car-colour pixels
               (clipping -> the body splits, frag drops toward ~0.5)

Outputs (all in this experiment's curation/):
  kerb_sweep.json   raw grid samples
  kerb_heatmap.png  2-panel (s, lat) heatmap of npx_ratio and frag + derived bands
  kerb_sample_*.png a few raw frames at band edges for eyeball confirmation

Needs a live select_arena server (same launch as the run matrix). Runtime ~1 min.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("scenegen", REPO / "runners" / "scenegen.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)
import cv2  # after scenegen (which imports venv cv2 before dist-packages append)

S_STATIONS = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
LATS = np.round(np.arange(-8.0, 8.01, 0.5), 2)
STANDOFF, ALT = 15.0, 15.0
FRAG_MIN_NPX = 30


def frag_metric(bgr, bbox, color, pad=0.10):
    x1, y1, x2, y2 = bbox
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = max(0, int(x1 - dx)), max(0, int(y1 - dy))
    x2, y2 = min(bgr.shape[1], int(x2 + dx)), min(bgr.shape[0], int(y2 + dy))
    m = sg.color_mask(bgr[y1:y2, x1:x2], color).astype(np.uint8)
    npx = int(m.sum())
    if npx < FRAG_MIN_NPX:
        return None, npx
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    return float(stats[1:, 4].max() / npx), npx


def main():
    h = sg.ROAD_HEADING
    u = np.array([math.cos(h), math.sin(h)])
    n = np.array([-math.sin(h), math.cos(h)])
    gz = sg.GzClient()
    import time
    time.sleep(0.7)
    gz.spawn_car("car_probe", sg.CAR_COLORS["blue"][0])
    # warmup at the first grid cell
    p0 = sg.GRID + S_STATIONS[0] * u + LATS[0] * n
    cam0 = np.array([*(p0 - u * STANDOFF), ALT])
    q0, _, _ = sg.look_at(cam0, [*p0, 0.0])
    yaw_q = sg.quat_yaw_pitch(h, 0.0)
    gz.set_poses([("uav_cam", cam0, q0), ("car_probe", (*p0, sg.CAR_Z), yaw_q)])
    warm = None
    for _ in range(5):
        warm, _ = gz.step_one_frame()
    assert warm is not None and warm.std() > 5, "warmup dead frame -- EGL env?"

    rows = []
    samples_dumped = 0
    for s in S_STATIONS:
        for lat in LATS:
            p = sg.GRID + s * u + float(lat) * n
            cam = np.array([*(p - u * STANDOFF), ALT])
            q, _, _ = sg.look_at(cam, [*p, 0.0])
            gz.set_poses([("uav_cam", cam, q), ("car_probe", (*p, sg.CAR_Z), yaw_q)])
            arr, _ = gz.step_one_frame()
            bgr = arr[:, :, ::-1]
            bbox, area = sg.project_box(cam, q, (*p, sg.CAR_Z), h)
            frag, npx = (None, 0) if bbox is None else frag_metric(bgr, bbox, "blue")
            rows.append({"s": s, "lat": float(lat), "npx": npx,
                         "frag": frag, "bbox": bbox})
            if frag is not None and frag < 0.9 and samples_dumped < 8:
                cv2.imwrite(str(HERE / "curation" / f"kerb_sample_s{int(s)}_lat{lat:+.1f}.png"), bgr)
                samples_dumped += 1
    gz.proxy.close()

    # per-station reference = max npx over the sweep
    out = {"stations": S_STATIONS, "lats": LATS.tolist(), "rows": rows}
    with open(HERE / "curation" / "kerb_sweep.json", "w") as f:
        json.dump(out, f)

    # grids
    S, L = len(S_STATIONS), len(LATS)
    npx = np.array([r["npx"] for r in rows], float).reshape(S, L)
    frag = np.array([r["frag"] if r["frag"] is not None else 0.0 for r in rows]).reshape(S, L)
    ref = npx.max(axis=1, keepdims=True)
    ratio = npx / np.maximum(ref, 1)

    ok = (ratio >= 0.90) & (frag >= 0.98)
    safe_all_s = ok.all(axis=0)  # lat safe at EVERY station
    bands = []
    start = None
    for i, v in enumerate(safe_all_s):
        if v and start is None:
            start = i
        if (not v or i == L - 1) and start is not None:
            end = i if v else i - 1
            bands.append((float(LATS[start]), float(LATS[end])))
            start = None
    print("kerb-safe lat bands (ratio>=0.90 AND frag>=0.98 at all stations):", bands)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, grid, title in ((axes[0], ratio, "npx ratio (car pixels / station max)"),
                            (axes[1], frag, "largest-connected-component fraction")):
        im = ax.imshow(grid, aspect="auto", origin="lower", vmin=0, vmax=1, cmap="viridis",
                       extent=[LATS[0], LATS[-1], -0.5, S - 0.5])
        ax.set_yticks(range(S))
        ax.set_yticklabels([f"s={int(s)}" for s in S_STATIONS])
        ax.set_title(title)
        fig.colorbar(im, ax=ax)
        for lo, hi in bands:
            ax.axvline(lo, color="w", ls="--", lw=1)
            ax.axvline(hi, color="w", ls="--", lw=1)
    axes[1].set_xlabel("lat (m, +left of ROAD_HEADING)")
    fig.suptitle("P5.9 kerb-safety sweep, select_arena straight (blue probe car)")
    fig.tight_layout()
    fig.savefig(HERE / "curation" / "kerb_heatmap.png", dpi=110)
    print("wrote curation/kerb_sweep.json + kerb_heatmap.png")


if __name__ == "__main__":
    main()
