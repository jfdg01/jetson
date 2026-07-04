"""E22 Phase 0 -- offline prior audit (MANDATORY GATE, no Jetson).

For each of the 6 clips, run the CPU prior at the frames a real run would submit at
(t=0 and, to sample a later REGROUND-era submit, t=10 s) and compare the proposed
3x3 cell to the GT cell (scope.hint_for on the GT box at that frame). `prev` is the
frame ~0.5 s (15 frames at 30 fps) before the submit frame (clamped to 0; when
submit_i == 0 the symmetric frame submit_i + 15 is used).

GATE: proceed to the Jetson matrix ONLY if the t=0 top-1 cell hit rate >= 4/6.
Below that, the campaign result is the documented negative "CPU prior insufficient
on this footage" (NO [prior-insufficient]) -- no Jetson legs.

Writes raw/phase0_prior_audit.txt (committed).

    .venv-ft/bin/python experiments/2026-07-04-cv-proposal-acquire/phase0.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
E20 = REPO / "experiments" / "2026-07-04-prompt-scoped-acquire"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(E18))
sys.path.insert(0, str(E20))

import proposals                                                     # noqa: E402
import scope                                                         # noqa: E402
from replay_source import load_uav123_gt                            # noqa: E402

DATA = E18 / "data" / "UAV123"
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]
PREV_LAG = 15   # ~0.5 s at 30 fps (README: prev is the frame before the submit)
SUBMITS = [(0, "t=0"), (300, "t=10s")]   # 300 = 10 s at 30 fps


def seq_dir(clip):
    return DATA / "data_seq" / "UAV123" / clip


def frames(clip):
    return sorted(seq_dir(clip).glob("*.jpg"))


def _stage_diag(clip, prev, cur, gt_box, w0):
    """D5 diagnosis: which stage emptied. Returns (motion_tot, color_tot,
    motion_inGT, color_inGT) at working width, sampled inside the GT box."""
    pw = proposals._work(prev)
    cw = proposals._work(cur)
    mm = proposals._motion_mask(pw, cw)
    cm = proposals._color_mask(cw, proposals.CLIP_KW[clip])
    s = proposals.WORK_W / w0
    if gt_box is None:
        gb = None
    else:
        gb = [int(gt_box[0] * s), int(gt_box[1] * s),
              int(gt_box[2] * s), int(gt_box[3] * s)]

    def insum(m):
        if gb is None:
            return 0
        sub = m[max(gb[1], 0):gb[3], max(gb[0], 0):gb[2]]
        return int(sub.sum() // 255) if sub.size else 0

    return (int(mm.sum() // 255), int(cm.sum() // 255), insum(mm), insum(cm))


def audit_one(clip, paths, gt, submit_i):
    """Run the prior at submit_i; return (hint, source, gt_hint, hit, diag)."""
    kw = proposals.CLIP_KW[clip]
    n = len(paths)
    si = min(submit_i, n - 1)
    prev_i = si - PREV_LAG if si - PREV_LAG >= 0 else si + PREV_LAG
    prev_i = min(max(prev_i, 0), n - 1)
    cur = cv2.imread(str(paths[si]))
    prev = cv2.imread(str(paths[prev_i]))
    h0, w0 = cur.shape[:2]
    hint, source = proposals.propose(prev, cur, kw)
    gt_box = gt[si] if si < len(gt) else None
    gt_hint = scope.hint_for(gt_box, w0, h0) if gt_box is not None else None
    hit = hint is not None and gt_hint is not None and hint == gt_hint
    diag = _stage_diag(clip, prev, cur, gt_box, w0)
    return hint, source, gt_hint, hit, diag


def main():
    lines = []
    lines.append("E22 Phase 0 -- offline CPU-prior audit (proposed cell vs GT cell)")
    lines.append(f"prev lag = {PREV_LAG} frames (~0.5 s); working width "
                 f"{proposals.WORK_W}; T={proposals.MOTION_T} area>={proposals.MIN_AREA}")
    lines.append("")
    hdr = f"{'clip':6} {'kw':7} | {'submit':7} {'proposed':14} {'source':13} {'GT':14} {'hit'}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    t0_hits = 0
    per_submit = {tag: 0 for _, tag in SUBMITS}
    diag_rows = []
    for clip in CLIPS:
        paths = frames(clip)
        gt = load_uav123_gt(DATA / "anno" / "UAV123" / f"{clip}.txt")
        for submit_i, tag in SUBMITS:
            hint, source, gt_hint, hit, diag = audit_one(clip, paths, gt, submit_i)
            if hit:
                per_submit[tag] += 1
                if tag == "t=0":
                    t0_hits += 1
            lines.append(f"{clip:6} {proposals.CLIP_KW[clip]:7} | {tag:7} "
                         f"{str(hint):14} {str(source):13} {str(gt_hint):14} "
                         f"{'HIT' if hit else 'miss'}")
            if tag == "t=0":
                diag_rows.append((clip, diag))
        lines.append("")
    # D5 stage diagnosis (which stage emptied) at the t=0 submit, GT-box sampled
    lines.append("Stage diagnosis at t=0 (working-width px; *_inGT = mask px inside the GT box):")
    dhdr = f"  {'clip':6} {'motion_tot':>10} {'color_tot':>9} {'motion_inGT':>11} {'color_inGT':>10}"
    lines.append(dhdr)
    for clip, (mt, ct, mg, cg) in diag_rows:
        lines.append(f"  {clip:6} {mt:>10} {ct:>9} {mg:>11} {cg:>10}")
    lines.append("")
    lines.append(f"t=0 top-1 cell hit rate  = {t0_hits}/6")
    lines.append(f"t=10s top-1 cell hit rate = {per_submit['t=10s']}/6")
    gate = t0_hits >= 4
    lines.append("")
    lines.append(f"GATE (t=0 >= 4/6): {'PASS -> run the Jetson matrix' if gate else 'FAIL -> NO [prior-insufficient], no Jetson legs'}")
    out = "\n".join(lines) + "\n"
    (HERE / "raw").mkdir(exist_ok=True)
    (HERE / "raw" / "phase0_prior_audit.txt").write_text(out)
    print(out)
    print("GATE PASS" if gate else "GATE FAIL")
    return gate


if __name__ == "__main__":
    main()
