#!/usr/bin/env python3
"""R-16 proof deliverables -- reproducible from raw/*.jsonl + raw/frame0400.jpg.

    ../../.venv-ft/bin/python make_proof.py

Four figures:

  boxes-on-frame.png       the three tracked boxes drawn on the real frame. Every
                           number in this campaign is conditioned on these being
                           actual vehicles; per the repo's "look at it" rule that
                           is a claim about pixels and needs an image, not a log.
  rate-decomposition.png   where the 6.15 Hz the Part IV/V replays assumed went.
  scaling-and-batching.png separate vs batched carry as candidates are added.
  coresidency.png          the carry and the VLM contending for one 8 GB board.

Labels are Spanish (thesis language), with diacritics.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW, PROOF = HERE / "raw", HERE / "proof"
PROOF.mkdir(exist_ok=True)

BOXES = [([496, 69, 577, 110], "1  coche oscuro", "#e34a33"),
         ([604, 78, 672, 112], "2  coche azul", "#2c7fb8"),
         ([400, 345, 555, 445], "3  todoterreno negro", "#00c000")]


def es(v: float, d: int = 2) -> str:
    """Spanish decimal comma. The prose on these figures is Spanish; a 2.69 next to
    a 6,15 in the same title is the kind of thing a tribunal notices."""
    return f"{v:.{d}f}".replace(".", ",")

def rows(name: str) -> dict:
    out = {}
    for line in (RAW / name).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["tag"]] = r
    return out


def fig_boxes() -> None:
    img = Image.open(RAW / "frame0400.jpg")
    W, H = img.size
    fig, ax = plt.subplots(figsize=(11, 11 * H / W))
    ax.imshow(img)
    for i, (((x1, y1, x2, y2), label, colour)) in enumerate(BOXES):
        ax.add_patch(mpatches.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                        fill=False, ec=colour, lw=2.4))
        # boxes 1 and 2 are side by side and only ~30 px apart, so labelling both
        # below runs the two strings straight through each other -- box 1 goes above
        up = i == 0
        ax.text(x1, y1 - 8 if up else y2 + 13, label, color=colour, fontsize=11,
                weight="bold", va="bottom" if up else "top",
                bbox=dict(fc="black", alpha=0.55, ec="none", pad=1.5))
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    ax.set_title("R-16: los tres objetos que arrastra SAM2 en cada celda\n"
                 f"cruce nocturno, {W}x{H}, fotograma 0400 del clip de la placa",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(PROOF / "boxes-on-frame.png", dpi=130)
    plt.close(fig)


def fig_rate() -> None:
    m = rows("m12.jsonl")
    trt, eag, big = (m["sep-n1-768-trt"], m["sep-n1-768-eager"], m["sep-n1-1024-eager"])
    n2 = m["sep-n2-1024-eager"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))

    bars = [("768 + TensorRT\n(lo que midió E1)", trt["per_cand_hz"], "#2c7fb8"),
            ("768, eager\n(sin TensorRT)", eag["per_cand_hz"], "#7fb8d8"),
            ("1024, eager\n(lo desplegado)", big["per_cand_hz"], "#e34a33")]
    ax.bar([b[0] for b in bars], [b[1] for b in bars], color=[b[2] for b in bars])
    for i, (_, v, _) in enumerate(bars):
        ax.text(i, v + 0.08, f"{es(v)} Hz", ha="center", fontsize=11, weight="bold")
    ax.set_ylabel("Hz por candidato (1 candidato)")
    ax.set_ylim(0, 7.2)
    ax.set_title("El 6,15 Hz heredado se midió a 768 con TensorRT;\n"
                 f"el sistema desplegado corre a 1024 sin él: {es(big['per_cand_hz'])} Hz")
    ax.annotate("", xy=(2, big["per_cand_hz"] + 0.5), xytext=(0, trt["per_cand_hz"] + 0.5),
                arrowprops=dict(arrowstyle="->", lw=2, color="#444"))
    ax.text(1, trt["per_cand_hz"] + 0.75,
            f"{es(trt['per_cand_hz'] / big['per_cand_hz'])}x optimista",
            ha="center", fontsize=12, weight="bold", color="#444")

    # the consequence: the replays' per-candidate sampling stride at 30 fps
    assumed_hz = 6.15 / 2.0          # select_p53.py:84
    meas_hz = n2["per_cand_hz"]
    st_a, st_m = round(30.0 / assumed_hz), round(30.0 / meas_hz)
    ax2.bar(["supuesto\n(CAND_HZ = 6,15/2)", "medido\n(2 estados, 1024)"],
            [st_a, st_m], color=["#7fb8d8", "#e34a33"])
    for i, v in enumerate([st_a, st_m]):
        ax2.text(i, v + 0.4, f"cada {v}º fotograma", ha="center", fontsize=11,
                 weight="bold")
    ax2.set_ylabel("intervalo de muestreo por candidato (fotogramas @ 30 fps)")
    ax2.set_ylim(0, st_m + 5)
    ax2.set_title("Consecuencia en las repeticiones de las Partes IV-V:\n"
                  f"muestrearon {es(st_m / st_a, 1)}x más a menudo de lo que permite la placa")
    fig.tight_layout()
    fig.savefig(PROOF / "rate-decomposition.png", dpi=130)
    plt.close(fig)


def fig_scaling() -> None:
    m = rows("m12.jsonl")
    mem = rows("mem.jsonl")
    ns = [1, 2, 3]
    sep = [m["sep-n1-1024-eager"]["tick_ms_p50"], m["sep-n2-1024-eager"]["tick_ms_p50"],
           m["sep-n3-1024-eager"]["tick_ms_p50"]]
    bat = [m["sep-n1-1024-eager"]["tick_ms_p50"], m["bat-n2-1024-eager"]["tick_ms_p50"],
           m["bat-n3-1024-eager"]["tick_ms_p50"]]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))
    ax.plot(ns, sep, "o-", lw=2.2, ms=9, color="#e34a33", label="estados separados (lo que hace el arnés)")
    ax.plot(ns, bat, "s-", lw=2.2, ms=9, color="#2c7fb8", label="un estado, N obj_id (lote)")
    for x, y in zip(ns, sep):
        ax.text(x, y + 32, f"{y:.0f}", ha="center", color="#e34a33", fontsize=10)
    for x, y in zip(ns[1:], bat[1:]):   # n=1 is the same run in both arms; one label
        ax.text(x, y - 62, f"{y:.0f}", ha="center", color="#2c7fb8", fontsize=10)
    ax.set_xticks(ns); ax.set_xlabel("candidatos arrastrados a la vez")
    ax.set_ylabel("ms por ronda (todos los candidatos avanzan 1 fotograma)")
    ax.set_title("Los estados separados escalan exactamente con N;\n"
                 "el lote comparte el codificador (G0: IoU de máscara 1,000)")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.3)

    # memory: the O(N) term is the video the offline state materialises, not the model
    labels = ["separados\n25 fotogramas", "separados\n100 fotogramas",
              "lote\n25 fotogramas", "lote\n100 fotogramas"]
    # each row against its OWN after_load, so the bar is the cost of creating the
    # states and not of loading the model
    def state_cost(r):
        a = r["mem_avail_mb"]
        return a["after_load"] - a["after_state"]
    vals = [state_cost(mem["mem-sep-n2-clip25"]), state_cost(mem["mem-sep-n2-clip"]),
            state_cost(mem["mem-bat-n2-clip25"]), state_cost(m["bat-n2-1024-eager"])]
    ax2.bar(labels, vals, color=["#e34a33", "#a01f0a", "#2c7fb8", "#17527a"])
    for i, v in enumerate(vals):
        ax2.text(i, v + 40, f"{v} MB", ha="center", fontsize=11, weight="bold")
    ax2.set_ylabel("RAM del anfitrión que cuesta crear los estados (MB, 2 candidatos)")
    ax2.set_title("El coste O(N) es el vídeo, no el modelo:\n"
                  f"{es((vals[1] - vals[0]) / 75 / 2, 1)} MB por fotograma y estado "
                  "(= 12,58 MB float32 a 1024²)")
    ax2.tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    fig.savefig(PROOF / "scaling-and-batching.png", dpi=130)
    plt.close(fig)


def fig_coresidency() -> None:
    src = RAW / "m3-clean.jsonl"
    if not src.exists():
        print("skip coresidency: no m3-clean.jsonl yet")
        return
    m3 = rows("m3-clean.jsonl")
    base = rows("m34.jsonl")["stream-n1-1024-ring100-server_absent"]

    cells = [("n=1, 1024\nanillo 100", "stream-n1-1024-ring100-server_load"),
             ("n=1, 1024\nanillo 32", "stream-n1-1024-ring32-server_load"),
             ("n=1, 768\nanillo 100", "stream-n1-768-ring100-server_load"),
             ("n=2, 1024\nanillo 100", "stream-n2-1024-ring100-server_load"),
             ("n=2, 1024\nanillo 32", "stream-n2-1024-ring32-server_load")]

    fig, (ax, ax2, ax3) = plt.subplots(1, 3, figsize=(18.5, 5.4))
    absent = rows("m34.jsonl")
    xs, base_hz, load_hz, notes = [], [], [], []
    for label, tag in cells:
        r = m3.get(tag)
        b = absent.get(tag.replace("server_load", "server_absent"))
        xs.append(label)
        base_hz.append(b["per_cand_hz"] if b else 0.0)
        if r is None or "tick_ms_p50" not in r:
            load_hz.append(0.0); notes.append("OOM")  # short: a wide string here overruns the neighbouring bar labels
        else:
            load_hz.append(r["per_cand_hz"])
            # each cell against ITS OWN no-server baseline: comparing an n=2 bar to
            # an n=1 baseline would bill the N-scaling cost to co-residency
            notes.append(f"{es(b['per_cand_hz'] / r['per_cand_hz'])}x" if b else "")
    idx = range(len(xs))
    ax.bar([i - 0.2 for i in idx], base_hz, 0.4, color="#2c7fb8", label="sin servidor")
    ax.bar([i + 0.2 for i in idx], load_hz, 0.4, color="#e34a33",
           label="con el VLM desplegado bajo carga real")
    for i, (bv, lv, t) in enumerate(zip(base_hz, load_hz, notes)):
        # the OOM label sits where the dead bar would be, which is on top of that
        # cell's no-server bar -- push it above the blue one instead
        ax.text(i + 0.2, (bv if lv == 0 else lv) + 0.12, t, ha="center", fontsize=10,
                weight="bold", color="#444" if lv == 0 else "#a01f0a")
        ax.text(i - 0.2, bv + 0.06, es(bv), ha="center", fontsize=9, color="#2c7fb8")
    ax.set_xticks(list(idx)); ax.set_xticklabels(xs, fontsize=9)
    ax.set_ylabel("Hz por candidato")
    ax.set_ylim(0, max(base_hz) + 0.8)
    ax.legend(fontsize=9)
    ax.set_title("E1 midió 0 coste de co-residencia contra un servidor OCIOSO;\n"
                 "bajo carga real cuesta ~2,3x en TODAS las configuraciones")

    # swap is the mechanism -- the ring lever is visible here and nowhere else
    sw, swc = [], []
    for label, tag in cells:
        r = m3.get(tag)
        if r is None or "swap_used_mb" not in r:
            sw.append(0); swc.append("#888")
        else:
            sw.append(r["swap_used_mb"]["end"] - r["swap_used_mb"]["before"])
            swc.append("#a01f0a" if sw[-1] > 500 else "#2c7fb8")
    ax2.bar(xs, sw, color=swc)
    for i, v in enumerate(sw):
        ax2.text(i, v + 40, "n/a" if v == 0 else f"{v:+d} MB", ha="center",
                 fontsize=10, weight="bold")
    ax2.set_ylabel("swap consumido durante la celda (MB)")
    ax2.tick_params(axis="x", labelsize=9)
    ax2.set_title("El anillo de StreamCarry se dimensiona en FOTOGRAMAS:\n"
                  "a 1024 son 12,58 MB cada uno, y 100 no caben junto al VLM")

    # the OOM cell produced no stdout -- the sidecar trace is the only record it
    # ran at all, and it is what turns "murió" into a measurement
    for tag, lbl, colour in [("n2-1024-r100", "n=2, anillo 100 (muere)", "#a01f0a"),
                             ("n2-1024-r32", "n=2, anillo 32 (sobrevive)", "#2c7fb8")]:
        f = RAW / f"tr-clean-{tag}.jsonl"
        if not f.exists():
            continue
        tr = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
        ax3.plot([r["tick"] for r in tr], [r["avail"] for r in tr], lw=2.2,
                 color=colour, label=lbl)
        ax3.plot(tr[-1]["tick"], tr[-1]["avail"], "x" if colour == "#a01f0a" else "o",
                 ms=12, mew=3, color=colour)
    ax3.axhline(0, color="#000", lw=1)
    ax3.set_xlabel("ronda (cada candidato avanza 1 fotograma)")
    ax3.set_ylabel("MemAvailable (MB)")
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)
    ax3.set_title("La celda que muere no imprime nada:\nla traza lateral es su única prueba")
    fig.tight_layout()
    fig.savefig(PROOF / "coresidency.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    fig_boxes()
    fig_rate()
    fig_scaling()
    fig_coresidency()
    print("wrote", ", ".join(sorted(p.name for p in PROOF.glob("*.png"))))
