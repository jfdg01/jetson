"""Regression gate for the retroactive-inference module.

The module's job is as much to REFUSE tests as to run them, so most of what is
locked here is refusal behaviour: undefined results stay undefined, ties do not
become evidence of equality, and underpowered designs are flagged as such. Those
are the properties a later session could silently break while "improving" the
reporting, and they are the ones a thesis defence depends on.
"""

from __future__ import annotations

import math

import pytest

from grounding.stats import (
    Claim,
    discordant_counts,
    evaluate,
    fisher_exact,
    holm_bonferroni,
    mcnemar,
    min_discordant_for_significance,
    min_successes_for_gate,
    paired_continuous,
    wilson_ci,
)


# --- interval estimation --------------------------------------------------

def test_wilson_never_leaves_the_unit_interval():
    for k, n in [(0, 6), (25, 25), (24, 25), (1, 3), (56, 56)]:
        lo, hi = wilson_ci(k, n)
        assert 0.0 <= lo <= hi <= 1.0


def test_wilson_zero_successes_is_not_certainty():
    # The Wald interval gives [0, 0] here, asserting the true rate is exactly 0
    # from six observations. Wilson must not.
    lo, hi = wilson_ci(0, 6)
    assert lo == 0.0
    assert hi > 0.3


def test_wilson_perfect_score_is_not_certainty():
    lo, hi = wilson_ci(56, 56)
    assert hi == 1.0
    assert lo < 0.95, "56/56 must not imply a lower bound of 1.0"


def test_wilson_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        wilson_ci(7, 6)
    with pytest.raises(ValueError):
        wilson_ci(1, 0)


# --- McNemar --------------------------------------------------------------

@pytest.mark.parametrize("b,c,expected", [
    (4, 0, 0.125),      # P5.1 shape
    (16, 0, 2 * 0.5 ** 16),
    (3, 0, 0.25),       # P5.19 shape
    (1, 0, 1.0),        # a single discordant pair proves nothing
    (2, 2, 1.0),
])
def test_mcnemar_matches_hand_computed_binomial(b, c, expected):
    assert mcnemar(b, c) == pytest.approx(expected, rel=1e-9)


def test_mcnemar_no_discordant_pairs_is_undefined_not_unity():
    # Returning 1.0 would read as "tested, arms equal". They were not tested.
    assert math.isnan(mcnemar(0, 0))


def test_mcnemar_is_symmetric_two_sided():
    assert mcnemar(5, 2) == pytest.approx(mcnemar(2, 5))


def test_mcnemar_one_sided_is_not_symmetric():
    assert mcnemar(5, 0, "greater") < mcnemar(0, 5, "greater")


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar(-1, 2)


# --- pairing extraction ---------------------------------------------------

def test_discordant_counts_drops_unmatched_items():
    # An item that only ran in one arm must not be scored as a failure in the
    # other. That is how a crashed run becomes a fabricated result.
    a = {"c1": 1, "c2": 1, "c3": 0, "c4": 1}
    b = {"c1": 0, "c2": 1, "c3": 1, "c5": 0}
    assert discordant_counts(a, b) == (1, 1, 3)


def test_discordant_counts_perfect_tie():
    arm = {f"c{i}": 1 for i in range(24)}
    assert discordant_counts(arm, dict(arm)) == (0, 0, 24)


# --- the retrospective-power guard ---------------------------------------

def test_five_paired_items_cannot_reach_significance():
    # The single most consequential fact about this repo's Part V select arms:
    # a 5-cell paired design has a p-value floor of 0.0625 two-sided. Several
    # YES/NO verdicts rest on such designs.
    assert min_discordant_for_significance(5) is None


def test_six_paired_items_can_only_just_reach_it():
    assert min_discordant_for_significance(6) == 6


def test_larger_designs_need_proportionally_fewer_flips():
    assert min_discordant_for_significance(26) == 6
    assert min_discordant_for_significance(56) == 6


def test_min_successes_for_gate_is_monotone_in_the_gate():
    assert min_successes_for_gate(25, 0.5) < min_successes_for_gate(25, 0.72)


def test_a_demanding_gate_is_unreachable_even_at_n25():
    # A gate of 90% cannot be beaten significantly with 25 items: a perfect
    # 25/25 gives p = 0.9**25 = 0.072. So a pre-registered "must exceed 90%"
    # floor at this n is a target that no result could ever have cleared on
    # statistical grounds - it can only be cleared descriptively.
    assert min_successes_for_gate(25, 0.9) is None
    assert min_successes_for_gate(25, 0.72) == 23


def test_impossible_gate_returns_none():
    assert min_successes_for_gate(5, 0.999) is None


# --- unpaired -------------------------------------------------------------

def test_fisher_on_the_generalisation_result():
    p_unpaired = fisher_exact(21, 25, 5, 25)
    assert p_unpaired < 0.001


def test_the_paired_test_is_not_always_the_smaller_p_and_is_still_the_right_one():
    """Locks a methodological trap rather than a numeric property.

    On P5.2's numbers the unpaired Fisher test gives a SMALLER p (1.2e-05) than
    the paired McNemar (3.1e-05), because McNemar discards the 9 concordant
    clips and draws all its power from the 16 discordant ones. It is therefore
    tempting to report Fisher.

    That would be p-hacking by test selection. The 25 clips were measured under
    both arms, so the observations are paired, and the test follows from the
    design and not from which number is prettier. This assertion exists so that
    a later session tuning the report cannot quietly switch to the smaller
    p-value and call it an improvement.
    """
    assert fisher_exact(21, 25, 5, 25) < mcnemar(16, 0)


# --- multiplicity ---------------------------------------------------------

def test_holm_is_monotone_and_conservative():
    h = holm_bonferroni({"a": 0.001, "b": 0.04, "c": 0.5})
    assert h["a"]["p_holm"] <= h["b"]["p_holm"] <= h["c"]["p_holm"]
    assert all(h[k]["p_holm"] >= h[k]["p_raw"] for k in h)


def test_holm_undefined_tests_do_not_consume_alpha():
    with_nan = holm_bonferroni({"a": 0.02, "nan1": float("nan"), "nan2": float("nan")})
    alone = holm_bonferroni({"a": 0.02})
    assert with_nan["a"]["p_holm"] == alone["a"]["p_holm"]
    assert not with_nan["nan1"]["reject"]


# --- claim evaluation -----------------------------------------------------

def _claim(**kw):
    base = dict(id="X", part="V", headline="h", design="paired-binary", verdict="NO",
                n_rows=5, n_effective=5, independence_note="", data_status="counts_only",
                counts={"b": 0, "c": 0})
    base.update(kw)
    return Claim(**base)


def test_tie_reports_absence_of_a_test():
    out = evaluate(_claim(id="P5.10", n_rows=24, n_effective=24, counts={"b": 0, "c": 0}))
    assert math.isnan(out.p_value)
    assert "ausencia de prueba" in out.reading


def test_underpowered_design_is_flagged_even_when_it_looks_decisive():
    out = evaluate(_claim(id="P5.14", counts={"b": 4, "c": 0}))
    assert not out.could_ever_reach_alpha
    assert "sin potencia por construcción" in out.reading


def test_missing_data_is_queued_not_tested():
    out = evaluate(_claim(data_status="missing"))
    assert math.isnan(out.p_value)
    assert "re-ejecución" in out.reading


def test_single_arm_against_a_gate():
    out = evaluate(_claim(id="P5.15", design="single-arm-binary", n_rows=25, n_effective=25,
                          counts={"k": 24, "n": 25}, gate_p=18 / 25))
    assert out.ci is not None and out.ci[0] > 0.75
    assert out.p_value < 0.05


def test_single_arm_without_a_gate_reports_interval_only():
    out = evaluate(_claim(design="single-arm-binary", n_rows=23, n_effective=23,
                          counts={"k": 5, "n": 23}, gate_p=None))
    assert math.isnan(out.p_value)
    assert out.ci is not None


# --- paired continuous ----------------------------------------------------

def test_paired_continuous_recovers_the_median_difference():
    r = paired_continuous([4.85, 4.90, 4.80, 4.88], [1.85, 1.90, 1.80, 1.88])
    assert r["median_diff"] == pytest.approx(3.0, abs=1e-6)
    assert r["ci95_median_diff"][0] > 2.5


def test_paired_continuous_all_zero_differences_is_undefined():
    r = paired_continuous([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert math.isnan(r["p_value"])


def test_paired_continuous_rejects_ragged_input():
    with pytest.raises(ValueError):
        paired_continuous([1.0, 2.0], [1.0])


# --- R-3: no dispatch branch may ignore n_effective -----------------------

def _probe(design: str, counts: dict, n_rows: int, n_effective: int) -> Claim:
    return Claim(
        id=f"probe-{design}", part="test", headline="probe", design=design,
        verdict="n/a", n_rows=n_rows, n_effective=n_effective,
        independence_note="synthetic probe", data_status="per_item", counts=counts,
    )


# One entry per design that consumes counts. `counts` is chosen so that deflating
# from n_rows to n_effective MUST move the p-value or the interval.
DEFLATION_PROBES = [
    ("paired-binary", {"b": 6, "c": 0}, 12, 6),
    ("single-arm-binary", {"k": 12, "n": 12}, 12, 6),
    ("unpaired-binary", {"k1": 12, "n1": 12, "k2": 2, "n2": 12}, 12, 6),
    ("descriptive", {"k": 6, "n": 12}, 12, 6),
]


def test_paired_deflation_measures_from_the_scale_bc_were_recorded_at():
    """R-22. Deflate b/c from `counts["n"]` when it exists, not from `n_rows`.

    Seven registry claims record discordants ALREADY collapsed to the clip scale:
    `counts["n"]=6` beside `n_rows=12`, with the independence_note spelling it out
    ("12 rows, 6 observations"). R-3 deflated every paired claim from n_rows, so
    those seven were halved a second time. It read as conservative, which is why it
    survived review, but it is just wrong: E18 -- the pivot claim of the whole
    Part IV -> V argument -- printed p=0.5 where the correct value is 0.0625, and
    E19 was published as "0 discordant pairs, absence of a test" when it has one.

    The tell was in the repo the whole time: the hand-written caveats carried the
    right numbers, so `stats-report.md` contradicted its own prose 112 lines apart.
    A generated document disagreeing with itself is the cheapest possible signal and
    nothing was checking for it.
    """
    already_collapsed = _probe("paired-binary", {"b": 5, "c": 0, "n": 6}, 12, 6)
    raw_rows = _probe("paired-binary", {"b": 5, "c": 0}, 12, 6)

    # b/c are at the clip scale and n_effective IS the clip count: nothing to do.
    assert evaluate(already_collapsed).p_value == pytest.approx(0.0625)
    # No counts["n"], so n_rows is the honest fallback and 5/12 -> ~2/6 still deflates.
    assert evaluate(raw_rows).p_value == pytest.approx(0.5)


@pytest.mark.parametrize("design,counts,n_rows,n_eff", DEFLATION_PROBES)
def test_every_design_branch_honours_n_effective(design, counts, n_rows, n_eff):
    """R-3. A branch that reads raw counts and ignores n_effective overstates us.

    This is not hypothetical. `paired-binary` computed McNemar on the full
    discordant counts while using n_effective for the reachability floor, so all
    16 deflated paired claims reported a p-value that was too small - always in
    the direction that favours the thesis. The bug survived because each branch
    was reviewed on its own; nothing asserted the property across the dispatch.

    Any new design added to `evaluate` must be added here too.
    """
    full = evaluate(_probe(design, counts, n_rows, n_rows))
    deflated = evaluate(_probe(design, counts, n_rows, n_eff))

    moved_p = not (math.isnan(full.p_value) and math.isnan(deflated.p_value)) and (
        math.isnan(full.p_value) != math.isnan(deflated.p_value)
        or full.p_value != deflated.p_value
    )
    moved_ci = full.ci != deflated.ci
    assert moved_p or moved_ci, (
        f"{design}: deflating {n_rows} -> {n_eff} changed neither the p-value "
        f"({full.p_value} -> {deflated.p_value}) nor the interval "
        f"({full.ci} -> {deflated.ci}). The branch is ignoring n_effective."
    )


def test_deflation_never_strengthens_a_paired_result():
    """Deflation is a correction, not a lever. It may only ever weaken."""
    full = evaluate(_probe("paired-binary", {"b": 8, "c": 0}, 16, 16))
    deflated = evaluate(_probe("paired-binary", {"b": 8, "c": 0}, 16, 8))
    assert deflated.p_value >= full.p_value


def test_paired_continuous_refuses_to_deflate_a_rank_test():
    """Rescaling a count cannot deflate a rank test; refusing is the honest path."""
    out = evaluate(_probe(
        "paired-continuous",
        {"x": [4.9, 4.8, 4.85, 4.88, 4.9, 4.8], "y": [1.9, 1.8, 1.85, 1.88, 1.9, 1.8]},
        6, 3,
    ))
    assert math.isnan(out.p_value)
    assert "deflaci" in out.reading
