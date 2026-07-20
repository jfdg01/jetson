#!/usr/bin/env python3
"""P5.20 carry-capacity A/B runner -- Arm T (sam2.1-hiera-tiny, the P5.19
config verbatim, fresh re-roll = the replication control) vs Arm S
(sam2.1-hiera-small, equal stride), both on the frozen scenes_p518.json.

The ONLY factor that differs between arms is the SAM2 checkpoint handed to
StreamCarry. Everything else -- idle-window discovery (schedule driven by
measured Jetson VLM latencies mapped onto the frame clock; local carry
compute never consumes clip time, see discover_p516.discover: cur = fr =
fs + round(lat*fps)), aligned dedup, bounded grace delivery, ROI re-anchor,
scoring, strengthened SWAP -- is rescue_p519 / discover_p516 VERBATIM via
import + the same monkeypatch chain P5.19 used.

Injection point: discover_p516.run_matrix_scene executes
`from stream_carry import MODEL, StreamCarry` INSIDE the function body, so
it reads stream_carry.MODEL at call time; setting the module attribute
before the matrix runs overrides the checkpoint with zero code duplication.
StreamCarry itself is checkpoint-agnostic (it only uses predictor.image_size
and the predictor API, identical across hiera sizes).

Every cell's results.json gets a p520 stamp {"arm", "sam2_model",
"equal_stride"} written the moment run_matrix_scene returns (rescue_p519's
own p519 stamp is added on top afterwards and preserves it), so a mixed-arm
or stale-harness runs dir is machine-detectable by verdict_p520.py. The
runner refuses to start an arm into an out dir already containing any cell
stamped for a different arm.

Usage:
    capacity_p520.py --selfcheck
    capacity_p520.py --arm T --matrix ../2026-07-20-n25-select/scenes_p518.json
    capacity_p520.py --arm S --matrix ../2026-07-20-n25-select/scenes_p518.json
    # optional: --only clip:f0, --legs WSEL,SWAP, --out DIR (default
    # runs/<arm>), --cover-s, --fps, --no-overlay
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
P519 = REPO / "experiments" / "2026-07-20-late-entry-rescue"
sys.path.insert(0, str(P519))
import rescue_p519                                                 # noqa: E402

p516 = rescue_p519.p516        # discover_p516, already on rescue_p519's paths

ARMS = {"T": "facebook/sam2.1-hiera-tiny",
        "S": "facebook/sam2.1-hiera-small"}


def _guard_out_dir(out_root: Path, arm: str) -> None:
    """Refuse to run arm X into a dir holding another arm's (or an
    unstamped) cell -- catches a swapped --out / --arm before any GPU work."""
    for rj in sorted(out_root.glob("DSC_*/results.json")):
        stamped = json.loads(rj.read_text()).get("p520", {}).get("arm")
        assert stamped == arm, (
            f"ARM MIX: {rj} is stamped arm={stamped!r}; refusing to run "
            f"arm={arm!r} into {out_root}. Fix --out/--arm or delete the "
            f"offending cell dir.")


def run_arm(args) -> None:
    import stream_carry                                             # noqa: E402
    model = ARMS[args.arm]
    out_root = Path(args.out) if args.out else HERE / "runs" / args.arm
    if not out_root.is_absolute():
        out_root = HERE / out_root
    out_root.mkdir(parents=True, exist_ok=True)
    _guard_out_dir(out_root, args.arm)
    stream_carry.MODEL = model                    # THE arm knob (call-time read)

    orig = p516.run_matrix_scene

    def rms_stamped(leg, scene, out_dir, **kw):
        assert stream_carry.MODEL == model, (stream_carry.MODEL, model)
        r = orig(leg, scene, out_dir, **kw)
        rj = out_dir / "results.json"
        d = json.loads(rj.read_text())
        d["p520"] = {"arm": args.arm, "sam2_model": model,
                     "equal_stride": True}
        rj.write_text(json.dumps(d, indent=2))
        return r

    p516.run_matrix_scene = rms_stamped
    try:
        ns = argparse.Namespace(
            matrix=args.matrix, legs=args.legs, only=args.only,
            out=str(out_root), cover_s=args.cover_s, fps=args.fps,
            overlay=args.overlay)
        rescue_p519.run_matrix(ns)     # p519 patch + skip logic + grace png
    finally:
        p516.run_matrix_scene = orig


# --------------------------------------------------------------------------- #
def selfcheck() -> None:
    """No GPU / no Jetson. Asserts:
      (S1) arm knob visibility: after run_arm sets stream_carry.MODEL, a
           function-level `from stream_carry import MODEL` (the exact form
           run_matrix_scene uses) sees the override, per arm;
      (S2) stamping: every cell written by the (stubbed) matrix carries
           p520 {arm, sam2_model} AND rescue_p519's p519 marker, and the
           p519 stamp did not clobber p520;
      (S3) resume: an existing results.json is skipped untouched (content
           byte-identical after a second run);
      (S4) arm-mix guard: running arm S into a dir holding an arm-T cell
           refuses before any cell runs;
      (S5) restoration: p516.run_matrix_scene is restored after run_arm.
    """
    import tempfile

    import stream_carry

    scenes = {"scenes": [
        {"clip": "car18", "f0": 150, "gating": True,
         "target_caption": "t", "distractor_caption": "d"},
        {"clip": "car3", "f0": 200, "gating": False,
         "target_caption": "t", "distractor_caption": "d"},
    ]}

    def read_model_like_p516():
        from stream_carry import MODEL              # call-time, as in p516
        return MODEL

    calls = []

    def stub_rms(leg, scene, out_dir, **kw):
        calls.append((leg, scene["clip"], read_model_like_p516()))
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(
            {"pass": True, "score": {}, "meta": {}}))

    root = Path(tempfile.mkdtemp(prefix="p520_rt_"))
    saved_rms, saved_model = p516.run_matrix_scene, stream_carry.MODEL
    mx = root / "scenes.json"
    mx.write_text(json.dumps(scenes))
    try:
        p516.run_matrix_scene = stub_rms

        def mkargs(arm, out):
            return argparse.Namespace(
                arm=arm, matrix=str(mx), legs="WSEL,SWAP", only=None,
                out=str(out), cover_s=10.0, fps=30.0, overlay=False)

        # S1 + S2: arm T
        run_arm(mkargs("T", root / "T"))
        assert [c[2] for c in calls] == [ARMS["T"]] * 4, calls
        for cid in ("DSC_WSEL_car18_150", "DSC_SWAP_car18_150",
                    "DSC_WSEL_car3_200", "DSC_SWAP_car3_200"):
            d = json.loads((root / "T" / cid / "results.json").read_text())
            assert d["p520"] == {"arm": "T", "sam2_model": ARMS["T"],
                                 "equal_stride": True}, (cid, d)
            assert d.get("p519", {}).get("patch") == "late-entry-rescue", d
        # S1: arm S sees the small checkpoint
        calls.clear()
        run_arm(mkargs("S", root / "S"))
        assert [c[2] for c in calls] == [ARMS["S"]] * 4, calls
        d = json.loads(
            (root / "S" / "DSC_SWAP_car18_150" / "results.json").read_text())
        assert d["p520"]["sam2_model"] == "facebook/sam2.1-hiera-small", d

        # S3: resume skips, bytes untouched
        before = (root / "T" / "DSC_WSEL_car18_150" / "results.json").read_bytes()
        calls.clear()
        run_arm(mkargs("T", root / "T"))
        assert calls == [], f"resume re-ran cells: {calls}"
        after = (root / "T" / "DSC_WSEL_car18_150" / "results.json").read_bytes()
        assert before == after, "resume mutated an existing cell"

        # S4: arm-mix guard
        try:
            run_arm(mkargs("S", root / "T"))
            raise SystemExit("arm-mix guard did not refuse")
        except AssertionError as e:
            assert "ARM MIX" in str(e), e
        assert calls == [], "arm-mix guard ran cells before refusing"
    finally:
        p516.run_matrix_scene = saved_rms
        stream_carry.MODEL = saved_model
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    # S5
    assert p516.run_matrix_scene is saved_rms
    print("capacity_p520 selfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--arm", choices=("T", "S"))
    ap.add_argument("--matrix", help="scenes_p518.json path")
    ap.add_argument("--legs", default="WSEL,SWAP")
    ap.add_argument("--only", help="restrict to scene id clip:f0")
    ap.add_argument("--out", default=None,
                    help="cell snapshot root (default runs/<arm>)")
    ap.add_argument("--cover-s", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--no-overlay", dest="overlay", action="store_false")
    args = ap.parse_args()
    if args.selfcheck:
        selfcheck()
        return
    assert args.arm and args.matrix, "--arm and --matrix are required"
    run_arm(args)


if __name__ == "__main__":
    main()
