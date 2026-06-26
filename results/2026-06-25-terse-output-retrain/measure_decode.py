"""RQ1 device leg: measure terse-model decode tokens + prefill/decode split on the Orin.

Replicates the T0a 512-anchor measurement (results/2026-06-18-t0-cadence) byte-for-byte
— same synthetic frame, same CAPTION, same verbatim contract path, 15 W + jetson_clocks —
but against the TERSE Q8_0 checkpoint, so the only change vs the JSON baseline is the
output format. Prints medians for the decode-token / wall-time comparison.

Baseline (JSON Q8_0 @512, T0a): wall 2265 ms, prefill 1113 ms, decode 1106 ms,
predicted_n ~24, 21.7 tok/s.

Run: source .venv-ft/bin/activate && python results/2026-06-25-terse-output-retrain/measure_decode.py
"""
import json
import sys

sys.path.insert(0, "experiments")
import run_t0_cadence as t0  # noqa: E402
from parsers import parse_vlm_server_timings  # noqa: E402

from grounding.contract import parse_bbox  # noqa: E402
from grounding.eval.backends import JetsonBackend  # noqa: E402

TERSE_MODEL = "/home/jfdg/grounding/phase3-terse-1024-q8_0.gguf"
TERSE_MMPROJ = "/home/jfdg/grounding/mmproj-phase3-terse-1024-f16.gguf"
MAX_SIDE = 512
N_REPS = 8

t0.RESULTS_RAW.mkdir(parents=True, exist_ok=True)
frame = t0.RESULTS_RAW / "terse-anchor-frame.png"
t0._make_synthetic_frame().save(frame)

print(f"[measure] booting terse Q8_0 on Orin (15 W, clocks locked)...", flush=True)
backend = JetsonBackend(TERSE_MODEL, TERSE_MMPROJ, max_side=1024, startup_timeout_s=300)
walls, prompt_ms, predicted_ms, predicted_n, prompt_n = [], [], [], [], []
parse_ok, outputs = 0, []
try:
    for _ in range(2):  # warmup
        t0._timed_anchor_post(backend._base, str(frame), t0.CAPTION, MAX_SIDE)
    for i in range(N_REPS):
        wall, raw = t0._timed_anchor_post(backend._base, str(frame), t0.CAPTION, MAX_SIDE)
        walls.append(wall)
        tm = parse_vlm_server_timings(raw)
        if tm:
            prompt_ms.append(tm.prompt_ms)
            predicted_ms.append(tm.predicted_ms)
            predicted_n.append(tm.predicted_n)
            prompt_n.append(tm.prompt_n)
        content = json.loads(raw)["choices"][0]["message"].get("content") or ""
        outputs.append(content)
        parse_ok += int(parse_bbox(content) is not None)
finally:
    backend.close()

st = t0._stats
res = {
    "phase": "terse-RQ1", "host": "Orin Nano 8GB (15 W, clocks locked)", "max_side": MAX_SIDE,
    "n_reps": N_REPS, "model": TERSE_MODEL,
    "wall_ms": st(walls),
    "prefill_ms_prompt": st(prompt_ms) if prompt_ms else None,
    "decode_ms_predicted": st(predicted_ms) if predicted_ms else None,
    "predicted_n": st([float(x) for x in predicted_n]) if predicted_n else None,
    "prompt_n": st([float(x) for x in prompt_n]) if prompt_n else None,
    "decode_tok_per_s": (st([float(x) for x in predicted_n])["median"] /
                         (st(predicted_ms)["median"] / 1000.0)) if predicted_n else None,
    "parse_rate": parse_ok / N_REPS,
    "sample_outputs": outputs[:4],
}
out_path = "results/2026-06-25-terse-output-retrain/decode_timing.json"
with open(out_path, "w") as f:
    json.dump(res, f, indent=2)

print(json.dumps(res, indent=2))
print(f"\n[measure] wrote {out_path}")
