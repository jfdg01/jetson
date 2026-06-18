"""HF → GGUF export with fidelity disambiguation (Phase 4a).

Converts a merged HF checkpoint to GGUF F16 + Q8_0 (plus the multimodal `mmproj`
projector) using the pinned-commit `convert_hf_to_gguf.py`, so the Part-I confound
— a −23pp runtime/preprocessing loss that was mistaken for, and stacked on top of, a
−7pp quant loss — can be split into its two components on the *actual fine-tuned
aerial model*:

  runtime/preprocessing gap = HF(reference) − GGUF-F16     (same weights, F16)
  quant gap                 = GGUF-F16     − GGUF-Q8_0     (preprocessing held fixed)

**Where the gate runs (decision, DECISIONS.md 2026-06-18):** the authoritative
F16-vs-Q8 disambiguation AND the deployment gate run **on the Jetson** over the full
RefDrone val (n=439) vs the committed HF reference (IoU@0.25 = 59.5%) — the Jetson is
the real deployment target, has CUDA (seconds/sample vs the many CPU-hours a local
n=439 GGUF eval at 1024px would cost), and sits at the *same pinned llama.cpp commit*
as the local build, so backend version is not a confound. Hence `export()` is
conversion-only by default; `run_fidelity_gate=True` runs an OPTIONAL small-n
local-CPU smoke (cheap sanity that the GGUF loads and parses), not the headline gate.

**mmproj reuse (decision, DECISIONS.md 2026-06-18):** the vision encoder was FROZEN
during the Phase-3 LoRA (`freeze_vision=True`; LoRA on the LLM attn+MLP only), so the
projector exported from the merged checkpoint is bit-equivalent to the base Qwen2-VL
mmproj. We regenerate it from the checkpoint anyway for self-contained provenance and
cross-check its sha256 against the Phase-0 base mmproj.

Conversion runs inside `.venv-ft` (needs torch). Idempotent: an existing, non-empty
output is reused, so re-runs are cheap.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Pinned-commit converter (see grounding/manifest.LLAMACPP_COMMIT).
_DEFAULT_CONVERT = "/tmp/llama.cpp-57fe1f0/convert_hf_to_gguf.py"

# convert_hf_to_gguf --outtype tokens keyed by our quant labels.
_OUTTYPE = {"F16": "f16", "Q8_0": "q8_0"}


@dataclass(frozen=True)
class ExportResult:
    gguf_path: str
    mmproj_path: str
    quant: str          # "F16" | "Q8_0"
    iou_gate_pass_rate: float  # NaN unless a local smoke gate was run
    drop_vs_hf_pp: float       # fidelity loss vs the HF reference (NaN if not gated)


def _sha256(path: str | Path, *, limit_mb: int = 0) -> str:
    h = hashlib.sha256()
    read = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            read += len(chunk)
            if limit_mb and read >= limit_mb << 20:
                break
    return h.hexdigest()


def _run_convert(convert_script: str, checkpoint: str, outfile: Path,
                 *, outtype: Optional[str] = None, mmproj: bool = False) -> None:
    """Invoke convert_hf_to_gguf.py for one artifact (weights or mmproj)."""
    if outfile.exists() and outfile.stat().st_size > 0:
        print(f"[export] reuse existing {outfile.name} "
              f"({outfile.stat().st_size / 1e9:.2f} GB)", flush=True)
        return
    cmd = ["python", convert_script, checkpoint, "--outfile", str(outfile)]
    if mmproj:
        cmd.append("--mmproj")
    if outtype:
        cmd += ["--outtype", outtype]
    print(f"[export] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def export(
    checkpoint: str,
    *,
    quants: List[str] = ["F16", "Q8_0"],
    out_dir: Optional[str] = None,
    convert_script: str = _DEFAULT_CONVERT,
    run_fidelity_gate: bool = False,
    base_mmproj: Optional[str] = None,
    write_manifest: bool = True,
) -> List[ExportResult]:
    """Export `checkpoint` to GGUF at each quant + a regenerated mmproj.

    Returns one `ExportResult` per quant. Gate fields are NaN unless
    `run_fidelity_gate=True` (a local-CPU smoke; the authoritative gate is the
    Jetson deployment — see module docstring). If `base_mmproj` is given, the
    regenerated mmproj's sha256 is cross-checked against it (vision was frozen, so
    they should match) and the result is printed.
    """
    import math

    ckpt = Path(checkpoint)
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint}")
    if not os.path.exists(convert_script):
        raise FileNotFoundError(f"convert script not found: {convert_script}")

    out = Path(out_dir) if out_dir else ckpt / "gguf"
    out.mkdir(parents=True, exist_ok=True)
    stem = ckpt.name

    # 1) mmproj (regenerate once, cross-check vs base).
    mmproj_path = out / f"mmproj-{stem}-f16.gguf"
    _run_convert(convert_script, str(ckpt), mmproj_path, mmproj=True)
    if base_mmproj and os.path.exists(base_mmproj):
        a, b = _sha256(mmproj_path), _sha256(base_mmproj)
        match = "MATCH (vision frozen, as expected)" if a == b else "DIFFER"
        print(f"[export] mmproj sha256 vs base: {match}\n"
              f"         this={a[:16]}…  base={b[:16]}…", flush=True)

    # 2) weights at each quant.
    results: List[ExportResult] = []
    for q in quants:
        outtype = _OUTTYPE.get(q)
        if outtype is None:
            raise ValueError(f"unsupported quant {q!r}; known: {list(_OUTTYPE)}")
        gguf_path = out / f"{stem}-{outtype}.gguf"
        _run_convert(convert_script, str(ckpt), gguf_path, outtype=outtype)

        gate = math.nan
        drop = math.nan
        if run_fidelity_gate:
            gate, drop = _local_smoke_gate(str(gguf_path), str(mmproj_path))

        results.append(ExportResult(
            gguf_path=str(gguf_path), mmproj_path=str(mmproj_path),
            quant=q, iou_gate_pass_rate=gate, drop_vs_hf_pp=drop,
        ))

    if write_manifest:
        _write_export_manifest(checkpoint, results, mmproj_path)
    return results


def _local_smoke_gate(gguf_path: str, mmproj_path: str, *, n: int = 8,
                      max_side: int = 1024) -> tuple[float, float]:
    """Cheap local-CPU sanity: load the GGUF, score a tiny RefDrone-val slice.

    Not the headline gate (that's the Jetson) — just confirms the exported GGUF
    serves, the mmproj pairs, and the contract parser fires. Returns (gate, NaN);
    the HF-delta is left NaN here because the authoritative comparison is n=439 on
    the Jetson.
    """
    import math

    from grounding.data.refdrone import load_refdrone
    from grounding.eval.backends import GGUFBackend
    from grounding.eval.harness import evaluate

    samples = load_refdrone("val", max_samples=n)
    backend = GGUFBackend(gguf_path, mmproj_path, n_gpu_layers=0, max_side=max_side)
    try:
        report = evaluate(backend, samples)
    finally:
        backend.close()
    print(f"[export] local smoke (n={report.n}): parse={report.parse_rate:.0%} "
          f"iou@0.25={report.iou_gate_pass_rate:.1%}", flush=True)
    return report.iou_gate_pass_rate, math.nan


def _write_export_manifest(checkpoint: str, results: List[ExportResult],
                           mmproj_path: Path) -> None:
    from grounding import manifest

    cfg = {
        "phase": "4a",
        "kind": "gguf-export",
        "checkpoint": checkpoint,
        "convert_script": _DEFAULT_CONVERT,
        "mmproj": str(mmproj_path),
        "quants": [r.quant for r in results],
        "outputs": {r.quant: r.gguf_path for r in results},
    }
    m = manifest.capture("export", cfg)
    res = {r.quant: {"gguf_path": r.gguf_path,
                     "iou_gate_pass_rate": r.iou_gate_pass_rate,
                     "drop_vs_hf_pp": r.drop_vs_hf_pp} for r in results}
    run_dir = manifest.write(m, results=res)
    print(f"[export] manifest -> {run_dir}", flush=True)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Export a merged HF checkpoint to GGUF.")
    p.add_argument("checkpoint")
    p.add_argument("--quants", default="F16,Q8_0")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--base-mmproj", default=None,
                   help="base mmproj GGUF to sha256 cross-check against")
    p.add_argument("--smoke", action="store_true", help="run the local-CPU smoke gate")
    args = p.parse_args()

    export(
        args.checkpoint,
        quants=[q.strip() for q in args.quants.split(",") if q.strip()],
        out_dir=args.out_dir,
        base_mmproj=args.base_mmproj,
        run_fidelity_gate=args.smoke,
    )
