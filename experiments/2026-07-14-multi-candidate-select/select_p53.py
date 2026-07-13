"""P5.3 multi-candidate select-on-command harness (Part V).

Fork of experiments/2026-07-04-warm-start-acquire/replay_e24.py (imported, not
copied). P5.1/P5.2 proved warm-start acquire with ONE dominant target -- the
"select" stage was trivially satisfied. P5.3 tests the untested stage: TWO
same-class candidates are warm-carried through the idle window; the operator's
phrase must pick the right one.

Method: LATE-BINDING SELECT. At the prompt, the deployed phrase-grounding VLM
(Qwen2-VL-2B q8_0 terse, the Part II RefDrone fine-tune -- referring expressions
with distractors are in its training lineage) fires on the prompt frame. Its box
lands ~4.5 s later, stale as a raw box -- but instead of USING it we MATCH it by
IoU against the candidates' carried boxes AT THE SUBMIT FRAME (the frame the VLM
actually saw), then deliver the matched TRACK's CURRENT box. Track identity
survives the VLM latency even though the raw box does not.

Legs (one scene = clip + f0 + t_p + target/distractor captions + seed boxes):

  WSEL : two carries seeded at f0 (target from GT[f0] -- oracle seed, a recorded
         scope cut mirroring P5.1; distractor from a hand-annotated box), idle
         catch-up f0..prompt at CARRY_HZ/2 per candidate (two tracks share the
         6.15 Hz SAM2 budget), VLM fired with the TARGET caption at the prompt,
         realtime bridge over the acquire latency (frames drop, both carries
         alternate at CARRY_HZ/2 each), IoU-match at delivery, deliver the
         selected track's current box, then 10 s realtime coverage on the
         selected carry alone (full CARRY_HZ -- the loser is dropped).
         REGROUND off (v1: isolate the select mechanism).
  SWAP : identical, but the VLM is fired with the DISTRACTOR caption. Negative
         control: proves the phrase (not seed order or track quality) drives the
         selection. Scored with target-only GT: PASS = distractor selected AND
         delivered box IoU vs target GT < 0.25.
  CSEL : deployed cold baseline = replay_e24 COLD with an f0 offset. VLM fires
         at the prompt with the target caption, raw box delivered STALE at
         prompt + measured acquire, carry seeds there, REGROUND on (mask gate).

Fairness: WSEL/SWAP and CSEL all deliver at the SAME frame (prompt + measured
acquire) -- unlike P5.1 the warm legs get no earlier delivery. The only
difference is WHAT is delivered: a live track's current box vs a stale raw box.
That isolates the late-binding claim from the delivery-lag claim already proven
in P5.1/P5.2.

Match rule: argmax IoU(vlm_box, candidate box at submit frame); NO_MATCH if the
max is < MATCH_FLOOR (0.10) -- e.g. the VLM boxed a third, uncarried object.
NO_MATCH delivers nothing (honest failure; in deployment it would fall back to
cold acquire).

Scoring: e24_score (unchanged) vs the annotated target's GT. GT exists ONLY for
the target -- selection correctness comes from the match rule (which candidate
track won), never from distractor GT.

    .venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py \
        --matrix experiments/2026-07-14-multi-candidate-select/scenes.json --out runs
    .venv-ft/bin/python experiments/2026-07-14-multi-candidate-select/select_p53.py \
        --matrix .../scenes.json --only car9:300 --legs WSEL --out runs
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
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import WallClockVideo, iou, load_uav123_gt  # noqa: E402
from warmstart import window                                    # noqa: E402
from replay_e24 import (                                         # noqa: E402
    APP_TAU, CARRY_HZ, LOSS_S, MAX_SIDE, NOMINAL_ACQUIRE,
    MaskGate, _rgb, _valid, coverage_realtime, e24_score, vlm_acquire,
)

CAND_HZ = CARRY_HZ / 2.0   # two candidates share the 6.15 Hz SAM2 budget
MATCH_FLOOR = 0.10         # argmax IoU below this -> NO_MATCH (uncarried object)
LEGS = ("WSEL", "SWAP", "CSEL")


def idle_catchup_multi(carries: dict, frame_at, seed_frame: int,
                       prompt_frame: int, fps: float) -> dict:
    """Free-compute idle window, two candidates: step each carry (seeded at
    seed_frame) through the buffered frames to prompt_frame, NON-REALTIME, at
    the per-candidate cadence CAND_HZ (stride = fps/CAND_HZ). Always lands
    exactly on prompt_frame. Returns {name: box_at_prompt | None}."""
    stride = max(1, round(fps / CAND_HZ))
    out = {}
    for name, carry in carries.items():
        steps = list(range(seed_frame + stride, prompt_frame, stride))
        if not steps or steps[-1] != prompt_frame:
            steps.append(prompt_frame)
        box = None
        for f in steps:
            frame = frame_at(f)
            _, b = carry.step(_rgb(frame))
            if _valid(b, frame.shape):
                box = b
        out[name] = box
    return out


def bridge_realtime(carries: dict, seq_dir, fps: float, start_frame: int,
                    end_frame: int, *, now=time.monotonic, sleep=time.sleep) -> dict:
    """REALTIME carry over the acquire latency [start_frame, end_frame): the
    operator has spoken, the VLM is thinking, frames DROP while the two carries
    alternate steps -- each step budgeted 1/CARRY_HZ so each candidate runs at
    CAND_HZ. Returns {name: last valid box in the bridge | None}."""
    video = WallClockVideo(seq_dir, fps=fps, now=now)
    video.start()
    video._t0 = now() - start_frame / fps
    boxes = {k: None for k in carries}
    names = list(carries)
    turn = 0
    while (grab := video.latest()) is not None:
        i, frame = grab
        if i >= end_frame:
            break
        t0 = now()
        name = names[turn % len(names)]
        turn += 1
        _, b = carries[name].step(_rgb(frame))
        if _valid(b, frame.shape):
            boxes[name] = b
        dt = 1.0 / CARRY_HZ - (now() - t0)
        if dt > 0:
            sleep(dt)
    return boxes


def run_leg_p53(leg, scene, gt, frame_at, submit, make_carry, gate, *,
                cover_s, fps, frame_shape, now=time.monotonic,
                sleep=time.sleep, seq_dir=None):
    """Run one P5.3 leg. Returns (events, score, meta). submit(frame, caption)
    is injectable (stubbed in --selfcheck). Frame arithmetic: prompt =
    f0 + round(t_p*fps); deliver = prompt + round(measured_acquire*fps) for ALL
    legs (late binding pays the same VLM latency as cold)."""
    f0, t_p = scene["f0"], scene["t_p"]
    clip_len = len(gt)
    prompt = f0 + round(t_p * fps)
    cover_frames = round(cover_s * fps)
    meta = {"leg": leg, "f0": f0, "t_p": t_p, "prompt_frame": prompt}

    def fail(reason, deliver=None, acquire_s=None):
        return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                    "deliver_frame": deliver, "selection": None,
                    "selection_correct": False, "reason": reason,
                    "leg": leg}, {**meta, "acquire_s": acquire_s}

    if leg in ("WSEL", "SWAP"):
        seed_t = gt[f0]
        assert seed_t is not None, f"scene f0={f0} needs valid target GT"
        seed_d = scene["distractor_box"]
        carries = {
            "target": make_carry(_rgb(frame_at(f0)), seed_t),
            "distractor": make_carry(_rgb(frame_at(f0)), tuple(seed_d)),
        }
        cand_at_prompt = idle_catchup_multi(carries, frame_at, f0, prompt, fps)

        caption = (scene["target_caption"] if leg == "WSEL"
                   else scene["distractor_caption"])
        t0 = now()
        vbox = submit(frame_at(prompt), caption)
        acquire_s = now() - t0
        deliver = prompt + round(acquire_s * fps)
        meta.update({"acquire_s": round(acquire_s, 2), "caption": caption,
                     "cand_at_prompt": {k: (None if b is None else
                                            [round(v, 1) for v in b])
                                        for k, b in cand_at_prompt.items()}})
        if deliver >= clip_len:
            return fail("deliver past clip end", deliver, round(acquire_s, 2))

        # both carries stay live (realtime, frames drop) while the VLM thinks
        cur = bridge_realtime(carries, seq_dir, fps, prompt, deliver,
                              now=now, sleep=sleep)

        if not _valid(vbox, frame_shape):
            return fail("acquire returned no box", deliver, round(acquire_s, 2))
        match_ious = {k: (iou(vbox, b) if b is not None else 0.0)
                      for k, b in cand_at_prompt.items()}
        selected = max(match_ious, key=match_ious.get)
        if match_ious[selected] < MATCH_FLOOR:
            selected = None
        meta.update({"vlm_box": [round(v, 1) for v in vbox],
                     "match_ious": {k: round(v, 4) for k, v in match_ious.items()},
                     "selected": selected})
        if selected is None:
            return fail("NO_MATCH: vlm box overlaps no carried candidate "
                        f"(max IoU {max(match_ious.values()):.3f} < {MATCH_FLOOR})",
                        deliver, round(acquire_s, 2))

        delivered_box = cur[selected] if cur[selected] is not None \
            else cand_at_prompt[selected]
        if delivered_box is None:
            return fail("selected track lost during idle+bridge",
                        deliver, round(acquire_s, 2))
        events = [(deliver / fps, tuple(delivered_box))]
        # loser dropped: the selected carry gets the full CARRY_HZ budget.
        # REGROUND off (v1 isolates the select mechanism, like E18-B/ORACLE).
        events += coverage_realtime(
            carries[selected], seq_dir, frame_at, gt, fps, deliver,
            window(deliver, cover_frames, clip_len)[1],
            reground=False, gate=None, submit=lambda f: None,
            make_carry=make_carry, now=now, sleep=sleep)
        want = "target" if leg == "WSEL" else "distractor"
        score = e24_score(events, gt, fps, deliver, cover_frames)
        score.update({"leg": leg, "selection": selected,
                      "selection_correct": selected == want,
                      "acquire_s": round(acquire_s, 2)})
        meta["deliver_frame"] = deliver
        return events, score, meta

    if leg == "CSEL":
        # replay_e24 COLD with an f0 offset: raw stale box, seed at arrival.
        t0 = now()
        vbox = submit(frame_at(prompt), scene["target_caption"])
        acquire_s = now() - t0
        deliver = prompt + round(acquire_s * fps)
        meta.update({"acquire_s": round(acquire_s, 2),
                     "caption": scene["target_caption"]})
        if not _valid(vbox, frame_shape):
            return fail("acquire returned no box", deliver, round(acquire_s, 2))
        if deliver >= clip_len:
            return fail("deliver past clip end", deliver, round(acquire_s, 2))
        carry = make_carry(_rgb(frame_at(deliver)), vbox)
        if gate is not None:
            gate.bind(frame_at(deliver), carry.init_mask)
        events = [(deliver / fps, tuple(vbox))]        # the stale raw box
        events += coverage_realtime(
            carry, seq_dir, frame_at, gt, fps, deliver,
            window(deliver, cover_frames, clip_len)[1],
            reground=True, gate=gate,
            submit=lambda f: submit(f, scene["target_caption"]),
            make_carry=make_carry, now=now, sleep=sleep)
        score = e24_score(events, gt, fps, deliver, cover_frames)
        score.update({"leg": leg, "selection": None, "selection_correct": None,
                      "acquire_s": round(acquire_s, 2)})
        meta.update({"deliver_frame": deliver,
                     "vlm_box": [round(v, 1) for v in vbox]})
        return events, score, meta

    raise ValueError(leg)


def leg_pass(leg: str, score: dict) -> bool:
    """Mechanical per-run PASS rule (mirrors the pre-registered README)."""
    if leg == "WSEL":
        return (score.get("selection_correct") is True
                and score["genuine_lock"] and score["coverage"] >= 0.5)
    if leg == "SWAP":
        # target-only GT: distractor selected AND delivered box NOT on target
        return (score.get("selection") == "distractor"
                and score.get("deliver_iou", 1.0) < 0.25
                and score.get("reason") is None)
    if leg == "CSEL":
        return bool(score["genuine_lock"])
    raise ValueError(leg)


def render_overlay_slice(seq_dir, events, gt, fps, out_path, start, end,
                         distractor_box=None, f0=None) -> None:
    """Overlay for frames [start, end): held/delivered box green, target GT red,
    distractor seed (drawn at f0 only) blue. Absolute frame index in the label."""
    paths = sorted(Path(seq_dir).glob("*.jpg"))[start:end]
    ev = sorted(events, key=lambda e: e[0])
    h, w = cv2.imread(str(paths[0])).shape[:2]
    vw = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"),
                         fps, (w, h))
    j, held = 0, None
    for k, p in enumerate(paths):
        i = start + k
        t = i / fps
        while j < len(ev) and ev[j][0] <= t:
            held = ev[j][1]
            j += 1
        frame = cv2.imread(str(p))
        if i < len(gt) and gt[i] is not None:
            g = [int(v) for v in gt[i]]
            cv2.rectangle(frame, (g[0], g[1]), (g[2], g[3]), (0, 0, 220), 2)
        if distractor_box is not None and f0 is not None and i == f0:
            d = [int(v) for v in distractor_box]
            cv2.rectangle(frame, (d[0], d[1]), (d[2], d[3]), (220, 80, 0), 2)
        if held is not None:
            b = [int(v) for v in held]
            cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), (40, 200, 80), 2)
        lab = "no box yet" if held is None else "DELIVERED"
        cv2.putText(frame, f"{lab} f={i} (green=held red=targetGT)", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)
        vw.write(frame)
    vw.release()


def run_matrix_scene(leg, scene, out_dir: Path, *, cover_s=10.0, fps=30.0,
                     overlay=True):
    """One real-stack run: Jetson q8_0 acquire over SSH, SAM2 carry local
    (rate-capped to the on-Orin budget), scored, snapshotted."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    data = E18 / "data" / "UAV123"
    seq_dir = data / "data_seq" / "UAV123" / scene["clip"]
    gt = load_uav123_gt(data / "anno" / "UAV123" / f"{scene['clip']}.txt")
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(seq_dir.glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]
    frame_shape = (h0, w0, 3)

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    print(f"[P5.3 {leg} {scene['clip']}:{scene['f0']}] booting Jetson q8_0...",
          flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit(frame_bgr, caption):
        path = f"/dev/shm/p53_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, frame_bgr)
        try:
            return vlm_acquire(be, path, caption, w0, h0)
        finally:
            Path(path).unlink(missing_ok=True)

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    gate = MaskGate(predictor) if leg == "CSEL" else None

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, score, meta = run_leg_p53(
                leg, scene, gt, frame_at, submit, make_carry, gate,
                cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                seq_dir=str(seq_dir))
    finally:
        be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = leg_pass(leg, score)
    result = {
        "leg": leg, "scene": scene, "cover_s": cover_s, "fps": fps,
        "wall_s": round(wall, 1), "cap_hz": CARRY_HZ, "cand_hz": CAND_HZ,
        "match_floor": MATCH_FLOOR, "app_tau": APP_TAU, "loss_s": LOSS_S,
        "n_gate_reject": gate.n_reject if gate else 0,
        "pass": ok, "score": score, "meta": meta,
        "events": [(round(t, 3), None if b is None else
                    [round(v, 1) for v in b]) for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    if overlay and score.get("deliver_frame"):
        end = window(score["deliver_frame"], round(cover_s * fps), len(gt))[1]
        render_overlay_slice(seq_dir, events, gt, fps, out_dir / "overlay.mp4",
                             scene["f0"], end,
                             distractor_box=scene["distractor_box"],
                             f0=scene["f0"])
    print(f"[P5.3 {leg} {scene['clip']}:{scene['f0']}] PASS={ok} "
          f"sel={score.get('selection')} genuine={score['genuine_lock']} "
          f"cov={score['coverage']} deliver_iou={score.get('deliver_iou')} "
          f"acq={score.get('acquire_s')} wall={wall:.0f}s "
          f"reason={score.get('reason')}", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub carries + stub VLM + fake clock. Asserts: f0-offset frame
    arithmetic, phrase-driven selection (WSEL picks target, SWAP picks
    distractor), NO_MATCH floor, CSEL stale-raw-box path, leg_pass rules."""
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 60, 8.0
    boxT = (10.0, 10.0, 30.0, 30.0)
    boxD = (100.0, 100.0, 130.0, 130.0)
    boxX = (170.0, 170.0, 190.0, 190.0)          # uncarried third object
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the white car",
             "distractor_caption": "the black car",
             "distractor_box": list(boxD)}
    prompt = f0 + round(t_p * fps)               # 60 + 240 = 300
    ACQ = 4.85
    deliver = prompt + round(ACQ * fps)          # 300 + 146 = 446

    with tempfile.TemporaryDirectory() as tmp:
        blank = np.full(frame_shape, 100, np.uint8)
        for i in range(clip_len):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", blank)
        frame_at = lambda _i: blank                                  # noqa: E731
        clk = [0.0]
        now = lambda: clk[0]                                         # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)           # noqa: E731

        class StubCarry:
            init_mask = np.ones((200, 200), dtype=bool)

            def __init__(self, box):
                self.box = tuple(box)

            def step(self, _f):
                return None, self.box

        make_carry = lambda _r, b: StubCarry(b)                      # noqa: E731

        answers = {"the white car": boxT, "the black car": boxD}

        def submit(_f, caption):
            clk[0] += ACQ
            return answers[caption]

        # WSEL: phrase names target -> target track selected, PASS
        clk[0] = 0.0
        ev, sc, meta = run_leg_p53("WSEL", scene, gt, frame_at, submit,
                                   make_carry, None, cover_s=cover_s, fps=fps,
                                   frame_shape=frame_shape, now=now,
                                   sleep=sleep, seq_dir=tmp)
        assert meta["prompt_frame"] == prompt and sc["deliver_frame"] == deliver, (meta, sc)
        assert sc["selection"] == "target" and sc["selection_correct"], sc
        assert sc["genuine_lock"] and sc["coverage"] == 1.0, sc
        assert abs(ev[0][0] - deliver / fps) < 1e-6, ev[0]
        assert leg_pass("WSEL", sc), sc

        # SWAP: phrase names distractor -> distractor selected, off-target, PASS
        clk[0] = 0.0
        _, sc, _ = run_leg_p53("SWAP", scene, gt, frame_at, submit,
                               make_carry, None, cover_s=cover_s, fps=fps,
                               frame_shape=frame_shape, now=now,
                               sleep=sleep, seq_dir=tmp)
        assert sc["selection"] == "distractor" and sc["selection_correct"], sc
        assert not sc["genuine_lock"] and sc["deliver_iou"] < 0.25, sc
        assert leg_pass("SWAP", sc), sc

        # NO_MATCH: VLM boxes an uncarried third object -> no delivery, FAIL
        clk[0] = 0.0
        _, sc, _ = run_leg_p53("WSEL", scene, gt, frame_at,
                               lambda _f, _c: (clk.__setitem__(0, clk[0] + ACQ),
                                               boxX)[1],
                               make_carry, None, cover_s=cover_s, fps=fps,
                               frame_shape=frame_shape, now=now,
                               sleep=sleep, seq_dir=tmp)
        assert sc["selection"] is None and "NO_MATCH" in sc["reason"], sc
        assert not leg_pass("WSEL", sc), sc

        # CSEL: stale raw box path, same deliver frame, stub holds GT -> PASS
        clk[0] = 0.0
        gate = MaskGate(predictor=None)          # fail-open, no template
        ev, sc, meta = run_leg_p53("CSEL", scene, gt, frame_at, submit,
                                   make_carry, gate, cover_s=cover_s, fps=fps,
                                   frame_shape=frame_shape, now=now,
                                   sleep=sleep, seq_dir=tmp)
        assert sc["deliver_frame"] == deliver and ev[0][1] == boxT, (sc, ev[0])
        assert sc["genuine_lock"] and leg_pass("CSEL", sc), sc

    # match floor arithmetic
    assert iou(boxT, boxT) == 1.0 and iou(boxT, boxD) == 0.0
    # per-candidate stride at CAND_HZ: 30/3.075 -> every 10th frame
    assert max(1, round(30.0 / CAND_HZ)) == 10
    print("select_p53 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes.json path")
    ap.add_argument("--legs", default="WSEL,SWAP,CSEL")
    ap.add_argument("--only", help="restrict to scene id clip:f0, e.g. car9:300")
    ap.add_argument("--out", default="runs", help="runs dir (under this file's dir)")
    ap.add_argument("--cover-s", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--no-overlay", dest="overlay", action="store_false",
                    default=True)
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return
    if not args.matrix:
        ap.error("need --matrix scenes.json (or --selfcheck)")

    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in LEGS for l in legs), legs
    out_root = HERE / args.out
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        for leg in legs:
            out_dir = out_root / f"{leg}_{scene['clip']}_{scene['f0']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.3] skip {out_dir.name} (results.json exists)")
                continue
            run_matrix_scene(leg, scene, out_dir, cover_s=args.cover_s,
                             fps=args.fps, overlay=args.overlay)


if __name__ == "__main__":
    main()
