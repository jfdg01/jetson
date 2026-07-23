"""Regenerate the R-34 proof deliverables from runs/*/results.json (+ overlays).

    ../../.venv-ft/bin/python make_proof.py

Writes into proof/:
  pass-grid.png        per-clip PASS grid, ORACLE vs COLD, this frame-0 run
  effect-3regimes.png  the effect in three regimes (E18 n=6, this n=25, P5.2a t_p=8s)
  discordant-bike1.png a discordant pair: ORACLE holds green-on-target, COLD LOST

The first two are figures (the numbers are the point); the third is a clip frame
(the behaviour is the point) and is verified by the look-at-it rule before commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score import CLIPS, class_of, load, passed  # noqa: E402

PROOF = HERE / "proof"
GREEN, RED = "#27ae60", "#c0392b"
CLASS_ORDER = ["car", "boat", "person", "cyclist", "wakeboarder"]


def rows():
    out = []
    for c in CLIPS:
        clip = c["clip"]
        o, cd = load("ORACLE", clip), load("COLD", clip)
        out.append((clip, class_of(clip),
                    passed(o) if o else None, passed(cd) if cd else None))
    out.sort(key=lambda r: (CLASS_ORDER.index(r[1]) if r[1] in CLASS_ORDER else 9, r[0]))
    return out


def fig_grid():
    data = rows()
    fig, ax = plt.subplots(figsize=(5.2, 0.30 * len(data) + 1.1))
    for i, (clip, cls, op, cp) in enumerate(data):
        y = len(data) - 1 - i
        for x, p in ((0, op), (1, cp)):
            ax.add_patch(plt.Rectangle((x, y), 0.92, 0.85,
                         fc=GREEN if p else RED, ec="white"))
        ax.text(-0.15, y + 0.42, f"{clip}", ha="right", va="center", fontsize=7)
    ax.set_xlim(-2.2, 2.05)
    ax.set_ylim(-0.4, len(data))
    ax.set_xticks([0.46, 1.46])
    ax.set_xticklabels(["ORACLE\n(seed fresco)", "COLD\n(anclaje frío)"], fontsize=8)
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    o_pass = sum(1 for r in data if r[2])
    c_pass = sum(1 for r in data if r[3])
    ax.set_title(f"E18-n25 (onset frame 0): ORACLE {o_pass}/25 vs COLD {c_pass}/25\n"
                 "verde = PASS (genuine_lock e IoU cobertura >= 0,50)", fontsize=9)
    ax.legend(handles=[Patch(fc=GREEN, label="PASS"), Patch(fc=RED, label="FAIL")],
              loc="lower left", fontsize=7, frameon=False, bbox_to_anchor=(0.0, -0.02))
    fig.tight_layout()
    fig.savefig(PROOF / "pass-grid.png", dpi=160)
    plt.close(fig)


def fig_3regimes():
    # E18 n=6 (car clips, its as-run), this run n=25 frame-0, P5.2a re-score t_p=8s.
    # The last two are n=25; E18 is n=6 - labelled, not hidden (pre-reg disclosure).
    data = rows()
    r34 = (sum(1 for r in data if r[2]), sum(1 for r in data if r[3]), 25)
    regimes = [("E18 as-run\nn=6 (coches)", 6, 1, 6),
               ("R-34 frame 0\nn=25", *r34),
               ("P5.2a re-marcado\nt_p=8 s, n=25", 22, 5, 25)]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    x = range(len(regimes))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [r[1] / r[3] for r in regimes], w,
           color=GREEN, label="ORACLE")
    ax.bar([i + w / 2 for i in x], [r[2] / r[3] for r in regimes], w,
           color=RED, label="COLD")
    for i, r in enumerate(regimes):
        ax.text(i - w / 2, r[1] / r[3] + 0.02, f"{r[1]}/{r[3]}", ha="center", fontsize=8)
        ax.text(i + w / 2, r[2] / r[3] + 0.02, f"{r[2]}/{r[3]}", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([r[0] for r in regimes], fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("tasa de PASS")
    ax.set_title("El efecto de obsolescencia del anclaje frío, en tres regímenes\n"
                 "el retardo de entrega (~146 fotogramas) es idéntico en los tres", fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(PROOF / "effect-3regimes.png", dpi=160)
    plt.close(fig)


def fig_discordant(clip="bike1", frame=300):
    def grab(leg):
        v = cv2.VideoCapture(str(HERE / f"runs/{leg}_{clip}/overlay.mp4"))
        n = int(v.get(cv2.CAP_PROP_FRAME_COUNT))
        v.set(cv2.CAP_PROP_POS_FRAMES, min(frame, n - 1))
        ok, img = v.read()
        assert ok, f"cannot read {leg} {clip} frame {frame}"
        # ponytail: >99% one-colour == dead render; assert the frame has real content
        assert img.std() > 12, f"{leg} frame looks blank (std={img.std():.1f})"
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2))
    for ax, leg, cap in ((axes[0], "ORACLE", "ORACLE: seed fresco, verde sobre el objetivo (PASS)"),
                         (axes[1], "COLD", "COLD: caja obsoleta en el fotograma ~141, LOST (FAIL)")):
        ax.imshow(grab(leg))
        ax.set_title(cap, fontsize=8)
        ax.axis("off")
    fig.suptitle(f"{clip} fotograma {frame}: par discordante (verde=mantenida, rojo=GT)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(PROOF / "discordant-bike1.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    PROOF.mkdir(exist_ok=True)
    fig_grid()
    fig_3regimes()
    fig_discordant()
    print("wrote", *(p.name for p in sorted(PROOF.glob("*.png"))))
