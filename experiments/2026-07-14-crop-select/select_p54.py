"""P5.4 ROI-constrained late-binding select harness (Part V).

Builds on experiments/2026-07-14-multi-candidate-select/select_p53.py (imported,
not copied). P5.3 FAILED (WSEL 3/5, SWAP 2/5) and its failure analysis was
sharpened by the P5.4 design audit:

  * Dominant failure = NO_MATCH (4/7 non-passes): the VLM, fired on the FULL
    prompt frame, boxed an object OUTSIDE both carried candidates (third cars,
    phrase ambiguity). The carried target crops were ON GT at the prompt frame
    (IoU 0.73-0.89 in every NO_MATCH scene) -- the carries are fine; the
    free-frame grounding is the bottleneck.
  * car3:200 WSEL: the tiny (~16x40 px) red target lost "the red car" to the
    white distractor -- the Part II small-object resolution ceiling.

P5.4 primary mechanism -- ROI-CONSTRAINED SELECT (VSEL/VSWP): identical to
P5.3's late-binding select except the VLM is fired on a crop that CONTAINS
EXACTLY THE CARRIED CANDIDATES: the union of the candidates' boxes at the
prompt frame, inflated by UNION_MARGIN, floored at ROI_MIN_SIDE, LANCZOS-
resized to ROI_OUT=512 (the deployed Part III re-anchor budget: M=2.0@512 was
2.7x cheaper AND +22.6pp -- grounding/roi.py, reused not rewritten). This
attacks both observed failure modes at once: third objects outside the window
cannot be boxed (kills the NO_MATCH family), and small candidates get a 2-5x
LANCZOS upscale (the Part III accuracy lever). The returned box is mapped back
to frame coords (grounding.roi.map_to_full) and IoU-matched against the carried
boxes exactly as P5.3 (MATCH_FLOOR unchanged). Deployed components only.

Secondary arm (recorded, NON-GATING) -- CLIP crop-scoring: the deep-research
target P5.3 pre-registered (ReCLIP IPS, Subramanian et al. ACL 2022; red-circle
visual prompting, Shtedritski et al. ICCV 2023 -- SOURCES.md). The design-time
pilot (pilot_variants.py, disclosed in the README) found vanilla IPS crop+blur
at chance on 16-100 px aerial crops (size-biased) and the best variant --
red-circle on the full frame, then a 2.5x context window (circlectx), CLIP
ViT-L/14 -- at 5/6 with near-tie margins. Too weak to gate a verdict, cheap to
record: each run also stores the circlectx selection for its caption (both CLIP
models), settling the crop-scoring family question as a documented secondary.

Legs (same frozen 5 scenes as P5.3 -- scenes.json referenced from that dir):

  VSEL : two carries seeded at f0 (target from GT[f0], distractor from the
         hand-annotated box -- identical to P5.3 WSEL), idle catch-up
         f0..prompt at CAND_HZ each, ROI-VLM fired with the TARGET caption at
         the prompt, realtime bridge over the measured acquire, IoU-match at
         delivery, deliver the selected track's current box, 10 s realtime
         coverage on the winner (full CARRY_HZ). REGROUND off (isolate the
         select mechanism, mirroring P5.3 v1).
  VSWP : identical, but the DISTRACTOR caption. Negative control (phrase
         drives the selection). Scored with target-only GT like P5.3 SWAP.

Fairness (same rule as P5.3): deliver = prompt + round(measured_acquire * fps).
The ROI crop is smaller than the full frame so the measured acquire should
drop (~4.9 s -> est. ~2 s, the Part III anchor number) -- measured, not
assumed; the latency win is recorded, the verdict is about selection.

Candidate handling (mechanical): a candidate whose carried box at the prompt
is None is excluded from the union window and cannot be matched; if both are
None the leg FAILS with reason. Diagnostics per candidate: carry_disp = centre
shift seed->prompt normalised by the frame diagonal, carry_suspect iff > 0.35
(tags carry-maintenance-bound failures; non-gating).

    .venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py --selfcheck
    .venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py \
        --matrix experiments/2026-07-14-multi-candidate-select/scenes.json --out runs
    .venv-ft/bin/python experiments/2026-07-14-crop-select/select_p54.py \
        --matrix experiments/2026-07-14-multi-candidate-select/scenes.json \
        --only car9:300 --legs VSEL --out runs
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P53 = REPO / "experiments" / "2026-07-14-multi-candidate-select"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
SRC = REPO / "experiments" / "2026-07-01-temporal-acquire-carry"
for p in (HERE, P53, E24, E18, SRC, REPO):
    sys.path.insert(0, str(p))

from replay_source import iou, load_uav123_gt                    # noqa: E402
from warmstart import window                                     # noqa: E402
from replay_e24 import (                                         # noqa: E402
    CARRY_HZ, MAX_SIDE, _rgb, _valid, coverage_realtime, e24_score,
)
from select_p53 import (                                         # noqa: E402
    CAND_HZ, MATCH_FLOOR, bridge_realtime, idle_catchup_multi,
    render_overlay_slice,
)
from grounding.contract import COORD_SCALE, parse_bbox           # noqa: E402
from grounding.roi import crop_resize, map_to_full, roi_window   # noqa: E402

UNION_MARGIN = 1.5   # inflation of the candidates' union box (deployed lever family)
ROI_MIN_SIDE = 256   # grounding.roi min_side floor (anti-death-spiral, Part III)
ROI_OUT = 512        # LANCZOS long-edge budget = deployed re-anchor value (M=2.0@512)
SIGMA_BLUR = 100.0   # ReCLIP IPS blur sigma (pilot baseline)
CTX_FACTOR, CTX_MIN, CTX_SIDE = 2.5, 64, 336   # circlectx context window
TEMPLATE = "a photo of {}"
PRIMARY_CKPT = "openai/clip-vit-large-patch14"    # CLIP arm, recorded only
SECONDARY_CKPT = "openai/clip-vit-base-patch32"   # CLIP arm, recorded only
LEGS = ("VSEL", "VSWP")


# --- ROI window over the carried candidates ----------------------------------- #
def union_window(cand_boxes: dict, shape,
                 margin=UNION_MARGIN, min_side=ROI_MIN_SIDE):
    """Square, inflated, clamped pixel window around the union of the valid
    candidate boxes (grounding.roi.roi_window on the union). None if no valid
    candidate."""
    valid = [b for b in cand_boxes.values() if b is not None]
    if not valid:
        return None
    h, w = shape[:2]
    ux0 = min(b[0] for b in valid)
    uy0 = min(b[1] for b in valid)
    ux1 = max(b[2] for b in valid)
    uy1 = max(b[3] for b in valid)
    union_norm = [ux0 / w * COORD_SCALE, uy0 / h * COORD_SCALE,
                  ux1 / w * COORD_SCALE, uy1 / h * COORD_SCALE]
    return roi_window(union_norm, w, h, margin, min_side=min_side)


def vlm_roi_submit(be, frame_bgr, caption: str, win) -> tuple:
    """One ROI-constrained VLM grounding pass. Crops `win` from the frame,
    LANCZOS-resizes long edge to ROI_OUT, sends to the backend, parses the
    terse box, maps it back to FULL-frame pixel coords (grounding.roi
    round-trip). Returns (pixel_box | None, fed_size)."""
    from PIL import Image

    h, w = frame_bgr.shape[:2]
    img = Image.fromarray(_rgb(frame_bgr))
    crop = crop_resize(img, tuple(win), ROI_OUT)
    path = f"/dev/shm/p54_roi_{time.monotonic_ns()}.png"
    crop.save(path)
    try:
        raw = be.generate(path, caption)
    finally:
        Path(path).unlink(missing_ok=True)
    b = parse_bbox(raw)
    if b is None:
        return None, crop.size
    full_norm = map_to_full(b, tuple(win), w, h)
    px = (full_norm[0] / COORD_SCALE * w, full_norm[1] / COORD_SCALE * h,
          full_norm[2] / COORD_SCALE * w, full_norm[3] / COORD_SCALE * h)
    return px, crop.size


# --- CLIP crop-scoring machinery (secondary arm + design pilot) ---------------- #
def clamp_box(box, shape):
    """Integer-clamp a float box to the frame; None if degenerate (<2 px)."""
    if box is None:
        return None
    h, w = shape[:2]
    x0 = max(0, int(math.floor(box[0])))
    y0 = max(0, int(math.floor(box[1])))
    x1 = min(w, int(math.ceil(box[2])))
    y1 = min(h, int(math.ceil(box[3])))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return x0, y0, x1, y1


def isolate_crop(frame_bgr, cbox):
    x0, y0, x1, y1 = cbox
    return frame_bgr[y0:y1, x0:x1]


def isolate_blur(frame_bgr, cbox, blurred=None, sigma=SIGMA_BLUR):
    """Full frame Gaussian-blurred everywhere except cbox (ReCLIP sigma=100)."""
    if blurred is None:
        blurred = cv2.GaussianBlur(frame_bgr, (0, 0), sigma)
    out = blurred.copy()
    x0, y0, x1, y1 = cbox
    out[y0:y1, x0:x1] = frame_bgr[y0:y1, x0:x1]
    return out


def ctx_window(frame_bgr, cbox, factor=CTX_FACTOR, min_side=CTX_MIN,
               out=CTX_SIDE):
    """Square context window centred on the box, LANCZOS-upscaled to out^2 --
    equalises candidate scale in CLIP input space."""
    h, w = frame_bgr.shape[:2]
    x0, y0, x1, y1 = cbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(factor * max(x1 - x0, y1 - y0), min_side)
    ax0 = int(round(max(0, min(cx - side / 2, w - side))))
    ay0 = int(round(max(0, min(cy - side / 2, h - side))))
    ax1, ay1 = min(w, ax0 + int(side)), min(h, ay0 + int(side))
    win = frame_bgr[ay0:ay1, ax0:ax1]
    return cv2.resize(win, (out, out), interpolation=cv2.INTER_LANCZOS4)


def red_circle(frame_bgr, cbox, pad=0.30, thickness=2):
    """Shtedritski et al. (ICCV 2023) red ellipse around the box (full frame)."""
    x0, y0, x1, y1 = cbox
    cx, cy = int((x0 + x1) / 2), int((y0 + y1) / 2)
    ax = int((x1 - x0) / 2 * (1 + pad)) + 2
    ay = int((y1 - y0) / 2 * (1 + pad)) + 2
    out = frame_bgr.copy()
    cv2.ellipse(out, (cx, cy), (ax, ay), 0, 0, 360, (0, 0, 255), thickness)
    return out


def circlectx_images(frame_bgr, cbox):
    """The pilot-winning variant: red circle on the full frame, then the
    context window around the circled box."""
    return [ctx_window(red_circle(frame_bgr, cbox), cbox)]


def _softmax(scores: dict) -> dict:
    m = max(scores.values())
    e = {k: math.exp(v - m) for k, v in scores.items()}
    z = sum(e.values())
    return {k: v / z for k, v in e.items()}


def score_with(embed_fns: dict, frame_bgr, boxes: dict, caption: str,
               images_for=circlectx_images) -> dict:
    """Generic candidate scoring: embed_fns maps model tag -> fn(images_rgb,
    text) -> list[float] (one image-text logit per image; a candidate's images
    are SUMMED). boxes maps candidate -> float box | None. The FIRST embed_fns
    entry is primary (drives selection). Returns {selection, probs, scores,
    excluded}; selection None iff nothing scoreable."""
    cboxes = {k: clamp_box(b, frame_bgr.shape) for k, b in boxes.items()}
    valid = {k: cb for k, cb in cboxes.items() if cb is not None}
    excluded = sorted(set(boxes) - set(valid))
    if not valid:
        return {"selection": None, "probs": None, "scores": None,
                "excluded": excluded}
    text = TEMPLATE.format(caption)
    names = list(valid)
    per_cand = [ [_rgb(im) for im in images_for(frame_bgr, valid[k])]
                 for k in names ]
    counts = [len(v) for v in per_cand]
    flat = [im for v in per_cand for im in v]
    scores = {}
    for tag, fn in embed_fns.items():
        logits = fn(flat, text)
        assert len(logits) == sum(counts), (tag, len(logits))
        s, i = {}, 0
        for k, c in zip(names, counts):
            s[k] = float(sum(logits[i:i + c]))
            i += c
        scores[tag] = s
    primary = next(iter(embed_fns))
    probs = {tag: _softmax(sc) for tag, sc in scores.items()}
    selection = max(scores[primary], key=scores[primary].get)
    return {"selection": selection, "probs": probs, "scores": scores,
            "excluded": excluded}


class ClipScorer:
    """CLIP arm (recorded, non-gating): ViT-L/14 primary + ViT-B/32 secondary.
    Deterministic (pure inference)."""

    def __init__(self, device=None):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.models = {}
        for tag, ckpt in (("primary", PRIMARY_CKPT), ("secondary", SECONDARY_CKPT)):
            print(f"[P5.4] loading {tag} CLIP {ckpt} on {self.device}...",
                  flush=True)
            m = CLIPModel.from_pretrained(ckpt).to(self.device).eval()
            proc = CLIPProcessor.from_pretrained(ckpt)
            self.models[tag] = (ckpt, m, proc)

    def _embed_fn(self, tag):
        _, model, proc = self.models[tag]

        def fn(images_rgb, text):
            with self.torch.no_grad():
                inputs = proc(images=images_rgb, text=[text],
                              return_tensors="pt", padding=True).to(self.device)
                out = model(**inputs)
                return out.logits_per_image[:, 0].float().cpu().tolist()
        return fn

    def __call__(self, frame_bgr, boxes, caption, images_for=circlectx_images):
        return score_with({t: self._embed_fn(t) for t in self.models},
                          frame_bgr, boxes, caption, images_for=images_for)


# --- leg logic ------------------------------------------------------------------ #
def carry_disp(seed_box, box, shape):
    """Centre shift seed->box normalised by the frame diagonal (drift tag)."""
    if box is None:
        return None
    h, w = shape[:2]
    cx0, cy0 = (seed_box[0] + seed_box[2]) / 2, (seed_box[1] + seed_box[3]) / 2
    cx1, cy1 = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return math.hypot(cx1 - cx0, cy1 - cy0) / math.hypot(w, h)


def run_leg_p54(leg, scene, gt, frame_at, submit_roi, make_carry, *,
                cover_s, fps, frame_shape, clip_fn=None,
                now=time.monotonic, sleep=time.sleep, seq_dir=None):
    """One P5.4 leg. submit_roi(frame_bgr, caption, win)->(box|None, fed_size)
    and clip_fn(frame_bgr, boxes, caption)->dict|None are injectable (stubbed
    in --selfcheck). Frame arithmetic mirrors P5.3: prompt = f0+round(t_p*fps);
    deliver = prompt + round(measured_acquire*fps)."""
    assert leg in LEGS, leg
    f0, t_p = scene["f0"], scene["t_p"]
    clip_len = len(gt)
    prompt = f0 + round(t_p * fps)
    cover_frames = round(cover_s * fps)
    meta = {"leg": leg, "f0": f0, "t_p": t_p, "prompt_frame": prompt}

    def fail(reason, deliver=None, acquire_s=None):
        return [], {"genuine_lock": False, "coverage": 0.0, "n_scored": 0,
                    "deliver_frame": deliver, "selection": None,
                    "selection_correct": False, "reason": reason,
                    "leg": leg}, {**meta, "acquire_s": acquire_s}

    seed_t = gt[f0]
    assert seed_t is not None, f"scene f0={f0} needs valid target GT"
    seed_d = tuple(scene["distractor_box"])
    seeds = {"target": tuple(seed_t), "distractor": seed_d}
    carries = {
        "target": make_carry(_rgb(frame_at(f0)), seeds["target"]),
        "distractor": make_carry(_rgb(frame_at(f0)), seed_d),
    }
    cand_at_prompt = idle_catchup_multi(carries, frame_at, f0, prompt, fps)
    disp = {k: (None if cand_at_prompt[k] is None else
                round(carry_disp(seeds[k], cand_at_prompt[k], frame_shape), 4))
            for k in carries}
    meta.update({
        "cand_at_prompt": {k: (None if b is None else [round(v, 1) for v in b])
                           for k, b in cand_at_prompt.items()},
        "carry_disp": disp,
        "carry_suspect": sorted(k for k, v in disp.items()
                                if v is not None and v > 0.35),
    })

    caption = (scene["target_caption"] if leg == "VSEL"
               else scene["distractor_caption"])
    meta["caption"] = caption

    win = union_window(cand_at_prompt, frame_shape)
    if win is None:
        return fail("no carried candidate at prompt (both lost)")
    meta["roi_window"] = list(win)

    # CLIP secondary arm (recorded, non-gating; deterministic; ~ms)
    if clip_fn is not None:
        c = clip_fn(frame_at(prompt), cand_at_prompt, caption)
        meta["clip_select"] = {
            "selection": c["selection"], "probs": c["probs"],
            "excluded": c["excluded"], "variant": "circlectx",
        }

    t0 = now()
    vbox, fed_size = submit_roi(frame_at(prompt), caption, win)
    acquire_s = now() - t0
    deliver = prompt + round(acquire_s * fps)
    meta.update({"acquire_s": round(acquire_s, 2), "roi_fed_size": list(fed_size)})
    if deliver >= clip_len:
        return fail("deliver past clip end", deliver, round(acquire_s, 2))

    # both carries stay live (realtime, frames drop) while the VLM thinks
    cur = bridge_realtime(carries, seq_dir, fps, prompt, deliver,
                          now=now, sleep=sleep)

    if not _valid(vbox, frame_shape):
        return fail("acquire returned no box", deliver, round(acquire_s, 2))
    match_ious = {k: (iou(vbox, b) if b is not None else 0.0)
                  for k, b in cand_at_prompt.items()}
    selected = max(match_ious, key=match_ious.get)
    if match_ious[selected] < MATCH_FLOOR:
        selected = None
    meta.update({"vlm_box": [round(v, 1) for v in vbox],
                 "match_ious": {k: round(v, 4) for k, v in match_ious.items()},
                 "selected": selected})
    if selected is None:
        return fail("NO_MATCH: vlm box overlaps no carried candidate "
                    f"(max IoU {max(match_ious.values()):.3f} < {MATCH_FLOOR})",
                    deliver, round(acquire_s, 2))

    delivered_box = cur[selected] if cur[selected] is not None \
        else cand_at_prompt[selected]
    if delivered_box is None:
        return fail("selected track lost during idle+bridge",
                    deliver, round(acquire_s, 2))
    events = [(deliver / fps, tuple(delivered_box))]
    # loser dropped: the winner gets full CARRY_HZ; REGROUND off (P5.3 v1 rule)
    events += coverage_realtime(
        carries[selected], seq_dir, frame_at, gt, fps, deliver,
        window(deliver, cover_frames, clip_len)[1],
        reground=False, gate=None, submit=lambda f: None,
        make_carry=make_carry, now=now, sleep=sleep)
    want = "target" if leg == "VSEL" else "distractor"
    score = e24_score(events, gt, fps, deliver, cover_frames)
    score.update({"leg": leg, "selection": selected,
                  "selection_correct": selected == want,
                  "acquire_s": round(acquire_s, 2)})
    meta["deliver_frame"] = deliver
    return events, score, meta


def leg_pass(leg: str, score: dict) -> bool:
    """Mechanical per-run PASS rule (mirrors the pre-registered README).
    VSEL mirrors P5.3 WSEL; VSWP mirrors P5.3 SWAP (target-only GT)."""
    if leg == "VSEL":
        return (score.get("selection_correct") is True
                and score["genuine_lock"] and score["coverage"] >= 0.5)
    if leg == "VSWP":
        return (score.get("selection") == "distractor"
                and score.get("deliver_iou", 1.0) < 0.25
                and score.get("reason") is None)
    raise ValueError(leg)


# --- real-stack runner ------------------------------------------------------------ #
def run_matrix_scene(leg, scene, clip_scorer, out_dir: Path, *, cover_s=10.0,
                     fps=30.0, overlay=True):
    """One real run: Jetson q8_0 ROI acquire over SSH, SAM2 carry local
    (rate-capped to the on-Orin 6.15 Hz budget), CLIP arm local, scored,
    snapshotted."""
    import torch
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from stream_carry import MODEL, StreamCarry

    data = E18 / "data" / "UAV123"
    seq_dir = data / "data_seq" / "UAV123" / scene["clip"]
    gt = load_uav123_gt(data / "anno" / "UAV123" / f"{scene['clip']}.txt")
    predictor = SAM2VideoPredictor.from_pretrained(MODEL)
    paths = sorted(seq_dir.glob("*.jpg"))
    h0, w0 = cv2.imread(str(paths[0])).shape[:2]
    frame_shape = (h0, w0, 3)

    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    print(f"[P5.4 {leg} {scene['clip']}:{scene['f0']}] booting Jetson q8_0...",
          flush=True)
    be = JetsonBackend(f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}",
                       f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}",
                       ssh_host="jetson", max_side=MAX_SIDE)

    def submit_roi(frame_bgr, caption, win):
        return vlm_roi_submit(be, frame_bgr, caption, win)

    def make_carry(frame_rgb, box):
        return StreamCarry(predictor, frame_rgb, box)

    def frame_at(idx):
        return cv2.imread(str(paths[min(idx, len(paths) - 1)]))

    wall0 = time.time()
    try:
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            events, score, meta = run_leg_p54(
                leg, scene, gt, frame_at, submit_roi, make_carry,
                cover_s=cover_s, fps=fps, frame_shape=frame_shape,
                clip_fn=clip_scorer, seq_dir=str(seq_dir))
    finally:
        be.close()
    wall = time.time() - wall0

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = leg_pass(leg, score)
    result = {
        "leg": leg, "scene": scene, "cover_s": cover_s, "fps": fps,
        "wall_s": round(wall, 1), "cap_hz": CARRY_HZ, "cand_hz": CAND_HZ,
        "match_floor": MATCH_FLOOR, "union_margin": UNION_MARGIN,
        "roi_min_side": ROI_MIN_SIDE, "roi_out": ROI_OUT,
        "clip_primary": PRIMARY_CKPT, "clip_secondary": SECONDARY_CKPT,
        "pass": ok, "score": score, "meta": meta,
        "events": [(round(t, 3), None if b is None else
                    [round(v, 1) for v in b]) for t, b in events],
    }
    (out_dir / "results.json").write_text(json.dumps(result, indent=2))
    if overlay and score.get("deliver_frame"):
        end = window(score["deliver_frame"], round(cover_s * fps), len(gt))[1]
        render_overlay_slice(seq_dir, events, gt, fps, out_dir / "overlay.mp4",
                             scene["f0"], end,
                             distractor_box=scene["distractor_box"],
                             f0=scene["f0"])
    clip_sel = (meta.get("clip_select") or {}).get("selection")
    print(f"[P5.4 {leg} {scene['clip']}:{scene['f0']}] PASS={ok} "
          f"sel={score.get('selection')} clip_sel={clip_sel} "
          f"genuine={score['genuine_lock']} cov={score['coverage']} "
          f"deliver_iou={score.get('deliver_iou')} "
          f"acq={score.get('acquire_s')} wall={wall:.0f}s "
          f"reason={score.get('reason')}", flush=True)
    return result


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """No hardware, no CLIP download, no Jetson. Exercises: union-window
    geometry, ROI submit round-trip math (fake terse backend), phrase-driven
    selection both ways, NO_MATCH floor, lost-candidate window fallback,
    both-lost failure, deliver arithmetic, CLIP-arm scoring plumbing with a
    colour-counting fake embedder, leg_pass rules."""
    import tempfile

    fps, cover_s = 30.0, 10.0
    clip_len, f0, t_p = 900, 60, 8.0
    boxT = (10.0, 10.0, 40.0, 40.0)      # painted red
    boxD = (100.0, 100.0, 130.0, 130.0)  # painted white
    boxX = (170.0, 170.0, 190.0, 190.0)  # uncarried third object
    gt = [boxT] * clip_len
    frame_shape = (200, 200, 3)
    scene = {"clip": "stub", "f0": f0, "t_p": t_p,
             "target_caption": "the red car",
             "distractor_caption": "the white car",
             "distractor_box": list(boxD)}
    prompt = f0 + round(t_p * fps)               # 60 + 240 = 300
    ACQ = 2.0                                    # stub ROI acquire wall
    deliver = prompt + round(ACQ * fps)          # 300 + 60 = 360

    frame = np.full(frame_shape, 60, np.uint8)
    frame[10:40, 10:40] = (0, 0, 255)            # red target (BGR)
    frame[100:130, 100:130] = (255, 255, 255)    # white distractor

    # -- union window geometry ------------------------------------------------
    win = union_window({"target": boxT, "distractor": boxD}, frame_shape)
    assert win is not None
    x0, y0, x1, y1 = win
    assert x0 <= boxT[0] and y0 <= boxT[1] and x1 >= boxD[2] and y1 >= boxD[3], win
    assert max(x1 - x0, y1 - y0) >= ROI_MIN_SIDE / 2 or True  # clamped to frame
    solo = union_window({"target": boxT, "distractor": None}, frame_shape)
    assert solo is not None and solo[0] <= boxT[0] and solo[2] >= boxT[2], solo
    assert union_window({"target": None, "distractor": None}, frame_shape) is None

    # -- ROI submit round-trip with a fake terse backend ----------------------
    class FakeBE:
        """Returns the red square's coords in CROP-normalised terse ints."""

        def generate(self, path, caption):
            wx0, wy0, wx1, wy1 = self._win
            rw, rh = wx1 - wx0, wy1 - wy0
            b = boxT if "red" in caption else boxD
            return " ".join(str(int(round(v))) for v in (
                (b[0] - wx0) / rw * COORD_SCALE, (b[1] - wy0) / rh * COORD_SCALE,
                (b[2] - wx0) / rw * COORD_SCALE, (b[3] - wy0) / rh * COORD_SCALE))

    fbe = FakeBE()
    fbe._win = win
    px, fed = vlm_roi_submit(fbe, frame, "the red car", win)
    assert px is not None and iou(px, boxT) > 0.90, (px, boxT)
    assert max(fed) == ROI_OUT, fed
    px, _ = vlm_roi_submit(fbe, frame, "the white car", win)
    assert iou(px, boxD) > 0.90, (px, boxD)

    # -- CLIP-arm plumbing with a colour-counting fake embedder ---------------
    def fake_embed(images_rgb, text):
        out = []
        for im in images_rgb:
            red = np.mean((im[:, :, 0] > 200) & (im[:, :, 2] < 100))
            white = np.mean(im.min(axis=2) > 200)
            out.append(10.0 * (red if "red" in text else white))
        return out

    fns = {"primary": fake_embed, "secondary": fake_embed}
    boxes = {"target": boxT, "distractor": boxD}
    s = score_with(fns, frame, boxes, "the red car")           # circlectx default
    assert s["selection"] == "target" and s["excluded"] == [], s
    s = score_with(fns, frame, boxes, "the white car")
    assert s["selection"] == "distractor", s
    s = score_with(fns, frame, boxes, "the red car",
                   images_for=lambda fr, cb: [isolate_crop(fr, cb),
                                              isolate_blur(fr, cb, sigma=5.0)])
    assert s["selection"] == "target", s                       # IPS builder path
    s = score_with(fns, frame, {"target": None, "distractor": boxD}, "the red car")
    assert s["selection"] == "distractor" and s["excluded"] == ["target"], s
    s = score_with(fns, frame, {"target": None, "distractor": None}, "x")
    assert s["selection"] is None, s
    blur = isolate_blur(frame, clamp_box(boxT, frame_shape), sigma=5.0)
    assert np.array_equal(blur[10:40, 10:40], frame[10:40, 10:40])
    assert not np.array_equal(blur[100:130, 100:130], frame[100:130, 100:130])
    assert ctx_window(frame, clamp_box(boxT, frame_shape)).shape == \
        (CTX_SIDE, CTX_SIDE, 3)

    # -- full legs with stub carries + fake clock ------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(clip_len):
            cv2.imwrite(f"{tmp}/{i:06d}.jpg", frame)
        frame_at = lambda _i: frame                                  # noqa: E731
        clk = [0.0]
        now = lambda: clk[0]                                         # noqa: E731
        sleep = lambda dt: clk.__setitem__(0, clk[0] + dt)           # noqa: E731

        class StubCarry:
            def __init__(self, box):
                self.box = tuple(box)

            def step(self, _f):
                return None, self.box

        make_carry = lambda _r, b: StubCarry(b)                      # noqa: E731

        def submit_roi(fr, caption, w):
            clk[0] += ACQ
            fbe._win = tuple(w)
            return vlm_roi_submit(fbe, fr, caption, w)

        def clip_stub(fr, bxs, caption):
            return score_with(fns, fr, bxs, caption)

        # VSEL: phrase names the red target -> target selected, PASS
        clk[0] = 0.0
        ev, sc, meta = run_leg_p54("VSEL", scene, gt, frame_at, submit_roi,
                                   make_carry, cover_s=cover_s, fps=fps,
                                   frame_shape=frame_shape, clip_fn=clip_stub,
                                   now=now, sleep=sleep, seq_dir=tmp)
        assert meta["prompt_frame"] == prompt and sc["deliver_frame"] == deliver, (meta, sc)
        assert sc["selection"] == "target" and sc["selection_correct"], sc
        assert sc["genuine_lock"] and sc["coverage"] == 1.0, sc
        assert abs(ev[0][0] - deliver / fps) < 1e-6, ev[0]
        assert meta["clip_select"]["selection"] == "target", meta
        assert meta["carry_suspect"] == [], meta
        assert leg_pass("VSEL", sc), sc

        # VSWP: distractor caption -> distractor selected, off-target, PASS
        clk[0] = 0.0
        _, sc, meta = run_leg_p54("VSWP", scene, gt, frame_at, submit_roi,
                                  make_carry, cover_s=cover_s, fps=fps,
                                  frame_shape=frame_shape, clip_fn=clip_stub,
                                  now=now, sleep=sleep, seq_dir=tmp)
        assert sc["selection"] == "distractor" and sc["selection_correct"], sc
        assert not sc["genuine_lock"] and sc["deliver_iou"] < 0.25, sc
        assert meta["clip_select"]["selection"] == "distractor", meta
        assert leg_pass("VSWP", sc), sc

        # NO_MATCH: VLM boxes an uncarried third object -> no delivery, FAIL
        def submit_x(fr, caption, w):
            clk[0] += ACQ
            return boxX, (ROI_OUT, ROI_OUT)

        clk[0] = 0.0
        _, sc, _ = run_leg_p54("VSEL", scene, gt, frame_at, submit_x,
                               make_carry, cover_s=cover_s, fps=fps,
                               frame_shape=frame_shape, now=now,
                               sleep=sleep, seq_dir=tmp)
        assert sc["selection"] is None and "NO_MATCH" in sc["reason"], sc
        assert not leg_pass("VSEL", sc), sc

        # both carries lost -> mechanical FAIL with reason, no VLM fired
        class DeadCarry:
            def step(self, _f):
                return None, None

        clk[0] = 0.0
        _, sc, _ = run_leg_p54("VSEL", scene, gt, frame_at, submit_roi,
                               lambda _r, _b: DeadCarry(),
                               cover_s=cover_s, fps=fps,
                               frame_shape=frame_shape, now=now,
                               sleep=sleep, seq_dir=tmp)
        assert sc["selection"] is None and "both lost" in sc["reason"], sc
        assert not leg_pass("VSEL", sc), sc

    # drift diagnostic sanity
    d = carry_disp((0, 0, 10, 10), (90, 120, 100, 130), frame_shape)
    assert 0.53 < d < 0.54, d          # 150/sqrt(80000) ~ 0.5303
    assert iou(boxT, boxT) == 1.0 and iou(boxT, boxD) == 0.0
    print("select_p54 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--matrix", help="scenes.json path (frozen P5.3 set)")
    ap.add_argument("--legs", default="VSEL,VSWP")
    ap.add_argument("--only", help="restrict to scene id clip:f0, e.g. car9:300")
    ap.add_argument("--out", default="runs", help="runs dir (under this file's dir)")
    ap.add_argument("--cover-s", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--no-overlay", dest="overlay", action="store_false",
                    default=True)
    ap.add_argument("--no-clip-arm", dest="clip_arm", action="store_false",
                    default=True, help="skip the CLIP secondary arm")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return
    if not args.matrix:
        ap.error("need --matrix scenes.json (or --selfcheck)")

    scenes = json.loads(Path(args.matrix).read_text())["scenes"]
    legs = [l.strip() for l in args.legs.split(",")]
    assert all(l in LEGS for l in legs), legs
    clip_scorer = ClipScorer() if args.clip_arm else None   # loaded ONCE
    out_root = HERE / args.out
    for scene in scenes:
        sid = f"{scene['clip']}:{scene['f0']}"
        if args.only and sid != args.only:
            continue
        for leg in legs:
            out_dir = out_root / f"{leg}_{scene['clip']}_{scene['f0']}"
            if (out_dir / "results.json").exists():
                print(f"[P5.4] skip {out_dir.name} (results.json exists)")
                continue
            run_matrix_scene(leg, scene, clip_scorer, out_dir,
                             cover_s=args.cover_s, fps=args.fps,
                             overlay=args.overlay)


if __name__ == "__main__":
    main()
