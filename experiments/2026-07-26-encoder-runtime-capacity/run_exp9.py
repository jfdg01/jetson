"""EXP-9 -- encoder runtime (eager bf16 vs TensorRT fp16) x capacity (tiny vs small), ON THE ORIN.

Fork of EXP-8's run_exp8.py: same UAV123 bank, same seed policy, same ssh-stdio bridge, same
stats. The only factor that changes between arms is (model, encoder runtime); image_size is
held at the EXP-1 elbow (640) and K/M/P at the deployed values. NO torch/SAM2 here, NO 3090.

  export  : host-side ONNX export of both encoders @640 + E1's two parity gates
  engines : trtexec --fp16 on the Orin, ONNX -> .plan
  stage   : plan.json (the 38-clip EXP-1/EXP-8 bank) + strata.json (H4 labels, frozen)
  census  : Stage 0 -- peak CUDA / RSS for tiny|small|base_plus, solo and co-resident
  parity  : G1 -- on-device TRT-vs-eager mask parity, must be mean IoU >= 0.99
  carry   : one bridge per arm; per clip re-init + step; carry_<arm>.json
  score   : IoU vs GT, re-find, paired Wilcoxon + McNemar vs base, Holm over the family

    .venv-ft/bin/python run_exp9.py export  --out runs/exp9
    .venv-ft/bin/python run_exp9.py engines --out runs/exp9
    .venv-ft/bin/python run_exp9.py stage   --out runs/exp9
    .venv-ft/bin/python run_exp9.py census  --out runs/exp9
    .venv-ft/bin/python run_exp9.py parity  --out runs/exp9
    .venv-ft/bin/python run_exp9.py carry   --out runs/exp9
    .venv-ft/bin/python run_exp9.py score   --out runs/exp9
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

STRIDE, N_STEPS = 11, 24          # EXP-1/EXP-8 bank, unchanged: ~264 frames ~= 8.8 s
SPAN = N_STEPS * STRIDE
MIN_CLIPS = 25
SIZE = 640                        # EXP-1 elbow, the deployed carry res -- HELD, not swept
BASE_K, BASE_M, BASE_P = 7, 16, 32   # EXP-8's keep-both verdict; P=32 never fires at 24 steps
REFIND_WINDOW = 5

REMOTE = Path("/home/jfdg/sam2-bench")
TINY, SMALL, BPLUS = ("facebook/sam2.1-hiera-tiny", "facebook/sam2.1-hiera-small",
                      "facebook/sam2.1-hiera-base-plus")
PLAN_T, PLAN_S = f"enc{SIZE}.plan", f"enc{SIZE}_small.plan"

BRIDGE = ("cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py"
          " --image-size {size} --num-maskmem {K} --max-obj-ptrs {M} --prune-after {P}"
          " --model {model}{trt}{extra}")

# name -> (model, trt plan filename or ""). base is the deployed config and the shared
# baseline; the 2x2 is fully crossed because small_trt is the only cell that could win both.
ARMS = {"base": (TINY, ""), "trt": (TINY, PLAN_T),
        "small": (SMALL, ""), "small_trt": (SMALL, PLAN_S)}
CENSUS_MODELS = [("tiny", TINY), ("small", SMALL), ("base_plus", BPLUS)]
PARITY_STEPS = 24


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


def _ssh(cmd: str, check: bool = True, timeout: int | None = None):
    p = subprocess.run(["ssh", "-T", "-q", "jetson", cmd], capture_output=True,
                       text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"ssh failed ({p.returncode}): {cmd}\n{p.stderr[-2000:]}")
    return p


# ---- export (host) ------------------------------------------------------------
def _parity_clip():
    """First bank clip whose GT starts at frame 0 -- export_encoder prompts frame_idx=0."""
    for clip in sorted(d.name for d in (DATA / "data_seq" / "UAV123").iterdir() if d.is_dir()):
        try:
            gt = load_gt(clip)
        except Exception:
            continue
        if clip_len(clip) >= 100 and gt and gt[0] is not None:
            return clip, [int(v) for v in gt[0]]
    raise AssertionError("no UAV123 clip with GT on frame 0")


def export(out: Path) -> None:
    """E1's exporter, twice, at 640. Its two asserts (ORT diff <1e-2, mask IoU>=0.99) are
    the gate: a failure here means no engine gets built, not a warning in a log."""
    clip, box = _parity_clip()
    print(f"[export] parity clip {clip} box={box}", flush=True)
    rows = []
    for tag, model, onnx in (("tiny", TINY, f"enc{SIZE}.onnx"),
                             ("small", SMALL, f"enc{SIZE}_small.onnx")):
        dst = out / onnx
        if dst.exists():
            print(f"[export] {onnx} exists -- skip", flush=True)
            rows.append({"tag": tag, "model": model, "onnx": onnx, "status": "cached"})
            continue
        cmd = [sys.executable,
               str(REPO / "experiments" / "2026-07-02-carry-trt-export" / "export_encoder.py"),
               "--image-size", str(SIZE), "--model", model, "--out", str(dst),
               "--clip", str(DATA / "data_seq" / "UAV123" / clip),
               "--box", ",".join(str(v) for v in box),
               # ORT's optimizer miscompiles the deeper hiera-small graph (see the flag's
               # comment in export_encoder.py). Unoptimised for both, so the two exports
               # are gated identically; the real gate is on-device G1, not this.
               "--ort-graph-opt", "disable"]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True)
        (out / f"export_{tag}.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
        print(p.stdout.strip(), flush=True)
        rows.append({"tag": tag, "model": model, "onnx": onnx,
                     "status": "ok" if p.returncode == 0 else "FAIL",
                     "secs": round(time.time() - t0, 1),
                     "mb": round(dst.stat().st_size / 2**20, 1) if dst.exists() else None})
        if p.returncode:
            print(f"[export] {tag} FAILED -- see export_{tag}.log\n{p.stderr[-2000:]}", flush=True)
    (out / "export.json").write_text(json.dumps({"clip": clip, "box": box, "rows": rows}, indent=1))


# ---- engines (Orin) -----------------------------------------------------------
def engines(out: Path) -> None:
    rows = []
    for onnx, plan in ((f"enc{SIZE}.onnx", PLAN_T), (f"enc{SIZE}_small.onnx", PLAN_S)):
        src = out / onnx
        assert src.exists(), f"{src} missing -- run `export` first"
        if _ssh(f"test -f {REMOTE}/{plan}", check=False).returncode == 0:
            print(f"[engines] {plan} exists on the Orin -- skip", flush=True)
            rows.append({"plan": plan, "status": "cached"})
            continue
        print(f"[engines] scp {onnx} ({src.stat().st_size / 2**20:.0f} MB)", flush=True)
        subprocess.run(["scp", "-q", str(src), f"jetson:{REMOTE}/{onnx}"], check=True)
        t0 = time.time()
        p = _ssh(f"cd {REMOTE} && /usr/src/tensorrt/bin/trtexec --onnx={onnx} "
                 f"--saveEngine={plan} --fp16 2>&1 | tail -40", check=False, timeout=3600)
        (out / f"trtexec_{plan}.log").write_text(p.stdout + p.stderr)
        ok = _ssh(f"test -f {REMOTE}/{plan}", check=False).returncode == 0
        rows.append({"plan": plan, "status": "ok" if ok else "FAIL",
                     "build_secs": round(time.time() - t0, 1)})
        print(f"[engines] {plan} {'built' if ok else 'FAILED'} in {rows[-1]['build_secs']}s",
              flush=True)
    (out / "engines.json").write_text(json.dumps(rows, indent=1))


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


# H4 stratum. UAV123 clip families are same-scene, same-class: `car1..car18` are one
# traffic scene, so a car clip has same-class distractors on screen by construction;
# `wakeboard`/`boat` are one subject over water. Derived from the clip name ONLY -- no
# result is consulted -- and frozen to strata.json by `stage`, before any arm runs.
DENSE_PREFIXES = ("car", "truck", "bus", "group", "person", "uav")


def _stratum(clip: str) -> str:
    # UAV123 suffixes a variant sequence with `_s` (car1_s, person1_s) -- same subject class,
    # so it must strip out with the digits or the family lands in the wrong stratum.
    name = "".join(ch for ch in clip if not ch.isdigit()).replace("_s", "").rstrip("_")
    return "distractor_dense" if name in DENSE_PREFIXES else "distractor_free"


def stage(out: Path) -> None:
    plan = _plan(STRIDE, N_STEPS)
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    print(f"[stage] bank: {len(plan)} clips (need >={MIN_CLIPS}): "
          f"{[p['clip'] for p in plan]}", flush=True)
    assert len(plan) >= MIN_CLIPS, f"only {len(plan)} clips < {MIN_CLIPS}"
    strata = {p["clip"]: _stratum(p["clip"]) for p in plan}
    (out / "strata.json").write_text(json.dumps(strata, indent=1))
    n_dense = sum(v == "distractor_dense" for v in strata.values())
    print(f"[stage] H4 strata FROZEN (name-derived, pre-run): dense {n_dense}, "
          f"free {len(strata) - n_dense} -- both under n=25, descriptive only", flush=True)


# ---- census (Stage 0, on the Orin) --------------------------------------------
def _tegra_free() -> dict:
    """Host-visible memory on the Orin. Unified memory + no per-process GPU accounting
    (nvidia-smi returns [N/A] here), so free/available is the only board-level number."""
    p = _ssh("free -m | awk 'NR==2{print $3,$4,$7}'")
    used, free, avail = (int(v) for v in p.stdout.split())
    return {"used_mb": used, "free_mb": free, "available_mb": avail}


def _llama_up() -> bool:
    return _ssh("pgrep -f llama-server >/dev/null", check=False).returncode == 0


def census(out: Path) -> None:
    """Load each model, run a few real steps, record peak CUDA + peak RSS. Three clips, not
    the bank: this sizes the box, it does not measure accuracy."""
    plan = json.loads((out / "plan.json").read_text())[:3]
    co = _llama_up()
    print(f"[census] llama-server {'UP (co-resident)' if co else 'DOWN (solo)'} -- this is the "
          f"deployed condition and is NOT changed by this script", flush=True)
    rows = []
    for tag, model in CENSUS_MODELS:
        before = _tegra_free()
        cmd = BRIDGE.format(size=SIZE, K=BASE_K, M=BASE_M, P=BASE_P, model=model, trt="", extra="")
        log = open(out / f"census_{tag}.err", "wb")
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", cmd], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=log)
        row = {"tag": tag, "model": model, "co_resident": co, "before": before}
        t0 = time.time()
        try:
            peak_c = peak_r = 0.0
            mss = []
            for e in plan:
                _send(proc.stdin, ("init", _rgb_jpg(e["clip"], e["seed"]), e["seed_box"]))
                ack = _recv(proc.stdout)
                assert ack and ack.get("ok"), f"init failed: {ack}"
                for st in e["steps"][:6]:
                    _send(proc.stdin, ("step", _rgb_jpg(e["clip"], st["frame"])))
                    r = _recv(proc.stdout)
                    assert r is not None, "bridge died mid-step"
                    peak_c = max(peak_c, r["cuda_mb"] or 0)
                    peak_r = max(peak_r, r["rss_mb"] or 0)
                    mss.append(r["ms"])
            row.update(status="ok", peak_cuda_mb=round(peak_c, 1), peak_rss_mb=round(peak_r, 1),
                       median_ms=round(float(np.median(mss)), 1),
                       load_and_run_secs=round(time.time() - t0, 1), during=_tegra_free())
        except (AssertionError, BrokenPipeError, OSError) as e:
            proc.kill()
            row.update(status="FAIL", error=str(e)[:300])
            print(f"[census] {tag} FAILED ({e}) -- see census_{tag}.err. This is a RESULT "
                  f"(does not fit), not a bug.", flush=True)
        else:
            proc.stdin.close()
            proc.wait()
        log.close()
        rows.append(row)
        print(f"[census] {tag:>9}: {row.get('status')} cuda={row.get('peak_cuda_mb')}MB "
              f"rss={row.get('peak_rss_mb')}MB ms={row.get('median_ms')} "
              f"avail={row.get('during', {}).get('available_mb')}MB", flush=True)
    (out / "census.json").write_text(json.dumps(rows, indent=1))


# ---- parity (G1, on the Orin) -------------------------------------------------
def parity(out: Path) -> None:
    """G1: eager vs TRT through the SAME bridge and the SAME clips. Compares the carried
    boxes step by step -- an end-to-end mask parity, not a tensor diff, because that is
    what the deployed carry actually consumes."""
    plan = json.loads((out / "plan.json").read_text())[:3]
    rows = []
    for tag, model, pl in (("tiny", TINY, PLAN_T), ("small", SMALL, PLAN_S)):
        got = {}
        for run, trt in (("eager", ""), ("trt", pl)):
            cmd = BRIDGE.format(size=SIZE, K=BASE_K, M=BASE_M, P=BASE_P, model=model,
                                trt=f" --trt-encoder {trt}" if trt else "", extra="")
            log = open(out / f"parity_{tag}_{run}.err", "wb")
            proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", cmd], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=log)
            boxes = []
            try:
                for e in plan:
                    _send(proc.stdin, ("init", _rgb_jpg(e["clip"], e["seed"]), e["seed_box"]))
                    assert (_recv(proc.stdout) or {}).get("ok"), "init failed"
                    for st in e["steps"][:PARITY_STEPS]:
                        _send(proc.stdin, ("step", _rgb_jpg(e["clip"], st["frame"])))
                        r = _recv(proc.stdout)
                        assert r is not None, "bridge died"
                        boxes.append(r["box"])
                proc.stdin.close()
                proc.wait()
            except (AssertionError, BrokenPipeError, OSError) as ex:
                proc.kill()
                print(f"[parity] {tag}/{run} DIED ({ex}) -- see parity_{tag}_{run}.err",
                      flush=True)
                boxes = None
            log.close()
            got[run] = boxes
        if not got["eager"] or not got["trt"]:
            rows.append({"tag": tag, "plan": pl, "status": "FAIL", "gate": False})
        else:
            ious = [1.0 if a is None and b is None else
                    (iou(tuple(a), tuple(b)) if a and b else 0.0)
                    for a, b in zip(got["eager"], got["trt"])]
            m = float(np.mean(ious))
            rows.append({"tag": tag, "plan": pl, "status": "ok", "n_steps": len(ious),
                         "mean_iou": round(m, 4), "min_iou": round(float(min(ious)), 4),
                         "gate": bool(m >= 0.99)})
        print(f"[parity] {tag}: {rows[-1]}", flush=True)
    (out / "parity.json").write_text(json.dumps(rows, indent=1))
    bad = [r["tag"] for r in rows if not r["gate"]]
    print(f"[parity] G1 {'PASS' if not bad else 'FAIL for ' + str(bad)} "
          f"-- a failing engine's arms are INVALID, not a rate win", flush=True)


# ---- carry (on the Orin, one bridge per arm) ----------------------------------
def _run_arm(plan, out: Path, tag: str, model: str, trt: str) -> bool:
    """Stream every clip through one bridge process. Returns False if the arm died."""
    dst = out / f"carry_{tag}.json"
    if dst.exists():
        print(f"[carry] {tag} already done -- skip", flush=True)
        return True
    cmd = BRIDGE.format(size=SIZE, K=BASE_K, M=BASE_M, P=BASE_P, model=model,
                        trt=f" --trt-encoder {trt}" if trt else "", extra="")
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
            rec = {"boxes": [], "ms": [], "cuda_mb": [], "rss_mb": []}
            for st in entry["steps"]:
                _send(proc.stdin, ("step", _rgb_jpg(entry["clip"], st["frame"])))
                r = _recv(proc.stdout)
                assert r is not None, f"bridge died {entry['clip']} arm={tag} step={st['j']}"
                rec["boxes"].append(r["box"])
                rec["ms"].append(r["ms"])
                rec["cuda_mb"].append(r.get("cuda_mb"))
                rec["rss_mb"].append(r.get("rss_mb"))
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


def carry(out: Path, arms: list[str], g1_override: str = "") -> None:
    plan = json.loads((out / "plan.json").read_text())
    gate = {r["tag"]: r["gate"] for r in
            json.loads((out / "parity.json").read_text())} if (out / "parity.json").exists() else {}
    for name in arms:
        model, trt = ARMS[name]
        if trt and gate and not gate.get("small" if model == SMALL else "tiny", True):
            # G1 as pre-registered compares two 24-step RECURSIVE carries, so it scores
            # trajectory agreement, not engine fidelity: one differing pixel at step t is
            # fed back as step t+1's memory. diag_g1.py supplies the control the
            # pre-registration lacked -- eager-vs-eager is exactly 1.0000 on both models
            # (the carry is deterministic, so the instrument is sound), while eager-vs-TRT
            # is 1.0000 / 0.9949 at STEP 1, before any state exists. The engines are
            # faithful; the carry amplifies. Overriding requires a written reason that
            # lands in carry_override.json, and it does NOT touch G2 -- adoption still has
            # to clear non-inferiority against GROUND TRUTH, which is the question that
            # matters and the one G1 never asked.
            if not g1_override:
                print(f"[carry] {name} SKIPPED -- its engine failed G1 parity", flush=True)
                continue
            (out / "carry_override.json").write_text(json.dumps(
                {"arm": name, "reason": g1_override, "g1": gate}, indent=1))
            print(f"[carry] {name} RUN UNDER G1 OVERRIDE: {g1_override}", flush=True)
        _run_arm(plan, out, name, model, trt)


# ---- score --------------------------------------------------------------------
def _draw(img, box, color, label):
    if box is None:
        return
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(img, (x0, y0), (x1, y1), color, 2)
    cv2.putText(img, label, (x0, max(12, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def _refind(ious: list[float], thr: float = 0.25, w: int = REFIND_WINDOW):
    """(n_lost, n_refound): a lost step counts as refound if IoU>=thr within the next w steps."""
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


def _overlays(out: Path, plan, carry_by_arm, arms, flips):
    """Mid-run overlay for a sample of clips, plus EVERY PASS-flip clip (look-at-it rule)."""
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    want = list(plan[:3]) + [e for e in plan if e["clip"] in flips]
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
    strata = json.loads((out / "strata.json").read_text())
    have = [a for a in arms if (out / f"carry_{a}.json").exists()]
    if have != arms:
        print(f"[score] missing arms {sorted(set(arms) - set(have))} -- scoring the rest",
              flush=True)
    assert "base" in have, "no base arm -- nothing to pair against"
    carry_by_arm = {a: json.loads((out / f"carry_{a}.json").read_text()) for a in have}
    per = {a: _per_clip(plan, carry_by_arm[a]) for a in have}

    result = {"n_clips": len(plan), "arms_run": have, "size": SIZE, "K": BASE_K, "M": BASE_M,
              "prune_after": BASE_P, "per_clip": per, "arms": {}, "paired": {}}
    for a in have:
        p = per[a]
        lost = sum(p[c]["n_lost"] for c in clips)
        refound = sum(p[c]["n_refound"] for c in clips)
        result["arms"][a] = {
            "model": ARMS[a][0], "encoder": "trt_fp16" if ARMS[a][1] else "eager_bf16",
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
    base_ms = result["arms"]["base"]["median_ms"]
    for a in have:
        result["arms"][a]["speedup_vs_base"] = round(base_ms / result["arms"][a]["median_ms"], 3)

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

    # G2/G3, evaluated mechanically from the pre-registered thresholds.
    gates = {}
    for a in have:
        if a == "base":
            continue
        r, d = result["arms"][a], result["paired"][a]
        noninf = d["noninferior_005"] and r["n_pass"] >= result["arms"]["base"]["n_pass"] - 1
        gates[a] = {"speedup": r["speedup_vs_base"], "noninferior": bool(noninf),
                    "G2_rate_ge_1.15_and_noninferior": bool(r["speedup_vs_base"] >= 1.15 and noninf),
                    "G3_wins_accuracy": bool(d["mcnemar"]["c_base_only"]
                                             > d["mcnemar"]["b_arm_only"]
                                             and result.get("holm", {}).get(a, {}).get("reject"))}
    result["gates"] = gates

    # H4: pre-frozen stratum, descriptive only (both strata are under n=25 -- I4).
    h4 = {}
    for s in sorted(set(strata.values())):
        cs = [c for c in clips if strata[c] == s]
        h4[s] = {"n": len(cs), "clips": cs, "inferential": False,
                 **{a: {"n_pass": int(sum(per[a][c]["median_iou"] >= 0.25 for c in cs)),
                        "median_iou": round(float(np.median([per[a][c]["median_iou"]
                                                             for c in cs])), 3)} for a in have}}
    result["h4_strata"] = h4

    flips = {c for a in have if a != "base" for c in clips
             if (per[a][c]["median_iou"] >= 0.25) != (per["base"][c]["median_iou"] >= 0.25)}
    _overlays(out, plan, carry_by_arm, have, flips)
    result["pass_flip_clips"] = sorted(flips)
    (out / "results.json").write_text(json.dumps(result, indent=1))

    for a in have:
        r = result["arms"][a]
        d = result["paired"].get(a, {})
        print(f"[score] {a:>9} {r['encoder']:>9}: medIoU {r['median_of_median_iou']} "
              f"held {r['mean_held_frac']} pass {r['n_pass']}/{len(clips)} "
              f"refind {r['refind'][0]}/{r['refind'][1]} ms {r['median_ms']} "
              f"({r['speedup_vs_base']}x) cuda {r['peak_cuda_mb']}MB rss {r['peak_rss_mb']}MB"
              + (f" | d={d['median_delta_vs_base']} CI{d['ci95']} p={d['wilcoxon_p']:.3g}"
                 f" b/c={d['mcnemar']['b_arm_only']}/{d['mcnemar']['c_base_only']}"
                 if d else ""), flush=True)
    for a, g in gates.items():
        print(f"[score] gate {a:>9}: G2={g['G2_rate_ge_1.15_and_noninferior']} "
              f"G3={g['G3_wins_accuracy']}", flush=True)
    for s, v in h4.items():
        print(f"[score] H4 {s:>17} n={v['n']} (descriptive): "
              + " ".join(f"{a}={v[a]['n_pass']}/{v['n']}" for a in have), flush=True)
    print(f"[score] PASS flips vs base: {sorted(flips) or 'none'}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["export", "engines", "stage", "census", "parity",
                                     "carry", "score"])
    ap.add_argument("--out", default="runs/exp9")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--g1-override", default="",
                    help="run a TRT arm whose engine failed G1, recording this string as the "
                         "reason in carry_override.json. G2 is unaffected.")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    arms = [s for s in a.arms.split(",") if s]
    assert all(s in ARMS for s in arms), f"unknown arm in {arms}; known: {list(ARMS)}"
    {"export": lambda: export(out), "engines": lambda: engines(out),
     "stage": lambda: stage(out), "census": lambda: census(out),
     "parity": lambda: parity(out), "carry": lambda: carry(out, arms, a.g1_override),
     "score": lambda: score(out, arms)}[a.mode]()


if __name__ == "__main__":
    main()
