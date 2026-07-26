"""EXP-8 proof figures, reproducible from runs/exp8/{results,ring}.json (no device needed).

  .venv-ft/bin/python experiments/2026-07-26-carry-memory-horizon/make_proof.py --out runs/exp8
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
PROOF = HERE / "proof"


def horizon_elbow(res: dict) -> None:
    """The elbow figure: IoU and ms/step vs K, and vs M. EXP-1's elbow one axis over."""
    arms = res["arms"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    # One ms scale for both panels. Let matplotlib autoscale and the M panel's 0.6 ms of
    # run-to-run noise fills the axis and reads as a dramatic effect; on K's real scale it
    # is the flat line it actually is.
    all_ms = [a["median_ms"] for a in arms.values()]
    ms_lim = (min(all_ms) - 2, max(all_ms) + 2)
    for ax, key, lab in ((axes[0], "K", "num_maskmem K (dense recent frames)"),
                         (axes[1], "M", "max_obj_ptrs_in_encoder M (sparse pointers)")):
        other = "M" if key == "K" else "K"
        stock = 16 if key == "K" else 7           # the held-constant value of the other lever
        pts = sorted(((a["K"] if key == "K" else a["M"], a)
                      for a in arms.values() if (a[other] == stock)), key=lambda t: t[0])
        xs = [p[0] for p in pts]
        ax.plot(xs, [p[1]["median_of_median_iou"] for p in pts], "o-", color="tab:blue",
                label="median-of-median IoU")
        ax.set_xlabel(lab)
        ax.set_ylabel("median IoU", color="tab:blue")
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.3)
        ax2 = ax.twinx()
        ax2.plot(xs, [p[1]["median_ms"] for p in pts], "s--", color="tab:red",
                 label="ms/step (Orin)")
        ax2.set_ylim(*ms_lim)
        ax2.set_ylabel("ms / step on the Orin", color="tab:red")
        base = arms["base"]
        ax.axhline(base["median_of_median_iou"], color="gray", lw=0.8, ls=":")
        ax.set_title(f"{key} sweep ({other}={stock} held), n={res['n_clips']} UAV123 clips")
    fig.suptitle("EXP-8 -- SAM2 memory horizon: K trades accuracy for a shallow latency slope, "
                 f"M is inert on both axes (image_size={res['size']}, Orin 15 W + jetson_clocks)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(PROOF / "horizon_elbow.png", dpi=130)
    print("wrote proof/horizon_elbow.png")


def ring_identity(ring: dict) -> None:
    """H1: mask bit-identity vs P, with the predicted step, plus what the ring costs in RAM."""
    rows = ring["rows"]
    ps = [r["P"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].plot(ps, [100 * r["identical_frac"] for r in rows], "o-", color="tab:blue")
    axes[0].axvline(ring["predicted_boundary"], color="tab:green", ls="--",
                    label=f"predicted boundary P={ring['predicted_boundary']}")
    if ring["measured_boundary"]:
        axes[0].axvline(ring["measured_boundary"], color="tab:red", ls=":",
                        label=f"measured P={ring['measured_boundary']}")
    axes[0].set_xscale("log")
    axes[0].set_xticks(ps)
    axes[0].set_xticklabels(ps, rotation=45)
    axes[0].set_xlabel("PRUNE_AFTER P (frames retained)")
    axes[0].set_ylabel("% steps bit-identical to P=100")
    axes[0].set_ylim(-2, 102)
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[0].set_title("the ring is inert above the horizon")
    # Growth, not peak, is the ring's own cost: peak RSS carries a per-process baseline
    # (the P=8 arm booted 580 MB lighter) that has nothing to do with how many frames are held.
    axes[1].plot(ps, [r["rss_growth_mb"] for r in rows], "s-", color="tab:red",
                 label="host RSS growth over the 120-step run (the ring)")
    axes[1].plot(ps, [r["peak_rss_mb"] for r in rows], "s:", color="tab:red", alpha=0.45,
                 label="peak RSS (carries a process baseline)")
    axes[1].plot(ps, [r["peak_cuda_mb"] for r in rows], "^-", color="tab:orange", label="peak CUDA")
    axes[1].set_xscale("log")
    axes[1].set_xticks(ps)
    axes[1].set_xticklabels(ps, rotation=45)
    axes[1].set_xlabel("PRUNE_AFTER P (frames retained)")
    axes[1].set_ylabel("MB")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=7)
    axes[1].set_title("what the retained frames cost (~8.1 MB/frame held)")
    fig.suptitle("EXP-8 Stage 0 -- PRUNE_AFTER identity: everything above the 15-step read "
                 "window is dead weight", fontsize=10)
    fig.tight_layout()
    fig.savefig(PROOF / "ring_identity.png", dpi=130)
    print("wrote proof/ring_identity.png")


def refind(res: dict) -> None:
    """The horizon-specific metric D-R16.2 feared losing: can a lost track come back?"""
    arms = res["arms"]
    names = [n for n in arms if arms[n]["refind_rate"] is not None]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    rates = [100 * arms[n]["refind_rate"] for n in names]
    lo = [100 * arms[n]["refind_ci95"][0] for n in names]
    hi = [100 * arms[n]["refind_ci95"][1] for n in names]
    ax.bar(names, rates, color=["tab:gray" if n == "base" else "tab:blue" for n in names])
    ax.errorbar(names, rates, yerr=[[r - l for r, l in zip(rates, lo)],
                                    [h - r for r, h in zip(rates, hi)]],
                fmt="none", ecolor="black", capsize=3, lw=1)
    for i, n in enumerate(names):
        a = arms[n]
        ax.text(i, rates[i] + 2, f"{a['refind'][0]}/{a['refind'][1]}", ha="center", fontsize=7)
    ax.axhline(100 * arms["base"]["refind_rate"], color="tab:gray", ls=":", lw=1)
    ax.set_ylabel(f"% of lost steps re-found within 5 steps (Wilson CI95)")
    ax.set_title("EXP-8 -- re-find after loss per arm: shortening the memory horizon does not "
                 "cost recovery", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(PROOF / "refind_by_arm.png", dpi=130)
    print("wrote proof/refind_by_arm.png")


def drift_clip(out: Path, clip: str, arms: list[str], fps: int = 6) -> None:
    """Behaviour is the point here, so: a clip, not a figure (per-experiment workflow rule).

    Side-by-side GT (green) vs the carried box (cyan) for the same frames under each arm, so
    the failure is watchable -- a shortened memory does not fail by drifting a few pixels, it
    fails by letting the mask leak onto a neighbour or by dropping the object outright.
    """
    import cv2
    import numpy as np
    sys.path.insert(0, str(HERE))
    from run_exp8 import _draw, frame                                   # noqa: E402
    plan = {e["clip"]: e for e in json.loads((out / "plan.json").read_text())}[clip]
    carry = {a: json.loads((out / f"carry_{a}.json").read_text())[clip] for a in arms}
    res = json.loads((out / "results.json").read_text())["per_clip"]
    vw, tmp = None, out / f"_drift_{clip}.mp4"
    for st in plan["steps"]:
        panels = []
        for a in arms:
            img = frame(clip, st["frame"]).copy()
            b = carry[a]["boxes"][st["j"]]
            _draw(img, tuple(st["gt"]), (0, 200, 0), "GT")
            _draw(img, tuple(b) if b else None, (255, 255, 0), "carry")
            iou_j = res[a][clip]["ious"][st["j"]]
            cv2.rectangle(img, (0, 0), (img.shape[1], 46), (0, 0, 0), -1)
            cv2.putText(img, f"{a}   IoU={iou_j:.2f}", (10, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            panels.append(cv2.resize(img, (640, 360)))
        grid = np.hstack(panels)
        if vw is None:
            vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps,
                                 (grid.shape[1], grid.shape[0]))
        vw.write(grid)
    vw.release()
    dst = PROOF / f"drift_{clip}.mp4"
    # re-encode to h264 so it plays outside opencv; mp4v is a viewer coin-flip
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)], check=True)
    tmp.unlink()
    print(f"wrote proof/{dst.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/exp8")
    ap.add_argument("--drift", default="", help="clip name -> proof/drift_<clip>.mp4")
    ap.add_argument("--drift-arms", default="base,K5,K1")
    a = ap.parse_args()
    out = Path(a.out)
    PROOF.mkdir(exist_ok=True)
    if a.drift:
        drift_clip(out, a.drift, [s for s in a.drift_arms.split(",") if s])
    if (out / "ring.json").exists():
        ring_identity(json.loads((out / "ring.json").read_text()))
    if (out / "results.json").exists():
        res = json.loads((out / "results.json").read_text())
        horizon_elbow(res)
        refind(res)


if __name__ == "__main__":
    main()
