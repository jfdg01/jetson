#!/usr/bin/env python3
"""Read the bank back the way a consumer would, and assert it is usable.

    .venv-ft/bin/python experiments/2026-07-21-carla-gt-bank/check_bank.py

Everything that has touched `runs/bank` so far was written by the code that
produced it, or reads a handful of frames out of it (`make_proof.py`). Nothing
has loaded a whole clip the way P6.2 will. That is the exact gap this campaign
already fell into once: the first bank passed every check in place at the time
-- correct actor counts, non-blank frames, non-identical frames -- and was 77-80%
empty of vehicles, because the checks verified the pixels were *valid* and not
that they were *useful*.

So this asserts the contract a consumer depends on, not that the files parse:
frame/GT alignment, no duplicate or missing indices, boxes inside the image,
and the anchor target actually present at the advertised rate. Collects every
violation rather than stopping at the first, then exits non-zero.

No server, no GPU: reads `runs/bank` only, so it is re-runnable at any time and
belongs to whoever inherits the bank rather than to the night that built it.
"""
import json
import sys
from pathlib import Path

BANK = Path(__file__).resolve().parent / "runs" / "bank"
W, H = 640, 480
SLACK = 2.0        # boxes may sit a hair outside after float projection


def check(d):
    m = json.loads((d / "manifest.json").read_text())
    gt = d / "gt.jsonl"
    if not gt.exists():
        return [f"{d.name}: no gt.jsonl (not committed -- recapture to check)"], 0, 0

    bad, idxs, tgt_seen, prev_on = [], [], 0, None
    n_box = n_deg = 0
    for line in gt.open():
        r = json.loads(line)
        i = r["i"]
        idxs.append(i)

        # a GT row is worthless without the frame it describes
        if not (d / "frames" / f"{i:05d}.jpg").exists():
            bad.append(f"{d.name}: frame {i:05d}.jpg missing for a GT row")

        on = [g for g in r["gt"] if g["box_vis"]]
        for g in on:
            x1, y1, x2, y2 = g["box_vis"]
            n_box += 1
            # Counted, not failed. These are edge slivers that were positive-area
            # before serialisation and collapsed at 2dp -- see the note in
            # carla_gt_bank._row, which now drops them at capture time. The bank
            # captured 2026-07-21 predates that fix and carries 19 of them in
            # 897 864 boxes, so this is a rate check, not a per-box assert.
            if x2 <= x1 or y2 <= y1:
                n_deg += 1
            elif (x1 < -SLACK or y1 < -SLACK or x2 > W + SLACK or y2 > H + SLACK):
                bad.append(f"{d.name}[{i}] id {g['id']}: box outside frame {g['box_vis']}")
        if any(g["id"] == m["target_id"] and g["box_vis"] for g in r["gt"]):
            tgt_seen += 1
        prev_on = len(on)

    # 1e-4 is ~5x the measured rate: tight enough that a real clipping regression
    # trips it, loose enough that the known artifact does not.
    if n_box and n_deg / n_box > 1e-4:
        bad.append(f"{d.name}: {n_deg}/{n_box} degenerate boxes "
                   f"({n_deg/n_box:.1e}) exceeds the 1e-4 edge-sliver tolerance")

    n = len(idxs)
    if sorted(idxs) != list(range(n)):
        bad.append(f"{d.name}: frame indices are not 0..{n-1} without gaps or repeats")
    if n != m["frames"]:
        bad.append(f"{d.name}: manifest says {m['frames']} frames, gt.jsonl has {n}")

    # the manifest is the only committed record, so it has to agree with the data
    frac = tgt_seen / n if n else 0.0
    if abs(frac - m.get("target_in_frame_frac", -1)) > 0.002:
        bad.append(f"{d.name}: target_in_frame_frac {m.get('target_in_frame_frac')} "
                   f"but recomputed {frac:.4f}")
    if m["coverage"] < 0.5:
        bad.append(f"{d.name}: coverage {m['coverage']:.3f} below the 0.5 floor")
    if prev_on == 0:
        bad.append(f"{d.name}: last frame has no on-screen vehicle")
    return bad, n_box, n_deg


def main():
    clips = sorted(BANK.glob("clip*"))
    if not clips:
        print("no bank on disk", file=sys.stderr)
        return 1
    fails, tot_box, tot_deg = [], 0, 0
    for d in clips:
        bad, n_box, n_deg = check(d)
        tot_box += n_box
        tot_deg += n_deg
        print(f"{d.name}: {'OK' if not bad else f'{len(bad)} PROBLEM(S)'}"
              f"  ({n_box} boxes, {n_deg} edge-sliver)")
        fails += bad
    if fails:
        print(f"\n{len(fails)} problem(s):", file=sys.stderr)
        for f in fails[:20]:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"\n{len(clips)} clips readable and self-consistent; "
          f"{tot_deg}/{tot_box} degenerate edge slivers "
          f"({tot_deg/tot_box:.1e}), under the 1e-4 tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
