"""E18 real-video replay harness: NL acquire -> SAM2 carry -> mask-gated REGROUND
on UAV123 aerial car footage, replayed at wall-clock rate (frames drop during
inference), scored against dataset GT.

Single-threaded on purpose (D4 harness spec): a blocking VLM submit is CORRECT
here -- the frames the pipeline misses while the model thinks are GONE, exactly
like a live camera. Threads/queues would hide the cadence cost this experiment
exists to measure. The carry tier is rate-capped to CARRY_HZ = 6.15 (E1's
measured co-resident TensorRT number on the Orin, D3); the anchor tier is real
Jetson wall time via JetsonBackend (self-boot per run, as in E16).

Reused, not rewritten: WallClockVideo / load_uav123_gt / score_run / iou from
replay_source.py (this dir); StreamCarry from the temporal-acquire-carry
campaign. mask_descriptor and vlm_acquire are COPIED (~15 lines each, with
provenance) rather than imported: phase3_sitl / follow_demo drag SITL + dataset
imports that do not exist on the replay path (D4). PermanenceController is NOT
imported (world-coupled).

    .venv-ft/bin/python experiments/2026-07-03-real-video-replay/replay_e18.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-03-real-video-replay/replay_e18.py \
        --leg A --clip car1_s --caption "the white car"
    .venv-ft/bin/python experiments/2026-07-03-real-video-replay/replay_e18.py \
        --leg B --clip car1_s          # oracle: init from GT frame-0, no VLM
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
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

from replay_source import WallClockVideo, load_uav123_gt, score_run  # noqa: E402

CARRY_HZ = 6.15   # D3: E1's measured on-Orin co-resident TensorRT carry rate
LOSS_S = 1.0      # D4: empty-mask streak (s) before declaring loss -> REGROUND
APP_TAU = 12.0    # D4/E14: mask-descriptor L-inf accept threshold for REGROUND
MAX_SIDE = 1024   # deployed full-frame acquire resolution (phase3_sitl / demo)

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
# Verbatim (docstring trimmed); phase3_sitl imports follow_demo+sitl_cam which
# drag SITL/dataset deps absent on the replay path, so we copy the 3 lines.
def mask_descriptor(frame_bgr, mask):
    """Per-channel MEDIAN BGR over a SAM2 mask's pixels (a majority vote over the
    instance SAM2 actually latched). None on a degenerate (<16 px) mask."""
    if mask is None or int(mask.sum()) < 16:
        return None
    return np.median(frame_bgr[mask.astype(bool)].astype(np.float64), axis=0)


# --- COPIED from experiments/.../follow_demo.py vlm_acquire -------------------
def vlm_acquire(backend, frame_path: str, caption: str, w: int, h: int):
    """One full-frame VLM grounding pass -> pixel box | None."""
    from grounding.contract import COORD_SCALE, parse_bbox
    raw = backend.generate(frame_path, caption)
    b = parse_bbox(raw)
    if b is None:
        return None
    return (b[0] / COORD_SCALE * w, b[1] / COORD_SCALE * h,
            b[2] / COORD_SCALE * w, b[3] / COORD_SCALE * h)


class MaskGate:
    """E14/E16 mask-bound REGROUND identity gate, transferred to real footage.

    The template is the median body-colour of the frame-0 mask the ACQUIRE carry
    latched (bind, at NL grounding). check() runs the exact StreamCarry init the
    accept path would run on the candidate REGROUND box, takes its frame-0 mask
    descriptor, and accepts iff it is within APP_TAU (L-inf) of the template.
    Fail-open with no template (no bound identity -> no claim to enforce).
    """

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


def replay(video, submit, make_carry, gate=None, *, oracle=None, reground=True,
           cap_hz=CARRY_HZ, loss_s=LOSS_S, now=time.monotonic, sleep=time.sleep):
    """Drive ACQUIRE -> TRACK -> (loss) -> REGROUND -> TRACK over the wall clock.

    submit(frame_bgr) -> box|None (blocks ~4.8 s on the real Jetson path).
    make_carry(frame_rgb, box) -> obj with .step(frame_rgb)->(mask, box) and
    .init_mask. gate: MaskGate|None (A-full only). oracle: GT frame-0 box for
    leg B (init carry from it, VLM skipped, REGROUND disabled). Returns
    (events, trace) where trace is the state sequence (selfcheck asserts it).
    """
    events, trace = [], []
    video.start()
    carry, state, empty, loss_recorded = None, ACQUIRE, 0, False

    if oracle is not None:                       # leg B: oracle-init, no VLM
        grab = video.latest()
        if grab is None:
            return events, trace
        _, frame = grab
        carry = make_carry(_rgb(frame), oracle)
        events.append((video.t(), tuple(oracle)))
        state = TRACK
        trace.append(TRACK)

    while (grab := video.latest()) is not None:
        _, frame = grab
        if state in (ACQUIRE, REGROUND):
            box = submit(frame)
            if not _valid(box, frame.shape):
                continue                          # retry on the then-current frame
            if state == REGROUND and gate is not None and not gate.check(box, frame):
                continue                          # E14 mask gate rejected the proposal
            carry = make_carry(_rgb(frame), box)
            if state == ACQUIRE and gate is not None:
                gate.bind(frame, carry.init_mask)
            events.append((video.t(), tuple(box)))
            empty, state = 0, TRACK
            trace.append(TRACK)
        else:                                     # TRACK (rate-capped)
            t0 = now()
            _, box = carry.step(_rgb(frame))
            if not _valid(box, frame.shape):
                empty += 1
                if reground and empty >= loss_s * cap_hz:
                    events.append((video.t(), None))
                    empty, state = 0, REGROUND
                    trace.append(REGROUND)
                elif not reground and not loss_recorded:
                    events.append((video.t(), None))   # leg B: record once, keep stepping
                    loss_recorded = True
            else:
                empty, loss_recorded = 0, False
                events.append((video.t(), tuple(box)))
            dt = 1.0 / cap_hz - (now() - t0)
            if dt > 0:
                sleep(dt)
    return events, trace


def render_overlay(seq_dir, events, gt, fps, out_path) -> None:
    """Post-hoc native-fps overlay: held box (green) + GT box (red) per frame.
    Held box at frame i = last event with t <= i/fps (the scorer's own rule)."""
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


def run_matrix_clip(leg, seq_dir, anno, caption, out_dir, fps=30.0):
    """One full run (A or B) of one clip on the real stack. Writes results.json
    and overlay.mp4 into out_dir; returns the score_run dict."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    gt = load_uav123_gt(anno)
    video = WallClockVideo(seq_dir, fps=fps)
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)

    be = None
    if leg == "A":
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        print("[E18] booting Jetson q8_0 server...", flush=True)
        be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                           f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                           ssh_host="jetson", max_side=MAX_SIDE)

    h0, w0 = cv2.imread(sorted(Path(seq_dir).glob("*.jpg"))[0]).shape[:2]

    def submit(frame_bgr):
        path = f"/dev/shm/e18_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        try:
            return vlm_acquire(be, path, caption, w0, h0)
        finally:
            Path(path).unlink(missing_ok=True)

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    gate = MaskGate(predictor) if leg == "A" else None
    oracle = gt[0] if leg == "B" else None
    if leg == "B" and oracle is None:
        raise RuntimeError("leg B needs a valid GT frame-0 box")

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, trace = replay(video, submit, make_carry, gate,
                                   oracle=oracle, reground=(leg == "A"))
    finally:
        if be is not None:
            be.close()
    wall = time.time() - wall0

    s = score_run(events, gt, fps)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "leg": leg, "clip": Path(seq_dir).name, "caption": caption,
        "fps": fps, "n_frames_gt": len(gt), "wall_s": round(wall, 1),
        "cap_hz": CARRY_HZ, "loss_s": LOSS_S, "app_tau": APP_TAU,
        "n_gate_reject": gate.n_reject if gate else 0,
        "n_events": len(events), "trace": trace, "score": s,
        "events": [(round(t, 3), None if b is None else [round(v, 1) for v in b])
                   for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    render_overlay(seq_dir, events, gt, fps, out_dir / "overlay.mp4")
    print(f"[E18 {leg} {Path(seq_dir).name}] genuine={s['genuine_lock']} "
          f"cov={s['coverage']} mean_iou={s['mean_iou']} t_lock={s['t_lock']} "
          f"gate_rej={result['n_gate_reject']} wall={wall:.0f}s", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Fake clock + synthetic frames + stub submit/carry; assert the state
    machine walks ACQUIRE -> TRACK -> REGROUND -> TRACK (D4 harness spec)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        for i in range(900):                      # 30 s @30 fps of dummy frames
            cv2.imwrite(f"{tmp}/{i:06d}.jpg",
                        np.full((40, 40, 3), i % 256, dtype=np.uint8))
        clk = [0.0]
        now = lambda: clk[0]                       # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        def submit(_frame):                        # blocks ~4.8 s of fake time
            clk[0] += 4.8
            return (5.0, 5.0, 25.0, 25.0)

        lives = {"n": 0}

        class StubCarry:
            init_mask = np.ones((40, 40), dtype=bool)

            def step(self, _f):
                lives["n"] -= 1
                return (None, (5.0, 5.0, 25.0, 25.0) if lives["n"] >= 0 else None)

        def make_carry(_frame_rgb, _box):
            lives["n"] = 4                          # alive 5 steps, then None -> loss
            return StubCarry()

        video = WallClockVideo(tmp, fps=30.0, now=now)
        events, trace = replay(video, submit, make_carry, gate=None,
                               reground=True, now=now, sleep=sleep)
    # ACQUIRE resolves -> TRACK; carry dies -> LOSS_S*CARRY_HZ empties -> REGROUND
    # -> submit re-accepts -> TRACK. Assert at least one full cycle occurred.
    assert trace[0] == TRACK, trace
    assert REGROUND in trace, trace
    assert trace.index(REGROUND) < len(trace) - 1, trace
    assert trace[trace.index(REGROUND) + 1] == TRACK, trace
    # every emitted event is a (t, box|None) with monotone-ish t
    assert all(len(e) == 2 for e in events)
    assert any(b is None for _, b in events), "a loss should have been recorded"

    # -- MaskGate fail-open with no template, and L-inf accept logic ----------
    g = MaskGate(predictor=None, app_tau=12.0)
    assert g.check((0, 0, 10, 10), np.zeros((40, 40, 3), np.uint8)) is True  # no template
    g.template = np.array([200.0, 200.0, 200.0])
    # exercise the descriptor math directly (no SAM2 needed)
    assert float(np.abs(np.array([205.0, 198.0, 203.0]) - g.template).max()) <= 12.0
    assert float(np.abs(np.array([180.0, 200.0, 200.0]) - g.template).max()) > 12.0
    print("replay_e18 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--leg", choices=["A", "B"])
    ap.add_argument("--clip", help="sequence name under data/ (dir of jpgs)")
    ap.add_argument("--seq-dir", help="explicit frames dir (overrides --clip)")
    ap.add_argument("--anno", help="explicit anno .txt (overrides default)")
    ap.add_argument("--caption", default="the car")
    ap.add_argument("--out", help="output run dir")
    ap.add_argument("--fps", type=float, default=30.0)
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    if not args.leg or not (args.clip or args.seq_dir):
        ap.error("need --leg and (--clip or --seq-dir)")
    data = HERE / "data" / "UAV123"
    seq_dir = args.seq_dir or (data / "data_seq" / "UAV123" / args.clip)
    anno = args.anno or (data / "anno" / "UAV123" / f"{args.clip}.txt")
    out = Path(args.out) if args.out else (HERE / "runs" / f"{args.leg}_{args.clip}")
    run_matrix_clip(args.leg, seq_dir, anno, args.caption, out, fps=args.fps)


if __name__ == "__main__":
    main()
