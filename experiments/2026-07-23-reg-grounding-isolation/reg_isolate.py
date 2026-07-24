"""REG -- grounding isolation: target-phrase vs distractor-phrase on the same frame.

What it does
------------
Isolates the GROUNDING stage of the Part V select pipeline from everything
downstream (carry / delivery). For each scene in the shared R-36 bank it dumps the
ONE prompt frame and grounds the deployed Jetson VLM twice on it -- once with the
target caption, once with the distractor caption -- then scores each returned box by
IoU >= 0.25 against its OWN hand GT:

  Arm A (target)     correct <=> IoU(box, target_gt)     >= 0.25   (target_gt = load_gt(clip)[prompt])
  Arm B (distractor) correct <=> IoU(box, distractor_gt) >= 0.25   (distractor_gt = scene['distractor_gt_prompt'])

Paired exact McNemar over distinct base captures answers RQ-REG: is the residual
select failure a grounding asymmetry (the VLM resolves the intended referent but not
an arbitrary distractor phrase on the same frame) or does the failure live downstream?

  b = target-correct AND distractor-wrong   (grounding resolves the referent, not the distractor)
  c = target-wrong    AND distractor-correct
  Directional expectation b >> c. Symmetric branch (b ~ c) = failure NOT isolable to
  grounding -> attribution redirects to carry / delivery. Honest content either way.

Subcommands (flags): --pilot grounds the distractor arm ONLY and reports its isolated
base rate first -- P5.18's 0.65 distractor rate was END-TO-END and confounds
carry+delivery, so reachability is only claimed after this pilot. The default run is
the paired matrix (both arms, same frame). --verdict <runs_dir> recomputes the
McNemar b/c + deflated p from a written results.json.

Reused, not reimplemented (signatures confirmed before use)
-----------------------------------------------------------
  vlm_acquire   experiments/2026-07-04-warm-start-acquire/replay_e24.py:93  (the grounding call)
  JetsonBackend grounding/eval/backends.py:344  (Orin q8_0 over SSH -- grounding runs HERE, never a local 3090 model)
  load_gt/frame experiments/2026-07-20-n25-select/curate_p518.py:49  (target GT rows + 1-indexed frame reader)
  iou           experiments/2026-07-03-real-video-replay/replay_source.py:86
  mcnemar / deflate_to_effective / min_discordant_for_significance / wilson_ci  grounding/stats.py

Machine of every number (registered machine='both'; S6 dependent decomposition of R-36)
---------------------------------------------------------------------------------------
  grounding boxes + all correctness / pass counts: JETSON ORIN NANO 8 GB, deployed
    phase3-terse100eos-1024-q8_0.gguf + mmproj-phase3-terse100eos-1024-f16.gguf at
    /home/jfdg/grounding, 15 W + jetson_clocks, max_side=1024, via JetsonBackend over SSH.
  McNemar / deflation / Wilson CI: host CPU (pure arithmetic over the on-device outcomes).
  No SAM2, no carry, no CARLA in this experiment -- this is the grounding stage alone.

Run for real (DEFERRED -- this file is written pure-logic and is NOT run on-device here)
---------------------------------------------------------------------------------------
  # pilot: isolated distractor-grounding base rate on the prompt frames (on-device)
  .venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py \
      --bank runs/r36/bank --pilot --out runs/reg/pilot
  # paired on-device matrix (target + distractor phrase, same frame)
  .venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py \
      --bank runs/r36/bank --out runs/reg
  # verdict (McNemar b/c + deflated p, same Part-V Holm family as R-36)
  .venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py \
      --verdict runs/reg
  # pure-logic self-test (no Jetson, no dataset, no GPU, no SSH):
  .venv-ft/bin/python experiments/2026-07-23-reg-grounding-isolation/reg_isolate.py --selftest
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E18 = REPO / "experiments" / "2026-07-03-real-video-replay"
E24 = REPO / "experiments" / "2026-07-04-warm-start-acquire"
P518 = REPO / "experiments" / "2026-07-20-n25-select"
for _p in (str(REPO), str(E18), str(E24), str(P518)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Light, pure imports only (no torch / SAM2 / CARLA): iou is a scalar formula and
# grounding.stats is scipy-only, so --selftest runs on these with no GPU/dataset/SSH.
from replay_source import iou                                            # noqa: E402
from grounding.stats import (                                           # noqa: E402
    deflate_to_effective, mcnemar, min_discordant_for_significance, wilson_ci,
)

IOU_FLOOR = 0.25          # same lock/coverage floor as every rule in Parts IV-V
FPS_DEFAULT = 30.0
ARMS_ALL = ("target", "distractor")


# --------------------------------------------------------------------------- #
# pure logic: correctness classifier, paired tally, verdict (host CPU)
# --------------------------------------------------------------------------- #
def arm_correct(box, gt, floor: float = IOU_FLOOR) -> bool:
    """Per-arm correctness: a grounded box is correct iff it lands on THAT arm's own
    hand GT at IoU >= floor. A None box (parse failure / no box) or a None/NaN GT is
    wrong. Shared verbatim by both arms -- the only difference between arms is which
    GT the box is scored against."""
    if box is None or gt is None:
        return False
    return iou(box, gt) >= floor


def classify_row(scene: dict, boxes: dict, target_gt, arms=ARMS_ALL,
                 *, fps: float = FPS_DEFAULT) -> dict:
    """Map the grounded box(es) of one scene to a paired row. The dispatch that
    matters: the TARGET box is scored against the target GT and the DISTRACTOR box
    against `scene['distractor_gt_prompt']` -- crossing them would manufacture the
    asymmetry the test is looking for. Pure; the run path fills `boxes` from
    vlm_acquire. Only the requested arms get a correctness key (so a --pilot row does
    not carry a spurious target_correct=False)."""
    dist_gt = tuple(scene["distractor_gt_prompt"]) if scene.get("distractor_gt_prompt") else None
    prompt = scene["f0"] + round(scene["t_p"] * fps)
    row = {"clip": scene["clip"], "f0": scene["f0"], "prompt_frame": prompt,
           "gating": scene.get("gating", True), "arms": list(arms)}
    if "target" in arms:
        tb = boxes.get("target")
        row["target_box"] = list(tb) if tb else None
        row["target_gt"] = list(target_gt) if target_gt else None
        row["target_correct"] = arm_correct(tb, target_gt)
    if "distractor" in arms:
        db = boxes.get("distractor")
        row["distractor_box"] = list(db) if db else None
        row["distractor_gt"] = list(dist_gt) if dist_gt else None
        row["distractor_correct"] = arm_correct(db, dist_gt)
    return row


def base_capture(clip: str) -> str:
    """R-36 S1 unit: one distinct UAV123 base capture. Strip the '_s' short-sequence
    suffix; different onsets (f0) on the same clip collapse by the shared clip string
    (car9:300 and car9:560 -> one unit; car1 and car1_s -> one). Used as n_effective
    for the deflation, so two scenes off one video never count as two independent
    grounding trials."""
    return clip[:-2] if clip.endswith("_s") else clip


def tally(rows: list[dict]) -> tuple[int, int, int]:
    """Paired discordant tally over the GATING rows. b = (target-correct AND
    distractor-wrong); c = (target-wrong AND distractor-correct). Returns (b, c, n)."""
    g = [r for r in rows if r.get("gating", True)]
    b = sum(1 for r in g if r["target_correct"] and not r["distractor_correct"])
    c = sum(1 for r in g if not r["target_correct"] and r["distractor_correct"])
    return b, c, len(g)


def verdict(rows: list[dict]) -> dict:
    """Frozen-gate verdict from the per-scene grounding outcomes (host CPU, pure
    arithmetic over the on-device boxes). Deflates the discordant counts from the
    paired denominator (n_rows) down to distinct base captures (n_eff) with the blunt
    R-29-style rescale, then runs the exact two-sided McNemar. Reachability is a
    statement about the DESIGN, computed from n_eff alone.

    branch: 'asymmetric-grounding' (H0 rejected, b>>c) | 'symmetric' (b~c, failure
    not isolable to grounding -> redirect downstream) | 'no-discordance' (b+c==0,
    no test)."""
    b_obs, c_obs, n_rows = tally(rows)
    g = [r for r in rows if r.get("gating", True)]
    n_eff = len({base_capture(r["clip"]) for r in g}) if g else 0
    if n_eff:
        b, _ = deflate_to_effective(b_obs, n_rows, n_eff)
        c, _ = deflate_to_effective(c_obs, n_rows, n_eff)
    else:
        b, c = b_obs, c_obs
    p_raw = mcnemar(b_obs, c_obs)
    p_def = mcnemar(b, c)
    floor = min_discordant_for_significance(n_eff) if n_eff else None
    reachable = floor is not None
    sig = (p_def == p_def) and p_def <= 0.05           # NaN-safe: NaN != NaN
    if b + c == 0:
        branch = "no-discordance"
    elif sig and b > c:
        branch = "asymmetric-grounding"
    else:
        branch = "symmetric"
    return {
        "b_obs": b_obs, "c_obs": c_obs, "n_rows": n_rows, "n_eff": n_eff,
        "b": b, "c": c, "p_raw": p_raw, "p_deflated": p_def,
        "min_discordant_for_alpha": floor, "reachable": reachable,
        "gate_pass": bool(sig and b > c and reachable), "branch": branch,
    }


# --------------------------------------------------------------------------- #
# on-device run path (DEFERRED; JetsonBackend built ONLY here -> --selftest is SSH-free)
# --------------------------------------------------------------------------- #
def _load_scenes(bank: str) -> list[dict]:
    """Read the shared R-36 bank scene list (same schema as scenes_p518.json: each
    scene has clip, f0, t_p, target_caption, distractor_caption, distractor_gt_prompt,
    gating). `bank` is the bank directory (looks for scenes.json / bank.json / *scenes*.json)
    or a scenes JSON path directly."""
    p = Path(bank)
    if p.is_dir():
        cands = [p / "scenes.json", p / "bank.json", *sorted(p.glob("*scenes*.json"))]
        p = next((c for c in cands if c.exists()), None)
        if p is None:
            raise FileNotFoundError(f"no scenes json under bank dir {bank}")
    return json.loads(p.read_text())["scenes"]


def ground_scene(backend, scene: dict, arms, *, fps: float) -> dict:
    """Ground the deployed VLM on the ONE prompt frame of a scene, once per requested
    arm. ON-DEVICE: `backend` is a JetsonBackend, so every box comes off the Orin.
    Reads the frame + target GT via the reused curate_p518 loaders; distractor GT is
    the scene's hand box. Returns the classified paired row."""
    import cv2
    from curate_p518 import frame, load_gt            # reuse: 1-indexed frame + GT rows
    from replay_e24 import vlm_acquire                # reuse: full-frame grounding call

    clip = scene["clip"]
    prompt = scene["f0"] + round(scene["t_p"] * fps)
    img = frame(clip, prompt)
    h, w = img.shape[:2]
    gt_rows = load_gt(clip)
    target_gt = gt_rows[prompt] if prompt < len(gt_rows) else None

    path = f"/dev/shm/reg_{clip}_{prompt}_{time.monotonic_ns()}.png"
    cv2.imwrite(path, img)
    boxes: dict = {}
    try:
        if "target" in arms:
            boxes["target"] = vlm_acquire(backend, path, scene["target_caption"], w, h)
        if "distractor" in arms:
            boxes["distractor"] = vlm_acquire(backend, path, scene["distractor_caption"], w, h)
    finally:
        Path(path).unlink(missing_ok=True)
    return classify_row(scene, boxes, target_gt, arms, fps=fps)


def run_matrix(bank: str, out_dir: str, *, pilot: bool, fps: float = FPS_DEFAULT,
               only: str | None = None) -> dict:
    """Real on-device run (DEFERRED -- NOT exercised by --selftest). Boots the Jetson
    q8_0 server via JetsonBackend, grounds every scene once per arm, scores, writes
    results.json. --pilot restricts to the distractor arm (the isolated base-rate
    reachability check that must precede the paired matrix)."""
    # Guarded here so --selftest constructs no backend and makes no SSH call. These
    # constants pin the EXACT deployed pair on the Orin (reused from grounding.deploy).
    from grounding.deploy.serve import _DEFAULT_REMOTE_DIR
    from grounding.deploy.video import _REMOTE_MMPROJ, _REMOTE_MODELS
    from grounding.eval.backends import JetsonBackend
    from replay_e24 import MAX_SIDE

    arms = ("distractor",) if pilot else ARMS_ALL
    scenes = _load_scenes(bank)
    if only:
        c, f = only.split(":")
        scenes = [s for s in scenes if s["clip"] == c and str(s["f0"]) == f]
    if not scenes:
        raise ValueError(f"no scenes selected (bank={bank}, only={only})")

    model = f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MODELS['q8_0']}"
    mmproj = f"{_DEFAULT_REMOTE_DIR}/{_REMOTE_MMPROJ}"
    print(f"[REG {'pilot' if pilot else 'matrix'}] booting Jetson q8_0 "
          f"({len(scenes)} scenes x {len(arms)} arm(s)) ...", flush=True)
    be = JetsonBackend(model, mmproj, ssh_host="jetson", max_side=MAX_SIDE)

    rows: list[dict] = []
    try:
        for sc in scenes:
            row = ground_scene(be, sc, arms, fps=fps)
            rows.append(row)
            if pilot:
                print(f"[REG {sc['clip']}:{sc['f0']}] distractor_correct="
                      f"{row['distractor_correct']}", flush=True)
            else:
                print(f"[REG {sc['clip']}:{sc['f0']}] target={row['target_correct']} "
                      f"distractor={row['distractor_correct']}", flush=True)
    finally:
        be.close()

    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)
    result = {
        "machine": "jetson-orin-nano-8gb",
        "model": _REMOTE_MODELS["q8_0"], "mmproj": _REMOTE_MMPROJ,
        "remote_dir": _DEFAULT_REMOTE_DIR, "max_side": MAX_SIDE,
        "power_mode": "15W + jetson_clocks", "iou_floor": IOU_FLOOR,
        "arms": list(arms), "pilot": pilot, "fps": fps, "bank": str(bank),
        "rows": rows,
    }
    if pilot:
        g = [r for r in rows if r.get("gating", True)]
        k = sum(1 for r in g if r["distractor_correct"])
        n = len(g)
        result["pilot_summary"] = {
            "distractor_correct": k, "n": n,
            "rate": round(k / n, 4) if n else None,
            "wilson95": list(wilson_ci(k, n)) if n else None,
        }
        print(f"[REG pilot] isolated distractor grounding {k}/{n} "
              f"= {result['pilot_summary']['rate']}", flush=True)
    else:
        result["verdict"] = verdict(rows)
        v = result["verdict"]
        print(f"[REG verdict] b={v['b']} c={v['c']} n_eff={v['n_eff']} "
              f"p_def={v['p_deflated']:.4g} branch={v['branch']} "
              f"gate_pass={v['gate_pass']}", flush=True)
    (outp / "results.json").write_text(json.dumps(result, indent=2))
    return result


def run_verdict(runs_dir: str) -> dict:
    """Recompute the McNemar verdict (or pilot summary) from a written results.json."""
    r = json.loads((Path(runs_dir) / "results.json").read_text())
    if r.get("pilot"):
        ps = r.get("pilot_summary") or {}
        print(f"[REG pilot] distractor grounding {ps.get('distractor_correct')}/"
              f"{ps.get('n')} = {ps.get('rate')} (Wilson95 {ps.get('wilson95')})")
        return r
    v = verdict(r["rows"])
    print(f"[REG verdict] target-vs-distractor grounding, machine={r.get('machine')}")
    print(f"  b={v['b']} c={v['c']} (raw b={v['b_obs']} c={v['c_obs']}, "
          f"n_rows={v['n_rows']} n_eff={v['n_eff']})")
    print(f"  p_deflated={v['p_deflated']:.4g} p_raw={v['p_raw']:.4g} "
          f"reachable={v['reachable']} (need >= {v['min_discordant_for_alpha']} discordant)")
    print(f"  branch={v['branch']} gate_pass={v['gate_pass']}")
    (Path(runs_dir) / "verdict.json").write_text(json.dumps(v, indent=2))
    return v


# --------------------------------------------------------------------------- #
# pure-logic self-test (no Jetson, no dataset, no GPU, no SSH)
# --------------------------------------------------------------------------- #
def selftest() -> None:
    """Assert-based, exit 0 on pass. Covers the non-trivial logic on SYNTHETIC boxes:
    the IoU>=0.25 correctness classifier, the arm dispatch (target box vs target GT,
    distractor box vs distractor GT -- never crossed), the b/c tally, the McNemar +
    deflation-to-distinct-clips wiring, the reachability floor, and the branch/gate.
    Constructs NO JetsonBackend and touches no dataset."""

    # 1. arm_correct: exact IoU@0.25 boundary, shared by both arms, None-safe.
    gt = (0.0, 0.0, 10.0, 10.0)
    assert abs(iou((6.0, 0.0, 16.0, 10.0), gt) - 0.25) < 1e-12          # inter 40 / union 160
    assert arm_correct((6.0, 0.0, 16.0, 10.0), gt) is True             # IoU == 0.25 -> correct (>=)
    assert arm_correct((7.0, 0.0, 17.0, 10.0), gt) is False            # IoU ~0.176 -> wrong
    assert arm_correct(gt, gt) is True                                 # identical box -> IoU 1.0
    assert arm_correct(None, gt) is False                              # no box parsed
    assert arm_correct(gt, None) is False                              # NaN GT

    # 2. classify_row: correct arm dispatch, and crossing the GTs must NOT score.
    scene = {"clip": "car9", "f0": 300, "t_p": 8.0,
             "target_caption": "the silver car", "distractor_caption": "the black car",
             "distractor_gt_prompt": [100, 100, 120, 120], "gating": True}
    tgt_gt = (0.0, 0.0, 10.0, 10.0)
    row = classify_row(scene, {"target": (0, 0, 10, 10), "distractor": (0, 0, 5, 5)},
                       tgt_gt, ARMS_ALL)
    assert row["target_correct"] is True and row["distractor_correct"] is False
    assert row["prompt_frame"] == 300 + 240                            # f0 + round(t_p*fps)
    crossed = classify_row(scene, {"target": (100, 100, 120, 120),     # distractor GT as target
                                   "distractor": (0, 0, 10, 10)},       # target GT as distractor
                           tgt_gt, ARMS_ALL)
    assert crossed["target_correct"] is False and crossed["distractor_correct"] is False
    # --pilot row carries only the distractor correctness key (no spurious target fail).
    prow = classify_row(scene, {"distractor": (100, 100, 120, 120)}, tgt_gt, ("distractor",))
    assert prow["distractor_correct"] is True and "target_correct" not in prow

    # 3. tally: b = target-ok & distractor-wrong, c = reverse; non-gating excluded.
    rows = [
        {"clip": "a", "gating": True, "target_correct": True, "distractor_correct": False},   # b
        {"clip": "b", "gating": True, "target_correct": True, "distractor_correct": False},   # b
        {"clip": "c", "gating": True, "target_correct": False, "distractor_correct": True},   # c
        {"clip": "d", "gating": True, "target_correct": True, "distractor_correct": True},    # concordant
        {"clip": "e", "gating": True, "target_correct": False, "distractor_correct": False},  # concordant
        {"clip": "f", "gating": False, "target_correct": True, "distractor_correct": False},  # excluded
    ]
    assert tally(rows) == (2, 1, 5)

    # 4. McNemar wiring: verdict reproduces the exact test; distinct clips -> no deflation.
    asym = ([{"clip": f"cl{i}", "gating": True, "target_correct": True,
              "distractor_correct": False} for i in range(8)]                 # b = 8
            + [{"clip": "clX", "gating": True, "target_correct": False,
                "distractor_correct": True}]                                  # c = 1
            + [{"clip": f"cc{i}", "gating": True, "target_correct": True,
                "distractor_correct": True} for i in range(19)])              # concordant
    v = verdict(asym)
    assert (v["b_obs"], v["c_obs"], v["n_rows"], v["n_eff"]) == (8, 1, 28, 28)
    assert (v["b"], v["c"]) == (8, 1)                                          # all distinct -> no deflation
    assert abs(v["p_deflated"] - mcnemar(8, 1)) < 1e-12 and v["p_deflated"] <= 0.05
    assert v["reachable"] is True and v["branch"] == "asymmetric-grounding" and v["gate_pass"] is True

    # 5. deflation to distinct base captures: repeated clip + '_s' collapse.
    assert base_capture("car1_s") == "car1" and base_capture("car9") == "car9"
    dup = [{"clip": "car9", "gating": True, "target_correct": True, "distractor_correct": False},
           {"clip": "car9", "gating": True, "target_correct": True, "distractor_correct": False}]
    vd = verdict(dup)
    assert vd["n_rows"] == 2 and vd["n_eff"] == 1                              # one base capture
    assert (vd["b_obs"], vd["b"]) == (2, 1) and vd["c"] == 0                   # 2 -> 1 under deflation

    # 6. symmetric branch: b ~ c -> not isolable to grounding.
    sym = ([{"clip": f"s{i}", "gating": True, "target_correct": True,
             "distractor_correct": False} for i in range(2)]
           + [{"clip": f"t{i}", "gating": True, "target_correct": False,
               "distractor_correct": True} for i in range(2)]
           + [{"clip": f"z{i}", "gating": True, "target_correct": True,
               "distractor_correct": True} for i in range(24)])
    vs = verdict(sym)
    assert (vs["b"], vs["c"]) == (2, 2) and vs["branch"] == "symmetric" and vs["gate_pass"] is False

    # 7. no-discordance: b + c == 0 is "no test" (NaN p), not equivalence.
    conc = [{"clip": f"q{i}", "gating": True, "target_correct": True,
             "distractor_correct": True} for i in range(6)]
    vc = verdict(conc)
    assert (vc["b"], vc["c"]) == (0, 0) and vc["branch"] == "no-discordance"
    assert vc["p_deflated"] != vc["p_deflated"] and vc["gate_pass"] is False   # NaN

    # 8. reachability floor: n_eff = 5 cannot reach alpha even if every pair flips.
    five = [{"clip": f"u{i}", "gating": True, "target_correct": True,
             "distractor_correct": False} for i in range(5)]
    v5 = verdict(five)
    assert v5["n_eff"] == 5 and v5["reachable"] is False and v5["gate_pass"] is False

    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="REG grounding isolation (target vs distractor phrase)")
    ap.add_argument("--selftest", action="store_true", help="pure-logic self-test (no Jetson/dataset/GPU)")
    ap.add_argument("--bank", help="R-36 bank dir (or scenes JSON) -- shares scenes_p518-schema entries")
    ap.add_argument("--pilot", action="store_true", help="distractor arm ONLY: isolated base-rate check")
    ap.add_argument("--verdict", metavar="RUNS_DIR", help="recompute McNemar b/c + deflated p from a runs dir")
    ap.add_argument("--out", help="output run dir")
    ap.add_argument("--only", help="restrict to one scene, clip:f0 (e.g. car9:300)")
    ap.add_argument("--fps", type=float, default=FPS_DEFAULT)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.verdict:
        run_verdict(args.verdict)
        return
    if not args.bank or not args.out:
        ap.error("need --bank and --out (or --selftest / --verdict RUNS_DIR)")
    run_matrix(args.bank, args.out, pilot=args.pilot, fps=args.fps, only=args.only)


if __name__ == "__main__":
    main()
