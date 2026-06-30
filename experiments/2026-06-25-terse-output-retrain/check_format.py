"""Sanity: what format does the terse model ACTUALLY emit on real RefDrone images,
and how many decode tokens? The synthetic-frame measure showed '(x, y, x, y)' tuples
(21 tok) not bare 'x y x y' (≈15 tok) — check whether that holds on real data."""
import json
import sys

sys.path.insert(0, "runners")
import run_t0_cadence as t0  # noqa: E402
from parsers import parse_vlm_server_timings  # noqa: E402

from grounding.contract import parse_bbox  # noqa: E402
from grounding.data.refdrone import load_refdrone  # noqa: E402
from grounding.eval.backends import JetsonBackend  # noqa: E402

TERSE_MODEL = "/home/jfdg/grounding/phase3-terse-1024-q8_0.gguf"
TERSE_MMPROJ = "/home/jfdg/grounding/mmproj-phase3-terse-1024-f16.gguf"

samples = load_refdrone("val", max_samples=12)
backend = JetsonBackend(TERSE_MODEL, TERSE_MMPROJ, max_side=1024, startup_timeout_s=300)
rows = []
try:
    for s in samples:
        wall, raw = t0._timed_anchor_post(backend._base, s.image_path, s.caption, 1024)
        tm = parse_vlm_server_timings(raw)
        content = json.loads(raw)["choices"][0]["message"].get("content") or ""
        rows.append((tm.predicted_n if tm else -1, repr(content), parse_bbox(content) is not None))
finally:
    backend.close()

print(f"{'dec_tok':>7}  {'parsed':>6}  output")
for ntok, out, ok in rows:
    print(f"{ntok:>7}  {str(ok):>6}  {out}")
toks = [r[0] for r in rows if r[0] > 0]
print(f"\nmedian decode tokens on real images: {sorted(toks)[len(toks)//2]}  (n={len(toks)})")
