"""E23 tolerant-cell acquire harness.

Fork of experiments/2026-07-04-prompt-scoped-acquire/replay_e20.py (provenance: that
file is the E20 source of truth; E20 forked E19, which forked the E18 replay). E23's
ONLY change vs E20 is the acquire crop: E20 cropped the operator's EXACT third-cell
with a fixed 0.10 pad; E23 crops a single half-width HW cell named by a FUZZED operator
phrase (`cells.worst_hint`, the most edge-ward plausible term at tau). At HW=0.2667 the
crop is byte-identical to E20; a bigger HW makes overlapping cells that absorb the fuzz.
Everything else -- the wall-clock loop, SAM2 carry, E14/E16 mask gate, the Jetson submit
path, and the E18 scorer -- is byte-for-byte E18/E19/E20 behaviour so campaigns compare.

E18 measured the binder: the ~4.85 s blocking full-frame acquire lands STALE (A 1/6).
E20 cut acquire to ~1.85 s with an operator third-cell crop (cell 3/6) but the third
grid is too cagey -- a casual operator naming a target one cell over escapes the crop
(Phase-0: E20 HW contains only 2/6 worst-case fuzzed phrasings). E23 asks whether a
bigger overlapping cell (HW*) absorbs that fuzz WITHOUT reintroducing E18 staleness.

  --hw   : cell half-width (default 0.2667 = E20-equivalent; matrix runs HW*).
  --tau  : fuzzy-operator band width (default 0.10; the worst plausible phrasing).
  --hint : the FUZZED phrase to crop (a cells grid-cell name). The matrix computes it
           as cells.worst_hint(frame-0 GT, tau); left explicit for reproducibility.
  --true-hint : the honest cell (cells.hint_for) -- logged, not used for the crop.
  --mc none : byte-equivalent to E18 leg A (full-frame carry init on the submit frame).

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/replay_e23.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/replay_e23.py \
        --mc none --hw 0.38 --hint "middle left" --true-hint "bottom center" \
        --clip car9 --caption "the white car" --out runs/tol_car9_r1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
E20 = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
sys.path.insert(0, str(E20))     # cells.py imports scope.py from here (do not copy)
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

import cells                                                           # noqa: E402
import scope                                                          # noqa: E402
from replay_source import WallClockVideo, load_uav123_gt, score_run  # noqa: E402

CARRY_HZ = 6.15   # D3: E1's measured on-Orin co-resident TensorRT carry rate
LOSS_S = 1.0      # empty-mask streak (s) before declaring loss -> REGROUND
APP_TAU = 12.0    # E14: mask-descriptor L-inf accept threshold for REGROUND
MAX_SIDE = 1024   # deployed full-frame acquire resolution
BUF_K = 12        # buf catch-up stride: step carry every 12th frame (D-buf)
HW_E20 = cells.HW_E20  # 0.2667 -- E20-equivalent half-width

ACQUIRE, TRACK, REGROUND = "ACQUIRE", "TRACK", "REGROUND"


def _rgb(bgr: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(bgr[:, :, ::-1])


def _valid(box, shape) -> bool:
    """A box is usable iff it is >=2 px on each side and overlaps the frame."""
    if box is None:
        return False
    x0, y0, x1, y1 = box
    h, w = shape[:2]
    return (x1 - x0 >= 2 and y1 - y0 >= 2
            and x1 > 0 and y1 > 0 and x0 < w and y0 < h)


# --- COPIED from experiments/.../phase3_sitl.py mask_descriptor (E14) ---------
def mask_descriptor(frame_bgr, mask):
    """Per-channel MEDIAN BGR over a SAM2 mask's pixels. None on <16 px mask."""
    if mask is None or int(mask.sum()) < 16:
        return None
    return np.median(frame_bgr[mask.astype(bool)].astype(np.float64), axis=0)


# --- COPIED from experiments/.../follow_demo.py vlm_acquire -------------------
def vlm_acquire(backend, frame_path: str, caption: str, w: int, h: int):
    """One VLM grounding pass over the image at frame_path -> pixel box | None,
    scaled to the (w, h) of THAT image (full frame or crop)."""
    from grounding.contract import COORD_SCALE, parse_bbox
    raw = backend.generate(frame_path, caption)
    b = parse_bbox(raw)
    if b is None:
        return None
    return (b[0] / COORD_SCALE * w, b[1] / COORD_SCALE * h,
            b[2] / COORD_SCALE * w, b[3] / COORD_SCALE * h)


class MaskGate:
    """E14/E16 mask-bound REGROUND identity gate (unchanged logic). Evaluated at
    the returned box location on the submit frame (E23 never shifts the box)."""

    def __init__(self, predictor, app_tau: float = APP_TAU):
        self.predictor, self.app_tau = predictor, app_tau
        self.template = None
        self.n_reject = 0

    def bind(self, frame_bgr, init_mask) -> None:
        self.template = mask_descriptor(frame_bgr, init_mask)

    def check(self, box, frame_bgr) -> bool:
        if self.template is None:
            return True
        from stream_carry import StreamCarry
        sc = StreamCarry(self.predictor, _rgb(frame_bgr), box)
        d = mask_descriptor(frame_bgr, sc.init_mask)
        del sc
        ok = d is not None and float(np.abs(d - self.template).max()) <= self.app_tau
        if not ok:
            self.n_reject += 1
        return ok


def replay(video, submit, make_carry, gate=None, *, mc="none", frame_at=None,
           scope_hint=None, hw=HW_E20, true_hint=None, reground=True, cap_hz=CARRY_HZ,
           loss_s=LOSS_S, buf_k=BUF_K, now=time.monotonic, sleep=time.sleep):
    """Drive ACQUIRE -> TRACK -> (loss) -> REGROUND -> TRACK over the wall clock.

    With `scope_hint` set, the FIRST ACQUIRE attempt submits the HW-cell named by the
    (fuzzed) hint: `rect = cells.crop_rect(scope_hint, w, h, hw)` (D4). At hw=0.2667 the
    rect is byte-identical to E20's padded cell; a larger hw is E23's tolerant cell.
    Any retry and every REGROUND submit pass rect=None (full frame), so the floor is
    exactly E18 behaviour.

    Returns (events, trace, mc_log). Each ACQUIRE mc_log entry records the submit ->
    arrival backlog as `acquire_s`, whether the submit was `scoped`, the `rect`, the
    `hw`, the `fuzzed_hint` actually cropped, and the honest `true_hint`.
    """
    events, trace, mc_log = [], [], []
    video.start()
    carry, state, empty = None, ACQUIRE, 0
    first_acquire_done = False

    while (grab := video.latest()) is not None:
        i, frame = grab
        if state in (ACQUIRE, REGROUND):
            submit_i, submit_frame = i, frame           # captured before blocking
            rect = None
            if state == ACQUIRE and scope_hint is not None and not first_acquire_done:
                h, w = submit_frame.shape[:2]
                rect = cells.crop_rect(scope_hint, w, h, hw)
                first_acquire_done = True                # consumed on first attempt (D4)
            box = submit(submit_frame, rect)            # blocks; frames drop
            if not _valid(box, submit_frame.shape):
                continue                                # retry on the then-current frame

            live_i = int(video.t() * video.fps)         # where the wall clock is NOW
            init_frame, init_i, gate_frame = submit_frame, submit_i, submit_frame
            scoped = rect is not None
            acquire_s = round((live_i - submit_i) / video.fps, 2)

            if state == REGROUND and gate is not None and not gate.check(box, gate_frame):
                mc_log.append({"state": REGROUND, "submit_i": submit_i,
                               "arrival_i": live_i, "acquire_s": acquire_s,
                               "scoped": scoped, "rect": rect, "hw": hw,
                               "fuzzed_hint": scope_hint if scoped else None,
                               "true_hint": true_hint, "gate": "reject"})
                continue                                # E14 mask gate rejected

            carry = make_carry(_rgb(init_frame), box)
            if state == ACQUIRE and gate is not None:
                gate.bind(init_frame, carry.init_mask)
            events.append((video.t(), tuple(box)))
            entry = {"state": state, "submit_i": submit_i, "arrival_i": live_i,
                     "acquire_s": acquire_s, "scoped": scoped, "rect": rect, "hw": hw,
                     "fuzzed_hint": scope_hint if scoped else None,
                     "true_hint": true_hint, "gate": "accept"}
            empty, state = 0, TRACK
            trace.append(TRACK)

            if mc == "buf":                             # catch-up from submit frame
                last, n_catch = init_i, 0
                w0 = now()
                while True:
                    live_i = int(video.t() * video.fps)
                    nxt = last + buf_k
                    if nxt >= live_i or nxt >= video.n:
                        break
                    t0 = now()
                    _, b = carry.step(_rgb(frame_at(nxt)))
                    events.append((video.t(), tuple(b) if _valid(b, submit_frame.shape) else None))
                    last, n_catch = nxt, n_catch + 1
                    dt = 1.0 / cap_hz - (now() - t0)
                    if dt > 0:
                        sleep(dt)
                entry.update({"backlog0": live_i - submit_i, "catchup_frames": n_catch,
                              "catchup_s": round(now() - w0, 2),
                              "final_gap": int(video.t() * video.fps) - last})
            mc_log.append(entry)
        else:                                           # TRACK (rate-capped)
            t0 = now()
            _, box = carry.step(_rgb(frame))
            if not _valid(box, frame.shape):
                empty += 1
                if reground and empty >= loss_s * cap_hz:
                    events.append((video.t(), None))
                    empty, state = 0, REGROUND
                    trace.append(REGROUND)
            else:
                empty = 0
                events.append((video.t(), tuple(box)))
            dt = 1.0 / cap_hz - (now() - t0)
            if dt > 0:
                sleep(dt)
    return events, trace, mc_log


def render_overlay(seq_dir, events, gt, fps, out_path) -> None:
    """Post-hoc native-fps overlay: held box (green) + GT box (red) per frame."""
    paths = sorted(Path(seq_dir).glob("*.jpg"))
    ev = sorted(events, key=lambda e: e[0])
    h, w = cv2.imread(str(paths[0])).shape[:2]
    vw = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    j, held = 0, None
    for i, p in enumerate(paths):
        t = i / fps
        while j < len(ev) and ev[j][0] <= t:
            held = ev[j][1]
            j += 1
        frame = cv2.imread(str(p))
        if i < len(gt) and gt[i] is not None:
            g = [int(v) for v in gt[i]]
            cv2.rectangle(frame, (g[0], g[1]), (g[2], g[3]), (0, 0, 220), 2)
        if held is not None:
            b = [int(v) for v in held]
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (40, 200, 80), 2)
        lab = "LOST" if held is None else "TRACK"
        cv2.putText(frame, f"{lab} f={i} (green=held red=GT)", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)
        vw.write(frame)
    vw.release()


def run_matrix_clip(mc, seq_dir, anno, caption, out_dir, hw=HW_E20, tau=0.10, fps=30.0):
    """One full E23 run of one clip on the real stack. The FUZZED (worst-case) acquire
    hint is computed from the frame-0 GT: fuzzed_hint = cells.worst_hint(gt0, w, h, tau),
    and the first ACQUIRE crops cells.crop_rect(fuzzed_hint, w, h, hw). Writes
    results.json + overlay.mp4 into out_dir; returns the score_run dict."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    gt = load_uav123_gt(anno)
    video = WallClockVideo(seq_dir, fps=fps)
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(Path(seq_dir).glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]

    # fuzzy operator: honest cell + the worst-case plausible phrasing at t=0 (D2)
    gt0 = gt[0]
    true_hint = cells.hint_for(gt0, w0, h0)
    fuzzed_hint = cells.worst_hint(gt0, w0, h0, tau)

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    print("[E23] booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit(frame_bgr, rect=None):
        """rect=None -> full frame (byte-identical to E18/E20). rect set -> crop the
        cell, ground in the CROP's coords, then map the box back to full-frame."""
        if rect is not None:
            x0, y0, x1, y1 = rect
            img = frame_bgr[y0:y1, x0:x1]
            cw, ch = x1 - x0, y1 - y0
        else:
            img, cw, ch = frame_bgr, w0, h0
        path = f"/dev/shm/e23_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img)
        try:
            box = vlm_acquire(be, path, caption, cw, ch)
        finally:
            Path(path).unlink(missing_ok=True)
        return cells.map_back(box, rect) if rect is not None else box

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[idx]))

    gate = MaskGate(predictor)

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, trace, mc_log = replay(video, submit, make_carry, gate,
                                           mc=mc, frame_at=frame_at,
                                           scope_hint=fuzzed_hint, hw=hw,
                                           true_hint=true_hint, reground=True)
    finally:
        be.close()
    wall = time.time() - wall0

    s = score_run(events, gt, fps)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "mc": mc, "clip": Path(seq_dir).name, "caption": caption,
        "hw": hw, "tau": tau, "true_hint": true_hint, "fuzzed_hint": fuzzed_hint,
        "fps": fps, "n_frames_gt": len(gt), "wall_s": round(wall, 1),
        "cap_hz": CARRY_HZ, "loss_s": LOSS_S, "app_tau": APP_TAU, "buf_k": BUF_K,
        "max_side": MAX_SIDE, "n_gate_reject": gate.n_reject,
        "n_events": len(events), "trace": trace, "mc_log": mc_log, "score": s,
        "events": [(round(t, 3), None if b is None else [round(v, 1) for v in b])
                   for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    render_overlay(seq_dir, events, gt, fps, out_dir / "overlay.mp4")
    acq = [e["acquire_s"] for e in mc_log if e.get("state") == "ACQUIRE"]
    print(f"[E23 {mc} hw={hw} {Path(seq_dir).name}] true={true_hint!r} "
          f"fuzzed={fuzzed_hint!r} genuine={s['genuine_lock']} cov={s['coverage']} "
          f"mean_iou={s['mean_iou']} t_lock={s['t_lock']} acquire_s={acq} "
          f"gate_rej={result['n_gate_reject']} wall={wall:.0f}s", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """The E20 state-machine checks (mc=none byte-equivalence, scoped crop+map-back,
    fallback, buf composition, MaskGate) plus two E23 checks: (a) at hw=0.2667 the
    scoped rect is byte-identical to E20's scope.crop_rect (superset); (b) the fuzzed
    path picks cells.worst_hint and a bigger hw enlarges the rect. Runs offline."""
    import tempfile

    # (E23 a+b) hw=0.2667 rect == E20's cell for all 9 grid cells; worst_hint + hw ----
    W, H = 1280, 720
    for hint in scope.REGIONS:
        if "half" in hint:
            continue
        assert cells.crop_rect(hint, W, H, HW_E20) == scope.crop_rect(hint, W, H), hint
    b14 = cells.gt0_box("car14")
    assert cells.worst_hint(b14, W, H, 0.10) == "top left"
    r_small = cells.crop_rect("top left", W, H, HW_E20)
    r_big = cells.crop_rect("top left", W, H, 0.38)
    assert (r_big[2] - r_big[0]) * (r_big[3] - r_big[1]) > \
           (r_small[2] - r_small[0]) * (r_small[3] - r_small[1])   # bigger hw = bigger crop

    # -- mc=none: state machine walks ACQUIRE -> TRACK -> REGROUND -> TRACK ----
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(900):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg",
                        np.full((40, 40, 3), i % 256, dtype=np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        def submit(_f, rect=None):
            clk[0] += 4.8
            return (5.0, 5.0, 25.0, 25.0)

        lives = {"n": 0}

        class StubCarry:
            init_mask = np.ones((40, 40), dtype=bool)

            def step(self, _f):
                lives["n"] -= 1
                return (None, (5.0, 5.0, 25.0, 25.0) if lives["n"] >= 0 else None)

        def make_carry(_r, _b):
            lives["n"] = 4
            return StubCarry()

        video = WallClockVideo(tmp, fps=30.0, now=now)
        events, trace, mc_log = replay(video, submit, make_carry, gate=None, mc="none",
                                       frame_at=lambda i: np.zeros((40, 40, 3), np.uint8),
                                       reground=True, now=now, sleep=sleep)
    assert trace[0] == TRACK, trace
    assert REGROUND in trace and trace.index(REGROUND) < len(trace) - 1, trace
    assert trace[trace.index(REGROUND) + 1] == TRACK, trace
    assert any(b is None for _, b in events), "a loss should have been recorded"
    assert all(e["scoped"] is False for e in mc_log), "unscoped run must not scope"
    assert all("acquire_s" in e for e in mc_log), "acquire_s recorded per submit"
    assert all(e["hw"] == HW_E20 for e in mc_log), "hw recorded per submit"

    # -- (a) scoped: first ACQUIRE gets the HW cell rect; box maps back --------
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(300):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731
        rects_seen = []

        def submit_s(_f, rect=None):
            clk[0] += 1.5
            rects_seen.append(rect)
            crop_box = (2.0, 3.0, 12.0, 13.0)               # grounded in crop coords
            return cells.map_back(crop_box, rect) if rect is not None else crop_box

        init_boxes = []

        class StubCarryS:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (2.0, 3.0, 12.0, 13.0))

        def make_carry_s(_r, box):
            init_boxes.append(tuple(round(v) for v in box))
            return StubCarryS()

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, _, mc_s = replay(video, submit_s, make_carry_s, gate=None, mc="none",
                            frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                            scope_hint="top left", hw=0.38, true_hint="center",
                            reground=False, now=now, sleep=sleep)
    rect0 = cells.crop_rect("top left", W, H, 0.38)
    assert rects_seen[0] == rect0, rects_seen                # first submit got the HW crop
    assert mc_s[0]["scoped"] is True and mc_s[0]["rect"] == rect0, mc_s[0]
    assert mc_s[0]["hw"] == 0.38 and mc_s[0]["fuzzed_hint"] == "top left", mc_s[0]
    assert mc_s[0]["true_hint"] == "center", mc_s[0]
    assert init_boxes[0] == (2 + rect0[0], 3 + rect0[1],
                             12 + rect0[0], 13 + rect0[1]), init_boxes  # mapped back

    # -- (b) fallback: invalid scoped result -> next attempt is full-frame -----
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(300):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731
        calls = []

        def submit_fb(_f, rect=None):
            clk[0] += 1.5
            calls.append(rect)
            if len(calls) == 1:
                return None                                 # first scoped attempt fails
            return (10.0, 10.0, 40.0, 40.0)                 # second full-frame attempt

        class StubCarryFb:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (10.0, 10.0, 40.0, 40.0))

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, _, mc_fb = replay(video, submit_fb, lambda r, b: StubCarryFb(),
                             gate=None, mc="none",
                             frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                             scope_hint="top left", hw=0.38, reground=False,
                             now=now, sleep=sleep)
    assert calls[0] == cells.crop_rect("top left", W, H, 0.38), calls  # first scoped
    assert calls[1] is None, calls                              # fell back to full frame
    assert mc_fb[0]["scoped"] is False, mc_fb[0]                # accepted attempt unscoped

    # -- (c) buf composition still terminates under a scope hint ---------------
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(900):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        def submit_b(_f, rect=None):
            clk[0] += 4.8                                   # ~144 frame backlog
            crop_box = (5.0, 5.0, 25.0, 25.0)
            return cells.map_back(crop_box, rect) if rect is not None else crop_box

        class StubCarryB:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (5.0, 5.0, 100.0, 100.0))

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, trace_b, mc_b = replay(video, submit_b, lambda r, b: StubCarryB(),
                                  gate=None, mc="buf",
                                  frame_at=lambda i: np.full((H, W, 3), i % 256, np.uint8),
                                  scope_hint="center", hw=0.38, reground=False,
                                  now=now, sleep=sleep)
    assert trace_b[0] == TRACK, trace_b
    assert mc_b[0]["scoped"] is True, mc_b[0]
    assert mc_b[0]["catchup_frames"] > 0, mc_b[0]
    assert 0 <= mc_b[0]["final_gap"] < BUF_K, mc_b[0]

    # -- MaskGate fail-open + L-inf accept logic (unchanged from E18) ---------
    g = MaskGate(predictor=None, app_tau=12.0)
    assert g.check((0, 0, 10, 10), np.zeros((40, 40, 3), np.uint8)) is True
    g.template = np.array([200.0, 200.0, 200.0])
    assert float(np.abs(np.array([205.0, 198.0, 203.0]) - g.template).max()) <= 12.0
    assert float(np.abs(np.array([180.0, 200.0, 200.0]) - g.template).max()) > 12.0
    print("replay_e23 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--mc", choices=["none", "buf"])
    ap.add_argument("--hw", type=float, default=HW_E20,
                    help=f"cell half-width (default {HW_E20:.4f} = E20-equivalent)")
    ap.add_argument("--tau", type=float, default=0.10, help="fuzzy-operator band width")
    ap.add_argument("--fuzz", type=float, dest="tau", help="alias for --tau")
    ap.add_argument("--hint", help="explicit fuzzed cell to crop (default: worst_hint "
                                   "of frame-0 GT); a cells grid-cell name")
    ap.add_argument("--true-hint", help="honest cell for logging (default: hint_for GT)")
    ap.add_argument("--clip", help="sequence name under E18 data/ (dir of jpgs)")
    ap.add_argument("--seq-dir", help="explicit frames dir (overrides --clip)")
    ap.add_argument("--anno", help="explicit anno .txt (overrides default)")
    ap.add_argument("--caption", default="the car")
    ap.add_argument("--out", help="output run dir")
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    if not args.mc or not (args.clip or args.seq_dir):
        ap.error("need --mc and (--clip or --seq-dir)")
    data = E18 / "data" / "UAV123"
    seq_dir = args.seq_dir or (data / "data_seq" / "UAV123" / args.clip)
    anno = args.anno or (data / "anno" / "UAV123" / f"{args.clip}.txt")
    out = Path(args.out) if args.out else (HERE / "runs" / f"tol_{args.clip}")
    run_matrix_clip(args.mc, seq_dir, anno, args.caption, out,
                    hw=args.hw, tau=args.tau, fps=args.fps)


if __name__ == "__main__":
    main()
