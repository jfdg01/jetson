"""P5.15 mechanical verdict. Reads runs/*/results.json, applies the frozen
gates, prints the verdict block and writes raw/verdict.txt. No judgment calls.

Gates (frozen at pre-registration, 2026-07-19):
  RQ-P5.15a (gating): PLAIN alive@16s >= 18 / (25 - n_na@16s).
      Denominator shrinks only by N/A horizons (no valid GT within +-30
      frames); the threshold 18 stays absolute (an N/A does NOT relax it).
  RQ-P5.15b (gating, conditional): if PLAIN alive@24s >= 22 -> N/A (ceiling);
      else YES iff MAINT alive@24s >= PLAIN alive@24s + 3.
  Overall verdict: YES iff RQ-P5.15a is YES. RQ-b reported either way.
  Any INVALID cell in a gating count makes the whole run INVALID.

    .venv-ft/bin/python experiments/2026-07-19-carry-horizon/verdict_p515.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HORIZONS = ("8", "16", "24")
THRESH_A = 18          # PLAIN alive@16s floor
CEIL_B = 22            # PLAIN alive@24s at/above this -> RQ-b N/A
MARGIN_B = 3           # MAINT@24s must beat PLAIN@24s by this
N_CLIPS = 25


def main() -> None:
    runs = HERE / "runs"
    cells: dict[tuple[str, str], dict] = {}
    invalid = []
    for rj in sorted(runs.glob("*/results.json")):
        r = json.loads(rj.read_text())
        if "INVALID" in r:
            invalid.append(rj.parent.name)
            continue
        cells[(r["arm"], r["clip"])] = r

    lines = ["P5.15 carry-horizon verdict", ""]
    alive: dict[str, dict[str, int]] = {}
    na: dict[str, dict[str, int]] = {}
    for arm in ("PLAIN", "MAINT"):
        got = [(c, r) for (a, c), r in cells.items() if a == arm]
        alive[arm] = {h: 0 for h in HORIZONS}
        na[arm] = {h: 0 for h in HORIZONS}
        lines.append(f"-- {arm} ({len(got)}/{N_CLIPS} cells) --")
        for clip, r in sorted(got):
            row = []
            for h in HORIZONS:
                rec = r["horizons"][h]
                if rec["na"]:
                    na[arm][h] += 1
                    row.append(f"h{h}=N/A")
                else:
                    if rec["alive"]:
                        alive[arm][h] += 1
                    row.append(f"h{h}={'ALIVE' if rec['alive'] else 'dead'}"
                               f"({rec['iou']:.3f}@f{rec['scoring_frame']})")
            lines.append(f"  {clip:12s} {'  '.join(row)}"
                         f"  death={r['death_frame']}")
        lines.append("")

    n_plain = sum(1 for (a, _) in cells if a == "PLAIN")
    n_maint = sum(1 for (a, _) in cells if a == "MAINT")
    complete = n_plain == N_CLIPS and n_maint == N_CLIPS and not invalid

    p16, p24 = alive["PLAIN"]["16"], alive["PLAIN"]["24"]
    m24 = alive["MAINT"]["24"]
    denom16 = n_plain - na["PLAIN"]["16"]
    rq_a = p16 >= THRESH_A
    if p24 >= CEIL_B:
        rq_b = f"N/A (ceiling: PLAIN@24s {p24} >= {CEIL_B})"
    else:
        rq_b = ("YES" if m24 >= p24 + MARGIN_B else "NO") + \
            f" (MAINT@24s {m24} vs PLAIN@24s {p24} + {MARGIN_B})"

    lines += [
        f"PLAIN alive: h8={alive['PLAIN']['8']}  h16={p16}  h24={p24}"
        f"  (N/A: {dict(na['PLAIN'])})",
        f"MAINT alive: h8={alive['MAINT']['8']}  h16={alive['MAINT']['16']}"
        f"  h24={m24}  (N/A: {dict(na['MAINT'])})",
        "",
        f"RQ-P5.15a: PLAIN alive@16s {p16}/{denom16} vs floor {THRESH_A}"
        f" -> {'YES' if rq_a else 'NO'}",
        f"RQ-P5.15b: {rq_b}",
    ]
    if invalid:
        lines.append(f"INVALID cells: {invalid} -> RUN INVALID")
        verdict = "INVALID"
    elif not complete:
        lines.append(f"incomplete matrix (PLAIN {n_plain}/25, MAINT "
                     f"{n_maint}/25) -> NO VERDICT YET")
        verdict = "INCOMPLETE"
    else:
        verdict = "YES" if rq_a else "NO"
    lines.append(f"VERDICT: {verdict}")

    out = "\n".join(lines)
    print(out)
    (HERE / "raw").mkdir(exist_ok=True)
    (HERE / "raw" / "verdict.txt").write_text(out + "\n")


if __name__ == "__main__":
    main()
