#!/usr/bin/env python3
"""T2 — appearance-memory re-ID lock policy (object permanence mechanism).

The T1 memoryless baseline re-acquires by *nearest-to-last-position*, so after an
occlusion it re-locks whichever same-class object is closest — the decoy (constraint
#2). This policy stores the target's **appearance descriptor** at acquisition, matches
on it at re-acquisition, and **refuses to lock** when no candidate matches (waiting for
a future VLM re-anchor) instead of grabbing the wrong object.

Pixels aren't rendered yet (T1 decision), so appearance is modelled as a per-instance
scalar descriptor whose observation noise scales with crop size — smaller crop (longer
range) → noisier descriptor. That `snr` knob ties the mechanism directly to the T0d
separability-vs-range frontier: high SNR fixes the baseline failure, low SNR degrades
gracefully (refuse rather than mis-lock).

Run `.venv-ft/bin/python runners/sitl/reid_policy.py` for the self-checks, or
`--score <clip_dir> [--snr S]` to print scores.
"""
import json
import math
import os
import sys

import numpy as np

here = os.path.dirname(__file__)
sys.path.insert(0, here)
sys.path.insert(0, os.path.join(here, "..", ".."))

from clip_recorder import load_clip, assemble_scores, _center  # noqa: E402
from bytetrack import ByteTracker  # noqa: E402
from grounding.contract import iou  # noqa: E402

# Appearance model: each object has a fixed true descriptor in [0,1); two objects are
# ~SEP apart. Observation noise std scales inversely with sqrt(crop area).
AREA_REF = 3000.0       # px² — a nominal mid-range crop
SIGMA0 = 0.5            # descriptor noise std at snr=1 and area=AREA_REF
GATE = 0.5             # max descriptor distance to memory to accept a (re)lock
MEM_EMA = 0.1          # memory update rate while locked & correct-class


def _desc_map(recs):
    """Spread distinct objects evenly over [0,1] so distinct instances are separable
    (van vs decoy *are* different vehicles); within-class confusion is the noise term."""
    ids = sorted({o["id"] for r in recs for o in r["objects"]})
    n = max(len(ids) - 1, 1)
    return {oid: i / n for i, oid in enumerate(ids)}


def _observe(true_desc, obj_id, area, frame_idx, snr):
    """Noisy appearance reading; std grows as the crop shrinks (range proxy)."""
    std = SIGMA0 / (snr * math.sqrt(max(area, 1.0) / AREA_REF))
    rng = np.random.default_rng((hash(obj_id) ^ (frame_idx * 0x9E3779B1)) & 0xFFFFFFFF)
    return true_desc + float(rng.normal(0.0, std))


def score_clip_reid(clip_dir, snr=8.0, timeout=30):
    manifest, recs = load_clip(clip_dir)
    tgt_id = manifest["target_id"]
    desc = _desc_map(recs)
    tracker = ByteTracker()
    locked = None
    mem = None                              # stored target appearance descriptor
    preds, gts, vis, locked_gt, correct = [], [], [], [], []

    for fi, rec in enumerate(recs):
        objs = {o["id"]: o for o in rec["objects"]}
        tgt = objs[tgt_id]
        gt_box, gt_vis = tgt["box"], tgt["visible"]
        dets = [{"cx": _center(o["box"])[0], "cy": _center(o["box"])[1],
                 "w": o["box"][2] - o["box"][0], "h": o["box"][3] - o["box"][1]}
                for o in rec["objects"] if o["box"] and o["visible"]]
        tracks = {t.id: t for t in tracker.update(dets)}

        def obs(tid):
            """Observe the appearance of the object track `tid` is sitting on."""
            bb = tracks[tid].bbox
            pb = [bb["cx"] - bb["w"] / 2, bb["cy"] - bb["h"] / 2,
                  bb["cx"] + bb["w"] / 2, bb["cy"] + bb["h"] / 2]
            oid = max((o["id"] for o in rec["objects"] if o["box"]),
                      key=lambda i: iou(pb, objs[i]["box"]), default=None)
            if oid is None or iou(pb, objs[oid]["box"]) <= 0:
                return None
            ob = objs[oid]["box"]
            return _observe(desc[oid], oid, (ob[2] - ob[0]) * (ob[3] - ob[1]), fi, snr)

        # seed appearance memory the first time the target is locked-on-acquisition
        if mem is None and gt_box and gt_vis and tracks:
            anchor = _center(gt_box)
            cand = min(tracks, key=lambda i: (tracks[i].bbox["cx"] - anchor[0]) ** 2
                       + (tracks[i].bbox["cy"] - anchor[1]) ** 2)
            if iou(_xyxy(tracks[cand]), gt_box) >= 0.25:
                locked, mem = cand, obs(cand)

        if locked not in tracks and mem is not None:   # re-acquire by appearance
            best, best_d = None, GATE
            for tid in tracks:
                d = abs((o := obs(tid)) - mem) if obs(tid) is not None else None
                if o is not None and d < best_d:
                    best, best_d = tid, d
            locked = best                              # None ⇒ refuse, keep waiting

        if locked in tracks:
            bb = tracks[locked].bbox
            pred = [bb["cx"] - bb["w"] / 2, bb["cy"] - bb["h"] / 2,
                    bb["cx"] + bb["w"] / 2, bb["cy"] + bb["h"] / 2]
            gtid = max((o["id"] for o in rec["objects"] if o["box"]),
                       key=lambda oid: iou(pred, objs[oid]["box"]), default=None)
            if gtid is not None and iou(pred, objs[gtid]["box"]) <= 0:
                gtid = None
            if gtid == tgt_id and (o := obs(locked)) is not None:   # trust → refine
                mem = (1 - MEM_EMA) * mem + MEM_EMA * o
        else:
            pred, gtid = None, None

        preds.append(pred)
        gts.append(gt_box if gt_vis else None)
        vis.append(gt_vis)
        locked_gt.append(gtid)
        correct.append(gtid == tgt_id and gt_box is not None
                       and pred is not None and iou(pred, gt_box) >= 0.25)

    return assemble_scores(manifest["name"] + f"+reid@snr{snr:g}", tgt_id,
                           preds, gts, vis, locked_gt, correct, timeout)


def _xyxy(tr):
    bb = tr.bbox
    return [bb["cx"] - bb["w"] / 2, bb["cy"] - bb["h"] / 2,
            bb["cx"] + bb["w"] / 2, bb["cy"] + bb["h"] / 2]


# ---- self-checks -----------------------------------------------------------
def _clip_dir():
    d = os.path.join(here, "..", "..", "results",
                     "2026-06-18-t1-temporal-contract", "clips", "crossing_occlusion")
    assert os.path.isdir(d), f"missing clip set: {d} (run clip_recorder --emit first)"
    return d


def _test_beats_baseline_high_snr():
    """High SNR fixes the constraint-#2 failure: full purity, no wrong-object switch."""
    s = score_clip_reid(_clip_dir(), snr=8.0)
    assert s["identity_purity"] == 1.0, s          # baseline 0.725
    assert s["id_switches"] == 0, s                # baseline 1
    assert s["reacq_failed"] == 0, s               # baseline 1
    assert s["oracle_coverage"] >= 0.69, s         # baseline 0.575; ceiling = visible frac
    print(f"  high-SNR test PASS  (purity={s['identity_purity']}, "
          f"id_sw={s['id_switches']}, reacq_failed={s['reacq_failed']}, "
          f"coverage={s['oracle_coverage']})")


def _test_degrades_low_snr():
    """The benefit is separability-dependent (the T0d frontier). At a moderate SNR the
    gate still refuses the decoy (purity high, coverage between); at very low SNR the
    descriptor noise swamps the van/decoy gap and it degrades toward the baseline."""
    hi = score_clip_reid(_clip_dir(), snr=8.0)
    mid = score_clip_reid(_clip_dir(), snr=1.2)
    lo = score_clip_reid(_clip_dir(), snr=0.4)
    # monotone collapse of the headline (purity) as separability falls
    assert hi["identity_purity"] >= mid["identity_purity"] >= lo["identity_purity"], \
        (hi["identity_purity"], mid["identity_purity"], lo["identity_purity"])
    # very low SNR is no better than the memoryless baseline (≈0.725 purity)
    assert lo["identity_purity"] <= 0.78, lo
    print(f"  frontier test PASS  (purity snr8={hi['identity_purity']} → "
          f"snr1.2={mid['identity_purity']} → snr0.4={lo['identity_purity']})")


def _test_reproducible():
    a = score_clip_reid(_clip_dir(), snr=2.0)
    b = score_clip_reid(_clip_dir(), snr=2.0)
    assert a == b, (a, b)
    print("  reproducibility test PASS")


if __name__ == "__main__":
    if "--score" in sys.argv:
        d = sys.argv[sys.argv.index("--score") + 1]
        snr = float(sys.argv[sys.argv.index("--snr") + 1]) if "--snr" in sys.argv else 8.0
        print(json.dumps(score_clip_reid(d, snr=snr), indent=2))
    else:
        print("reid_policy unit tests:")
        _test_reproducible()
        _test_beats_baseline_high_snr()
        _test_degrades_low_snr()
        print("all reid_policy tests passed")
