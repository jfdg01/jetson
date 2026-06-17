# `grounding/` — v2 principled rebuild (Part II)

This package is the deliberate rebuild that replaces Part I's per-stage script
sprawl. It is organised around **one shared contract** and a **fidelity-before-GPU**
workflow. See the project `DECISIONS.md` (Part II) for *why*; this file is the
*what / where*.

## The one rule: everything imports `contract.py`

`grounding/contract.py` is the **single source of truth** for the grounding skill:

- `GROUNDING_PROMPT` — verbatim, byte-identical to the validated Stage-3 trainer.
- `parse_bbox` — the output parser.
- `iou`, `center_std` — the metrics (center_std is the mode-collapse sentinel).
- `normalize_bbox`, and constants `IMAGE_SIZE`, `COORD_SCALE`, `SEED`,
  `MAX_NEW_TOKENS`, `IOU_GATE_THRESHOLD`.

In Part I these were copy-pasted across five scripts and silently diverged. In v2
**no other module may define them** — probe, trainer, exporter, and the Jetson
deploy path all import from here, so prompt/parser/metric can never drift again.
`contract.py` is stdlib-only (`re`, `statistics`) so every backend can import it
without pulling in torch.

## Module map

```
contract.py        SHARED TRUTH (the only module implemented today)
data/
  schema.py        canonical GroundingSample {image, caption, 0–1000 bbox} + AuditStats
  refcoco.py       RefCOCO  → canonical schema
  refdrone.py      RefDrone (well-posed) → canonical schema  [+ largest-box aug lever]
  audit.py         box-per-caption + object-size gate (Phase 1)
eval/
  backends.py      HF / GGUF / Jetson behind one Backend interface
  harness.py       run a backend over a dataset → contract metrics (Phase 0 spine)
  parity.py        HF↔GGUF↔Jetson fidelity report (the −23pp probe)
train/
  config.py        single TrainConfig dataclass (replaces per-stage forks)
  trainer.py       one config-driven LoRA loop + in-loop eval
export/
  to_gguf.py       HF→GGUF with F16-vs-Q8 fidelity gate
deploy/
  serve.py         Jetson serve + Phase C hook
resolution.py      Phase 2: resize512 / tile / upscale strategies
```

## Convention: skeleton now, body at step startup

Only `contract.py` is implemented. Every other module ships as a **skeleton** —
module docstring + typed signatures that `raise NotImplementedError("filled in at
<phase> startup")`. This is intentional: the body of each module is written at the
**start of the phase that needs it**, against fresh measurements, not speculatively
up front. The skeletons exist so the structure, imports, and the contract boundary
are fixed and reviewable today.

Fill order follows the gated phases (see the APPENDIX in `DECISIONS.md` / the plan):

| Phase | Fills | Gate |
|---|---|---|
| **0** Backend fidelity | `eval/` | spine chosen by the numbers; fidelity gap quantified |
| **1** Dataset audit | `data/` | target well-posed (one box/caption); size distribution understood |
| **2** Resolution | `resolution.py` | one strategy chosen + justified |
| **3** Train | `train/` | aerial IoU@0.25 ≥ 20%, center_std non-degenerate, parse ≥ 90% |
| **4** Export & deploy | `export/`, `deploy/` | deployed IoU within Phase-0 fidelity budget of HF |

Each phase is a lab-notebook unit: do not start the next until the prior gate is
green **and documented** in `results/` + `RESULTS.md` + `DECISIONS.md` in the same
turn.
