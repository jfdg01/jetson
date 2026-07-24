"""EXP-1 -- resolution-decoupled carry: SAM2 track-res 768 vs 1024, ON THE ORIN.

Seed box is fixed (GT at the seed frame); the only factor that changes is SAM2's internal
image_size. Carry runs on the Jetson via the ssh-stdio bridge (carry_ssh_bridge.py --image-size N);
this host script holds UAV123 + GT, streams RGB JPEGs over ssh, scores IoU vs GT. NO torch/SAM2
here, NO 3090. machine=jetson.

  stage : pick >=25 UAV123 clips with a contiguous GT window; write plan.json (clip/seed/steps/gt).
  carry : for each size, spawn one ssh bridge; per clip re-init + step; write carry_<size>.json.
  score : IoU vs GT per step; per-clip median/held/hz; paired McNemar + bootstrap CI; overlays.

    .venv-ft/bin/python run_exp1.py stage --out runs/exp1
    .venv-ft/bin/python run_exp1.py carry --out runs/exp1 --sizes 768,1024
    .venv-ft/bin/python run_exp1.py score --out runs/exp1
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

STRIDE = 11               # 2.69 Hz carry over 30 fps (R-16; matches P5.21 / showcase cadence)
N_STEPS = 24             # ~264-frame window ~= 8.8 s
SPAN = N_STEPS * STRIDE
MIN_CLIPS = 25
BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"


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
    hdr = f.read(4)
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
    """UAV123 frame (BGR on disk) -> RGB JPEG (the bridge feeds bytes straight to StreamCarry,
    which expects RGB via PIL.fromarray -- NO swap on the device side, so we swap here)."""
    rgb = cv2.cvtColor(frame(clip, idx), cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


# ---- stage --------------------------------------------------------------------
def _first_contiguous_seed(gt: list, span: int):
    """First 0-based seed s with gt[s..s+span] all present. None if no such window."""
    run = 0
    for i, g in enumerate(gt):
        run = run + 1 if g is not None else 0
        if run >= span + 1:
            return i - span
    return None


def stage(out: Path) -> None:
    clips = sorted(d.name for d in (DATA / "data_seq" / "UAV123").iterdir() if d.is_dir())
    plan = []
    for clip in clips:
        try:
            gt = load_gt(clip)
        except Exception:
            continue
        if clip_len(clip) < SPAN + 1:
            continue
        seed = _first_contiguous_seed(gt, SPAN)
        if seed is None:
            continue
        steps = [{"j": k, "frame": seed + (k + 1) * STRIDE,
                  "gt": list(gt[seed + (k + 1) * STRIDE])} for k in range(N_STEPS)]
        plan.append({"clip": clip, "seed": seed, "seed_box": [int(v) for v in gt[seed]],
                     "steps": steps})
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(f"[stage] {len(plan)} clips with a contiguous {SPAN + 1}-frame GT window "
          f"(need >={MIN_CLIPS}): {[p['clip'] for p in plan]}", flush=True)
    if len(plan) < MIN_CLIPS:
        print(f"[stage] WARNING only {len(plan)} < {MIN_CLIPS}; consider smaller N_STEPS/STRIDE",
              flush=True)


# ---- carry (on the Orin, one bridge per size) ---------------------------------
def carry(out: Path, sizes: list[int]) -> None:
    plan = json.loads((out / "plan.json").read_text())
    for size in sizes:
        if (out / f"carry_{size}.json").exists():
            print(f"[carry] size={size} already done -- skip (reusing carry_{size}.json)", flush=True)
            continue
        log = open(out / f"bridge_{size}.err", "wb")
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE.format(size=size)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        res = {}
        t_all = time.time()
        # ponytail: one bad image_size (SAM2 window/pos-embed mismatch) must not abort the
        # whole sweep -- catch it, record the size as unsupported, move to the next.
        try:
            for pi, entry in enumerate(plan):
                clip, seed = entry["clip"], entry["seed"]
                _send(proc.stdin, ("init", _rgb_jpg(clip, seed), entry["seed_box"]))
                ack = _recv(proc.stdout)
                assert ack and ack.get("ok"), f"init failed clip={clip} size={size}: {ack}"
                boxes, mss = [], []
                for st in entry["steps"]:
                    _send(proc.stdin, ("step", _rgb_jpg(clip, st["frame"])))
                    r = _recv(proc.stdout)
                    assert r is not None, f"bridge died clip={clip} size={size} step={st['j']}"
                    boxes.append(r["box"])
                    mss.append(r["ms"])
                res[clip] = {"boxes": boxes, "ms": mss}
                print(f"[carry] size={size} [{pi + 1}/{len(plan)}] {clip} "
                      f"median_ms={np.median([m for m in mss if m]):.0f}", flush=True)
        except (AssertionError, BrokenPipeError, OSError) as e:
            proc.kill()
            log.close()
            print(f"[carry] size={size} UNSUPPORTED / died ({e}); see bridge_{size}.err -- skipping",
                  flush=True)
            continue
        proc.stdin.close()
        proc.wait()
        log.close()
        (out / f"carry_{size}.json").write_text(json.dumps(res, indent=1))
        print(f"[carry] size={size} done {len(res)} clips in {time.time() - t_all:.0f}s "
              f"-> carry_{size}.json", flush=True)


# ---- score --------------------------------------------------------------------
def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(12, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def _per_clip(plan, carry_res):
    """clip -> {median_iou, held_frac, final_iou, hz, ious}."""
    summ = {}
    for entry in plan:
        clip = entry["clip"]
        cr = carry_res[clip]
        ious = []
        for st, cb in zip(entry["steps"], cr["boxes"]):
            ious.append(iou(tuple(cb) if cb else None, tuple(st["gt"])))
        mss = [m for m in cr["ms"] if m]
        summ[clip] = {"median_iou": float(np.median(ious)),
                      "held_frac": float(np.mean([i >= 0.25 for i in ious])),
                      "final_iou": float(ious[-1]),
                      "hz": round(1000.0 / float(np.median(mss)), 3) if mss else None,
                      "median_ms": round(float(np.median(mss)), 1) if mss else None,
                      "ious": [round(i, 3) for i in ious]}
    return summ


def _overlays(out: Path, plan, carry_by_size, sizes, n=3):
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    for entry in plan[:n]:
        clip = entry["clip"]
        mid = entry["steps"][len(entry["steps"]) // 2]
        img_base = frame(clip, mid["frame"])
        for size in sizes:
            img = img_base.copy()
            cb = carry_by_size[size][clip]["boxes"][mid["j"]]
            _draw(img, tuple(mid["gt"]), (0, 200, 0), "GT")
            _draw(img, tuple(cb) if cb else None, (255, 255, 0), f"carry@{size}")
            p = ovr / f"{clip}_mid_{size}.jpg"
            cv2.imwrite(str(p), img)
            frac = float((img == img[0, 0]).all(axis=2).mean())
            assert frac < 0.99, f"{p} is {frac:.0%} one colour -- failed render"
    print(f"[score] wrote overlays for {[e['clip'] for e in plan[:n]]} -> {ovr}", flush=True)


def _bootstrap_ci(deltas, iters=5000):
    rng = np.random.default_rng(0)
    a = np.asarray(deltas)
    meds = [float(np.median(rng.choice(a, size=len(a), replace=True))) for _ in range(iters)]
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def score(out: Path, sizes: list[int]) -> None:
    plan = json.loads((out / "plan.json").read_text())
    have = [s for s in sizes if (out / f"carry_{s}.json").exists()]
    if have != sizes:
        print(f"[score] carry files present for {have}; missing {sorted(set(sizes) - set(have))} "
              f"(unsupported image_size?) -- scoring the rest", flush=True)
    sizes = have
    carry_by_size = {s: json.loads((out / f"carry_{s}.json").read_text()) for s in sizes}
    per = {s: _per_clip(plan, carry_by_size[s]) for s in sizes}
    _overlays(out, plan, carry_by_size, sizes)

    result = {"n_clips": len(plan), "sizes": sizes, "per_clip": per, "arms": {}}
    for s in sizes:
        mi = [per[s][c]["median_iou"] for c in per[s]]
        hz = [per[s][c]["hz"] for c in per[s] if per[s][c]["hz"]]
        result["arms"][s] = {"median_of_median_iou": round(float(np.median(mi)), 3),
                             "mean_held_frac": round(float(np.mean(
                                 [per[s][c]["held_frac"] for c in per[s]])), 3),
                             "n_pass": int(sum(per[s][c]["median_iou"] >= 0.25 for c in per[s])),
                             "ondevice_hz_median": round(float(np.median(hz)), 3) if hz else None}

    # paired: 768 (low) vs 1024 (high) if both present
    if 768 in sizes and 1024 in sizes:
        clips = [e["clip"] for e in plan]
        deltas = [per[768][c]["median_iou"] - per[1024][c]["median_iou"] for c in clips]
        ci = _bootstrap_ci(deltas)
        pass768 = {c: per[768][c]["median_iou"] >= 0.25 for c in clips}
        pass1024 = {c: per[1024][c]["median_iou"] >= 0.25 for c in clips}
        b, c, _ = gstats.discordant_counts(pass768, pass1024)  # b=768-only-pass, c=1024-only-pass
        mc = gstats.mcnemar(b, c, "two-sided")
        result["paired"] = {
            "median_delta_768_minus_1024": round(float(np.median(deltas)), 4),
            "delta_ci95": [round(ci[0], 4), round(ci[1], 4)],
            "noninferior_005": ci[0] > -0.05,   # 768 loses < 0.05 median IoU at the 95% floor
            "mcnemar_pass": {"b_768only": b, "c_1024only": c, "p": mc,
                             "min_discordant": gstats.min_discordant_for_significance(len(clips))},
        }
    (out / "results.json").write_text(json.dumps(result, indent=1))
    for s in sizes:
        a = result["arms"][s]
        print(f"[score] size={s}: median-IoU {a['median_of_median_iou']} "
              f"held {a['mean_held_frac']} pass {a['n_pass']}/{len(plan)} "
              f"hz {a['ondevice_hz_median']}", flush=True)
    if "paired" in result:
        p = result["paired"]
        print(f"[score] 768-1024 median delta {p['median_delta_768_minus_1024']} "
              f"CI{p['delta_ci95']} noninferior(<0.05)={p['noninferior_005']} "
              f"McNemar b={p['mcnemar_pass']['b_768only']} c={p['mcnemar_pass']['c_1024only']} "
              f"p={p['mcnemar_pass']['p']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stage", "carry", "score"])
    ap.add_argument("--out", default="runs/exp1")
    ap.add_argument("--sizes", default="768,1024")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sizes = [int(s) for s in a.sizes.split(",")]
    if a.mode == "stage":
        stage(out)
    elif a.mode == "carry":
        carry(out, sizes)
    else:
        score(out, sizes)


if __name__ == "__main__":
    main()
