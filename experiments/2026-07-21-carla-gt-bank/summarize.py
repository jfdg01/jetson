#!/usr/bin/env python3
"""Print one line per captured clip. Read-only, safe to run mid-capture."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else
            Path(__file__).resolve().parent / "runs" / "bank")
rows = []
for p in sorted(root.glob("clip*/manifest.json")):
    m = json.loads(p.read_text())
    rows.append(m)
    print(f"{m['clip']} alt{m['alt']:4.0f} gain{m['track_gain']:4.1f} "
          f"drift{m['drift_m']:4.0f}m cov {m['coverage']:6.1%} "
          f"onscreen {m['onscreen_mean']:5.2f} "
          f"tgt {m.get('target_in_frame_frac', float('nan')):6.1%} "
          f"{m['capture_hz']:5.1f}Hz "
          f"{m['frames']:5d}f {m['target_type']}")
if rows:
    print(f"-- {len(rows)} clips, mean cov "
          f"{sum(r['coverage'] for r in rows) / len(rows):.1%}, mean "
          f"{sum(r['capture_hz'] for r in rows) / len(rows):.1f} Hz, "
          f"{sum(r['frames'] for r in rows)} frames")
