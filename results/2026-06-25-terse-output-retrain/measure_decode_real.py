"""On-Orin decode benchmark over REAL RefDrone images (not the OOD synthetic frame).

The synthetic anchor frame makes the model fall back to its pretrained tuple/0-1000 prior,
masking the trained terse format — so it under-reports the token saving. This measures
predicted_n + decode_ms on real val images at the 512 anchor resolution, for BOTH the JSON
deploy and the terse iter-2b model, on the same images → a fair decode-token comparison.

Run: source .venv-ft/bin/activate && python results/2026-06-25-terse-output-retrain/measure_decode_real.py
"""
import json
import statistics as st
import sys

sys.path.insert(0, "experiments")
import run_t0_cadence as t0  # noqa: E402
from parsers import parse_vlm_server_timings  # noqa: E402

from grounding.contract import parse_bbox  # noqa: E402
from grounding.data.refdrone import load_refdrone  # noqa: E402
from grounding.eval.backends import JetsonBackend  # noqa: E402

MODELS = {
    "JSON-deploy": ("/home/jfdg/grounding/phase3-refdrone-1024-q8_0.gguf",
                    "/home/jfdg/grounding/mmproj-phase3-refdrone-1024-f16.gguf"),
    "terse-iter2b": ("/home/jfdg/grounding/phase3-terse100eos-1024-q8_0.gguf",
                     "/home/jfdg/grounding/mmproj-phase3-terse100eos-1024-f16.gguf"),
}
N = 20
MAX_SIDE = 512
samples = load_refdrone("val", max_samples=N)

import subprocess
import time

results = {}
for name, (model, mmproj) in MODELS.items():
    # Fully kill any prior remote llama-server so the new model actually loads
    # (JetsonBackend uses a fixed port; a lingering server would be reused silently).
    subprocess.run(["ssh", "jetson", "pkill -f llama-server; sleep 2"], timeout=30)
    time.sleep(3)
    print(f"\n[measure] {name} on {N} real val images @ {MAX_SIDE} ...", flush=True)
    backend = JetsonBackend(model, mmproj, max_side=1024, startup_timeout_s=300)
    dec_tok, dec_ms, wall, parse_ok, outs = [], [], [], 0, []
    try:
        # warmup
        t0._timed_anchor_post(backend._base, samples[0].image_path, samples[0].caption, MAX_SIDE)
        for s in samples:
            w, raw = t0._timed_anchor_post(backend._base, s.image_path, s.caption, MAX_SIDE)
            tm = parse_vlm_server_timings(raw)
            content = json.loads(raw)["choices"][0]["message"].get("content") or ""
            if tm:
                dec_tok.append(tm.predicted_n)
                dec_ms.append(tm.predicted_ms)
            wall.append(w)
            outs.append(content)
            parse_ok += int(parse_bbox(content) is not None)
    finally:
        backend.close()
    results[name] = {
        "decode_tok_median": st.median(dec_tok), "decode_tok_mean": st.mean(dec_tok),
        "decode_ms_median": st.median(dec_ms), "wall_ms_median": st.median(wall),
        "parse_rate": parse_ok / len(samples), "sample_outputs": outs[:5],
    }
    r = results[name]
    print(f"  decode_tok median={r['decode_tok_median']:.0f} (mean {r['decode_tok_mean']:.1f}) "
          f"decode_ms={r['decode_ms_median']:.0f} wall={r['wall_ms_median']:.0f} "
          f"parse={r['parse_rate']:.0%}", flush=True)
    print(f"  outputs: {r['sample_outputs']}", flush=True)

j = results["JSON-deploy"]; t = results["terse-iter2b"]
print(f"\n=== DELTA (real images @512) ===")
print(f"decode tokens: {j['decode_tok_median']:.0f} -> {t['decode_tok_median']:.0f} "
      f"({100*(t['decode_tok_median']-j['decode_tok_median'])/j['decode_tok_median']:+.0f}%)")
print(f"decode ms:     {j['decode_ms_median']:.0f} -> {t['decode_ms_median']:.0f} "
      f"({100*(t['decode_ms_median']-j['decode_ms_median'])/j['decode_ms_median']:+.0f}%)")
print(f"wall ms:       {j['wall_ms_median']:.0f} -> {t['wall_ms_median']:.0f} "
      f"({100*(t['wall_ms_median']-j['wall_ms_median'])/j['wall_ms_median']:+.0f}%)")

with open("results/2026-06-25-terse-output-retrain/decode_real.json", "w") as f:
    json.dump(results, f, indent=2)
print("\n[measure] wrote decode_real.json")
