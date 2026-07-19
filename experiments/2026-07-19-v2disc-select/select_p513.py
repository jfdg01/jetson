"""P5.13 contract A/B select on the P5.12 bank v2.1 designed-crossing bank (Part V).

Two contracts, evaluated PAIRED on identical carries, per (clip, leg) cell:

  DD (direct delivery, the parked P5.6 contract): the operator phrase binds to
     a carried candidate by its stored caption (string equality against the
     bank's per-object phrases); that candidate's carried box at the prompt
     frame is delivered directly. No VLM call, acquire_s = 0.
  RG (prompt-time re-ground, the P5.3 contract): the deployed VLM
     (Qwen2-VL-2B q8_0 terse on the Jetson) fires full-frame at the prompt
     with the phrase; the raw box is IoU-matched against the carried boxes at
     the prompt frame (MATCH_FLOOR 0.10, argmax, NO_MATCH below floor); the
     matched track's box at prompt + round(acquire_s*fps) is delivered.

Both contracts read the SAME deterministic dual-candidate carry pass: two SAM2
carries seeded at f0 from the bank's GT boxes (oracle-seed scope cut, as in
P5.1-P5.6), stepped on every CAND_STRIDE-th frame (rate cap = the on-Orin
two-candidate budget), zero-order hold between samples. The carry pass is
cached to runs/carry_<clip>.json so both legs (and any resume) score
byte-identical carries.

Scene source: the P5.12 bank v2.1 designed-crossing bank
(experiments/2026-07-17-bankv21-recal/runs/bank01..bank12), 300 frames @
25 fps, 1280x720, per-frame GT for BOTH cars (id0 "the white car", id1 "the
blue car"). Exact dual GT makes selection scoring exact — no hand-annotated
distractor boxes (P5.6's curation step is obsolete here).

Usage:
    .venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py --preflight
    .venv-ft/bin/python experiments/2026-07-19-v2disc-select/select_p513.py \
        --matrix
    # single clip / leg rerun (resumable; completed cells are skipped):
    ... --matrix --only bank03 --legs white --out .../runs
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BANK = REPO / "experiments" / "2026-07-17-bankv21-recal" / "runs"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import iou                       # noqa: E402
from replay_e24 import MAX_SIDE, _rgb, _valid, vlm_acquire  # noqa: E402

# ---------------------------------------------------------------- constants
FPS = 25.0                 # bank camera rate (40 ms sim steps)
N_FRAMES = 300             # bank v2.1 clip length (12.0 s)
T_P = 6.0                  # idle window s: prompt lands AFTER the crossing (see README)
PROMPT_FRAME = round(T_P * FPS)          # 150
CARRY_HZ = 6.15            # E1 on-Orin SAM2 budget (two candidates share it)
CAND_STRIDE = max(1, round(FPS / (CARRY_HZ / 2.0)))  # 8 -> 3.125 Hz/candidate
MATCH_FLOOR = 0.10         # P5.3/P5.4/P5.5-consistent NO_MATCH floor
DELIVER_FLOOR = 0.25       # P5.3-consistent lock floor
OVERRUN_FRAME = N_FRAMES - 1
CLIPS = [f"bank{i:02d}" for i in range(1, 13)]
LEGS = {"white": "the white car", "blue": "the blue car"}

DD_CLASSES = ("CARRY_LOST", "CARRY_SWITCH", "CARRY_DRIFT")
RG_CLASSES = ("NO_BOX", "OVERRUN", "NO_MATCH", "MATCH_WRONG",
              "DELIVERY_LOST", "DELIVERY_SWITCH", "DELIVERY_DRIFT")


# ---------------------------------------------------------------- helpers
def sample_frames() -> list[int]:
    """Carry-pass sample set: every CAND_STRIDE-th frame, plus a forced sample
    exactly at the prompt frame and at the last frame."""
    s = set(range(0, N_FRAMES, CAND_STRIDE))
    s.add(PROMPT_FRAME)
    s.add(N_FRAMES - 1)
    return sorted(s)


def zoh(track: dict, f: int):
    """Zero-order hold: the last sampled VALID box at or before frame f (what a
    realtime consumer would hold). None if no valid sample yet."""
    best = None
    for fs in sorted(track):
        if fs > f:
            break
        if track[fs] is not None:
            best = track[fs]
    return best


def frame_health(frame: np.ndarray, prev: np.ndarray | None, f: int) -> None:
    """Cheap mechanical render checks (CLAUDE.md 'Look at it'):
    a frame >99% one colour is a failed render, not a night scene; frames
    byte-identical across time are a dead feed, not a still camera."""
    small = frame[::8, ::8]
    _, counts = np.unique(small.reshape(-1, small.shape[-1]), axis=0,
                          return_counts=True)
    assert counts.max() / counts.sum() <= 0.99, \
        f"frame {f}: >99% a single colour -> failed render"
    if prev is not None:
        assert not np.array_equal(frame, prev), \
            f"frame {f}: byte-identical to previous sampled frame -> dead feed"


def load_bank_clip(clip: str, bank_root: Path = BANK):
    """Load one bank clip: frame paths + {oid: phrase} + {oid: [box|None]*300}.
    Asserts the P5.9 schema (2 objects, distinct phrases, 300 GT lines)."""
    d = bank_root / clip
    lines = (d / "gt.jsonl").read_text().strip().splitlines()
    assert len(lines) == N_FRAMES, f"{clip}: {len(lines)} gt lines != {N_FRAMES}"
    recs = [json.loads(ln) for ln in lines]
    objs0 = recs[0]["objs"]
    assert len(objs0) == 2, f"{clip}: expected 2 objects, got {len(objs0)}"
    phrases = {o["id"]: o["phrase"] for o in objs0}
    assert len(set(phrases.values())) == 2, f"{clip}: phrases not distinct"
    gtb = {oid: [None] * N_FRAMES for oid in phrases}
    for r in recs:
        assert len(r["objs"]) == 2, f"{clip} f{r['f']}: missing object"
        for o in r["objs"]:
            if o["visible"]:
                gtb[o["id"]][r["f"]] = tuple(float(v) for v in o["bbox"])
    paths = [d / "frames" / f"{i:04d}.png" for i in range(N_FRAMES)]
    for pth in (paths[0], paths[PROMPT_FRAME], paths[-1]):
        assert pth.exists(), f"{clip}: missing frame {pth}"
    return paths, phrases, gtb


def carry_pass(make_carry, frame_at, seed_boxes: dict) -> dict:
    """Deterministic dual-candidate carry: seed both candidates at f0 from GT,
    step both on every sampled frame (frame-health asserted), record the box
    (or None if invalid). Returns {oid: {f: box|None}} incl. the f0 seed."""
    samples = sample_frames()
    f0 = frame_at(0)
    carries = {oid: make_carry(_rgb(f0), tuple(b))
               for oid, b in seed_boxes.items()}
    tracks = {oid: {0: tuple(seed_boxes[oid])} for oid in carries}
    prev = f0
    for f in samples[1:]:
        frame = frame_at(f)
        frame_health(frame, prev, f)
        prev = frame
        for oid, c in carries.items():
            _, b = c.step(_rgb(frame))
            tracks[oid][f] = tuple(float(v) for v in b) \
                if _valid(b, frame.shape) else None
    return tracks


def delivery_metrics(box, g_named, g_other) -> dict:
    """IoUs of a delivered box vs both GT boxes + the two pass rules:
    gating   = IoU_named >= DELIVER_FLOOR AND IoU_named > IoU_other (dominance:
               robust to GT-GT overlap when the cars cross in image space);
    strict   = IoU_named >= DELIVER_FLOOR AND IoU_other < DELIVER_FLOOR
               (P5.6's strengthened-rule shape, non-gating diagnostic)."""
    i_n = iou(box, g_named) if (box is not None and g_named is not None) else 0.0
    i_o = iou(box, g_other) if (box is not None and g_other is not None) else 0.0
    return {"iou_named": round(i_n, 4), "iou_other": round(i_o, 4),
            "ok": bool(i_n >= DELIVER_FLOOR and i_n > i_o),
            "strict_ok": bool(i_n >= DELIVER_FLOOR and i_o < DELIVER_FLOOR)}


def dd_result(named: int, other: int, tracks: dict, gtb: dict) -> dict:
    """DD contract: deliver the named candidate's carried box at the prompt."""
    box = zoh(tracks[named], PROMPT_FRAME)
    out = {"deliver_frame": PROMPT_FRAME, "acquire_s": 0.0,
           "delivered_box": None if box is None else [round(v, 1) for v in box]}
    if box is None:
        out.update({"pass": False, "fail_class": "CARRY_LOST",
                    "iou_named": 0.0, "iou_other": 0.0, "strict_ok": False})
        return out
    m = delivery_metrics(box, gtb[named][PROMPT_FRAME], gtb[other][PROMPT_FRAME])
    cls = None
    if not m["ok"]:
        cls = ("CARRY_SWITCH"
               if m["iou_other"] >= DELIVER_FLOOR and m["iou_other"] >= m["iou_named"]
               else "CARRY_DRIFT")
    out.update({"pass": m["ok"], "fail_class": cls, "iou_named": m["iou_named"],
                "iou_other": m["iou_other"], "strict_ok": m["strict_ok"]})
    return out


def rg_result(phrase: str, named: int, other: int, tracks: dict, gtb: dict,
              submit, frame_at) -> dict:
    """RG contract: full-frame VLM at the prompt, IoU-match vs carried boxes,
    deliver the matched track's ZOH box at prompt + round(acquire_s*FPS).
    submit(frame_bgr, phrase) -> (pixel box | None, acquire_s)."""
    vbox, acquire_s = submit(frame_at(PROMPT_FRAME), phrase)
    deliver = PROMPT_FRAME + round(acquire_s * FPS)
    overrun = deliver > OVERRUN_FRAME
    deliver_c = min(deliver, OVERRUN_FRAME)
    g_named_p, g_other_p = gtb[named][PROMPT_FRAME], gtb[other][PROMPT_FRAME]
    frame_shape = frame_at(PROMPT_FRAME).shape

    out = {"acquire_s": round(acquire_s, 2), "deliver_frame": deliver_c,
           "overrun": overrun,
           "vlm_box": None if vbox is None else [round(v, 1) for v in vbox]}

    # non-gating attribution: where did the raw VLM box land (vs exact GT)?
    if vbox is None or not _valid(vbox, frame_shape):
        out["vlm_on"] = None
    else:
        vn = iou(vbox, g_named_p) if g_named_p else 0.0
        vo = iou(vbox, g_other_p) if g_other_p else 0.0
        out["vlm_on"] = ("named" if vn >= DELIVER_FLOOR and vn > vo else
                         "other" if vo >= DELIVER_FLOOR else "miss")
        out["vlm_iou_named"], out["vlm_iou_other"] = round(vn, 4), round(vo, 4)

    def fail(cls, **extra):
        out.update({"pass": False, "fail_class": cls, "selection": None,
                    "delivered_box": None, "iou_named": 0.0, "iou_other": 0.0,
                    "strict_ok": False, **extra})
        return out

    if vbox is None or not _valid(vbox, frame_shape):
        return fail("NO_BOX")
    if overrun:
        return fail("OVERRUN")

    match_ious = {oid: (iou(vbox, b) if (b := zoh(tracks[oid], PROMPT_FRAME))
                        is not None else 0.0) for oid in tracks}
    out["match_ious"] = {str(k): round(v, 4) for k, v in match_ious.items()}
    selection = max(match_ious, key=match_ious.get)
    if match_ious[selection] < MATCH_FLOOR:
        return fail("NO_MATCH")
    out["selection"] = selection
    if selection != named:
        return fail("MATCH_WRONG", selection=selection)

    box = zoh(tracks[selection], deliver_c)
    if box is None:
        return fail("DELIVERY_LOST", selection=selection)
    m = delivery_metrics(box, gtb[named][deliver_c], gtb[other][deliver_c])
    cls = None
    if not m["ok"]:
        cls = ("DELIVERY_SWITCH"
               if m["iou_other"] >= DELIVER_FLOOR and m["iou_other"] >= m["iou_named"]
               else "DELIVERY_DRIFT")
    out.update({"pass": m["ok"], "fail_class": cls, "selection": selection,
                "delivered_box": [round(v, 1) for v in box],
                "iou_named": m["iou_named"], "iou_other": m["iou_other"],
                "strict_ok": m["strict_ok"]})
    return out


def coverage(track: dict, gtseq: list, f_start: int) -> dict:
    """Non-gating: per-frame ZOH IoU vs GT over [f_start, N_FRAMES)."""
    ious = []
    for f in range(f_start, N_FRAMES):
        if gtseq[f] is None:
            continue
        b = zoh(track, f)
        ious.append(iou(b, gtseq[f]) if b is not None else 0.0)
    if not ious:
        return {"mean_iou": 0.0, "frac_lock": 0.0, "n": 0}
    a = np.asarray(ious)
    return {"mean_iou": round(float(a.mean()), 4),
            "frac_lock": round(float((a >= DELIVER_FLOOR).mean()), 4),
            "n": len(ious)}


# ---------------------------------------------------------------- overlays
def draw_overlay(frame_bgr, out_path: Path, f: int, label: str,
                 g_named=None, g_other=None, delivered=None, vbox=None) -> None:
    """Named GT red, other GT orange, delivered box green (thick), raw VLM box
    yellow. Frame index + verdict text top-left."""
    img = frame_bgr.copy()

    def rect(b, color, th):
        cv2.rectangle(img, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])),
                      color, th)

    if g_named is not None:
        rect(g_named, (0, 0, 220), 2)          # red = named GT
    if g_other is not None:
        rect(g_other, (0, 140, 255), 2)        # orange = other GT
    if vbox is not None:
        rect(vbox, (0, 220, 220), 2)           # yellow = raw VLM box
    if delivered is not None:
        rect(delivered, (60, 220, 60), 3)      # green = delivered box
    cv2.putText(img, f"f={f} {label}", (8, 26), cv2.FONT_HERSHEY_SIMPLEX,
                0.62, (245, 245, 245), 2)
    cv2.putText(img, "green=delivered red=namedGT orange=otherGT yellow=vlm",
                (8, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (245, 245, 245), 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(out_path), img)
    assert ok, f"overlay write failed: {out_path}"


# ---------------------------------------------------------------- one cell
def run_cell(clip: str, leg: str, phrases: dict, gtb: dict, tracks: dict,
             submit, frame_at, out_dir: Path, extra_meta: dict | None = None):
    """Score both contracts for one (clip, leg) cell and snapshot everything.
    Pure post-hoc arithmetic on the shared carry pass + one VLM call (in
    submit). Writes results.json + 4 overlay PNGs."""
    phrase = LEGS[leg]
    by_phrase = {v: k for k, v in phrases.items()}
    assert phrase in by_phrase, f"{clip}: phrase {phrase!r} not in bank GT"
    named = by_phrase[phrase]
    other = next(o for o in phrases if o != named)

    dd = dd_result(named, other, tracks, gtb)
    rg = rg_result(phrase, named, other, tracks, gtb, submit, frame_at)
    cov_dd = coverage(tracks[named], gtb[named], PROMPT_FRAME)
    cov_rg = (coverage(tracks[rg["selection"]], gtb[named], rg["deliver_frame"])
              if rg.get("selection") is not None else
              {"mean_iou": 0.0, "frac_lock": 0.0, "n": 0})
    gt_overlap_prompt = (iou(gtb[named][PROMPT_FRAME], gtb[other][PROMPT_FRAME])
                         if gtb[named][PROMPT_FRAME] and gtb[other][PROMPT_FRAME]
                         else 0.0)

    result = {
        "cell": f"{clip}_{leg}", "clip": clip, "leg": leg, "phrase": phrase,
        "named_id": named, "other_id": other,
        "fps": FPS, "t_p": T_P, "prompt_frame": PROMPT_FRAME,
        "cand_stride": CAND_STRIDE, "match_floor": MATCH_FLOOR,
        "deliver_floor": DELIVER_FLOOR,
        "seed_boxes": {str(o): [round(v, 1) for v in tracks[o][0]]
                       for o in tracks},
        "gt_overlap_prompt": round(gt_overlap_prompt, 4),
        "dd": dd, "rg": rg, "cov_dd": cov_dd, "cov_rg": cov_rg,
        # full sampled carry tracks (small): scoring is exactly reproducible
        # from this file + gt.jsonl alone, without the runs/carry_*.json cache
        "tracks": {str(o): {str(f): (None if b is None else
                                     [round(v, 1) for v in b])
                            for f, b in t.items()}
                   for o, t in tracks.items()},
        **(extra_meta or {}),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))

    # overlays (mid-clip frames -- never frame 0)
    fp = PROMPT_FRAME
    draw_overlay(frame_at(fp), out_dir / f"overlay_dd_f{fp:04d}.png", fp,
                 f"{clip}_{leg} DD pass={dd['pass']} cls={dd['fail_class']}",
                 gtb[named][fp], gtb[other][fp],
                 delivered=dd["delivered_box"])
    draw_overlay(frame_at(fp), out_dir / f"overlay_vlm_f{fp:04d}.png", fp,
                 f"{clip}_{leg} RG raw vlm_on={rg.get('vlm_on')}",
                 gtb[named][fp], gtb[other][fp], vbox=rg.get("vlm_box"))
    fd = rg["deliver_frame"]
    draw_overlay(frame_at(fd), out_dir / f"overlay_rg_f{fd:04d}.png", fd,
                 f"{clip}_{leg} RG pass={rg['pass']} cls={rg['fail_class']} "
                 f"acq={rg['acquire_s']}s",
                 gtb[named][fd], gtb[other][fd],
                 delivered=rg.get("delivered_box"))
    fe = N_FRAMES - 1
    draw_overlay(frame_at(fe), out_dir / f"overlay_end_f{fe:04d}.png", fe,
                 f"{clip}_{leg} end-of-clip carries (green=named, yellow=other)",
                 gtb[named][fe], gtb[other][fe],
                 delivered=zoh(tracks[named], fe),
                 vbox=zoh(tracks[other], fe))
    print(f"[P5.13 {clip}_{leg}] DD pass={dd['pass']} ({dd['fail_class']}) "
          f"iouN={dd['iou_named']} | RG pass={rg['pass']} "
          f"({rg['fail_class']}) vlm_on={rg.get('vlm_on')} "
          f"acq={rg['acquire_s']}s deliver=f{rg['deliver_frame']}", flush=True)
    return result


# ---------------------------------------------------------------- VLM client
class VLMClient:
    """One Jetson q8_0 backend for the whole matrix. A transport/boot EXCEPTION
    triggers one reboot + one retry of that call; a clean parse-fail (None) is
    a legitimate NO_BOX result and is NEVER retried (no outcome shopping)."""

    def __init__(self):
        self.be = None
        self.reboots = 0

    def _boot(self):
        from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
        from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
        from grounding.eval.backends import JetsonBackend
        print("[P5.13] booting Jetson q8_0 server...", flush=True)
        self.be = JetsonBackend(
            f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
            f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
            ssh_host="jetson", max_side=MAX_SIDE)

    def submit(self, frame_bgr, caption):
        h, w = frame_bgr.shape[:2]
        for attempt in (0, 1):
            try:
                if self.be is None:
                    self._boot()
                path = f"/dev/shm/p513_{time.monotonic_ns()}.png"
                cv2.imwrite(path, frame_bgr)
                try:
                    t0 = time.monotonic()
                    box = vlm_acquire(self.be, path, caption, w, h)
                    return box, time.monotonic() - t0
                finally:
                    Path(path).unlink(missing_ok=True)
            except Exception as e:                        # noqa: BLE001
                print(f"[P5.13] VLM call failed ({e!r}); "
                      f"{'rebooting once' if attempt == 0 else 'giving up'}",
                      flush=True)
                self.close()
                self.reboots += 1
                if attempt:
                    raise
        raise RuntimeError("unreachable")

    def close(self):
        if self.be is not None:
            try:
                self.be.close()
            finally:
                self.be = None


# ---------------------------------------------------------------- matrix
def run_matrix(args) -> None:
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    clips = [c for c in CLIPS if args.only in (None, c)]
    legs = [l for l in LEGS if args.legs in (None, l)]
    assert clips and legs, "empty selection (--only/--legs typo?)"

    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    vlm = VLMClient()
    versions = {"torch": torch.__version__, "numpy": np.__version__,
                "cv2": cv2.__version__, "sam2_model": MODEL,
                "vlm": "qwen2-vl-2b q8_0 terse (Jetson llama.cpp)",
                "python": sys.version.split()[0]}
    try:
        for clip in clips:
            todo = [l for l in legs
                    if not (out_root / f"{clip}_{l}" / "results.json").exists()]
            if not todo:
                print(f"[P5.13] {clip}: all cells done, skipping", flush=True)
                continue
            paths, phrases, gtb = load_bank_clip(clip, Path(args.bank))
            cache = {}

            def frame_at(i, _paths=paths, _c=cache):
                if i not in _c:
                    f = cv2.imread(str(_paths[min(i, N_FRAMES - 1)]))
                    assert f is not None, f"unreadable frame {i} of {_paths[0].parent}"
                    _c[i] = f
                return _c[i]

            carry_file = out_root / f"carry_{clip}.json"
            if carry_file.exists():
                raw = json.loads(carry_file.read_text())
                tracks = {int(o): {int(f): (None if b is None else tuple(b))
                                   for f, b in t.items()}
                          for o, t in raw["tracks"].items()}
                print(f"[P5.13] {clip}: carry pass loaded from cache", flush=True)
            else:
                seed_boxes = {oid: gtb[oid][0] for oid in phrases}
                for oid, b in seed_boxes.items():
                    assert b is not None, f"{clip}: no GT seed at f0 for id{oid}"
                t0 = time.time()
                with torch.inference_mode(), \
                        torch.autocast("cuda", dtype=torch.bfloat16):
                    tracks = carry_pass(
                        lambda rgb, box: StreamCarry(predictor, rgb, box),
                        frame_at, seed_boxes)
                carry_file.write_text(json.dumps(
                    {"clip": clip, "cand_stride": CAND_STRIDE,
                     "samples": sample_frames(), "wall_s": round(time.time() - t0, 1),
                     "tracks": {str(o): {str(f): b for f, b in t.items()}
                                for o, t in tracks.items()}}, indent=1))
                print(f"[P5.13] {clip}: carry pass done "
                      f"({time.time() - t0:.0f}s), cached", flush=True)

            for leg in todo:
                run_cell(clip, leg, phrases, gtb, tracks, vlm.submit, frame_at,
                         out_root / f"{clip}_{leg}",
                         extra_meta={"versions": versions,
                                     "vlm_reboots_so_far": vlm.reboots})
    finally:
        vlm.close()
    print(f"[P5.13] matrix done (vlm reboots: {vlm.reboots})", flush=True)


# ---------------------------------------------------------------- preflight
def preflight(bank_root: Path = BANK) -> None:
    """Offline bank validation (no GPU, no Jetson). Verifies the dataset this
    experiment consumes actually exists and is healthy on THIS machine."""
    for clip in CLIPS:
        paths, phrases, gtb = load_bank_clip(clip, bank_root)
        assert set(phrases.values()) == set(LEGS.values()), \
            f"{clip}: phrases {sorted(phrases.values())}"
        missing = [i for i, p in enumerate(paths) if not p.exists()]
        assert not missing, f"{clip}: {len(missing)} missing frames, first {missing[0]}"
        prev = None
        for f in (10, PROMPT_FRAME, 180):
            fr = cv2.imread(str(paths[f]))
            assert fr is not None and fr.shape[:2] == (720, 1280), \
                f"{clip} f{f}: bad frame"
            frame_health(fr, prev, f)
            prev = fr
        # consecutive-pair dead-feed check
        a, b = cv2.imread(str(paths[PROMPT_FRAME])), cv2.imread(str(paths[PROMPT_FRAME + 1]))
        assert not np.array_equal(a, b), f"{clip}: f150==f151 (dead feed)"
        vis = min(sum(g is not None for g in gtb[o]) for o in gtb)
        ov = max((iou(gtb[0][f], gtb[1][f]) if gtb[0][f] and gtb[1][f] else 0.0)
                 for f in range(N_FRAMES))
        print(f"[preflight] {clip}: 300 frames, phrases OK, min-visible {vis}/300, "
              f"max GT-GT IoU {ov:.3f}")
    print(f"preflight OK ({len(CLIPS)} clips)")


# ---------------------------------------------------------------- selfcheck
class _StubCarry:
    """Deterministic scripted carry: pops one box per step() in sample order."""

    def __init__(self, boxes):
        self.boxes = list(boxes)

    def step(self, _frame):
        return None, self.boxes.pop(0)


def _synth_clip(tmp: Path, jitter=0):
    """Synthetic 300-frame bank clip: noisy grey bg, moving white + blue rects,
    real gt.jsonl in the P5.9 schema. Returns (bank_root, clip_name)."""
    rng = np.random.default_rng(7)
    clip = "bank01"
    d = tmp / clip
    (d / "frames").mkdir(parents=True)
    recs = []
    for f in range(N_FRAMES):
        img = rng.integers(70, 130, (180, 320, 3), np.uint8)
        wb = (20 + 0.5 * f, 40.0, 60 + 0.5 * f, 70.0)
        bb = (200 - 0.3 * f, 100.0, 240 - 0.3 * f, 130.0)
        cv2.rectangle(img, (int(wb[0]), int(wb[1])), (int(wb[2]), int(wb[3])),
                      (255, 255, 255), -1)
        cv2.rectangle(img, (int(bb[0]), int(bb[1])), (int(bb[2]), int(bb[3])),
                      (200, 60, 20), -1)
        cv2.imwrite(str(d / "frames" / f"{f:04d}.png"), img)
        recs.append(json.dumps({"f": f, "objs": [
            {"id": 0, "phrase": "the white car", "bbox": list(wb), "visible": True},
            {"id": 1, "phrase": "the blue car", "bbox": list(bb), "visible": True},
        ]}))
    (d / "gt.jsonl").write_text("\n".join(recs) + "\n")
    return tmp, clip


def selfcheck() -> None:
    """Offline: no GPU, no Jetson, no bank. Exercises every scoring rule and
    fail class on scripted carries + a scripted VLM, the gt.jsonl parser on a
    synthetic clip, the overlay writer, and the frame-health asserts."""
    import tempfile

    # -- arithmetic
    s = sample_frames()
    assert s[0] == 0 and PROMPT_FRAME in s and (N_FRAMES - 1) in s
    assert CAND_STRIDE == 8 and PROMPT_FRAME == 150
    assert zoh({0: (1, 1, 2, 2), 8: None, 16: (3, 3, 4, 4)}, 12) == (1, 1, 2, 2)
    assert zoh({0: (1, 1, 2, 2), 8: None, 16: (3, 3, 4, 4)}, 20) == (3, 3, 4, 4)
    assert zoh({8: (1, 1, 2, 2)}, 4) is None

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bank_root, clip = _synth_clip(tmp)
        paths, phrases, gtb = load_bank_clip(clip, bank_root)
        assert phrases == {0: "the white car", 1: "the blue car"}
        assert gtb[0][150] is not None and len(gtb[1]) == N_FRAMES

        frames = {}

        def frame_at(i):
            if i not in frames:
                frames[i] = cv2.imread(str(paths[min(i, N_FRAMES - 1)]))
            return frames[i]

        # -- carry pass with scripted perfect carries (follow GT exactly)
        samples = sample_frames()
        mk = {0: _StubCarry([gtb[0][f] for f in samples[1:]]),
              1: _StubCarry([gtb[1][f] for f in samples[1:]])}
        tracks = carry_pass(lambda _r, b: mk[_seed_id(b, gtb)], frame_at,
                            {0: gtb[0][0], 1: gtb[1][0]})
        assert tracks[0][150] == gtb[0][150] and tracks[1][299] == gtb[1][299]

        # -- DD: pass / switch / drift / lost
        assert dd_result(0, 1, tracks, gtb)["pass"]
        swapped = {0: tracks[1], 1: tracks[0]}
        r = dd_result(0, 1, swapped, gtb)
        assert not r["pass"] and r["fail_class"] == "CARRY_SWITCH", r
        junk = {0: {0: (0.0, 0.0, 5.0, 5.0), 150: (0.0, 0.0, 5.0, 5.0)},
                1: tracks[1]}
        r = dd_result(0, 1, junk, gtb)
        assert not r["pass"] and r["fail_class"] == "CARRY_DRIFT", r
        r = dd_result(0, 1, {0: {0: None}, 1: tracks[1]}, gtb)
        assert not r["pass"] and r["fail_class"] == "CARRY_LOST", r

        # -- RG: pass + every fail class
        def sub(box, acq=4.6):
            return lambda _f, _c: (box, acq)

        r = rg_result("the white car", 0, 1, tracks, gtb, sub(gtb[0][150]), frame_at)
        assert r["pass"] and r["deliver_frame"] == 150 + round(4.6 * FPS) == 265
        assert r["vlm_on"] == "named" and r["selection"] == 0, r
        r = rg_result("the white car", 0, 1, tracks, gtb, sub(None), frame_at)
        assert r["fail_class"] == "NO_BOX", r
        r = rg_result("the white car", 0, 1, tracks, gtb, sub(gtb[0][150], 7.0),
                      frame_at)
        assert r["fail_class"] == "OVERRUN" and r["deliver_frame"] == 299, r
        far = (300.0, 160.0, 318.0, 178.0)
        r = rg_result("the white car", 0, 1, tracks, gtb, sub(far), frame_at)
        assert r["fail_class"] == "NO_MATCH" and r["vlm_on"] == "miss", r
        r = rg_result("the white car", 0, 1, tracks, gtb, sub(gtb[1][150]), frame_at)
        assert r["fail_class"] == "MATCH_WRONG" and r["vlm_on"] == "other", r
        # DELIVERY_DRIFT: carry good at prompt, junk afterwards
        drift = {0: {**tracks[0], **{f: (0.0, 0.0, 6.0, 6.0)
                                     for f in samples if f > 150}}, 1: tracks[1]}
        r = rg_result("the white car", 0, 1, drift, gtb, sub(gtb[0][150]), frame_at)
        assert r["fail_class"] == "DELIVERY_DRIFT", r

        # -- dominance vs strict on overlapping GT
        ga = (10.0, 10.0, 50.0, 50.0)
        gb = (20.0, 20.0, 60.0, 60.0)          # IoU(ga,gb) ~ 0.29 > 0.25
        m = delivery_metrics(ga, ga, gb)
        assert m["ok"] and not m["strict_ok"], m       # correct box still passes
        m = delivery_metrics((100.0, 100.0, 140.0, 140.0), ga, gb)
        assert not m["ok"] and not m["strict_ok"]      # junk fails both

        # -- coverage
        c = coverage(tracks[0], gtb[0], 150)
        assert c["frac_lock"] == 1.0 and c["n"] == 150, c

        # -- overlays
        op = tmp / "ov.png"
        draw_overlay(frame_at(150), op, 150, "selfcheck", gtb[0][150], gtb[1][150],
                     delivered=gtb[0][150], vbox=gtb[1][150])
        img = cv2.imread(str(op))
        assert img is not None and img.shape == frame_at(150).shape

        # -- run_cell end-to-end (scripted carry + scripted VLM)
        res = run_cell(clip, "white", phrases, gtb, tracks,
                       sub(gtb[0][150]), frame_at, tmp / "cell")
        assert res["dd"]["pass"] and res["rg"]["pass"]
        for f in ("results.json", "overlay_dd_f0150.png", "overlay_vlm_f0150.png",
                  "overlay_rg_f0265.png", "overlay_end_f0299.png"):
            assert (tmp / "cell" / f).exists(), f

        # -- frame-health asserts have teeth
        flat = np.full((180, 320, 3), 128, np.uint8)
        try:
            frame_health(flat, None, 0)
            raise SystemExit("flat frame not caught")
        except AssertionError:
            pass
        noisy = frame_at(150)
        try:
            frame_health(noisy, noisy.copy(), 1)
            raise SystemExit("identical frames not caught")
        except AssertionError:
            pass

    print("select_p513 selfcheck OK")


def _seed_id(box, gtb):
    """selfcheck helper: which object id a seed box belongs to."""
    return 0 if tuple(box) == tuple(gtb[0][0]) else 1


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--out", default=str(HERE / "runs"))
    ap.add_argument("--bank", default=str(BANK))
    ap.add_argument("--only", default=None, help="single clip, e.g. bank03")
    ap.add_argument("--legs", default=None, choices=list(LEGS))
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
    elif args.preflight:
        preflight(Path(args.bank))
    elif args.matrix:
        run_matrix(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
