"""
Minimal ByteTrack implementation for Phase B/C.

Kalman filter (constant-velocity, pixel space) + two-round IoU matching.
Designed for the Phase B/C use case: single dominant target, ~25 Hz oracle
(Phase B) or ~1.2 Hz VLM (Phase C) with Kalman propagation between updates.

State vector: [cx, cy, w, h, vx, vy, vw, vh]  (8-D, pixel coordinates)
Measurement:  [cx, cy, w, h]                   (4-D)

References: ByteTrack (Zhang et al., 2022) — simplified to single-class,
no appearance embedding (not needed when oracle or VLM provides one box/frame).

Unit test: python experiments/sitl/bytetrack.py
"""

import numpy as np
from scipy.optimize import linear_sum_assignment

# Kalman filter noise (tuned for ~25 Hz oracle; scale Q up for VLM at 1.2 Hz)
_STD_WEIGHT_POS = 1.0 / 20   # positional noise relative to bbox height
_STD_WEIGHT_VEL = 1.0 / 160  # velocity noise relative to bbox height

# Matching thresholds
HIGH_IOU_THR = 0.3    # round-1: confirmed tracks vs high-conf detections
LOW_IOU_THR  = 0.1    # round-2: lost tracks  vs low-conf  detections
MAX_LOST_FRAMES = 30  # frames before a lost track is deleted


class KalmanBox:
    """Single tracked object with constant-velocity Kalman filter."""

    _F = np.eye(8)                  # state transition
    _F[:4, 4:] = np.eye(4)         # pos += vel * dt (dt=1 frame)

    _H = np.zeros((4, 8))          # measurement matrix
    _H[:4, :4] = np.eye(4)        # observes [cx, cy, w, h]

    def __init__(self, bbox: dict, track_id: int):
        """
        Args:
            bbox: dict with keys cx, cy, w, h
            track_id: unique integer ID for this track
        """
        self.id = track_id
        self.lost = 0           # frames since last matched detection
        self.age = 1            # total frames alive
        self.hits = 1           # matched detection count

        # State: [cx, cy, w, h, vx, vy, vw, vh]
        self.x = np.array([bbox["cx"], bbox["cy"], bbox["w"], bbox["h"],
                            0.0, 0.0, 0.0, 0.0], dtype=float)
        h = bbox["h"]
        std = self._init_std(h)
        self.P = np.diag(std ** 2)

    def _init_std(self, h: float) -> np.ndarray:
        return np.array([
            2 * _STD_WEIGHT_POS * h,
            2 * _STD_WEIGHT_POS * h,
            2 * _STD_WEIGHT_POS * h,
            2 * _STD_WEIGHT_POS * h,
            10 * _STD_WEIGHT_VEL * h,
            10 * _STD_WEIGHT_VEL * h,
            10 * _STD_WEIGHT_VEL * h,
            10 * _STD_WEIGHT_VEL * h,
        ])

    def _proc_std(self) -> np.ndarray:
        h = self.x[3]
        return np.array([
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_VEL * h,
            _STD_WEIGHT_VEL * h,
            _STD_WEIGHT_VEL * h,
            _STD_WEIGHT_VEL * h,
        ])

    def predict(self):
        """Propagate state one timestep (call once per frame)."""
        Q = np.diag(self._proc_std() ** 2)
        self.x = self._F @ self.x
        self.P = self._F @ self.P @ self._F.T + Q
        self.x[2] = max(1.0, self.x[2])   # w > 0
        self.x[3] = max(1.0, self.x[3])   # h > 0
        self.age += 1

    def update(self, bbox: dict):
        """Correct state with a matched detection."""
        z = np.array([bbox["cx"], bbox["cy"], bbox["w"], bbox["h"]])
        h = bbox["h"]
        R = np.diag((np.array([
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
            _STD_WEIGHT_POS * h,
        ])) ** 2)
        S = self._H @ self.P @ self._H.T + R
        K = self.P @ self._H.T @ np.linalg.inv(S)
        self.x = self.x + K @ (z - self._H @ self.x)
        self.P = (np.eye(8) - K @ self._H) @ self.P
        self.x[2] = max(1.0, self.x[2])
        self.x[3] = max(1.0, self.x[3])
        self.lost = 0
        self.hits += 1

    @property
    def bbox(self) -> dict:
        return {"cx": self.x[0], "cy": self.x[1], "w": self.x[2], "h": self.x[3]}


def _iou(a: dict, b: dict) -> float:
    """IoU between two bboxes (dict with cx,cy,w,h)."""
    ax1, ay1 = a["cx"] - a["w"] / 2, a["cy"] - a["h"] / 2
    ax2, ay2 = a["cx"] + a["w"] / 2, a["cy"] + a["h"] / 2
    bx1, by1 = b["cx"] - b["w"] / 2, b["cy"] - b["h"] / 2
    bx2, by2 = b["cx"] + b["w"] / 2, b["cy"] + b["h"] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / union if union > 0 else 0.0


def _iou_matrix(tracks: list, dets: list) -> np.ndarray:
    """(n_tracks × n_dets) IoU matrix."""
    m = np.zeros((len(tracks), len(dets)))
    for i, t in enumerate(tracks):
        for j, d in enumerate(dets):
            m[i, j] = _iou(t.bbox, d)
    return m


def _hungarian(cost: np.ndarray, thr: float) -> tuple[list, list, list]:
    """
    Solve assignment on 1-IoU cost matrix.
    Returns (matched_pairs, unmatched_track_idxs, unmatched_det_idxs).
    """
    if cost.size == 0:
        return [], list(range(cost.shape[0])), list(range(cost.shape[1]))
    row_ind, col_ind = linear_sum_assignment(cost)
    matched, unmatched_t, unmatched_d = [], [], []
    matched_rows, matched_cols = set(), set()
    for r, c in zip(row_ind, col_ind):
        if cost[r, c] < 1.0 - thr:
            matched.append((r, c))
            matched_rows.add(r)
            matched_cols.add(c)
    unmatched_t = [i for i in range(cost.shape[0]) if i not in matched_rows]
    unmatched_d = [j for j in range(cost.shape[1]) if j not in matched_cols]
    return matched, unmatched_t, unmatched_d


class ByteTracker:
    """
    Single-class ByteTrack tracker.

    Usage:
        tracker = ByteTracker()
        for frame in ...:
            # dets = list of dicts {cx, cy, w, h, score} from oracle or VLM
            tracks = tracker.update(dets)
            # tracks = list of KalmanBox objects with confirmed state
    """

    def __init__(self):
        self._tracks: list[KalmanBox] = []
        self._lost:   list[KalmanBox] = []
        self._next_id = 1

    def update(self, detections: list[dict]) -> list[KalmanBox]:
        """
        Run one frame update.

        Args:
            detections: list of {cx, cy, w, h, score} dicts.
                        score in [0,1]; high >= 0.5, low < 0.5.

        Returns:
            List of KalmanBox objects with valid Kalman estimates — includes
            recently-lost tracks (lost > 0 but <= MAX_LOST_FRAMES) so the
            control loop can coast on predictions between sparse VLM updates.
        """
        high_dets = [d for d in detections if d.get("score", 1.0) >= 0.5]
        low_dets  = [d for d in detections if d.get("score", 1.0) <  0.5]

        # Predict all existing tracks; advance lost counter for _lost tracks
        for t in self._tracks:
            t.predict()
        for t in self._lost:
            t.predict()
            t.lost += 1

        # --- Round 1: confirmed tracks vs high-confidence detections ---
        if self._tracks and high_dets:
            iou_m = _iou_matrix(self._tracks, high_dets)
            matched, unmatched_t, unmatched_hd = _hungarian(
                1.0 - iou_m, HIGH_IOU_THR)
            for ti, di in matched:
                self._tracks[ti].update(high_dets[di])
        else:
            unmatched_t  = list(range(len(self._tracks)))
            unmatched_hd = list(range(len(high_dets)))

        # --- Round 2: unmatched active tracks + lost tracks vs low-conf dets ---
        n_active_r2 = len(unmatched_t)
        r2_tracks = [self._tracks[i] for i in unmatched_t] + self._lost
        if r2_tracks and low_dets:
            iou_m2 = _iou_matrix(r2_tracks, low_dets)
            matched2, unmatched_r2, _ = _hungarian(
                1.0 - iou_m2, LOW_IOU_THR)
            matched_r2_idxs = {ti for ti, _ in matched2}
            for ti, di in matched2:
                r2_tracks[ti].update(low_dets[di])
                if r2_tracks[ti] in self._lost:
                    self._lost.remove(r2_tracks[ti])
                    self._tracks.append(r2_tracks[ti])
            # Active tracks still unmatched after round 2
            still_unmatched_t = [
                r2_tracks[i] for i in range(n_active_r2)
                if i not in matched_r2_idxs
            ]
        else:
            still_unmatched_t = [self._tracks[i] for i in unmatched_t]

        # Mark unmatched active tracks as lost
        for t in still_unmatched_t:
            t.lost += 1
            if t in self._tracks:
                self._tracks.remove(t)
                self._lost.append(t)

        # Delete tracks lost too long
        self._lost = [t for t in self._lost if t.lost <= MAX_LOST_FRAMES]

        # Create new tracks from unmatched high-conf detections
        for di in unmatched_hd:
            d = high_dets[di]
            if d["w"] > 0 and d["h"] > 0:
                self._tracks.append(KalmanBox(d, self._next_id))
                self._next_id += 1

        # Return active tracks + lost-but-coasting tracks (Kalman still valid)
        return self._tracks + self._lost

    def reset(self):
        self._tracks.clear()
        self._lost.clear()
        self._next_id = 1


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def _test_single_track_no_loss():
    """Single detection per frame; track should never be lost."""
    tracker = ByteTracker()
    det = {"cx": 320.0, "cy": 240.0, "w": 60.0, "h": 100.0, "score": 1.0}
    for frame in range(50):
        det_moved = {**det, "cx": 320.0 + frame * 2}
        tracks = tracker.update([det_moved])
        assert len(tracks) == 1, f"frame {frame}: expected 1 track, got {len(tracks)}"
        assert tracks[0].lost == 0
    print(f"  single-track test PASS  (50 frames, track id={tracks[0].id})")


def _test_kalman_prediction():
    """After 5 frames without detection, Kalman should predict ahead."""
    tracker = ByteTracker()
    det = {"cx": 100.0, "cy": 240.0, "w": 60.0, "h": 100.0, "score": 1.0}
    # Feed 10 detections moving at +10 px/frame so Kalman learns velocity
    for i in range(10):
        tracker.update([{**det, "cx": 100.0 + i * 10}])
    # cx after 10 frames = 100 + 9*10 = 190; learned vel ≈ +10 px/frame
    # Feed 5 blank frames — track coasts; cx should grow beyond 190
    last_cx_list = []
    for _ in range(5):
        tracks = tracker.update([])
        if tracks:
            last_cx_list.append(tracks[0].bbox["cx"])
    assert len(last_cx_list) > 0, "Track lost immediately — update() not returning _lost tracks"
    assert last_cx_list[-1] > 190.0, \
        f"Kalman prediction stalled at cx={last_cx_list[-1]:.1f} (expected > 190)"
    print(f"  Kalman-prediction test PASS  cx after 5 blank frames: "
          f"{last_cx_list[-1]:.1f}  (expected > 190)")


def _test_new_track_after_loss():
    """Track deleted after MAX_LOST_FRAMES; new detection spawns new id."""
    tracker = ByteTracker()
    det = {"cx": 320.0, "cy": 240.0, "w": 60.0, "h": 100.0, "score": 1.0}
    tracker.update([det])
    first_id = tracker._tracks[0].id if tracker._tracks else tracker._lost[0].id
    for _ in range(MAX_LOST_FRAMES + 2):
        tracker.update([])
    assert len(tracker._lost) == 0, "old track should be deleted"
    tracker.update([det])
    new_id = tracker._tracks[0].id
    assert new_id != first_id, f"Expected new id, got same id={new_id}"
    print(f"  re-detection test PASS  first_id={first_id}  new_id={new_id}")


def _test_iou():
    a = {"cx": 50, "cy": 50, "w": 100, "h": 100}
    b = {"cx": 50, "cy": 50, "w": 100, "h": 100}
    assert abs(_iou(a, b) - 1.0) < 1e-9
    c = {"cx": 200, "cy": 200, "w": 100, "h": 100}
    assert _iou(a, c) == 0.0
    print("  iou test PASS")


if __name__ == "__main__":
    print("bytetrack unit tests:")
    _test_iou()
    _test_single_track_no_loss()
    _test_kalman_prediction()
    _test_new_track_after_loss()
    print("all bytetrack tests passed")
