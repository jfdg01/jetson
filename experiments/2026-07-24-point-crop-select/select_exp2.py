"""EXP-2 -- point-and-crop select vs NL referring expression, ON THE ORIN.

The user's question is about ACQUISITION: does an operator pointer (point -> crop -> VLM ground
in crop -> box) beat a natural-language referring expression (VLM ground the phrase on the whole
frame)? The carry + delivery AFTER acquisition are identical in both arms, so this drops the
P5.16/P5.18 two-candidate idle-discovery apparatus (which existed to carry two tracks and is why
that harness ran SAM2 on the 3090) and compares the two acquisition methods on a SINGLE carry,
delivered directly at the command frame. Both the VLM (JetsonBackend q8_0) and SAM2 carry run on
the Jetson; NO 3090. machine=jetson.

Arms (differ ONLY in how the command-frame box is obtained):
  NL : vlm_acquire(whole frame, phrase)                       -- the referring-expression baseline
  PT : roi_reanchor(frame, box-around-operator-point, phrase) -- crop 256px around the point, ground

Legs:
  WSEL : intended = target;    phrase = target_caption;     point = center of target GT at cmd.
  SWAP : intended = distractor; phrase = distractor_caption; point = center of distractor_gt_prompt.
SWAP is the real test (two same-class objects -> NL must ground the right one on the whole frame;
PT crops around the point so only the intended object is in view). WSEL is a grounding+carry control.

Three passes (VLM and SAM2 decoupled -- avoids co-residency OOM, R-16; the claim is accuracy not Hz):
  acquire : boot the Jetson VLM once, get the command-frame box for every cell x leg x arm.
  carry   : ssh-bridge SAM2 on the Orin (image_size 1024), seed each box, step the coverage window.
  score   : deliver_iou / coverage / PASS per cell; paired McNemar NL vs PT per leg, deflated to clips.

    .venv-ft/bin/python select_exp2.py acquire --matrix .../scenes_p518.json --out runs/exp2
    .venv-ft/bin/python select_exp2.py carry   --out runs/exp2
    .venv-ft/bin/python select_exp2.py score   --matrix .../scenes_p518.json --out runs/exp2
    .venv-ft/bin/python select_exp2.py --selfcheck
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
N25 = REPO / "experiments" / "2026-07-20-n25-select"
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
for p in (HERE, N25, P55, E24, E18, REPO, REPO / "grounding"):
    sys.path.insert(0, str(p))

from curate_p518 import clip_len, frame, load_gt          # noqa: E402
from replay_e24 import MAX_SIDE, _valid, vlm_acquire      # noqa: E402
from replay_source import iou                             # noqa: E402
from select_p55 import roi_reanchor                       # noqa: E402
import stats as gstats                                    # noqa: E402

FPS = 30.0
COVER_S = 10.0
STRIDE = 11                    # 2.69 Hz carry on the Orin (R-16)
COVER_FRAMES = round(COVER_S * FPS)
ARMS = ("NL", "PT")
LEGS = ("WSEL", "SWAP")
BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size 1024"


def _center_box(g):
    """Degenerate 2px pixel box centered on the box's center -- the operator point.
    roi_reanchor's min_side=256 floor turns this into a 256px crop around the point."""
    cx, cy = (g[0] + g[2]) / 2.0, (g[1] + g[3]) / 2.0
    return (cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)


def _key(arm, leg, scene):
    return f"{arm}_{leg}_{scene['clip']}_{scene['f0']}"


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


def _rgb_jpg_arr(bgr) -> bytes:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    ok, buf = cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return buf.tobytes()


def _gating(matrix):
    d = json.loads(Path(matrix).read_text())
    scenes = d["scenes"] if isinstance(d, dict) else d
    return [s for s in scenes if s.get("gating", True)]


# ---- acquire (VLM on the Orin) ------------------------------------------------
def acquire(out: Path, matrix: str) -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    scenes = _gating(matrix)
    print(f"[acquire] booting Jetson q8_0 for {len(scenes)} scenes x {len(LEGS)} legs "
          f"x {len(ARMS)} arms...", flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_img(img_bgr, caption):
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/exp2_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img_bgr)
        try:
            return vlm_acquire(be, path, caption, w, h)
        finally:
            Path(path).unlink(missing_ok=True)

    res = {}
    try:
        for scene in scenes:
            clip, f0 = scene["clip"], scene["f0"]
            cmd = f0 + round(scene["t_p"] * FPS)
            gt = load_gt(clip)
            frame_cmd = frame(clip, cmd)
            for leg in LEGS:
                if leg == "WSEL":
                    intended = gt[cmd] if cmd < len(gt) else None
                    phrase = scene["target_caption"]
                else:
                    intended = scene.get("distractor_gt_prompt")
                    phrase = scene["distractor_caption"]
                for arm in ARMS:
                    k = _key(arm, leg, scene)
                    if intended is None:
                        res[k] = {"box": None, "reason": "no-gt-at-cmd", "cmd": cmd,
                                  "leg": leg, "arm": arm, "clip": clip, "f0": f0}
                        continue
                    if arm == "NL":
                        box = submit_img(frame_cmd, phrase)
                    else:
                        box, dbg = roi_reanchor(frame_cmd, _center_box(intended),
                                                phrase, submit_img)
                    ok = _valid(box, frame_cmd.shape)
                    res[k] = {"box": [round(v, 1) for v in box] if ok else None,
                              "cmd": cmd, "phrase": phrase, "leg": leg, "arm": arm,
                              "clip": clip, "f0": f0,
                              "point": None if arm == "NL"
                              else [round((intended[0] + intended[2]) / 2, 1),
                                    round((intended[1] + intended[3]) / 2, 1)],
                              "reason": None if ok else "acquire-failed"}
                    print(f"[acquire] {k} box={res[k]['box']} reason={res[k]['reason']}",
                          flush=True)
    finally:
        be.close()
    (out / "acquire.json").write_text(json.dumps(res, indent=1))
    n_ok = sum(v["box"] is not None for v in res.values())
    print(f"[acquire] {n_ok}/{len(res)} boxes acquired -> acquire.json", flush=True)


# ---- carry (SAM2 on the Orin, single target per cell) -------------------------
def carry(out: Path) -> None:
    acq = json.loads((out / "acquire.json").read_text())
    cells = [(k, v) for k, v in acq.items() if v.get("box") is not None]
    log = open(out / "bridge.err", "wb")
    proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
    res = {}
    t0 = time.time()
    for i, (k, v) in enumerate(cells):
        clip, cmd = v["clip"], v["cmd"]
        n = clip_len(clip)
        steps = [cmd + s * STRIDE for s in range(1, COVER_FRAMES // STRIDE + 1)
                 if cmd + s * STRIDE < n]
        _send(proc.stdin, ("init", _rgb_jpg_arr(frame(clip, cmd)),
                           [int(x) for x in v["box"]]))
        ack = _recv(proc.stdout)
        assert ack and ack.get("ok"), f"init failed {k}: {ack}"
        boxes, mss = [], []
        for fi in steps:
            _send(proc.stdin, ("step", _rgb_jpg_arr(frame(clip, fi))))
            r = _recv(proc.stdout)
            assert r is not None, f"bridge died {k} frame {fi}"
            boxes.append(r["box"])
            mss.append(r["ms"])
        res[k] = {"steps": steps, "boxes": boxes, "ms": mss}
        print(f"[carry] [{i + 1}/{len(cells)}] {k} steps={len(steps)} "
              f"median_ms={np.median([m for m in mss if m]):.0f}", flush=True)
    proc.stdin.close()
    proc.wait()
    log.close()
    (out / "carry.json").write_text(json.dumps(res, indent=1))
    print(f"[carry] {len(res)} cells in {time.time() - t0:.0f}s -> carry.json", flush=True)


# ---- score --------------------------------------------------------------------
def _score_cell(v, carry_cell, gt, scene):
    """Returns the per-cell metric dict + PASS bool for the cell's leg/arm."""
    leg = v["leg"]
    cmd = v["cmd"]
    box = tuple(v["box"])
    tgt = gt[cmd] if cmd < len(gt) and gt[cmd] is not None else None
    dg = scene.get("distractor_gt_prompt")
    deliver_iou = iou(box, tuple(tgt)) if tgt else 0.0
    deliver_iou_d = iou(box, tuple(dg)) if dg else 0.0
    # coverage vs the TARGET GT track over the window (WSEL only gate)
    held = tot = 0
    if carry_cell:
        for fi, cb in zip(carry_cell["steps"], carry_cell["boxes"]):
            g = gt[fi] if fi < len(gt) else None
            if g is None:
                continue
            tot += 1
            if cb and iou(tuple(cb), tuple(g)) >= 0.25:
                held += 1
    coverage = held / tot if tot else 0.0
    if leg == "WSEL":
        genuine = deliver_iou >= 0.25
        passed = genuine and coverage >= 0.5
    else:  # SWAP: delivered the distractor, suppressed the target
        genuine = deliver_iou_d >= 0.25
        passed = deliver_iou < 0.25 and deliver_iou_d >= 0.25
    return {"leg": leg, "arm": v["arm"], "deliver_iou": round(deliver_iou, 4),
            "deliver_iou_distractor": round(deliver_iou_d, 4),
            "coverage": round(coverage, 3), "genuine_lock": genuine,
            "pass": passed, "reason": None}, passed


def _overlay(out: Path, k, v, carry_cell, gt, scene):
    """deliver frame: acquired box (green) vs target GT (red) vs distractor GT (blue)."""
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    cmd = v["cmd"]
    img = frame(scene["clip"], cmd).copy()
    frac = float((img == img[0, 0]).all(axis=2).mean())
    assert frac < 0.99, f"{k} deliver frame {frac:.0%} one colour -- failed render"
    tgt = gt[cmd] if cmd < len(gt) and gt[cmd] is not None else None
    dg = scene.get("distractor_gt_prompt")
    for g, col in ((tgt, (0, 0, 220)), (dg, (220, 80, 0))):
        if g:
            cv2.rectangle(img, (int(g[0]), int(g[1])), (int(g[2]), int(g[3])), col, 2)
    b = [int(x) for x in v["box"]]
    cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
    if v.get("point"):
        cv2.circle(img, (int(v["point"][0]), int(v["point"][1])), 5, (0, 220, 220), -1)
    cv2.putText(img, f"{k} f={cmd} green=acquired red=tgtGT blue=distGT",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.imwrite(str(ovr / f"{k}.jpg"), img)


def score(out: Path, matrix: str) -> None:
    acq = json.loads((out / "acquire.json").read_text())
    carry_res = json.loads((out / "carry.json").read_text()) if (out / "carry.json").exists() else {}
    scenes = {(_s["clip"], _s["f0"]): _s for _s in _gating(matrix)}
    gts = {}
    per = {}
    for k, v in acq.items():
        scene = scenes.get((v["clip"], v["f0"]))
        if scene is None:
            continue
        clip = scene["clip"]
        gt = gts.setdefault(clip, load_gt(clip))
        if v["box"] is None:
            per[k] = {"leg": v["leg"], "arm": v["arm"], "pass": False,
                      "reason": v.get("reason"), "deliver_iou": 0.0,
                      "deliver_iou_distractor": 0.0, "coverage": 0.0}
            continue
        m, _ = _score_cell(v, carry_res.get(k), gt, scene)
        per[k] = m
        _overlay(out, k, v, carry_res.get(k), gt, scene)

    # paired McNemar NL vs PT, per leg, over scenes
    report = {"n_scenes": len(scenes), "per_cell": per, "legs": {}}
    for leg in LEGS:
        nl = {f"{s['clip']}_{s['f0']}": int(per.get(_key('NL', leg, s), {}).get("pass", False))
              for s in scenes.values()}
        pt = {f"{s['clip']}_{s['f0']}": int(per.get(_key('PT', leg, s), {}).get("pass", False))
              for s in scenes.values()}
        b, c, n = gstats.discordant_counts(nl, pt)   # b=NL-only-pass, c=PT-only-pass
        p = gstats.mcnemar(b, c, "two-sided")
        n_clips = len({s["clip"] for s in scenes.values()})
        report["legs"][leg] = {
            "n": n, "n_clips_effective": n_clips,
            "nl_pass": sum(nl.values()), "pt_pass": sum(pt.values()),
            "mcnemar": {"b_nl_only": b, "c_pt_only": c, "p": p,
                        "min_discordant": gstats.min_discordant_for_significance(n)},
        }
    (out / "results.json").write_text(json.dumps(report, indent=2))
    for leg in LEGS:
        r = report["legs"][leg]
        print(f"[score] {leg}: NL {r['nl_pass']}/{r['n']}  PT {r['pt_pass']}/{r['n']}  "
              f"McNemar b(NLonly)={r['mcnemar']['b_nl_only']} "
              f"c(PTonly)={r['mcnemar']['c_pt_only']} p={r['mcnemar']['p']} "
              f"(min_discordant={r['mcnemar']['min_discordant']}, {r['n_clips_effective']} clips)",
              flush=True)
    print("[score] NOTE: verdict requires the hand visual audit (verdict_exp2.py) over "
          "discordant + SWAP-pass cells.", flush=True)


# ---- selfcheck ----------------------------------------------------------------
def selfcheck() -> None:
    # point center -> degenerate box centered on the point
    g = (100.0, 40.0, 140.0, 80.0)
    cb = _center_box(g)
    assert abs((cb[0] + cb[2]) / 2 - 120.0) < 1e-9 and abs((cb[1] + cb[3]) / 2 - 60.0) < 1e-9, cb
    # SWAP pass logic: delivered distractor, suppressed target
    gt = {480: (10.0, 10.0, 30.0, 30.0)}
    scene = {"clip": "x", "f0": 240, "t_p": 8.0, "distractor_gt_prompt": [100, 100, 130, 130]}

    class _GT(dict):
        def __len__(self):  # _score_cell does cmd < len(gt)
            return 900
    gtl = _GT(gt)
    v_swap_good = {"leg": "SWAP", "arm": "PT", "cmd": 480, "box": [100, 100, 130, 130]}
    m, ok = _score_cell(v_swap_good, None, gtl, scene)
    assert ok and m["deliver_iou"] < 0.25 and m["deliver_iou_distractor"] >= 0.25, m
    v_swap_bad = {"leg": "SWAP", "arm": "NL", "cmd": 480, "box": [10, 10, 30, 30]}  # grounded target
    _, bad = _score_cell(v_swap_bad, None, gtl, scene)
    assert not bad, "SWAP must FAIL when the target box is delivered instead of the distractor"
    # WSEL needs coverage>=0.5 AND deliver_iou>=0.25
    carry_cell = {"steps": [491, 502], "boxes": [[10, 10, 30, 30], [10, 10, 30, 30]]}
    gtl2 = _GT({480: (10.0, 10.0, 30.0, 30.0), 491: (10.0, 10.0, 30.0, 30.0),
                502: (10.0, 10.0, 30.0, 30.0)})
    v_wsel = {"leg": "WSEL", "arm": "NL", "cmd": 480, "box": [10, 10, 30, 30]}
    _, wok = _score_cell(v_wsel, carry_cell, gtl2, scene)
    assert wok, "WSEL should pass with a locked box + full coverage"
    print("select_exp2 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", choices=["acquire", "carry", "score"])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", default=str(N25 / "scenes_p518.json"))
    ap.add_argument("--out", default="runs/exp2")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "acquire":
        acquire(out, a.matrix)
    elif a.mode == "carry":
        carry(out)
    elif a.mode == "score":
        score(out, a.matrix)
    else:
        ap.error("need a mode (acquire|carry|score) or --selfcheck")


if __name__ == "__main__":
    main()
