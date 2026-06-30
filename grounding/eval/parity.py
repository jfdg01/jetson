"""Backend-fidelity parity report (Phase 0) — the −23pp probe.

Compares the *same* checkpoint and the *same* eval set across HF, GGUF (F16 and
Q8_0), and (later) the Jetson, then diffs the contract metrics to attribute the
drop to **preprocessing/runtime** (HF → GGUF-F16) vs **quantization**
(GGUF-F16 → Q8_0). This is the de-risk-before-GPU instrument: Phase 0 self-checks
it against the known Part-I gap on `smolvlm_ft3` (−23pp runtime, −7pp quant), then
uses it to pick the v2 spine BY THE NUMBERS.

Design follows the project's manifest-per-run rule: each backend is scored by a
separate `grounding.eval.run` invocation (its own manifest under `runners/runs/<id>/`), and
this module *composes* those `EvalReport`s into a fidelity table. It does not
re-run inference, so every number in the table is traceable to a committed manifest.

CLI — build the table from finished run dirs:

    python -m grounding.eval.parity \\
      --checkpoint smolvlm_ft3 \\
      --hf runners/runs/<id>/ --f16 runners/runs/<id>/ --q8 runners/runs/<id>/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from grounding.eval.harness import EvalReport


@dataclass(frozen=True)
class ParityReport:
    """Side-by-side fidelity across backends for one checkpoint.

    `runtime_gap_pp` and `quant_gap_pp` are in **percentage points** of the
    IoU@0.25 gate pass-rate (the headline grounding metric). Either may be `None`
    if the corresponding arm was not supplied.
    """

    checkpoint: str
    per_backend: Dict[str, EvalReport]      # label → report (e.g. "hf", "gguf-f16", "gguf-q8_0")
    runtime_gap_pp: Optional[float]         # HF → GGUF-F16 drop (preprocessing/runtime)
    quant_gap_pp: Optional[float]           # GGUF-F16 → Q8_0 drop (quantization)


def build_parity(checkpoint: str,
                 reports: Dict[str, EvalReport],
                 *, hf_key: str = "hf",
                 f16_key: str = "gguf-f16",
                 q8_key: str = "gguf-q8_0") -> ParityReport:
    """Compose per-backend `EvalReport`s into a fidelity report with attributed gaps.

    Gaps are IoU@0.25 pass-rate deltas in percentage points: runtime = HF − F16,
    quant = F16 − Q8_0. Missing arms yield `None` gaps rather than an error, so the
    probe is usable incrementally (e.g. F16 before Q8_0 is run).
    """
    def gate(key: str) -> Optional[float]:
        r = reports.get(key)
        return r.iou_gate_pass_rate if r is not None else None

    hf, f16, q8 = gate(hf_key), gate(f16_key), gate(q8_key)
    runtime_gap = (hf - f16) * 100 if (hf is not None and f16 is not None) else None
    quant_gap = (f16 - q8) * 100 if (f16 is not None and q8 is not None) else None

    return ParityReport(
        checkpoint=checkpoint,
        per_backend=dict(reports),
        runtime_gap_pp=runtime_gap,
        quant_gap_pp=quant_gap,
    )


def format_markdown(report: ParityReport) -> str:
    """Render a parity report as a Markdown table + attributed-gap summary."""
    lines: List[str] = [
        f"### Parity — `{report.checkpoint}`",
        "",
        "| Backend | n | IoU@0.25 | mean IoU | parse_rate | center_std |",
        "|---|---|---|---|---|---|",
    ]
    for label, r in report.per_backend.items():
        lines.append(
            f"| {label} | {r.n} | {r.iou_gate_pass_rate:.1%} | {r.mean_iou:.3f} "
            f"| {r.parse_rate:.1%} | {r.center_std:.1f} |"
        )
    lines.append("")
    if report.runtime_gap_pp is not None:
        lines.append(f"- **Runtime/preprocessing gap (HF → GGUF-F16):** "
                     f"{report.runtime_gap_pp:+.1f} pp")
    if report.quant_gap_pp is not None:
        lines.append(f"- **Quantization gap (GGUF-F16 → Q8_0):** "
                     f"{report.quant_gap_pp:+.1f} pp")
    return "\n".join(lines)


def _load_report(run_dir: str) -> EvalReport:
    """Reconstruct an `EvalReport` from a run dir's `results.json`."""
    import json
    import os

    with open(os.path.join(run_dir, "results.json")) as f:
        d = json.load(f)
    return EvalReport(
        backend=d["backend"], n=d["n"], parse_rate=d["parse_rate"],
        iou_gate_pass_rate=d["iou_gate_pass_rate"], mean_iou=d["mean_iou"],
        center_std=d["center_std"],
    )


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--hf", help="run dir for the HF arm")
    p.add_argument("--f16", help="run dir for the GGUF-F16 arm")
    p.add_argument("--q8", help="run dir for the GGUF-Q8_0 arm")
    args = p.parse_args()

    reports: Dict[str, EvalReport] = {}
    if args.hf:
        reports["hf"] = _load_report(args.hf)
    if args.f16:
        reports["gguf-f16"] = _load_report(args.f16)
    if args.q8:
        reports["gguf-q8_0"] = _load_report(args.q8)
    if not reports:
        raise SystemExit("supply at least one of --hf/--f16/--q8")

    print(format_markdown(build_parity(args.checkpoint, reports)))


if __name__ == "__main__":
    main()
