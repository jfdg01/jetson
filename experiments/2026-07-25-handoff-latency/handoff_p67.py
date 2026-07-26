"""P6.7 -- the handoff seam: designation -> live SAM2 track, decomposed and timed.

Runs on the HOST. SAM2 runs ONLY on the Jetson, over the ssh-stdio bridge
(`~/sam2-bench/carry_ssh_bridge.py`) -- the standing constraint, and the same transport
`runners/carla_debug_ui.py` uses live. The host replays the committed CARLA GT bank at the
panel's 5 Hz feed rate and holds the clock; no CARLA, no SITL, no 3090.

Two arms, differing ONLY in when the tracker process was started:

  COLD : ssh-spawn the bridge at designation time            (what the panel deploys today)
  WARM : one bridge, spawned + CUDA-warmed before the trial; designation only re-`init`s

crossed with the designation lag applied as a stub (P6.2-DELIVERY does the same for the
cold acquire): 0.0 s = ORACLE/Shift-click, 4.85 s = whole-frame VLM caption grounding.

`t_handoff` is byte-for-byte the panel's `catchup_s`: designation -> first carry step whose
feed lag is <= 1. Decomposed into ssh_spawn / import / weights / warmup_init / drain using
the bridge's two stderr markers, so no clock sync between host and Orin is needed.

    .venv-ft/bin/python handoff_p67.py --clips clip00 --out runs/p67/smoke   # smoke
    .venv-ft/bin/python handoff_p67.py --out runs/p67/matrix                 # the matrix
    .venv-ft/bin/python handoff_p67.py --sweep-jump 1,12,999 --lags 4.85 --out runs/p67/jump
    .venv-ft/bin/python handoff_p67.py --selfcheck
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import re
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BANK = REPO / "experiments" / "2026-07-21-carla-gt-bank" / "runs" / "bank"
sys.path.insert(0, str(REPO))
from grounding.contract import CARRY_IMAGE_SIZE  # noqa: E402

# The panel's constants, verbatim -- this harness is only honest if it reproduces them.
# runners/carla_debug_ui.py: CAM_HZ, CATCHUP_JUMP, ORIN_CARRY_SIZE.
CAM_HZ = 5.0
CATCHUP_JUMP = 12
# Reads the owner (R-46) instead of copying a literal, since "verbatim" above is the whole
# point of this block. **The published P6.7 numbers were measured at 512**, which is what
# the panel said at the time; a re-run today measures 640. The start-up terms (4.95 s of
# the 6.15 s) are resolution-independent, so the seam conclusion does not move -- but the
# per-step terms (`warmup_init`, `drain`) will not reproduce the published values.
CARRY_SIZE = CARRY_IMAGE_SIZE
BRIDGE_CMD = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"
# Bank clips are dt=0.05 (20 Hz); the 5 Hz feed takes every 4th frame.
CLIP_HZ = 20.0
FEED_STRIDE = int(round(CLIP_HZ / CAM_HZ))
# Designate 2 s into the clip: settled camera, and clear of any frame-0 render artifact.
SEED_AT = 40
STEPS = 100          # post-live carry steps per cell = 20 s of tracking at 5 Hz
SLACK = 75           # extra fed frames (15 s) to cover a cold arm's establishment
HARD_TIMEOUT = 90.0  # a cell that has not finished by now is a failure, not a slow run
LAGS = (0.0, 4.85)

_LOADED = re.compile(r"model loaded in ([0-9.]+)s")


# ---- ssh bridge framing (host side of carry_ssh_bridge.py) --------------------
# Copied, not imported: select_exp2.py owns the canonical pair but drags the whole
# UAV123 sys.path apparatus with it. Same 3 functions, byte-identical semantics.
def _send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data)))
    f.write(data)
    f.flush()


def _recv(f):
    hdr = b""
    while len(hdr) < 4:
        more = f.read(4 - len(hdr))
        if not more:
            return None
        hdr += more
    (n,) = struct.unpack(">I", hdr)
    buf = b""
    while len(buf) < n:
        more = f.read(n - len(buf))
        if not more:
            return None
        buf += more
    return pickle.loads(buf)


def _rgb_jpg_arr(bgr) -> bytes:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def iou(a, b) -> float:
    if a is None or b is None:
        return 0.0
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


# ---- the bank ----------------------------------------------------------------
class Clip:
    """One bank clip: decoded frames for the window under test + per-frame GT."""

    def __init__(self, name: str, first: int, last: int):
        d = BANK / name
        self.name = name
        self.man = json.loads((d / "manifest.json").read_text())
        self.target_id = self.man["target_id"]
        self.w, self.h, _ = self.man["cam_wh_fov"]
        self.gt = {}          # clip index -> {actor_id: box_vis} for in-frame actors
        for ln in (d / "gt.jsonl").open():
            r = json.loads(ln)
            i = r["i"]
            if first <= i <= last:
                self.gt[i] = {g["id"]: g["box_vis"] for g in r["gt"]
                              if g.get("area_vis_px", 0) > 0 and g.get("box_vis")}
        # Decode OUTSIDE the timed loop: a real camera hands the panel a BGR array, so
        # disk-decode is harness cost, not system cost. The jpg ENCODE stays in the loop
        # because the deployed path really does encode per frame before the ssh write.
        self.frames = {}
        for i in range(first, last + 1, FEED_STRIDE):
            p = d / "frames" / f"{i:05d}.jpg"
            img = cv2.imread(str(p))
            if img is None:
                raise SystemExit(f"missing frame {p}")
            self.frames[i] = img

    def target_box(self, i):
        return self.gt.get(i, {}).get(self.target_id)

    def best_actor(self, i, box):
        """Which GT vehicle the carried box actually covers -- the identity check."""
        best, bid = 0.0, None
        for aid, gb in self.gt.get(i, {}).items():
            v = iou(box, gb)
            if v > best:
                best, bid = v, aid
        return bid, best


def in_frame_run(name: str) -> tuple[int, int]:
    """Longest run of frames where the target is visible. Returns (start, length)."""
    d = BANK / name
    tid = json.loads((d / "manifest.json").read_text())["target_id"]
    best = cur = bstart = cstart = 0
    for ln in d.joinpath("gt.jsonl").open():
        r = json.loads(ln)
        vis = any(g["id"] == tid and g.get("area_vis_px", 0) > 0 for g in r["gt"])
        if vis:
            if cur == 0:
                cstart = r["i"]
            cur += 1
            if cur > best:
                best, bstart = cur, cstart
        else:
            cur = 0
    return bstart, best


# ---- the bridge --------------------------------------------------------------
class Bridge:
    """One `carry_ssh_bridge.py` on the Orin, with its start-up stages stamped.

    The two stderr markers are the whole decomposition: `[bridge] up` fires before
    torch/sam2 are imported, `model loaded in Ns` after `from_pretrained`. Both are
    stderr-only, so the framed stdout protocol is untouched and the live panel keeps
    working against the same file.
    """

    def __init__(self, size: int = CARRY_SIZE, errlog: Path | None = None):
        self.t_spawn = time.time()
        self.t_up = self.t_ready = self.load_s = None
        self.proc = subprocess.Popen(
            ["ssh", "-T", "-q", "jetson", BRIDGE_CMD.format(size=int(size))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.err_lines = []
        self._errlog = errlog
        self._t = threading.Thread(target=self._pump_err, daemon=True)
        self._t.start()

    def _pump_err(self):
        for raw in self.proc.stderr:
            ln = raw.decode("utf8", "replace").rstrip()
            now = time.time()
            self.err_lines.append(ln)
            if "[bridge] up" in ln and self.t_up is None:
                self.t_up = now
            m = _LOADED.search(ln)
            if m and self.t_ready is None:
                self.t_ready, self.load_s = now, float(m.group(1))
        if self._errlog is not None:
            self._errlog.write_text("\n".join(self.err_lines) + "\n")

    def wait_ready(self, timeout=120.0):
        t0 = time.time()
        while self.t_ready is None and time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise SystemExit(f"bridge died rc={self.proc.returncode}: {self.err_lines[-3:]}")
            time.sleep(0.005)
        if self.t_ready is None:
            raise SystemExit("bridge never reported ready")

    def init(self, bgr, box):
        _send(self.proc.stdin, ("init", _rgb_jpg_arr(bgr), [int(v) for v in box]))
        return _recv(self.proc.stdout)

    def step(self, bgr):
        _send(self.proc.stdin, ("step", _rgb_jpg_arr(bgr)))
        return _recv(self.proc.stdout)

    def warm(self, w, h):
        """One throwaway init+step on synthetic pixels: pays the first-forward CUDA
        warm-up so the WARM arm's designation does not. Noise, not a black frame --
        SAM2 on a uniform image is a degenerate forward that may skip kernels."""
        rng = np.random.default_rng(0)
        img = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        assert self.init(img, [w // 3, h // 3, 2 * w // 3, 2 * h // 3]).get("ok")
        self.step(img)

    def close(self):
        for fn in (lambda: self.proc.stdin.close(), lambda: self.proc.wait(timeout=5),
                   self.proc.kill):
            try:
                fn()
            except Exception:
                pass


# ---- one cell ----------------------------------------------------------------
def run_cell(clip: Clip, arm: str, lag_s: float, jump: int, warm_bridge, outdir: Path,
             steps: int = STEPS) -> dict:
    """Replay one designation. Returns the per-cell record; writes trace.jsonl."""
    lag_frames = int(round(lag_s * CAM_HZ))
    seed_i = SEED_AT
    seed_box = clip.target_box(seed_i)
    if seed_box is None:
        raise SystemExit(f"{clip.name}: target not visible at seed frame {seed_i}")
    # Feed indices, in clip frames. At t0 the world has already advanced by the
    # designation lag, so those frames are ALREADY in the backlog -- that is the
    # staleness the drain has to eat. Everything after arrives live at 5 Hz, and it
    # keeps arriving WHILE the bridge is starting up: the camera does not wait for the
    # tracker. That is the whole reason a cold start costs more than its own duration,
    # and it is what makes the panel's oracle follows take exactly 3 jump-12 steps.
    # SLACK covers the worst establishment (~12 s) so the cell still collects `steps`
    # post-live rows in both arms.
    start = seed_i + FEED_STRIDE
    feed = [start + FEED_STRIDE * j for j in range(lag_frames + steps + SLACK)]
    feed = [i for i in feed if i in clip.frames]

    tdir = outdir / f"{clip.name}-{arm}-lag{lag_s:g}-j{jump}"
    tdir.mkdir(parents=True, exist_ok=True)
    trace = (tdir / "trace.jsonl").open("w", buffering=1)

    backlog, live_n = collections.deque(maxlen=400), {"n": seed_i}
    for i in feed[:lag_frames]:
        backlog.append(i)
        live_n["n"] = i
    stop = threading.Event()

    def feeder():
        t = time.time()
        for i in feed[lag_frames:]:
            t += 1.0 / CAM_HZ
            d = t - time.time()
            if d > 0:
                time.sleep(d)
            if stop.is_set():
                return
            backlog.append(i)
            live_n["n"] = i

    # t0 IS the designation instant, and the feed starts with it -- not after the tracker
    # is ready. Starting it later would hand the cold arm a frozen world and erase the
    # backlog its own start-up creates.
    t0 = time.time()
    th = threading.Thread(target=feeder, daemon=True)
    th.start()
    if arm == "COLD":
        br = Bridge(errlog=tdir / "bridge.err")
        br.wait_ready()
    else:
        br = warm_bridge
    ack = br.init(clip.frames[seed_i], seed_box)
    t_initack = time.time()
    if not (ack and ack.get("ok")):
        stop.set()
        th.join(timeout=2)
        trace.close()
        return {"clip": clip.name, "arm": arm, "lag_s": lag_s, "jump": jump,
                "ok": False, "why": f"init failed: {ack}"}

    cursor, t_live, rows, prev_id = seed_i, None, [], None
    swaps, rc, n_post = 0, None, 0
    try:
        while time.time() - t0 < HARD_TIMEOUT and n_post < steps:
            pending = [i for i in backlog if i > cursor]
            if not pending:
                if not th.is_alive():
                    break
                time.sleep(0.005)
                continue
            n = pending[min(len(pending), jump) - 1]
            r = br.step(clip.frames[n])
            if r is None:
                try:
                    rc = br.proc.wait(timeout=2)
                except Exception:
                    rc = None
                trace.write(json.dumps({"ev": "bridge_died", "n": n, "rc": rc}) + "\n")
                break
            cursor = n
            box = [float(v) for v in r["box"]] if r.get("box") else None
            flag = live_n["n"] - cursor
            gtb = clip.target_box(n)
            bid, bi = clip.best_actor(n, box) if box else (None, 0.0)
            if t_live is None and flag <= 1:
                t_live = time.time()
            n_post += t_live is not None
            if bid is not None and bid != prev_id:
                swaps += prev_id is not None
                prev_id = bid
            row = {"ev": "step", "n": n, "lag": flag, "ms": r.get("ms"), "box": box,
                   "iou": round(iou(box, gtb), 4) if gtb else None,
                   "in_frame": gtb is not None, "best_id": bid,
                   "best_iou": round(bi, 4), "post_live": t_live is not None}
            rows.append(row)
            trace.write(json.dumps(row) + "\n")
    finally:
        stop.set()
        th.join(timeout=2)
        trace.close()
        if arm == "COLD":
            br.close()

    post = [r for r in rows if r["post_live"] and r["in_frame"]]
    ious = [r["iou"] for r in post if r["iou"] is not None]
    rec = {
        "clip": clip.name, "arm": arm, "lag_s": lag_s, "jump": jump, "ok": t_live is not None,
        "alt": clip.man["alt"], "target_id": clip.target_id, "seed_i": seed_i,
        "seed_box": seed_box, "n_steps": len(rows), "n_post": len(post),
        "t_handoff": round(t_live - t0, 4) if t_live else None,
        "steps_to_live": sum(1 for r in rows if not r["post_live"]) + 1 if t_live else None,
        "median_iou": round(float(np.median(ious)), 4) if ious else None,
        "box_frac": round(sum(r["box"] is not None for r in post) / len(post), 4) if post else None,
        "on_target_frac": round(sum(r["best_id"] == clip.target_id for r in post) / len(post), 4)
        if post else None,
        "swaps": swaps, "rc": rc, "trace": str(tdir / "trace.jsonl"),
    }
    if arm == "COLD":
        rec["stages"] = {
            "ssh_spawn": round(br.t_up - br.t_spawn, 4) if br.t_up else None,
            "import": round(br.t_ready - br.t_up - br.load_s, 4)
            if (br.t_up and br.t_ready) else None,
            "weights": br.load_s,
            "warmup_init": round(t_initack - br.t_ready, 4) if br.t_ready else None,
            "drain": round(t_live - t_initack, 4) if t_live else None,
        }
    else:
        rec["stages"] = {"ssh_spawn": 0.0, "import": 0.0, "weights": 0.0,
                         "warmup_init": round(t_initack - t0, 4),
                         "drain": round(t_live - t_initack, 4) if t_live else None}
    # I5: an overlay at the instant the track goes live, and one mid-window. A verdict
    # about what the tracker latched onto is not writable from a log.
    for tag, r in (("live", next((r for r in rows if r["post_live"]), None)),
                   ("mid", post[len(post) // 2] if post else None)):
        if r and r["box"]:
            f = clip.frames[r["n"]].copy()
            gtb = clip.target_box(r["n"])
            if gtb:
                cv2.rectangle(f, (int(gtb[0]), int(gtb[1])), (int(gtb[2]), int(gtb[3])),
                              (0, 200, 255), 1)
            b = [int(v) for v in r["box"]]
            cv2.rectangle(f, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 2)
            cv2.putText(f, f"{clip.name} {arm} lag{lag_s:g} n={r['n']} iou={r['iou']}",
                        (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.imwrite(str(tdir / f"seam-{tag}.png"), f)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default="", help="comma list; default = all 25")
    ap.add_argument("--lags", default=",".join(str(x) for x in LAGS))
    ap.add_argument("--arms", default="COLD,WARM")
    ap.add_argument("--sweep-jump", default=str(CATCHUP_JUMP))
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--out")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    if not args.out:
        ap.error("--out is required unless --selfcheck")

    names = ([c.strip() for c in args.clips.split(",") if c.strip()]
             or sorted(p.name for p in BANK.glob("clip*") if p.is_dir()))
    lags = [float(x) for x in args.lags.split(",")]
    arms = [a.strip() for a in args.arms.split(",")]
    jumps = [int(x) for x in args.sweep_jump.split(",")]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    last = SEED_AT + FEED_STRIDE * (int(max(lags) * CAM_HZ) + args.steps + SLACK + 1)
    # COLD runs FIRST, with no other SAM2 on the board. Interleaving the arms would let
    # the resident WARM bridge contend with every COLD start-up and inflate the very gap
    # this experiment reports -- a confound in the direction of the hypothesis, which is
    # the one direction that is never acceptable. Deployment has exactly one SAM2 in
    # either arm, and so does each pass. `llama-server` stays resident throughout.
    arms = sorted(arms, key=lambda a: a != "COLD")
    recs, warm = [], None

    def emit(r, name, arm, lag, jump, run):
        r["target_run"] = list(run)
        recs.append(r)
        print(f"[{name} {arm} lag{lag:g} j{jump}] t_handoff={r['t_handoff']} "
              f"steps={r['n_steps']}/{r['n_post']} iou={r['median_iou']} "
              f"on_target={r['on_target_frac']} stages={r['stages']}", flush=True)
        (out / "results.json").write_text(json.dumps(
            {"cells": recs, "config": {
                "cam_hz": CAM_HZ, "carry_size": CARRY_SIZE, "seed_at": SEED_AT,
                "steps": args.steps, "slack": SLACK, "feed_stride": FEED_STRIDE,
                "catchup_jump_default": CATCHUP_JUMP, "bank": str(BANK)}}, indent=1))

    try:
        for arm in arms:
            if arm == "WARM":
                warm = Bridge(errlog=out / "warm_bridge.err")
                warm.wait_ready()
                warm.warm(640, 480)
                print(f"[warm] bridge up: ssh+py {warm.t_up - warm.t_spawn:.2f}s, "
                      f"import {warm.t_ready - warm.t_up - warm.load_s:.2f}s, "
                      f"weights {warm.load_s:.2f}s", flush=True)
            for name in names:
                run = in_frame_run(name)
                clip = Clip(name, 0, last)
                for lag in lags:
                    for jump in jumps:
                        emit(run_cell(clip, arm, lag, jump, warm, out, args.steps),
                             name, arm, lag, jump, run)
    finally:
        if warm is not None:
            warm.close()
    print(f"wrote {out/'results.json'} ({len(recs)} cells)")


def selfcheck() -> None:
    """The pure parts, offline: no Jetson, no bank decode."""
    assert abs(iou([0, 0, 10, 10], [0, 0, 10, 10]) - 1.0) < 1e-9
    assert abs(iou([0, 0, 10, 10], [5, 0, 15, 10]) - 1 / 3) < 1e-9
    assert iou([0, 0, 1, 1], [5, 5, 6, 6]) == 0.0
    assert iou(None, [0, 0, 1, 1]) == 0.0
    assert FEED_STRIDE == 4, FEED_STRIDE
    # the framing round-trips through a real file object
    import io
    buf = io.BytesIO()
    _send(buf, ("step", b"xy"))
    buf.seek(0)
    assert _recv(buf) == ("step", b"xy")
    assert _recv(io.BytesIO(b"")) is None          # clean EOF, not an exception
    assert _LOADED.search("[bridge] model loaded in 1.7s, image_size=512, ready").group(1) == "1.7"
    # a 4.85 s lag really is 24 backlog frames at 5 Hz
    assert int(round(4.85 * CAM_HZ)) == 24
    print("selfcheck OK")


if __name__ == "__main__":
    main()
