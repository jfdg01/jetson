"""EXP-2 carry-res robustness: does the NL-vs-PT select verdict move when the SAM2 tracker
runs at a different image_size? The acquire boxes are FIXED (runs/exp2/acquire.json); only the
carry image_size changes, so this isolates the tracker-resolution knob on the SELECT task.
(The full carry-res elbow lives in EXP-1 on 38 clips; here the question is verdict robustness.)

Reuses the primary 1024 carry (runs/exp2/carry.json). Runs new sizes on the Orin via the ssh
bridge, re-scores PASS per leg with select_exp2._score_cell, and reports NL/PT pass + discordants
per carry-res. machine=jetson. Run AFTER the other on-device sweeps free the GPU.

    .venv-ft/bin/python carry_res_sweep.py --matrix .../scenes_p518.json --out runs/exp2 --sizes 512,768
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
N25 = REPO / "experiments" / "2026-07-20-n25-select"
for _p in (HERE, N25, REPO, REPO / "grounding"):
    sys.path.insert(0, str(_p))

from curate_p518 import clip_len, frame, load_gt          # noqa: E402
from select_exp2 import (COVER_FRAMES, LEGS, STRIDE, _gating, _key,  # noqa: E402
                         _recv, _rgb_jpg_arr, _score_cell, _send)
import stats as gstats                                     # noqa: E402

BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"


def carry_at(out: Path, size: int) -> dict:
    """carry_{size}.json for size!=1024; the 1024 arm reuses the primary carry.json."""
    if size == 1024 and (out / "carry.json").exists():
        return json.loads((out / "carry.json").read_text())
    cf = out / f"carry_{size}.json"
    if cf.exists():
        print(f"[csweep] size={size} reuse {cf.name}", flush=True)
        return json.loads(cf.read_text())
    acq = json.loads((out / "acquire.json").read_text())
    cells = [(k, v) for k, v in acq.items() if v.get("box") is not None]
    log = open(out / f"bridge_{size}.err", "wb")
    proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE.format(size=size)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
    res = {}
    t0 = time.time()
    for i, (k, v) in enumerate(cells):
        clip, cmd = v["clip"], v["cmd"]
        n = clip_len(clip)
        steps = [cmd + s * STRIDE for s in range(1, COVER_FRAMES // STRIDE + 1) if cmd + s * STRIDE < n]
        _send(proc.stdin, ("init", _rgb_jpg_arr(frame(clip, cmd)), [int(x) for x in v["box"]]))
        ack = _recv(proc.stdout)
        assert ack and ack.get("ok"), f"init failed {k} size={size}: {ack}"
        boxes, mss = [], []
        for fi in steps:
            _send(proc.stdin, ("step", _rgb_jpg_arr(frame(clip, fi))))
            r = _recv(proc.stdout)
            assert r is not None, f"bridge died {k} size={size} frame {fi}"
            boxes.append(r["box"]); mss.append(r["ms"])
        res[k] = {"steps": steps, "boxes": boxes, "ms": mss}
        if (i + 1) % 20 == 0:
            print(f"[csweep] size={size} [{i + 1}/{len(cells)}]", flush=True)
    proc.stdin.close(); proc.wait(); log.close()
    cf.write_text(json.dumps(res, indent=1))
    print(f"[csweep] size={size} {len(res)} cells in {time.time() - t0:.0f}s -> {cf.name}", flush=True)
    return res


def score_size(acq, carry_res, scenes) -> dict:
    per = {}
    for k, v in acq.items():
        s = scenes.get((v["clip"], v["f0"]))
        if s is None or v.get("box") is None:
            continue
        gt = load_gt(v["clip"])
        m, _ = _score_cell(v, carry_res.get(k), gt, s)
        per[k] = m
    out = {"legs": {}}
    hz = [1000.0 / np.median([m for m in c["ms"] if m]) for c in carry_res.values()
          if c.get("ms") and any(c["ms"])]
    out["ondevice_hz_median"] = round(float(np.median(hz)), 3) if hz else None
    for leg in LEGS:
        nl = {f"{s['clip']}_{s['f0']}": int(per.get(_key('NL', leg, s), {}).get("pass", False))
              for s in scenes.values()}
        pt = {f"{s['clip']}_{s['f0']}": int(per.get(_key('PT', leg, s), {}).get("pass", False))
              for s in scenes.values()}
        b, c, n = gstats.discordant_counts(nl, pt)
        out["legs"][leg] = {"nl_pass": sum(nl.values()), "pt_pass": sum(pt.values()),
                            "n": n, "b_nl_only": b, "c_pt_only": c,
                            "p": gstats.mcnemar(b, c, "two-sided")}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", default=str(REPO / "experiments" / "2026-07-20-n25-select" / "scenes_p518.json"))
    ap.add_argument("--out", default="runs/exp2")
    ap.add_argument("--sizes", default="512,768")   # 1024 reused from carry.json
    a = ap.parse_args()
    out = Path(a.out)
    sizes = sorted(set(int(s) for s in a.sizes.split(",")) | {1024})
    scenes = {(s["clip"], s["f0"]): s for s in _gating(a.matrix)}
    acq = json.loads((out / "acquire.json").read_text())
    report = {"sizes": sizes, "by_size": {}}
    for size in sizes:
        cr = carry_at(out, size)
        report["by_size"][size] = score_size(acq, cr, scenes)
    (out / "carry_res_sweep.json").write_text(json.dumps(report, indent=2))
    print("\n[csweep] SELECT PASS vs carry image_size (acquire boxes fixed):")
    for size in sizes:
        r = report["by_size"][size]
        w, s2 = r["legs"]["WSEL"], r["legs"]["SWAP"]
        print(f"  size={size:4d} Hz~{r['ondevice_hz_median']}  "
              f"WSEL NL {w['nl_pass']}/{w['n']} PT {w['pt_pass']}/{w['n']} (b{w['b_nl_only']}/c{w['c_pt_only']})  "
              f"SWAP NL {s2['nl_pass']}/{s2['n']} PT {s2['pt_pass']}/{s2['n']} (b{s2['b_nl_only']}/c{s2['c_pt_only']})",
              flush=True)
    print(f"[csweep] -> {out / 'carry_res_sweep.json'}", flush=True)


if __name__ == "__main__":
    main()
