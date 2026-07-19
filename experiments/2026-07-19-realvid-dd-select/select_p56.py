"""P5.6 direct-delivery select-on-command harness (Part V).

Builds on select_p53.py and select_p55.py (imported, not copied). Three
consecutive select NOs (P5.3 IoU-match, P5.4 union-ROI crop select, P5.5
idle-maintained match) all failed at the SAME step: the prompt-time full-frame
VLM re-ground + IoU match against the carried boxes. The P5.6 audit of the
P5.5 raw runs shows the carried tracks themselves were fine or fixable:

  - MC_SWAP_car10_240: the carried distractor box at the prompt IS the true
    black car (hand GT IoU ~0.9); the select-time VLM boxed a DIFFERENT dark
    car further up the road. The match step threw away a correct carry.
  - MC_WSEL_car10_615: target carry sat on GT (IoU ~0.97) at the prompt; the
    VLM grounded a different white car -> NO_MATCH. Same story.
  - MC_SWAP_car7_460: the one genuine carry failure (frame-edge junk box).

P5.6 changes the DELIVERY CONTRACT (the one untested lever, per the P5.5
decision entry): the operator phrase binds to a carried candidate by its
stored caption (string equality -- captions are asserted referentially
distinct per scene), and that candidate's carried box at the prompt frame is
delivered DIRECTLY. No prompt-time VLM call, no IoU match, acquire_s = 0.0,
deliver_frame = prompt_frame. The idle-window maintenance is BYTE-IDENTICAL
to P5.5 MC (segmented idle + distractor ROI re-anchor at f0+90/f0+165 via
select_p55.roi_reanchor; accept = parseable + valid, no IoU floor;
single-factor discipline: only the select/delivery step changes).

Scoring changes that keep the test honest without the re-ground:

  - STRENGTHENED SWAP RULE: without NO_MATCH there is no honest fallback --
    any junk box would trivially pass the old "not on target" check. So SWAP
    now ALSO requires the delivered box to be ON the named distractor:
    IoU >= 0.25 vs the hand-annotated distractor GT at the prompt frame
    (scenes_p56.json distractor_gt_prompt, provenance renders in curation/).
    The old weak rule is still computed (swap_weak_pass) as a NON-GATING
    column to quantify how much the old rule flattered.
  - SHADOW RE-GROUND (non-gating diagnostic): after coverage finishes, the
    P5.5-style full-frame VLM call fires at the prompt frame and its
    match-IoUs vs the carried boxes are recorded (meta["shadow"]) -- what the
    old contract WOULD have done, for cell-by-cell attribution at zero cost
    to the gating path.

    .venv-ft/bin/python experiments/2026-07-14-direct-delivery-select/select_p56.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-14-direct-delivery-select/select_p56.py \
        --matrix experiments/2026-07-14-direct-delivery-select/scenes_p56.json --out runs
    .venv-ft/bin/python ... --only car9:560 --legs SWAP --out runs
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
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
P53 = REPO / "experiments" / "2026-07-14-multi-candidate-select"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, P55, P53, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import iou, load_uav123_gt                     # noqa: E402
from warmstart import window                                      # noqa: E402
from replay_e24 import (                                          # noqa: E402
    APP_TAU, CARRY_HZ, LOSS_S, MAX_SIDE, _rgb, _valid,
    coverage_realtime, e24_score, vlm_acquire,
)
from select_p53 import (                                          # noqa: E402
    CAND_HZ, MATCH_FLOOR, idle_catchup_multi, render_overlay_slice,
)
from select_p55 import (                                          # noqa: E402
    REANCHOR_OFFSETS, ROI_MARGIN, ROI_MIN_SIDE, ROI_RES, roi_reanchor,
)

DIST_FLOOR = 0.25   # strengthened SWAP: delivered box IoU vs distractor hand
                    # GT at the prompt frame must clear this (same threshold
                    # family as every lock/coverage rule in Parts IV-V)
LEGS = ("WSEL", "SWAP")


def bind_by_caption(phrase: str, scene: dict) -> str:
    """The P5.6 delivery contract's binding step: the operator phrase is
    matched against the candidates' STORED captions (string equality). In
    deployment this would be free-text matching; here the phrase IS one of
    the stored captions by construction, so binding is exact -- the
    experiment isolates the delivery mechanism, not phrase understanding
    (scope cut recorded in the README). Captions must be referentially
    distinct or the contract is ill-posed."""
    caps = {"target": scene["target_caption"],
            "distractor": scene["distractor_caption"]}
    assert caps["target"] != caps["distractor"], \
        f"ill-posed scene: identical captions {caps}"
    matches = [k for k, c in caps.items() if c == phrase]
    assert len(matches) == 1, (phrase, caps)
    return matches[0]


def run_leg_p56(leg, scene, gt, frame_at, submit_img, make_carry, *,
                cover_s, fps, frame_shape, now=time.monotonic,
                sleep=time.sleep, seq_dir=None, shadow=True):
    """One P5.6 leg (WSEL|SWAP). Idle window IDENTICAL to select_p55.
    run_leg_p55 (segmented idle + distractor ROI re-anchor at f0+90/f0+165);
    then the select step is replaced by direct delivery: bind the phrase to a
    carried candidate by caption equality and deliver that candidate's box at
    the prompt frame (acquire_s=0.0, deliver=prompt, no VLM, no IoU match,
    no realtime bridge -- there is no latency to bridge). submit_img is still
    used by the re-anchor rounds and the post-coverage shadow re-ground."""
    f0, t_p = scene["f0"], scene["t_p"]
    clip_len = len(gt)
    prompt = f0 + round(t_p * fps)
    cover_frames = round(cover_s * fps)
    meta = {"leg": leg, "f0": f0, "t_p": t_p, "prompt_frame": prompt,
            "reanchor": []}

    def fail(reason, deliver=None):
        return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                    "deliver_frame": deliver, "selection": None,
                    "selection_correct": False, "reason": reason,
                    "leg": leg}, {**meta, "acquire_s": 0.0}

    seed_t = gt[f0]
    assert seed_t is not None, f"scene f0={f0} needs valid target GT"
    seed_d = scene["distractor_box"]
    carries = {
        "target": make_carry(_rgb(frame_at(f0)), seed_t),
        "distractor": make_carry(_rgb(frame_at(f0)), tuple(seed_d)),
    }

    # --- idle window: byte-identical to run_leg_p55 (P5.5 MC maintenance) ---
    cur_d = tuple(seed_d)
    seg_start = f0
    boundaries = [f0 + off for off in REANCHOR_OFFSETS if f0 + off < prompt]
    for b in boundaries:
        cand = idle_catchup_multi(carries, frame_at, seg_start, b, fps)
        if cand.get("distractor") is not None:
            cur_d = cand["distractor"]
        frame_b = frame_at(b)
        new_box, dbg = roi_reanchor(frame_b, cur_d,
                                    scene["distractor_caption"], submit_img)
        accepted = new_box is not None
        if accepted:
            carries["distractor"] = make_carry(_rgb(frame_b), new_box)
            cur_d = new_box
        meta["reanchor"].append({
            "frame": b, **dbg, "accepted": accepted,
            "new_box": None if new_box is None
            else [round(v, 1) for v in new_box]})
        seg_start = b
    cand_at_prompt = idle_catchup_multi(carries, frame_at, seg_start,
                                        prompt, fps)

    # --- P5.6 delivery contract: bind by caption, deliver the carried box ---
    phrase = (scene["target_caption"] if leg == "WSEL"
              else scene["distractor_caption"])
    selected = bind_by_caption(phrase, scene)
    deliver = prompt                       # acquire_s = 0.0 by construction
    meta.update({"acquire_s": 0.0, "caption": phrase, "selected": selected,
                 "cand_at_prompt": {k: (None if b is None else
                                        [round(v, 1) for v in b])
                                    for k, b in cand_at_prompt.items()}})
    if deliver >= clip_len:
        return fail("deliver past clip end", deliver)
    delivered_box = cand_at_prompt[selected]
    if delivered_box is None:
        return fail("selected track lost during idle", deliver)

    events = [(deliver / fps, tuple(delivered_box))]
    # loser dropped: the selected carry gets the full CARRY_HZ budget.
    events += coverage_realtime(
        carries[selected], seq_dir, frame_at, gt, fps, deliver,
        window(deliver, cover_frames, clip_len)[1],
        reground=False, gate=None, submit=lambda f: None,
        make_carry=make_carry, now=now, sleep=sleep)
    want = "target" if leg == "WSEL" else "distractor"
    score = e24_score(events, gt, fps, deliver, cover_frames)
    score.update({"leg": leg, "selection": selected,
                  "selection_correct": selected == want,
                  "acquire_s": 0.0})
    dg = scene.get("distractor_gt_prompt")
    score["deliver_iou_distractor"] = (
        round(iou(delivered_box, tuple(dg)), 4) if dg else None)
    meta["deliver_frame"] = deliver

    # --- shadow re-ground (non-gating diagnostic, after coverage) -----------
    if shadow:
        t0 = now()
        svbox = submit_img(frame_at(prompt), phrase)
        shadow_s = now() - t0
        sh = {"acquire_s": round(shadow_s, 2),
              "vlm_box": None if not _valid(svbox, frame_shape)
              else [round(v, 1) for v in svbox]}
        if sh["vlm_box"] is not None:
            mi = {k: (iou(svbox, b) if b is not None else 0.0)
                  for k, b in cand_at_prompt.items()}
            ssel = max(mi, key=mi.get)
            if mi[ssel] < MATCH_FLOOR:
                ssel = None
            sh.update({"match_ious": {k: round(v, 4) for k, v in mi.items()},
                       "selected": ssel})
        else:
            sh.update({"match_ious": None, "selected": None})
        meta["shadow"] = sh
    return events, score, meta


def leg_pass_p56(leg: str, score: dict) -> bool:
    """Mechanical per-run PASS rule (mirrors the pre-registered README).
    WSEL unchanged from P5.3/P5.5; SWAP strengthened: the delivered box must
    be ON the named distractor (hand GT), not merely off the target."""
    if leg == "WSEL":
        return (score.get("selection_correct") is True
                and score["genuine_lock"] and score["coverage"] >= 0.5)
    if leg == "SWAP":
        return (score.get("selection") == "distractor"
                and score.get("deliver_iou", 1.0) < 0.25
                and (score.get("deliver_iou_distractor") or 0.0) >= DIST_FLOOR
                and score.get("reason") is None)
    raise ValueError(leg)


def swap_weak_pass(score: dict) -> bool:
    """The OLD P5.3/P5.5 SWAP rule (off-target only) -- computed non-gating
    to show how much it flatters under direct delivery, where a junk box
    would trivially satisfy it."""
    return (score.get("selection") == "distractor"
            and score.get("deliver_iou", 1.0) < 0.25
            and score.get("reason") is None)


def run_matrix_scene(leg, scene, out_dir: Path, *, cover_s=10.0, fps=30.0,
                     overlay=True):
    """One real-stack run: Jetson q8_0 over SSH (ROI re-anchor crops + the
    shadow re-ground only -- the gating delivery path makes NO VLM call),
    SAM2 carry local (rate-capped to the on-Orin budget), scored,
    snapshotted under DD_<LEG>_<clip>_<f0>/."""
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
    print(f"[P5.6 DD {leg} {scene['clip']}:{scene['f0']}] booting Jetson "
          "q8_0...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_img(img_bgr, caption):
        # Grounds on the image AS GIVEN (crop or full frame): a 512 crop is
        # below the backend's max_side=1024 so it is fed unresized, matching
        # the deployed ROI convention.
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/p56_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img_bgr)
        try:
            return vlm_acquire(be, path, caption, w, h)
        finally:
            Path(path).unlink(missing_ok=True)

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, score, meta = run_leg_p56(
                leg, scene, gt, frame_at, submit_img, make_carry,
                cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                seq_dir=str(seq_dir))
    finally:
        be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = leg_pass_p56(leg, score)
    result = {
        "arm": "DD", "leg": leg, "scene": scene, "cover_s": cover_s,
        "fps": fps, "wall_s": round(wall, 1), "cap_hz": CARRY_HZ,
        "cand_hz": CAND_HZ, "match_floor": MATCH_FLOOR,
        "dist_floor": DIST_FLOOR, "app_tau": APP_TAU, "loss_s": LOSS_S,
        "roi_margin": ROI_MARGIN, "roi_min_side": ROI_MIN_SIDE,
        "roi_res": ROI_RES, "reanchor_offsets": list(REANCHOR_OFFSETS),
        "pass": ok,
        "swap_weak_pass": swap_weak_pass(score) if leg == "SWAP" else None,
        "score": score, "meta": meta,
        "events": [(round(t, 3), None if b is None else
                    [round(v, 1) for v in b]) for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    if overlay and score.get("deliver_frame"):
        end = window(score["deliver_frame"], round(cover_s * fps), len(gt))[1]
        # WSEL: draw the distractor SEED at f0 (P5.5 convention). SWAP: draw
        # the hand-annotated distractor GT at the PROMPT frame instead -- the
        # box the strengthened rule scores against, visible where it matters.
        if leg == "SWAP" and scene.get("distractor_gt_prompt"):
            dbox, dfr = scene["distractor_gt_prompt"], meta["prompt_frame"]
        else:
            dbox, dfr = scene["distractor_box"], scene["f0"]
        render_overlay_slice(seq_dir, events, gt, fps, out_dir / "overlay.mp4",
                             scene["f0"], end, distractor_box=dbox, f0=dfr)
    print(f"[P5.6 DD {leg} {scene['clip']}:{scene['f0']}] PASS={ok} "
          f"sel={score.get('selection')} genuine={score['genuine_lock']} "
          f"cov={score['coverage']} deliver_iou={score.get('deliver_iou')} "
          f"iou_dist={score.get('deliver_iou_distractor')} "
          f"weak={result['swap_weak_pass']} "
          f"shadow_sel={(meta.get('shadow') or {}).get('selected')} "
          f"reanchor={[r['accepted'] for r in meta.get('reanchor', [])]} "
          f"wall={wall:.0f}s reason={score.get('reason')}", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub carries + stub VLM + fake clock. Asserts, beyond the P5.3+P5.5
    suites (which still run at the end): (1) delivery contract: acquire_s=0.0,
    deliver_frame=prompt_frame, no full-frame VLM call on the gating path;
    (2) maintenance unchanged: re-anchor rounds fire at f0+90/f0+165 exactly
    as in P5.5; (3) HONESTY: a junk delivered box (off target AND off
    distractor GT) PASSES the old weak SWAP rule but FAILS the strengthened
    one; (4) a delivered box on the distractor GT passes the strengthened
    rule; (5) shadow re-ground recorded with match-IoUs and does not affect
    the verdict; (6) lost-track and identical-caption guard paths."""
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 60, 8.0
    boxT = (10.0, 10.0, 30.0, 30.0)
    boxD = (100.0, 100.0, 130.0, 130.0)
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the white car",
             "distractor_caption": "the black car",
             "distractor_box": list(boxD),
             "distractor_gt_prompt": list(boxD)}   # stationary distractor
    prompt = f0 + round(t_p * fps)
    ACQ = 4.85   # stub full-frame VLM latency (shadow path only)

    from grounding.contract import COORD_SCALE
    from grounding.roi import roi_window

    with tempfile.TemporaryDirectory() as tmp:
        blank = np.full(frame_shape, 100, np.uint8)
        for i in range(clip_len):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", blank)
        frame_at = lambda _i: blank                                  # noqa: E731
        clk = [0.0]
        now = lambda: clk[0]                                         # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)           # noqa: E731

        class HoldCarry:
            def __init__(self, box):
                self.box = tuple(box)

            def step(self, _f):
                return None, self.box

        drift_next = [False]   # armed per-run: the f0 distractor seed drifts
        seeded = []

        def make_carry(_r, b):
            seeded.append(tuple(round(v, 1) for v in b))
            if drift_next[0] and tuple(b) == boxD:
                drift_next[0] = False
                return HoldCarry((150.0, 150.0, 160.0, 160.0))   # junk corner
            return HoldCarry(b)

        # Stub crop geometry, per round: round 1's prior is the drifted
        # corner box, round 2's prior is boxD (post-reseed), and the two ROI
        # windows differ -- roi_window gives (27,27,200,200) then
        # (0,0,200,200) -- so the crop answer must be mapped with the RIGHT
        # window each call (a fixed-window stub would corrupt round 2's box).
        def crop_answer(prior):
            norm = [v / 200 * COORD_SCALE for v in prior]
            win = roi_window(norm, 200, 200, ROI_MARGIN, min_side=ROI_MIN_SIDE)
            s = ROI_RES / max(win[2] - win[0], win[3] - win[1])
            return ((boxD[0] - win[0]) * s, (boxD[1] - win[1]) * s,
                    (boxD[2] - win[0]) * s, (boxD[3] - win[1]) * s)

        crop_answers = [crop_answer((150, 150, 160, 160)),   # round 1 prior
                        crop_answer(boxD)]                   # round 2 prior
        crop_i = [0]
        full_calls = []

        def submit_fix(img, caption):
            """Re-anchor answers boxD on crops; full-frame (shadow) answers
            per caption after ACQ seconds."""
            h, w = img.shape[:2]
            if (w, h) == (200, 200):
                full_calls.append(caption)
                clk[0] += ACQ
                return {"the white car": boxT, "the black car": boxD}[caption]
            assert caption == "the black car", caption
            ans = crop_answers[crop_i[0]]
            crop_i[0] += 1
            return ans

        def submit_reject(img, caption):
            h, w = img.shape[:2]
            if (w, h) == (200, 200):
                full_calls.append(caption)
                clk[0] += ACQ
                return boxD
            return None                     # re-anchor never accepted

        # (1)+(2)+(4)+(5) SWAP, drifted distractor FIXED by re-anchor:
        # delivered box ~= boxD at the prompt, on the distractor hand GT.
        clk[0] = 0.0
        crop_i[0] = 0
        crop_answers[:] = [crop_answer((150, 150, 160, 160)),  # round 1 prior
                           crop_answer(boxD)]                  # round 2 prior
        seeded.clear(); full_calls.clear(); drift_next[0] = True
        ev, sc, meta = run_leg_p56("SWAP", scene, gt, frame_at, submit_fix,
                                   make_carry, cover_s=cover_s, fps=fps,
                                   frame_shape=frame_shape, now=now,
                                   sleep=sleep, seq_dir=tmp)
        assert sc["acquire_s"] == 0.0 and sc["deliver_frame"] == prompt, sc
        assert [r["frame"] for r in meta["reanchor"]] == [f0 + 90, f0 + 165], meta
        assert all(r["accepted"] for r in meta["reanchor"]), meta
        assert sc["selection"] == "distractor" and sc["selection_correct"], sc
        assert sc["deliver_iou"] < 0.25, sc            # off the target GT
        assert sc["deliver_iou_distractor"] >= DIST_FLOOR, sc
        assert leg_pass_p56("SWAP", sc) and swap_weak_pass(sc), sc
        # gating path made NO full-frame call; the ONE full-frame call is the
        # post-coverage shadow, and it happened after deliver was fixed
        assert full_calls == ["the black car"], full_calls
        assert meta["shadow"]["selected"] == "distractor", meta["shadow"]
        assert meta["shadow"]["acquire_s"] >= ACQ, meta["shadow"]
        assert meta["shadow"]["match_ious"]["distractor"] > 0.9, meta["shadow"]

        # (3) HONESTY: re-anchor rejected -> the drifted junk corner box is
        # delivered. Old weak rule PASSES it (off-target); strengthened rule
        # FAILS it (not on the distractor hand GT either).
        clk[0] = 0.0
        seeded.clear(); full_calls.clear(); drift_next[0] = True
        _, sc, meta = run_leg_p56("SWAP", scene, gt, frame_at, submit_reject,
                                  make_carry, cover_s=cover_s, fps=fps,
                                  frame_shape=frame_shape, now=now,
                                  sleep=sleep, seq_dir=tmp)
        assert [r["accepted"] for r in meta["reanchor"]] == [False, False], meta
        assert sc["selection"] == "distractor" and sc.get("reason") is None, sc
        assert sc["deliver_iou"] < 0.25, sc
        assert sc["deliver_iou_distractor"] == 0.0, sc
        assert swap_weak_pass(sc) and not leg_pass_p56("SWAP", sc), sc

        # WSEL: target carry holds GT -> genuine lock, full coverage,
        # acquire 0, PASS; shadow present and agrees. The undrifted
        # distractor's re-anchor priors are boxD both rounds.
        clk[0] = 0.0
        crop_i[0] = 0
        crop_answers[:] = [crop_answer(boxD), crop_answer(boxD)]
        seeded.clear(); full_calls.clear(); drift_next[0] = False
        _, sc, meta = run_leg_p56("WSEL", scene, gt, frame_at, submit_fix,
                                  make_carry, cover_s=cover_s, fps=fps,
                                  frame_shape=frame_shape, now=now,
                                  sleep=sleep, seq_dir=tmp)
        assert sc["acquire_s"] == 0.0 and sc["deliver_frame"] == prompt, sc
        assert sc["genuine_lock"] and sc["coverage"] == 1.0, sc
        assert sc["selection"] == "target" and sc["selection_correct"], sc
        assert leg_pass_p56("WSEL", sc), sc
        assert full_calls == ["the white car"], full_calls   # shadow only
        assert meta["shadow"]["selected"] == "target", meta["shadow"]

        # (6a) lost track: a carry that never yields a valid box -> clean fail
        class LostCarry:
            def step(self, _f):
                return None, None

        clk[0] = 0.0
        crop_i[0] = 0
        # lost carry never yields a box, so both re-anchor priors stay boxD
        crop_answers[:] = [crop_answer(boxD), crop_answer(boxD)]
        _, sc, _ = run_leg_p56(
            "WSEL", scene, gt, frame_at, submit_fix,
            lambda _r, b: LostCarry(), cover_s=cover_s, fps=fps,
            frame_shape=frame_shape, now=now, sleep=sleep, seq_dir=tmp)
        assert sc["reason"] == "selected track lost during idle", sc
        assert not leg_pass_p56("WSEL", sc), sc

        # (6b) identical captions -> ill-posed contract, hard assert
        bad = dict(scene, distractor_caption=scene["target_caption"])
        try:
            bind_by_caption(bad["target_caption"], bad)
            raise SystemExit("identical-caption guard did not fire")
        except AssertionError:
            pass

    # upstream suites still green (frame arithmetic, re-anchor geometry)
    import select_p55
    select_p55.selfcheck()
    print("select_p56 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes_p56.json path")
    ap.add_argument("--legs", default="WSEL,SWAP")
    ap.add_argument("--only", help="restrict to scene id clip:f0, e.g. car9:560")
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
        ap.error("need --matrix scenes_p56.json (or --selfcheck)")

    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in LEGS for l in legs), legs
    out_root = HERE / args.out
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        for leg in legs:
            out_dir = out_root / f"DD_{leg}_{scene['clip']}_{scene['f0']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.6] skip {out_dir.name} (results.json exists)")
                continue
            run_matrix_scene(leg, scene, out_dir, cover_s=args.cover_s,
                             fps=args.fps, overlay=args.overlay)


if __name__ == "__main__":
    main()
