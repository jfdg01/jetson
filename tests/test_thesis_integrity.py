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

MAX_CLAIMS_WITHOUT_MACHINE = 0  # R-2. Reached 2026-07-21; this one is now a hard rule.


def test_machine_field_coverage_ratchet(claims):
    """Every claim must record WHICH MACHINE measured it.

    The thesis premise is edge deployment on a Jetson Orin Nano. A number
    measured on an RTX 3090 does not support that premise, and the registry
    could not tell the two apart until R-2. See HANDOFF.md invariant 3.

    Ratchet closed at 0 - a new claim without `machine` now fails outright.
    """
    without = [c["id"] for c in claims if not c.get("machine")]
    assert len(without) <= MAX_CLAIMS_WITHOUT_MACHINE, (
        f"{len(without)} claims lack a `machine` field, ceiling is "
        f"{MAX_CLAIMS_WITHOUT_MACHINE}. Ratchet went the wrong way: {without[:5]}"
    )
    if len(without) < MAX_CLAIMS_WITHOUT_MACHINE:
        pytest.fail(
            f"Good news: only {len(without)} claims lack `machine` (ceiling "
            f"{MAX_CLAIMS_WITHOUT_MACHINE}). Lower MAX_CLAIMS_WITHOUT_MACHINE to "
            f"{len(without)} in this file and commit.",
            pytrace=False,
        )


def test_on_device_claims_really_are_on_device(claims):
    """R-2. `jetson-orin-nano-8gb` is the load-bearing value; keep it earned.

    The whole point of the field is that «runs on the board» must be checkable.
    Only three claims carry it, and each is a number the Orin produced end to
    end. Anything that leans on the rate-capped 3090 carry is `both`, not
    Jetson - that distinction is the finding, so pin it.
    """
    on_device = {c["id"] for c in claims if c.get("machine") == "jetson-orin-nano-8gb"}
    assert on_device == {
        "P1-S1.2-zeroshot-smolvlm",
        "P3-wholeframe-resolution-knee",
        "P3-E1-TRT-fps",
        "P3-ROI-M2.0-512-ondevice",  # R-14: both arms one Orin Q8_0 session, control reproduced 63.1%
        "P3-R13-owlv2-vs-vlm",  # R-13: OWLv2 fp16 + the VLM comparator both measured on the Orin
        "P4-R16-carry-rate-1024",  # R-16: SAM2 carry + deployed VLM server, both on the Orin
    }, (
        "the set of wholly-on-device claims changed. If that is deliberate, update "
        "this test AND experiments/2026-07-21-machine-disclosure/README.md, which is "
        f"where each assignment is justified. Got: {sorted(on_device)}"
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


# --- R-4: pseudo-replication --------------------------------------------------
# The unit of independence is the SOURCE CLIP, not the scene cut from it. This was
# applied to 49 claims and dropped on the 4 where it cost the headline, which is
# the shape a reader reads as concealment whatever the intent was. The two tests
# below close both halves of that hole: the count must be derived from the frozen
# scene set (not asserted in prose), and a claim drawn from a campaign that HAS a
# scene set may not quietly omit the pointer to it.

CAMPAIGN_SCENE_SETS = {
    "experiments/2026-07-20-n25-select/": "experiments/2026-07-20-n25-select/scenes_p518.json",
    "experiments/2026-07-20-late-entry-rescue/": "experiments/2026-07-20-n25-select/scenes_p518.json",
    "experiments/2026-07-20-carry-capacity/": "experiments/2026-07-20-n25-select/scenes_p518.json",
}


def _distinct_gating_clips(scene_set: str) -> int:
    scenes = json.loads((REPO / scene_set).read_text())["scenes"]
    return len({s["clip"] for s in scenes if s.get("gating", True)})


def test_n_effective_respects_the_distinct_clip_count(claims):
    """R-4. A claim may not count more independent units than it has source clips.

    Derived from the scene set itself, so it self-updates if the bank changes and
    cannot drift out of step with a hardcoded number. Claims whose own n_rows is
    smaller than the bank (e.g. the 4 grace firings) are bounded by n_rows.
    """
    bad = []
    for c in claims:
        if not c.get("scene_set"):
            continue
        ceiling = min(c["n_rows"], _distinct_gating_clips(c["scene_set"]))
        if c["n_effective"] > ceiling:
            bad.append(f"{c['id']}: n_effective={c['n_effective']} > {ceiling} "
                       f"(distinct gating clips in {c['scene_set']}, capped by n_rows)")
    assert not bad, "pseudo-replication: cells counted as independent units:\n  " + "\n  ".join(bad)


def test_claims_from_a_banked_campaign_declare_their_scene_set(claims):
    """R-4. The check above is only as good as the pointer; make omission fail."""
    silent = [c["id"] for c in claims
              if not c.get("scene_set")
              and any(p.startswith(prefix) for p in c.get("data_paths", [])
                      for prefix in CAMPAIGN_SCENE_SETS)]
    assert not silent, (
        f"claims drawn from a campaign with a frozen scene set but declaring no "
        f"`scene_set`: {silent}. Add it, or the clip-clustering check skips them."
    )
