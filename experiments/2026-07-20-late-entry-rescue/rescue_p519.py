"""P5.19 late-entry rescue harness (Part V).

Single mechanism changed vs the P5.18 run (discover_p516.py, imported not
copied): DISTRACTOR-SIDE DISCOVERY INTEGRITY UNDER LATE ENTRY. Two coupled
patches, one lever:

  PATCH 1 -- frame-ALIGNED distinctness guard (bug fix). The P5.16 guard
  compares the VLM box (from frame fs, the frame the VLM saw) against carried
  boxes that have already been stepped through the ~4.6 s call window to fr.
  Under motion the same physical object no longer overlaps itself across 138
  frames, so the guard NEVER fired in P5.18 (0 duplicate_rejects in 108
  discovery calls; e.g. car18:150 "black SUV" box vs the carried target:
  IoU 0.854 at fs, 0.087 at fr -> accepted, distractor track born ON the
  target). Fix: snapshot the carried boxes BEFORE the catch-up step and dedup
  against the snapshot -- both boxes at fs, apples to apples.

  PATCH 2 -- bounded GRACE delivery (contract completion). With the guard
  alive, a rejected caption requeues, but the retry's return frame lands
  ~13 frames past the prompt and P5.16 discards it (in_flight_at_prompt) --
  the schedule has exactly 2 completed slots per idle window, so PATCH 1
  alone converts wrong-seed deliveries into honest discovery-failed and
  recovers ZERO cells. The harness is synchronous: at the prompt the
  in-flight call's result is already in hand. Grace: iff the operator phrase
  names a candidate with no carry but with an in-flight discovery result,
  and that result is _valid AND aligned-distinct AND lands within
  GRACE_MAX_S of the prompt, honor it -- seed SAM2 at fs, catch up
  fs -> prompt (box_at_prompt, used for the strengthened-SWAP distractor-GT
  check so the hand GT stays frame-aligned), catch up prompt -> fr, deliver
  at fr with acquire_s = (fr - prompt)/fps. Observed candidate cells land
  at 0.23-0.8 s -- still ~6x under the 4.68 s cold re-ground.

Everything else -- schedule, retries, ROI re-anchor, binding, delivery,
coverage, scoring, strengthened SWAP rule -- is discover_p516 verbatim via
monkeypatch: p516.run_leg_p516 = run_leg_p519, then the unchanged
p516.run_matrix_scene runs the cell (module-global resolution at call time).

Usage:
    .venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/rescue_p519.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-20-late-entry-rescue/rescue_p519.py \
        --matrix /home/gara/jetson/experiments/2026-07-20-n25-select/scenes_p518.json \
        --out /home/gara/jetson/experiments/2026-07-20-late-entry-rescue/runs
    ... --only car18:150 --legs SWAP   (single-cell retry)
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
P516_DIR = REPO / "experiments" / "2026-07-19-autodisc-select"
sys.path.insert(0, str(P516_DIR))
import discover_p516 as p516                                       # noqa: E402
from discover_p516 import DS_OFFSET, IOU_SAME                      # noqa: E402

# single-source the upstream helpers through p516's namespace
iou = p516.iou
_valid = p516._valid
_rgb = p516._rgb
idle_catchup_multi = p516.idle_catchup_multi
window = p516.window
coverage_realtime = p516.coverage_realtime
e24_score = p516.e24_score

GRACE_MAX_S = 2.0   # frozen: max seconds past the prompt a grace delivery
                    # may land (P5.18 in-flight returns land 0.23-0.8 s late;
                    # the cap keeps "late" bounded well under the 4.68 s cold
                    # re-ground it replaces)

_ORIG_DISCOVER = p516.discover          # kept for the selfcheck A/B
_ORIG_RUN_LEG = p516.run_leg_p516


# --------------------------------------------------------------------------- #
def discover_aligned(scene, frame_at, submit_img, make_carry, *, fps,
                     frame_shape, prompt, now=time.monotonic):
    """PATCH 1: p516.discover with the distinctness guard evaluated at fs.
    Returns (carries, boxes, log, done_f, pending); pending is the fully-
    evaluated in-flight call (or None) for PATCH 2."""
    ds = scene["f0"] - DS_OFFSET
    assert ds >= 0, f"scene f0={scene['f0']} has no {DS_OFFSET}-frame pre-roll"
    queue = ["target", "distractor"]
    carries: dict = {}
    boxes: dict = {}
    log: list = []
    pending = None
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
        # PATCH 1: snapshot carried boxes AT fs -- the invariant at loop top
        # is boxes aligned with cur == fs -- BEFORE the catch-up step moves
        # them to fr. vbox is from fs; the dedup must compare at fs.
        boxes_at_fs = dict(boxes)
        if carries:
            stepped = idle_catchup_multi(carries, frame_at, fs,
                                         min(fr, prompt), fps)
            boxes.update(stepped)
        valid = _valid(vbox, frame_shape)
        dup_iou, dup_vs = 0.0, None
        if valid:
            for n, b in boxes_at_fs.items():
                if n != cand and b is not None:
                    v = iou(vbox, b)
                    if v > dup_iou:
                        dup_iou, dup_vs = v, n
        dup = valid and dup_iou >= IOU_SAME
        if fr >= prompt:
            entry["outcome"] = "in_flight_at_prompt"
            entry["pending_valid"] = bool(valid)
            entry["pending_dup"] = bool(dup)
            if valid:
                entry["box"] = [round(v, 1) for v in vbox]
                entry["aligned_iou_max"] = round(dup_iou, 4)
            pending = {"cand": cand, "caption": caption, "fs": fs, "fr": fr,
                       "latency_s": round(lat, 2),
                       "vbox": None if not valid else tuple(vbox),
                       "valid": bool(valid), "dup": bool(dup),
                       "dup_iou": round(dup_iou, 4), "dup_vs": dup_vs}
            log.append(entry)
            cur = prompt
            break
        if not valid:
            entry["outcome"] = "invalid"
            queue.append(cand)                          # retry at the back
        elif dup:
            entry["outcome"] = "duplicate_reject"
            entry["box"] = [round(v, 1) for v in vbox]
            entry["dup_iou"] = round(dup_iou, 4)
            entry["dup_vs"] = dup_vs
            queue.append(cand)
        else:
            entry["outcome"] = "accepted"
            entry["box"] = [round(v, 1) for v in vbox]
            entry["aligned_iou_max"] = round(dup_iou, 4)
            carry = make_carry(_rgb(frame_at(fs)), tuple(vbox))
            caught = idle_catchup_multi({cand: carry}, frame_at, fs, fr, fps)
            carries[cand] = carry
            boxes[cand] = caught[cand] if caught[cand] is not None else tuple(vbox)
        log.append(entry)
        cur = fr
    if queue:      # ran out of window with captions still undiscovered
        cur = prompt
    return carries, boxes, log, cur, pending


def _discover4(scene, frame_at, submit_img, make_carry, **kw):
    """4-tuple wrapper so discover_aligned can stand in for p516.discover
    (static-equivalence selfcheck only; the real path uses run_leg_p519)."""
    carries, boxes, log, done_f, _ = discover_aligned(
        scene, frame_at, submit_img, make_carry, **kw)
    return carries, boxes, log, done_f


# --------------------------------------------------------------------------- #
def run_leg_p519(leg, scene, gt, frame_at, submit_img, make_carry, *,
                 cover_s, fps, frame_shape, now=time.monotonic,
                 sleep=time.sleep, seq_dir=None, shadow=True):
    """p516.run_leg_p516 with discover_aligned (PATCH 1) and the grace
    delivery block (PATCH 2). Everything else line-for-line identical."""
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

    carries, boxes, dlog, done_f, pending = discover_aligned(
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
    for off in p516.REANCHOR_OFFSETS:
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
        new_box, dbg = p516.roi_reanchor(frame_b, cur_d,
                                         scene["distractor_caption"],
                                         submit_img)
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

    # --- P5.14 delivery contract + PATCH 2 grace --------------------------
    phrase = (scene["target_caption"] if leg == "WSEL"
              else scene["distractor_caption"])
    selected = p516.bind_by_caption(phrase, scene)
    deliver = prompt
    meta.update({"acquire_s": 0.0, "caption": phrase, "selected": selected,
                 "cand_at_prompt": {k: (None if b is None else
                                        [round(v, 1) for v in b])
                                    for k, b in cand_at_prompt.items()}})
    delivered_box = None            # set by grace; else cand_at_prompt below
    grace_box_prompt = None
    graced = False
    if selected not in carries:
        gr = {"fired": False}
        meta["grace"] = gr
        if pending is None or pending["cand"] != selected:
            gr["refused"] = "no-pending"
            return fail(f"discovery-failed:{selected}", deliver)
        gr.update({"fs": pending["fs"], "fr": pending["fr"],
                   "latency_s": pending["latency_s"]})
        if not pending["valid"]:
            gr["refused"] = "invalid"
            return fail(f"discovery-failed:{selected}", deliver)
        if pending["dup"]:
            gr["refused"] = "duplicate"
            gr["dup_iou"] = pending["dup_iou"]
            gr["dup_vs"] = pending["dup_vs"]
            return fail(f"discovery-failed:{selected}", deliver)
        acq = (pending["fr"] - prompt) / fps
        if acq > GRACE_MAX_S:
            gr["refused"] = "cap"
            gr["acquire_s"] = round(acq, 3)
            return fail(f"discovery-failed:{selected}", deliver)
        if pending["fr"] >= clip_len:
            gr["refused"] = "past-clip-end"
            return fail("deliver past clip end", pending["fr"])
        # honor the in-flight result: seed at fs (the frame the VLM saw),
        # catch up fs -> prompt (aligned scoring box), then prompt -> fr.
        vbox = tuple(pending["vbox"])
        carry = make_carry(_rgb(frame_at(pending["fs"])), vbox)
        upto = idle_catchup_multi({selected: carry}, frame_at,
                                  pending["fs"], prompt, fps)
        grace_box_prompt = upto.get(selected)
        upto = idle_catchup_multi({selected: carry}, frame_at,
                                  prompt, pending["fr"], fps)
        delivered_box = upto.get(selected)
        if delivered_box is None:
            gr["refused"] = "carry-lost"
            return fail("grace-carry-lost", deliver)
        carries[selected] = carry
        cand_at_prompt[selected] = grace_box_prompt
        meta["cand_at_prompt"][selected] = (
            None if grace_box_prompt is None
            else [round(v, 1) for v in grace_box_prompt])
        deliver = pending["fr"]
        graced = True
        gr.update({"fired": True, "acquire_s": round(acq, 3),
                   "vbox": [round(v, 1) for v in vbox],
                   "box_at_prompt": None if grace_box_prompt is None
                   else [round(v, 1) for v in grace_box_prompt],
                   "box_at_deliver": [round(v, 1) for v in delivered_box]})
        meta["acquire_s"] = round(acq, 3)
        # re-mark the log entry so _dump_pngs renders the discovery frame
        for e in dlog:
            if (e.get("outcome") == "in_flight_at_prompt"
                    and e["cand"] == selected):
                e["outcome"] = "accepted"
                e["graced"] = True
                e["box"] = [round(v, 1) for v in vbox]
    if deliver >= clip_len:
        return fail("deliver past clip end", deliver)
    if delivered_box is None:
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
                  "acquire_s": meta["acquire_s"]})
    dg = scene.get("distractor_gt_prompt")
    # strengthened SWAP stays frame-aligned: the hand GT is at the prompt
    # frame, so a graced delivery is checked with its box_at_prompt (the
    # SAM2 catch-up box at the prompt), falling back to the delivered box.
    iou_box = (grace_box_prompt if graced and grace_box_prompt is not None
               else delivered_box)
    score["deliver_iou_distractor"] = (
        round(iou(iou_box, tuple(dg)), 4) if dg else None)
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
            if ssel is not None and mi[ssel] < p516.MATCH_FLOOR:
                ssel = None
            sh.update({"match_ious": {k: round(v, 4) for k, v in mi.items()},
                       "selected": ssel})
        else:
            sh.update({"match_ious": None, "selected": None})
        meta["shadow"] = sh
    return events, score, meta


# --------------------------------------------------------------------------- #
def _dump_grace_png(out_dir: Path, scene, r):
    """Graced cells get a claim frame AT the grace deliver frame fr (the
    stock deliver.png is drawn on the prompt frame). green = delivered box,
    red = target GT at fr, blue = hand distractor GT (annotated at the
    PROMPT frame -- up to GRACE_MAX_S stale here, labelled as such)."""
    gr = (r["meta"].get("grace") or {})
    if not gr.get("fired"):
        return
    E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
    data = E18 / "data" / "UAV123"
    seq_dir = data / "data_seq" / "UAV123" / scene["clip"]
    gt = p516.load_uav123_gt(data / "anno" / "UAV123" / f"{scene['clip']}.txt")
    paths = sorted(seq_dir.glob("*.jpg"))
    fr = gr["fr"]
    img = cv2.imread(str(paths[min(fr, len(paths) - 1)])).copy()
    p516._frame_health(img, "grace_deliver.png")
    g = gt[fr] if fr < len(gt) and gt[fr] is not None else None
    if g is not None:
        cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])),
                      (0, 0, 220), 2)
    dg = scene.get("distractor_gt_prompt")
    if dg:
        cv2.rectangle(img, (int(dg[0]), int(dg[1])), (int(dg[2]), int(dg[3])),
                      (220, 80, 0), 2)
    b = [int(v) for v in gr["box_at_deliver"]]
    cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
    cv2.putText(img, f"GRACE DELIVER f={fr} acquire_s={gr['acquire_s']} "
                     "green=delivered red=targetGT@fr "
                     "blue=distractorGT@prompt(stale here)",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(out_dir / "grace_deliver.png"), img)


def run_matrix(args) -> None:
    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in ("WSEL", "SWAP") for l in legs), legs
    out_root = Path(args.out)
    if not out_root.is_absolute():
        out_root = HERE / out_root
    p516.run_leg_p516 = run_leg_p519          # THE patch (module-global)
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        for leg in legs:
            out_dir = out_root / f"DSC_{leg}_{scene['clip']}_{scene['f0']}"
            rj = out_dir / "results.json"
            if rj.exists():
                print(f"[P5.19] skip {out_dir.name} (results.json exists)")
                continue
            p516.run_matrix_scene(leg, scene, out_dir, cover_s=args.cover_s,
                                  fps=args.fps, overlay=args.overlay)
            r = json.loads(rj.read_text())
            r["p519"] = {"patch": "late-entry-rescue",
                         "aligned_dedup": True, "grace_max_s": GRACE_MAX_S}
            rj.write_text(json.dumps(r, indent=2))
            _dump_grace_png(out_dir, scene, r)


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """Stub suite (no GPU/Jetson). Asserts:
      (S1) BUG REPRO A/B: under motion (MovingCarry, 2 px/step) the ORIGINAL
           guard accepts a distractor discovery that is the target's own box
           (misaligned IoU ~0 at fr), the ALIGNED guard rejects it (IoU 1.0
           at fs) and the retry is correctly in-flight-with-dup at the
           prompt;
      (S2) an in-window retry after an aligned duplicate_reject is accepted
           and delivers normally (acquire_s = 0, no grace);
      (S3) grace fires: in-flight clean distractor result 0.8 s past the
           prompt -> delivered at fr, acquire_s = 0.8, strengthened SWAP
           passes via box_at_prompt, log entry re-marked accepted+graced;
      (S4) grace refuses a duplicate in-flight result -> honest
           discovery-failed:distractor;
      (S5) grace refuses past the cap (3.2 s > GRACE_MAX_S) -> honest fail;
      (S6) STATIC EQUIVALENCE: with motionless carries the aligned guard is
           behaviour-identical -- the entire upstream p516 selfcheck runs
           green with discover_aligned patched in (grace NOT patched: p516's
           scenario (B) asserts the in-flight discard that grace replaces).
    """
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 240, 8.0
    boxT = (10.0, 10.0, 30.0, 30.0)
    boxD = (100.0, 100.0, 130.0, 130.0)
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the white car",
             "distractor_caption": "the black car",
             "distractor_box": list(boxD),
             "distractor_gt_prompt": list(boxD)}
    ds = f0 - DS_OFFSET                      # 90
    prompt = f0 + round(t_p * fps)           # 480
    ACQ = 4.6
    ACQ_F = round(ACQ * fps)                 # 138 frames per call

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

        class MovingCarry:
            """Box drifts +dx px per step() -- models on-screen motion.
            idle_catchup_multi strides ~10 frames, so a 138-frame call
            window is 14 steps = 28 px: a 20 px box no longer overlaps
            itself across the window (misaligned IoU 0.0)."""
            def __init__(self, box, dx=2.0):
                self.box = tuple(box)
                self.dx = dx

            def step(self, _f):
                x1, y1, x2, y2 = self.box
                self.box = (x1 + self.dx, y1, x2 + self.dx, y2)
                return None, self.box

        def make_carry(_r, b):
            return HoldCarry(b)

        def scripted(answers):
            """answers: list of (value_or_callable, latency_s) consumed by
            FULL-FRAME calls in order; callables are evaluated at call time
            (models the VLM boxing whatever is there NOW). ROI crop calls
            (re-anchor) return None and are not recorded."""
            calls = []
            it = iter(list(answers))

            def submit(img, caption):
                h, w = img.shape[:2]
                if (w, h) == (frame_shape[1], frame_shape[0]):
                    calls.append(caption)
                    val, lat = next(it)
                    clk[0] += lat
                    return val() if callable(val) else val
                return None   # ROI crop path: re-anchor rejected in stubs
            return submit, calls

        # (S1) bug repro A/B on discover itself ------------------------------
        created = []

        def make_moving(_r, b):
            c = MovingCarry(b)
            created.append(c)
            return c

        live_target_box = lambda: created[0].box                    # noqa: E731
        # ORIGINAL guard: distractor answer == the target's CURRENT box at
        # call time; by the post-step compare the target has moved 28 px on.
        created.clear()
        clk[0] = 0.0
        submit, _ = scripted([(boxT, ACQ), (live_target_box, ACQ)])
        _, _, log_o, _ = _ORIG_DISCOVER(
            scene, frame_at, submit, make_moving, fps=fps,
            frame_shape=frame_shape, prompt=prompt, now=now)
        assert [(e["cand"], e["outcome"]) for e in log_o] == [
            ("target", "accepted"), ("distractor", "accepted")], (
            "bug no longer reproduces", log_o)
        # ALIGNED guard: same script + one retry answer -> reject, retry
        # in-flight at the prompt, itself evaluated as a duplicate.
        created.clear()
        clk[0] = 0.0
        submit, _ = scripted([(boxT, ACQ), (live_target_box, ACQ),
                              (live_target_box, ACQ)])
        _, _, log_a, _, pend = discover_aligned(
            scene, frame_at, submit, make_moving, fps=fps,
            frame_shape=frame_shape, prompt=prompt, now=now)
        assert [(e["cand"], e["outcome"]) for e in log_a] == [
            ("target", "accepted"), ("distractor", "duplicate_reject"),
            ("distractor", "in_flight_at_prompt")], log_a
        assert log_a[1]["dup_iou"] == 1.0 and log_a[1]["dup_vs"] == "target", log_a
        assert pend and pend["cand"] == "distractor" and pend["dup"], pend

        # (S2) aligned reject -> in-window retry accepted, normal delivery --
        clk[0] = 0.0
        submit, calls = scripted([(boxT, 3.0), (boxT, 3.0), (boxD, 3.0),
                                  (boxT, 3.0)])          # last = shadow
        ev, sc, meta = run_leg_p519("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        d = meta["discovery"]
        assert [(e["cand"], e["outcome"]) for e in d] == [
            ("target", "accepted"), ("distractor", "duplicate_reject"),
            ("distractor", "accepted")], d
        assert sc["acquire_s"] == 0.0 and sc["deliver_frame"] == prompt, sc
        assert "grace" not in meta, meta.get("grace")
        assert p516.leg_pass_p56("SWAP", sc), sc

        # (S3) grace fires: clean in-flight result 0.8 s past the prompt ----
        clk[0] = 0.0
        submit, calls = scripted([(boxT, ACQ), (None, ACQ), (boxD, ACQ),
                                  (boxT, ACQ)])          # last = shadow
        ev, sc, meta = run_leg_p519("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        d = meta["discovery"]
        assert [(e["cand"], e["outcome"]) for e in d] == [
            ("target", "accepted"), ("distractor", "invalid"),
            ("distractor", "accepted")], d
        assert d[2].get("graced") is True, d
        gr = meta["grace"]
        assert gr["fired"] and gr["fs"] == ds + 2 * ACQ_F == 366, gr
        assert gr["fr"] == 504 and sc["deliver_frame"] == 504, (gr, sc)
        assert sc["acquire_s"] == 0.8 == meta["acquire_s"], sc
        assert sc["deliver_iou_distractor"] == 1.0, sc   # via box_at_prompt
        assert sc["deliver_iou"] < 0.25, sc              # vs target GT at fr
        assert p516.leg_pass_p56("SWAP", sc), sc
        assert len(calls) == 4, calls                    # shadow still fired

        # (S4) grace refuses a duplicate in-flight result --------------------
        clk[0] = 0.0
        submit, calls = scripted([(boxT, ACQ), (None, ACQ), (boxT, ACQ)])
        ev, sc, meta = run_leg_p519("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert sc["reason"] == "discovery-failed:distractor", sc
        assert meta["grace"]["refused"] == "duplicate", meta["grace"]
        assert meta["grace"]["dup_iou"] == 1.0, meta["grace"]
        assert not p516.leg_pass_p56("SWAP", sc), sc
        assert len(calls) == 3, calls                    # no shadow on fail

        # (S5) grace refuses past the cap ------------------------------------
        clk[0] = 0.0
        submit, calls = scripted([(boxT, ACQ), (None, ACQ), (boxD, 7.0)])
        ev, sc, meta = run_leg_p519("SWAP", scene, gt, frame_at, submit,
                                    make_carry, cover_s=cover_s, fps=fps,
                                    frame_shape=frame_shape, now=now,
                                    sleep=sleep, seq_dir=tmp)
        assert sc["reason"] == "discovery-failed:distractor", sc
        g = meta["grace"]
        assert g["refused"] == "cap" and g["acquire_s"] == 3.2, g
        assert not p516.leg_pass_p56("SWAP", sc), sc

    # (S6) static equivalence: whole upstream suite with the aligned guard --
    p516.discover = _discover4
    try:
        assert p516.run_leg_p516 is _ORIG_RUN_LEG, "run_leg must be unpatched"
        p516.selfcheck()
    finally:
        p516.discover = _ORIG_DISCOVER
    print("rescue_p519 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes_p518.json path")
    ap.add_argument("--legs", default="WSEL,SWAP")
    ap.add_argument("--only", help="restrict to scene id clip:f0, e.g. car18:150")
    ap.add_argument("--out", default=str(HERE / "runs"))
    ap.add_argument("--cover-s", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--no-overlay", dest="overlay", action="store_false",
                    default=True)
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return
    if not args.matrix:
        ap.error("need --matrix scenes_p518.json (or --selfcheck)")
    run_matrix(args)


if __name__ == "__main__":
    main()
