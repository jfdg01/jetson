"""Phase 3a: synthetic nadir camera rendering SITL world state to 640x480 frames.

The camera model is the exact Phase B oracle pinhole (level gimbal, real yaw):
ground plane -> image is an affine map, so the frame is a warpAffine of one
world-anchored ground texture, plus a top-down white car polygon at the rover's
NED position and a world-fixed bridge strip drawn AFTER the car (that IS the
occlusion -- the tracker sees the car disappear under it, no mask injection).

    .venv-ft/bin/python experiments/2026-07-01-temporal-acquire-carry/sitl_cam.py  # selfcheck
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "runners"))

from sitl.oracle_bbox import (  # noqa: E402
    FOCAL_PX, IMG_H, IMG_W, TARGET_LEN_M, TARGET_WID_M, _ned2body,
)

PX_PER_M = 24  # texture resolution; independent of camera scale (F/alt ~= 55 px/m)


def world_to_px(pts_ne: np.ndarray, copter_ned, yaw: float) -> np.ndarray:
    """(K,2) ground NE points -> (K,2) pixel (u,v). Same optics as oracle project()."""
    pts_ne = np.atleast_2d(np.asarray(pts_ne, dtype=np.float64))
    rel = np.zeros((len(pts_ne), 3))
    rel[:, 0] = pts_ne[:, 0] - copter_ned[0]
    rel[:, 1] = pts_ne[:, 1] - copter_ned[1]
    rel[:, 2] = 0.0 - copter_ned[2]
    body = rel @ _ned2body(0.0, 0.0, yaw).T
    cam_x, cam_y, cam_z = body[:, 1], -body[:, 0], body[:, 2]
    return np.stack([FOCAL_PX * cam_x / cam_z + IMG_W / 2,
                     FOCAL_PX * cam_y / cam_z + IMG_H / 2], axis=1)


class NadirCam:
    """render(copter_ned, yaw, rover_ned) -> HxWx3 uint8 BGR frame."""

    def __init__(self, bridge_n: tuple[float, float] | None = None,
                 road_e: float = 0.0, seed: int = 0):
        self.bridge_n = bridge_n          # world-fixed N-extent (m) of the overpass
        # world texture: N in [-20, 140], E in [-25, 25]. North bound covers the
        # E2 1.5 m/s reach (ROVER_START_N 0.5 + 1.5*75 = 113 m) with margin; was
        # [-20, 110] which the 1.5 m/s trailing follow ran off in its last ~2 s.
        self.n0, self.e0 = -20.0, -25.0
        rows, cols = int(160 * PX_PER_M), int(50 * PX_PER_M)
        rng = np.random.default_rng(seed)
        # grass: green base + noise + darker blotches so SAM2 has real background
        tex = np.full((rows, cols, 3), (60, 110, 75), np.uint8)
        tex = (tex + rng.integers(-25, 25, (rows, cols, 1))).clip(0, 255).astype(np.uint8)
        for _ in range(400):
            c = (int(rng.integers(0, cols)), int(rng.integers(0, rows)))
            cv2.circle(tex, c, int(rng.integers(8, 60)), (55, 95, 65), -1)
        tex = cv2.GaussianBlur(tex, (5, 5), 0)
        # N-S asphalt road (5 m wide) under the car's lane, with dashed centreline
        rc = int((road_e - self.e0) * PX_PER_M)
        hw = int(2.5 * PX_PER_M)
        tex[:, rc - hw:rc + hw] = (70, 70, 70)
        for r in range(0, rows, int(4 * PX_PER_M)):
            tex[r:r + int(2 * PX_PER_M), rc - 2:rc + 2] = (200, 200, 200)
        self.tex = tex

    def _tex_to_img(self, copter_ned, yaw) -> np.ndarray:
        src = np.float32([[0, 0], [1000, 0], [0, 1000]])
        ne = np.array([[self.n0 + y / PX_PER_M, self.e0 + x / PX_PER_M]
                       for x, y in src])
        dst = world_to_px(ne, copter_ned, yaw).astype(np.float32)
        return cv2.getAffineTransform(src, dst)

    def _fill_world_rect(self, img, copter_ned, yaw, n_lo, n_hi, e_lo, e_hi, color):
        corners = np.array([[n_lo, e_lo], [n_lo, e_hi], [n_hi, e_hi], [n_hi, e_lo]])
        px = world_to_px(corners, copter_ned, yaw)
        cv2.fillPoly(img, [px.astype(np.int32)], color)
        return px

    def render(self, copter_ned, yaw: float, rover_ned) -> np.ndarray:
        img = cv2.warpAffine(self.tex, self._tex_to_img(copter_ned, yaw),
                             (IMG_W, IMG_H), flags=cv2.INTER_LINEAR)
        rn, re = rover_ned[0], rover_ned[1]
        hl, hw = TARGET_LEN_M / 2, TARGET_WID_M / 2
        # white car body, heading north (front = +N), dark windshield near front
        self._fill_world_rect(img, copter_ned, yaw, rn - hl, rn + hl,
                              re - hw, re + hw, (245, 245, 245))
        self._fill_world_rect(img, copter_ned, yaw, rn + 0.3 * hl, rn + 0.7 * hl,
                              re - 0.8 * hw, re + 0.8 * hw, (60, 50, 40))
        if self.bridge_n is not None:
            b0, b1 = self.bridge_n
            self._fill_world_rect(img, copter_ned, yaw, b0, b1, -30, 30, (90, 90, 90))
            for edge in (b0, b1):  # bridge parapet lines
                self._fill_world_rect(img, copter_ned, yaw, edge - 0.15, edge + 0.15,
                                      -30, 30, (140, 140, 140))
        return img


def selfcheck() -> None:
    from sitl.oracle_bbox import project as oracle_project

    cam = NadirCam(bridge_n=(5.6, 11.6))
    out = HERE / "raw" / "phase3a-rendercheck"
    out.mkdir(parents=True, exist_ok=True)
    for name, cop, rov in [
        ("visible", (0.0, 0.0, -10.0), (0.5, 0.0, 0.0)),      # t=0-ish
        ("occluded", (8.6, 0.0, -10.0), (8.6, 0.0, 0.0)),     # under the bridge
        ("after", (12.5, 0.0, -10.0), (13.0, 0.0, 0.0)),      # re-emerged
        ("yawed", (0.5, 0.0, -10.0), (0.5, 0.0, 0.0)),
    ]:
        yaw = 0.6 if name == "yawed" else 0.0
        img = cam.render(cop, yaw, rov)
        bb = oracle_project(cop, rov, 0.0, 0.0, yaw)
        x1, y1 = int(bb["cx"] - bb["w"] / 2), int(bb["cy"] - bb["h"] / 2)
        x2, y2 = int(bb["cx"] + bb["w"] / 2), int(bb["cy"] + bb["h"] / 2)
        inside = img[y1:y2, x1:x2].mean()
        if name == "occluded":
            assert inside < 130, f"{name}: car visible under bridge (mean {inside:.0f})"
        else:
            assert inside > 150, f"{name}: no car at oracle box (mean {inside:.0f})"
        cv2.imwrite(str(out / f"{name}.png"), img)
    print(f"selfcheck PASS -- frames in {out}")


if __name__ == "__main__":
    selfcheck()
