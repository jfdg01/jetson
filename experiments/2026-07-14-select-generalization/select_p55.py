"""P5.5 maintained-candidate select-on-command harness (Part V).

Builds on select_p53.py (imported, not copied). The P5.5 audit of P5.3/P5.4
re-diagnosed the select failures: of the 7 non-passing cells, 2 were
DISTRACTOR-CARRY DRIFT (the VLM grounded the phrase correctly but the carried
candidate box had wandered, so the IoU match missed), 1 was genuine phrase
ambiguity, 1 a tiny-box match near-miss, 1 resolution-bound. "match-bound" was
therefore substantially a MAINTENANCE problem, not a grounding problem. P5.5
attacks the two real failure families with deployed components:

  Lever 1 -- IDLE-WINDOW CANDIDATE MAINTENANCE (loop-focus direction 2):
    during the idle window the DISTRACTOR carry is re-anchored by the deployed
    Part III ROI lever (grounding/roi.py, margin 2.0, min_side 256, crop
    long-edge 512): crop around the carry's current box, fire the VLM with the
    distractor caption on the crop, map the box back, RESEED the SAM2 carry
    there. Rounds at f0+90 and f0+165 (both < every scene's prompt). Accept
    rule: parseable + in-frame valid, NO IoU-vs-carry floor -- a drifted carry
    must not veto its own fix. The TARGET carry is never re-anchored
    (GT-oracle-seeded target carries have never drifted in P5.1/P5.3/P5.4;
    single-factor discipline).
    This is NOT the dead union-crop-select lever (P5.4): the ROI here serves
    carry maintenance during idle, not the select-time acquire, which stays
    full-frame exactly as in P5.3.

  Lever 2 -- REFERENTIALLY UNIQUE CAPTIONS (MC arm) on the two cells where the
    P5.3 caption was genuinely ambiguous (car10:240 SWAP near-miss,
    car10:615 WSEL ambiguity); all captions that passed in P5.3 are kept.

Arms:
  MC : maintenance + new captions, all scenes, WSEL+SWAP -- the gating arm.
  M  : maintenance + OLD P5.3 captions, only the caption-changed scenes
       (scenes carrying old_* fields) -- attribution: separates what the
       maintenance lever fixed from what the caption fixed. Non-gating.

Select step at the prompt is UNCHANGED from P5.3 (full-frame VLM, IoU match
against carried boxes at the prompt, MATCH_FLOOR 0.10, realtime bridge,
deliver the matched track's current box, 10 s realtime coverage). The idle
window stays non-realtime (pre-existing recorded convention from P5.1/P5.3);
the deployment-budget note for the two ROI calls is in the README.

    .venv-ft/bin/python experiments/2026-07-14-select-generalization/select_p55.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-14-select-generalization/select_p55.py \
        --matrix experiments/2026-07-14-select-generalization/scenes_p55.json \
        --arm MC --out runs
    .venv-ft/bin/python ... --arm M --out runs        # runs only old_*-bearing scenes
    .venv-ft/bin/python ... --arm MC --only car9:560 --legs WSEL --out runs
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
P53 = REPO / "experiments" / "2026-07-14-multi-candidate-select"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, P53, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import WallClockVideo, iou, load_uav123_gt   # noqa: E402
from warmstart import window                                     # noqa: E402
from replay_e24 import (                                          # noqa: E402
    APP_TAU, CARRY_HZ, LOSS_S, MAX_SIDE, _rgb, _valid,
    coverage_realtime, e24_score, vlm_acquire,
)
from select_p53 import (                                          # noqa: E402
    CAND_HZ, MATCH_FLOOR, bridge_realtime, idle_catchup_multi, leg_pass,
    render_overlay_slice,
)
from grounding.contract import COORD_SCALE                        # noqa: E402
from grounding.roi import roi_window                              # noqa: E402

# ROI re-anchor knobs = the deployed Part III lever (M=2.0 @512 + the min_side
# floor added for the deploy re-anchor loop; see grounding/roi.py docstring).
ROI_MARGIN = 2.0
ROI_MIN_SIDE = 256
ROI_RES = 512
REANCHOR_OFFSETS = (90, 165)   # frames after f0; both < min prompt (f0+180)
ARMS = ("MC", "M")
LEGS = ("WSEL", "SWAP")


def roi_reanchor(frame_bgr, prior_box, caption, submit_img):
    """One distractor re-anchor pass: crop the deployed ROI window around the
    carry's current box, resize long edge to ROI_RES (LANCZOS), fire the VLM
    on the crop, map the box back to full-frame pixels. Returns
    (mapped_box | None, debug_dict). Accept rule = parseable + valid in the
    full frame; deliberately NO IoU floor vs the prior (a drifted prior must
    not veto its own correction)."""
    h, w = frame_bgr.shape[:2]
    norm = [prior_box[0] / w * COORD_SCALE, prior_box[1] / h * COORD_SCALE,
            prior_box[2] / w * COORD_SCALE, prior_box[3] / h * COORD_SCALE]
    x0, y0, x1, y1 = roi_window(norm, w, h, ROI_MARGIN, min_side=ROI_MIN_SIDE)
    crop = frame_bgr[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    s = ROI_RES / max(cw, ch)
    if s < 1.0 or s > 1.0:
        crop = cv2.resize(crop, (max(1, round(cw * s)), max(1, round(ch * s))),
                          interpolation=cv2.INTER_LANCZOS4)
    rh, rw = crop.shape[:2]
    vbox = submit_img(crop, caption)           # pixel box in resized-crop coords
    dbg = {"win": [x0, y0, x1, y1], "crop_wh": [rw, rh],
           "prior": [round(v, 1) for v in prior_box]}
    if vbox is None:
        return None, {**dbg, "raw": None}
    sx, sy = (x1 - x0) / rw, (y1 - y0) / rh
    full = (x0 + vbox[0] * sx, y0 + vbox[1] * sy,
            x0 + vbox[2] * sx, y0 + vbox[3] * sy)
    dbg["raw"] = [round(v, 1) for v in full]
    if not _valid(full, frame_bgr.shape):
        return None, dbg
    return full, dbg


def run_leg_p55(leg, scene, gt, frame_at, submit_img, make_carry, *,
                cover_s, fps, frame_shape, now=time.monotonic,
                sleep=time.sleep, seq_dir=None):
    """One P5.5 leg (WSEL|SWAP). Identical to select_p53.run_leg_p53's warm
    path except the idle window runs in segments with a distractor ROI
    re-anchor at f0+90 and f0+165. submit_img(frame_bgr, caption) grounds on
    the GIVEN image (full frame or crop) and returns a pixel box in that
    image's coords -- injectable (stubbed in --selfcheck)."""
    f0, t_p = scene["f0"], scene["t_p"]
    clip_len = len(gt)
    prompt = f0 + round(t_p * fps)
    cover_frames = round(cover_s * fps)
    meta = {"leg": leg, "f0": f0, "t_p": t_p, "prompt_frame": prompt,
            "reanchor": []}

    def fail(reason, deliver=None, acquire_s=None):
        return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                    "deliver_frame": deliver, "selection": None,
                    "selection_correct": False, "reason": reason,
                    "leg": leg}, {**meta, "acquire_s": acquire_s}

    seed_t = gt[f0]
    assert seed_t is not None, f"scene f0={f0} needs valid target GT"
    seed_d = scene["distractor_box"]
    carries = {
        "target": make_carry(_rgb(frame_at(f0)), seed_t),
        "distractor": make_carry(_rgb(frame_at(f0)), tuple(seed_d)),
    }

    # --- idle window in segments, distractor re-anchored at each round ------
    cur_d = tuple(seed_d)
    seg_start = f0
    boundaries = [f0 + off for off in REANCHOR_OFFSETS if f0 + off < prompt]
    cand = {}
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

    # --- select at the prompt: UNCHANGED from P5.3 --------------------------
    caption = (scene["target_caption"] if leg == "WSEL"
               else scene["distractor_caption"])
    t0 = now()
    vbox = submit_img(frame_at(prompt), caption)
    acquire_s = now() - t0
    deliver = prompt + round(acquire_s * fps)
    meta.update({"acquire_s": round(acquire_s, 2), "caption": caption,
                 "cand_at_prompt": {k: (None if b is None else
                                        [round(v, 1) for v in b])
                                    for k, b in cand_at_prompt.items()}})
    if deliver >= clip_len:
        return fail("deliver past clip end", deliver, round(acquire_s, 2))

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


def effective_scene(scene: dict, arm: str) -> dict:
    """MC arm uses the scene captions as written; M arm swaps in the old_*
    P5.3 captions (attribution runs). Scenes without old_* fields are
    identical under both arms (M runs skip them at the CLI level)."""
    if arm == "MC":
        return scene
    s = dict(scene)
    if "old_target_caption" in s:
        s["target_caption"] = s["old_target_caption"]
    if "old_distractor_caption" in s:
        s["distractor_caption"] = s["old_distractor_caption"]
    return s


def run_matrix_scene(arm, leg, scene, out_dir: Path, *, cover_s=10.0,
                     fps=30.0, overlay=True):
    """One real-stack run: Jetson q8_0 acquire over SSH (full-frame select +
    ROI re-anchor crops through the same backend), SAM2 carry local
    (rate-capped to the on-Orin budget), scored, snapshotted."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    scene = effective_scene(scene, arm)
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
    print(f"[P5.5 {arm} {leg} {scene['clip']}:{scene['f0']}] booting Jetson "
          "q8_0...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_img(img_bgr, caption):
        # Grounds on the image AS GIVEN (crop or full frame): a 512 crop is
        # below the backend's max_side=1024 so it is fed unresized, matching
        # the deployed ROI convention.
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/p55_acq_{time.monotonic_ns()}.png"
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
            events, score, meta = run_leg_p55(
                leg, scene, gt, frame_at, submit_img, make_carry,
                cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                seq_dir=str(seq_dir))
    finally:
        be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = leg_pass(leg, score)
    result = {
        "arm": arm, "leg": leg, "scene": scene, "cover_s": cover_s, "fps": fps,
        "wall_s": round(wall, 1), "cap_hz": CARRY_HZ, "cand_hz": CAND_HZ,
        "match_floor": MATCH_FLOOR, "app_tau": APP_TAU, "loss_s": LOSS_S,
        "roi_margin": ROI_MARGIN, "roi_min_side": ROI_MIN_SIDE,
        "roi_res": ROI_RES, "reanchor_offsets": list(REANCHOR_OFFSETS),
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
    print(f"[P5.5 {arm} {leg} {scene['clip']}:{scene['f0']}] PASS={ok} "
          f"sel={score.get('selection')} genuine={score['genuine_lock']} "
          f"cov={score['coverage']} deliver_iou={score.get('deliver_iou')} "
          f"acq={score.get('acquire_s')} "
          f"reanchor={[r['accepted'] for r in meta.get('reanchor', [])]} "
          f"wall={wall:.0f}s reason={score.get('reason')}", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub carries + stub VLM + fake clock. Asserts, beyond the P5.3 suite
    (which still runs upstream): (1) re-anchor rounds fire at f0+90/f0+165
    with the ROI window around the CURRENT carry box; (2) a drifted distractor
    carry is reseeded from the crop answer and SWAP then selects it (the P5.3
    drift-failure cell flips); (3) a reject (unparseable crop answer) leaves
    the carry alone; (4) rounds >= prompt are skipped; (5) M-arm caption
    swap."""
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 60, 8.0
    boxT = (10.0, 10.0, 30.0, 30.0)
    boxD = (100.0, 100.0, 130.0, 130.0)
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the white car",
             "old_target_caption": "old target phrase",
             "distractor_caption": "the black car",
             "distractor_box": list(boxD)}
    prompt = f0 + round(t_p * fps)
    ACQ = 4.85
    deliver = prompt + round(ACQ * fps)

    with tempfile.TemporaryDirectory() as tmp:
        blank = np.full(frame_shape, 100, np.uint8)
        for i in range(clip_len):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", blank)
        frame_at = lambda _i: blank                                  # noqa: E731
        clk = [0.0]
        now = lambda: clk[0]                                         # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)           # noqa: E731

        class DriftCarry:
            """Distractor stub that has drifted to a corner; target holds."""

            def __init__(self, box):
                self.box = tuple(box)

            def step(self, _f):
                return None, self.box

        seeded = []
        drift_next = [False]   # armed per-run: the f0 distractor seed drifts

        def make_carry(_r, b):
            seeded.append(tuple(round(v, 1) for v in b))
            if drift_next[0] and tuple(b) == boxD:    # initial distractor seed
                drift_next[0] = False
                return DriftCarry((150.0, 150.0, 160.0, 160.0))   # drifted
            return DriftCarry(b)

        calls = []

        # Crop geometry for the stub: the drifted prior is (150,150,160,160)
        # in a 200x200 frame -> margin*side=20 < the 256 min_side floor -> the
        # 256 window centered at (155,155) clamps to (27,27,200,200): a
        # 173x173 crop, LANCZOS-upscaled to 512 (s=512/173). boxD in crop
        # coords = (boxD - offset) * s. The window happens to still contain
        # boxD (100..130) -- the true distractor is recoverable from the crop.
        norm = [v / 200 * COORD_SCALE for v in (150, 150, 160, 160)]
        win = roi_window(norm, 200, 200, ROI_MARGIN, min_side=ROI_MIN_SIDE)
        assert win == (27, 27, 200, 200), win        # clamped, not re-centered
        s = ROI_RES / (win[2] - win[0])

        def submit_img(img, caption):
            h, w = img.shape[:2]
            calls.append((w, h, caption))
            if (w, h) == (200, 200):                  # full-frame select
                clk[0] += ACQ
                return {"the white car": boxT,
                        "the black car": boxD,
                        "old target phrase": boxT}[caption]
            assert max(w, h) == ROI_RES, (w, h)       # LANCZOS-upscaled crop
            assert caption == "the black car", caption    # distractor caption
            return ((boxD[0] - win[0]) * s, (boxD[1] - win[1]) * s,
                    (boxD[2] - win[0]) * s, (boxD[3] - win[1]) * s)

        # (2) SWAP on the drifted-distractor scene: without re-anchor this is
        # exactly the P5.3 drift failure (match IoU 0 vs the corner box);
        # with re-anchor the carry is reseeded on boxD and SWAP passes.
        clk[0] = 0.0
        seeded.clear(); calls.clear(); drift_next[0] = True
        ev, sc, meta = run_leg_p55("SWAP", scene, gt, frame_at, submit_img,
                                   make_carry, cover_s=cover_s, fps=fps,
                                   frame_shape=frame_shape, now=now,
                                   sleep=sleep, seq_dir=tmp)
        assert meta["prompt_frame"] == prompt and sc["deliver_frame"] == deliver
        # (1) two rounds at the right frames, accepted, window logged
        assert [r["frame"] for r in meta["reanchor"]] == [f0 + 90, f0 + 165], meta
        assert all(r["accepted"] for r in meta["reanchor"]), meta
        assert meta["reanchor"][0]["win"] == list(win), meta
        # reseed happened on ~boxD both rounds
        assert seeded.count(tuple(round(v, 1) for v in boxD)) >= 2, seeded
        assert sc["selection"] == "distractor" and sc["selection_correct"], sc
        assert sc["deliver_iou"] < 0.25 and leg_pass("SWAP", sc), sc
        # crop calls used the distractor caption; select call used SWAP caption
        assert sum(1 for c in calls if c[:2] == (ROI_RES, ROI_RES)) == 2, calls

        # (3) reject path: unparseable crop answers leave the drifted carry
        # alone -> SWAP reproduces the P5.3 drift failure (NO_MATCH).
        def submit_reject(img, caption):
            h, w = img.shape[:2]
            if (w, h) == (200, 200):
                clk[0] += ACQ
                return boxD
            return None
        clk[0] = 0.0
        seeded.clear(); drift_next[0] = True
        _, sc, meta = run_leg_p55("SWAP", scene, gt, frame_at, submit_reject,
                                  make_carry, cover_s=cover_s, fps=fps,
                                  frame_shape=frame_shape, now=now,
                                  sleep=sleep, seq_dir=tmp)
        assert [r["accepted"] for r in meta["reanchor"]] == [False, False], meta
        assert len(seeded) == 2, seeded              # only the two f0 seeds
        assert sc["selection"] is None and "NO_MATCH" in sc["reason"], sc
        assert not leg_pass("SWAP", sc), sc

        # (4) rounds at/after the prompt are skipped
        near = dict(scene, t_p=2.0)                  # prompt = f0+60 < f0+90
        clk[0] = 0.0
        drift_next[0] = False                        # undrifted: WSEL path only
        _, sc, meta = run_leg_p55("WSEL", near, gt, frame_at, submit_img,
                                  make_carry, cover_s=cover_s, fps=fps,
                                  frame_shape=frame_shape, now=now,
                                  sleep=sleep, seq_dir=tmp)
        assert meta["reanchor"] == [], meta

        # (5) M-arm caption swap
        m = effective_scene(scene, "M")
        assert m["target_caption"] == "old target phrase"
        assert m["distractor_caption"] == "the black car"   # no old_ field
        assert effective_scene(scene, "MC")["target_caption"] == "the white car"

    # upstream P5.3 suite still green (frame arithmetic, WSEL/CSEL paths)
    import select_p53
    select_p53.selfcheck()
    print("select_p55 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes_p55.json path")
    ap.add_argument("--arm", default="MC", choices=ARMS)
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
        ap.error("need --matrix scenes_p55.json (or --selfcheck)")

    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in LEGS for l in legs), legs
    out_root = HERE / args.out
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        if args.arm == "M" and not any(k.startswith("old_") for k in scene):
            continue           # M arm runs only the caption-changed scenes
        for leg in legs:
            out_dir = out_root / f"{args.arm}_{leg}_{scene['clip']}_{scene['f0']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.5] skip {out_dir.name} (results.json exists)")
                continue
            run_matrix_scene(args.arm, leg, scene, out_dir,
                             cover_s=args.cover_s, fps=args.fps,
                             overlay=args.overlay)


if __name__ == "__main__":
    main()
