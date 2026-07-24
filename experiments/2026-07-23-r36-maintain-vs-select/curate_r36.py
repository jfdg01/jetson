#!/usr/bin/env python3
"""R-36 SWAP-hard clip CANDIDATE curation (Part V paired maintain-vs-select).

WHAT THIS DOES
--------------
R-36 needs >= 12 NEW distinct UAV123 base clips (README REACHABILITY note): the
committed SWAP data is b=3, c=0, n=13 -> exact McNemar p=0.25, three discordant
pairs short of alpha. This script PROPOSES candidate clips from the SWAP-hard
families so a human can lock the bank by eye. It:

  1. enumerates the UAV123 sequences, STRIPS the P5.18 13-clip bank (any onset /
     `_s` / `_<n>` segment of an already-banked base capture is excluded), then
  2. classifies each remaining distinct base sequence into ONE SWAP-hard family
     with a simple, documented GT-only heuristic (see `classify_family`), and
  3. emits a CANDIDATE manifest (jsonl: clip, family, why, suggested prompt
     frame) + candidate cells in the exact `DSC_SWAP_<clip>_<f0>` scene schema
     that `select_p56.py` / `verdict_p518.py` already consume.

This is a PROPOSER, not a bank-locker. Captions and the two distractor boxes
per cell are left as explicit TODO placeholders: the >= 2-same-class-near-target
check and every box are hand-annotations that require look-at-it on the main
thread (curate_p518.py zoom / scene), per the project "look at it" rule. Final
selection = one hard SWAP scene per distinct clip, human-verified.

WHAT IT REUSES
--------------
  - experiments/2026-07-20-n25-select/curate_p518.py  load_gt (:49), clip_len
    (:68) for GT + distractor_gt loading; verify (:149) is the scene-set
    validator whose GT-viability asserts `verify_candidates` mirrors for the
    pre-annotation subset (late-entry cells deliberately differ: the target may
    be NaN at ds, which curate_p518.verify forbids -- documented below).
  - the cell schema is exactly the scenes_p518.json / select_p56 scene dict:
    clip, f0, t_p, target_caption, distractor_caption, distractor_box,
    distractor_gt_prompt, gating, note (REQUIRED_CELL_KEYS).
  - downstream: select_p56.py leg_pass_p56 (:212) scores the built cells;
    verdict_p518.py + grounding/stats.py mcnemar/deflate render the verdict.

MACHINE OF EVERY NUMBER
-----------------------
Every number this script emits (bbox short-side px, normalized center speed,
absence-run length, suggested f0) is PURE GEOMETRY read from the UAV123 GT text
files, computed on the RTX-3090 host CPU -- no model, no GPU, no Jetson, no
CARLA. The downstream WSEL/SWAP grounding it feeds runs the deployed q8_0 VLM on
the Jetson Orin (15 W + jetson_clocks) via grounding.eval.backends.JetsonBackend
inside select_p56.py; the SAM2 carry runs on the 3090 (E1 verified on-device
mask parity 1.000; timing is not claimed on-device). This curation touches
neither.

HOW TO RUN (deferred -- these are the REAL runs, on the main thread)
--------------------------------------------------------------------
  # this script: pure-logic self-test (no dataset, no GPU) -- runs anywhere
  .venv-ft/bin/python experiments/2026-07-23-r36-maintain-vs-select/curate_r36.py --selftest

  # propose + GT-verify candidates into a manifest for human review (reads UAV123)
  .venv-ft/bin/python experiments/2026-07-23-r36-maintain-vs-select/curate_r36.py \
      --families late-entry,carry-drift,distractor --n-new 17 --verify --out runs/r36/bank

  # (human) annotate captions + distractor boxes on 10-px zooms, lock scenes_r36.json,
  # then the frozen matrix + verdict (VLM on Jetson, carry on 3090):
  .venv-ft/bin/python experiments/2026-07-20-n25-select/select_p56.py \
      --matrix .../scenes_r36.json --arms wsel,swap --out runs/r36
  .venv-ft/bin/python experiments/2026-07-20-n25-select/verdict_p518.py --runs runs/r36
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P518 = REPO / "experiments" / "2026-07-20-n25-select"
DATA = REPO / "experiments" / "2026-07-03-real-video-replay" / "data" / "UAV123"

# --- harness geometry (mirrors curate_p518 / select_p56 frame arithmetic) --- #
FPS = 30.0
T_P = 8.0
DS_OFFSET = 150               # discovery start = f0 - 150
PROMPT_OFF = round(T_P * FPS)  # prompt frame = f0 + 240 (t_p = 8 s)
COVER_F = 300                 # 10 s coverage window after the prompt

# --- classifier thresholds (documented; pure GT geometry, 3090 host CPU) ---- #
LATE_MIN = 60      # frames: a NaN run >= 60 (>= 2 s) FOLLOWED by a valid frame
                   # -> the target is absent then (re)enters == late-entry.
SMALL_PX = 45      # median bbox short-side < 45 px -> "small" target (carry leaks).
FAST_NORM = 0.15   # median per-frame center displacement > 0.15 * bbox short-side
                   # -> "fast" target (carry lags). small OR fast == carry-drift.

# classes that plausibly host >= 2 same-class instances in a UAV123 aerial scene
# (traffic / crowds / boat-board clusters). Singleton-ish classes (building, uav,
# bird) are NOT assigned distractor-confusion -- they fall through to "not SWAP-hard".
CROWD_CLASSES = {"car", "person", "bike", "truck", "boat", "group", "wakeboard"}

FAMILIES = ("late-entry", "carry-drift", "distractor-confusion")
# CLI shorthands accepted by --families
FAMILY_ALIASES = {"distractor": "distractor-confusion",
                  "late": "late-entry", "drift": "carry-drift"}

# the scene dict keys select_p56.run_leg_p56 / verdict_p518 consume verbatim
REQUIRED_CELL_KEYS = frozenset({
    "clip", "f0", "t_p", "target_caption", "distractor_caption",
    "distractor_box", "distractor_gt_prompt", "gating", "note"})


# --------------------------------------------------------------------------- #
# P5.18 exclusion-set logic (pure string parsing over run-dir cell names)
# --------------------------------------------------------------------------- #
def parse_cell(name: str) -> tuple[str, str, int]:
    """`DSC_SWAP_wakeboard8_150` -> ('SWAP', 'wakeboard8', 150). The trailing
    `_<int>` is f0; everything before it (after the leg) is the sequence name,
    which may itself carry a segment/onset suffix (e.g. `car6_1`)."""
    assert name.startswith("DSC_"), name
    leg, rest = name[4:].split("_", 1)     # SWAP , wakeboard8_150
    seq, f0 = rest.rsplit("_", 1)          # wakeboard8 , 150
    return leg, seq, int(f0)


def base_capture(seq: str) -> str:
    """UAV123 base capture (README unit): strip a trailing `_s` (short variant)
    or `_<n>` (split segment). `car6_1`->`car6`, `car1_s`->`car1`, `car10`->
    `car10` (no separator, the 10 is part of the name), `bird1_3`->`bird1`."""
    m = re.match(r"^([a-z]+\d+)(?:_(?:s|\d+))?$", seq)
    return m.group(1) if m else seq


def seq_class(seq: str) -> str:
    """Leading alpha class prefix: `car9`->`car`, `wakeboard8`->`wakeboard`."""
    m = re.match(r"^[a-z]+", seq)
    return m.group(0) if m else seq


def banked_base_clips(cell_names) -> set[str]:
    """Distinct P5.18 base captures to EXCLUDE, from the run-dir cell names."""
    bases: set[str] = set()
    for n in cell_names:
        try:
            _, seq, _ = parse_cell(n)
        except (AssertionError, ValueError):
            continue
        bases.add(base_capture(seq))
    return bases


def is_excluded(seq: str, banked: set[str]) -> bool:
    """A sequence is excluded iff its base capture is already in the bank."""
    return base_capture(seq) in banked


# --------------------------------------------------------------------------- #
# SWAP-hard family classifier (pure GT geometry)
# --------------------------------------------------------------------------- #
def _center_short(box) -> tuple[float, float, float]:
    x0, y0, x1, y1 = box
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0, min(x1 - x0, y1 - y0)


def _median(xs) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def longest_absent_before_return(gt) -> int:
    """Longest run of None that is followed by at least one valid frame. A
    leading absence counts (target enters late); a trailing absence does NOT
    (target lost, never returns -- that is carry-loss, not late-entry)."""
    best = cur = 0
    for g in gt:
        if g is None:
            cur += 1
        else:
            if cur:
                best = max(best, cur)
            cur = 0
    return best  # trailing `cur` intentionally discarded (no return)


def gt_metrics(gt) -> dict:
    """Pure-geometry summary of a target track (list of (x0,y0,x1,y1)|None)."""
    valid = [g for g in gt if g is not None]
    shorts = [_center_short(g)[2] for g in valid]
    speeds = []
    prev = None
    for g in gt:
        if g is None:
            prev = None
            continue
        cx, cy, sh = _center_short(g)
        if prev is not None:
            pcx, pcy, _ = prev
            disp = math.hypot(cx - pcx, cy - pcy)
            speeds.append(disp / max(sh, 1.0))
        prev = (cx, cy, sh)
    first_valid = next((i for i, g in enumerate(gt) if g is not None), None)
    return {
        "n_valid": len(valid),
        "first_valid": first_valid,
        "max_absent_return": longest_absent_before_return(gt),
        "med_short": _median(shorts),
        "med_speed_norm": _median(speeds),
    }


def classify_family(gt, seq: str) -> str | None:
    """Assign ONE SWAP-hard family (or None = not SWAP-hard), precedence order:

      late-entry           : a NaN run >= LATE_MIN followed by a valid frame
                             (target absent then (re)enters -- the acquire lands
                             late; structural, so it wins over scale/speed).
      carry-drift          : median bbox short-side < SMALL_PX  OR  median
                             normalized center speed > FAST_NORM (small and/or
                             fast target the SAM2 carry can leak off).
      distractor-confusion : residual -- a stable, clear, multi-instance-class
                             target (>= 2 same-class objects plausible nearby).
                             This is a class-prefix PROXY: the human confirms the
                             second same-class object by eye (this script only
                             proposes).
      None                 : no target, or a singleton-class stable target -> not
                             a SWAP-hard candidate.
    """
    m = gt_metrics(gt)
    if m["n_valid"] == 0:
        return None
    if m["max_absent_return"] >= LATE_MIN:
        return "late-entry"
    if m["med_short"] < SMALL_PX or m["med_speed_norm"] > FAST_NORM:
        return "carry-drift"
    if seq_class(seq) in CROWD_CLASSES:
        return "distractor-confusion"
    return None


def why_str(gt, seq: str, family: str) -> str:
    m = gt_metrics(gt)
    return (f"class={seq_class(seq)} n_valid={m['n_valid']} "
            f"first_valid={m['first_valid']} "
            f"max_absent_return={m['max_absent_return']} "
            f"med_short_px={m['med_short']:.0f} "
            f"med_speed_norm={m['med_speed_norm']:.2f} -> {family}")


# --------------------------------------------------------------------------- #
# f0 / prompt-frame suggestion + cell-schema builder
# --------------------------------------------------------------------------- #
def pick_f0(gt, family: str) -> int | None:
    """Suggest a viable f0: seed (gt[f0]) and prompt (gt[f0+240]) both present,
    with ds >= 0 and the coverage window inside the clip. For late-entry, prefer
    an f0 whose discovery start ds=f0-150 is ABSENT (the late-entry signature).
    Returns None if the clip is too short to host one scene."""
    n = len(gt)
    lo, hi = DS_OFFSET, n - (PROMPT_OFF + COVER_F + 5)
    if hi < lo:
        return None
    cand = [f for f in range(lo, hi + 1)
            if gt[f] is not None and gt[f + PROMPT_OFF] is not None]
    if not cand:
        return None
    if family == "late-entry":
        late = [f for f in cand if gt[f - DS_OFFSET] is None]
        if late:
            return late[len(late) // 2]
    return cand[len(cand) // 2]


def cell_id(leg: str, clip: str, f0: int) -> str:
    return f"DSC_{leg}_{clip}_{f0}"


def build_cell(clip: str, f0: int, family: str, why: str) -> dict:
    """A CANDIDATE scene dict in the exact select_p56 / scenes_p518 schema.
    Captions and the two distractor boxes are explicit TODO placeholders: they
    are hand-annotations (look-at-it on 10-px zooms). Captions are kept
    referentially DISTINCT so the cell is not ill-posed by construction, and a
    `candidate`/`todo` marker keeps a proposal from ever masquerading as a
    locked cell. Drops straight into select_p56.run_matrix_scene once filled."""
    cell = {
        "clip": clip,
        "f0": int(f0),
        "t_p": T_P,
        "target_caption": "TODO_TARGET",
        "distractor_caption": "TODO_DISTRACTOR",
        "distractor_box": None,          # seed @ f0        (human: curate zoom)
        "distractor_gt_prompt": None,    # hand GT @ prompt (human: curate zoom)
        "gating": True,
        "note": (f"CANDIDATE R-36 [{family}]. {why}. TODO human: caption the "
                 f"target + distractor, annotate distractor_box@f0={f0} and "
                 f"distractor_gt_prompt@prompt={f0 + PROMPT_OFF} on 10-px zooms "
                 f"(curate_p518.py zoom), confirm >=2 same-class near target."),
        "candidate": True,
        "todo": ["target_caption", "distractor_caption",
                 "distractor_box", "distractor_gt_prompt"],
    }
    assert REQUIRED_CELL_KEYS <= set(cell), REQUIRED_CELL_KEYS - set(cell)
    return cell


# --------------------------------------------------------------------------- #
# real path (reads UAV123; NOT exercised by --selftest)
# --------------------------------------------------------------------------- #
def _curate_p518():
    """Import curate_p518 lazily (it pulls cv2/numpy at its top) so --selftest
    stays dependency-free. Re-points its DATA at ours."""
    if str(P518) not in sys.path:
        sys.path.insert(0, str(P518))
    import curate_p518
    curate_p518.DATA = DATA
    return curate_p518


def enumerate_sequences(data: Path) -> list[str]:
    seq_root = data / "data_seq" / "UAV123"
    return sorted(d.name for d in seq_root.iterdir() if d.is_dir())


def propose(families: list[str], n_new: int, out: Path,
            do_verify: bool) -> list[dict]:
    """Enumerate -> strip P5.18 -> classify -> dedupe per base capture -> pick
    f0 -> emit candidate jsonl + candidate scenes json. Reads UAV123 GT via the
    reused curate_p518.load_gt/clip_len. Returns the candidate rows."""
    cur = _curate_p518()
    runs = P518 / "runs"
    banked = banked_base_clips(p.name for p in runs.iterdir() if p.is_dir())
    print(f"[R-36] excluding {len(banked)} P5.18 base clips: "
          f"{', '.join(sorted(banked))}")

    want = set(families)
    best: dict[str, dict] = {}   # base capture -> best candidate row
    for seq in enumerate_sequences(DATA):
        if is_excluded(seq, banked):
            continue
        gt = cur.load_gt(seq)
        fam = classify_family(gt, seq)
        if fam is None or fam not in want:
            continue
        f0 = pick_f0(gt, fam)
        if f0 is None:
            continue
        base = base_capture(seq)
        row = {"clip": seq, "base": base, "family": fam,
               "why": why_str(gt, seq, fam),
               "suggested_prompt_frame": f0 + PROMPT_OFF, "f0": f0,
               "cell_id": cell_id("SWAP", seq, f0),
               "n_valid": gt_metrics(gt)["n_valid"]}
        # dedupe per base capture: keep the longest usable track
        if base not in best or row["n_valid"] > best[base]["n_valid"]:
            best[base] = row

    # balance across families (round-robin), then cap at n_new
    by_fam: dict[str, list] = {f: [] for f in FAMILIES}
    for r in sorted(best.values(), key=lambda r: (r["family"], r["clip"])):
        by_fam[r["family"]].append(r)
    ordered, i = [], 0
    while len(ordered) < n_new and any(by_fam[f][i:] for f in FAMILIES):
        for f in FAMILIES:
            if i < len(by_fam[f]) and len(ordered) < n_new:
                ordered.append(by_fam[f][i])
        i += 1
    rows = ordered

    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates_r36.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    scenes = [build_cell(r["clip"], r["f0"], r["family"], r["why"])
              for r in rows]
    (out / "scenes_r36_candidates.json").write_text(
        json.dumps({"comment": "R-36 CANDIDATE cells (NOT locked). Human must "
                    "fill captions + distractor boxes and re-verify before the "
                    "matrix. One hard SWAP scene per distinct base clip.",
                    "scenes": scenes}, indent=2))
    counts = {f: sum(r["family"] == f for r in rows) for f in FAMILIES}
    print(f"[R-36] proposed {len(rows)} candidates ({counts}) -> "
          f"{out / 'candidates_r36.jsonl'}")
    if do_verify:
        verify_candidates(rows, cur)
    return rows


def verify_candidates(rows: list[dict], cur) -> None:
    """GT-viability asserts on each candidate -- the pre-annotation SUBSET of
    curate_p518.verify (:149): ds >= 0, seed gt[f0] valid, prompt gt[prompt]
    valid, coverage window inside the clip (<=60 NaN like verify). The
    distractor asserts are SKIPPED (boxes not yet annotated), and unlike
    curate_p518.verify we do NOT require gt[ds] valid -- R-36 late-entry cells
    deliberately have the target absent at the discovery start."""
    for r in rows:
        clip, f0 = r["clip"], r["f0"]
        n, gt = cur.clip_len(clip), cur.load_gt(clip)
        prompt = f0 + PROMPT_OFF
        assert f0 - DS_OFFSET >= 0, (clip, f0, "no discovery pre-roll")
        assert prompt + COVER_F <= n + 60, (clip, f0, "coverage past clip end")
        assert gt[f0] is not None, (clip, f0, "seed target GT NaN at f0")
        assert gt[prompt] is not None, (clip, f0, "target GT NaN at prompt")
        nan_cover = sum(1 for g in gt[prompt:min(prompt + COVER_F, n)]
                        if g is None)
        assert nan_cover <= 60, (clip, f0, f"{nan_cover} NaN GT frames in cover")
    print(f"[R-36] verify_candidates OK: {len(rows)} candidates GT-viable "
          "(distractor boxes still need hand annotation).")


# --------------------------------------------------------------------------- #
# pure-logic self-test (NO dataset, NO GPU, NO Jetson, NO CARLA)
# --------------------------------------------------------------------------- #
def selftest() -> None:
    B = lambda x0, y0, w, h: (x0, y0, x0 + w, y0 + h)  # noqa: E731

    # ---- exclusion-set logic ------------------------------------------------
    assert parse_cell("DSC_SWAP_car9_950") == ("SWAP", "car9", 950)
    assert parse_cell("DSC_WSEL_wakeboard8_150") == ("WSEL", "wakeboard8", 150)
    assert parse_cell("DSC_SWAP_car6_1_460") == ("SWAP", "car6_1", 460)
    assert base_capture("car6_1") == "car6"
    assert base_capture("car1_s") == "car1"
    assert base_capture("car10") == "car10"
    assert base_capture("bird1_3") == "bird1"
    banked = banked_base_clips(["DSC_SWAP_car9_950",
                                "DSC_WSEL_wakeboard8_150",
                                "DSC_SWAP_car6_1_460", "junk"])
    assert {"car9", "wakeboard8", "car6"} <= banked, banked
    assert is_excluded("car9", banked)          # already-banked clip excluded
    assert is_excluded("car6_2", banked)        # a DIFFERENT segment of a base
    assert not is_excluded("car11", banked)     # a fresh base is kept

    # ---- family classifier on SYNTHETIC GT arrays ---------------------------
    large_slow = [B(600, 300, 100, 100)] * 400          # 100x100, stationary
    # (1) late-entry: absent for the first 100 frames then enters
    late = [None] * 100 + large_slow
    assert classify_family(late, "car5") == "late-entry"
    # re-entry mid-clip (absent 80 frames, valid on both sides) also late-entry
    reentry = large_slow[:120] + [None] * 80 + large_slow[:120]
    assert classify_family(reentry, "car5") == "late-entry"
    # (2) carry-drift: small target (short side 20 < 45), present from start
    small_fast = [B(20 * i, 300, 20, 20) for i in range(30)]  # also 20 px/frame
    assert classify_family(small_fast, "person7") == "carry-drift"
    # carry-drift by SPEED alone (large but fast: 60/200 = 0.30 > 0.15)
    big_fast = [B(60 * i, 100, 200, 200) for i in range(30)]
    assert classify_family(big_fast, "car5") == "carry-drift"
    # (3) distractor-confusion: stable clear target, crowd class
    assert classify_family(large_slow, "car2") == "distractor-confusion"
    # residual only for crowd classes: a singleton-class stable target -> None
    assert classify_family(large_slow, "building2") is None
    # no target ever -> None
    assert classify_family([None] * 300, "car2") is None
    # precedence: late-entry beats small/fast
    late_small = [None] * 80 + small_fast
    assert classify_family(late_small, "person7") == "late-entry"

    # ---- gt_metrics + absence helper ---------------------------------------
    assert longest_absent_before_return([None] * 5 + [B(0, 0, 1, 1)]) == 5
    assert longest_absent_before_return([B(0, 0, 1, 1)] + [None] * 9) == 0  # trailing
    m = gt_metrics(small_fast)
    assert m["n_valid"] == 30 and abs(m["med_short"] - 20) < 1e-6, m
    assert m["med_speed_norm"] > 0.9, m       # 20 px / 20 px short side ~= 1.0

    # ---- f0 suggestion ------------------------------------------------------
    present = [B(600, 300, 100, 100)] * 1000
    f0 = pick_f0(present, "distractor-confusion")
    assert f0 is not None and DS_OFFSET <= f0 <= 1000 - (PROMPT_OFF + COVER_F + 5)
    assert present[f0] is not None and present[f0 + PROMPT_OFF] is not None
    # late-entry prefers an f0 whose ds is absent
    late_track = [None] * 200 + [B(600, 300, 100, 100)] * 900
    lf0 = pick_f0(late_track, "late-entry")
    assert lf0 is not None and late_track[lf0 - DS_OFFSET] is None, lf0
    assert late_track[lf0] is not None
    # too-short clip -> None
    assert pick_f0([B(0, 0, 1, 1)] * 100, "carry-drift") is None

    # ---- cell-schema builder (drops into select_p56 / verdict_p518) ---------
    cell = build_cell("car11", 500, "carry-drift", why_str(present, "car11",
                                                           "carry-drift"))
    assert REQUIRED_CELL_KEYS <= set(cell), set(cell)
    assert cell_id("SWAP", "car11", 500) == "DSC_SWAP_car11_500"
    assert cell["clip"] == "car11" and cell["f0"] == 500 and cell["t_p"] == T_P
    assert cell["gating"] is True and cell["candidate"] is True
    # captions distinct (contract not ill-posed) but flagged TODO
    assert cell["target_caption"] != cell["distractor_caption"]
    assert cell["distractor_box"] is None and cell["distractor_gt_prompt"] is None
    assert set(cell["todo"]) == {"target_caption", "distractor_caption",
                                 "distractor_box", "distractor_gt_prompt"}

    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="R-36 SWAP-hard candidate curation")
    ap.add_argument("--selftest", action="store_true",
                    help="pure-logic self-test (no dataset/GPU/Jetson/CARLA)")
    ap.add_argument("--families", default="late-entry,carry-drift,distractor",
                    help="comma list; 'distractor' == distractor-confusion")
    ap.add_argument("--n-new", type=int, default=17,
                    help="max NEW candidates to propose (over-provision to n~30)")
    ap.add_argument("--verify", action="store_true",
                    help="GT-viability check on the proposed candidates")
    ap.add_argument("--out", default="runs/r36/bank",
                    help="output dir (relative to this file's dir if not abs)")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    fams = [FAMILY_ALIASES.get(f.strip(), f.strip())
            for f in args.families.split(",") if f.strip()]
    bad = [f for f in fams if f not in FAMILIES]
    assert not bad, f"unknown families {bad}; valid: {FAMILIES}"
    out = Path(args.out)
    if not out.is_absolute():
        out = HERE / out
    propose(fams, args.n_new, out, args.verify)


if __name__ == "__main__":
    main()
