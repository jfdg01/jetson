"""EXP-8 -- SAM2 memory-horizon levers (num_maskmem K / max_obj_ptrs M / ring P), ON THE ORIN.

Fork of EXP-1's run_exp1.py: same UAV123 bank, same seed policy, same ssh-stdio bridge. The
only factor that changes between arms is SAM2's temporal memory; image_size is held at the
EXP-1 elbow (640) except where an arm says otherwise. NO torch/SAM2 here, NO 3090.

  stage : plan.json (38-clip sweep bank) + plan_ring.json (3 clips x 120 steps, ring fires)
  ring  : P in {8,14,15,16,32,100} with --mask-hash; bit-identity vs P=100 (H1)
  carry : one bridge per arm; per clip re-init + step; carry_<arm>.json
  score : IoU vs GT, re-find rate, paired Wilcoxon + McNemar vs base, Holm over the family

    .venv-ft/bin/python run_exp8.py stage --out runs/exp8
    .venv-ft/bin/python run_exp8.py ring  --out runs/exp8
    .venv-ft/bin/python run_exp8.py carry --out runs/exp8
    .venv-ft/bin/python run_exp8.py score --out runs/exp8
"""
from __future__ import annotations

import argparse
import json
import pickle
import struct
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-07-20-n25-select"))
sys.path.insert(0, str(REPO / "grounding"))
from curate_p518 import DATA, clip_len, frame, load_gt  # noqa: E402
import stats as gstats                                  # noqa: E402  grounding/stats.py

STRIDE, N_STEPS = 11, 24          # EXP-1 bank, unchanged: ~264 frames ~= 8.8 s
SPAN = N_STEPS * STRIDE
MIN_CLIPS = 25
RING_STRIDE, RING_STEPS, RING_CLIPS = 2, 120, 3   # long enough that the ring actually pops
RING_PS = [8, 14, 15, 16, 32, 100]
SIZE = 640                        # EXP-1 elbow, the deployed carry res
REFIND_WINDOW = 5                 # steps a lost track gets to come back

BRIDGE = ("cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py"
          " --image-size {size} --num-maskmem {K} --max-obj-ptrs {M} --prune-after {P}{extra}")

# name -> (K, M). base is the deployed config and the shared baseline of both sweeps.
ARMS = {"base": (7, 16),
        "K5": (5, 16), "K4": (4, 16), "K3": (3, 16), "K2": (2, 16), "K1": (1, 16),
        "M8": (7, 8), "M4": (7, 4), "M2": (7, 2), "M32": (7, 32)}
BASE_P = 32


def iou(a, b) -> float:
    if a is None or b is None:
        return 0.0
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / ua if ua > 0 else 0.0


# ---- ssh bridge framing (host side of carry_ssh_bridge.py) --------------------
def _send(f, obj):
    data = pickle.dumps(obj)
    f.write(struct.pack(">I", len(data)))
    f.write(data)
    f.flush()


def _recv(f):
    hdr = b""
    while len(hdr) < 4:
        more = f.read(4 - len(hdr))
        if not more:
            return None
        hdr += more
    (n,) = struct.unpack(">I", hdr)
    buf = b""
    while len(buf) < n:
        more = f.read(n - len(buf))
        if not more:
            return None
        buf += more
    return pickle.loads(buf)


def _rgb_jpg(clip: str, idx: int) -> bytes:
    """UAV123 frame (BGR on disk) -> RGB JPEG; StreamCarry expects RGB, bridge does no swap."""
    rgb = cv2.cvtColor(frame(clip, idx), cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


# ---- stage --------------------------------------------------------------------
def _first_contiguous_seed(gt: list, span: int):
    run = 0
    for i, g in enumerate(gt):
        run = run + 1 if g is not None else 0
        if run >= span + 1:
            return i - span
    return None


def _plan(stride: int, n_steps: int, limit: int | None = None) -> list:
    span = stride * n_steps
    plan = []
    for clip in sorted(d.name for d in (DATA / "data_seq" / "UAV123").iterdir() if d.is_dir()):
        try:
            gt = load_gt(clip)
        except Exception:
            continue
        if clip_len(clip) < span + 1:
            continue
        seed = _first_contiguous_seed(gt, span)
        if seed is None:
            continue
        plan.append({"clip": clip, "seed": seed, "seed_box": [int(v) for v in gt[seed]],
                     "steps": [{"j": k, "frame": seed + (k + 1) * stride,
                                "gt": list(gt[seed + (k + 1) * stride])} for k in range(n_steps)]})
        if limit and len(plan) >= limit:
            break
    return plan


def stage(out: Path) -> None:
    plan = _plan(STRIDE, N_STEPS)
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(f"[stage] sweep bank: {len(plan)} clips (need >={MIN_CLIPS}): "
          f"{[p['clip'] for p in plan]}", flush=True)
    assert len(plan) >= MIN_CLIPS, f"only {len(plan)} clips < {MIN_CLIPS}"
    ring = _plan(RING_STRIDE, RING_STEPS, limit=RING_CLIPS)
    (out / "plan_ring.json").write_text(json.dumps(ring, indent=1))
    print(f"[stage] ring bank: {[p['clip'] for p in ring]} x {RING_STEPS} steps "
          f"@stride {RING_STRIDE}", flush=True)
    assert len(ring) == RING_CLIPS


# ---- carry (on the Orin, one bridge per arm) ----------------------------------
def _run_arm(plan, out: Path, tag: str, size: int, K: int, M: int, P: int,
             mask_hash: bool = False) -> bool:
    """Stream every clip through one bridge process. Returns False if the arm died."""
    dst = out / f"carry_{tag}.json"
    if dst.exists():
        print(f"[carry] {tag} already done -- skip", flush=True)
        return True
    cmd = BRIDGE.format(size=size, K=K, M=M, P=P, extra=" --mask-hash" if mask_hash else "")
    log = open(out / f"bridge_{tag}.err", "wb")
    proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", cmd],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
    res, t_all = {}, time.time()
    # ponytail: one bad arm (assert in the bridge, OOM) must not abort the sweep.
    try:
        for pi, entry in enumerate(plan):
            _send(proc.stdin, ("init", _rgb_jpg(entry["clip"], entry["seed"]), entry["seed_box"]))
            ack = _recv(proc.stdout)
            assert ack and ack.get("ok"), f"init failed {entry['clip']} arm={tag}: {ack}"
            rec = {"boxes": [], "ms": [], "cuda_mb": [], "rss_mb": [], "mh": []}
            for st in entry["steps"]:
                _send(proc.stdin, ("step", _rgb_jpg(entry["clip"], st["frame"])))
                r = _recv(proc.stdout)
                assert r is not None, f"bridge died {entry['clip']} arm={tag} step={st['j']}"
                rec["boxes"].append(r["box"])
                rec["ms"].append(r["ms"])
                rec["cuda_mb"].append(r.get("cuda_mb"))
                rec["rss_mb"].append(r.get("rss_mb"))
                rec["mh"].append(r.get("mh"))
            res[entry["clip"]] = rec
            print(f"[carry] {tag} [{pi + 1}/{len(plan)}] {entry['clip']} "
                  f"median_ms={np.median([m for m in rec['ms'] if m]):.0f} "
                  f"rss={rec['rss_mb'][-1]}MB", flush=True)
    except (AssertionError, BrokenPipeError, OSError) as e:
        proc.kill()
        log.close()
        print(f"[carry] {tag} DIED ({e}); see bridge_{tag}.err -- skipping", flush=True)
        return False
    proc.stdin.close()
    proc.wait()
    log.close()
    dst.write_text(json.dumps(res, indent=1))
    print(f"[carry] {tag} done {len(res)} clips in {time.time() - t_all:.0f}s -> {dst.name}",
          flush=True)
    return True


def carry(out: Path, arms: list[str]) -> None:
    plan = json.loads((out / "plan.json").read_text())
    for name in arms:
        K, M = ARMS[name]
        _run_arm(plan, out, name, SIZE, K, M, BASE_P)


def ring(out: Path) -> None:
    """H1: the ring is inert above the horizon. Prediction: P>=15 bit-identical to P=100."""
    plan = json.loads((out / "plan_ring.json").read_text())
    for P in RING_PS:
        _run_arm(plan, out, f"ringP{P}", SIZE, 7, 16, P, mask_hash=True)
    ref = json.loads((out / f"carry_ringP{RING_PS[-1]}.json").read_text())
    rows = []
    for P in RING_PS:
        f = out / f"carry_ringP{P}.json"
        if not f.exists():
            continue
        cur = json.loads(f.read_text())
        same = tot = 0
        for clip, rec in cur.items():
            for a, b in zip(rec["mh"], ref[clip]["mh"]):
                assert a and b, "no mask hash -- rerun ring with --mask-hash"
                tot += 1
                same += a == b
        ious = []
        for entry in plan:
            for st, cb in zip(entry["steps"], cur[entry["clip"]]["boxes"]):
                ious.append(iou(tuple(cb) if cb else None, tuple(st["gt"])))
        # The ring's OWN cost is per-clip growth, not peak: peak RSS carries a process
        # baseline (P=8 booted 580 MB lighter than every other arm) that has nothing to
        # do with the ring. Growth = last step - first step, maxed over clips.
        rows.append({"P": P, "identical_frac": round(same / tot, 4),
                     "median_iou": round(float(np.median(ious)), 3),
                     "rss_growth_mb": round(max(r["rss_mb"][-1] - r["rss_mb"][0]
                                                for r in cur.values()), 1),
                     "peak_rss_mb": max(max(r["rss_mb"]) for r in cur.values()),
                     "peak_cuda_mb": max(max(r["cuda_mb"]) for r in cur.values()),
                     "median_ms": round(float(np.median(
                         [m for r in cur.values() for m in r["ms"] if m])), 1)})
        print(f"[ring] P={P:>3} identical={rows[-1]['identical_frac']:.4f} "
              f"medIoU={rows[-1]['median_iou']} rss={rows[-1]['peak_rss_mb']}MB "
              f"cuda={rows[-1]['peak_cuda_mb']}MB", flush=True)
    boundary = min((r["P"] for r in rows if r["identical_frac"] == 1.0), default=None)
    print(f"[ring] H1 predicted the identity boundary at P=15; measured lowest identical P="
          f"{boundary}  ->  {'CONFIRMED' if boundary == 15 else 'REFUTED'}", flush=True)
    (out / "ring.json").write_text(json.dumps(
        {"rows": rows, "predicted_boundary": 15, "measured_boundary": boundary}, indent=1))


# ---- score --------------------------------------------------------------------
def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(12, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def _refind(ious: list[float], thr: float = 0.25, w: int = REFIND_WINDOW):
    """(n_lost, n_refound): a lost step counts as refound if IoU>=thr within the next w steps.

    The horizon-specific metric: D-R16.2 feared a short memory would stop SAM2 re-finding an
    occluded target, and a median IoU cannot see that.
    """
    lost = refound = 0
    for i, v in enumerate(ious):
        if v >= thr:
            continue
        lost += 1
        refound += any(u >= thr for u in ious[i + 1:i + 1 + w])
    return lost, refound


def _per_clip(plan, rec_by_clip):
    summ = {}
    for entry in plan:
        cr = rec_by_clip[entry["clip"]]
        ious = [iou(tuple(cb) if cb else None, tuple(st["gt"]))
                for st, cb in zip(entry["steps"], cr["boxes"])]
        mss = [m for m in cr["ms"] if m]
        lost, refound = _refind(ious)
        summ[entry["clip"]] = {
            "median_iou": float(np.median(ious)),
            "held_frac": float(np.mean([i >= 0.25 for i in ious])),
            "final_iou": float(ious[-1]),
            "n_lost": lost, "n_refound": refound,
            "median_ms": round(float(np.median(mss)), 1) if mss else None,
            "hz": round(1000.0 / float(np.median(mss)), 3) if mss else None,
            "peak_cuda_mb": max([v for v in cr["cuda_mb"] if v] or [0]),
            "peak_rss_mb": max([v for v in cr["rss_mb"] if v] or [0]),
            "ious": [round(i, 3) for i in ious]}
    return summ


def _overlays(out: Path, plan, per, carry_by_arm, arms, flips):
    """Mid-run overlay for a sample of clips, plus EVERY PASS-flip clip (look-at-it rule)."""
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    want = [e for e in plan[:3]] + [e for e in plan if e["clip"] in flips]
    shown = []
    for entry in want:
        clip = entry["clip"]
        mid = entry["steps"][len(entry["steps"]) // 2]
        base_img = frame(clip, mid["frame"])
        for arm in arms:
            img = base_img.copy()
            cb = carry_by_arm[arm][clip]["boxes"][mid["j"]]
            _draw(img, tuple(mid["gt"]), (0, 200, 0), "GT")
            _draw(img, tuple(cb) if cb else None, (255, 255, 0), f"carry@{arm}")
            p = ovr / f"{clip}_mid_{arm}.jpg"
            cv2.imwrite(str(p), img)
            frac = float((img == img[0, 0]).all(axis=2).mean())
            assert frac < 0.99, f"{p} is {frac:.0%} one colour -- failed render"
        boxes = [tuple(b) for b in carry_by_arm[arms[0]][clip]["boxes"] if b]
        assert len(set(boxes)) > 1, f"{clip}: carried box identical every step -- dead feed"
        shown.append(clip)
    print(f"[score] overlays for {shown} -> {ovr}", flush=True)


def score(out: Path, arms: list[str]) -> None:
    plan = json.loads((out / "plan.json").read_text())
    clips = [e["clip"] for e in plan]
    have = [a for a in arms if (out / f"carry_{a}.json").exists()]
    if have != arms:
        print(f"[score] missing arms {sorted(set(arms) - set(have))} -- scoring the rest",
              flush=True)
    carry_by_arm = {a: json.loads((out / f"carry_{a}.json").read_text()) for a in have}
    per = {a: _per_clip(plan, carry_by_arm[a]) for a in have}

    result = {"n_clips": len(plan), "arms_run": have, "size": SIZE, "prune_after": BASE_P,
              "per_clip": per, "arms": {}, "paired": {}}
    for a in have:
        p = per[a]
        lost = sum(p[c]["n_lost"] for c in clips)
        refound = sum(p[c]["n_refound"] for c in clips)
        result["arms"][a] = {
            "K": ARMS[a][0], "M": ARMS[a][1],
            "median_of_median_iou": round(float(np.median([p[c]["median_iou"] for c in clips])), 3),
            "mean_held_frac": round(float(np.mean([p[c]["held_frac"] for c in clips])), 3),
            "n_pass": int(sum(p[c]["median_iou"] >= 0.25 for c in clips)),
            "refind": [refound, lost],
            "refind_rate": round(refound / lost, 3) if lost else None,
            "refind_ci95": [round(v, 3) for v in gstats.wilson_ci(refound, lost)] if lost else None,
            "median_ms": round(float(np.median([p[c]["median_ms"] for c in clips])), 1),
            "hz": round(float(np.median([p[c]["hz"] for c in clips])), 3),
            "peak_cuda_mb": max(p[c]["peak_cuda_mb"] for c in clips),
            "peak_rss_mb": max(p[c]["peak_rss_mb"] for c in clips)}

    pvals = {}
    for a in have:
        if a == "base":
            continue
        x = [per[a][c]["median_iou"] for c in clips]
        y = [per["base"][c]["median_iou"] for c in clips]
        w = gstats.paired_continuous(x, y)
        pa = {c: per[a][c]["median_iou"] >= 0.25 for c in clips}
        pb = {c: per["base"][c]["median_iou"] >= 0.25 for c in clips}
        b, c_, _ = gstats.discordant_counts(pa, pb)
        ci = w.get("ci95_median_diff")
        result["paired"][a] = {
            "median_delta_vs_base": round(w["median_diff"], 4),
            "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "wilcoxon_p": w["p_value"],
            "noninferior_005": bool(ci and ci[0] > -0.05),
            "mcnemar": {"b_arm_only": b, "c_base_only": c_,
                        "p": gstats.mcnemar(b, c_, "two-sided"),
                        "min_discordant": gstats.min_discordant_for_significance(len(clips))},
        }
        pvals[a] = w["p_value"]
    if pvals:
        result["holm"] = gstats.holm_bonferroni(
            {k: v for k, v in pvals.items() if v == v})   # drop NaN (all-zero-diff arms)

    flips = {c for a in have if a != "base" for c in clips
             if (per[a][c]["median_iou"] >= 0.25) != (per["base"][c]["median_iou"] >= 0.25)}
    _overlays(out, plan, per, carry_by_arm, have, flips)
    result["pass_flip_clips"] = sorted(flips)
    (out / "results.json").write_text(json.dumps(result, indent=1))

    for a in have:
        r = result["arms"][a]
        d = result["paired"].get(a, {})
        print(f"[score] {a:>5} K={r['K']} M={r['M']:>2}: medIoU {r['median_of_median_iou']} "
              f"held {r['mean_held_frac']} pass {r['n_pass']}/{len(clips)} "
              f"refind {r['refind'][0]}/{r['refind'][1]} ms {r['median_ms']} "
              f"cuda {r['peak_cuda_mb']}MB"
              + (f" | d={d['median_delta_vs_base']} CI{d['ci95']} p={d['wilcoxon_p']:.3g}"
                 if d else ""), flush=True)
    print(f"[score] PASS flips vs base: {sorted(flips) or 'none'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stage", "ring", "carry", "score"])
    ap.add_argument("--out", default="runs/exp8")
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    arms = [s for s in a.arms.split(",") if s]
    assert all(s in ARMS for s in arms), f"unknown arm in {arms}; known: {list(ARMS)}"
    {"stage": lambda: stage(out), "ring": lambda: ring(out),
     "carry": lambda: carry(out, arms), "score": lambda: score(out, arms)}[a.mode]()


if __name__ == "__main__":
    main()
