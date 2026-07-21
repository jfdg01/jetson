"""Mechanical enforcement of the thesis integrity invariants.

    .venv-ft/bin/python -m pytest tests/test_thesis_integrity.py

These are the checks that catch, automatically, the class of defect this project
has actually shipped: a claim whose evidence path does not exist, an n_effective
that claims more independence than the rows support, and a number whose measuring
machine was never recorded (the defect that let "todo corre en la placa" sit in
README.md while Part V ran its tracker on an RTX 3090).

The rules themselves, and why each exists, are in HANDOFF.md. This file is only
the enforcement. A rule that cannot be checked mechanically lives there and not
here, on purpose - a doc that asks nicely is not an invariant.

RATCHET TESTS
-------------
Some invariants are not satisfied yet; making them hard assertions today would
leave `make test` red, which trains everyone to ignore it. Those are written as
ratchets instead: the test asserts the violation count has not grown past a
recorded ceiling. Fix some claims, lower the ceiling, commit. The suite stays
green and the number can only go down.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "thesis" / "claims.json"


@pytest.fixture(scope="module")
def claims() -> list[dict]:
    return json.loads(REGISTRY.read_text())["claims"]


def _expand_braces(pattern: str) -> list[str]:
    """Expand shell brace syntax, which the registry uses but glob does not grok.

    Handles `{a,b,c}` and `{1..8}` / `{01..12}` (zero-padding preserved). Without
    this every braced path reads as missing and the real breakage hides in the noise.
    """
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    body, out = m.group(1), []
    rng = re.fullmatch(r"(\d+)\.\.(\d+)", body)
    if rng:
        lo, hi = rng.groups()
        width = len(lo) if lo.startswith("0") else 0
        alts = [str(i).zfill(width) for i in range(int(lo), int(hi) + 1)]
    else:
        alts = body.split(",")
    for alt in alts:
        out += _expand_braces(pattern[: m.start()] + alt + pattern[m.end():])
    return out


def _path_has_evidence(pattern: str) -> bool:
    for p in _expand_braces(pattern):
        hits = list(REPO.glob(p)) if any(ch in p for ch in "*?[") else [REPO / p]
        if any(h.exists() for h in hits):
            return True
    return False


def test_registry_parses_and_is_not_empty(claims):
    assert len(claims) >= 60, "claim registry shrank unexpectedly"


def test_claim_ids_are_unique(claims):
    ids = [c["id"] for c in claims]
    assert len(ids) == len(set(ids)), f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})}"


def test_data_paths_exist(claims):
    """A claim that is not `missing` must point at evidence that is on disk.

    This is the check that catches provenance rot - a renamed experiment dir
    silently orphaning the claim that cites it.
    """
    broken = []
    for c in claims:
        if c["data_status"] == "missing":
            continue
        for p in c.get("data_paths", []):
            if not _path_has_evidence(p):
                broken.append(f"{c['id']} -> {p}")
    assert not broken, "claims citing evidence that does not exist:\n  " + "\n  ".join(broken)


def test_missing_claims_declare_a_rerun(claims):
    """`missing` means undefendable, so it must carry the command that fixes it."""
    for c in claims:
        if c["data_status"] == "missing":
            assert c.get("rerun"), f"{c['id']} is missing data but has no rerun block"


def test_n_effective_never_exceeds_n_rows(claims):
    """Deflation may only ever reduce. n_effective > n_rows manufactures independence."""
    bad = [f"{c['id']}: n_effective={c['n_effective']} > n_rows={c['n_rows']}"
           for c in claims
           if c.get("n_rows") and c.get("n_effective")
           and c["n_effective"] > c["n_rows"]]
    assert not bad, "n_effective claims more independence than the data has:\n  " + "\n  ".join(bad)


def test_deflated_claims_explain_themselves(claims):
    """If n_effective < n_rows, the reader is owed the reason."""
    silent = [c["id"] for c in claims
              if c.get("n_rows") and c.get("n_effective")
              and c["n_effective"] < c["n_rows"]
              and not (c.get("independence_note") or "").strip()]
    assert not silent, f"deflated without an independence_note: {silent}"


# --- ratchets ---------------------------------------------------------------
# Lower these as the remediation tasks in thesis/REMEDIATION.md land. Never raise
# one: a rising ceiling is the regression this file exists to prevent.

MAX_CLAIMS_WITHOUT_MACHINE = 65  # R-2. Target 0.


def test_machine_field_coverage_ratchet(claims):
    """Every claim must record WHICH MACHINE measured it.

    The thesis premise is edge deployment on a Jetson Orin Nano. A number
    measured on an RTX 3090 does not support that premise, and the registry
    currently cannot tell the two apart. See HANDOFF.md invariant 3.
    """
    without = [c["id"] for c in claims if not c.get("machine")]
    assert len(without) <= MAX_CLAIMS_WITHOUT_MACHINE, (
        f"{len(without)} claims lack a `machine` field, ceiling is "
        f"{MAX_CLAIMS_WITHOUT_MACHINE}. Ratchet went the wrong way."
    )
    if len(without) < MAX_CLAIMS_WITHOUT_MACHINE:
        pytest.fail(
            f"Good news: only {len(without)} claims lack `machine` (ceiling "
            f"{MAX_CLAIMS_WITHOUT_MACHINE}). Lower MAX_CLAIMS_WITHOUT_MACHINE to "
            f"{len(without)} in this file and commit.",
            pytrace=False,
        )


def test_machine_values_are_from_the_known_set(claims):
    """Free-text machines defeat the point; keep the vocabulary closed."""
    allowed = {"jetson-orin-nano-8gb", "rtx-3090", "both", "n/a"}
    bad = [f"{c['id']}: {c['machine']}" for c in claims
           if c.get("machine") and c["machine"] not in allowed]
    assert not bad, f"unknown machine values (allowed: {sorted(allowed)}):\n  " + "\n  ".join(bad)


def test_every_caveat_reaches_the_report(claims):
    """R-12. A caveat written but not rendered reads as concealment.

    `thesis/run_stats.py` silently dropped all 65 caveats - ~19k characters of
    the most honest text in the project, including one claim flagged in the
    registry as THE ONE NUMBER THAT MUST NOT BE CITED. Anyone diffing
    claims.json against the report saw a cover-up where there was a missing
    field read. This test is the reason it cannot happen twice.
    """
    report = REPO / "thesis" / "stats-report.md"
    if not report.exists():
        pytest.skip("report not generated yet; run thesis/run_stats.py")
    text = report.read_text()
    missing = [c["id"] for c in claims
               if (c.get("caveats") or "").strip() and c["caveats"].strip() not in text]
    assert not missing, (
        f"{len(missing)} caveats never reach thesis/stats-report.md: {missing[:5]}"
        f"{' ...' if len(missing) > 5 else ''}\nRegenerate with thesis/run_stats.py."
    )
