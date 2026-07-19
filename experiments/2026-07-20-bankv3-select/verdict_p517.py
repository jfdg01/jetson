#!/usr/bin/env python
"""P5.17 mechanical verdict: bank v3 lag-stress build gates + DD-vs-RG select.

Two modes, both pure numeric comparisons pre-registered in README.md:

  --build     grade the 30 record runs (28 bank s<seed> + 2 determinism
              re-records), print the gate table, and write runs/bank_valid.json
              (the ONLY source of the select matrix's clip list).
              BUILD PASS iff >= 25 bank clips pass every per-clip gate AND
              G4a (both pairs) AND G4b AND G7 AND G11 hold, with <= 3 INFRA.
  (default)   select A/B verdict over runs/<clip>_<leg>/results.json:
              RQ-P5.17a |DD_total - RG_total| >= SEP_MARGIN (7) of n_cells,
              plus the pre-registered interpretation branches.
  --selfcheck offline (no gz, no GPU): synthetic v3 fixture through the real
              build grader + doctored negatives; select-mode branch table.

Per-clip build gates (adapted from P5.12's verdict_p512.py; the ONLY
structural change is that near/far roles come from the seeded z-order coin
instead of v2's fixed blue-near — plus the NEW G10):

  G0  completion: 300 gt lines, retries_pose+retries_step+response_lost <= 15
  G1  render alive: 0 dead frames, 0 identical consecutive, stamps ok
  G2c occlusion-aware purity: FAR car on CLEAR frames (occl <= 0.05) and NEAR
      car on all visible frames -- median >= 0.30 and >= 4x its bg control
  G3  co-visibility >= 0.80
  G5  >= 0.5 fps wall
  G6c fragmentation: FAR-car clear pool n >= 40, p10 >= 0.95,
      frac(<0.90) <= 0.02; NEAR-car all-frames pool n >= 250, same floors
  G8a >= 25 frames with far-car occl >= 0.50 (both boxes present)
  G8b NEAR-car colour dominance in the intersection ROI, median >= 0.40
  G8c occluder (NEAR car) intact during occlusion: frag median >= 0.95,
      frac(<0.90) <= 0.10
  G9  crossing as designed: recorded v3_screen.pass AND recorded GT-GT IoU
      max >= 0.20 with argmax <= 125 and tail (f>=150) <= 0.15 AND the
      recorded z-order matches the pinned near flag (nearer-frac >= 0.95)
  G10 staleness REALIZED in the recorded gt (the whole point of bank v3):
      for BOTH cars, IoU(bbox[150], bbox[260]) <= 0.20 and every frame in
      [150, 299] visible with area >= 150 px^2

Cross-run gates: G4a byte-determinism (s002 vs s002_R, s007 vs s007_R: gt
identical after dropping t_sim_ns, frame mean|diff| <= 2.0, frac(>8) <= 0.01),
G4b min pairwise authored divergence over the 28 seeds >= 1.0 m + recorded-f0
faithfulness, G7 screen pin (sg.v3_bank() reproduces V3_BANK_PINNED), G11 set
diversity ON THE VALID CLIPS (>= 10 near-white AND >= 10 near-blue, recorded
crossing-peak span >= 30 frames).

Select-mode thresholds: SEP_MARGIN = 7 cells; health floor = ceil(0.8 *
n_cells) per contract; > 2 select INFRA cells = NO [infra]; INFRA counts FAIL
for both contracts. The visual gate V can only DOWNGRADE either mode.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location("scenegen", REPO / "runners" / "scenegen.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)
import cv2  # noqa: E402

BANK_SEEDS = list(sg.V3_BANK_PINNED)                      # 28 pinned seeds
BANK_RUNS = [(f"s{s:03d}", s) for s in BANK_SEEDS]
G4A_PAIRS = [("s002", "s002_R", 2), ("s007", "s007_R", 7)]  # 1st admit per class
N_FRAMES = 300
PROMPT_F = 150
STALE_F = PROMPT_F + sg.V3_LAG_FRAMES                     # 260
N_CLEAR_FLOOR = 40        # P5.12-recalibrated far-car clear-pool floor
NDOM_FLOOR = 0.40         # P5.12-recalibrated occluder-dominance floor
VALID_FLOOR = 25          # bank clips that must pass everything (n >= 25 rule)
INFRA_CAP_BANK = 3
SEP_MARGIN = 7            # RQ-P5.17a separation, in cells
INFRA_CAP_SELECT = 2
LEGS = ("white", "blue")

_NEAR = {}


def near_flag(seed: int) -> str:
    if seed not in _NEAR:
        _NEAR[seed] = sg.author_scenario(seed, N_FRAMES, profile="v3")["params"]["near"]
    return _NEAR[seed]


def _load(d: Path):
    rj = d / "results.json"
    if not rj.exists():
        return None, None
    recs = [json.loads(l) for l in open(d / "gt.jsonl")]
    return json.load(open(rj)), recs


# ------------------------------------------------------------- build grading
def grade_run(runs_root: Path, run: str, seed: int):
    d = runs_root / run
    r, recs = _load(d)
    if r is None:
        return None
    near = near_flag(seed)
    near_id = 0 if near == "white" else 1        # objs[0] = white, objs[1] = blue
    far_id = 1 - near_id
    far_col = "white" if far_id == 0 else "blue"

    g0 = (len(recs) == N_FRAMES and
          r["g0_retries_pose"] + r["g0_retries_step"] + r["g0_response_lost"] <= 15)
    g1 = (r["g1_dead_frames"] == 0 and r["g1_identical_consecutive"] == 0
          and r["g1_stamp_steps_ok"])
    g3 = r["g3_both_visible_frac"] >= 0.80
    g5 = r["fps_wall"] >= 0.5

    far_pur_clear, far_frag_clear = [], []
    near_pur_all, near_frag_all = [], []
    occ_frames, near_frag_occ = [], []
    nearer_hits, nearer_n = 0, 0
    for rec in recs:
        fo, no = rec["objs"][far_id], rec["objs"][near_id]
        occ = fo.get("occl", 0.0)
        if fo["bbox"] is not None and occ <= 0.05:
            if "purity" in fo:
                far_pur_clear.append(fo["purity"])
            if "frag" in fo:
                far_frag_clear.append(fo["frag"])
        if no["bbox"] is not None:
            if "purity" in no:
                near_pur_all.append(no["purity"])
            if "frag" in no:
                near_frag_all.append(no["frag"])
        if occ >= 0.50 and fo["bbox"] is not None and no["bbox"] is not None:
            occ_frames.append((rec["f"], fo["bbox"], no["bbox"]))
            if "frag" in no:
                near_frag_occ.append(no["frag"])
        if fo["bbox"] is not None and no["bbox"] is not None:
            nearer_n += 1
            nearer_hits += bool(no.get("nearer"))

    bg = r["g2_bg_purity_median"]
    f_pur = float(np.median(far_pur_clear)) if far_pur_clear else None
    n_pur = float(np.median(near_pur_all)) if near_pur_all else None
    g2c = (f_pur is not None and f_pur >= 0.30 and f_pur >= 4 * (bg[str(far_id)] or 0.0)
           and n_pur is not None and n_pur >= 0.30
           and n_pur >= 4 * (bg[str(near_id)] or 0.0))
    ff, nf = np.array(far_frag_clear), np.array(near_frag_all)
    g6c = (len(ff) >= N_CLEAR_FLOOR and float(np.percentile(ff, 10)) >= 0.95
           and float(np.mean(ff < 0.90)) <= 0.02
           and len(nf) >= 250 and float(np.percentile(nf, 10)) >= 0.95
           and float(np.mean(nf < 0.90)) <= 0.02)

    g8a = len(occ_frames) >= 25
    doms = []
    for f, fb, nb in occ_frames:
        img = cv2.imread(str(d / "frames" / f"{f:04d}.png"))
        if img is None:
            break
        x1, y1 = int(max(fb[0], nb[0])), int(max(fb[1], nb[1]))
        x2, y2 = int(min(fb[2], nb[2])), int(min(fb[3], nb[3]))
        if x2 <= x1 or y2 <= y1:
            continue
        roi = img[y1:y2, x1:x2]
        n_near = int(sg.color_mask(roi, near).sum())
        n_far = int(sg.color_mask(roi, far_col).sum())
        doms.append(n_near / max(n_near + n_far, 1))
    g8b = len(doms) == len(occ_frames) > 0 and float(np.median(doms)) >= NDOM_FLOOR
    nfo = np.array(near_frag_occ)
    g8c = (len(nfo) > 0 and float(np.median(nfo)) >= 0.95
           and float(np.mean(nfo < 0.90)) <= 0.10)
    g8 = g8a and g8b and g8c
    ndom = round(float(np.median(doms)), 3) if doms else None

    iou_rec = np.array([sg._iou2d(rec["objs"][0]["bbox"], rec["objs"][1]["bbox"])
                        for rec in recs])
    g9 = (bool(r.get("v3_screen", {}).get("pass"))
          and float(iou_rec.max()) >= 0.20
          and int(iou_rec.argmax()) <= PROMPT_F - 25
          and float(iou_rec[PROMPT_F:].max()) <= 0.15
          and nearer_n > 0 and nearer_hits / nearer_n >= 0.95)

    stale = {0: None, 1: None}
    g10 = len(recs) == N_FRAMES        # short recording cannot realize staleness
    if g10:
        for oid in (0, 1):
            b0 = recs[PROMPT_F]["objs"][oid]["bbox"]
            b1 = recs[STALE_F]["objs"][oid]["bbox"]
            s = sg._iou2d(b0, b1) if (b0 is not None and b1 is not None) else None
            stale[oid] = None if s is None else round(float(s), 3)
            g10 &= s is not None and s <= 0.20
            g10 &= all(rec["objs"][oid]["visible"] and rec["objs"][oid]["area"] >= 150
                       for rec in recs[PROMPT_F:])

    gates = [g0, g1, g2c, g3, g5, g6c, g8, g9, g10]
    return {"run": run, "seed": seed, "near": near,
            "g0": g0, "g1": g1, "g2c": g2c, "g3": g3, "g5": g5, "g6c": g6c,
            "g8": g8, "g9": g9, "g10": g10,
            "fps": r["fps_wall"], "pur": (f_pur, n_pur),
            "ffrag_p10": round(float(np.percentile(ff, 10)), 3) if len(ff) else None,
            "n_clear": len(ff), "n_occ": len(occ_frames), "ndom": ndom,
            "xpeak_rec": int(iou_rec.argmax()),
            "stale": (stale[0], stale[1]),
            "ok": all(gates)}


def canonical_gt(path: Path) -> str:
    out = []
    for line in open(path):
        r = json.loads(line)
        r.pop("t_sim_ns", None)
        out.append(json.dumps(r, sort_keys=True))
    return "\n".join(out)


def g4a_pair(a: Path, d: Path):
    if not (a / "results.json").exists() or not (d / "results.json").exists():
        return None, "missing runs"
    ident = canonical_gt(a / "gt.jsonl") == canonical_gt(d / "gt.jsonl")
    means, fracs = [], []
    for i in range(N_FRAMES):
        fa = cv2.imread(str(a / "frames" / f"{i:04d}.png"))
        fd = cv2.imread(str(d / "frames" / f"{i:04d}.png"))
        if fa is None or fd is None:
            return None, f"missing frame {i}"
        diff = np.abs(fa.astype(np.int16) - fd.astype(np.int16))
        means.append(diff.mean())
        fracs.append((diff > 8).mean())
    mean_abs, frac8 = float(np.mean(means)), float(np.mean(fracs))
    ok = ident and mean_abs <= 2.0 and frac8 <= 0.01
    return ok, (f"gt_identical={ident} frame_mean_absdiff={round(mean_abs, 4)}"
                f" (<= 2.0) frac_gt8={round(frac8, 5)} (<= 0.01)")


def g4b(runs_root: Path):
    scs = {s: sg.author_scenario(s, N_FRAMES, profile="v3") for s in BANK_SEEDS}

    def div(A, B):
        dt = np.linalg.norm(A["target"]["xy"] - B["target"]["xy"], axis=1).mean()
        dd = np.linalg.norm(A["distractor"]["xy"] - B["distractor"]["xy"], axis=1).mean()
        dc = np.linalg.norm(A["cam_pos"] - B["cam_pos"], axis=1).mean()
        return (dt + dd + dc) / 3

    dmin, argmin = 1e9, None
    for a, b in itertools.combinations(BANK_SEEDS, 2):
        v = div(scs[a], scs[b])
        if v < dmin:
            dmin, argmin = v, (a, b)
    faithful, checked = True, 0
    for run, seed in BANK_RUNS + [(r, s) for _, r, s in G4A_PAIRS]:
        gt = runs_root / run / "gt.jsonl"
        if not gt.exists():
            continue
        r0 = json.loads(open(gt).readline())
        for oid, role in ((0, "target"), (1, "distractor")):
            want = scs[seed][role]["xy"][0]
            got = np.array(r0["objs"][oid]["pos"][:2])
            if np.abs(want - got).max() > 1e-3:
                faithful = False
        checked += 1
    ok = dmin >= 1.0 and faithful and checked > 0
    return ok, (f"min pairwise scenario divergence {dmin:.2f} m (>= 1.0) at "
                f"pair {argmin}; recorded-f0 faithful={faithful} over {checked} runs")


def g7():
    admitted, _ = sg.v3_bank()
    ok = admitted == BANK_SEEDS
    return ok, (f"v3 screen admission {'reproduces' if ok else 'DIVERGES from'} "
                f"the pinned bank: {admitted}")


def g11(valid_rows):
    nw = sum(1 for g in valid_rows if g["near"] == "white")
    nb = len(valid_rows) - nw
    pk = [g["xpeak_rec"] for g in valid_rows]
    span = (max(pk) - min(pk)) if pk else 0
    ok = nw >= 10 and nb >= 10 and span >= 30
    return ok, (f"valid-set diversity: near-white {nw} (>= 10), near-blue {nb} "
                f"(>= 10), recorded peak span {span} (>= 30)")


def build(runs_root: Path) -> int:
    print(f"{'run':8s} {'seed':4s} {'near':5s} G0 G1 G2c G3 G5 G6c G8 G9 G10 "
          f"fps    purF/N        ffragp10 nclr nocc ndom   xpeak staleT/D")
    rows, missing = [], []
    for run, seed in BANK_RUNS:
        g = grade_run(runs_root, run, seed)
        if g is None:
            infra = (runs_root / f"{run}.INFRA").exists()
            missing.append((run, "INFRA" if infra else "MISSING"))
            print(f"{run:8s} {seed:<4d} "
                  f"{'-- INFRA --' if infra else '-- MISSING results.json --'}")
            continue
        rows.append(g)
        print(f"{g['run']:8s} {g['seed']:<4d} {g['near']:5s} {int(g['g0'])}  "
              f"{int(g['g1'])}  {int(g['g2c'])}   {int(g['g3'])}  {int(g['g5'])}  "
              f"{int(g['g6c'])}   {int(g['g8'])}  {int(g['g9'])}  {int(g['g10'])}   "
              f"{g['fps']:<6.2f} {(g['pur'][0] or 0):.3f}/{(g['pur'][1] or 0):.3f}   "
              f"{g['ffrag_p10']}    {g['n_clear']:<4d} {g['n_occ']:<4d} "
              f"{str(g['ndom']):<6s} {g['xpeak_rec']:<5d} "
              f"{g['stale'][0]}/{g['stale'][1]}")

    results = {}
    for a_run, d_run, seedp in G4A_PAIRS:
        ok, msg = g4a_pair(runs_root / a_run, runs_root / d_run)
        print(f"G4a determinism {a_run} vs {d_run} (seed {seedp}): {msg} -> "
              f"{'PASS' if ok else 'FAIL' if ok is not None else 'INCOMPLETE'}")
        results[f"g4a_{a_run}"] = ok
    b_ok, b_msg = g4b(runs_root)
    print(f"G4b seed diversity (28 seeds, v3): {b_msg} -> {'PASS' if b_ok else 'FAIL'}")
    s_ok, s_msg = g7()
    print(f"G7 screen pin: {s_msg} -> {'PASS' if s_ok else 'FAIL'}")

    valid_rows = [g for g in rows if g["ok"]]
    d_ok, d_msg = g11(valid_rows)
    print(f"G11 {d_msg} -> {'PASS' if d_ok else 'FAIL'}")

    bank_missing = [m for m in missing if m[1] == "MISSING"]
    bank_infra = [m for m in missing if m[1] == "INFRA"]
    if bank_missing or any(v is None for v in results.values()):
        print(f"P5.17 BUILD: INCOMPLETE (missing: {missing}; g4a: {results})")
        return 2

    valid = [g["run"] for g in valid_rows]
    build_pass = (len(valid) >= VALID_FLOOR and all(results.values())
                  and b_ok and s_ok and d_ok
                  and len(bank_infra) <= INFRA_CAP_BANK)
    out = {"build_pass": bool(build_pass),
           "valid": valid,
           "near": {g["run"]: g["near"] for g in valid_rows},
           "xpeak_rec": {g["run"]: g["xpeak_rec"] for g in valid_rows},
           "n_valid": len(valid), "n_infra": len(bank_infra),
           "gates": {"g4a": {k: bool(v) for k, v in results.items()},
                     "g4b": bool(b_ok), "g7": bool(s_ok), "g11": bool(d_ok)}}
    # written NEXT TO the select cells (runs/), where select_p517.load_clips
    # and the select verdict read it -- not inside runs/bank/
    (runs_root.parent / "bank_valid.json").write_text(json.dumps(out, indent=1))
    why = []
    if len(valid) < VALID_FLOOR:
        why.append(f"valid {len(valid)} < {VALID_FLOOR}")
    if not all(results.values()):
        why.append("G4a")
    if not b_ok:
        why.append("G4b")
    if not s_ok:
        why.append("G7")
    if not d_ok:
        why.append("G11")
    if len(bank_infra) > INFRA_CAP_BANK:
        why.append(f"infra {len(bank_infra)} > {INFRA_CAP_BANK}")
    print(f"P5.17 BUILD: {'PASS' if build_pass else 'FAIL'}"
          + (f" [{'; '.join(why)}]" if why else "")
          + f" -- {len(valid)}/28 clips valid, bank_valid.json written"
          + " (PASS iff >= 25 valid AND G4a x2 AND G4b AND G7 AND G11 AND"
            " <= 3 infra; the visual gate V can only downgrade)")
    return 0 if build_pass else 1


# ------------------------------------------------------------- select verdict
def decide(dd_total, rg_total, n_cells):
    """Pure, testable. Returns (overall_yes, branch_tag)."""
    floor = math.ceil(0.8 * n_cells)
    if abs(dd_total - rg_total) >= SEP_MARGIN:
        return True, "1" if dd_total > rg_total else "2"
    return False, "3" if (dd_total >= floor and rg_total >= floor) else "4"


def collect(runs: Path, clips):
    cells, missing = {}, []
    for clip in clips:
        for leg in LEGS:
            f = runs / f"{clip}_{leg}" / "results.json"
            if f.exists():
                cells[f"{clip}_{leg}"] = json.loads(f.read_text())
            elif (runs / f"{clip}_{leg}.INFRA").exists():
                cells[f"{clip}_{leg}"] = None
            else:
                missing.append(f"{clip}_{leg}")
    return cells, missing


def select_verdict(runs: Path) -> int:
    bv = json.loads((runs / "bank_valid.json").read_text())
    assert bv["build_pass"], "bank build did not PASS -- no select verdict"
    clips, near = bv["valid"], bv["near"]
    n_cells = 2 * len(clips)
    floor = math.ceil(0.8 * n_cells)
    cells, missing = collect(runs, clips)
    if missing:
        print(f"INCOMPLETE: {len(missing)} cells missing (no results.json, "
              f"no .INFRA marker): {', '.join(missing)}")
        return 2

    print(f"{'cell':<12}{'role':<6}{'DD':<6}{'dd_class':<14}{'ddIoU':<7}{'RG':<6}"
          f"{'rg_class':<16}{'vlm_on':<8}{'acq_s':<7}{'delivF':<8}"
          f"{'ddCov':<7}{'rgCov':<7}")
    dd_total = rg_total = 0
    dd_role = {"near": 0, "far": 0}       # DD passes by named-car z-order role
    n_role = {"near": 0, "far": 0}
    infra = [k for k, v in cells.items() if v is None]
    dd_classes, rg_classes = {}, {}
    for key in sorted(cells):
        r = cells[key]
        clip, leg = key.rsplit("_", 1)
        role = "near" if near[clip] == leg else "far"
        if r is None:
            print(f"{key:<12}{role:<6}{'INFRA':<6}")
            continue
        dd, rg = r["dd"], r["rg"]
        n_role[role] += 1
        dd_total += bool(dd["pass"])
        rg_total += bool(rg["pass"])
        dd_role[role] += bool(dd["pass"])
        if not dd["pass"]:
            dd_classes[dd["fail_class"]] = dd_classes.get(dd["fail_class"], 0) + 1
        if not rg["pass"]:
            rg_classes[rg["fail_class"]] = rg_classes.get(rg["fail_class"], 0) + 1
        print(f"{key:<12}{role:<6}{('PASS' if dd['pass'] else 'FAIL'):<6}"
              f"{str(dd['fail_class']):<14}{dd['iou_named']:<7.3f}"
              f"{('PASS' if rg['pass'] else 'FAIL'):<6}"
              f"{str(rg['fail_class']):<16}{str(rg.get('vlm_on')):<8}"
              f"{rg['acquire_s']:<7.2f}{rg['deliver_frame']:<8}"
              f"{r['cov_dd']['frac_lock']:<7.3f}{r['cov_rg']['frac_lock']:<7.3f}")

    print(f"\nDD_total {dd_total}/{n_cells}  RG_total {rg_total}/{n_cells}  "
          f"(health floor {floor} = ceil(0.8*{n_cells}))")
    print(f"DD by named-car role: far {dd_role['far']}/{n_role['far']}, "
          f"near {dd_role['near']}/{n_role['near']}")
    print(f"DD fail classes: {dd_classes or '{}'}  RG fail classes: {rg_classes or '{}'}")
    if infra:
        print(f"INFRA cells ({len(infra)}, count as FAIL for both contracts): {infra}")
    if len(infra) > INFRA_CAP_SELECT:
        print(f"VERDICT: NO [infra] -- more than {INFRA_CAP_SELECT} infra-lost "
              f"cells (pre-registered cap)")
        return 1

    overall, branch = decide(dd_total, rg_total, n_cells)
    asym = (n_role["far"] - dd_role["far"]) - (n_role["near"] - dd_role["near"])
    print(f"\nRQ-P5.17a (|DD_total - RG_total| >= {SEP_MARGIN} of {n_cells}): "
          f"{'YES' if overall else 'NO'} "
          f"(DD {dd_total} vs RG {rg_total}, |diff| {abs(dd_total - rg_total)})")
    print(f"RQ-P5.17b (DIAGNOSTIC, non-gating; far-leg DD fails minus near-leg "
          f"DD fails >= 3): {'YES' if asym >= 3 else 'NO'} (asym {asym}) -- YES "
          f"means the occlusion aftermath, not generic drift, breaks the carry")
    print(f"OVERALL RQ-P5.17: {'YES' if overall and dd_total > rg_total else 'NO'} "
          f"(YES iff branch 1; the visual gate V can only downgrade)")

    print("\nPre-registered interpretation branches (the matching one applies):")
    marks = [
        ("1", branch == "1",
         "DD - RG >= 7: the lag-stress bank reproduces P5.14's real-video "
         "delivery-contract separation in sim at n >= 25 -- the staleness "
         "mechanism (target moves during the ~4.4 s re-ground lag) is "
         "sufficient to separate the contracts, and bank v3 is a working "
         "discriminating test-bed for select levers."),
        ("2", branch == "2",
         "RG - DD >= 7: prompt-time re-grounding WINS on lag-stress scenes -- "
         "the carry through the crossing is the weak link and the VLM repairs "
         "it. Inverts the P5.14 delivery-contract conclusion for occluded "
         "targets; next lever = hybrid carry + re-ground confirmation."),
        ("3", branch == "3",
         "No separation, both contracts >= ceil(0.8*n): third consecutive sim "
         "contract tie, now at proper n WITH realized staleness and designed "
         "crossings. Pre-registered conclusion: sim-select discrimination is "
         "CLOSED -- the DD advantage seen on real video (P5.14) is attributable "
         "to real-imagery VLM fragility that clean renders cannot reproduce; "
         "further select levers must be tested on real video."),
        ("4", branch == "4",
         "No separation, at least one contract < ceil(0.8*n): the stack fails "
         "upstream of the delivery contract (carry loss on both, or VLM "
         "failure on both); diagnose the stack before re-asking the contract "
         "question."),
    ]
    for tag, hit, txt in marks:
        print(f"  [{'X' if hit else ' '}] branch {tag}: {txt}")
    return 0


# ------------------------------------------------------------------ selfcheck
def _synth_run(root: Path, run: str, seed: int) -> None:
    """Synthetic v3 record run from the AUTHORED scenario: flat-grey frames
    with the two car boxes painted in z-order, gt.jsonl with the same
    provenance fields record() writes, results.json with clean aggregates and
    the real v3_screen. Passes every build gate by construction."""
    sc = sg.author_scenario(seed, N_FRAMES, profile="v3")
    boxes = sg.scenario_boxes(sc)
    near = sc["params"]["near"]
    near_id = 0 if near == "white" else 1
    d = root / run
    (d / "frames").mkdir(parents=True)
    draw = {"white": (235, 235, 235), "blue": (200, 60, 20)}
    roles = ("target", "distractor")
    colors = ("white", "blue")
    both_vis = 0
    with open(d / "gt.jsonl", "w") as gtf:
        for f in range(N_FRAMES):
            img = np.full((720, 1280, 3), 60, np.uint8)
            order = [1 - near_id, near_id]          # far first, near on top
            for oid in order:
                b = boxes[roles[oid]][f]
                if b is not None:
                    cv2.rectangle(img, (int(b[0]), int(b[1])),
                                  (int(b[2]), int(b[3])), draw[colors[oid]], -1)
            cv2.imwrite(str(d / "frames" / f"{f:04d}.png"), img)
            objs = []
            for oid in (0, 1):
                b = boxes[roles[oid]][f]
                xy = sc[roles[oid]]["xy"][f]
                rec = {"id": oid, "name": f"car_{colors[oid]}",
                       "color": colors[oid],
                       "phrase": sg.CAR_COLORS[colors[oid]][1],
                       "pos": [round(float(xy[0]), 4), round(float(xy[1]), 4),
                               sg.CAR_Z],
                       "bbox": None if b is None else [round(v, 1) for v in b],
                       "area": 0.0 if b is None else
                       round((b[2] - b[0]) * (b[3] - b[1]), 1),
                       "visible": b is not None}
                if b is not None:
                    rec.update(purity=0.9, bg_purity=0.01, frag=1.0, npx=500)
                objs.append(rec)
            for a, b_ in ((0, 1), (1, 0)):
                objs[a]["nearer"] = a == near_id
                objs[a]["occl"] = round(
                    sg._overlap_frac(objs[a]["bbox"], objs[b_]["bbox"])
                    if a != near_id and objs[a]["bbox"] and objs[b_]["bbox"]
                    else 0.0, 4)
            both_vis += (objs[0]["visible"] and objs[0]["area"] >= 150
                         and objs[1]["visible"] and objs[1]["area"] >= 150)
            gtf.write(json.dumps({"f": f, "t_sim_ns": f * 40_000_000,
                                  "objs": objs}) + "\n")
    (d / "results.json").write_text(json.dumps({
        "g0_retries_pose": 0, "g0_retries_step": 0, "g0_response_lost": 0,
        "g1_dead_frames": 0, "g1_identical_consecutive": 0,
        "g1_stamp_steps_ok": True,
        "g2_bg_purity_median": {"0": 0.01, "1": 0.01},
        "g3_both_visible_frac": round(both_vis / N_FRAMES, 4),
        "fps_wall": 8.0, "v3_screen": sg.v3_crossing_screen(sc)}))


def selfcheck() -> None:
    import shutil
    import tempfile

    # pure decision table (n_cells 56 -> floor 45)
    assert decide(50, 40, 56) == (True, "1")
    assert decide(40, 50, 56) == (True, "2")
    assert decide(50, 50, 56) == (False, "3")
    assert decide(50, 44, 56) == (False, "4")    # diff 6 < 7, RG under floor
    assert decide(51, 44, 56) == (True, "1")     # diff 7 == margin
    assert decide(45, 45, 56) == (False, "3")    # both exactly at floor
    assert decide(30, 28, 56) == (False, "4")
    print("--- selfcheck: decide() branch table OK")

    with tempfile.TemporaryDirectory() as td:
        runs = Path(td)
        _synth_run(runs, "s002", 2)
        g = grade_run(runs, "s002", 2)
        assert g is not None and g["near"] == "white", g
        for k in ("g0", "g1", "g2c", "g3", "g5", "g6c", "g8", "g9", "g10"):
            assert g[k], (k, g)
        assert g["ok"] and g["n_occ"] >= 25 and g["n_clear"] >= N_CLEAR_FLOOR, g
        assert g["ndom"] >= NDOM_FLOOR, g
        print(f"--- selfcheck: synthetic s002 passes all build gates "
              f"(ndom={g['ndom']}, stale={g['stale']})")

        # negative: truncated gt -> G0
        neg = runs / "neg0"
        shutil.copytree(runs / "s002", neg)
        lines = open(neg / "gt.jsonl").readlines()
        (neg / "gt.jsonl").write_text("".join(lines[:200]))
        gn = grade_run(runs, "neg0", 2)
        assert gn is not None and not gn["g0"] and not gn["ok"]
        print("--- selfcheck: truncated gt.jsonl fails G0")

        # negative: doctored v3_screen -> G9
        neg = runs / "neg9"
        shutil.copytree(runs / "s002", neg)
        r = json.loads((neg / "results.json").read_text())
        r["v3_screen"]["pass"] = False
        (neg / "results.json").write_text(json.dumps(r))
        gn = grade_run(runs, "neg9", 2)
        assert gn is not None and not gn["g9"] and not gn["ok"]
        print("--- selfcheck: doctored v3_screen fails G9")

        # negative: flipped z-order provenance -> G9 (nearer-frac)
        neg = runs / "negz"
        shutil.copytree(runs / "s002", neg)
        recs = [json.loads(l) for l in open(neg / "gt.jsonl")]
        for rec in recs:
            for o in rec["objs"]:
                o["nearer"] = not o["nearer"]
        (neg / "gt.jsonl").write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs))
        gn = grade_run(runs, "negz", 2)
        assert gn is not None and not gn["g9"] and not gn["ok"]
        print("--- selfcheck: flipped z-order provenance fails G9")

        # negative: staleness NOT realized (freeze f260 boxes at f150) -> G10
        neg = runs / "neg10"
        shutil.copytree(runs / "s002", neg)
        recs = [json.loads(l) for l in open(neg / "gt.jsonl")]
        for oid in (0, 1):
            recs[STALE_F]["objs"][oid]["bbox"] = recs[PROMPT_F]["objs"][oid]["bbox"]
        (neg / "gt.jsonl").write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs))
        gn = grade_run(runs, "neg10", 2)
        assert gn is not None and not gn["g10"] and not gn["ok"]
        print("--- selfcheck: frozen post-prompt boxes fail G10")

        # negative: fragmented far-car clear frames -> G6c
        neg = runs / "neg6"
        shutil.copytree(runs / "s002", neg)
        recs = [json.loads(l) for l in open(neg / "gt.jsonl")]
        doctored = 0
        for rec in recs:
            fo = rec["objs"][1]                      # far car of s002 = blue
            if doctored < 10 and fo["bbox"] is not None \
                    and fo.get("occl", 0.0) <= 0.05 and "frag" in fo:
                fo["frag"] = 0.5
                doctored += 1
        assert doctored == 10
        (neg / "gt.jsonl").write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs))
        gn = grade_run(runs, "neg6", 2)
        assert gn is not None and not gn["g6c"] and not gn["ok"]
        print("--- selfcheck: doctored clear-frame frag fails G6c")

        # G4a: identical copy passes, doctored frame fails
        shutil.copytree(runs / "s002", runs / "s002_R")
        ok, msg = g4a_pair(runs / "s002", runs / "s002_R")
        assert ok, msg
        img = cv2.imread(str(runs / "s002_R" / "frames" / "0150.png"))
        img[:100, :100] = 255
        cv2.imwrite(str(runs / "s002_R" / "frames" / "0150.png"), img)
        recs = [json.loads(l) for l in open(runs / "s002_R" / "gt.jsonl")]
        recs[0]["objs"][0]["pos"][0] += 1.0
        (runs / "s002_R" / "gt.jsonl").write_text(
            "".join(json.dumps(rec) + "\n" for rec in recs))
        ok, msg = g4a_pair(runs / "s002", runs / "s002_R")
        assert not ok, msg
        print("--- selfcheck: G4a passes identical pair, fails doctored pair")

        # G4b faithfulness has teeth on the doctored run dir too
        b_ok, b_msg = g4b(runs)
        assert not b_ok and "faithful=False" in b_msg, b_msg
        shutil.rmtree(runs / "s002_R")
        b_ok, b_msg = g4b(runs)
        assert b_ok, b_msg
        print(f"--- selfcheck: G4b OK ({b_msg.split(';')[0]})")

    # G7 pin must hold offline
    s_ok, s_msg = g7()
    assert s_ok, s_msg
    print(f"--- selfcheck: {s_msg}")

    # G11 teeth
    rows = ([{"near": "white", "xpeak_rec": 50}] * 13
            + [{"near": "blue", "xpeak_rec": 100}] * 13)
    ok, _ = g11(rows)
    assert ok
    ok, _ = g11([{"near": "white", "xpeak_rec": 50}] * 26)
    assert not ok
    ok, _ = g11(rows[:13] + [{"near": "blue", "xpeak_rec": 55}] * 13)
    assert not ok                                    # span 5 < 30
    print("--- selfcheck: G11 teeth OK")
    print("verdict_p517 selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    elif "--build" in sys.argv:
        sys.exit(build(HERE / "runs" / "bank"))
    else:
        sys.exit(select_verdict(HERE / "runs"))
