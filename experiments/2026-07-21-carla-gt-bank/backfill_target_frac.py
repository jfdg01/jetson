#!/usr/bin/env python3
"""Add `target_in_frame_frac` to each clip manifest. Idempotent, re-runnable.

    .venv-ft/bin/python experiments/2026-07-21-carla-gt-bank/backfill_target_frac.py

`coverage` asserts that *a* vehicle is on screen. It does not assert that *the*
clip's anchor target is, and those come apart hard: on clip01 (`track_gain 0.0`,
fixed camera) coverage reads 100% while the anchor is in frame on a small
fraction of frames, because other traffic keeps driving through. That is a
legitimate regime -- it is exactly what the `gain 0.0` arm is for -- but a
downstream consumer picking a follow clip needs to see it before picking, and
`gt.jsonl` is not committed, so the manifest is the record.

Computed post-hoc rather than added to the capture loop on purpose: the bank was
already mid-run, and a mid-run code change would have given clips 05-24 the field
and clips 00-04 nothing.
"""
import json
import sys
from pathlib import Path

BANK = Path(__file__).resolve().parent / "runs" / "bank"


def main():
    mans = sorted(BANK.glob("clip*/manifest.json"))
    if not mans:
        print("no clips captured yet", file=sys.stderr)
        return 1
    for p in mans:
        m = json.loads(p.read_text())
        gt = p.parent / "gt.jsonl"
        if not gt.exists():
            print(f"{m['clip']}: no gt.jsonl, skipped")
            continue
        tid, n, seen = m.get("target_id"), 0, 0
        for line in gt.read_text().splitlines():
            n += 1
            if any(g["id"] == tid and g["box_vis"] for g in json.loads(line)["gt"]):
                seen += 1
        m["target_in_frame_frac"] = round(seen / n, 4) if n else 0.0
        p.write_text(json.dumps(m, indent=2))
        print(f"{m['clip']} gain {m['track_gain']:4.1f}  coverage {m['coverage']:6.1%}  "
              f"target in frame {m['target_in_frame_frac']:6.1%}  ({seen}/{n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
