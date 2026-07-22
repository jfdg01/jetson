#!/usr/bin/env python3
"""R-13 proof figures, reproducible from results.json + raw/.

    PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-detector-baseline/make_proof.py

Three figures, one per claim the campaign makes:

  arms-bar.png        the rates, with Wilson intervals on n_effective=316 (not 439)
  oracle-gap.png      recall@k -- the "competent proposer, hopeless selector" split
  qualitative-grid.png six frames, GT + VLM box + OWLv2 top-3, zoomed

The qualitative grid zooms each panel to the union of the boxes: RefDrone targets
are single-digit-percent of frame width, and a full-frame view renders every box
as an invisible dot (this bit the R-14 figures first).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from PIL import Image

from grounding.contract import IOU_GATE_THRESHOLD, iou, normalize_bbox

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PROOF = HERE / "proof"
ROOT = HERE.parent.parent
VLM_ITEMS = HERE.parent / "2026-07-21-roi-ondevice" / "raw" / "items-full.jsonl"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def arms_bar(res: dict) -> None:
    """Rates with Wilson intervals computed on n_effective, which is the honest n."""
    n_eff = res["n_effective"]
    order = [("vlm", "Qwen2-VL-2B Q8_0\n(el sistema desplegado)", "#2c7fb8"),
             ("oracle", "D-oracle\n(mejor de top-10, usa GT)", "#999999"),
             ("phrase", "D-phrase\n(sintagma nominal)", "#41ab5d"),
             ("full", "D-full\n(expresión completa)", "#fe9929"),
             ("head", "D-head\n(sustantivo núcleo)", "#e34a33")]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for i, (k, label, colour) in enumerate(order):
        a = res["arms"][k]
        rate = a["iou_gate_pass_rate"]
        # deflate the count onto n_effective so the interval is not fake-tight
        k_eff = round(rate * n_eff)
        lo, hi = wilson(k_eff, n_eff)
        ax.barh(i, rate, color=colour, height=0.62,
                hatch="//" if k == "oracle" else None, edgecolor="white")
        ax.plot([lo, hi], [i, i], color="black", lw=1.6)
        ax.plot([lo, lo], [i - .1, i + .1], color="black", lw=1.6)
        ax.plot([hi, hi], [i - .1, i + .1], color="black", lw=1.6)
        # label goes past the interval, not past the bar, or the whisker crosses the text
        ax.text(hi + 0.015, i, f"{rate*100:.1f}%  ({a['k']}/{a['n']})",
                va="center", fontsize=10)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([l for _, l, _ in order], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.06)
    ax.set_xlabel("Tasa de acierto IoU@0.25 sobre RefDrone val (n=439)")
    ax.set_title("R-13 — OWLv2 frente al VLM desplegado, ambos en la Orin Nano 8 GB\n"
                 f"barras de error: Wilson 95% sobre n_efectivo={n_eff} imágenes únicas",
                 fontsize=11)
    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)
    fig.text(0.5, 0.015,
             "D-oracle elige entre las propuestas del detector usando la verdad-terreno: "
             "es una cota superior, no un sistema.",
             ha="center", fontsize=8.5, style="italic")
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(PROOF / "arms-bar.png", dpi=150)
    plt.close(fig)


def oracle_gap(rows: list[dict], res: dict) -> None:
    """Recall@k for the phrase arm. The whole claim is the shape of this curve:
    it climbs steeply and then flattens far above the top-1 point."""
    ks = range(1, 11)
    curves = {}
    for arm in ("phrase", "full", "head"):
        hits = []
        for r in rows:
            w, h = r["img_wh"]
            rank = None
            for j, b in enumerate(r[arm]["boxes"]):
                if iou(normalize_bbox(b, w, h), r["gt"]) >= IOU_GATE_THRESHOLD:
                    rank = j
                    break
            hits.append(rank)
        curves[arm] = [sum(1 for x in hits if x is not None and x < k) / len(rows) for k in ks]

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    style = {"phrase": ("#41ab5d", "D-phrase (sintagma nominal)"),
             "full": ("#fe9929", "D-full (expresión completa)"),
             "head": ("#e34a33", "D-head (sustantivo núcleo)")}
    for arm, (c, lab) in style.items():
        ax.plot(list(ks), curves[arm], "-o", color=c, label=lab, ms=4.5)
    vlm = res["arms"]["vlm"]["iou_gate_pass_rate"]
    ax.axhline(vlm, color="#2c7fb8", ls="--", lw=1.8,
               label=f"VLM desplegado, top-1 ({vlm*100:.1f}%)")
    ax.annotate("", xy=(1, curves["phrase"][-1]), xytext=(1, curves["phrase"][0]),
                arrowprops=dict(arrowstyle="<->", color="black", lw=1.4))
    ax.text(1.25, (curves["phrase"][0] + curves["phrase"][-1]) / 2,
            f"brecha de selección\n{100*(curves['phrase'][-1]-curves['phrase'][0]):.1f} pp",
            fontsize=9.5, va="center")
    ax.set_xlabel("k (número de propuestas consideradas)")
    ax.set_ylabel("Fracción con una caja correcta entre las k primeras")
    ax.set_title("R-13 — OWLv2 propone bien y ordena mal\n"
                 "el objeto correcto ya está entre sus propuestas; el lenguaje no lo selecciona",
                 fontsize=11)
    ax.set_xticks(list(ks))
    ax.set_ylim(0, 1.0)
    ax.grid(alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(PROOF / "oracle-gap.png", dpi=150)
    plt.close(fig)


def qualitative(rows: list[dict], n: int = 6) -> None:
    """Six cases where OWLv2 had the box and ranked it below top-1, with the VLM box
    for comparison. Zoomed, or the boxes are dots."""
    vlm = {}
    for line in VLM_ITEMS.read_text().splitlines():
        if line.strip():
            d = json.loads(line)
            vlm[f"{d['image_path']}||{d['caption']}"] = d

    cand = []
    for r in rows:
        w, h = r["img_wh"]
        nb = [normalize_bbox(b, w, h) for b in r["phrase"]["boxes"]]
        if not nb:
            continue
        top1 = iou(nb[0], r["gt"])
        best_rank = next((j for j, b in enumerate(nb)
                          if iou(b, r["gt"]) >= IOU_GATE_THRESHOLD), None)
        v = vlm.get(f"{r['image_path']}||{r['caption']}")
        if best_rank is not None and best_rank > 0 and top1 < IOU_GATE_THRESHOLD and v:
            # prefer cases the VLM got right: that is the contrast the figure is for
            cand.append((v["gate_pass"], -best_rank, r, v, best_rank))
    cand.sort(key=lambda t: (not t[0], t[1]))
    picked = cand[:n]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9.4))
    for ax, (_, _, r, v, rank) in zip(axes.ravel(), picked):
        img = Image.open(ROOT / r["image_path"]).convert("RGB")
        W, H = img.size
        gt = r["gt"]
        allb = [normalize_bbox(b, W, H) for b in r["phrase"]["boxes"]]
        # The correct proposal sits at rank 7-10, so drawing only the top-3 would leave
        # the figure's own claim -- "it IS among the proposals" -- unshown. Draw it too.
        drawn = [("GT", gt, "#00c000", 2.6, "up"), ("VLM", v.get("pred"), "#2c7fb8", 2.2, "down")]
        for j, b in enumerate(allb[:3]):
            drawn.append((f"OWLv2 #{j+1}", b, "#e34a33", 1.7, "up"))
        drawn.append((f"OWLv2 #{rank+1} (correcta)", allb[rank], "#d000d0", 2.4, "down"))
        boxes = [b for _, b, _, _, _ in drawn if b]
        xs = [c for b in boxes for c in (b[0], b[2])]
        ys = [c for b in boxes for c in (b[1], b[3])]
        pad = max(8, (max(xs) - min(xs)) * 0.35, (max(ys) - min(ys)) * 0.35)
        x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        x1, y1 = min(100, max(xs) + pad), min(100, max(ys) + pad)
        # normalized 0-100 -> pixels for the crop
        px = (x0 / 100 * W, y0 / 100 * H, x1 / 100 * W, y1 / 100 * H)
        ax.imshow(img.crop([int(v_) for v_ in px]),
                  extent=(x0, x1, y1, y0))
        for lab, b, colour, lw, side in drawn:
            if not b:
                continue
            ax.add_patch(mpatches.Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                                            fill=False, edgecolor=colour, lw=lw))
            # GT and the VLM box are near-coincident by construction; label them on
            # opposite sides or the two strings render on top of each other.
            ty, va = (b[1] - 0.4, "bottom") if side == "up" else (b[3] + 0.4, "top")
            ax.text(b[0], ty, lab, color=colour, fontsize=7.5, weight="bold", va=va)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.set_xticks([])
        ax.set_yticks([])
        cap = r["caption"].strip()
        ax.set_title(f'"{cap[:58]}{"..." if len(cap) > 58 else ""}"\n'
                     f'consulta OWLv2: "{r["text"]["phrase"]}"  ·  caja correcta en el puesto '
                     f'#{rank+1}  ·  VLM {"acierta" if v["gate_pass"] else "falla"}',
                     fontsize=8.5)
    handles = [mpatches.Patch(color="#00c000", label="verdad-terreno"),
               mpatches.Patch(color="#2c7fb8", label="VLM desplegado (top-1)"),
               mpatches.Patch(color="#e34a33", label="OWLv2, 3 primeras propuestas"),
               mpatches.Patch(color="#d000d0", label="OWLv2, la propuesta correcta (mal ordenada)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=10,
               frameon=False, bbox_to_anchor=(0.5, 0.005))
    fig.suptitle("R-13 — el fallo de OWLv2 es de selección, no de localización\n"
                 "en los seis casos la caja correcta está entre sus propuestas, "
                 "pero no es la primera", fontsize=12)
    fig.tight_layout(rect=(0, 0.04, 1, 0.955))
    fig.savefig(PROOF / "qualitative-grid.png", dpi=140)
    plt.close(fig)

    # ponytail: the cheapest check that the grid is not six copies of one frame
    assert len({r["image_path"] for _, _, r, _, _ in picked}) >= 4, "grid lacks frame diversity"


def main() -> None:
    PROOF.mkdir(exist_ok=True)
    res = json.loads((HERE / "results.json").read_text())
    rows = [json.loads(l) for l in (RAW / "owlv2.jsonl").read_text().splitlines() if l.strip()]
    arms_bar(res)
    oracle_gap(rows, res)
    qualitative(rows)
    print(f"[r13] wrote 3 figures to {PROOF}")


if __name__ == "__main__":
    main()
