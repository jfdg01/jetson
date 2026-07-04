"""P5.1 (E24) warm-start frame-schedule contract (Part V).

Pins the frame arithmetic shared by all three legs so the verdict has no
ambiguity. This is the load-bearing bit: staleness bugs hide in "which frame
seeds the carry" and "which frame the operator's box is scored at". The forked
replay imports `schedule()` and `window()`; it does NOT re-derive these.

The three legs, all answering ONE operator command issued at t_p seconds:

    WARM   (the Part V bet): a full-frame VLM acquire fires at t=0 during idle;
           its box (computed from the SUBMIT frame, frame 0) seeds StreamCarry
           on the CACHED frame 0, then carry consumes the buffered frames
           0..prompt_frame in idle (non-realtime -- that is the free compute the
           whole reframe rests on) so it is CURRENT at the prompt. Operator
           SELECTS the carried track at prompt_frame; box scored there (fresh).
    ORACLE (ceiling control): same as WARM but seeded from gt[0] instead of a
           real VLM box -- isolates "is the real detection good enough to seed".
           This is E18 leg B extended to a t_p>0 select.
    COLD   (baseline = deployed behaviour): operator speaks at t_p; a full-frame
           VLM acquire fires THEN; it lands acquire_s later, and the box (from
           submit frame prompt_frame) is delivered STALE at prompt_frame+acquire.
           This is E18 leg A shifted to t_p. Scored at its delivery frame.

Fairness rule: each leg is scored at the frame the operator ACTUALLY RECEIVES a
box (its `deliver_frame`) -- WARM/ORACLE deliver instantly at the prompt, COLD
makes the operator wait acquire_s and hands back a stale box. genuine_lock and
coverage are both measured from the leg's own delivery frame, so the metric is
"quality of the box the operator gets, at the moment they get it, and whether it
holds for cover_s after". That is the deployment-relevant comparison.

    .venv-ft/bin/python .../warmstart.py   # selfcheck
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Legs:
    prompt_frame: int          # frame at which the operator issues the command (t_p)
    warm_seed_frame: int       # WARM/ORACLE seed carry here (cached submit frame)
    warm_deliver_frame: int    # WARM/ORACLE box delivered/scored here (== prompt)
    cold_acquire_start: int    # COLD fires the acquire here (== prompt)
    cold_deliver_frame: int    # COLD stale box delivered/scored here
    cover_frames: int          # coverage window length after any delivery frame
    replay_end_frame: int      # last frame the replay must reach (COLD needs it)


def schedule(t_p: float, acquire_s: float, fps: float = 30.0, cover_s: float = 10.0) -> Legs:
    """Frame plan for one t_p. `acquire_s` is the acquire wall-time: pass the
    NOMINAL ~4.85 s for planning/selfcheck, the MEASURED per-run wall-time at
    runtime so COLD's delivery frame reflects the real staleness."""
    assert t_p > acquire_s, (
        f"t_p ({t_p}s) must exceed acquire_s ({acquire_s}s): otherwise the WARM "
        "acquire has not finished when the operator speaks -- that is a separate "
        "experiment (early prompt / cold fallback), out of scope for E24."
    )
    prompt = round(t_p * fps)
    acq_frames = round(acquire_s * fps)
    cover = round(cover_s * fps)
    cold_deliver = prompt + acq_frames
    return Legs(
        prompt_frame=prompt,
        warm_seed_frame=0,
        warm_deliver_frame=prompt,
        cold_acquire_start=prompt,
        cold_deliver_frame=cold_deliver,
        cover_frames=cover,
        replay_end_frame=cold_deliver + cover,
    )


def window(deliver_frame: int, cover_frames: int, clip_len: int) -> tuple[int, int]:
    """[start, end) frame range for coverage scoring after a delivery frame,
    clamped to the clip. genuine_lock is scored at `deliver_frame` alone; coverage
    is the IoU>=0.25 fraction over this window."""
    start = min(deliver_frame, clip_len - 1)
    end = min(clip_len, deliver_frame + cover_frames)
    return start, end


def selfcheck() -> None:
    # nominal deployed numbers: t_p=8s, acquire ~4.85s, 30 fps, 10s coverage
    L = schedule(8.0, 4.85, fps=30.0, cover_s=10.0)
    assert L.prompt_frame == 240, L
    assert L.warm_seed_frame == 0 and L.warm_deliver_frame == 240, L
    assert L.cold_acquire_start == 240, L
    # 4.85*30 = 145.5 -> round-half-to-even -> 146; cold lands 146 frames stale
    assert L.cold_deliver_frame == 240 + 146 == 386, L
    assert L.cover_frames == 300, L
    assert L.replay_end_frame == 386 + 300 == 686, L

    # WARM delivers 146 frames FRESHER than COLD -- the entire point
    assert L.cold_deliver_frame - L.warm_deliver_frame == 146, L

    # window clamps to clip end
    assert window(240, 300, 1717) == (240, 540)
    assert window(386, 300, 500) == (386, 500)          # clipped tail
    assert window(1400, 300, 1405) == (1400, 1405)      # near end

    # t_p must beat acquire
    try:
        schedule(4.0, 4.85)
    except AssertionError:
        pass
    else:
        raise AssertionError("schedule should reject t_p <= acquire_s")

    print("warmstart selfcheck OK:", L)


if __name__ == "__main__":
    selfcheck()
