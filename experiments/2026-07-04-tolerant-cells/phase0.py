"""E23 Phase 0 -- offline containment/latency sweep (FREE, the primary deliverable).

For each HW in the sweep and the frozen fuzzy operator (tau=0.10), compute per clip:
  - worst-case containment: does the HW-crop for the WORST plausible phrasing contain
    the whole frame-0 GT box? (6 clips)
  - all-phrasing containment: over every (clip x plausible-phrasing) pair.
  - crop-area frac: worst-case crop's capped pixels / capped full frame (latency proxy).
Plus tau sensitivity at {0.05, 0.15}.

HW* = the smallest HW with 100% worst-case containment on all 6 clips. If E20's HW
(0.2667) is already 100%, that is flagged [already-tolerant] (no bigger cell needed).

    .venv-ft/bin/python experiments/2026-07-04-tolerant-cells/phase0.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cells  # noqa: E402
from cells import (GT0, HW_E20, crop_area_frac, crop_rect, contains, gt0_box,  # noqa: E402
                   hint_for, plausible_hints, worst_hint)

W, H = 1280, 720
HW_SWEEP = [HW_E20, 0.32, 0.38, 0.44, 0.50]
TAU = 0.10
TAU_SENS = [0.05, 0.15]
CLIPS = ["car3", "car7", "car9", "car10", "car14", "car18"]


def worstcase_contained(hw: float, tau: float):
    """Per clip: (worst_hint, contained?) at a HW for the worst-case plausible phrasing."""
    out = {}
    for clip in CLIPS:
        box = gt0_box(clip)
        wh = worst_hint(box, W, H, tau)
        out[clip] = (wh, contains(crop_rect(wh, W, H, hw), box))
    return out


def allphrasing_rate(hw: float, tau: float):
    """Containment rate over every (clip x plausible-phrasing) pair at a HW."""
    n = ok = 0
    for clip in CLIPS:
        box = gt0_box(clip)
        for hint in plausible_hints(box, W, H, tau):
            n += 1
            ok += contains(crop_rect(hint, W, H, hw), box)
    return ok, n


def main():
    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit("E23 Phase-0 cell sweep (offline, free) -- frame-0 GT, 1280x720, tau=0.10")
    emit("=" * 78)
    emit()
    emit("Per-clip fuzz exposure (tau=0.10):")
    emit(f"  {'clip':6} {'cx':>6} {'cy':>6}  {'true':>13}  {'worst_hint':>13}  "
         f"{'plausible':<28}")
    for clip in CLIPS:
        box = gt0_box(clip)
        cx = (box[0] + box[2]) / 2 / W
        cy = (box[1] + box[3]) / 2 / H
        true = hint_for(box, W, H)
        wh = worst_hint(box, W, H, TAU)
        pl = ",".join(plausible_hints(box, W, H, TAU))
        emit(f"  {clip:6} {cx:6.3f} {cy:6.3f}  {true:>13}  {wh:>13}  {pl:<28}")
    emit()

    emit("Sweep (worst-case containment /6, all-phrasing rate, mean worst-case area frac):")
    emit(f"  {'HW':>7} {'wc_contain':>11} {'allphrase':>11} {'mean_area':>10} "
         f"{'note':<16}")
    wc_by_hw, area_by_hw = {}, {}
    hw_star = None
    for hw in HW_SWEEP:
        wc = worstcase_contained(hw, TAU)
        n_wc = sum(1 for _, c in wc.values() if c)
        ok, n = allphrasing_rate(hw, TAU)
        areas = [crop_area_frac(wc[clip][0], W, H, hw) for clip in CLIPS]
        mean_area = sum(areas) / len(areas)
        wc_by_hw[hw] = n_wc
        area_by_hw[hw] = mean_area
        note = "E20-equiv" if abs(hw - HW_E20) < 1e-9 else ""
        if n_wc == 6 and hw_star is None:
            hw_star = hw
            note = (note + " HW*").strip()
        emit(f"  {hw:7.4f} {n_wc:>7}/6   {ok:>4}/{n:<4}  {mean_area:>9.3f} {note:<16}")
    emit()

    emit("Per-clip worst-case containment across HW (1=contained, 0=escapes):")
    hdr = "  " + f"{'clip':6} " + " ".join(f"{hw:>7.4f}" for hw in HW_SWEEP)
    emit(hdr)
    for clip in CLIPS:
        row = f"  {clip:6} "
        for hw in HW_SWEEP:
            wc = worstcase_contained(hw, TAU)
            row += f"{1 if wc[clip][1] else 0:>8}"
        emit(row)
    emit()

    emit(f"tau sensitivity (worst-case containment /6 at tau in {TAU_SENS + [TAU]}):")
    emit(f"  {'HW':>7} " + " ".join(f"tau={t:<5}" for t in sorted(TAU_SENS + [TAU])))
    for hw in HW_SWEEP:
        row = f"  {hw:7.4f} "
        for t in sorted(TAU_SENS + [TAU]):
            wc = worstcase_contained(hw, t)
            n = sum(1 for _, c in wc.values() if c)
            row += f"{n:>3}/6    "
        emit(row)
    emit()

    e20_wc = wc_by_hw[HW_E20]
    already = e20_wc == 6
    emit("-" * 78)
    emit(f"E20 HW (0.2667) worst-case containment = {e20_wc}/6"
         + ("  [already-tolerant]" if already else "  (< 6/6 -> too cagey, E23 justified)"))
    if hw_star is None:
        emit("HW* = NONE reaches 6/6 worst-case containment below 0.50 -> verdict NO gate")
    elif already:
        emit(f"HW* = {HW_E20:.4f} (E20's own HW already 100%): reconfirm E20 on device, "
             "no bigger cell")
    else:
        emit(f"HW* = {hw_star:.4f} (smallest HW with 6/6 worst-case containment), "
             f"mean worst-case area frac {area_by_hw[hw_star]:.3f} "
             f"(vs E20 {area_by_hw[HW_E20]:.3f})")
    emit("-" * 78)

    (HERE / "raw").mkdir(exist_ok=True)
    (HERE / "raw" / "phase0_cell_sweep.txt").write_text("\n".join(lines) + "\n")

    # plot: worst-case containment (bars) + mean worst-case crop-area frac (line) vs HW
    (HERE / "proof").mkdir(exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(7, 4.2))
    xs = list(range(len(HW_SWEEP)))
    labels = [f"{hw:.3f}" + ("\n(E20)" if abs(hw - HW_E20) < 1e-9 else "") for hw in HW_SWEEP]
    conts = [wc_by_hw[hw] for hw in HW_SWEEP]
    colors = ["#4C9F70" if c == 6 else "#C24B4B" for c in conts]
    ax1.bar(xs, conts, color=colors, alpha=0.85, width=0.6)
    ax1.axhline(6, ls="--", lw=1, color="#4C9F70")
    ax1.set_ylabel("worst-case containment /6", color="#2f6b4a")
    ax1.set_ylim(0, 6.5)
    ax1.set_xticks(xs)
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.set_xlabel("cell half-width HW (fraction of axis)")
    for x, c in zip(xs, conts):
        ax1.text(x, c + 0.08, f"{c}/6", ha="center", fontsize=9, color="#333")
    ax2 = ax1.twinx()
    ax2.plot(xs, [area_by_hw[hw] for hw in HW_SWEEP], "o-", color="#C2872B", lw=2)
    ax2.set_ylabel("mean worst-case crop-area frac (latency proxy)", color="#8a5f1e")
    ax2.set_ylim(0, 1.0)
    star_note = ""
    if hw_star is not None:
        sx = HW_SWEEP.index(hw_star)
        ax1.text(sx, 0.3, "HW*", ha="center", fontsize=11, fontweight="bold",
                 color="white")
        star_note = f"  HW*={hw_star:.3f}"
    ax1.set_title(f"E23 tolerant cells: containment vs crop area (tau=0.10){star_note}")
    fig.tight_layout()
    fig.savefig(HERE / "proof" / "cell_sweep.png", dpi=130)
    print("wrote raw/phase0_cell_sweep.txt + proof/cell_sweep.png")


if __name__ == "__main__":
    main()
