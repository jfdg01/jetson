#!/usr/bin/env python3
"""R-13 host half -- score the OWLv2 raw boxes and pair them against the VLM.

    PYTHONPATH=. .venv-ft/bin/python experiments/2026-07-21-detector-baseline/score_r13.py

The device script emits boxes in ORIGINAL PIXEL coordinates. The project's GT and
every VLM number live in the contract's 0-`COORD_SCALE` normalized space, so the
detector boxes are normalized here through `grounding.contract.normalize_bbox`.
That conversion is the whole reason scoring is split off the device: the first
smoke run compared pixel boxes against 0-100 GT and returned IoU 0.000 on every
sample, which is the same coordinate-space contamination the 2026-06-25 campaign
hit with the 0-1000 checkpoint. One scoring path, applied once, on the host.

The VLM comparator is arm A of `../2026-07-21-roi-ondevice/` -- same 439 samples,
same board, same session, no re-run.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from grounding import stats
from grounding.contract import IOU_GATE_THRESHOLD, iou, normalize_bbox

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
VLM_ITEMS = HERE.parent / "2026-07-21-roi-ondevice" / "raw" / "items-full.jsonl"
ARMS = ("full", "phrase", "head")


def key(r: dict) -> str:
    return f"{r['image_path']}||{r['caption']}"


def norm(boxes: list, wh: list) -> list:
    w, h = wh
    return [normalize_bbox(b, w, h) for b in boxes]


def summarise(name: str, per_item: dict[str, dict]) -> dict:
    ious = [v["iou"] for v in per_item.values()]
    k = sum(v["gate_pass"] for v in per_item.values())
    cx = [(v["pred"][0] + v["pred"][2]) / 2 for v in per_item.values() if v["pred"]]
    cy = [(v["pred"][1] + v["pred"][3]) / 2 for v in per_item.values() if v["pred"]]
    return {
        "arm": name, "k": k, "n": len(per_item),
        "iou_gate_pass_rate": round(k / len(per_item), 6),
        "mean_iou": round(statistics.mean(ious), 6),
        "center_std": round((statistics.pstdev(cx) + statistics.pstdev(cy)) / 2, 3)
        if len(cx) > 1 else 0.0,
    }


def main() -> None:
    rows = [json.loads(l) for l in (RAW / "owlv2.jsonl").read_text().splitlines() if l.strip()]
    meta = json.loads((RAW / "owlv2.meta.json").read_text())
    vlm = {key(json.loads(l)): json.loads(l)
           for l in VLM_ITEMS.read_text().splitlines() if l.strip()}
    print(f"[r13] {len(rows)} detector rows, {len(vlm)} VLM rows")

    scored: dict[str, dict[str, dict]] = {a: {} for a in ARMS}
    scored["oracle"] = {}
    lat: dict[str, list[float]] = {a: [] for a in ARMS}

    for r in rows:
        kk, gt, wh = key(r), r["gt"], r["img_wh"]
        best_any, best_any_box = 0.0, None
        for arm in ARMS:
            nb = norm(r[arm]["boxes"], wh)
            top1 = nb[0] if nb else None
            v = iou(top1, gt) if top1 else 0.0
            scored[arm][kk] = {"pred": top1, "iou": round(v, 6),
                               "gate_pass": bool(top1) and v >= IOU_GATE_THRESHOLD}
            lat[arm].append(r[arm]["fwd_ms"])
            # oracle: best of top-k across EVERY arm's proposals, chosen with the GT.
            for b in nb:
                vb = iou(b, gt)
                if vb > best_any:
                    best_any, best_any_box = vb, b
        scored["oracle"][kk] = {"pred": best_any_box, "iou": round(best_any, 6),
                                "gate_pass": best_any >= IOU_GATE_THRESHOLD}

    out: dict = {"meta": meta, "n": len(rows),
                 "n_effective": len({r["image_path"] for r in rows}), "arms": {}}
    for a in (*ARMS, "oracle"):
        s = summarise(a, scored[a])
        if a in lat:
            s["fwd_ms_median"] = round(statistics.median(lat[a]), 1)
        out["arms"][a] = s
        print(f"[r13] {s}")

    # VLM comparator, from R-14 arm A. Not re-run.
    vlm_pass = {k: int(v["gate_pass"]) for k, v in vlm.items()}
    out["arms"]["vlm"] = {
        "arm": "qwen2-vl-2b-q8_0-fullframe@1024", "k": sum(vlm_pass.values()),
        "n": len(vlm_pass),
        "iou_gate_pass_rate": round(sum(vlm_pass.values()) / len(vlm_pass), 6),
        "mean_iou": round(statistics.mean(v["iou"] for v in vlm.values()), 6),
        "source": str(VLM_ITEMS.relative_to(HERE.parent.parent)),
    }
    print(f"[r13] {out['arms']['vlm']}")

    n_eff = out["n_effective"]
    out["paired"] = {}
    for a in (*ARMS, "oracle"):
        arm_pass = {k: int(v["gate_pass"]) for k, v in scored[a].items()}
        b, c, n_paired = stats.discordant_counts(vlm_pass, arm_pass)  # b = VLM right, det wrong
        bd, _ = stats.deflate_to_effective(b, n_paired, n_eff)
        cd, _ = stats.deflate_to_effective(c, n_paired, n_eff)
        out["paired"][f"vlm_vs_{a}"] = {
            "b_vlm_only": b, "c_det_only": c, "n_paired": n_paired,
            "b_deflated": bd, "c_deflated": cd, "n_effective": n_eff,
            "p_raw": stats.mcnemar(b, c), "p_deflated": stats.mcnemar(bd, cd),
        }
        print(f"[r13] VLM vs {a}: {out['paired'][f'vlm_vs_{a}']}")

    (HERE / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    with (RAW / "scored.jsonl").open("w") as f:
        for kk in scored["full"]:
            f.write(json.dumps({"key": kk, **{a: scored[a][kk] for a in (*ARMS, "oracle")},
                                "vlm": vlm_pass.get(kk)}) + "\n")
    print(f"[r13] -> {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
