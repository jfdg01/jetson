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


_NO_COMMAND = "NO RUNNABLE COMMAND EXISTS"


def test_rerun_commands_resolve(claims):
    """A re-run command must run, or say plainly that it cannot.

    R-31 (2026-07-23) found all three backlog commands were fiction:
    `grounding.eval.score_clips` does not exist, and `run_phase_c.py` has no
    `--arms`, no `--reps` and no CARLA path. The old test asserted only that a
    `rerun` key was *present*, so a backlog of unrunnable commands read as a
    costed, actionable plan for two days. Presence is not resolvability.

    An honest "no runnable command exists, here is what would have to be built"
    passes. A command naming a module or a flag that does not exist does not.
    """
    import importlib.util

    bad = []
    for c in claims:
        cmd = ((c.get("rerun") or {}).get("command") or "").strip()
        if not cmd or cmd.startswith(_NO_COMMAND):
            continue

        for mod in re.findall(r"-m\s+([A-Za-z_][\w.]*)", cmd):
            try:
                found = importlib.util.find_spec(mod) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                found = False
            if not found:
                bad.append(f"{c['id']}: `-m {mod}` does not exist")

        scripts = re.findall(r"([\w/]+\.py)", cmd)
        for rel in scripts:
            if not (REPO / rel).exists():
                bad.append(f"{c['id']}: script `{rel}` does not exist")

        # flags are only checkable against a script we can read
        readable = [REPO / s for s in scripts if (REPO / s).exists()]
        if readable:
            text = "\n".join(p.read_text() for p in readable)
            for flag in set(re.findall(r"(?<![\w-])(--[a-z][\w-]*)", cmd)):
                if flag not in text:
                    bad.append(f"{c['id']}: `{flag}` not accepted by {scripts[0]}")

    assert not bad, (
        "re-run commands that do not resolve (say " + _NO_COMMAND + " instead):\n  "
        + "\n  ".join(bad))


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


_NO_TEST_RAN = re.compile(
    r"0 pares discordantes|cero pares discordantes|"
    r"\bb\s*=\s*0\s*,?\s*(?:y\s+)?c\s*=\s*0|"
    r"McNemar (?:queda )?indefinid[oa]|no (?:se )?corri[oó] (?:ninguna )?prueba",
    re.IGNORECASE)


def test_paired_caveats_do_not_contradict_their_own_discordant_counts(claims):
    """R-22. A caveat may not say "no test ran" when the registry records discordants.

    This is the table/prose agreement check, and it is deliberately narrow. Most
    caveats quote p-values that are NOT this claim's own result - a counterfactual
    ("even a perfect 5/5 would give p = 0.33"), a sibling arm, an undeflated value
    that the same sentence then deflates, or a number explicitly marked retired.
    Comparing every `p = X` in the prose against the computed p flags thirteen
    claims, all thirteen legitimate, so that test would be noise with a maintenance
    bill attached.

    The zero-discordance assertion has no such ambiguity: either the registry
    records b + c > 0 or it does not. E19 published "b=0, c=0, McNemar indefinido"
    for eight days while its counts said b=1, c=0, because the paired deflation
    halved already-collapsed counts a second time (see `grounding.stats`, R-22).
    The prose was generated from the caveat and the table from the counts, so the
    same file disagreed with itself 112 lines apart and nothing caught it.
    """
    lying = []
    for c in claims:
        if c.get("design") != "paired-binary":
            continue
        counts = c.get("counts") or {}
        discordant = counts.get("b", 0) + counts.get("c", 0)
        if discordant == 0:
            continue
        for field in ("caveats", "caveats_en"):
            text = c.get(field) or ""
            hit = _NO_TEST_RAN.search(text)
            if hit:
                lying.append(f"{c['id']}.{field}: says {hit.group(0)!r} "
                             f"but counts record b={counts.get('b')}, c={counts.get('c')}")
    assert not lying, ("paired caveats contradict their own counts:\n  "
                       + "\n  ".join(lying))


# R-39. Only the present-tense third person, and only within 130 characters of the
# word "Holm". Both narrowings are load-bearing: the registry uses "sobrevivir" /
# "survive" freely for masks, clips, mechanisms, tracks and files ("los números solo
# sobreviven en el README", "the warm track survives THIS rig's ego-motion"), and a
# looser pattern flags eleven claims, all eleven innocent. Past tenses are excluded
# because a corrected caveat legitimately narrates its own history -- P5.15 now says
# "sí sobrevivía, por poco (0,04653), mientras la Parte V tenía m = 18".
_HOLM_VERDICT = re.compile(
    r"(no\s+|tampoco\s+|NOT\s+|not\s+)?\b(sobrevive|survives|survive)\b", re.IGNORECASE)


def test_caveats_agree_with_the_computed_holm_verdict(claims):
    """R-39. A caveat may not claim Holm survival the correction does not grant.

    The incident: `P5.15-plain-carry-survival` said per-Part Holm "eleva a 0,04653:
    **sobrevive por poco**" while the table two screens above it in the SAME
    generated `stats-report.md` printed 0.05525 and the survivor list omitted the
    claim. Nothing was edited to break it. Registering R-36, R-38 and P5.21 on
    2026-07-24 grew Part V's family from m = 18 to m = 21, Holm's threshold
    tightened, and a claim that had survived stopped surviving -- silently, because
    the p-values are computed and the verdict prose is stored.

    That is the standing hazard of the R-30 per-Part family, and it is not a
    one-off: every future experiment added to a Part re-runs this correction over
    every claim already published in that Part. The prose cannot be trusted to
    follow the arithmetic on its own, so it is checked.

    A caveat may assert BOTH verdicts, because it usually reports both families in
    one sentence ("survives per-Part; under the global family it does not"). So the
    assertion set must be a SUBSET of what was actually computed, not equal to it.
    """
    import sys
    sys.path.insert(0, str(REPO / "thesis"))
    from run_stats import holm_by_family, load_claims
    from grounding.stats import evaluate, holm_bonferroni

    parsed, _ = load_claims()
    outcomes = {c.id: evaluate(c) for c in parsed}
    per_part = holm_by_family(parsed, outcomes)
    global_ = holm_bonferroni({cid: o.p_value for cid, o in outcomes.items()})
    by_id = {c["id"]: c for c in claims}

    lying = []
    for c in parsed:
        computed = {per_part[c.id]["reject"], global_[c.id]["reject"]}
        for field in ("caveats", "caveats_en"):
            text = (by_id[c.id].get(field) or "")
            for m in _HOLM_VERDICT.finditer(text):
                window = text[max(0, m.start() - 130):m.end() + 130]
                if "holm" not in window.lower():
                    continue
                asserts = not m.group(1)          # a leading "no"/"not" negates it
                if asserts not in computed:
                    lying.append(
                        f"{c.id}.{field}: prose says {m.group(0)!r} "
                        f"(survives={asserts}) but Holm computes "
                        f"per-Part={per_part[c.id]['reject']} "
                        f"(p={per_part[c.id]['p_holm']:.4g}), "
                        f"global={global_[c.id]['reject']} "
                        f"(p={global_[c.id]['p_holm']:.4g})")
    assert not lying, (
        "caveat prose contradicts the Holm correction it describes -- the family "
        "probably grew since the caveat was written; fix thesis/claims.json and "
        "regenerate with thesis/run_stats.py:\n  " + "\n  ".join(lying))


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
        # P6.7: every timed term is the Orin's -- bridge spawn, torch/sam2 import,
        # weight load, CUDA warm-up, carry steps -- and the G3 grounding probe hits
        # the deployed llama-server over 127.0.0.1 on the board. The host only
        # replays JPEGs from disk and holds the clock; no 3090 arm exists.
        "P6.7-HANDOFF-warm-vs-cold-bridge",
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
        if not c.get("scene_set") or c.get("icc"):
            continue  # calibrated claims are checked by the test below instead
        ceiling = min(c["n_rows"], _distinct_gating_clips(c["scene_set"]))
        if c["n_effective"] > ceiling:
            bad.append(f"{c['id']}: n_effective={c['n_effective']} > {ceiling} "
                       f"(distinct gating clips in {c['scene_set']}, capped by n_rows)")
    assert not bad, "pseudo-replication: cells counted as independent units:\n  " + "\n  ".join(bad)


def test_icc_calibrated_n_effective_is_derived_not_chosen(claims):
    """R-29 (author decision, 2026-07-23). Calibration must be arithmetic, not taste.

    R-4 collapsed clustered cells to one observation per cluster, which asserts an
    intra-class correlation of exactly 1.0. Measured, it is not: P5.19's SWAP cells
    give ICC(1) = 0.418 and P5.18's 0.454. So the collapse *created* the
    unreachability R-4 then reported - `min_successes_for_gate(26, 0.8)` is
    reachable where `0.8 ** 13` is not.

    Calibration only ever moves n_effective UP, which is the direction I2 forbids
    when it is a choice. It is survivable only because it is not a choice: every
    calibrated claim carries the inputs, and this test recomputes the output from
    them. Hand-editing `n_effective` on a calibrated claim fails here.

    Two guards are load-bearing:
      - the UPPER 95% confidence bound on the ICC is used, never the point estimate.
        Few clusters give a wide interval, an upper bound near 1, and therefore
        n_effective near the conservative collapse. Noise cannot manufacture
        independence.
      - `collapsed_floor` keeps R-4's value as a published sensitivity analysis.
    """
    bad = []
    for c in claims:
        icc = c.get("icc")
        if not icc:
            continue
        for k in ("point", "upper95", "mean_cluster_size", "clusters", "collapsed_floor"):
            if k not in icc:
                bad.append(f"{c['id']}: icc block missing `{k}`")
        if bad:
            continue
        if not 0.0 <= icc["upper95"] <= 1.0:
            bad.append(f"{c['id']}: upper95={icc['upper95']} outside [0, 1]")
        if icc["upper95"] < icc["point"]:
            bad.append(f"{c['id']}: upper95 {icc['upper95']} below the point estimate {icc['point']}")
        deff = 1 + (icc["mean_cluster_size"] - 1) * icc["upper95"]
        want = max(icc["clusters"], min(c["n_rows"], round(c["n_rows"] / deff)))
        if c["n_effective"] != want:
            bad.append(f"{c['id']}: n_effective={c['n_effective']} but its own icc block "
                       f"implies {want} (deff={deff:.3f}, n_rows={c['n_rows']})")
        if c["n_effective"] > c["n_rows"]:
            bad.append(f"{c['id']}: calibrated past n_rows")
        if icc["collapsed_floor"] > c["n_effective"]:
            bad.append(f"{c['id']}: calibration TIGHTENED below the collapsed floor "
                       f"{icc['collapsed_floor']} - that is fine, but record it as the floor")
    assert not bad, "ICC calibration is not derivable from its own inputs:\n  " + "\n  ".join(bad)


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


def test_the_claim_buckets_are_a_partition():
    """R-23. Every claim lands in exactly one bucket and the counts sum to 70.

    The report used to print four overlapping filters summing to 88 over 70
    claims: "no defined p" and "could never reach alpha" are the same claims
    twice for 29 of them. Both labels also lied about their contents. "33 had 0
    discordant pairs" was true of four; the rest were not paired designs at all,
    and four more had a single discordant pair that deflation rounded away, so
    they printed "0 pares discordantes" directly followed by "[deflactado desde
    b=1, c=0]". "38 designs could never reach alpha" folded twelve genuinely
    unreachable gates in with 23 arms that had no gate to miss and 12 that were
    descriptive on purpose.

    Twelve gated designs no outcome could have cleared is the sentence the
    chapter should carry. It is damning and it is true. 38 is refutable in a
    minute, and a reader who refutes it stops believing the rest of the chapter.
    """
    import sys
    sys.path.insert(0, str(REPO / "thesis"))
    from run_stats import BUCKETS, bucket_of, holm_by_family, load_claims
    from grounding.stats import evaluate

    parsed, _ = load_claims()
    outcomes = {c.id: evaluate(c) for c in parsed}
    # R-30: the family is the Part. Import the helper rather than re-deriving it -
    # this test disagreed with the report it audits because it computed the global
    # family by hand while the report had moved to per-Part.
    holm = holm_by_family(parsed, outcomes)

    known = {key for key, _, _ in BUCKETS}
    assigned = {c.id: bucket_of(c, outcomes[c.id], holm[c.id]["reject"]) for c in parsed}

    unknown = {i: b for i, b in assigned.items() if b not in known}
    assert not unknown, f"bucket_of returned a key BUCKETS does not declare: {unknown}"
    assert len(assigned) == len(parsed), "a claim was assigned twice or not at all"

    report = REPO / "thesis" / "stats-report.md"
    if not report.exists():
        pytest.skip("report not generated yet; run thesis/run_stats.py")
    text = report.read_text()
    for key, label, _ in BUCKETS:
        n = sum(1 for b in assigned.values() if b == key)
        assert f"**{label} ({n}).**" in text, (
            f"report does not print {label} at {n}; regenerate with thesis/run_stats.py")


def test_paired_claims_carry_no_gate_p(claims):
    """R-25. `gate_p` is the PRE-registration; a paired design never reads it.

    Two of the eight Holm survivors stored their own achieved p-value there,
    bit-identical to what `evaluate()` recomputes: `P3-ROI-M2.0-512-ondevice` held
    2.501505063220086e-14 and `P3-R13-owlv2-vs-vlm` held 2.2605981543610277e-07.
    The pre-registration for both was prose, so the field was empty and the result
    got written into it. Inert, because the paired branch of `evaluate` never reads
    `gate_p` — but a field named "the bar we set in advance" holding the number we
    got is the exact shape of the mistake this registry exists to prevent.
    """
    populated = [f"{c['id']}: gate_p={c['gate_p']}" for c in claims
                 if c.get("design") == "paired-binary" and c.get("gate_p") is not None]
    assert not populated, (
        "paired-binary claims carry a gate_p, which nothing reads and which has "
        "already been used to store an achieved p-value:\n  " + "\n  ".join(populated))


def test_the_stats_module_selfcheck_passes():
    """R-25. `python -m grounding.stats` had been exiting 1 since eacf746.

    The self-check asserted the English string "absence of a test" and kept
    asserting it after every reading was translated to Spanish. `make test` stayed
    green because `tests/test_stats.py` never enters that branch, so the module's
    own advertised check was the only thing that could catch the drift, and it was
    the broken thing. Running it from the suite closes that gap.
    """
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "grounding.stats"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"grounding.stats self-check failed:\n{r.stdout}\n{r.stderr}"


def test_no_generated_report_line_hand_counts_the_registry(claims):
    """R-25. A generated document must not carry a typed constant about itself.

    `run_stats.py` shipped "Solo tres afirmaciones se midieron íntegramente en la
    placa", then someone edited it by hand to "Seis" under a commit message saying
    a generated document should not carry a hand-counted constant. It still did; it
    just counted higher. Both counts are derived now, and this asserts the report
    agrees with the registry rather than with whoever last edited the string.
    """
    report = REPO / "thesis" / "stats-report.md"
    if not report.exists():
        pytest.skip("report not generated yet; run thesis/run_stats.py")
    text = report.read_text()
    spelled = {1: "Una", 2: "Dos", 3: "Tres", 4: "Cuatro", 5: "Cinco", 6: "Seis",
               7: "Siete", 8: "Ocho", 9: "Nueve", 10: "Diez"}
    n = sum(1 for c in claims if c.get("machine") == "jetson-orin-nano-8gb")
    want = spelled.get(n, str(n))
    assert f"{want} afirmaciones se midieron íntegramente en la placa" in text, (
        f"registry has {n} on-device claims; the report does not say so. "
        "Regenerate with thesis/run_stats.py.")


_SUPERSEDED = re.compile(r"SUPERSEDED\b[^]]*?\bby\s+([A-Za-z0-9.\-]+)", re.IGNORECASE)
_BARE_POSITIVE = {"pass", "yes", "gate pass", "ok", "pass "}


def test_supersede_markers_are_bidirectional_and_qualify_the_verdict(claims):
    """R-27. The marker went on the number that got better, not the one that got worse.

    R-14 wrote a supersede marker into the verdict of the claim it replaced. R-16
    wrote none, so `P3-E1-TRT-fps` kept reading headline "TensorRT fp16 lifts the
    co-resident carry rate 4.89 -> 6.15 FPS", verdict `PASS`, `machine:
    jetson-orin-nano-8gb` — for a configuration (`image_size` 768, against an IDLE
    llama-server) that R-16 proved was never deployed. The campaign README says it
    flatly: "E1's 'co-residency costs 0 FPS' is falsified."

    Two rules, because one alone was not enough to catch it:

    1. A `SUPERSEDED by X` marker must name a real claim, and X must name it back.
       A one-way link is what R-16 left; requiring both ends is what makes the
       omission fail rather than pass silently.
    2. A superseded claim may not still read as a bare `PASS`.
    """
    by_id = {c["id"]: c for c in claims}
    problems = []
    for c in claims:
        verdict = c.get("verdict") or ""
        m = _SUPERSEDED.search(verdict)
        if not m:
            continue
        successor = m.group(1).rstrip(",;.")
        if successor not in by_id:
            problems.append(f"{c['id']}: superseded by {successor!r}, which is not a claim id")
            continue
        back = by_id[successor].get("verdict") or ""
        if c["id"] not in back:
            problems.append(
                f"{c['id']} points at {successor}, but {successor}'s verdict never names it back. "
                "A one-way supersede link is how P3-E1-TRT-fps stayed at PASS for a day")
        if verdict.strip().lower() in _BARE_POSITIVE:
            problems.append(f"{c['id']}: superseded but the verdict still reads {verdict!r}")
    assert not problems, "supersede markers:\n  " + "\n  ".join(problems)


def test_readme_machine_table_is_generated_and_current():
    """R-26. The front door must not carry a hand-typed count of the registry.

    R-6 swept every number in README.md against the registry on 2026-07-21 and it
    resolved. No task owned the re-sweep, so by 23 July the file said "65
    afirmaciones" against a registry of 70, and its machine table read 47/13/3/2
    against a real 47/15/6/2 — under-reporting the wholly-on-device claims by half,
    which is the exact axis the entire first remediation wave was about.

    `run_stats.py` writes the table between HTML markers now. This asserts the
    committed block equals what the registry would render, so the front door cannot
    drift again without `make test` going red.
    """
    import sys
    sys.path.insert(0, str(REPO / "thesis"))
    from run_stats import MACHINE_BEGIN, MACHINE_END, load_claims, machine_table

    parsed, _ = load_claims()
    text = (REPO / "README.md").read_text()
    assert MACHINE_BEGIN in text and MACHINE_END in text, (
        "README.md lost the generated-block markers; run thesis/run_stats.py")
    got = text[text.index(MACHINE_BEGIN) + len(MACHINE_BEGIN):text.index(MACHINE_END)]
    assert machine_table(parsed).strip() == got.strip(), (
        "README.md machine table is stale against thesis/claims.json. "
        "Regenerate with thesis/run_stats.py.")


def test_readme_quotes_no_stale_claim_count(claims):
    """R-26. The registry grew 65 -> 70 and three prose sentences did not notice."""
    text = (REPO / "README.md").read_text()
    n = len(claims)
    stale = sorted({int(m) for m in re.findall(r"las (\d+) afirmaciones", text)} - {n})
    assert not stale, (
        f"README.md says 'las {stale} afirmaciones'; the registry holds {n}")


# The surfaces an agent or a reader hits before anything else. A wrong number here
# propagates into every later session; a wrong number in an experiment README is
# read by whoever is already looking at that experiment.
_FIRST_READ = ("README.md", "CLAUDE.md", "docs/questions/part5-anticipatory.md",
               "docs/questions/part6-flight.md", "thesis/00-esquema.md")

# Any mention of deflation on the same line clears it: the correct construction
# is "p = X, and p = Y al deflactar a N clips", which names both on one line.
_UNDEFLATED_OK = re.compile(r"undeflat|deflact|deflated", re.IGNORECASE)


def test_first_read_surfaces_cite_the_deflated_p(claims):
    """R-32/I2. An undeflated p may appear, but never bare.

    Found by R-32's spot-check of R-19: the Part V QUESTIONS banner told the reader
    "P5.2 is the properly powered claim (p = 3.05e-05, survives Holm)" - the
    undeflated value, in the one sentence on that page whose whole job is to say
    which figure to cite. CLAUDE.md and the auto-memory both had it right, so this
    was not a misunderstanding; it was the surface nothing swept twice.

    The undeflated number is legitimate content (it belongs in the derivation, and
    in a record of what was published before), so this does not forbid it. It
    requires the word that marks it as the superseded one on the same line.
    """
    import sys
    sys.path.insert(0, str(REPO / "thesis"))
    from run_stats import load_claims
    from grounding.stats import evaluate, mcnemar

    parsed, _ = load_claims()
    # p as it would read WITHOUT deflation, for every paired claim where deflating
    # actually moved it. Those are the only strings that can be quoted by mistake.
    undeflated, by_id = {}, {c.id: c for c in parsed}
    for c in parsed:
        if c.design != "paired-binary":
            continue
        counts = c.counts or {}
        if "b" not in counts or "c" not in counts:
            continue
        b, cc = counts["b"], counts["c"]
        if b + cc == 0:
            continue
        raw = mcnemar(b, cc)
        got = evaluate(c).p_value
        if got == got and abs(raw - got) > 1e-12:
            undeflated[c.id] = raw

    # Only `p = X` forms, never a bare number: 0.25 is also an IoU threshold, and
    # matching it loose flags every line in the repo that mentions IoU@0.25.
    # The trailing [.,] is stripped, not captured: "p = 0.25," would otherwise
    # parse as "0.25," -> ValueError -> silently skipped, which is how the same
    # scanner missed a real defect in P5.15's caveat (R-33).
    # greedy, then strip trailing sentence punctuation - a lazy quantifier here
    # captures a single digit, and a greedy one without the strip swallows the
    # comma in "p = 0.0016," so float() raises and the line is silently skipped.
    quoted = re.compile(r"\bp\s*=\s*([0-9][0-9.,]*(?:e[-+]?[0-9]+)?)", re.IGNORECASE)

    bad = []
    for rel in _FIRST_READ:
        for lineno, line in enumerate((REPO / rel).read_text().splitlines(), 1):
            if _UNDEFLATED_OK.search(line):
                continue
            for m in quoted.finditer(line):
                txt = m.group(1).rstrip(".,")
                try:
                    val = float(txt.replace(",", "."))
                except ValueError:
                    continue
                for cid, raw in undeflated.items():
                    # same to the precision the prose actually printed, AND
                    # attributable: p = 0,25 is McNemar for b=3, c=0 and also the
                    # p of four unrelated claims, so a loose match flags every
                    # correct sentence in the repo. Either the line names the claim
                    # or the value is small enough that coincidence is not credible.
                    if not (val and abs(val - raw) / raw < 0.02):
                        continue
                    if raw < 0.01 or cid.split("-")[0] in line or cid in line:
                        bad.append(
                            f"{rel}:{lineno} quotes {cid}'s undeflated p = {m.group(1)} bare "
                            f"(deflated: {evaluate(by_id[cid]).p_value:.3g})")
    assert not bad, (
        "first-read surfaces must cite the deflated p (HANDOFF I2):\n  " + "\n  ".join(bad))
