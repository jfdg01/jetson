#!/usr/bin/env python3
"""R-5: the shadow re-ground (RG) arm of P5.18/P5.19, recorded and never analysed.

Both campaigns ran the deployed delivery contract (DD: hand over the carried
track, bound to the operator phrase) while a *shadow* re-ground fired the VLM at
the prompt frame and matched its box against the maintained candidates. The
shadow's pick landed in `meta.shadow.selected` and was never compared.

What this script found, and why it is not the paired test the ledger expected:

1. **DD cannot lose on selection.** `select_p56.bind_by_caption` is string
   equality against the stored captions, with an assert that exactly one matches.
   DD scores 48/48 and 50/50 on selection correctness *by construction*. That is
   a scoped-out assumption (recorded in P5.14's README: the experiment isolates
   the delivery mechanism, not phrase understanding), not a measurement, so
   "DD beats RG at selection" is not a finding a paired test can produce.
2. **The published-style pairing compares two different quantities.** Pairing DD
   `pass` (genuine lock + coverage + IoU + carry survival) against RG `selected`
   (selection only) reproduces the ledger's `b=4, c=2` / `b=3, c=2` exactly --
   arithmetically right, conceptually mismatched, and the R-21 MISLEADING shape
   "two differently-defined quantities juxtaposed as a comparison".
3. **RG's number is a ceiling, not a rate.** Selecting correctly is necessary but
   not sufficient for an RG pass -- the shadow never carries a track after its
   re-ground, so it is never charged coverage or IoU. RG selection-correct is
   therefore an upper bound on what RG's pass rate could have been.
4. **The missing rows are informative.** `meta.shadow` is absent exactly where DD
   returned early via `fail()`, so all 4 (P5.18) and 2 (P5.19) dropped cells are
   DD failures. Conditioning on shadow-present drops DD's worst cells, which
   flatters DD in any paired analysis and is a further reason not to run one.
5. **RG is not an independent contract.** It matches its VLM box against
   `cand_at_prompt`, i.e. DD's own maintained tracks, so a drifted carry costs RG
   a match it would have made against a good box. RG's failures are re-ground
   failures *plus* inherited carry failures.

The defensible statement is one-directional: a prompt-time re-ground would have
failed to pick the right candidate in 10/48 and 8/50 cells, and that is the cost
DD's caption-binding assumption buys out.

    .venv-ft/bin/python thesis/analyse_shadow_rg.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

CAMPAIGNS = {
    "P5.18": "experiments/2026-07-20-n25-select",
    "P5.19": "experiments/2026-07-20-late-entry-rescue",
}
CORRECT = {"WSEL": "target", "SWAP": "distractor"}


def cells(campaign_dir: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(f"{campaign_dir}/runs/*/results.json")):
        d = json.loads(Path(p).read_text())
        shadow = d["meta"].get("shadow")
        out.append({
            "cell": Path(p).parent.name,
            "clip": d["scene"]["clip"],
            "leg": d["leg"],
            "gating": d["scene"]["gating"],
            "dd_pass": bool(d["pass"]),
            "dd_reason": d["score"].get("reason"),
            "dd_sel_ok": d["score"].get("selection") == CORRECT[d["leg"]],
            "rg_sel_ok": None if shadow is None
            else shadow.get("selected") == CORRECT[d["leg"]],
            "rg_no_match": bool(shadow) and shadow.get("selected") is None,
        })
    return out


def paired(rows: list[dict], dd_key: str) -> dict:
    """b/c against RG selection, with DD scored on `dd_key`. `dd_key='dd_sel_ok'`
    is the like-for-like pairing (and is vacuous); `'dd_pass'` is the pairing the
    ledger published (and is definitionally mismatched)."""
    kept = [r for r in rows if r["rg_sel_ok"] is not None]
    b = sum(1 for r in kept if r[dd_key] and not r["rg_sel_ok"])
    c = sum(1 for r in kept if r["rg_sel_ok"] and not r[dd_key])
    return {"n": len(kept), "b": b, "c": c, "agree": len(kept) - b - c,
            "dd_k": sum(r[dd_key] for r in kept),
            "rg_k": sum(r["rg_sel_ok"] for r in kept)}


def report() -> dict:
    out = {}
    for name, d in CAMPAIGNS.items():
        rows = cells(d)
        gating = [r for r in rows if r["gating"]]
        kept = [r for r in gating if r["rg_sel_ok"] is not None]
        dropped = [r for r in gating if r["rg_sel_ok"] is None]
        out[name] = {
            "gating_cells": len(gating),
            "paired_cells": len(kept),
            "clips": len({r["clip"] for r in kept}),
            "rg_ceiling": {"k": sum(r["rg_sel_ok"] for r in kept), "n": len(kept)},
            "rg_no_match": sum(r["rg_no_match"] for r in kept),
            "dd_pass_realized": {"k": sum(r["dd_pass"] for r in kept), "n": len(kept)},
            "like_for_like": paired(gating, "dd_sel_ok"),
            "as_published": paired(rows, "dd_pass"),   # all rows: reproduces the ledger
            "dropped": [(r["cell"], r["dd_pass"], r["dd_reason"]) for r in dropped],
            "by_leg": {leg: {"rg_k": sum(r["rg_sel_ok"] for r in kept if r["leg"] == leg),
                             "n": sum(1 for r in kept if r["leg"] == leg)}
                       for leg in ("WSEL", "SWAP")},
        }
        o = out[name]
        print(f"\n{name}  ({d})")
        print(f"  gating {o['gating_cells']}  paired {o['paired_cells']}  clips {o['clips']}")
        print(f"  RG selection-correct (CEILING) {o['rg_ceiling']['k']}/{o['rg_ceiling']['n']}"
              f"   of which NO_MATCH {o['rg_no_match']}")
        print(f"  DD pass (realized)             {o['dd_pass_realized']['k']}/{o['dd_pass_realized']['n']}")
        for leg, m in o["by_leg"].items():
            print(f"    RG {leg}: {m['rg_k']}/{m['n']}")
        lfl, pub = o["like_for_like"], o["as_published"]
        print(f"  like-for-like (DD selection, VACUOUS): DD {lfl['dd_k']}/{lfl['n']}"
              f"  RG {lfl['rg_k']}/{lfl['n']}  b={lfl['b']} c={lfl['c']}")
        print(f"  as published (DD pass vs RG selection): n={pub['n']} b={pub['b']} "
              f"c={pub['c']} agree={pub['agree']}  -- mismatched criteria")
        print(f"  dropped (no shadow; all are DD early-fails):")
        for cell, dd, why in o["dropped"]:
            print(f"    {cell}  dd_pass={dd}  {why}")
    return out


def _selfcheck() -> None:
    for name, d in CAMPAIGNS.items():
        rows = cells(d)
        gating = [r for r in rows if r["gating"]]
        assert len(gating) == 52, (name, len(gating))
        # 1. the schema is real, not guessed (the b=39,c=7 failure mode)
        assert any(r["rg_sel_ok"] for r in rows), f"{name}: no RG pick ever correct"
        # 2. leg semantics respected: SWAP-correct is `distractor`
        swap = [r for r in gating if r["leg"] == "SWAP" and r["rg_sel_ok"] is not None]
        assert swap and not all(r["rg_sel_ok"] for r in swap), f"{name}: SWAP never fails RG"
        # 3. DD selection is correct by construction wherever DD gets as far as
        #    selecting. (An early `fail()` writes selection=None, which is a
        #    carry/discovery failure, not a mis-pick.) If this ever trips, the
        #    caption binding changed and the whole framing above must be redone.
        assert all(r["dd_sel_ok"] for r in gating if r["dd_reason"] is None), \
            f"{name}: DD mis-selected on a cell that reached selection"
        # 4. missingness is informative, not random
        assert all(not r["dd_pass"] for r in gating if r["rg_sel_ok"] is None), \
            f"{name}: a shadow-missing cell passed DD -- missingness assumption broken"
    # 5. the ledger's published counts are reproduced, so the correction is about
    #    definition and not about arithmetic
    p18 = paired(cells(CAMPAIGNS["P5.18"]), "dd_pass")
    p19 = paired(cells(CAMPAIGNS["P5.19"]), "dd_pass")
    assert (p18["n"], p18["b"], p18["c"]) == (50, 4, 2), p18
    assert (p19["n"], p19["b"], p19["c"]) == (52, 3, 2), p19


if __name__ == "__main__":
    _selfcheck()
    report()
