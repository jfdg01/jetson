"""P5.16 auto-discovery direct-delivery select harness (Part V).

Single factor changed vs P5.14 (select_p56.py, imported not copied): SEED
PROVENANCE. P5.14's first select YES rests on two oracle inputs at f0 --
`gt[f0]` for the target carry and the hand-annotated `distractor_box` for the
distractor carry. P5.16 removes both: the two candidate carries are seeded by
the deployed VLM itself during the idle window (anticipatory grounding of the
scene's two known operator phrases), with NO ground truth anywhere in the
loop. Everything downstream -- idle ROI maintenance, caption binding, direct
delivery at the prompt (acquire_s = 0), coverage, scoring, the strengthened
SWAP rule -- is the P5.14 path, byte-reused from select_p56/select_p55/
select_p53/replay_e24.

Discovery protocol (frozen):
  - Discovery starts at ds = f0 - DS_OFFSET (150 frames = 5 s of pre-roll;
    design-time frame audit 2026-07-19: all 6 targets visible with valid GT at
    ds; 4/6 distractors enter the FOV only near f0, which is why the schedule
    below fires the distractor call ~f0 where presence is proven by the P5.14
    hand seed's existence).
  - A queue starts as [target, distractor]. The head caption is fired as a
    FULL-FRAME VLM call on the current frame fs; the call's measured wall
    latency advances the stream: fr = fs + round(latency*fps). Existing
    carries keep stepping (CAND_HZ, idle_catchup_multi) across [fs, fr].
  - Accept rule (NO GT): parseable + _valid in frame AND IoU < IOU_SAME vs
    every already-carried candidate's current box (distinctness guard --
    rejects the VLM re-finding the same object). Accepted -> SAM2 carry
    seeded on frame fs (the frame the VLM actually saw), caught up fs -> fr.
  - Rejected/invalid -> the caption requeues at the BACK (the other caption
    gets the next slot). A call still in flight at the prompt frame is
    DISCARDED (outcome recorded); a caption never accepted by the prompt is
    an honest per-leg failure: reason "discovery-failed:<candidate>".
  - After both accepted, the P5.14 idle maintenance runs unchanged
    (distractor ROI re-anchor at f0+90 / f0+165), with one mechanical guard:
    a boundary that falls inside the discovery phase (frame < discovery-done)
    is SKIPPED and recorded -- the Jetson was busy discovering.

Usage:
    .venv-ft/bin/python experiments/2026-07-19-autodisc-select/discover_p516.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-19-autodisc-select/discover_p516.py \
        --matrix experiments/2026-07-19-autodisc-select/scenes_p516.json --out runs
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
P56 = REPO / "experiments" / "2026-07-19-realvid-dd-select"
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
P53 = REPO / "experiments" / "2026-07-14-multi-candidate-select"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, P56, P55, P53, E24, E18, SRC, REPO):
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
from select_p56 import (                                          # noqa: E402
    DIST_FLOOR, LEGS, bind_by_caption, leg_pass_p56, swap_weak_pass,
)

DS_OFFSET = 150   # discovery pre-roll before f0 (frames); frozen, see README
IOU_SAME = 0.5    # distinctness guard: a discovery whose box overlaps an
                  # already-carried candidate at IoU >= this is a duplicate


def discover(scene, frame_at, submit_img, make_carry, *, fps, frame_shape,
             prompt, now=time.monotonic):
    """Idle-window candidate discovery. Returns (carries, boxes, log, done_f):
    carries = {name: carry} for accepted candidates, boxes = {name: last box}
    at done_f, log = per-call records, done_f = frame the discovery phase
    released the Jetson (== prompt if a caption was never accepted)."""
    ds = scene["f0"] - DS_OFFSET
    assert ds >= 0, f"scene f0={scene['f0']} has no {DS_OFFSET}-frame pre-roll"
    queue = ["target", "distractor"]
    carries: dict = {}
    boxes: dict = {}
    log: list = []
    cur = ds
    while queue and cur < prompt:
        cand = queue.pop(0)
        caption = scene[f"{cand}_caption"]
        fs = cur
        t0 = now()
        vbox = submit_img(frame_at(fs), caption)
        lat = now() - t0
        fr = fs + max(1, round(lat * fps))
        entry = {"cand": cand, "caption": caption, "call_frame": fs,
                 "return_frame": fr, "latency_s": round(lat, 2)}
        # existing carries keep stepping through the call window
        if carries:
            stepped = idle_catchup_multi(carries, frame_at, fs,
                                         min(fr, prompt), fps)
            boxes.update(stepped)
        if fr >= prompt:
            entry["outcome"] = "in_flight_at_prompt"   # result discarded
            log.append(entry)
            cur = prompt
            break
        if not _valid(vbox, frame_shape):
            entry["outcome"] = "invalid"
            queue.append(cand)                          # retry at the back
        elif any(b is not None and iou(vbox, b) >= IOU_SAME
                 for n, b in boxes.items() if n != cand):
            entry["outcome"] = "duplicate_reject"
            entry["box"] = [round(v, 1) for v in vbox]
            queue.append(cand)
        else:
            entry["outcome"] = "accepted"
            entry["box"] = [round(v, 1) for v in vbox]
            carry = make_carry(_rgb(frame_at(fs)), tuple(vbox))
            caught = idle_catchup_multi({cand: carry}, frame_at, fs, fr, fps)
            carries[cand] = carry
            boxes[cand] = caught[cand] if caught[cand] is not None else tuple(vbox)
        log.append(entry)
        cur = fr
    if queue:      # ran out of window with captions still undiscovered
        cur = prompt
    return carries, boxes, log, cur


def run_leg_p516(leg, scene, gt, frame_at, submit_img, make_carry, *,
                 cover_s, fps, frame_shape, now=time.monotonic,
                 sleep=time.sleep, seq_dir=None, shadow=True):
    """One P5.16 leg (WSEL|SWAP): VLM discovery (above) -> P5.14 idle
    maintenance (guarded) -> P5.14 direct delivery, coverage, scoring."""
    f0, t_p = scene["f0"], scene["t_p"]
    clip_len = len(gt)
    prompt = f0 + round(t_p * fps)
    cover_frames = round(cover_s * fps)
    meta = {"leg": leg, "f0": f0, "t_p": t_p, "prompt_frame": prompt,
            "ds": f0 - DS_OFFSET, "reanchor": []}

    def fail(reason, deliver=None):
        return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                    "deliver_frame": deliver, "selection": None,
                    "selection_correct": False, "reason": reason,
                    "leg": leg}, {**meta, "acquire_s": 0.0}

    carries, boxes, dlog, done_f = discover(
        scene, frame_at, submit_img, make_carry, fps=fps,
        frame_shape=frame_shape, prompt=prompt, now=now)
    meta["discovery"] = dlog
    meta["discovery_done_frame"] = done_f
    # diagnostic only (never gates, never feeds the loop): target seed vs GT
    for e in dlog:
        if e["outcome"] == "accepted" and e["cand"] == "target":
            g = gt[e["call_frame"]] if e["call_frame"] < clip_len else None
            e["seed_iou_gt"] = round(iou(tuple(e["box"]), g), 4) if g else None

    # --- idle maintenance: P5.14/P5.5 distractor ROI re-anchor, guarded ----
    cur_d = boxes.get("distractor")
    seg_start = done_f
    for off in REANCHOR_OFFSETS:
        b = f0 + off
        if b >= prompt:
            continue
        if b < done_f or "distractor" not in carries:
            meta["reanchor"].append(
                {"frame": b, "skipped": "in-discovery" if b < done_f
                 else "undiscovered"})
            continue
        stepped = idle_catchup_multi(carries, frame_at, seg_start, b, fps)
        if stepped.get("distractor") is not None:
            cur_d = stepped["distractor"]
        if cur_d is None:                       # no box to crop around
            meta["reanchor"].append({"frame": b, "skipped": "no-prior"})
            seg_start = b
            continue
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
                                        prompt, fps) if carries else {}

    # --- P5.14 delivery contract, unchanged -------------------------------
    phrase = (scene["target_caption"] if leg == "WSEL"
              else scene["distractor_caption"])
    selected = bind_by_caption(phrase, scene)
    deliver = prompt
    meta.update({"acquire_s": 0.0, "caption": phrase, "selected": selected,
                 "cand_at_prompt": {k: (None if b is None else
                                        [round(v, 1) for v in b])
                                    for k, b in cand_at_prompt.items()}})
    if selected not in carries:
        return fail(f"discovery-failed:{selected}", deliver)
    if deliver >= clip_len:
        return fail("deliver past clip end", deliver)
    delivered_box = cand_at_prompt.get(selected)
    if delivered_box is None:
        return fail("selected track lost during idle", deliver)

    events = [(deliver / fps, tuple(delivered_box))]
    events += coverage_realtime(
        carries[selected], seq_dir, frame_at, gt, fps, deliver,
        window(deliver, cover_frames, clip_len)[1],
        reground=False, gate=None, submit=lambda f: None,
        make_carry=make_carry, now=now, sleep=sleep)
    score = e24_score(events, gt, fps, deliver, cover_frames)
    score.update({"leg": leg, "selection": selected,
                  "selection_correct": selected == ("target" if leg == "WSEL"
                                                    else "distractor"),
                  "acquire_s": 0.0})
    dg = scene.get("distractor_gt_prompt")
    score["deliver_iou_distractor"] = (
        round(iou(delivered_box, tuple(dg)), 4) if dg else None)
    meta["deliver_frame"] = deliver

    # --- shadow re-ground (non-gating diagnostic), unchanged from P5.14 ---
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
            ssel = max(mi, key=mi.get) if mi else None
            if ssel is not None and mi[ssel] < MATCH_FLOOR:
                ssel = None
            sh.update({"match_ious": {k: round(v, 4) for k, v in mi.items()},
                       "selected": ssel})
        else:
            sh.update({"match_ious": None, "selected": None})
        meta["shadow"] = sh
    return events, score, meta


# --------------------------------------------------------------------------- #
def _frame_health(img, name):
    """CLAUDE.md cheap asserts: a frame that is >99% one colour is a failed
    render, not a night scene."""
    flat = img.reshape(-1, img.shape[-1])
    _, counts = np.unique(flat, axis=0, return_counts=True)
    frac = counts.max() / len(flat)
    assert frac < 0.99, f"frame_health: {name} is {frac:.1%} one colour"


def _dump_pngs(out_dir: Path, scene, leg, gt, frame_at, meta, score,
               delivered_box):
    """The gating claim frames: the deliver frame (what was delivered, vs
    both GTs) and the accepted discovery frame of the SELECTED candidate
    (what the VLM found, on the frame it saw)."""
    prompt = meta["prompt_frame"]
    img = frame_at(prompt).copy()
    _frame_health(img, "deliver.png")
    g = gt[prompt] if prompt < len(gt) and gt[prompt] is not None else None
    if g is not None:
        cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])),
                      (0, 0, 220), 2)
    dg = scene.get("distractor_gt_prompt")
    if dg:
        cv2.rectangle(img, (int(dg[0]), int(dg[1])), (int(dg[2]), int(dg[3])),
                      (220, 80, 0), 2)
    if delivered_box is not None:
        b = [int(v) for v in delivered_box]
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
    cv2.putText(img, f"DELIVERED f={prompt} {leg} green=delivered "
                     f"red=targetGT blue=distractorGT iou_t="
                     f"{score.get('deliver_iou')} iou_d="
                     f"{score.get('deliver_iou_distractor')}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(out_dir / "deliver.png"), img)

    sel = meta.get("selected")
    for e in meta.get("discovery", []):
        if e["outcome"] != "accepted":
            continue
        img = frame_at(e["call_frame"]).copy()
        _frame_health(img, f"discovery_{e['cand']}.png")
        b = [int(v) for v in e["box"]]
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
        gd = (gt[e["call_frame"]] if e["cand"] == "target"
              and e["call_frame"] < len(gt) else None)
        if gd is not None:
            cv2.rectangle(img, (int(gd[0]), int(gd[1])),
                          (int(gd[2]), int(gd[3])), (0, 0, 220), 2)
        tag = " <== SELECTED" if e["cand"] == sel else ""
        cv2.putText(img, f"DISCOVERY f={e['call_frame']} {e['cand']}"
                         f"{tag} '{e['caption']}' green=VLM"
                         + (" red=targetGT" if gd is not None else ""),
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2)
        cv2.imwrite(str(out_dir / f"discovery_{e['cand']}.png"), img)


def run_matrix_scene(leg, scene, out_dir: Path, *, cover_s=10.0, fps=30.0,
                     overlay=True):
    """One real-stack run: Jetson q8_0 over SSH (discovery calls + ROI
    re-anchor crops + shadow), SAM2 carry local. Snapshot under
    DSC_<LEG>_<clip>_<f0>/."""
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
    print(f"[P5.16 DSC {leg} {scene['clip']}:{scene['f0']}] booting Jetson "
          "q8_0...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_img(img_bgr, caption):
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/p516_acq_{time.monotonic_ns()}.png"
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
            events, score, meta = run_leg_p516(
                leg, scene, gt, frame_at, submit_img, make_carry,
                cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                seq_dir=str(seq_dir))
    finally:
        be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = leg_pass_p56(leg, score)
    result = {
        "arm": "DSC", "leg": leg, "scene": scene, "cover_s": cover_s,
        "fps": fps, "wall_s": round(wall, 1), "cap_hz": CARRY_HZ,
        "cand_hz": CAND_HZ, "match_floor": MATCH_FLOOR,
        "dist_floor": DIST_FLOOR, "app_tau": APP_TAU, "loss_s": LOSS_S,
        "roi_margin": ROI_MARGIN, "roi_min_side": ROI_MIN_SIDE,
        "roi_res": ROI_RES, "reanchor_offsets": list(REANCHOR_OFFSETS),
        "ds_offset": DS_OFFSET, "iou_same": IOU_SAME,
        "pass": ok,
        "swap_weak_pass": swap_weak_pass(score) if leg == "SWAP" else None,
        "score": score, "meta": meta,
        "events": [(round(t, 3), None if b is None else
                    [round(v, 1) for v in b]) for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    delivered = None
    if score.get("deliver_frame") is not None and score.get("reason") is None:
        delivered = next((b for t, b in events), None)
    _dump_pngs(out_dir, scene, leg, gt, frame_at, meta, score, delivered)
    if overlay and score.get("deliver_frame") and score.get("reason") is None:
        end = window(score["deliver_frame"], round(cover_s * fps), len(gt))[1]
        if leg == "SWAP" and scene.get("distractor_gt_prompt"):
            dbox, dfr = scene["distractor_gt_prompt"], meta["prompt_frame"]
        else:
            dbox, dfr = None, None
        render_overlay_slice(seq_dir, events, gt, fps, out_dir / "overlay.mp4",
                             scene["f0"], end, distractor_box=dbox, f0=dfr)
    print(f"[P5.16 DSC {leg} {scene['clip']}:{scene['f0']}] PASS={ok} "
          f"sel={score.get('selection')} genuine={score['genuine_lock']} "
          f"cov={score['coverage']} deliver_iou={score.get('deliver_iou')} "
          f"iou_dist={score.get('deliver_iou_distractor')} "
          f"weak={result['swap_weak_pass']} "
          f"disc={[e['outcome'] for e in meta.get('discovery', [])]} "
          f"shadow_sel={(meta.get('shadow') or {}).get('selected')} "
          f"wall={wall:.0f}s reason={score.get('reason')}", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub suite (no GPU/Jetson). Asserts, beyond the upstream P5.6 suite
    (which still runs at the end):
      (A) happy path: schedule (target at ds, distractor after one measured
          latency), latency-driven frame advance, in-discovery re-anchor
          skip + post-discovery re-anchor fire, delivery acquire_s=0 at the
          prompt, WSEL PASS, exactly discovery+shadow full-frame calls;
      (B) invalid first call -> requeue at back, other caption gets the
          slot; the retry no longer fits the window (2 completed slots at
          4.6 s latency -- the real budget) -> in_flight_at_prompt recorded,
          SWAP still passes off the accepted distractor, WSEL on the same
          script fails honestly with 'discovery-failed:target';
      (C) duplicate discovery (VLM re-finds the target) -> rejected,
          requeued, retry ACCEPTED (fast-latency stub so a 3rd slot fits);
      (D) discovery-failed: distractor never valid -> SWAP fails with reason
          'discovery-failed:distractor', WSEL on the same scene still passes;
      (E) honesty: a WRONG-OBJECT discovered distractor is carried and
          delivered -> weak SWAP passes, strengthened SWAP FAILS."""
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 240, 8.0
    boxT = (10.0, 10.0, 30.0, 30.0)
    boxD = (100.0, 100.0, 130.0, 130.0)
    boxJ = (150.0, 150.0, 162.0, 162.0)     # junk corner (wrong object)
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the white car",
             "distractor_caption": "the black car",
             "distractor_box": list(boxD),          # unused by P5.16 (oracle)
             "distractor_gt_prompt": list(boxD)}
    ds = f0 - DS_OFFSET
    prompt = f0 + round(t_p * fps)
    ACQ = 4.6
    ACQ_F = round(ACQ * fps)                         # 138 frames per call

    with tempfile.TemporaryDirectory() as tmp:
        blank = np.full(frame_shape, 100, np.uint8)
        blank[0, 0] = (0, 0, 0)     # defeat the >99%-one-colour assert
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

        def make_carry(_r, b):
            return HoldCarry(b)

        def scripted(answers, acq=ACQ):
            """Full-frame answers consumed in order, each costing `acq`
            seconds of fake clock; ROI crop calls (re-anchor) return None
            (rejected) and are not recorded. Records full-frame captions."""
            calls = []
            it = iter(answers)

            def submit(img, caption):
                h, w = img.shape[:2]
                if (w, h) == (frame_shape[1], frame_shape[0]):
                    calls.append(caption)
                    clk[0] += acq
                    return next(it)
                return None   # ROI crop path: re-anchor rejected in stubs
            return submit, calls

        # (A) happy path -----------------------------------------------------
        clk[0] = 0.0
        submit, calls = scripted([boxT, boxD, boxT])   # T, D, shadow(WSEL)
        ev, sc, meta = run_leg_p516("WSEL", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        d = meta["discovery"]
        assert [e["cand"] for e in d] == ["target", "distractor"], d
        assert d[0]["call_frame"] == ds and d[0]["outcome"] == "accepted", d
        assert d[1]["call_frame"] == ds + ACQ_F, d
        assert d[1]["outcome"] == "accepted", d
        assert meta["discovery_done_frame"] == ds + 2 * ACQ_F, meta
        # ds+2*ACQ_F = f0+126: the f0+90 boundary is in-discovery -> skipped,
        # f0+165 fires (rejected by the stub -> accepted False)
        ra = meta["reanchor"]
        assert ra[0] == {"frame": f0 + 90, "skipped": "in-discovery"}, ra
        assert ra[1]["frame"] == f0 + 165 and ra[1]["accepted"] is False, ra
        assert sc["acquire_s"] == 0.0 and sc["deliver_frame"] == prompt, sc
        assert sc["genuine_lock"] and sc["coverage"] == 1.0, sc
        assert leg_pass_p56("WSEL", sc), sc
        assert calls == ["the white car", "the black car", "the white car"], calls
        assert meta["shadow"]["selected"] == "target", meta["shadow"]

        # (B) invalid first call -> requeue at back; retry does not fit the
        # window (slots: ds->ds+138, ds+138->ds+276; retry ds+276->ds+414 =
        # f0+264 >= prompt f0+240) -> in-flight discard. SWAP still passes
        # off the accepted distractor; WSEL fails honestly.
        clk[0] = 0.0
        submit, calls = scripted([None, boxD, boxT, boxD])  # T inv, D, T*, shadow
        ev, sc, meta = run_leg_p516("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        d = meta["discovery"]
        assert [(e["cand"], e["outcome"]) for e in d] == [
            ("target", "invalid"), ("distractor", "accepted"),
            ("target", "in_flight_at_prompt")], d
        assert d[2]["call_frame"] == ds + 2 * ACQ_F, d
        assert meta["discovery_done_frame"] == prompt, meta
        assert all(r.get("skipped") == "in-discovery"
                   for r in meta["reanchor"]), meta["reanchor"]
        assert sc["selection"] == "distractor" and sc["deliver_iou"] < 0.25, sc
        assert sc["deliver_iou_distractor"] >= DIST_FLOOR, sc
        assert leg_pass_p56("SWAP", sc) and swap_weak_pass(sc), sc
        clk[0] = 0.0
        submit, calls = scripted([None, boxD, boxT])        # same script, WSEL
        ev, sc, meta = run_leg_p516("WSEL", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert sc["reason"] == "discovery-failed:target", sc
        assert not leg_pass_p56("WSEL", sc), sc

        # (C) duplicate discovery rejected, retry accepted (acq=3.0 so a 3rd
        # slot fits: calls at ds, ds+90, ds+180, done ds+270 < prompt) ------
        clk[0] = 0.0
        submit, calls = scripted([boxT, boxT, boxD, boxD], acq=3.0)
        ev, sc, meta = run_leg_p516("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        d = meta["discovery"]
        assert [(e["cand"], e["outcome"]) for e in d] == [
            ("target", "accepted"), ("distractor", "duplicate_reject"),
            ("distractor", "accepted")], d
        assert d[2]["call_frame"] == ds + 2 * 90, d
        assert leg_pass_p56("SWAP", sc), sc

        # (D) discovery-failed: distractor never valid ----------------------
        clk[0] = 0.0
        submit, calls = scripted([boxT, None, None])
        ev, sc, meta = run_leg_p516("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert sc["reason"] == "discovery-failed:distractor", sc
        assert not leg_pass_p56("SWAP", sc) and not swap_weak_pass(sc), sc
        clk[0] = 0.0
        submit, calls = scripted([boxT, None, None, boxT])
        ev, sc, meta = run_leg_p516("WSEL", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert leg_pass_p56("WSEL", sc), sc   # target leg unharmed

        # (E) honesty: wrong-object distractor discovery delivered ----------
        clk[0] = 0.0
        submit, calls = scripted([boxT, boxJ, boxD])   # D grounds junk corner
        ev, sc, meta = run_leg_p516("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert meta["discovery"][1]["outcome"] == "accepted", meta["discovery"]
        assert sc["selection"] == "distractor" and sc.get("reason") is None, sc
        assert sc["deliver_iou"] < 0.25, sc
        assert sc["deliver_iou_distractor"] < DIST_FLOOR, sc
        assert swap_weak_pass(sc) and not leg_pass_p56("SWAP", sc), sc

    # upstream suite still green (delivery contract, honesty, geometry)
    import select_p56
    select_p56.selfcheck()
    print("discover_p516 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes_p516.json path")
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
        ap.error("need --matrix scenes_p516.json (or --selfcheck)")

    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in ("WSEL", "SWAP") for l in legs), legs
    out_root = HERE / args.out
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        for leg in legs:
            out_dir = out_root / f"DSC_{leg}_{scene['clip']}_{scene['f0']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.16] skip {out_dir.name} (results.json exists)")
                continue
            run_matrix_scene(leg, scene, out_dir, cover_s=args.cover_s,
                             fps=args.fps, overlay=args.overlay)


if __name__ == "__main__":
    main()
