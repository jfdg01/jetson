"""E21 coarse-to-fine acquire harness.

Fork of experiments/2026-07-04-prompt-scoped-acquire/replay_e20.py (provenance: that
file is the E20 source of truth; E20 forked E19, which forked the E18 replay). E21's
ONLY change vs E20 is who supplies the crop hint: E20 took the operator's spatial
phrase; E21 computes it automatically with a cheap low-resolution first VLM pass. The
coarse box is NOT trusted as a box -- it is quantised through E20's audited
`scope.hint_for` into a 3x3 cell vote, and the exact E20 scoped submit runs on that
cell (D1). Everything else -- the wall-clock loop, SAM2 carry, E14/E16 mask gate, the
Jetson submit path, and the E18 scorer -- is byte-for-byte E18/E19/E20 behaviour.

E18 measured the binder: the ~4.85 s blocking full-frame VLM acquire returns a box
correct for the frame the model SAW, but the target has moved ~146 frames by arrival,
so the lock lands stale (A 1/6 PASS). E20 cut acquire to 1.57-2.07 s with an operator
cell-crop (cell 3/6) but a WRONG operator hint makes the VLM hallucinate in the empty
crop and poisons the mask-gate template (PARTIAL [hint-fragile]). E21 asks: can a
coarse VLM pass replace the operator's hint -- same crop mechanism, prior produced
automatically -- and still beat staleness on the E20-flipped clips?

Two-pass acquire on the FIRST ACQUIRE attempt only:
  1. coarse pass -- downscale the submit frame client-side to max side COARSE_MAX_SIDE
     (cv2.resize INTER_AREA), ground the frozen caption; parse with the FULL frame dims
     so the box lands directly in full-frame coords (contract coords are relative).
  2. cell quantise -- hint = scope.hint_for(coarse_box, w0, h0); rect = crop_rect(hint).
  3. fine pass -- exact E20 scoped submit on rect, box mapped back.
Fallbacks (floor = E18): coarse None/invalid -> this attempt is a plain full-frame
submit; fine invalid -> next ACQUIRE attempt is full-frame; REGROUND always full-frame.

  --c2f          : enable the coarse-to-fine acquire (default OFF = byte-equivalent
                   E20/E18: full-frame acquire, or the E20 --scope-hint path if given).
  --coarse-side  : coarse-pass max side in px (default 320; 448 is the pre-registered
                   one-shot contingency, not a sweep -- see README D3).
  --scope-hint   : an E20 scope.REGIONS key; kept working for debugging only (the
                   matrix path never passes it -- E21's hint is computed).
  --mc none      : byte-equivalent to E18 leg A (full-frame carry init on submit frame).
  --mc buf       : E19 replay-buffer catch-up (dropped from the E21 matrix, D2).

    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/replay_e21.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-04-coarse-to-fine-acquire/replay_e21.py \
        --mc none --c2f --clip car10 --caption "the red car" --out runs/c2f_car10_r1
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
sys.path.insert(0, str(E20))       # import E20's audited scope.py (D1) -- do not copy
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

import scope                                                          # noqa: E402
from replay_source import WallClockVideo, load_uav123_gt, score_run  # noqa: E402

CARRY_HZ = 6.15   # D3: E1's measured on-Orin co-resident TensorRT carry rate
LOSS_S = 1.0      # empty-mask streak (s) before declaring loss -> REGROUND
APP_TAU = 12.0    # E14: mask-descriptor L-inf accept threshold for REGROUND
MAX_SIDE = 1024   # deployed full-frame acquire resolution (fine + fallback pass)
COARSE_MAX_SIDE = 320  # E21 D3: coarse-pass client-side downscale (~10x px cut)
BUF_K = 12        # buf catch-up stride: step carry every 12th frame (D-buf)

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


def downscale(frame_bgr: np.ndarray, max_side: int) -> np.ndarray:
    """Client-side downscale so the coarse pass grounds a low-res image (INTER_AREA).
    Never upscales (max_side >= max frame side -> return the frame unchanged)."""
    h, w = frame_bgr.shape[:2]
    s = max_side / max(w, h)
    if s >= 1.0:
        return frame_bgr
    return cv2.resize(frame_bgr, (max(round(w * s), 1), max(round(h * s), 1)),
                      interpolation=cv2.INTER_AREA)


# --- COPIED from experiments/.../phase3_sitl.py mask_descriptor (E14) ---------
def mask_descriptor(frame_bgr, mask):
    """Per-channel MEDIAN BGR over a SAM2 mask's pixels. None on <16 px mask."""
    if mask is None or int(mask.sum()) < 16:
        return None
    return np.median(frame_bgr[mask.astype(bool)].astype(np.float64), axis=0)


# --- COPIED from experiments/.../follow_demo.py vlm_acquire -------------------
def vlm_acquire(backend, frame_path: str, caption: str, w: int, h: int):
    """One VLM grounding pass over the image at frame_path -> pixel box | None,
    scaled to the (w, h) passed in. The contract coords are RELATIVE (COORD_SCALE),
    so passing the FULL-frame (w, h) for a downscaled coarse image lands the box in
    full-frame coords directly -- no map-back for the coarse pass."""
    from grounding.contract import COORD_SCALE, parse_bbox
    raw = backend.generate(frame_path, caption)
    b = parse_bbox(raw)
    if b is None:
        return None
    return (b[0] / COORD_SCALE * w, b[1] / COORD_SCALE * h,
            b[2] / COORD_SCALE * w, b[3] / COORD_SCALE * h)


class MaskGate:
    """E14/E16 mask-bound REGROUND identity gate (unchanged logic). Evaluated at
    the returned box location on the submit frame (E21 never shifts the box)."""

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
           scope_hint=None, c2f=False, coarse_submit=None, reground=True,
           cap_hz=CARRY_HZ, loss_s=LOSS_S, buf_k=BUF_K,
           now=time.monotonic, sleep=time.sleep):
    """Drive ACQUIRE -> TRACK -> (loss) -> REGROUND -> TRACK over the wall clock.

    With `c2f` set (and `coarse_submit` provided), the FIRST ACQUIRE attempt runs a
    coarse pass on the submit frame, quantises the coarse box to a 3x3 cell via
    scope.hint_for, and submits the E20 scoped crop for that cell (D1). A None/invalid
    coarse box falls through to a full-frame fine pass (fallback). With `scope_hint`
    set instead (E20 debug path), the first ACQUIRE uses that fixed cell. Any retry and
    every REGROUND submit pass rect=None (full frame), so the floor is exactly E18.

    Returns (events, trace, mc_log). Each ACQUIRE mc_log entry records `acquire_s` (the
    submit -> arrival backlog spanning BOTH passes), `coarse_s`, `coarse_box`,
    `coarse_hint`, `scoped`, and the `rect` used.
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
            coarse_box = coarse_hint = coarse_s = None
            if state == ACQUIRE and not first_acquire_done:
                h, w = submit_frame.shape[:2]
                if c2f and coarse_submit is not None:
                    first_acquire_done = True            # first acquire = coarse+fine (D4)
                    coarse_box = coarse_submit(submit_frame)   # blocks; downscaled full frame
                    coarse_s = round((int(video.t() * video.fps) - submit_i) / video.fps, 2)
                    if _valid(coarse_box, submit_frame.shape):
                        coarse_hint = scope.hint_for(coarse_box, w, h)
                        rect = scope.crop_rect(coarse_hint, w, h)
                    # else: coarse invalid -> rect stays None -> full-frame fine pass
                elif scope_hint is not None:
                    rect = scope.crop_rect(scope_hint, w, h)
                    first_acquire_done = True            # consumed on first attempt (D4)
            box = submit(submit_frame, rect)            # blocks; frames drop (fine/full pass)
            if not _valid(box, submit_frame.shape):
                continue                                # retry on the then-current frame

            live_i = int(video.t() * video.fps)         # where the wall clock is NOW
            init_frame, init_i, gate_frame = submit_frame, submit_i, submit_frame
            scoped = rect is not None
            acquire_s = round((live_i - submit_i) / video.fps, 2)
            cb = tuple(coarse_box) if coarse_box is not None else None

            if state == REGROUND and gate is not None and not gate.check(box, gate_frame):
                mc_log.append({"state": REGROUND, "submit_i": submit_i,
                               "arrival_i": live_i, "acquire_s": acquire_s,
                               "scoped": scoped, "rect": rect, "coarse_s": coarse_s,
                               "coarse_box": cb, "coarse_hint": coarse_hint,
                               "gate": "reject"})
                continue                                # E14 mask gate rejected

            carry = make_carry(_rgb(init_frame), box)
            if state == ACQUIRE and gate is not None:
                gate.bind(init_frame, carry.init_mask)
            events.append((video.t(), tuple(box)))
            entry = {"state": state, "submit_i": submit_i, "arrival_i": live_i,
                     "acquire_s": acquire_s, "scoped": scoped, "rect": rect,
                     "coarse_s": coarse_s, "coarse_box": cb, "coarse_hint": coarse_hint,
                     "gate": "accept"}
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


def run_matrix_clip(mc, seq_dir, anno, caption, out_dir, hint=None, c2f=False,
                    coarse_side=COARSE_MAX_SIDE, fps=30.0):
    """One full E21 run of one clip on the real stack. Writes results.json and
    overlay.mp4 into out_dir; returns the score_run dict. With `c2f`, the first
    ACQUIRE runs the coarse pass (downscale to `coarse_side`) -> cell -> E20 scoped
    fine pass. `hint` (a scope.REGIONS key) is the E20 debug path; None + c2f False
    -> full-frame (E18/E19-equivalent)."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    gt = load_uav123_gt(anno)
    video = WallClockVideo(seq_dir, fps=fps)
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(Path(seq_dir).glob("*.jpg"))

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    print("[E21] booting Jetson q8_0 server...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    h0, w0 = cv2.imread(str(paths[0])).shape[:2]

    def submit(frame_bgr, rect=None):
        """FINE / full pass. rect=None -> full frame (byte-identical to E20/E18).
        rect set -> crop the cell, ground in the CROP's coords, map back to full."""
        if rect is not None:
            x0, y0, x1, y1 = rect
            img = frame_bgr[y0:y1, x0:x1]
            cw, ch = x1 - x0, y1 - y0
        else:
            img, cw, ch = frame_bgr, w0, h0
        path = f"/dev/shm/e21_fine_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img)
        try:
            box = vlm_acquire(be, path, caption, cw, ch)
        finally:
            Path(path).unlink(missing_ok=True)
        return scope.map_back(box, rect) if rect is not None else box

    def coarse_submit(frame_bgr):
        """COARSE pass: downscale the full frame to `coarse_side`, ground the frozen
        caption, parse with FULL-frame dims -> box directly in full-frame coords."""
        img = downscale(frame_bgr, coarse_side)
        path = f"/dev/shm/e21_coarse_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img)
        try:
            box = vlm_acquire(be, path, caption, w0, h0)
        finally:
            Path(path).unlink(missing_ok=True)
        return box

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[idx]))

    gate = MaskGate(predictor)

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, trace, mc_log = replay(video, submit, make_carry, gate,
                                           mc=mc, frame_at=frame_at, scope_hint=hint,
                                           c2f=c2f, coarse_submit=coarse_submit,
                                           reground=True)
    finally:
        be.close()
    wall = time.time() - wall0

    s = score_run(events, gt, fps)
    # post-hoc coarse-hint truth: GT cell at the (first ACQUIRE) submit frame (D4)
    gt_hint = None
    acq0 = next((e for e in mc_log if e.get("state") == "ACQUIRE"), None)
    if acq0 is not None:
        si = acq0["submit_i"]
        if si < len(gt) and gt[si] is not None:
            gt_hint = scope.hint_for(gt[si], w0, h0)

    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "mc": mc, "clip": Path(seq_dir).name, "caption": caption, "hint": hint,
        "c2f": c2f, "coarse_side": coarse_side, "gt_hint": gt_hint,
        "fps": fps, "n_frames_gt": len(gt), "wall_s": round(wall, 1),
        "cap_hz": CARRY_HZ, "loss_s": LOSS_S, "app_tau": APP_TAU, "buf_k": BUF_K,
        "max_side": MAX_SIDE, "n_gate_reject": gate.n_reject,
        "n_events": len(events), "trace": trace, "mc_log": mc_log, "score": s,
        "events": [(round(t, 3), None if b is None else [round(v, 1) for v in b])
                   for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    render_overlay(seq_dir, events, gt, fps, out_dir / "overlay.mp4")
    acq = [(e.get("coarse_s"), e["acquire_s"]) for e in mc_log if e.get("state") == "ACQUIRE"]
    print(f"[E21 {mc} c2f={c2f} {Path(seq_dir).name}] "
          f"genuine={s['genuine_lock']} cov={s['coverage']} mean_iou={s['mean_iou']} "
          f"t_lock={s['t_lock']} coarse_hint={acq0['coarse_hint'] if acq0 else None} "
          f"gt_hint={gt_hint} (coarse_s,acquire_s)={acq} "
          f"gate_rej={result['n_gate_reject']} wall={wall:.0f}s", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """The E20 selfcheck (mc=none byte-equivalence, scoped crop+map-back, fallback,
    buf composition, MaskGate) UNCHANGED, plus three E21 coarse-to-fine checks:
    (a) a coarse box in a known cell -> the fine submit receives that cell's rect and
    the log records the coarse box/hint; (b) coarse None -> the same attempt falls
    through to a full-frame fine submit (rect None, scoped False); (c) the E20 checks
    still pass. Runs offline (no Jetson)."""
    import tempfile

    rng = np.random.default_rng(0)

    # -- downscale helper: max side honoured, aspect kept, never upscales -------
    d = downscale(np.zeros((720, 1280, 3), np.uint8), 320)
    assert d.shape[:2] == (180, 320), d.shape
    assert downscale(np.zeros((100, 200, 3), np.uint8), 320).shape[:2] == (100, 200)

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
    assert all(e["coarse_s"] is None for e in mc_log), "no c2f -> no coarse pass"
    assert all("acquire_s" in e for e in mc_log), "acquire_s recorded per submit"

    # -- (E20 a) scoped: first ACQUIRE gets the padded cell rect; box maps back -
    with tempfile.TemporaryDirectory() as tmp:
        W, H = 1280, 720
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
            return scope.map_back(crop_box, rect) if rect is not None else crop_box

        init_boxes = []

        class StubCarryS:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (2.0, 3.0, 12.0, 13.0))       # stay alive

        def make_carry_s(_r, box):
            init_boxes.append(tuple(round(v) for v in box))
            return StubCarryS()

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, trace_s, mc_s = replay(video, submit_s, make_carry_s, gate=None, mc="none",
                                  frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                                  scope_hint="center", reground=False, now=now, sleep=sleep)
    rect0 = scope.crop_rect("center", W, H)
    assert rects_seen[0] == rect0, rects_seen                # first submit got the crop
    assert mc_s[0]["scoped"] is True and mc_s[0]["rect"] == rect0, mc_s[0]
    assert init_boxes[0] == (2 + rect0[0], 3 + rect0[1],
                             12 + rect0[0], 13 + rect0[1]), init_boxes  # mapped back
    assert mc_s[0]["coarse_s"] is None, mc_s[0]              # scope_hint path is not c2f

    # -- (E20 b) fallback: invalid scoped result -> next attempt is full-frame --
    with tempfile.TemporaryDirectory() as tmp:
        W, H = 1280, 720
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
        _, trace_fb, mc_fb = replay(video, submit_fb, lambda r, b: StubCarryFb(),
                                    gate=None, mc="none",
                                    frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                                    scope_hint="center", reground=False, now=now, sleep=sleep)
    assert calls[0] == scope.crop_rect("center", W, H), calls   # first attempt scoped
    assert calls[1] is None, calls                              # fell back to full frame
    assert mc_fb[0]["scoped"] is False, mc_fb[0]                # accepted attempt unscoped

    # -- (E20 c) buf composition still terminates under a scope hint -----------
    with tempfile.TemporaryDirectory() as tmp:
        W, H = 1280, 720
        for i in range(900):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        def submit_b(_f, rect=None):
            clk[0] += 4.8                                   # ~144 frame backlog
            crop_box = (5.0, 5.0, 25.0, 25.0)
            return scope.map_back(crop_box, rect) if rect is not None else crop_box

        class StubCarryB:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (5.0, 5.0, 100.0, 100.0))     # stays alive

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, trace_b, mc_b = replay(video, submit_b, lambda r, b: StubCarryB(),
                                  gate=None, mc="buf",
                                  frame_at=lambda i: np.full((H, W, 3), i % 256, np.uint8),
                                  scope_hint="center", reground=False, now=now, sleep=sleep)
    assert trace_b[0] == TRACK, trace_b
    assert mc_b[0]["scoped"] is True, mc_b[0]                # buf leg is scoped too
    assert mc_b[0]["catchup_frames"] > 0, mc_b[0]
    assert 0 <= mc_b[0]["final_gap"] < BUF_K, mc_b[0]        # caught up to live

    # -- (E21 a) c2f: coarse box in a known cell -> fine submit gets that rect --
    with tempfile.TemporaryDirectory() as tmp:
        W, H = 1280, 720
        for i in range(300):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731
        coarse_ret = (600.0, 330.0, 680.0, 390.0)           # centroid ~ (640,360) -> center

        def coarse_sub(_f):
            clk[0] += 0.9
            return coarse_ret

        rects_c = []

        def submit_c(_f, rect=None):
            clk[0] += 1.6
            rects_c.append(rect)
            crop_box = (2.0, 3.0, 12.0, 13.0)
            return scope.map_back(crop_box, rect) if rect is not None else crop_box

        class StubCarryC:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (2.0, 3.0, 12.0, 13.0))

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, _, mc_c = replay(video, submit_c, lambda r, b: StubCarryC(), gate=None,
                            mc="none", frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                            c2f=True, coarse_submit=coarse_sub, reground=False,
                            now=now, sleep=sleep)
    want_hint = scope.hint_for(coarse_ret, W, H)
    assert want_hint == "center", want_hint
    want_rect = scope.crop_rect(want_hint, W, H)
    assert rects_c[0] == want_rect, (rects_c, want_rect)     # fine submit got the cell
    assert mc_c[0]["scoped"] is True, mc_c[0]
    assert mc_c[0]["coarse_hint"] == want_hint, mc_c[0]
    assert tuple(mc_c[0]["coarse_box"]) == coarse_ret, mc_c[0]
    assert mc_c[0]["coarse_s"] is not None and mc_c[0]["coarse_s"] > 0, mc_c[0]

    # -- (E21 b) c2f fallback: coarse None -> full-frame fine submit (rect None) -
    with tempfile.TemporaryDirectory() as tmp:
        W, H = 1280, 720
        for i in range(300):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full((H, W, 3), i % 256, np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                                # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        def coarse_none(_f):
            clk[0] += 0.9
            return None                                     # coarse pass fails

        rects_fb2 = []

        def submit_fb2(_f, rect=None):
            clk[0] += 1.6
            rects_fb2.append(rect)
            return (10.0, 10.0, 40.0, 40.0)                 # full-frame fine pass succeeds

        class StubCarryFb2:
            init_mask = np.ones((H, W), dtype=bool)

            def step(self, _f):
                return (None, (10.0, 10.0, 40.0, 40.0))

        video = WallClockVideo(tmp, fps=30.0, now=now)
        _, _, mc_fb2 = replay(video, submit_fb2, lambda r, b: StubCarryFb2(), gate=None,
                              mc="none", frame_at=lambda i: np.zeros((H, W, 3), np.uint8),
                              c2f=True, coarse_submit=coarse_none, reground=False,
                              now=now, sleep=sleep)
    assert rects_fb2[0] is None, rects_fb2                   # coarse None -> full-frame fine
    assert mc_fb2[0]["scoped"] is False, mc_fb2[0]
    assert mc_fb2[0]["coarse_box"] is None, mc_fb2[0]        # invalid coarse box not logged
    assert mc_fb2[0]["coarse_hint"] is None, mc_fb2[0]
    assert mc_fb2[0]["coarse_s"] is not None, mc_fb2[0]      # coarse pass still timed

    # -- MaskGate fail-open + L-inf accept logic (unchanged from E18) ---------
    g = MaskGate(predictor=None, app_tau=12.0)
    assert g.check((0, 0, 10, 10), np.zeros((40, 40, 3), np.uint8)) is True
    g.template = np.array([200.0, 200.0, 200.0])
    assert float(np.abs(np.array([205.0, 198.0, 203.0]) - g.template).max()) <= 12.0
    assert float(np.abs(np.array([180.0, 200.0, 200.0]) - g.template).max()) > 12.0
    print("replay_e21 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--mc", choices=["none", "buf"])
    ap.add_argument("--c2f", action="store_true",
                    help="enable coarse-to-fine acquire (default off = E20/E18 path)")
    ap.add_argument("--coarse-side", type=int, default=COARSE_MAX_SIDE,
                    help=f"coarse-pass max side px (default {COARSE_MAX_SIDE})")
    ap.add_argument("--scope-hint", help="a scope.REGIONS key (E20 debug path); the "
                                         "c2f matrix never sets this")
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
    if args.scope_hint is not None and args.scope_hint not in scope.REGIONS:
        ap.error(f"--scope-hint must be one of {sorted(scope.REGIONS)}")
    data = E18 / "data" / "UAV123"
    seq_dir = args.seq_dir or (data / "data_seq" / "UAV123" / args.clip)
    anno = args.anno or (data / "anno" / "UAV123" / f"{args.clip}.txt")
    out = Path(args.out) if args.out else (HERE / "runs" / f"{args.mc}_{args.clip}")
    run_matrix_clip(args.mc, seq_dir, anno, args.caption, out,
                    hint=args.scope_hint, c2f=args.c2f, coarse_side=args.coarse_side,
                    fps=args.fps)


if __name__ == "__main__":
    main()
