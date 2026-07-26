#!/usr/bin/env python3
"""WARM / COLD detection producers for the P6.2 closed-loop flight (R-35, incr. 3).

Both satisfy the `run_p62_flight` seam: constructed with the shared
`LatestDetectionSlot`, driven each control tick by `.step(frame_bgr, gt, now)`
(non-blocking -- it only stashes the latest frame), and torn down with `.close()`.
The heavy work (VLM acquire, SAM2 carry) runs on the producer's OWN worker thread
so the 20 Hz control loop never blocks on a ~4.85 s acquire or a carry step.

WARM vs COLD -- the whole experiment, in the worker state machine
----------------------------------------------------------------
- WARM: grounds an IDLE-window frame (free compute, before the operator's prompt),
  seeds the SAM2 carry on it, and MAINTAINS the track. At the prompt the maintained
  box is delivered immediately -- acquire latency at command = 0.
- COLD: does nothing until the prompt, then fires a BLOCKING acquire at the prompt
  frame (real Jetson wall-clock ~4.85 s, the copter hovers meanwhile), seeds the
  carry on the ARRIVAL frame with the now-STALE box, and delivers it late. The box
  is whatever the target has become ~4.85 s later -- stale, or gone from frame.
Mirrors `replay_e24.run_leg` WARM/COLD (which invariant-checks
`cold_deliver_frame - warm_deliver_frame == 146`), lifted onto a live camera.

Swappable backends (D-part6 SAM2-device decision)
-------------------------------------------------
`acquire_fn(frame_bgr, w, h) -> (x1,y1,x2,y2)|None`  -- grounding; real = Jetson
  q8_0 via `JetsonBackend`+`vlm_acquire` (ALWAYS on-device: quantization moves the box).
`carry_factory(frame_rgb, box) -> Carry` with `Carry.step(frame_rgb) -> box|None`
  -- real matrix = `StreamCarry` on the 3090 rate-capped to the Jetson's measured
  rate (E1 parity 1.000 makes the boxes device-identical; capping to CARRY_HZ models
  the on-board cadence with zero SSH-transport artifact). The published P6.2 matrix
  ran at `P62_ASRUN_CARRY_HZ` (2.69, image_size 1024); the default is now the
  deployed 640 rate. Showcase swaps in a Jetson-service carry. The producer never
  assumes which; that is the point.

ponytail: the carry is rate-capped, not run every tick -- a real device can't do more,
and running it at 20 Hz would fake a cadence the deployment can't deliver.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grounding.contract import CARRY_HZ  # noqa: E402  -- 5.76 Hz @ the deployed 640 (R-46)

# What the published P6.2 matrix actually ran at. The rate cap is a *parameter*
# (`carry_hz=`), and the default now follows the deployed resolution, so reproducing
# P6.2's numbers means passing this explicitly rather than inheriting the default.
# It is R-16's 1024 rate; EXP-1 later measured 2.34 Hz at the same resolution on the
# same box, so treat 2.69 as the as-run cap, not as today's best estimate of 1024.
P62_ASRUN_CARRY_HZ = 2.69


def _rgb(bgr):
    """BGR (CARLA/cv2) -> RGB (SAM2 / StreamCarry expects RGB), matches replay_e24._rgb."""
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _box_to_bbox(box):
    """(x1,y1,x2,y2) -> {cx,cy,w,h}, the slot/PID convention. None-safe.

    Duplicated from run_p62_flight to keep this module importable on its own for the
    selftest; the shapes are asserted identical there.
    """
    if box is None:
        return None
    return {"cx": (box[0] + box[2]) / 2.0, "cy": (box[1] + box[3]) / 2.0,
            "w": box[2] - box[0], "h": box[3] - box[1]}


class WarmColdProducer:
    """One producer, two modes. Worker thread owns all grounding + carry."""

    def __init__(self, slot, acquire_fn: Callable, carry_factory: Callable, *,
                 mode: str, t_prompt: float, w: int, h: int,
                 warm_seed_at: float = 0.5, carry_hz: float = CARRY_HZ,
                 oracle_gt: bool = False, cold_latency_s: float = 4.85):
        assert mode in ("warm", "cold"), mode
        self.slot = slot
        self.acquire_fn = acquire_fn
        self.carry_factory = carry_factory
        self.mode = mode
        self.t_prompt = t_prompt
        self.w, self.h = w, h
        self.warm_seed_at = warm_seed_at
        self.period = 1.0 / carry_hz
        # oracle_gt: seed the carry from the operator's DESIGNATION (target GT box), not a VLM
        # phrase. Isolates the closed-loop delivery variable from the nadir-grounding
        # center-bias (probe8: off-centre lock 0/8) -- P6's declared novelty is the loop, not
        # grounding. cold_latency_s models the ~4.85 s Jetson acquire the copter hovers through.
        self.oracle_gt = oracle_gt
        self.cold_latency_s = cold_latency_s

        self._frame = None            # latest BGR frame from the control loop
        self._gt = None               # latest target GT box (oracle designation source)
        self._now = 0.0               # its wall-clock stamp (loop-relative)
        self._flock = threading.Lock()
        self._stop = threading.Event()
        self._cur_box = None          # latest carried/acquired box (x1,y1,x2,y2)
        # observable outcome, for scoring + the per-flight record
        self.info = {"mode": mode, "seeded": False, "seed_box": None,
                     "acquire_s": None, "deliver_t": None, "grounded_out_of_scope": False}
        self._thread = threading.Thread(target=self._worker, name=f"prod-{mode}", daemon=True)
        self._thread.start()

    # -- control-loop side (non-blocking) -----------------------------------
    def step(self, frame_bgr, gt_box, now_ts):
        """Called every control tick. Only stashes the frame; never blocks.

        In VLM mode `gt_box` is IGNORED (a real producer perceives the frame). In oracle_gt
        mode it is the operator's target DESIGNATION, stashed to seed the carry from.
        """
        with self._flock:
            self._frame = frame_bgr
            self._gt = gt_box
            self._now = now_ts

    def _latest(self):
        with self._flock:
            return self._frame, self._now

    def _deliver(self, box, ts):
        self.slot.write(ts, _box_to_bbox(box), vlm_ms=0.0, raw_text=self.mode)
        if self.info["deliver_t"] is None:
            self.info["deliver_t"] = ts

    # -- worker side (all heavy work) ---------------------------------------
    def _wait_frame(self, until_now):
        """Block (polling) until a frame exists AND loop-time >= until_now, or stop."""
        while not self._stop.is_set():
            f, now = self._latest()
            if f is not None and now >= until_now:
                return f, now
            self._stop.wait(0.02)
        return None, None

    def _seed_box(self, frame):
        """Grounding OR oracle designation -> the seed box. In oracle_gt mode the box is the
        operator's stashed target GT (no VLM call, no acquire cost in the idle window)."""
        if self.oracle_gt:
            with self._flock:
                gt = self._gt
            return None if gt is None else tuple(float(v) for v in gt)
        return self.acquire_fn(frame, self.w, self.h)

    def _seed_warm(self):
        f, _ = self._wait_frame(self.warm_seed_at)
        if f is None:
            return None
        t0 = time.time()
        box = self._seed_box(f)                        # FREE: pre-prompt idle compute
        self.info["acquire_s"] = time.time() - t0
        if box is None:
            self.info["grounded_out_of_scope"] = True
            return None
        self.info.update(seeded=True, seed_box=[round(float(v), 1) for v in box])
        self._cur_box = box
        return self.carry_factory(_rgb(f), box)

    def _seed_cold(self):
        f, _ = self._wait_frame(self.t_prompt)        # wait for the operator's command
        if f is None:
            return None
        t0 = time.time()
        box = self._seed_box(f)                        # BLOCKING at prompt; copter hovers
        if self.oracle_gt:
            self._stop.wait(self.cold_latency_s)       # model the ~4.85 s acquire wall-clock
        self.info["acquire_s"] = time.time() - t0
        f2, now2 = self._latest()                     # frame AFTER the ~4.85 s wait
        if box is None or f2 is None:
            self.info["grounded_out_of_scope"] = box is None
            return None
        self.info.update(seeded=True, seed_box=[round(float(v), 1) for v in box])
        self._cur_box = box
        self._deliver(box, now2)                      # STALE box, delivered late
        return self.carry_factory(_rgb(f2), box)      # seed on arrival frame w/ stale box

    def _worker(self):
        carry = self._seed_warm() if self.mode == "warm" else self._seed_cold()
        if carry is None:
            return                                     # no track: copter never gets a box
        while not self._stop.is_set():                 # rate-capped carry loop
            t = time.time()
            f, now = self._latest()
            if f is not None:
                box = carry.step(_rgb(f))
                if box is not None:
                    self._cur_box = box
                # WARM follows from the seed (idle) so the copter is ON-target at the prompt;
                # COLD's carry only exists post-prompt, so it also only delivers then.
                if self._cur_box is not None and (self.mode == "warm" or now >= self.t_prompt):
                    self._deliver(self._cur_box, now)
            dt = self.period - (time.time() - t)
            if dt > 0:
                self._stop.wait(dt)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=10.0)


# --------------------------------------------------------------------------
# selftest: the WARM/COLD state machine + timing, with fake acquire + fake carry
# (no Jetson, no SAM2, no CUDA). Drives the producer with a synthetic frame stream.
# --------------------------------------------------------------------------
def _selftest():
    import numpy as np

    class _FakeSlot:
        def __init__(self):
            self.writes = []
            self._lock = threading.Lock()
        def write(self, ts, bbox, vlm_ms=0.0, raw_text=""):
            with self._lock:
                self.writes.append((ts, bbox, raw_text))
            return True

    class _FakeCarry:
        """step returns a box that creeps +1px/step, so 'maintained' is observable."""
        def __init__(self, frame_rgb, box):
            self.box = list(box)
        def step(self, frame_rgb):
            self.box = [v + 1.0 for v in self.box]
            return tuple(self.box)

    FAKE_LAT = 0.3            # stand-in for the ~4.85 s Jetson acquire
    W, H = 640, 480

    def fake_acquire(frame_bgr, w, h):
        time.sleep(FAKE_LAT)                 # the acquire costs wall-clock, as the real one does
        return (300.0, 220.0, 320.0, 260.0)  # a plausible centered box

    def run(mode, t_prompt, total_s, oracle_gt=False, gt_box=None, cold_latency_s=0.3):
        slot = _FakeSlot()
        p = WarmColdProducer(slot, fake_acquire, _FakeCarry, mode=mode, t_prompt=t_prompt,
                             w=W, h=H, warm_seed_at=0.05, carry_hz=20.0,
                             oracle_gt=oracle_gt, cold_latency_s=cold_latency_s)
        t0 = time.time()
        frame = np.zeros((H, W, 3), np.uint8)
        while time.time() - t0 < total_s:            # drive the loop at ~50 Hz
            p.step(frame, gt_box, time.time() - t0)
            time.sleep(0.02)
        p.close()
        return slot.writes, p.info

    # WARM: seeds in the idle window and FOLLOWS from there -> first delivery is pre-prompt,
    # and it keeps delivering past the prompt (the copter is on-target when the command lands).
    writes, info = run("warm", t_prompt=0.6, total_s=1.2)
    assert info["seeded"], info
    assert writes, "WARM never delivered"
    first_deliver = writes[0][0]
    assert first_deliver < 0.6, f"WARM should follow during idle (deliver pre-prompt), got {first_deliver:.3f}"
    assert any(t >= 0.6 for t, _, _ in writes), "WARM must keep delivering past the prompt"
    assert info["acquire_s"] < 0.6, "WARM acquire must fit inside the idle window"

    # ORACLE WARM: seed box IS the designation (no acquire cost), carry maintains it.
    writes, info = run("warm", t_prompt=0.6, total_s=1.2, oracle_gt=True,
                       gt_box=(300.0, 220.0, 320.0, 260.0))
    assert info["seeded"] and info["seed_box"][0] == 300.0, info
    assert info["acquire_s"] < 0.05, f"oracle warm must not pay an acquire cost, got {info['acquire_s']}"

    # COLD: nothing until the prompt, then delivery is LATE by ~FAKE_LAT (stale).
    writes, info = run("cold", t_prompt=0.3, total_s=1.4)
    assert info["seeded"], info
    assert writes, "COLD never delivered"
    first_deliver = writes[0][0]
    assert first_deliver >= 0.3 + FAKE_LAT - 0.05, \
        f"COLD must not deliver before prompt+acquire, got {first_deliver:.3f}"
    assert abs(first_deliver - (0.3 + FAKE_LAT)) < 0.2, \
        f"COLD delivery should be ~prompt+acquire, got {first_deliver:.3f}"
    assert 0.2 < info["acquire_s"] < 0.6, info["acquire_s"]

    # out-of-scope grounding: no box -> no track -> no delivery, no crash.
    def none_acquire(frame_bgr, w, h):
        time.sleep(0.05)
        return None
    slot = _FakeSlot()
    p = WarmColdProducer(slot, none_acquire, _FakeCarry, mode="warm", t_prompt=0.2,
                         w=W, h=H, warm_seed_at=0.02, carry_hz=20.0)
    t0 = time.time()
    frame = np.zeros((H, W, 3), np.uint8)
    while time.time() - t0 < 0.5:
        p.step(frame, None, time.time() - t0)
        time.sleep(0.02)
    p.close()
    assert not slot.writes, "out-of-scope grounding must deliver nothing"
    assert p.info["grounded_out_of_scope"], p.info

    print("selftest OK")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print("run with --selftest (this module has no CLI; it is wired into run_p62_flight)")
