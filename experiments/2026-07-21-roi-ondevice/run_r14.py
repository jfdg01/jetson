#!/usr/bin/env python3
"""R-14 — the ROI headline, re-measured on the Orin at Q8_0, both arms paired.

Pre-registration and rationale: `README.md` next to this file. In one sentence: the
deployed 85.2% ROI number was HF bf16 on the 3090 and the 62.6% it beats was Q8_0 on
the Orin, so the headline effect of the thesis is a subtraction across two runtimes.
This runs both arms on the board, on the same items, in one server session.

  .venv-ft/bin/python experiments/2026-07-21-roi-ondevice/run_r14.py

Arm A is the *published* full-frame path (`harness.evaluate`, max_side=1024), not a
margin=inf special case of the ROI path -- so the control reproduces the existing
63.1% rather than a new number that happens to agree with it (RQ-R14.2).
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from grounding import manifest, stats
from grounding.data.refdrone import load_refdrone
from grounding.eval.backends import JetsonBackend
from grounding.eval.harness import evaluate
from grounding.roi import evaluate_roi

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
REMOTE_DIR = "/home/jfdg/grounding"
MODEL = f"{REMOTE_DIR}/phase3-terse100eos-1024-q8_0.gguf"
MMPROJ = f"{REMOTE_DIR}/mmproj-phase3-terse100eos-1024-f16.gguf"
FULL_FRAME_SIDE = 1024
ROI_MARGIN, ROI_RES = 2.0, 512


def key(item: dict) -> str:
    """Pairing key. Position is deliberately not used -- see R-15."""
    return f"{item['image_path']}||{item['caption']}"


def timed(backend, sink: Path):
    """Route `generate` through `generate_stats`, logging each call as it happens.

    Incremental because a dropped ssh tunnel at item 300 should leave 300 usable
    rows, not an empty file and a re-run.
    """
    calls: list[dict] = []
    fh = sink.open("w")

    def generate(image_path: str, caption: str) -> str:
        st: dict = {}
        t0 = time.perf_counter()
        text = backend.generate_stats(image_path, caption, st)
        st["client_wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        st["image_path"], st["caption"], st["text"] = image_path, caption, text
        calls.append(st)
        fh.write(json.dumps(st) + "\n")
        fh.flush()
        return text

    backend.generate = generate
    return calls, fh


def med(calls: list[dict], field: str) -> float | None:
    vals = [c[field] for c in calls if isinstance(c.get(field), (int, float))]
    return round(statistics.median(vals), 1) if vals else None


def record(arm: dict, cfg: dict) -> str:
    """Manifest per arm (git SHA, llama.cpp commit, lock sha256), beside the runs."""
    m = manifest.capture("eval", {"experiment": "r14-roi-ondevice", "backend": "jetson",
                                  "dataset": "refdrone", "split": "val",
                                  "device": "jetson-orin-nano-8gb", "dtype": "q8_0",
                                  "power_mode": "15W+jetson_clocks",
                                  "model": MODEL, "mmproj": MMPROJ, **cfg})
    return str(manifest.write(m, runs_dir=HERE / "runs", results=arm))


def summarise(name: str, report, calls: list[dict]) -> dict:
    return {
        "arm": name,
        "k": sum(it["gate_pass"] for it in report.items),
        "n": report.n,
        "iou_gate_pass_rate": report.iou_gate_pass_rate,
        "parse_rate": report.parse_rate,
        "mean_iou": report.mean_iou,
        "center_std": report.center_std,
        # llama.cpp's own names: prompt_ms = prefill, predicted_ms = decode.
        "prefill_ms_median": med(calls, "prompt_ms"),
        "decode_ms_median": med(calls, "predicted_ms"),
        "wall_ms_median": med(calls, "wall_ms"),
        "transfer_ms_median": med(calls, "transfer_ms"),
        "prompt_tokens_median": med(calls, "prompt_n"),
        "fed_mpx_median": med(calls, "fed_mpx"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=0, help="cap samples (0 = all 439); smoke-test lever")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    samples = load_refdrone("val", max_samples=args.n)
    n_eff = len({s.image_path for s in samples})
    print(f"[r14] {len(samples)} samples over {n_eff} unique images", flush=True)

    print(f"[r14] booting llama-server on the Orin: {Path(MODEL).name}", flush=True)
    backend = JetsonBackend(MODEL, MMPROJ, n_gpu_layers=99)
    out: dict = {"model": MODEL, "mmproj": MMPROJ, "n": len(samples), "n_effective": n_eff}
    try:
        # --- arm A: the published full-frame path -------------------------------
        backend.max_side = FULL_FRAME_SIDE
        calls_a, fh_a = timed(backend, RAW / "calls-full.jsonl")
        t0 = time.time()
        rep_a = evaluate(backend, samples, progress_every=max(1, len(samples) // 20),
                         items_path=RAW / "items-full.jsonl")
        fh_a.close()
        out["arm_full"] = summarise("full-frame@1024", rep_a, calls_a) | {
            "wall_s": round(time.time() - t0, 1)}
        out["arm_full"]["run_dir"] = record(out["arm_full"], {"max_side": FULL_FRAME_SIDE})
        print(f"[r14] A {out['arm_full']}", flush=True)

        # --- arm B: the ROI crop ------------------------------------------------
        calls_b, fh_b = timed(backend, RAW / "calls-roi.jsonl")
        t0 = time.time()
        rep_b = evaluate_roi(backend, samples, ROI_MARGIN, ROI_RES,
                             progress_every=max(1, len(samples) // 20))
        fh_b.close()
        (RAW / "items-roi.jsonl").write_text(
            "".join(json.dumps(it) + "\n" for it in rep_b.items))
        out["arm_roi"] = summarise(f"roi-M{ROI_MARGIN}@{ROI_RES}", rep_b, calls_b) | {
            "wall_s": round(time.time() - t0, 1)}
        out["arm_roi"]["run_dir"] = record(
            out["arm_roi"], {"roi_margin": ROI_MARGIN, "roi_out_res": ROI_RES})
        print(f"[r14] B {out['arm_roi']}", flush=True)
    finally:
        backend.close()

    # --- paired test ------------------------------------------------------------
    a = {key(it): int(it["gate_pass"]) for it in rep_a.items}
    b_ = {key(it): int(it["gate_pass"]) for it in rep_b.items}
    assert len(a) == rep_a.n and len(b_) == rep_b.n, \
        "image+caption is not unique in this split -- the pairing key needs widening"
    b, c, n_paired = stats.discordant_counts(b_, a)   # b = ROI right, full wrong
    bd, _ = stats.deflate_to_effective(b, n_paired, n_eff)
    cd, _ = stats.deflate_to_effective(c, n_paired, n_eff)
    out["paired"] = {
        "b_roi_only": b, "c_full_only": c, "n_paired": n_paired,
        "b_deflated": bd, "c_deflated": cd, "n_effective": n_eff,
        "p_raw": stats.mcnemar(b, c),
        "p_deflated": stats.mcnemar(bd, cd),
    }
    print(f"[r14] paired {out['paired']}", flush=True)

    (HERE / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"[r14] -> {HERE / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
