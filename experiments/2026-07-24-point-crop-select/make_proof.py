"""EXP-2 proof figures (DoD-7), reproducible from runs/exp2/*.json.

  proof/grounding_elbow.png : grounding accuracy (hit-rate @ IoU>=0.5 + median IoU) vs VLM feed
                              resolution, NL whole-frame vs PT point-crop. The headline: PT reaches
                              its ceiling at a ~256px crop, out-grounding NL at full 1024px.
  proof/carry_robustness.png: SELECT PASS (WSEL/SWAP, NL vs PT) vs SAM2 carry image_size -- the
                              verdict's robustness to the tracker-res knob (if carry_res_sweep ran).
  proof/deliver_pass.png    : primary NL-vs-PT delivered PASS at the deployed res (bar).

    .venv-ft/bin/python make_proof.py --out runs/exp2
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent


def grounding_elbow(out: Path, proof: Path):
    g = json.loads((out / "ground_sweep.json").read_text())
    nl_x = sorted(int(k) for k in g["nl"])
    pt_x = sorted(int(k) for k in g["pt"])
    nl_hit = [g["nl"][str(s)]["hit_rate"] for s in nl_x]
    pt_hit = [g["pt"][str(s)]["hit_rate"] for s in pt_x]
    nl_iou = [g["nl"][str(s)]["median_iou"] for s in nl_x]
    pt_iou = [g["pt"][str(s)]["median_iou"] for s in pt_x]

    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    ax.plot(nl_x, nl_hit, "o-", color="#d62728", lw=2, label="NL whole-frame (hit @IoU>=0.5)")
    ax.plot(pt_x, pt_hit, "s-", color="#1f77b4", lw=2, label="PT point-crop (hit @IoU>=0.5)")
    ax.plot(nl_x, nl_iou, "o--", color="#d62728", lw=1, alpha=0.5, label="NL median IoU")
    ax.plot(pt_x, pt_iou, "s--", color="#1f77b4", lw=1, alpha=0.5, label="PT median IoU")
    # deployed operating points
    ax.axvline(1024, color="#d62728", ls=":", lw=1)
    ax.axvline(512, color="#1f77b4", ls=":", lw=1)
    ax.annotate("PT@256 > NL@1024", xy=(256, g["pt"]["256"]["hit_rate"]),
                xytext=(330, 0.30), fontsize=9,
                arrowprops=dict(arrowstyle="->", color="k", lw=1))
    ax.set_xlabel("VLM feed resolution (px)  --  NL: full-frame long edge / PT: crop upscale")
    ax.set_ylabel("grounding accuracy")
    ax.set_ylim(0, 1); ax.grid(alpha=0.25)
    ax.set_xticks(sorted(set(nl_x) | set(pt_x)))
    ax.set_title(f"EXP-2 grounding-res elbow (n={g['n_cells']} WSEL cells, Orin)\n"
                 "the point-crop concentrates the VLM's resolution onto the target")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout(); fig.savefig(proof / "grounding_elbow.png", dpi=130)
    plt.close(fig)
    return nl_x, nl_hit, pt_x, pt_hit


def carry_robustness(out: Path, proof: Path):
    f = out / "carry_res_sweep.json"
    if not f.exists():
        print("  (carry_res_sweep.json absent -- skipping carry_robustness.png)")
        return
    r = json.loads(f.read_text())
    sizes = sorted(int(s) for s in r["by_size"])
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    series = [("WSEL", "nl_pass", "#d62728", "o-", "WSEL NL"),
              ("WSEL", "pt_pass", "#1f77b4", "s-", "WSEL PT"),
              ("SWAP", "nl_pass", "#d62728", "o--", "SWAP NL"),
              ("SWAP", "pt_pass", "#1f77b4", "s--", "SWAP PT")]
    n = r["by_size"][str(sizes[0])]["legs"]["WSEL"]["n"]
    for leg, key, col, sty, lab in series:
        ys = [r["by_size"][str(s)]["legs"][leg][key] for s in sizes]
        ax.plot(sizes, ys, sty, color=col, lw=1.8, label=lab)
    ax.set_xlabel("SAM2 carry image_size (px)"); ax.set_ylabel(f"select PASS (/{n})")
    ax.set_xticks(sizes); ax.set_ylim(0, n + 1); ax.grid(alpha=0.25)
    ax.set_title(f"EXP-2 select PASS vs carry image_size (acquire boxes fixed, n={n})\n"
                 "verdict robustness to the tracker-resolution knob")
    ax.legend(fontsize=8, loc="lower left", ncol=2)
    fig.tight_layout(); fig.savefig(proof / "carry_robustness.png", dpi=130)
    plt.close(fig)


def deliver_pass(out: Path, proof: Path):
    r = json.loads((out / "results.json").read_text())
    legs = ["WSEL", "SWAP"]
    nl = [r["legs"][l]["nl_pass"] for l in legs]
    pt = [r["legs"][l]["pt_pass"] for l in legs]
    n = [r["legs"][l]["n"] for l in legs]
    x = range(len(legs))
    fig, ax = plt.subplots(figsize=(5.0, 4.2))
    ax.bar([i - 0.2 for i in x], nl, 0.4, color="#d62728", label="NL", edgecolor="k")
    ax.bar([i + 0.2 for i in x], pt, 0.4, color="#1f77b4", label="PT", edgecolor="k")
    for i, (a, b, tot) in enumerate(zip(nl, pt, n)):
        ax.text(i - 0.2, a + 0.2, f"{a}/{tot}", ha="center", fontsize=9)
        ax.text(i + 0.2, b + 0.2, f"{b}/{tot}", ha="center", fontsize=9)
    ax.set_xticks(list(x)); ax.set_xticklabels(legs)
    ax.set_ylabel("delivered PASS"); ax.set_ylim(0, max(n) + 3)
    ax.set_title("EXP-2 delivered PASS at deployed res\n(NL max_side=1024, PT crop=512)")
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.25)
    fig.tight_layout(); fig.savefig(proof / "deliver_pass.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "runs" / "exp2"))
    a = ap.parse_args()
    out = Path(a.out)
    proof = HERE / "proof"; proof.mkdir(exist_ok=True)
    nl_x, nl_hit, pt_x, pt_hit = grounding_elbow(out, proof)
    carry_robustness(out, proof)
    deliver_pass(out, proof)
    print(f"wrote grounding_elbow.png (+carry_robustness/deliver_pass) -> {proof}")
    print(f"  NL hit@feed: {dict(zip(nl_x, nl_hit))}")
    print(f"  PT hit@feed: {dict(zip(pt_x, pt_hit))}")


if __name__ == "__main__":
    main()
