#!/usr/bin/env python3
"""R-21 work queue — the MISLEADING/UNVERIFIED rows of the R-7 sweep, per file.

    .venv-ft/bin/python thesis/r21_queue.py                       # counts, all files
    .venv-ft/bin/python thesis/r21_queue.py docs/results/part5-anticipatory.md

`provenance-sweep.json` is frozen evidence and is never edited (see the header of
`make_provenance_sweep.py`). Rows therefore have no stored id; the id used here and
in `provenance-resolutions.json` is **positional** -- `<agent index>.<row index>` --
which is stable exactly because the file is frozen. If the sweep is ever re-run, the
resolutions file is invalidated with it, and that is the correct behaviour.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE_TAGS = ("MISLEADING", "UNVERIFIED")


def rows() -> list[dict]:
    data = json.loads((HERE / "provenance-sweep.json").read_text())
    return [dict(r, row_id=f"{ai}.{ri}")
            for ai, a in enumerate(data["agents"])
            for ri, r in enumerate(a["rows"])]


def resolutions() -> dict[str, dict]:
    p = HERE / "provenance-resolutions.json"
    return json.loads(p.read_text())["resolutions"] if p.exists() else {}


def main() -> None:
    queue = [r for r in rows() if r["tag"] in QUEUE_TAGS]
    done = resolutions()
    if len(sys.argv) < 2:
        by_file: dict[str, list[dict]] = {}
        for r in queue:
            by_file.setdefault(r["file"], []).append(r)
        for f, rs in sorted(by_file.items()):
            open_n = sum(1 for r in rs if r["row_id"] not in done)
            print(f"{open_n:3d} open / {len(rs):3d} total  {f}")
        print(f"\n{sum(1 for r in queue if r['row_id'] not in done)} open of {len(queue)}")
        return

    target = sys.argv[1]
    for r in queue:
        if r["file"] != target:
            continue
        state = done.get(r["row_id"])
        print(f"\n=== {r['row_id']}  [{r['tag']}]"
              f"{'  RESOLVED: ' + state['status'] if state else ''}")
        print(f"  published: {r['quoted']}")
        print(f"  claim:     {r.get('claim_id') or '-'}")
        print(f"  artifact:  {r['artifact']}")
        print(f"  says:      {r['artifact_value']}")
        print(f"  finding:   {r['note']}")


if __name__ == "__main__":
    main()
