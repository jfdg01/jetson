"""
T1a — scored SITL clip recorder (Part III, object permanence).

Produces a deterministic, replayable referring-video clip: a scripted multi-
vehicle NED trajectory (target van + same-class distractor) projected per frame
to pixel GT via oracle_bbox.project_object, with the four permanence stressors
baked in — occlusion (static AABB occluder), scale change (camera descent),
same-class distractor proximity, and brief out-of-frame.

No renderer: the scorable artifact for the T1 gate is the GT label stream, not
RGB pixels (those are a T2 concern, when an appearance re-ID head needs real
crops). So this is pure stdlib + numpy and fully reproducible from a fixed seed.

On disk per clip:
    labels.jsonl   one JSON object per frame: {frame, t, objects:[{id,box,visible}]}
                   box is pixel [x1,y1,x2,y2] or null (out of frame)
    manifest.json  scenario params, intrinsics, sizes, occluders, stressor tags

Run the self-check:  .venv-ft/bin/python runners/sitl/clip_recorder.py
"""

import json
import os

import numpy as np

import oracle_bbox as ob


# --- scenarios: keyframes are (t_frac, N, E) for objects, (t_frac, alt_m) for
# camera altitude.  Linear interp between them — deterministic, no seed needed
# for GT (seed only drives downstream detection noise in the eval harness).
SCENARIOS = {
    # one rich clip carrying all four stressors (RQ-T1.3)
    "crossing_occlusion": {
        "n_frames": 200,
        "fps": 20,
        "seed": 0,
        "target_id": "van",
        # camera hovers above scene centre, descends 20→12 m (scale change)
        "alt_keys": [(0.0, 20.0), (1.0, 12.0)],
        "objects": {
            "van": [(0.0, -9.0, 0.0), (0.5, 0.0, 0.0), (1.0, 9.0, 2.5)],
            # same-class distractor crosses near the target mid-clip (proximity)
            "decoy": [(0.0, 6.0, -6.0), (0.5, 1.0, 1.0), (1.0, -6.0, 6.0)],
        },
        # a raised "overpass" slab the target passes under (occlusion):
        # AABB in NED metres ((N,E,D)_min, (N,E,D)_max), ~5 m above ground
        "occluders": [((1.0, -6.0, -6.0), (3.0, 6.0, -4.0))],
        "stressors": ["occlusion", "scale_change", "distractor_proximity",
                      "out_of_frame"],
    },
    # control: clean follow, no occluder, target stays framed
    "clean_follow": {
        "n_frames": 120,
        "fps": 20,
        "seed": 1,
        "target_id": "van",
        "alt_keys": [(0.0, 15.0), (1.0, 15.0)],
        "objects": {
            "van": [(0.0, -4.0, 0.0), (1.0, 4.0, 0.0)],
            "decoy": [(0.0, 5.0, 5.0), (1.0, 5.0, -5.0)],
        },
        "occluders": [],
        "stressors": [],
    },
}


def _interp(keys, t_frac):
    """Linear-interp keyframes [(t_frac, *vals)] at t_frac → tuple of vals."""
    ts = [k[0] for k in keys]
    cols = list(zip(*[k[1:] for k in keys]))
    return tuple(float(np.interp(t_frac, ts, col)) for col in cols)


def _to_xyxy(box):
    """oracle_bbox cx,cy,w,h dict → pixel [x1,y1,x2,y2]."""
    return [box["cx"] - box["w"] / 2, box["cy"] - box["h"] / 2,
            box["cx"] + box["w"] / 2, box["cy"] + box["h"] / 2]


def frames(scn):
    """Yield (frame_idx, t, [(obj_id, box_xyxy_or_None, visible)]) per frame."""
    n, fps = scn["n_frames"], scn["fps"]
    for i in range(n):
        tf = i / (n - 1) if n > 1 else 0.0
        alt = _interp(scn["alt_keys"], tf)[0]
        cam = (0.0, 0.0, -alt)             # camera above scene centre, nadir
        objs = []
        for oid, keys in scn["objects"].items():
            nN, eE = _interp(keys, tf)
            proj = ob.project_object(cam, (nN, eE, 0.0), 0.0, 0.0, 0.0,
                                     occluders=scn["occluders"] or None)
            if proj is None:
                objs.append((oid, None, False))      # out of frame
            else:
                objs.append((oid, _to_xyxy(proj), bool(proj["visible"])))
        yield i, i / fps, objs


def record_clip(name, out_dir):
    """Write labels.jsonl + manifest.json for scenario `name` under out_dir."""
    scn = SCENARIOS[name]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "labels.jsonl"), "w") as f:
        for i, t, objs in frames(scn):
            rec = {"frame": i, "t": round(t, 4),
                   "objects": [{"id": o, "box": b, "visible": v}
                               for o, b, v in objs]}
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    manifest = {
        "name": name, **scn,
        "intrinsics": {"IMG_W": ob.IMG_W, "IMG_H": ob.IMG_H,
                       "FOCAL_PX": ob.FOCAL_PX, "FOV_H_DEG": ob.FOV_H_DEG},
        "object_size_m": {"len": ob.TARGET_LEN_M, "wid": ob.TARGET_WID_M},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return out_dir


def load_clip(out_dir):
    """Read back (manifest, [frame_record,...])."""
    with open(os.path.join(out_dir, "manifest.json")) as f:
        manifest = json.load(f)
    recs = []
    with open(os.path.join(out_dir, "labels.jsonl")) as f:
        for line in f:
            recs.append(json.loads(line))
    return manifest, recs


def _center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def score_clip(clip_dir, timeout=30):
    """Run the memoryless-ByteTrack baseline over a clip and score the §6 suite.

    Lock policy (the baseline T2 must beat): acquire onto the track nearest the
    target's GT centre (the VLM anchor, simulated by oracle at acquisition);
    follow that track id while it survives; on loss, **event-triggered** re-acq
    to the track nearest the *last* predicted centre — appearance-blind, so a
    same-class distractor near the last position steals the lock (constraint #2).

    locked_id is recorded as the *GT identity* the locked track really overlaps
    (van/decoy/None) so id-switch and purity measure true-object flips.
    """
    import sys
    here = os.path.dirname(__file__)
    sys.path.insert(0, here)
    sys.path.insert(0, os.path.join(here, "..", ".."))
    from bytetrack import ByteTracker
    from grounding.contract import iou

    manifest, recs = load_clip(clip_dir)
    tgt_id = manifest["target_id"]
    tracker = ByteTracker()
    locked = None                       # current ByteTrack id we follow
    last_pred = None                    # last predicted centre (re-acq anchor)
    preds, gts, vis, locked_gt, correct = [], [], [], [], []

    for rec in recs:
        objs = {o["id"]: o for o in rec["objects"]}
        tgt = objs[tgt_id]
        gt_box, gt_vis = tgt["box"], tgt["visible"]
        dets = [{"cx": _center(o["box"])[0], "cy": _center(o["box"])[1],
                 "w": o["box"][2] - o["box"][0], "h": o["box"][3] - o["box"][1]}
                for o in rec["objects"] if o["box"] and o["visible"]]
        tracks = {t.id: t for t in tracker.update(dets)}

        if locked not in tracks:        # (re)acquire — event-triggered
            anchor = last_pred or (_center(gt_box) if gt_box and gt_vis else None)
            if tracks and anchor:
                locked = min(tracks, key=lambda i: (tracks[i].bbox["cx"] - anchor[0]) ** 2
                             + (tracks[i].bbox["cy"] - anchor[1]) ** 2)
            else:
                locked = None

        if locked in tracks:
            bb = tracks[locked].bbox
            pred = [bb["cx"] - bb["w"] / 2, bb["cy"] - bb["h"] / 2,
                    bb["cx"] + bb["w"] / 2, bb["cy"] + bb["h"] / 2]
            last_pred = _center(pred)
            # which real object is this track on? (max IoU to a GT box, >0)
            gtid = max((o["id"] for o in rec["objects"] if o["box"]),
                       key=lambda oid: iou(pred, objs[oid]["box"]), default=None)
            if gtid is not None and iou(pred, objs[gtid]["box"]) <= 0:
                gtid = None
        else:
            pred, gtid = None, None

        preds.append(pred)
        gts.append(gt_box if gt_vis else None)
        vis.append(gt_vis)
        locked_gt.append(gtid)
        correct.append(gtid == tgt_id and gt_box is not None
                       and pred is not None and iou(pred, gt_box) >= 0.25)

    return assemble_scores(manifest["name"], tgt_id, preds, gts, vis,
                           locked_gt, correct, timeout)


def assemble_scores(name, tgt_id, preds, gts, vis, locked_gt, correct, timeout=30):
    """Run the §6 suite over per-frame streams → a scores dict (policy-agnostic)."""
    from grounding.contract import (sot_success, sot_precision, sot_success_auc,
                                    oracle_coverage, following_error,
                                    count_id_switches, identity_purity,
                                    reacquisition_frames, track_loss_events)
    reacq = reacquisition_frames(vis, correct)
    ok_reacq = [r for r in reacq if r is not None]
    return {
        "clip": name,
        "frames": len(preds),
        "sot_success": round(sot_success(preds, gts), 4),
        "sot_precision": round(sot_precision(preds, gts), 4),
        "sot_success_auc": round(sot_success_auc(preds, gts), 4),
        "oracle_coverage": round(oracle_coverage(preds, gts), 4),
        "following_error_px": (round(fe, 2) if (fe := following_error(preds, gts)) else None),
        "id_switches": count_id_switches(locked_gt),
        "identity_purity": round(identity_purity(locked_gt, tgt_id), 4),
        "reacq_events": len(reacq),
        "reacq_failed": sum(1 for r in reacq if r is None),
        "reacq_mean_frames": (round(sum(ok_reacq) / len(ok_reacq), 1) if ok_reacq else None),
        "track_loss_events": track_loss_events(vis, correct, timeout),
    }


# ponytail: GT is deterministic (no RNG); seed lives in the manifest for the
# downstream eval harness's detection noise, not for the recorder itself.
def _test_reproducible():
    import tempfile, filecmp
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a"), os.path.join(d, "b")
        record_clip("crossing_occlusion", a)
        record_clip("crossing_occlusion", b)
        assert filecmp.cmp(os.path.join(a, "labels.jsonl"),
                           os.path.join(b, "labels.jsonl"), shallow=False), \
            "labels.jsonl not byte-identical across re-runs"
        print("  reproducibility test PASS (labels byte-identical)")


def _test_stressors_present():
    """The rich clip must actually contain its four stressors at measurable severity."""
    scn = SCENARIOS["crossing_occlusion"]
    recs = [(i, t, objs) for i, t, objs in frames(scn)]
    tgt = scn["target_id"]

    def tobj(objs):
        return next(o for o in objs if o[0] == tgt)

    # occlusion: some frames where target is in-frame but visible=False
    occluded = sum(1 for _, _, objs in recs
                   if tobj(objs)[1] is not None and not tobj(objs)[2])
    assert occluded > 0, "no occluded frames"

    # out-of-frame: some frames where target box is None
    oof = sum(1 for _, _, objs in recs if tobj(objs)[1] is None)
    assert oof > 0, "no out-of-frame frames"

    # scale change: target box area grows as camera descends
    areas = [((b := tobj(objs)[1]) and (b[2] - b[0]) * (b[3] - b[1]))
             for _, _, objs in recs if tobj(objs)[1] is not None]
    assert max(areas) > 1.5 * min(areas), "scale change too small"

    # distractor proximity: target & decoy centres come within ~1 box width
    def ctr(b):
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    min_gap = min(
        (abs(ctr(tobj(objs)[1])[0] - ctr(d[1])[0]) ** 2
         + abs(ctr(tobj(objs)[1])[1] - ctr(d[1])[1]) ** 2) ** 0.5
        for _, _, objs in recs
        if tobj(objs)[1] is not None
        and (d := next(o for o in objs if o[0] == "decoy"))[1] is not None)
    assert min_gap < 60.0, f"distractor never close (min gap {min_gap:.0f}px)"

    print(f"  stressors test PASS  (occluded={occluded}f, oof={oof}f, "
          f"area×{max(areas)/min(areas):.1f}, min_gap={min_gap:.0f}px)")


def _test_perfect_tracker_scores():
    """Oracle dets → ByteTracker should perfectly cover co-present frames."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from bytetrack import ByteTracker
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from grounding.contract import oracle_coverage, sot_success

    scn = SCENARIOS["clean_follow"]
    tracker = ByteTracker()
    preds, gts = [], []
    for _, _, objs in frames(scn):
        tgt = next(o for o in objs if o[0] == scn["target_id"])
        dets = [{"cx": (b[0] + b[2]) / 2, "cy": (b[1] + b[3]) / 2,
                 "w": b[2] - b[0], "h": b[3] - b[1]}
                for _, b, vis in objs if b is not None and vis]
        tracks = tracker.update(dets)
        # pick the track nearest the target GT centre (oracle association)
        if tgt[1] is not None and tracks:
            tcx, tcy = (tgt[1][0] + tgt[1][2]) / 2, (tgt[1][1] + tgt[1][3]) / 2
            best = min(tracks, key=lambda tr: (tr.bbox["cx"] - tcx) ** 2
                       + (tr.bbox["cy"] - tcy) ** 2)
            bb = best.bbox
            preds.append([bb["cx"] - bb["w"] / 2, bb["cy"] - bb["h"] / 2,
                          bb["cx"] + bb["w"] / 2, bb["cy"] + bb["h"] / 2])
        else:
            preds.append(None)
        gts.append(tgt[1])

    cov = oracle_coverage(preds, gts)
    succ = sot_success(preds, gts)
    assert cov > 0.9, f"oracle coverage low ({cov:.2f})"
    assert succ > 0.9, f"SOT success low ({succ:.2f})"
    print(f"  perfect-tracker test PASS  (coverage={cov:.2f}, sot_success={succ:.2f})")


def _test_metrics_discriminate():
    """The §6 suite must detect the memoryless failure on the occlusion clip."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        record_clip("crossing_occlusion", d)
        s = score_clip(d)
    # a clean control would score ~perfect; the occlusion+distractor clip must
    # register the permanence failure on at least one identity metric
    assert s["id_switches"] >= 1 or s["identity_purity"] < 1.0 \
        or s["oracle_coverage"] < 1.0, f"metrics blind to failure: {s}"
    print(f"  discrimination test PASS  (id_switches={s['id_switches']}, "
          f"purity={s['identity_purity']}, coverage={s['oracle_coverage']})")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--emit":
        for name in SCENARIOS:
            print("wrote", record_clip(name, os.path.join(sys.argv[2], name)))
        raise SystemExit
    if len(sys.argv) == 3 and sys.argv[1] == "--score":
        print(json.dumps(score_clip(sys.argv[2]), indent=2))
        raise SystemExit
    print("clip_recorder unit tests:")
    _test_reproducible()
    _test_stressors_present()
    _test_perfect_tracker_scores()
    _test_metrics_discriminate()
    print("all clip_recorder tests passed")
