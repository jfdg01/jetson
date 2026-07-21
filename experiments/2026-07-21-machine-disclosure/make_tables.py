"""Render the per-Part machine tables in README.md from raw/machine-audit.json.

The audit is the data; the README is a view of it. Keeping the tables generated
means a later correction to one campaign's row cannot silently disagree with the
JSON that R-2 will read to fill in `machine` on all 65 claims.

    .venv-ft/bin/python experiments/2026-07-21-machine-disclosure/make_tables.py

Rewrites everything between the BEGIN/END markers in README.md, in place.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEGIN = "<!-- BEGIN GENERATED TABLES -->"
END = "<!-- END GENERATED TABLES -->"

PART_ORDER = ["I", "II", "II/III", "III", "IV", "V", "VI"]
PART_TITLE = {
    "I": "Part I — exploratory (device benchmarks + first fine-tune)",
    "II": "Part II — v2 principled rebuild",
    "II/III": "Part II/III boundary",
    "III": "Part III — v3 object permanence",
    "IV": "Part IV — v4 end-to-end workflow refinement",
    "V": "Part V — v5 anticipatory grounding",
    "VI": "Part VI — v6 closed-loop flight",
}
SHORT = {
    "jetson-orin-nano-8gb": "Jetson",
    "rtx-3090": "3090",
    "both": "both",
    "n/a": "none",
    "unclear": "**unclear**",
}
# `confidence` is about the README, not about the truth: `stated` = the campaign
# names its own host; `inferred` = the host is only reachable through code, a
# sibling doc or an inheritance chain; `unknown` = nothing in the tree says.
MARK = {"stated": "stated", "inferred": "**inferred**", "unknown": "**UNKNOWN**"}


def _cell(text: str, width: int = 96) -> str:
    text = " ".join((text or "").split())
    if len(text) > width:
        text = text[: width - 1].rsplit(" ", 1)[0] + "…"
    return text.replace("|", "\\|")


def render(campaigns: list[dict]) -> str:
    out: list[str] = []
    for part in PART_ORDER:
        rows = [c for c in campaigns if c["part"] == part]
        if not rows:
            continue
        out += [f"### {PART_TITLE[part]}", ""]
        out += ["| Campaign | VLM ran on | Other compute | Disclosure |",
                "|---|---|---|---|"]
        for c in sorted(rows, key=lambda r: r["campaign"]):
            out.append(
                f"| `{c['campaign']}` | {SHORT.get(c['vlm_machine'], c['vlm_machine'])} "
                f"| {_cell(c['other_compute_machine'])} | {MARK[c['confidence']]} |"
            )
        out.append("")
    return "\n".join(out)


def main() -> None:
    campaigns = json.loads((HERE / "raw" / "machine-audit.json").read_text())
    readme = HERE / "README.md"
    text = readme.read_text()
    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    assert head and tail, "markers missing from README.md"
    readme.write_text(f"{head}{BEGIN}\n\n{render(campaigns)}\n{END}{tail}")
    print(f"rendered {len(campaigns)} campaigns into {readme}")


if __name__ == "__main__":
    main()
