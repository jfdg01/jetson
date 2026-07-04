"""E24 warm-start acquire harness (Part V, first experiment).

Fork of experiments/2026-07-03-real-video-replay/replay_e18.py (provenance: that
file is the E18 source of truth). E24 reframes the Part IV acquire-latency arc: the
operator's command arrives mid-flight at t_p > 0, not at frame 0, so the idle
pre-prompt stream is FREE COMPUTE. Three legs answer ONE command issued at t_p:

  WARM   : a full-frame VLM acquire fires at t=0 during idle; its box (from the
           SUBMIT frame 0, cached) seeds StreamCarry on that cached frame (E4
           "Fix B" submit-frame init); the carry then consumes the buffered frames
           0..prompt at the carry cadence NON-REALTIME (the free-compute idle
           catch-up, E19 BUF-style stride sub-sample) so the track is CURRENT at
           the prompt. Operator SELECTS the single carried track at prompt_frame;
           box scored there (fresh). REGROUND on (mask gate, app-tau 12.0).
  ORACLE : same as WARM but seeded from gt[0] instead of a real VLM box -- E18-B
           extended to a t_p>0 select. Isolates "is the real detection good
           enough to seed?". REGROUND off (E18-B rule).
  COLD   : E18-A shifted to t_p. Operator speaks at prompt; a full-frame VLM
           acquire fires THEN, lands acq_frames later (MEASURED wall-time, not the
           nominal 4.85), and the submit-frame box is delivered STALE at
           prompt+acq; carry seeds at that arrival frame. REGROUND on.

Fairness: each leg is scored at the frame the operator ACTUALLY RECEIVES a box
(its deliver_frame) -- genuine_lock at that frame, coverage over the cover_s window
after it (warmstart.window). Frame arithmetic is frozen in warmstart.schedule --
imported, NOT re-derived.

Reused, not rewritten: WallClockVideo / load_uav123_gt / iou (replay_source),
StreamCarry / MODEL (stream_carry), warmstart.schedule / window. vlm_acquire /
mask_descriptor / MaskGate / render_overlay are forked verbatim from replay_e18
(with provenance) -- phase3_sitl / follow_demo drag SITL deps absent on this path.

    .venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-04-warm-start-acquire/replay_e24.py \
        --leg WARM --clip car10 --caption "the red car" --out runs/warm_car10_r1
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
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(REPO))

from replay_source import WallClockVideo, iou, load_uav123_gt  # noqa: E402
from warmstart import schedule, window                          # noqa: E402

CARRY_HZ = 6.15        # D3: E1's measured on-Orin co-resident TensorRT carry rate
LOSS_S = 1.0           # empty-mask streak (s) before declaring loss -> REGROUND
APP_TAU = 12.0         # E14: mask-descriptor L-inf accept threshold for REGROUND
MAX_SIDE = 1024        # deployed full-frame acquire resolution
NOMINAL_ACQUIRE = 4.85  # planning-only acquire wall-time; COLD uses the MEASURED one

TRACK, REGROUND = "TRACK", "REGROUND"


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
    """One full-frame VLM grounding pass -> pixel box | None."""
    from grounding.contract import COORD_SCALE, parse_bbox
    raw = backend.generate(frame_path, caption)
    b = parse_bbox(raw)
    if b is None:
        return None
    return (b[0] / COORD_SCALE * w, b[1] / COORD_SCALE * h,
            b[2] / COORD_SCALE * w, b[3] / COORD_SCALE * h)


class MaskGate:
    """E14/E16 mask-bound REGROUND identity gate (verbatim from E18)."""

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


def _stride(fps: float) -> int:
    """Carry-cadence sub-sample: process every ~1/CARRY_HZ s worth of frames."""
    return max(1, round(fps / CARRY_HZ))


def idle_catchup(carry, frame_at, seed_frame, prompt_frame, fps):
    """WARM/ORACLE free-compute idle window: step the carry (seeded on
    seed_frame) forward through the buffered frames seed_frame..prompt_frame at
    the carry cadence, NON-REALTIME (the operator has not spoken yet). E19
    BUF-style stride sub-sample so the track is CURRENT at prompt_frame. Returns
    (held_box_at_prompt | None, n_steps)."""
    stride = _stride(fps)
    steps = list(range(seed_frame + stride, prompt_frame, stride))
    if not steps or steps[-1] != prompt_frame:
        steps.append(prompt_frame)          # always land exactly on the prompt
    box, n = None, 0
    for f in steps:
        frame = frame_at(f)
        _, b = carry.step(_rgb(frame))
        n += 1
        if _valid(b, frame.shape):
            box = b
    return box, n


def coverage_realtime(carry, seq_dir_or_video, frame_at, gt, fps, deliver_frame,
                      window_end, *, reground, gate, submit, make_carry,
                      cap_hz=CARRY_HZ, loss_s=LOSS_S, now=time.monotonic,
                      sleep=time.sleep):
    """Post-delivery REALTIME carry over [deliver_frame, window_end): frames DROP
    while the carry (rate-capped at cap_hz) and any REGROUND submit run -- the E18
    WallClockVideo rule applied AFTER delivery (the drone acting under load).
    Returns the list of (t_rel_s, box|None) events emitted in the window; t is in
    the absolute clip time-base (deliver_frame/fps offset), so held_at frame
    scoring lines up with the deliver event."""
    video = WallClockVideo(seq_dir_or_video, fps=fps, now=now)
    video.start()
    video._t0 = now() - deliver_frame / fps      # begin the wall clock at delivery
    events, state, empty = [], TRACK, 0
    while (grab := video.latest()) is not None:
        i, frame = grab
        if i >= window_end:
            break
        t0 = now()
        if state == TRACK:
            _, box = carry.step(_rgb(frame))
            if _valid(box, frame.shape):
                events.append((video.t(), tuple(box)))
                empty = 0
            else:
                empty += 1
                if reground and empty >= loss_s * cap_hz:
                    events.append((video.t(), None))
                    empty, state = 0, REGROUND
        else:                                    # REGROUND
            box = submit(frame)
            if not _valid(box, frame.shape):
                continue
            if gate is not None and not gate.check(box, frame):
                continue
            carry = make_carry(_rgb(frame), box)
            events.append((video.t(), tuple(box)))
            empty, state = 0, TRACK
        dt = 1.0 / cap_hz - (now() - t0)
        if dt > 0:
            sleep(dt)
    return events


def e24_score(events, gt, fps, deliver_frame, cover_frames):
    """Authoritative E24 metric: genuine_lock at deliver_frame, coverage over
    warmstart.window after it. `events` = [(t_rel_s, box|None)] in the clip
    time-base; held box at native frame i = last event with t <= i/fps."""
    ev = sorted(events, key=lambda e: e[0])
    clip_len = len(gt)
    d = min(deliver_frame, clip_len - 1)
    start, end = window(deliver_frame, cover_frames, clip_len)

    def held_at(frame_i):
        t = frame_i / fps
        held = None
        for te, b in ev:
            if te <= t:
                held = b
            else:
                break
        return held

    dbox = held_at(d)
    gl = (gt[d] is not None and dbox is not None
          and iou(dbox, gt[d]) >= 0.25)
    ious = []
    for i in range(start, end):
        if gt[i] is None:
            continue
        h = held_at(i)
        ious.append(iou(h, gt[i]) if h is not None else 0.0)
    cov = sum(v >= 0.25 for v in ious) / len(ious) if ious else 0.0
    return {
        "genuine_lock": bool(gl),
        "coverage": round(cov, 4),
        "mean_iou": round(float(np.mean(ious)), 4) if ious else 0.0,
        "n_scored": len(ious),
        "deliver_frame": deliver_frame,
        "deliver_iou": round(iou(dbox, gt[d]), 4) if (dbox and gt[d]) else 0.0,
        "window": [start, end],
    }


def run_leg(leg, gt, frame_at, submit, make_carry, gate, *, t_p, cover_s, fps,
            frame_shape, now=time.monotonic, sleep=time.sleep,
            seq_dir_or_video=None):
    """Run one leg. Returns (events, warm_block, meta). Injectable submit/
    make_carry/frame_at/gt so --selfcheck can stub the real stack.

    events: the operator-visible timeline -- FIRST event is the delivery (nothing
    before it: the operator has no box until the prompt / the stale arrival)."""
    clip_len = len(gt)
    meta = {"leg": leg}

    if leg == "ORACLE":
        # E18-B extended: seed gt[0], idle catch-up to prompt, select there.
        sched = schedule(t_p, NOMINAL_ACQUIRE, fps=fps, cover_s=cover_s)
        seed = gt[0]
        assert seed is not None, "ORACLE needs a valid GT frame-0 box"
        carry = make_carry(_rgb(frame_at(0)), seed)
        box, n = idle_catchup(carry, frame_at, sched.warm_seed_frame,
                              sched.warm_deliver_frame, fps)
        deliver = sched.warm_deliver_frame
        events = [(deliver / fps, tuple(box))] if _valid(box, frame_shape) else []
        events += coverage_realtime(
            carry, seq_dir_or_video, frame_at, gt, fps, deliver,
            window(deliver, sched.cover_frames, clip_len)[1],
            reground=False, gate=None, submit=submit, make_carry=make_carry,
            now=now, sleep=sleep)
        meta.update({"acquire_s": None, "seed": "gt[0]", "seed_frame": 0,
                     "deliver_frame": deliver, "catchup_steps": n})

    elif leg == "WARM":
        # Free-compute idle acquire on cached frame 0, Fix-B submit-frame seed,
        # idle catch-up to prompt, select there. REGROUND on.
        t0 = now()
        box0 = submit(frame_at(0))
        acquire_s = now() - t0
        if not _valid(box0, frame_shape):
            return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                        "deliver_frame": None, "reason": "acquire returned no box"}, \
                {**meta, "acquire_s": round(acquire_s, 2), "seed": "vlm[0]"}
        if acquire_s >= t_p:
            # warm track not ready by the prompt -> out of scope (early-prompt case)
            meta["warning"] = f"acquire {acquire_s:.2f}s >= t_p {t_p}s (out of E24 scope)"
        sched = schedule(t_p, NOMINAL_ACQUIRE, fps=fps, cover_s=cover_s)
        carry = make_carry(_rgb(frame_at(0)), box0)
        if gate is not None:
            gate.bind(frame_at(0), carry.init_mask)
        box, n = idle_catchup(carry, frame_at, sched.warm_seed_frame,
                              sched.warm_deliver_frame, fps)
        deliver = sched.warm_deliver_frame
        events = [(deliver / fps, tuple(box))] if _valid(box, frame_shape) else []
        events += coverage_realtime(
            carry, seq_dir_or_video, frame_at, gt, fps, deliver,
            window(deliver, sched.cover_frames, clip_len)[1],
            reground=True, gate=gate, submit=submit, make_carry=make_carry,
            now=now, sleep=sleep)
        meta.update({"acquire_s": round(acquire_s, 2), "seed": "vlm[0]",
                     "seed_frame": 0, "deliver_frame": deliver, "catchup_steps": n,
                     "seed_box": [round(v, 1) for v in box0]})

    elif leg == "COLD":
        # E18-A shifted to t_p: acquire fires at the prompt, lands acq_frames later
        # (MEASURED wall-time), submit-frame box delivered STALE at the arrival
        # frame; carry seeds THERE. REGROUND on.
        prompt = round(t_p * fps)
        t0 = now()
        box0 = submit(frame_at(prompt))
        acquire_s = now() - t0
        sched = schedule(t_p, acquire_s if acquire_s < t_p else NOMINAL_ACQUIRE,
                         fps=fps, cover_s=cover_s)
        if acquire_s >= t_p:
            meta["warning"] = (f"measured acquire {acquire_s:.2f}s >= t_p {t_p}s; "
                               "used nominal for schedule")
        deliver = sched.cold_deliver_frame
        if not _valid(box0, frame_shape) or deliver >= clip_len:
            return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                        "deliver_frame": deliver,
                        "reason": "no box" if not _valid(box0, frame_shape)
                        else "deliver past clip end"}, \
                {**meta, "acquire_s": round(acquire_s, 2), "seed": "vlm[prompt]"}
        carry = make_carry(_rgb(frame_at(deliver)), box0)   # seed at ARRIVAL frame
        if gate is not None:
            gate.bind(frame_at(deliver), carry.init_mask)
        events = [(deliver / fps, tuple(box0))]             # stale submit box
        events += coverage_realtime(
            carry, seq_dir_or_video, frame_at, gt, fps, deliver,
            window(deliver, sched.cover_frames, clip_len)[1],
            reground=True, gate=gate, submit=submit, make_carry=make_carry,
            now=now, sleep=sleep)
        meta.update({"acquire_s": round(acquire_s, 2), "seed": "vlm[prompt]",
                     "seed_frame": deliver, "deliver_frame": deliver,
                     "acq_frames": deliver - prompt,
                     "seed_box": [round(v, 1) for v in box0]})
    else:
        raise ValueError(leg)

    warm = e24_score(events, gt, fps, meta["deliver_frame"], sched.cover_frames)
    warm.update({"leg": leg, "t_p": t_p, "cover_s": cover_s,
                 "acquire_s": meta.get("acquire_s"),
                 "seed_frame": meta.get("seed_frame")})
    return events, warm, meta


# --- overlay: forked verbatim from replay_e18.render_overlay ------------------
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


def run_matrix_clip(leg, seq_dir, anno, caption, out_dir, t_p=8.0, cover_s=10.0,
                    fps=30.0, clip=False):
    """One full E24 run of one clip/leg on the real stack. WARM/COLD use the real
    Jetson q8_0 acquire; the SAM2 carry runs locally rate-capped to CARRY_HZ."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    gt = load_uav123_gt(anno)
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(Path(seq_dir).glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]
    frame_shape = (h0, w0, 3)

    be = None
    if leg in ("WARM", "COLD"):
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        print(f"[E24 {leg} {Path(seq_dir).name}] booting Jetson q8_0 server...", flush=True)
        be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                           f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                           ssh_host="jetson", max_side=MAX_SIDE)

    def submit(frame_bgr):
        if be is None:
            return None
        path = f"/dev/shm/e24_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        try:
            return vlm_acquire(be, path, caption, w0, h0)
        finally:
            Path(path).unlink(missing_ok=True)

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    gate = MaskGate(predictor) if leg in ("WARM", "COLD") else None

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, warm, meta = run_leg(
                leg, gt, frame_at, submit, make_carry, gate,
                t_p=t_p, cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                seq_dir_or_video=str(seq_dir))
    finally:
        if be is not None:
            be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "leg": leg, "clip": Path(seq_dir).name, "caption": caption,
        "t_p": t_p, "cover_s": cover_s, "fps": fps, "n_frames_gt": len(gt),
        "wall_s": round(wall, 1), "cap_hz": CARRY_HZ, "loss_s": LOSS_S,
        "app_tau": APP_TAU, "n_gate_reject": gate.n_reject if gate else 0,
        "n_events": len(events), "meta": meta,
        # authoritative E24 metric (windowed at the leg's deliver_frame):
        "warm": warm,
        "events": [(round(t, 3), None if b is None else [round(v, 1) for v in b])
                   for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    if clip:
        render_overlay(seq_dir, events, gt, fps, out_dir / "overlay.mp4")
    print(f"[E24 {leg} {Path(seq_dir).name}] genuine={warm['genuine_lock']} "
          f"cov={warm['coverage']} deliver_iou={warm['deliver_iou']} "
          f"deliver_f={warm['deliver_frame']} acq={meta.get('acquire_s')} "
          f"gate_rej={result['n_gate_reject']} wall={wall:.0f}s", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub backend + synthetic frames + fake clock: assert each leg's seed/
    deliver frame matches warmstart.schedule, and that WARM/ORACLE deliver 146
    frames FRESHER than COLD (t_p=8s, acquire 4.85s)."""
    import tempfile

    fps, t_p, cover_s = 30.0, 8.0, 10.0
    clip_len = 800
    box = (10.0, 10.0, 30.0, 30.0)
    gt = [box] * clip_len
    frame_shape = (48, 48, 3)
    L = schedule(t_p, NOMINAL_ACQUIRE, fps=fps, cover_s=cover_s)

    with tempfile.TemporaryDirectory() as tmp:
        for i in range(clip_len):                            # synthetic clip on disk
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", np.full(frame_shape, 100, np.uint8))

        def frame_at(_i):
            return np.full(frame_shape, 100, np.uint8)

        clk = [0.0]
        now = lambda: clk[0]                                 # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)  # noqa: E731

        class StubCarry:
            init_mask = np.ones((48, 48), dtype=bool)

            def step(self, _f):
                return (None, box)                           # always alive on GT box

        def make_carry(_r, _b):
            return StubCarry()

        def submit(_f):
            clk[0] += 4.85                                   # measured acquire ~4.85s
            return box

        for leg, want_deliver, want_seed in (("ORACLE", L.warm_deliver_frame, 0),
                                             ("WARM", L.warm_deliver_frame, 0),
                                             ("COLD", L.cold_deliver_frame, None)):
            clk[0] = 0.0
            gate = MaskGate(predictor=None) if leg != "ORACLE" else None  # fail-open
            events, warm, meta = run_leg(
                leg, gt, frame_at, submit, make_carry, gate,
                t_p=t_p, cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                now=now, sleep=sleep, seq_dir_or_video=tmp)
            assert warm["deliver_frame"] == want_deliver, (leg, warm)
            assert meta["deliver_frame"] == want_deliver, (leg, meta)
            # first (delivery) event lands exactly at the deliver frame's time
            assert abs(events[0][0] - want_deliver / fps) < 1e-6, (leg, events[0])
            if want_seed is not None:
                assert meta["seed_frame"] == want_seed, (leg, meta)
            # stub carry holds the GT box everywhere -> genuine lock + full coverage
            assert warm["genuine_lock"] is True, (leg, warm)
            assert warm["coverage"] == 1.0, (leg, warm)
    # the whole point: WARM/ORACLE deliver 146 frames fresher than COLD
    assert L.cold_deliver_frame - L.warm_deliver_frame == 146, L

    # windowed scorer: a box that misses GT fails genuine_lock and scores 0 cov
    miss = [(240 / 30.0, (500.0, 500.0, 520.0, 520.0))]
    w2 = e24_score(miss, gt, 30.0, 240, 300)
    assert not w2["genuine_lock"] and w2["coverage"] == 0.0, w2

    # MaskGate fail-open with no template (unchanged from E18)
    g = MaskGate(predictor=None, app_tau=12.0)
    assert g.check((0, 0, 10, 10), np.zeros((40, 40, 3), np.uint8)) is True
    g.template = np.array([200.0, 200.0, 200.0])
    assert float(np.abs(np.array([205.0, 198.0, 203.0]) - g.template).max()) <= 12.0
    assert float(np.abs(np.array([180.0, 200.0, 200.0]) - g.template).max()) > 12.0
    print("replay_e24 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--leg", choices=["WARM", "COLD", "ORACLE"])
    ap.add_argument("--clip", help="sequence name under E18 data/ (dir of jpgs)")
    ap.add_argument("--seq-dir", help="explicit frames dir (overrides --clip)")
    ap.add_argument("--anno", help="explicit anno .txt (overrides default)")
    ap.add_argument("--caption", default="the car")
    ap.add_argument("--t-p", type=float, default=8.0)
    ap.add_argument("--cover-s", type=float, default=10.0)
    ap.add_argument("--out", help="output run dir")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--clip-overlay", dest="clip_overlay", action="store_true",
                    default=True, help="write overlay.mp4 (default on)")
    ap.add_argument("--no-clip-overlay", dest="clip_overlay", action="store_false")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    if not args.leg or not (args.clip or args.seq_dir):
        ap.error("need --leg and (--clip or --seq-dir)")
    data = E18 / "data" / "UAV123"
    seq_dir = args.seq_dir or (data / "data_seq" / "UAV123" / args.clip)
    anno = args.anno or (data / "anno" / "UAV123" / f"{args.clip}.txt")
    out = Path(args.out) if args.out else (HERE / "runs" / f"{args.leg}_{args.clip}")
    run_matrix_clip(args.leg, seq_dir, anno, args.caption, out,
                    t_p=args.t_p, cover_s=args.cover_s, fps=args.fps,
                    clip=args.clip_overlay)


if __name__ == "__main__":
    main()
