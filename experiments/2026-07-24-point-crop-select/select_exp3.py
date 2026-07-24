"""EXP-3 -- CARLA click-to-ground-to-track TIMING at the discovered resolutions.

Composes the two elbows found earlier into one clicked pipeline and times it on the SAME
recorded CARLA scenes:
  - grounding at the point-crop elbow (EXP-2: PT@256 out-grounds NL@1024), and
  - carry at the tracker elbow (EXP-1: image_size 640 = 99.4% of 1024's IoU at 2.5x throughput).

User clicks an object -> hit-test resolves the clicked pixel to a CARLA actor id (over the
already-projected GT boxes) -> VLM grounds a crop around the click -> SAM2 carries the box.
Two arms differ ONLY in the two resolution knobs, on identical frames:
  OPT  : ground crop @ ROI_RES=256, carry @ image_size=640   (the discovered resolutions)
  FULL : ground crop @ ROI_RES=1024, carry @ image_size=1024  (naive full-res baseline)

Primary metric = per-scene LATENCY (grounding wall ms + on-device carry ms/frame), paired
OPT-vs-FULL over the clips (Wilcoxon signed-rank). GT is free on every CARLA frame (gt.jsonl),
so grounding IoU + carry coverage ride along as the accuracy guardrail -- a timing win is only
real if accuracy does not regress. Altitude (40-120 m across the bank) is the analysis axis.

Data: the deterministic 25-clip bank at experiments/2026-07-21-carla-gt-bank/runs/bank/
(Town10HD_Opt, nadir, per-frame per-vehicle GT). CARLA rendered these earlier on the 3090; here
we REPLAY frames from disk and run BOTH the VLM (q8_0) and SAM2 carry on the Jetson. machine=jetson.

  .venv-ft/bin/python select_exp3.py acquire --out runs/exp3   # VLM point-crop ground, both arms
  .venv-ft/bin/python select_exp3.py carry   --out runs/exp3   # SAM2 carry on the Orin, both arms
  .venv-ft/bin/python select_exp3.py score   --out runs/exp3   # timing + accuracy, paired
  .venv-ft/bin/python select_exp3.py --selfcheck
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P55 = REPO / "experiments" / "2026-07-14-select-generalization"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
for p in (HERE, P55, E24, E18, REPO, REPO / "grounding"):
    sys.path.insert(0, str(p))

# reuse the EXP-2 ssh-bridge framing + the point-crop grounder verbatim
from select_exp2 import _center_box, _recv, _rgb_jpg_arr, _send   # noqa: E402
from replay_e24 import MAX_SIDE, _valid, vlm_acquire              # noqa: E402
from replay_source import iou                                     # noqa: E402
from select_p55 import roi_reanchor                               # noqa: E402
import select_p55                                                 # noqa: E402  (mutate ROI_RES)

BANK = REPO / "experiments" / "2026-07-21-carla-gt-bank" / "runs" / "bank"
CAPTION = "car"

# --- rich caption (color + object + position) --------------------------------
# The crop is centered on the click by construction, so the target is ALWAYS at the
# crop center -> position is the constant "in the center" (it ties the caption to the
# click). Object comes from the CARLA actor type; colour is sampled from the target's
# pixels (CARLA does not log vehicle colour in gt.jsonl). This mirrors a RefDrone-style
# referring expression, which is what the terse grounding model was trained on.
_TYPE_WORD = {  # actor-type fragment -> object word (default "car")
    "charger_police": "police car", "sprinter": "van", "patrol": "SUV",
    "ambulance": "ambulance", "cybertruck": "truck"}
# OpenCV hue (0-179) -> colour name, for the saturated (chromatic) case
_HUE_BINS = [(9, "red"), (22, "orange"), (33, "yellow"), (85, "green"),
             (130, "blue"), (160, "purple"), (180, "red")]


def object_word(ttype: str) -> str:
    key = ttype.split("vehicle.")[-1]
    for frag, word in _TYPE_WORD.items():
        if frag in key:
            return word
    return "car"


def named_color(patch_bgr) -> str:
    """Colour of a top-down car crop. Saturated body pixels vote the hue (so the gray
    roof-glass and the road margin can't hijack a coloured car); if too few are saturated
    the car is achromatic -> black / white / silver by brightness."""
    if patch_bgr is None or patch_bgr.size == 0:
        return "silver"
    hsv = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sat = s > 70
    if sat.mean() > 0.15:                        # enough coloured pixels -> chromatic car
        hue = float(np.median(h[sat]))
        return next(name for edge, name in _HUE_BINS if hue <= edge)
    vv = float(np.median(v))                      # achromatic -> brightness decides
    return "black" if vv < 70 else "white" if vv > 185 else "silver"


def rich_caption(frame_bgr, box, ttype: str) -> str:
    """'{colour} {object} in the center' -- colour from the target's inner pixels."""
    x1, y1, x2, y2 = (int(round(v)) for v in box)
    x1, y1 = max(0, x1), max(0, y1)
    w, h = x2 - x1, y2 - y1
    mx, my = int(w * 0.15), int(h * 0.15)        # trim the box edge (road/shadow bleed)
    patch = frame_bgr[y1 + my:y2 - my, x1 + mx:x2 - mx]
    if patch.size == 0:
        patch = frame_bgr[y1:y2, x1:x2]
    return f"{named_color(patch)} {object_word(ttype)} in the center"

ARMS = {"OPT": {"ground_res": 256, "carry_size": 640},
        "FULL": {"ground_res": 1024, "carry_size": 1024}}
WINDOW_S = 8.0            # carry window seconds
FED_HZ = 5.0             # frames fed to the tracker per second (strided from the ~18 Hz bank)
CMD_SEARCH_FROM = 100    # look for the command frame from here (let traffic move off the settle)
MIN_AREA_VIS = 120.0     # target must be at least this many visible px to be a fair click
BRIDGE = "cd ~/sam2-bench && ./.venv/bin/python -u carry_ssh_bridge.py --image-size {size}"


# ---- CARLA bank loaders -------------------------------------------------------
def clips() -> list[str]:
    return sorted(d.name for d in BANK.iterdir() if d.is_dir() and (d / "gt.jsonl").exists())


def manifest(clip: str) -> dict:
    return json.loads((BANK / clip / "manifest.json").read_text())


def load_rows(clip: str) -> list[dict]:
    """Per-frame rows: {'i','cam','cam_rot','gt':[actor,...]}. ~31 MB/clip, load once per clip."""
    return [json.loads(l) for l in (BANK / clip / "gt.jsonl").open()]


def frame(clip: str, i: int):
    img = cv2.imread(str(BANK / clip / "frames" / f"{i:05d}.jpg"))
    assert img is not None, f"missing frame {clip}/{i}"
    return img


def _actor(row: dict, aid: int):
    for a in row["gt"]:
        if a["id"] == aid:
            return a
    return None


def target_box(row: dict, tid: int):
    """The target's in-frame (clipped) box at this row, or None if off-screen/too small."""
    a = _actor(row, tid)
    if a is None or a.get("box_vis") is None or a.get("area_vis_px", 0) < 1:
        return None
    return tuple(a["box_vis"])


def visible_vehicles(row: dict):
    """[(id, box_vis, area_vis)] for every on-screen vehicle -- the hit-test candidates."""
    out = []
    for a in row["gt"]:
        if a.get("kind") == "vehicle" and a.get("box_vis") and a.get("area_vis_px", 0) >= 1:
            out.append((a["id"], tuple(a["box_vis"]), float(a["area_vis_px"])))
    return out


def hit_test(px: float, py: float, row: dict):
    """Resolve a clicked pixel to an actor id: the SMALLEST-area visible vehicle box that
    contains the point (smallest-area breaks overlap ties toward the nearer/topmost car)."""
    hits = [(area, aid, box) for aid, box, area in visible_vehicles(row)
            if box[0] <= px <= box[2] and box[1] <= py <= box[3]]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def pick_cmd(clip: str, rows: list[dict], tid: int):
    """First frame >= CMD_SEARCH_FROM where the target is on-screen and >= MIN_AREA_VIS px."""
    for i in range(CMD_SEARCH_FROM, len(rows)):
        a = _actor(rows[i], tid)
        if a and a.get("box_vis") and a.get("area_vis_px", 0) >= MIN_AREA_VIS:
            return i
    return None


def _fed_frames(cmd: int, n_frames: int, cap_hz: float) -> list[int]:
    stride = max(1, round(cap_hz / FED_HZ))
    last = cmd + round(WINDOW_S * cap_hz)
    return [fi for fi in range(cmd + stride, min(last, n_frames), stride)]


# ---- acquire (VLM point-crop on the Orin, both arms) --------------------------
def acquire(out: Path, cap_mode: str = "generic") -> None:
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend

    cl = clips()
    print(f"[acquire:{cap_mode}] booting Jetson q8_0 for {len(cl)} clips x {len(ARMS)} arms...",
          flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)
    _t = {"ms": 0.0}

    def submit_img(img_bgr, caption):
        h, w = img_bgr.shape[:2]
        path = f"/dev/shm/exp3_acq_{time.monotonic_ns()}.png"
        cv2.imwrite(path, img_bgr)
        try:
            t0 = time.perf_counter()
            box = vlm_acquire(be, path, caption, w, h)
            _t["ms"] = round(1000 * (time.perf_counter() - t0), 1)
            return box
        finally:
            Path(path).unlink(missing_ok=True)

    res = {}
    try:
        for clip in cl:
            m = manifest(clip)
            tid = m["target_id"]
            rows = load_rows(clip)
            cmd = pick_cmd(clip, rows, tid)
            if cmd is None:
                print(f"[acquire] {clip} SKIP: target never >= {MIN_AREA_VIS}px", flush=True)
                continue
            tb = target_box(rows[cmd], tid)
            cx, cy = (tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0   # the click = target center
            hid = hit_test(cx, cy, rows[cmd])                       # REAL hit-test on that pixel
            frame_cmd = frame(clip, cmd)
            cap = CAPTION if cap_mode == "generic" else rich_caption(frame_cmd, tb, m["target_type"])
            for arm, cfg in ARMS.items():
                select_p55.ROI_RES = cfg["ground_res"]              # the grounding-res knob
                box, dbg = roi_reanchor(frame_cmd, _center_box((cx, cy, cx, cy)),
                                        cap, submit_img)
                ok = _valid(box, frame_cmd.shape)
                gi = iou(tuple(box), tb) if ok else 0.0
                res[f"{arm}_{clip}"] = {
                    "clip": clip, "arm": arm, "cmd": cmd, "alt": m["alt"],
                    "target_id": tid, "target_type": m["target_type"],
                    "click": [round(cx, 1), round(cy, 1)],
                    "caption": cap,
                    "hit_id": hid, "hit_ok": (hid == tid),
                    "target_box": [round(x, 1) for x in tb],
                    "box": [round(x, 1) for x in box] if ok else None,
                    "ground_iou": round(gi, 4), "ground_ms": _t["ms"],
                    "ground_res": cfg["ground_res"], "carry_size": cfg["carry_size"],
                    "cap_hz": m["capture_hz"], "reason": None if ok else "acquire-failed"}
                print(f"[acquire] {arm}_{clip} alt={m['alt']:.0f} hit_ok={hid == tid} "
                      f"g_iou={gi:.2f} g_ms={_t['ms']:.0f} box={res[f'{arm}_{clip}']['box']}",
                      flush=True)
    finally:
        be.close()
    fname = "acquire.json" if cap_mode == "generic" else "acquire_rich.json"
    (out / fname).write_text(json.dumps(res, indent=1))
    n_ok = sum(v["box"] is not None for v in res.values())
    n_hit = sum(v["hit_ok"] for v in res.values())
    print(f"[acquire:{cap_mode}] {n_ok}/{len(res)} grounded, hit-test {n_hit}/{len(res)} "
          f"-> {fname}", flush=True)


# ---- carry (SAM2 on the Orin, one bridge per arm at its carry_size) -----------
def carry(out: Path) -> None:
    acq = json.loads((out / "acquire.json").read_text())
    for arm, cfg in ARMS.items():
        size = cfg["carry_size"]
        cf = out / f"carry_{arm}.json"
        if cf.exists():
            print(f"[carry] {arm} reuse {cf.name}", flush=True)
            continue
        cells = [(k, v) for k, v in acq.items() if v["arm"] == arm and v.get("box") is not None]
        log = open(out / f"bridge_{arm}.err", "wb")
        proc = subprocess.Popen(["ssh", "-T", "-q", "jetson", BRIDGE.format(size=size)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        res, t0 = {}, time.time()
        for i, (k, v) in enumerate(cells):
            clip, cmd = v["clip"], v["cmd"]
            rows = load_rows(clip)
            steps = _fed_frames(cmd, len(rows), v["cap_hz"])
            _send(proc.stdin, ("init", _rgb_jpg_arr(frame(clip, cmd)), [int(x) for x in v["box"]]))
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
            print(f"[carry] {arm} [{i + 1}/{len(cells)}] {k} steps={len(steps)} "
                  f"median_ms={np.median([m for m in mss if m]):.0f}", flush=True)
        proc.stdin.close()
        proc.wait()
        log.close()
        cf.write_text(json.dumps(res, indent=1))
        print(f"[carry] {arm} {len(res)} cells in {time.time() - t0:.0f}s -> {cf.name}", flush=True)


# ---- score (timing primary, accuracy guardrail) -------------------------------
def _carry_metrics(clip, v, carry_cell, rows, tid):
    held = tot = 0
    ious = []
    for fi, cb in zip(carry_cell["steps"], carry_cell["boxes"]):
        g = target_box(rows[fi], tid) if fi < len(rows) else None
        if g is None:
            continue
        tot += 1
        j = iou(tuple(cb), g) if cb else 0.0
        ious.append(j)
        if j >= 0.25:
            held += 1
    ms = [m for m in carry_cell["ms"] if m]
    return {"coverage": round(held / tot, 3) if tot else 0.0,
            "carry_median_iou": round(float(np.median(ious)), 4) if ious else 0.0,
            "carry_median_ms": round(float(np.median(ms)), 1) if ms else None,
            "carry_hz": round(1000.0 / float(np.median(ms)), 3) if ms else None,
            "n_steps": len(carry_cell["steps"])}


def _overlay(out: Path, k, v, rows, tid):
    ovr = out / "overlays"
    ovr.mkdir(exist_ok=True)
    img = frame(v["clip"], v["cmd"]).copy()
    frac = float((img == img[0, 0]).all(axis=2).mean())
    assert frac < 0.99, f"{k} cmd frame {frac:.0%} one colour -- failed render"
    tb = target_box(rows[v["cmd"]], tid)
    if tb:
        cv2.rectangle(img, (int(tb[0]), int(tb[1])), (int(tb[2]), int(tb[3])), (0, 0, 220), 2)
    if v.get("box"):
        b = [int(x) for x in v["box"]]
        cv2.rectangle(img, (b[0], b[1]), (b[2], b[3]), (0, 220, 0), 2)
    cx, cy = int(v["click"][0]), int(v["click"][1])
    cv2.circle(img, (cx, cy), 5, (0, 220, 220), -1)
    cv2.putText(img, f"{k} alt{v['alt']:.0f} g_iou={v['ground_iou']:.2f} "
                f"green=ground red=GT yellow=click", (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imwrite(str(ovr / f"{k}.jpg"), img)


def score(out: Path) -> None:
    from scipy.stats import wilcoxon
    acq = json.loads((out / "acquire.json").read_text())
    carries = {arm: json.loads((out / f"carry_{arm}.json").read_text())
               if (out / f"carry_{arm}.json").exists() else {} for arm in ARMS}
    rows_cache = {}
    per = {}
    for k, v in acq.items():
        clip = v["clip"]
        rows = rows_cache.setdefault(clip, load_rows(clip))
        tid = v["target_id"]
        m = dict(v)
        cc = carries[v["arm"]].get(k)
        if cc:
            m.update(_carry_metrics(clip, v, cc, rows, tid))
            m["end_to_end_ms"] = round((v["ground_ms"] or 0) + sum(x for x in cc["ms"] if x), 1)
        per[k] = m
        if v.get("box"):
            _overlay(out, k, v, rows, tid)

    cl = sorted({v["clip"] for v in acq.values()})
    # paired OPT vs FULL over clips where BOTH arms grounded
    def paired(field):
        o, f = [], []
        for clip in cl:
            po, pf = per.get(f"OPT_{clip}"), per.get(f"FULL_{clip}")
            if po and pf and po.get(field) is not None and pf.get(field) is not None:
                o.append(po[field]); f.append(pf[field])
        return o, f

    report = {"n_clips": len(cl), "per_cell": per, "arms": {}, "paired": {}}
    for arm in ARMS:
        vs = [per[f"{arm}_{clip}"] for clip in cl if f"{arm}_{clip}" in per]
        gi = [x["ground_iou"] for x in vs]
        cov = [x.get("coverage") for x in vs if x.get("coverage") is not None]
        cms = [x.get("carry_median_ms") for x in vs if x.get("carry_median_ms")]
        gms = [x["ground_ms"] for x in vs if x.get("ground_ms")]
        report["arms"][arm] = {
            "n": len(vs), "hit_ok": sum(x["hit_ok"] for x in vs),
            "ground_iou_median": round(float(np.median(gi)), 4) if gi else None,
            "ground_hit_rate@0.5": round(float(np.mean([g >= 0.5 for g in gi])), 3) if gi else None,
            "ground_ms_median": round(float(np.median(gms)), 1) if gms else None,
            "coverage_median": round(float(np.median(cov)), 3) if cov else None,
            "carry_ms_median": round(float(np.median(cms)), 1) if cms else None,
            "carry_hz_median": round(1000.0 / float(np.median(cms)), 3) if cms else None}
    for field in ("ground_ms", "carry_median_ms", "end_to_end_ms", "ground_iou", "coverage"):
        o, f = paired(field)
        d = {"n_pairs": len(o), "opt_median": round(float(np.median(o)), 4) if o else None,
             "full_median": round(float(np.median(f)), 4) if f else None,
             "median_paired_diff_opt_minus_full":
                 round(float(np.median(np.array(o) - np.array(f))), 4) if o else None}
        if len(o) >= 3 and any(a != b for a, b in zip(o, f)):
            try:
                d["wilcoxon_p"] = round(float(wilcoxon(o, f).pvalue), 5)
            except ValueError:
                d["wilcoxon_p"] = None
        report["paired"][field] = d
    (out / "results.json").write_text(json.dumps(report, indent=2))
    print(f"[score] {len(cl)} clips. hit-test OPT {report['arms']['OPT']['hit_ok']}/"
          f"{report['arms']['OPT']['n']}", flush=True)
    for arm in ARMS:
        a = report["arms"][arm]
        print(f"  {arm}: g_iou~{a['ground_iou_median']} hit@0.5={a['ground_hit_rate@0.5']} "
              f"g_ms~{a['ground_ms_median']} cov~{a['coverage_median']} "
              f"carry_ms~{a['carry_ms_median']} ({a['carry_hz_median']} Hz)", flush=True)
    for field in ("ground_ms", "carry_median_ms", "end_to_end_ms", "ground_iou", "coverage"):
        p = report["paired"][field]
        print(f"  paired {field}: OPT {p['opt_median']} vs FULL {p['full_median']} "
              f"(diff {p['median_paired_diff_opt_minus_full']}, "
              f"p={p.get('wilcoxon_p')}, n={p['n_pairs']})", flush=True)


# ---- selfcheck ----------------------------------------------------------------
def selfcheck() -> None:
    # hit-test: smallest-area containing box wins on overlap
    row = {"gt": [
        {"id": 1, "kind": "vehicle", "box_vis": [0, 0, 100, 100], "area_vis_px": 10000},
        {"id": 2, "kind": "vehicle", "box_vis": [40, 40, 60, 60], "area_vis_px": 400},
        {"id": 3, "kind": "walker", "box_vis": [50, 50, 55, 55], "area_vis_px": 25}]}
    assert hit_test(50, 50, row) == 2, "smallest-area vehicle box must win the overlap"
    assert hit_test(10, 10, row) == 1, "point only in the big box -> that id"
    assert hit_test(200, 200, row) is None, "point outside all boxes -> None"
    # walkers are not hit-test candidates (vehicle-only GT)
    assert hit_test(52, 52, row) == 2, "walker ignored; the vehicle box that contains it wins"
    # fed-frame strider: ~18 Hz bank, 8 s window, 5 Hz feed -> stride ~4
    fr = _fed_frames(cmd=100, n_frames=1000, cap_hz=18.8)
    assert fr and fr[0] == 104 and all(fr[i + 1] - fr[i] == 4 for i in range(len(fr) - 1)), fr
    assert fr[-1] <= 100 + round(8.0 * 18.8), fr[-1]
    # target_box None when off-screen
    assert target_box({"gt": [{"id": 9, "box_vis": None, "area_vis_px": 0}]}, 9) is None
    # rich caption: object word + colour from pixels + constant position
    assert object_word("vehicle.dodge.charger_police_2020") == "police car"
    assert object_word("vehicle.mercedes.sprinter") == "van"
    assert object_word("vehicle.ford.mustang") == "car"
    red = np.zeros((20, 20, 3), np.uint8); red[:, :, 2] = 200      # solid red (BGR)
    assert rich_caption(red, (0, 0, 20, 20), "vehicle.ford.mustang") == "red car in the center"
    blue = np.zeros((20, 20, 3), np.uint8); blue[:, :, 0] = 200    # solid blue
    assert named_color(blue) == "blue", named_color(blue)
    gray = np.full((20, 20, 3), 150, np.uint8)                    # achromatic mid -> silver
    assert named_color(gray) == "silver", named_color(gray)
    assert named_color(np.full((20, 20, 3), 20, np.uint8)) == "black"
    assert named_color(np.full((20, 20, 3), 230, np.uint8)) == "white"
    print("select_exp3 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", choices=["acquire", "carry", "score"])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--caption", choices=["generic", "rich"], default="generic")
    ap.add_argument("--out", default="runs/exp3")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "acquire":
        acquire(out, a.caption)
    elif a.mode == "carry":
        carry(out)
    elif a.mode == "score":
        score(out)
    else:
        ap.error("need a mode (acquire|carry|score) or --selfcheck")


if __name__ == "__main__":
    main()
