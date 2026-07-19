"""P5.15 carry-horizon rig (Part V).

Question: how long does a warm SAM2 carry survive on real UAV123 video, and
does the deployed idle ROI re-anchor lever extend that horizon? Every Part V
select result (P5.1-P5.14) carried for at most ~8 s of idle before the prompt;
P5.14 named "carry quality on real video" the binding constraint (its one FAIL
was carry-off-object). This rig measures carry survival directly, with no
prompt and no select step.

Arms (per clip, seeded at GT[0], stepped at the deployed CARRY_HZ budget):
  PLAIN : SAM2 carry only, no maintenance  = the P5.1/P5.2 idle convention.
  MAINT : PLAIN + ROI re-anchor (the deployed P5.5 lever, select_p55.
          roi_reanchor: margin 2.0, min_side 256, crop 512, accept =
          parseable+valid, NO IoU floor) every REANCHOR_EVERY frames, VLM =
          Jetson q8_0 terse with the clip's P5.2 caption.

Scoring: at each horizon h in {8,16,24} s the carried box at the scoring
frame is compared to UAV123 GT; alive = IoU >= ALIVE_IOU. Scoring frame =
h*30, or the nearest valid-GT frame within +-GT_TOL if GT is absent there
(tie -> earlier frame); no valid GT in the window -> horizon N/A for that
cell (excluded from that horizon's denominator).

Non-gating diagnostics logged per cell: full per-step IoU trace, first-death
frame (first valid-GT step with box lost or IoU < DEATH_IOU), HSV-histogram
correlation of the carried-box crop vs the seed crop, and box-area ratio.

    .venv-ft/bin/python experiments/2026-07-19-carry-horizon/carry_horizon_p515.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-19-carry-horizon/carry_horizon_p515.py \
        --matrix experiments/2026-07-19-carry-horizon/clips_p515.json --arm PLAIN --out runs
    .venv-ft/bin/python ... --arm MAINT --out runs
    .venv-ft/bin/python ... --arm PLAIN --only car7 --out runs      # subset
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
P53 = REPO / "experiments" / "2026-07-14-multi-candidate-select"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, P55, P53, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import iou, load_uav123_gt                     # noqa: E402
from replay_e24 import CARRY_HZ, MAX_SIDE, _rgb, _valid, vlm_acquire  # noqa: E402
from select_p55 import (                                           # noqa: E402
    ROI_MARGIN, ROI_MIN_SIDE, ROI_RES, roi_reanchor,
)

FPS = 30.0
HORIZONS_S = (8, 16, 24)       # scoring horizons (frames h*30 from f0=0)
ALIVE_IOU = 0.25               # carried box vs GT at the scoring frame
GT_TOL = 30                    # frames: nearest-valid-GT fallback window
DEATH_IOU = 0.10               # diagnostic first-death threshold (non-gating)
REANCHOR_EVERY = 165           # MAINT cadence, extends P5.5's f0+90/f0+165 spacing
ARMS = ("PLAIN", "MAINT")


# --------------------------------------------------------------------------- #
def scoring_frames(gt, fps: float = FPS, horizons=HORIZONS_S,
                   tol: int = GT_TOL) -> dict:
    """horizon_s -> scoring frame index with valid GT (nearest to h*fps within
    +-tol, tie -> earlier), or None if no valid GT in the window."""
    out = {}
    for h in horizons:
        F = round(h * fps)
        best = None
        for d in range(tol + 1):
            for f in (F - d, F + d):
                if 0 <= f < len(gt) and gt[f] is not None:
                    best = f
                    break
            if best is not None:
                break
        out[h] = best
    return out


def crop_hist(frame_bgr, box):
    """HSV H+S histogram of the box crop (clamped to frame), for the carry
    health diagnostic. Returns None for degenerate crops."""
    h, w = frame_bgr.shape[:2]
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(w, int(box[2])), min(h, int(box[3]))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    hsv = cv2.cvtColor(frame_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def run_cell(arm: str, clip: str, caption: str, gt, frame_at, submit_img,
             make_carry, *, fps: float = FPS) -> dict:
    """One (arm, clip) cell, fully injectable (stubbed in --selfcheck).
    Steps a single carry seeded at GT[0] through the frames at the deployed
    CARRY_HZ budget (stride = round(fps/CARRY_HZ) = 5 at 30 fps), forcing the
    schedule to land exactly on every scoring frame; MAINT additionally
    re-anchors at multiples of REANCHOR_EVERY (< the last scoring frame).
    Returns the per-cell result dict (not yet written to disk)."""
    assert arm in ARMS, arm
    stride = max(1, round(fps / CARRY_HZ))
    sf = scoring_frames(gt, fps)
    must = sorted({f for f in sf.values() if f is not None})
    assert must, f"{clip}: no scoreable horizon at all"
    end = max(must)
    reanchors = ([f for f in range(REANCHOR_EVERY, end, REANCHOR_EVERY)]
                 if arm == "MAINT" else [])
    # re-anchor frames must not coincide with scoring frames (score would be
    # ambiguous pre/post reseed) -- true by construction for the frozen
    # constants (165k vs 240/480/720 +- 30), asserted here.
    assert not set(reanchors) & set(must), (reanchors, must)
    steps = sorted(set(range(stride, end + 1, stride)) | set(must)
                   | set(reanchors))

    seed = tuple(gt[0])
    frame0 = frame_at(0)
    carry = make_carry(_rgb(frame0), seed)
    seed_h = crop_hist(frame0, seed)
    seed_area = (seed[2] - seed[0]) * (seed[3] - seed[1])

    trace = []                 # [frame, box|None, iou|None]
    box_at: dict[int, tuple | None] = {}
    ra_log = []
    cur = seed                 # last valid carried box (re-anchor prior)
    for f in steps:
        frame = frame_at(f)
        _, b = carry.step(_rgb(frame))
        box = tuple(b) if _valid(b, frame.shape) else None
        if box is not None:
            cur = box
        g = gt[f] if f < len(gt) else None
        iv = iou(box, g) if (box is not None and g is not None) else None
        trace.append([f, box, iv])
        box_at[f] = box
        if f in reanchors:
            new_box, dbg = roi_reanchor(frame, cur, caption, submit_img)
            accepted = new_box is not None
            if accepted:
                carry = make_carry(_rgb(frame), new_box)
                cur = tuple(new_box)
                box_at[f] = cur            # post-reanchor box at this frame
                trace[-1][1] = cur
                trace[-1][2] = iou(cur, g) if g is not None else None
            ra_log.append({"frame": f, **dbg, "accepted": accepted,
                           "new_box": None if new_box is None
                           else [round(v, 1) for v in new_box]})

    horizons = {}
    for h, f in sf.items():
        if f is None:
            horizons[str(h)] = {"scoring_frame": None, "na": True}
            continue
        box, g = box_at[f], gt[f]
        iv = iou(box, g) if box is not None else 0.0
        frame = frame_at(f)
        hh = crop_hist(frame, box) if box is not None else None
        hist_corr = (float(cv2.compareHist(seed_h, hh, cv2.HISTCMP_CORREL))
                     if (seed_h is not None and hh is not None) else None)
        area = ((box[2] - box[0]) * (box[3] - box[1])
                if box is not None else 0.0)
        horizons[str(h)] = {
            "scoring_frame": f, "na": False,
            "box": None if box is None else [round(v, 1) for v in box],
            "gt": [round(v, 1) for v in g],
            "iou": round(iv, 4), "alive": iv >= ALIVE_IOU,
            "hist_corr": None if hist_corr is None else round(hist_corr, 4),
            "area_ratio": round(area / seed_area, 4) if seed_area else None,
        }

    death = next((f for f, box, iv in trace
                  if gt[f] is not None and (box is None or iv < DEATH_IOU)),
                 None)
    return {
        "arm": arm, "clip": clip, "caption": caption, "fps": fps,
        "stride": stride, "cap_hz": CARRY_HZ, "alive_iou": ALIVE_IOU,
        "death_iou": DEATH_IOU, "gt_tol": GT_TOL,
        "reanchor_every": REANCHOR_EVERY if arm == "MAINT" else None,
        "reanchor": ra_log, "seed": [round(v, 1) for v in seed],
        "horizons": horizons, "death_frame": death,
        "trace": [[f, None if b is None else [round(v, 1) for v in b],
                   None if iv is None else round(iv, 4)] for f, b, iv in trace],
    }


# --------------------------------------------------------------------------- #
def frame_health(img) -> None:
    """CLAUDE.md cheap asserts: a frame >99% one colour is a failed render."""
    flat = img.reshape(-1, img.shape[-1]) if img.ndim == 3 else img.reshape(-1, 1)
    _, counts = np.unique(flat, axis=0, return_counts=True)
    assert counts.max() / len(flat) < 0.99, "frame is >99% one colour"


def write_overlay(frame_bgr, box, g, path: Path, label: str) -> None:
    img = frame_bgr.copy()
    if g is not None:
        cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])),
                      (0, 0, 255), 2)                       # GT red
    if box is not None:
        cv2.rectangle(img, (int(box[0]), int(box[1])),
                      (int(box[2]), int(box[3])), (0, 255, 0), 2)  # carry green
    cv2.putText(img, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (255, 255, 255), 2)
    frame_health(img)
    cv2.imwrite(str(path), img)


def run_matrix_cell(arm, clip, caption, out_dir: Path, *, predictor,
                    submit_img) -> dict:
    """Real-stack cell: UAV123 frames, SAM2 carry local (rate-capped),
    MAINT re-anchor through the Jetson q8_0 backend. Writes results.json +
    horizon overlays (h8/h16/h24.png) + death.png if the carry died."""
    from stream_carry import StreamCarry

    data = E18 / "data" / "UAV123"
    seq_dir = data / "data_seq" / "UAV123" / clip
    gt = load_uav123_gt(data / "anno" / "UAV123" / f"{clip}.txt")
    paths = sorted(seq_dir.glob("*.jpg"))

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    wall0 = time.time()
    result = run_cell(arm, clip, caption, gt, frame_at, submit_img, make_carry)
    result["wall_s"] = round(time.time() - wall0, 1)

    out_dir.mkdir(parents=True, exist_ok=True)
    prev = None
    for h, rec in result["horizons"].items():
        if rec["na"]:
            continue
        f = rec["scoring_frame"]
        frame = frame_at(f)
        # dead-feed assert: consecutive horizon frames must not be identical
        if prev is not None:
            assert not np.array_equal(frame, prev), "byte-identical horizon frames"
        prev = frame
        write_overlay(frame, rec["box"], gt[f], out_dir / f"h{h}.png",
                      f"{arm} {clip} h={h}s f={f} IoU={rec['iou']:.3f} "
                      f"alive={rec['alive']}")
    if result["death_frame"] is not None:
        f = result["death_frame"]
        box = next(b for fr, b, _ in result["trace"] if fr == f)
        write_overlay(frame_at(f), box, gt[f], out_dir / "death.png",
                      f"{arm} {clip} DEATH f={f}")
    (out_dir / "results.json").write_text(json.dumps(result, indent=1))
    alive = {h: r.get("alive") for h, r in result["horizons"].items()}
    print(f"[P5.15 {arm} {clip}] alive={alive} death={result['death_frame']} "
          f"reanchor={[r['accepted'] for r in result['reanchor']]} "
          f"wall={result['wall_s']}s", flush=True)
    return result


def run_matrix(arm: str, matrix_path: Path, out_root: Path,
               only: list[str] | None) -> None:
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL

    cfg = json.loads(matrix_path.read_text())
    clips = [c for c in cfg["clips"] if not only or c["clip"] in only]
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)

    be = None
    submit_img = None
    if arm == "MAINT":
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        print("[P5.15] booting Jetson q8_0 (once for the arm)...", flush=True)
        be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                           f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                           ssh_host="jetson", max_side=MAX_SIDE)

        def submit_img(img_bgr, caption):
            h, w = img_bgr.shape[:2]
            path = f"/dev/shm/p515_acq_{time.monotonic_ns()}.png"
            cv2.imwrite(path, img_bgr)
            try:
                return vlm_acquire(be, path, caption, w, h)
            finally:
                Path(path).unlink(missing_ok=True)

    try:
        for c in clips:
            out_dir = out_root / f"{arm}_{c['clip']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.15] skip {out_dir.name} (results.json exists)",
                      flush=True)
                continue
            try:
                with torch.inference_mode(), \
                     torch.autocast("cuda", dtype=torch.bfloat16):
                    run_matrix_cell(arm, c["clip"], c["caption"], out_dir,
                                    predictor=predictor, submit_img=submit_img)
            except Exception:  # one cell's crash must not sink the matrix
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "results.json").write_text(json.dumps(
                    {"arm": arm, "clip": c["clip"],
                     "INVALID": traceback.format_exc()}, indent=1))
                print(f"[INVALID] {arm} {c['clip']}\n{traceback.format_exc()}",
                      flush=True)
    finally:
        if be is not None:
            be.close()


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub carries + stub VLM on synthetic textured frames. Asserts:
    (1) step schedule lands on every scoring frame and re-anchor frames are
    disjoint from them; (2) a holding carry is alive 3/3; (3) a drifting carry
    dies with the right death frame and alive pattern; (4) MAINT re-anchor
    fires at 165/330/495/660, an accepted answer reseeds and rescues the
    horizon, a reject leaves the carry alone; (5) GT-absent fallback picks the
    nearest valid frame, tie -> earlier; (6) no valid GT in the window -> N/A;
    (7) overlay writer passes/fails the frame-health asserts as designed."""
    rng = np.random.default_rng(0)
    H, W = 240, 320
    base = rng.integers(0, 255, (H, W, 3), np.uint8)   # textured, health-safe
    frame_at = lambda _i: base.copy()                  # noqa: E731
    boxT = (100.0, 100.0, 140.0, 140.0)
    gt = [boxT] * 800

    class StubCarry:
        def __init__(self, fn):
            self.fn = fn

        def step(self, _f):
            return None, self.fn()

    def make_hold(_r, b):
        bb = tuple(b)
        return StubCarry(lambda: bb)

    r = run_cell("PLAIN", "stub", "the car", gt, frame_at, None, make_hold)
    # (1) schedule + scoring frames
    assert [r["horizons"][str(h)]["scoring_frame"] for h in (8, 16, 24)] \
        == [240, 480, 720]
    assert r["stride"] == 5 and r["trace"][-1][0] == 720
    # (2) hold carry alive everywhere, health diagnostics sane
    assert all(r["horizons"][str(h)]["alive"] for h in (8, 16, 24)), r["horizons"]
    assert r["death_frame"] is None
    hc = r["horizons"]["24"]["hist_corr"]
    assert hc is not None and hc > 0.99, hc            # same crop, same frame
    assert abs(r["horizons"]["24"]["area_ratio"] - 1.0) < 1e-6

    # (3) drift: carry walks off after frame 300
    clock = [0]

    def make_drift(_r, b):
        def fn():
            clock[0] += 1
            return boxT if clock[0] * 5 <= 300 else (10.0, 10.0, 50.0, 50.0)
        return StubCarry(fn)

    clock[0] = 0
    r = run_cell("PLAIN", "stub", "the car", gt, frame_at, None, make_drift)
    hs = {h: r["horizons"][str(h)]["alive"] for h in (8, 16, 24)}
    assert hs == {8: True, 16: False, 24: False}, hs
    assert r["death_frame"] is not None and 300 < r["death_frame"] <= 480

    # (4) MAINT rescue: stub VLM returns the true box on every crop
    from grounding.contract import COORD_SCALE
    from grounding.roi import roi_window

    calls = []

    def make_submit(prior_getter):
        def submit(img, caption):
            h, w = img.shape[:2]
            calls.append((w, h, caption))
            norm = [prior_getter()[k] / (W if k % 2 == 0 else H) * COORD_SCALE
                    for k in range(4)]
            win = roi_window(norm, W, H, ROI_MARGIN, min_side=ROI_MIN_SIDE)
            s = max(w, h) / max(win[2] - win[0], win[3] - win[1])
            return ((boxT[0] - win[0]) * s, (boxT[1] - win[1]) * s,
                    (boxT[2] - win[0]) * s, (boxT[3] - win[1]) * s)
        return submit

    cur_prior = [boxT]
    drift_box = (10.0, 10.0, 50.0, 50.0)

    class DriftThenHold:
        """Drifts off after 300 until reseeded; a reseed pins it to the seed."""

        def __init__(self, seed, drifted):
            self.seed, self.drifted = tuple(seed), drifted

        def step(self, _f):
            clock[0] += 1
            if self.drifted and clock[0] * 5 > 300:
                cur_prior[0] = drift_box
                return None, drift_box
            cur_prior[0] = self.seed
            return None, self.seed

    seeds = []

    def make_maint(_r, b):
        seeds.append(tuple(round(v, 1) for v in b))
        # the f0 seed AND the pre-drift 165-reseed drift after frame 300;
        # the 330 reseed (fired while the carry sits on drift_box) holds ->
        # a genuine post-drift rescue is exercised.
        return DriftThenHold(b, drifted=len(seeds) <= 2)

    clock[0] = 0
    seeds.clear()
    calls.clear()
    r = run_cell("MAINT", "stub", "the car", gt, frame_at,
                 make_submit(lambda: cur_prior[0]), make_maint)
    assert [x["frame"] for x in r["reanchor"]] == [165, 330, 495, 660], r["reanchor"]
    assert all(x["accepted"] for x in r["reanchor"])
    assert all(c[2] == "the car" for c in calls)
    hs = {h: r["horizons"][str(h)]["alive"] for h in (8, 16, 24)}
    assert hs == {8: True, 16: True, 24: True}, hs     # rescued by 330 reseed
    assert len(seeds) == 5, seeds                      # f0 + 4 reseeds

    # reject path: carry left alone -> drift verdict reproduced
    clock[0] = 0
    seeds.clear()
    r = run_cell("MAINT", "stub", "the car", gt, frame_at,
                 lambda img, cap: None, make_maint)
    assert [x["accepted"] for x in r["reanchor"]] == [False] * 4
    assert len(seeds) == 1
    hs = {h: r["horizons"][str(h)]["alive"] for h in (8, 16, 24)}
    assert hs == {8: True, 16: False, 24: False}, hs

    # (5) GT-absent fallback, tie -> earlier
    gt2 = list(gt)
    for f in range(229, 270):
        gt2[f] = None
    sf = scoring_frames(gt2)
    assert sf[8] == 228, sf                            # car7-shaped span
    gt3 = list(gt)
    gt3[240] = None
    assert scoring_frames(gt3)[8] == 239               # tie -> earlier
    # (6) no valid GT within +-30 -> N/A
    gt4 = list(gt)
    for f in range(200, 281):
        gt4[f] = None
    assert scoring_frames(gt4)[8] is None
    clock[0] = 0
    r = run_cell("PLAIN", "stub", "the car", gt4, frame_at, None, make_hold)
    assert r["horizons"]["8"]["na"] and not r["horizons"]["16"]["na"]

    # (7) frame-health asserts
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        write_overlay(base, boxT, boxT, Path(tmp) / "ok.png", "ok")
        assert (Path(tmp) / "ok.png").exists()
        try:
            frame_health(np.zeros((H, W, 3), np.uint8))
            raise AssertionError("uniform frame passed health check")
        except AssertionError as e:
            assert "one colour" in str(e), e

    print("carry_horizon_p515 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="clips_p515.json path")
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--only", nargs="*", help="clip subset, e.g. car7 person10")
    ap.add_argument("--out", default="runs", help="runs dir (under this file's dir)")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return
    if not args.matrix or not args.arm:
        ap.error("need --matrix clips_p515.json and --arm (or --selfcheck)")
    run_matrix(args.arm, Path(args.matrix), HERE / args.out, args.only)


if __name__ == "__main__":
    main()
