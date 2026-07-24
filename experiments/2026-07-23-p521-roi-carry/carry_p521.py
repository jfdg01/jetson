"""P5.21 -- ROI-crop + lanczos re-anchor carry vs plain SAM2 carry, paired.

RQ-P5.21: does the ROI-crop + lanczos re-anchor lever (adopted for anchor prefill
on a per-frame-IoU argument, never tested as an *outcome* contrast) actually beat
plain SAM2 carry on hard-carry UAV123 sequences? This closes the last non-capacity
carry lever (bigger SAM2 is already dead, P5.20).

Frozen design + gate: this campaign's README.md (read it). Exact two-sided McNemar,
deflated to distinct UAV123 source sequences (strip ``_s``), Part-V Holm; b+c >= 6
one-directional; directional expectation b(ROI-pass, plain-fail) > c.

Arms (both GT-frame-0 seeded -- no VLM *acquire*; this is what the pre-reg means by
"no VLM in the loop"):
  A = plain  : ``StreamCarry`` 1024-eager, ``prune_after=32`` (R-16 OOM ring), carry
               to the end, no re-ground.
  B = roi    : same carry, plus a periodic ROI-crop re-anchor -- crop the deployed
               ROI window around the current predicted box, lanczos-upscale to 512,
               ground the target caption, map the box back, reseed the carry
               (``select_p55.roi_reanchor``, MARGIN 2.0 / RES 512 / LANCZOS4). A
               drift-reinforcement guard skips (clamps) the crop when the predicted
               box has clearly drifted (area-ratio / displacement), so the crop is
               not taken around a wrong location.

Per-seq PASS = final-frame track IoU >= 0.25 vs GT (the carry survived to the end).

Machine of every number (thesis premise is edge deployment -- state it):
  - SAM2 carry: RTX-3090. Timing is NOT claimed on-device (E1 verified on-device
    mask parity; the rate here is a 3090 rate).
  - Arm-B ROI re-anchor grounding: Jetson Orin Nano 8GB via ``JetsonBackend`` over
    SSH on the deployed q8_0 GGUF (on-device VLM discipline). The crop is fed
    unresized (<=512 < the backend max_side).
  - Per-seq PASS / McNemar b,c / deflated p: machine = "both" (3090 carry + on-device
    VLM re-anchor for Arm B; Arm A and the pilot are pure 3090).

Reuse (signatures confirmed):
  - StreamCarry(predictor, first_frame, box, prune_after)  -- stream_carry.py:65
  - roi_reanchor(frame_bgr, prior_box, caption, submit_img) -- select_p55.py:92
  - replay_source.iou / load_uav123_gt                      -- replay_source.py:71,86
  - grounding.stats Claim / evaluate / discordant_counts / mcnemar (deflated verdict)

Run for real (deferred -- executed later on the main thread, NOT here):
    .venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/carry_p521.py \
        pilot  --bank experiments/2026-07-23-p521-roi-carry/bank.json --out runs/p521
    .venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/carry_p521.py \
        matrix --bank experiments/2026-07-23-p521-roi-carry/bank.json \
               --arms plain,roi --prune-after 32 --out runs/p521
    .venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/carry_p521.py \
        verdict --out runs/p521

Pure-logic self-check (no GPU / dataset / Jetson / CARLA -- heavy imports are guarded
inside the run paths):
    .venv-ft/bin/python experiments/2026-07-23-p521-roi-carry/carry_p521.py --selftest
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
for _p in (str(E18), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Light-only reuse: replay_source pulls cv2/numpy (CPU, no GPU); grounding.stats
# pulls scipy only. Neither imports torch/SAM2/CARLA, so --selftest stays pure.
from replay_source import iou, load_uav123_gt                     # noqa: E402
from grounding.stats import (                                     # noqa: E402
    Claim, discordant_counts, evaluate, mcnemar,
)

MACHINE = ("SAM2 carry=RTX-3090 (timing not claimed on-device); "
           "Arm-B ROI re-anchor VLM=Jetson-Orin-Nano-8GB via JetsonBackend; "
           "per-seq PASS/McNemar=both")

PRUNE_AFTER = 32          # R-16: the deployed ring OOM-kills at 100 with n>=2 + VLM.
REANCHOR_STRIDE = 90      # re-anchor every ~90 carry frames (P5.5 idle-round cadence).
IOU_PASS = 0.25           # final-frame track PASS threshold.

# Drift-reinforcement guard thresholds (clamp the crop when the predicted box has
# clearly drifted from the last accepted box). Cropping around a drifted box grounds
# whatever is at the wrong location and reinforces the drift; skipping keeps the
# SAM2 carry, which may recover on its own.
AREA_LO, AREA_HI = 0.4, 2.5     # mask collapse / bloat band on area ratio.
DISP_MAX = 1.5                  # center moved > DISP_MAX * prior box size => drifted.
# A re-anchor that JUMPS the box farther than this from the prior accepted box is
# flagged as a candidate drift-reinforcement (grounded a different object); counted
# c-side in the verdict.
REINFORCE_DISP = 1.5

ARMS = ("plain", "roi")


# --------------------------------------------------------------------------- #
# pure box / drift geometry (testable without torch, cv2, or a dataset)
# --------------------------------------------------------------------------- #
def _center(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _size(b):
    return max(1.0, b[2] - b[0], b[3] - b[1])


def area_ratio(prior, cur):
    return _area(cur) / max(1.0, _area(prior))


def displacement_ratio(prior, cur):
    (px, py), (cx, cy) = _center(prior), _center(cur)
    return math.hypot(cx - px, cy - py) / _size(prior)


def drift_guard(prior_box, cur_box, *, area_lo=AREA_LO, area_hi=AREA_HI,
                disp_max=DISP_MAX):
    """Clamp decision for one re-anchor round.

    Returns (do_reanchor, drifted, reason). If the current predicted box has
    clearly drifted from the last accepted box -- mask area collapsed/bloated,
    or the center moved more than `disp_max` box-sizes -- the crop is skipped
    (do_reanchor=False) so it is not taken around a wrong location.
    """
    ar = area_ratio(prior_box, cur_box)
    if ar < area_lo or ar > area_hi:
        return False, True, f"area_ratio={ar:.2f}"
    dr = displacement_ratio(prior_box, cur_box)
    if dr > disp_max:
        return False, True, f"disp_ratio={dr:.2f}"
    return True, False, "ok"


def final_pass(final_box, gt_final, *, thr=IOU_PASS):
    """Per-seq PASS rule: the final-frame track box overlaps GT at >= thr.

    A lost track (final_box None) or an absent GT final frame is a FAIL.
    """
    if final_box is None or gt_final is None:
        return False
    return iou(final_box, gt_final) >= thr


def source_id(seq: str) -> str:
    """Distinct-source key: UAV123 sub-clips carry a trailing ``_s`` (car1_s is a
    slice of the car1 source). Strip it so the McNemar n_effective counts sources,
    not slices (deflation unit)."""
    return seq[:-2] if seq.endswith("_s") else seq


def distinct_sources(seqs) -> int:
    return len({source_id(s) for s in seqs})


# --------------------------------------------------------------------------- #
# one arm over one sequence -- dependency-injected so it is pure-testable
# --------------------------------------------------------------------------- #
def run_arm(arm, seed_idx, seed_box, caption, indices, reanchor_frames, gt_final,
            *, carry_factory, reanchor_fn, frame_rgb_at, frame_bgr_at,
            guard=drift_guard, thr=IOU_PASS):
    """Carry one sequence under one arm and score the final frame.

    `carry_factory(frame_rgb, box)` -> object with `.step(frame_rgb) -> (mask, box)`.
    `reanchor_fn(frame_bgr, prior_box, caption)` -> (new_box | None, dbg).
    `frame_rgb_at(i)` / `frame_bgr_at(i)` fetch frames. Only arm=='roi' re-anchors;
    arm=='plain' never calls `reanchor_fn`. Returns a per-seq result dict.
    """
    assert arm in ARMS, arm
    carry = carry_factory(frame_rgb_at(seed_idx), seed_box)
    prior_accepted = seed_box
    box = seed_box
    drift_reinforced = False
    reanchors = []
    for i in indices:
        _, box = carry.step(frame_rgb_at(i))
        if arm == "roi" and i in reanchor_frames and box is not None:
            do_re, drifted, reason = guard(prior_accepted, box)
            rec = {"frame": i, "drifted": drifted, "clamped": not do_re,
                   "reason": reason}
            if do_re:
                new_box, _dbg = reanchor_fn(frame_bgr_at(i), box, caption)
                rec["accepted"] = new_box is not None
                if new_box is not None:
                    if displacement_ratio(prior_accepted, new_box) > REINFORCE_DISP:
                        drift_reinforced = True
                        rec["reinforced"] = True
                    carry = carry_factory(frame_rgb_at(i), new_box)
                    box = new_box
                    prior_accepted = new_box
            else:
                rec["accepted"] = False
            reanchors.append(rec)
    final_box = box                       # box at the last processed frame (None = lost)
    fiou = (iou(final_box, gt_final)
            if final_box is not None and gt_final is not None else 0.0)
    return {
        "arm": arm,
        "final_box": None if final_box is None else [round(v, 1) for v in final_box],
        "final_iou": round(fiou, 4),
        "pass": bool(final_pass(final_box, gt_final, thr=thr)),
        "reanchors": reanchors,
        "drift_reinforced": drift_reinforced,
    }


# --------------------------------------------------------------------------- #
# paired verdict -- reuse Claim/evaluate for the deflated McNemar
# --------------------------------------------------------------------------- #
def compute_verdict(plain_outcomes, roi_outcomes, drift_reinforced=None):
    """Paired McNemar with README orientation: b = ROI-pass & plain-fail (good),
    c = ROI-fail & plain-pass (bad = drift-reinforcement candidates). Deflates b/c
    to the number of distinct UAV123 source sequences via grounding.stats.evaluate.
    """
    shared = sorted(set(plain_outcomes) & set(roi_outcomes))
    # discordant_counts(a, b): b=a&!b, c=!a&b. Pass a=roi, b=plain so
    # b = roi-pass & plain-fail, c = roi-fail & plain-pass (README convention).
    b, c, n_pairs = discordant_counts(roi_outcomes, plain_outcomes)
    n_eff = distinct_sources(shared)
    claim = Claim(
        id="P5.21", part="V", headline="ROI-carry vs plain SAM2 carry",
        design="paired-binary", verdict="TBD", n_rows=n_pairs, n_effective=n_eff,
        independence_note=("distinct UAV123 source sequences (strip _s); slices of "
                           "one source are not independent trials"),
        data_status="counts_only", machine="both",
        counts={"b": b, "c": c, "n": n_pairs},
    )
    outcome = evaluate(claim)
    dr = drift_reinforced or {}
    c_side = [s for s in shared if roi_outcomes[s] == 0 and plain_outcomes[s] == 1]
    c_drift = sum(1 for s in c_side if dr.get(s))
    p_def = outcome.p_value
    reject = (p_def == p_def and p_def <= 0.05 and (b + c) >= 6 and b > c)
    return {
        "b": b, "c": c, "n_pairs": n_pairs, "n_effective": n_eff,
        "p_deflated": p_def, "p_raw": mcnemar(b, c),
        "reading": outcome.reading, "reject_h0": bool(reject),
        "plain_pass": sum(plain_outcomes[s] for s in shared),
        "roi_pass": sum(roi_outcomes[s] for s in shared),
        "c_side_seqs": c_side, "c_side_drift_reinforced": c_drift,
    }


# --------------------------------------------------------------------------- #
# real run paths (heavy imports guarded inside -- deferred, not run in --selftest)
# --------------------------------------------------------------------------- #
def load_bank(bank_path: Path):
    """Bank JSON: {"sequences": [{"seq": "car1_s", "caption": "the car"}, ...]}.

    Resolves each sequence's frames + GT, seed = first valid GT frame, final =
    last valid GT frame. Returns [{seq, caption, seq_dir, paths, gt, seed_idx,
    final_idx, seed_box}].
    """
    import cv2  # noqa: F401  (kept explicit so a missing-frames bank fails loud)

    data = E18 / "data" / "UAV123"
    spec = json.loads(Path(bank_path).read_text())["sequences"]
    out = []
    for e in spec:
        seq = e["seq"]
        seq_dir = data / "data_seq" / "UAV123" / seq
        paths = sorted(seq_dir.glob("*.jpg"))
        assert paths, f"no frames for {seq} under {seq_dir}"
        gt = load_uav123_gt(data / "anno" / "UAV123" / f"{seq}.txt")
        valid = [i for i, g in enumerate(gt) if g is not None and i < len(paths)]
        assert valid, f"{seq}: no valid GT frames"
        seed_idx, final_idx = valid[0], valid[-1]
        out.append({
            "seq": seq, "caption": e["caption"], "seq_dir": str(seq_dir),
            "paths": paths, "gt": gt, "seed_idx": seed_idx,
            "final_idx": final_idx, "seed_box": tuple(gt[seed_idx]),
        })
    return out


def _frame_accessors(paths):
    """(frame_rgb_at, frame_bgr_at) reading UAV123 jpgs on demand from the 3090 host."""
    import cv2

    def bgr(i):
        return cv2.imread(str(paths[min(i, len(paths) - 1)]))

    def rgb(i):
        import numpy as np
        return np.ascontiguousarray(bgr(i)[:, :, ::-1])

    return rgb, bgr


def _run_seq(arm, entry, *, carry_factory, reanchor_fn, out_dir: Path):
    """Run one arm over one bank sequence and persist results.json + a final-frame
    overlay PNG (GT green / pred red) so the carry is visually verifiable."""
    import cv2

    rgb_at, bgr_at = _frame_accessors(entry["paths"])
    seed_idx, final_idx = entry["seed_idx"], entry["final_idx"]
    reanchor_frames = set(range(seed_idx + REANCHOR_STRIDE, final_idx,
                                REANCHOR_STRIDE))
    res = run_arm(arm, seed_idx, entry["seed_box"], entry["caption"],
                  range(seed_idx + 1, final_idx + 1), reanchor_frames,
                  entry["gt"][final_idx], carry_factory=carry_factory,
                  reanchor_fn=reanchor_fn, frame_rgb_at=rgb_at,
                  frame_bgr_at=bgr_at)
    out = {"experiment": "P5.21", "arm": arm, "seq": entry["seq"],
           "source": source_id(entry["seq"]), "caption": entry["caption"],
           "seed_idx": seed_idx, "final_idx": final_idx,
           "prune_after": PRUNE_AFTER, "reanchor_stride": REANCHOR_STRIDE,
           "machine": MACHINE, **res}
    d = out_dir / f"{arm}_{entry['seq']}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps(out, indent=2))
    # look-at-it: overlay the final GT/pred on the final frame, not frame 0.
    frame = bgr_at(final_idx)
    gtf = entry["gt"][final_idx]
    if gtf is not None:
        cv2.rectangle(frame, (int(gtf[0]), int(gtf[1])), (int(gtf[2]), int(gtf[3])),
                      (0, 255, 0), 2)
    if res["final_box"] is not None:
        fb = res["final_box"]
        cv2.rectangle(frame, (int(fb[0]), int(fb[1])), (int(fb[2]), int(fb[3])),
                      (0, 0, 255), 2)
    cv2.imwrite(str(d / "final_overlay.png"), frame)
    print(f"[P5.21 {arm} {entry['seq']}] pass={res['pass']} "
          f"final_iou={res['final_iou']} reanchors={len(res['reanchors'])} "
          f"drift_reinforced={res['drift_reinforced']}", flush=True)
    return out


def _build_predictor(prune_after):
    """Load SAM2 once on the 3090; return (predictor, carry_factory)."""
    import torch  # noqa: F401
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    sys.path.insert(0, str(REPO / "experiments" / "2026-07-01-temporal-acquire-carry"))
    from stream_carry import MODEL, StreamCarry

    predictor = SAM2VideoPredictor.from_pretrained(MODEL)

    def carry_factory(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box, prune_after=prune_after)

    return predictor, carry_factory


def _jetson_reanchor_fn():
    """(reanchor_fn, close) -- boot the on-device VLM (JetsonBackend) and wrap
    select_p55.roi_reanchor to ground each crop on the Orin. VLM discipline: this
    is the ONLY grounding call and it goes to the Jetson, never the local 3090."""
    import time

    import cv2

    sys.path.insert(0, str(REPO / "experiments" / "2026-07-14-select-generalization"))
    from replay_e24 import MAX_SIDE, vlm_acquire
    from select_p55 import roi_reanchor
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    print("[P5.21] booting Jetson q8_0 for Arm-B ROI re-anchor...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_img(img_bgr, caption):
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/p521_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img_bgr)
        try:
            return vlm_acquire(be, path, caption, w, h)
        finally:
            Path(path).unlink(missing_ok=True)

    def reanchor_fn(frame_bgr, prior_box, caption):
        return roi_reanchor(frame_bgr, prior_box, caption, submit_img)

    return reanchor_fn, be.close


def run_pilot(bank_path, out_dir: Path):
    """Plain-carry base rate on the hard-carry bank (S2 headroom check). The gate
    is locked only if 0 < rate < 1; ceiling => bank too easy, floor => too hard."""
    import torch

    out_dir.mkdir(parents=True, exist_ok=True)
    bank = load_bank(bank_path)
    _, carry_factory = _build_predictor(PRUNE_AFTER)

    def no_reanchor(*_a):
        raise AssertionError("plain arm must not re-anchor")

    passes = 0
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        for e in bank:
            r = _run_seq("plain", e, carry_factory=carry_factory,
                         reanchor_fn=no_reanchor, out_dir=out_dir / "pilot")
            passes += r["pass"]
    n = len(bank)
    rate = passes / n if n else 0.0
    head = "HEADROOM OK" if 0 < passes < n else (
        "CEILING -- bank too easy, harden before locking" if passes == n
        else "FLOOR -- bank too hard, ease before locking")
    print(f"\n[P5.21 pilot] machine: SAM2 carry=RTX-3090")
    print(f"[P5.21 pilot] plain base rate {passes}/{n} = {rate:.2f}  -> {head}")
    (out_dir / "pilot.json").write_text(json.dumps(
        {"plain_pass": passes, "n": n, "rate": rate, "headroom": head,
         "machine": MACHINE}, indent=2))
    return passes, n


def run_matrix(bank_path, out_dir: Path, arms, prune_after):
    """Paired matrix: both arms over every bank sequence (skips existing cells)."""
    import torch

    out_dir.mkdir(parents=True, exist_ok=True)
    bank = load_bank(bank_path)
    _, carry_factory = _build_predictor(prune_after)
    reanchor_fn, close = (None, lambda: None)
    if "roi" in arms:
        reanchor_fn, close = _jetson_reanchor_fn()

    def no_reanchor(*_a):
        raise AssertionError("plain arm must not re-anchor")

    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            for e in bank:
                for arm in arms:
                    if (out_dir / f"{arm}_{e['seq']}" / "results.json").exists():
                        print(f"[P5.21] skip {arm}_{e['seq']} (exists)")
                        continue
                    fn = reanchor_fn if arm == "roi" else no_reanchor
                    _run_seq(arm, e, carry_factory=carry_factory,
                             reanchor_fn=fn, out_dir=out_dir)
    finally:
        close()


def run_verdict(out_dir: Path):
    """Read the matrix results and print the paired McNemar verdict."""
    plain, roi, dr = {}, {}, {}
    for p in sorted(out_dir.glob("*/results.json")):
        if p.parent.name.startswith("pilot"):
            continue
        r = json.loads(p.read_text())
        seq, arm = r["seq"], r["arm"]
        (plain if arm == "plain" else roi)[seq] = int(r["pass"])
        if arm == "roi":
            dr[seq] = bool(r.get("drift_reinforced"))
    v = compute_verdict(plain, roi, dr)
    print(f"[P5.21 verdict] machine: {MACHINE}")
    print(f"[P5.21 verdict] plain {v['plain_pass']}/{v['n_pairs']}  "
          f"roi {v['roi_pass']}/{v['n_pairs']}  (n_pairs={v['n_pairs']}, "
          f"n_effective={v['n_effective']} distinct sources)")
    print(f"[P5.21 verdict] McNemar b(ROI-pass,plain-fail)={v['b']}  "
          f"c(ROI-fail,plain-pass)={v['c']}")
    print(f"[P5.21 verdict] p_raw={v['p_raw']:.5g}  p_deflated={v['p_deflated']:.5g}")
    print(f"[P5.21 verdict] c-side drift-reinforcement failures: "
          f"{v['c_side_drift_reinforced']}/{len(v['c_side_seqs'])} "
          f"({v['c_side_seqs']})")
    print(f"[P5.21 verdict] reading: {v['reading']}")
    tag = "WIN [ROI-carry beats plain]" if v["reject_h0"] else (
        "TIE [measured negative -- closes the last non-capacity carry lever]")
    print(f"[P5.21 verdict] {tag}")
    (out_dir / "verdict.json").write_text(json.dumps(v, indent=2))
    return v


# --------------------------------------------------------------------------- #
# pure-logic self-check (no GPU / dataset / Jetson / CARLA)
# --------------------------------------------------------------------------- #
def selftest() -> None:
    SEED = (100.0, 100.0, 120.0, 120.0)
    GT_FINAL = SEED
    GOOD = (99.0, 99.0, 121.0, 121.0)         # re-anchor recovers ~on target
    FAR = (0.0, 0.0, 20.0, 20.0)              # re-anchor grounds a distractor
    DRIFTED = (0.0, 0.0, 5.0, 5.0)            # plain carry wanders here

    # (1) IoU@0.25 classification + final-frame PASS rule.
    assert iou(SEED, SEED) == 1.0
    assert iou(SEED, FAR) < IOU_PASS
    assert final_pass(SEED, GT_FINAL) is True
    assert final_pass(FAR, GT_FINAL) is False
    assert final_pass(None, GT_FINAL) is False          # lost track = fail
    assert final_pass(SEED, None) is False              # absent GT = fail
    # a box that just clears the 0.25 boundary passes; just under fails.
    over = (100.0, 100.0, 133.0, 133.0)   # iou(over,SEED)=400/1089=0.367 >= .25
    assert iou(over, SEED) >= IOU_PASS and final_pass(over, GT_FINAL)

    # (2) drift-guard clamp decision.
    assert drift_guard(SEED, (101.0, 101.0, 121.0, 121.0))[0] is True   # small move
    assert drift_guard(SEED, (0.0, 0.0, 5.0, 5.0))[1] is True           # area collapse
    assert drift_guard(SEED, (0.0, 0.0, 80.0, 80.0))[1] is True         # area bloat
    assert drift_guard(SEED, (0.0, 0.0, 22.0, 22.0))[1] is True         # far center
    do, drifted, _ = drift_guard(SEED, (98.0, 102.0, 118.0, 122.0))
    assert do is True and drifted is False

    # (3) distinct source ids (deflation unit).
    assert source_id("car1_s") == "car1" and source_id("car2") == "car2"
    assert distinct_sources(["car1_s", "car2", "car3", "car3_s"]) == 3

    # --- stub carries + injected re-anchor (no torch / cv2) ----------------- #
    class ScriptCarry:
        """Returns a scripted box per .step, holding the last one past the end."""

        def __init__(self, boxes):
            self.boxes, self.i = list(boxes), 0

        def step(self, _frame):
            b = self.boxes[min(self.i, len(self.boxes) - 1)]
            self.i += 1
            return None, b

    idx = [1, 2, 3, 4]
    ra_frames = {2}
    rgb = bgr = lambda _i: None                                  # noqa: E731

    def boom(*_a):
        raise AssertionError("reanchor_fn must not be called")

    # (4) arm dispatch: plain NEVER re-anchors even when a re-anchor frame is due.
    plain_drift_factory = lambda _f, b: ScriptCarry(          # noqa: E731
        [SEED, SEED, DRIFTED, DRIFTED])
    rp = run_arm("plain", 0, SEED, "cap", idx, ra_frames, GT_FINAL,
                 carry_factory=plain_drift_factory, reanchor_fn=boom,
                 frame_rgb_at=rgb, frame_bgr_at=bgr)
    assert rp["reanchors"] == [] and rp["pass"] is False        # drifted -> fail

    # (5) roi arm recovers the drift (b-side: ROI passes where plain fails).
    def recover_factory(_f, b):
        return (ScriptCarry([SEED, SEED, DRIFTED, DRIFTED]) if b == SEED
                else ScriptCarry([b, b, b, b]))

    rr = run_arm("roi", 0, SEED, "cap", idx, ra_frames, GT_FINAL,
                 carry_factory=recover_factory,
                 reanchor_fn=lambda *_a: (GOOD, {}),
                 frame_rgb_at=rgb, frame_bgr_at=bgr)
    assert len(rr["reanchors"]) == 1 and rr["reanchors"][0]["accepted"]
    assert rr["reanchors"][0]["clamped"] is False
    assert rr["pass"] is True and rr["drift_reinforced"] is False

    # (6) guard clamps a drifted predicted box -> reanchor_fn NOT called.
    clamp_factory = lambda _f, b: ScriptCarry(                 # noqa: E731
        [SEED, DRIFTED, DRIFTED, DRIFTED])   # already drifted at the re-anchor frame
    rc = run_arm("roi", 0, SEED, "cap", idx, ra_frames, GT_FINAL,
                 carry_factory=clamp_factory, reanchor_fn=boom,
                 frame_rgb_at=rgb, frame_bgr_at=bgr)
    assert rc["reanchors"][0]["clamped"] is True
    assert rc["reanchors"][0]["accepted"] is False

    # (7) c-side drift-reinforcement: re-anchor jumps to a distractor -> roi fails
    #     where plain passes, flagged drift_reinforced.
    def reinforce_factory(_f, b):
        return ScriptCarry([SEED, SEED, SEED, SEED]) if b == SEED \
            else ScriptCarry([b, b, b, b])

    rp2 = run_arm("plain", 0, SEED, "cap", idx, ra_frames, GT_FINAL,
                  carry_factory=reinforce_factory, reanchor_fn=boom,
                  frame_rgb_at=rgb, frame_bgr_at=bgr)
    rr2 = run_arm("roi", 0, SEED, "cap", idx, ra_frames, GT_FINAL,
                  carry_factory=reinforce_factory,
                  reanchor_fn=lambda *_a: (FAR, {}),
                  frame_rgb_at=rgb, frame_bgr_at=bgr)
    assert rp2["pass"] is True and rr2["pass"] is False
    assert rr2["drift_reinforced"] is True

    # (8) McNemar wiring on synthetic per-seq outcomes, README orientation.
    #     b-side seq (carX): plain fail, roi pass; c-side (carY): plain pass, roi fail.
    v = compute_verdict({"carX": rp["pass"] * 1, "carY": rp2["pass"] * 1},
                        {"carX": rr["pass"] * 1, "carY": rr2["pass"] * 1},
                        {"carX": rr["drift_reinforced"],
                         "carY": rr2["drift_reinforced"]})
    assert (v["b"], v["c"]) == (1, 1), v
    assert v["c_side_seqs"] == ["carY"] and v["c_side_drift_reinforced"] == 1
    assert v["reject_h0"] is False                       # 2 discordants can't reach .05

    # (9) a decisive, reachable case rejects H0 (b=6, c=0, n_eff=6).
    six = {f"car{k}": 0 for k in range(6)}               # plain fails all six
    roi6 = {f"car{k}": 1 for k in range(6)}              # roi passes all six
    dec = compute_verdict(six, roi6)
    assert dec["b"] == 6 and dec["c"] == 0 and dec["n_effective"] == 6
    assert abs(dec["p_deflated"] - 2 * 0.5 ** 6) < 1e-12  # mcnemar(6,0)=0.03125
    assert dec["reject_h0"] is True

    # (10) deflation wiring: 12 slices over 6 sources, b=8 -> deflated to 4 -> p=0.125.
    seqs = [f"car{k}{sfx}" for k in range(1, 7) for sfx in ("", "_s")]
    assert distinct_sources(seqs) == 6
    plain12 = {s: (1 if i >= 8 else 0) for i, s in enumerate(seqs)}  # 8 fail, 4 pass
    roi12 = {s: 1 for s in seqs}                                     # roi passes all
    dfl = compute_verdict(plain12, roi12)
    assert (dfl["b"], dfl["c"]) == (8, 0) and dfl["n_effective"] == 6
    assert abs(dfl["p_raw"] - 2 * 0.5 ** 8) < 1e-12                  # undeflated
    assert abs(dfl["p_deflated"] - 0.125) < 1e-12                    # b 8->4, mcnemar(4,0)

    print("selftest OK")


# --------------------------------------------------------------------------- #
def main() -> None:
    if "--selftest" in sys.argv or (len(sys.argv) > 1 and sys.argv[1] == "selftest"):
        selftest()
        return

    ap = argparse.ArgumentParser(description="P5.21 ROI-carry vs plain carry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap.add_argument("--selftest", action="store_true", help="pure-logic checks, exit")

    sp = sub.add_parser("pilot", help="plain-carry base rate / S2 headroom check")
    sp.add_argument("--bank", required=True)
    sp.add_argument("--out", default="runs/p521")

    sm = sub.add_parser("matrix", help="paired plain+roi matrix over the bank")
    sm.add_argument("--bank", required=True)
    sm.add_argument("--arms", default="plain,roi")
    sm.add_argument("--prune-after", type=int, default=PRUNE_AFTER)
    sm.add_argument("--out", default="runs/p521")

    sv = sub.add_parser("verdict", help="paired McNemar + deflated p from results")
    sv.add_argument("--out", default="runs/p521")

    args = ap.parse_args()
    if args.cmd == "pilot":
        run_pilot(args.bank, Path(args.out))
    elif args.cmd == "matrix":
        arms = tuple(a.strip() for a in args.arms.split(",") if a.strip())
        assert all(a in ARMS for a in arms), arms
        run_matrix(args.bank, Path(args.out), arms, args.prune_after)
    elif args.cmd == "verdict":
        run_verdict(Path(args.out))


if __name__ == "__main__":
    main()
