"""Retroactive statistical inference for the thesis campaigns.

Why this module exists
----------------------
Parts I-VI were run as a lab notebook: a gate was pre-registered ("WSEL must
clear 4/5"), the arm was run, the count was compared to the gate by eye, and a
YES/NO was recorded. That is a legitimate way to steer a research programme and
an illegitimate way to defend a claim in a thesis. Nowhere in the repo was a
p-value or a confidence interval computed.

Adding p-values after the fact is easy and mostly worthless. The hard part -
what this module is actually for - is refusing to compute the ones that would
mislead. Three failure modes are specifically guarded:

1. **Wrong design.** McNemar needs the SAME items under both arms. Applying it
   to two independent groups inflates significance. `mcnemar()` takes discordant
   counts only, so an unpaired dataset cannot reach it by accident.

2. **Pseudo-replication.** "6 clips x 2 repetitions" is 6 observations, not 12,
   and 5 cells cut from one video are not 5 independent trials. Every claim
   carries `n_effective` separately from `n_rows`, and the report prints both.

3. **Designs that could never have answered their question.** A 5-item paired
   comparison cannot reach p < 0.05 two-sided even if every pair flips: the
   floor is p = 0.0625. Several campaigns in this repo are in that category, and
   `min_discordant_for_significance()` says so up front. A NO from such a design
   is not evidence of no effect - it is evidence of no experiment. This is the
   most useful thing here and the reason the module is not just three scipy
   calls.

Everything exact. No normal approximations: n is small enough throughout that
the chi-square McNemar and the Wald interval would both be wrong, and Wilson +
exact binomial cost nothing.

Run `python -m grounding.stats` for the self-check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import comb
from typing import Literal, Sequence

from scipy import stats

Alternative = Literal["two-sided", "greater", "less"]


# --------------------------------------------------------------------------
# interval estimation
# --------------------------------------------------------------------------

def wilson_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Used instead of the textbook Wald interval because Wald is badly wrong at
    the sample sizes and the extreme proportions this repo is full of: for
    24/25 it produces an upper bound above 1, and for 0/6 it produces the
    degenerate [0, 0], which would assert certainty from six observations.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError(f"k={k} out of range for n={n}")
    lo, hi = stats.binomtest(k, n).proportion_ci(confidence_level=conf, method="wilson")
    return float(lo), float(hi)


def deflate_to_effective(k: int, n: int, n_effective: int) -> tuple[int, int]:
    """Rescale an observed k/n down to the number of independent observations.

    This repo is full of counts whose denominator is not a count of independent
    things: 10 SITL trials of one deterministic failure, 5 select cells cut from
    3 videos, 439 captions over 316 images. Reporting an interval on the inflated
    denominator claims precision that was never purchased, and it is the single
    most common way a lab notebook overstates itself.

    The proportion is preserved and the denominator is replaced by
    `n_effective`, which is a design-effect correction with deff = n /
    n_effective. It is deliberately blunt: it widens the interval and weakens the
    p-value, never the reverse, so it cannot manufacture a result.
    """
    if n_effective >= n or n <= 0:
        return k, n
    n_eff = max(1, int(n_effective))
    return min(n_eff, round(k * n_eff / n)), n_eff


# --------------------------------------------------------------------------
# single arm against a pre-registered gate
# --------------------------------------------------------------------------

def binomial_gate_test(k: int, n: int, gate_p: float,
                       alternative: Alternative = "greater") -> float:
    """Exact binomial p for 'k/n beats a gate of gate_p'.

    The gate is a *probability*, not a count: a pre-registered floor of 18/25
    means gate_p = 0.72. The null is that the arm's true success rate is exactly
    the gate; a small p means the observed count is hard to explain by an arm
    sitting at the threshold.

    Caveat that belongs in the write-up: several gates in this repo were set
    after seeing pilot data from the same system, which weakens the null.
    """
    if not 0.0 <= gate_p <= 1.0:
        raise ValueError("gate_p is a probability")
    return float(stats.binomtest(k, n, gate_p, alternative=alternative).pvalue)


# --------------------------------------------------------------------------
# paired binary: the workhorse for A/B arms over the same clips
# --------------------------------------------------------------------------

def mcnemar(b: int, c: int, alternative: Alternative = "two-sided") -> float:
    """Exact McNemar test on the discordant pairs.

    b = items where arm A succeeded and arm B failed.
    c = items where arm B succeeded and arm A failed.

    Concordant pairs carry no information about which arm is better and are
    deliberately not an argument: passing n would invite treating 24/24 vs 24/24
    as strong evidence of equality, which it is not. It is 0 discordant pairs,
    i.e. no evidence in either direction.

    Exact means binomial(b, b+c, 0.5), not the chi-square approximation, which
    is invalid for the b+c <= 5 that most of these campaigns produce.
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n_disc = b + c
    if n_disc == 0:
        # Undefined rather than 1.0: there is no test, and returning a p-value
        # of 1.0 reads as "tested, found equal" instead of "not tested".
        return float("nan")
    return float(stats.binomtest(b, n_disc, 0.5, alternative=alternative).pvalue)


def discordant_counts(arm_a: dict[str, int], arm_b: dict[str, int]) -> tuple[int, int, int]:
    """(b, c, n_paired) from two {item_id: 0|1} maps.

    Only items present in BOTH arms are paired. Items in one arm only are
    dropped and counted out, because silently treating them as failures is how a
    missing run becomes a result.
    """
    shared = sorted(set(arm_a) & set(arm_b))
    b = sum(1 for k in shared if arm_a[k] == 1 and arm_b[k] == 0)
    c = sum(1 for k in shared if arm_a[k] == 0 and arm_b[k] == 1)
    return b, c, len(shared)


# --------------------------------------------------------------------------
# unpaired binary
# --------------------------------------------------------------------------

def fisher_exact(k1: int, n1: int, k2: int, n2: int,
                 alternative: Alternative = "two-sided") -> float:
    """Fisher exact test for two independent groups.

    Only correct when the arms ran on DIFFERENT items. If they ran on the same
    items, this throws away the pairing and is substantially less powerful -
    use mcnemar().
    """
    table = [[k1, n1 - k1], [k2, n2 - k2]]
    return float(stats.fisher_exact(table, alternative=alternative)[1])


# --------------------------------------------------------------------------
# paired continuous (latencies, IoU, pixel error)
# --------------------------------------------------------------------------

def paired_continuous(x: Sequence[float], y: Sequence[float],
                      alternative: Alternative = "two-sided") -> dict:
    """Wilcoxon signed-rank on paired measurements, plus a bootstrap CI.

    Non-parametric because acquire latencies are right-skewed and n is small, so
    a t-test's normality assumption is doing unearned work.
    """
    if len(x) != len(y):
        raise ValueError("paired data must be the same length")
    diffs = [a - b for a, b in zip(x, y)]
    n_nonzero = sum(1 for d in diffs if d != 0)
    out = {"n": len(x), "n_nonzero": n_nonzero,
           "median_diff": float(stats.scoreatpercentile(diffs, 50))}
    if n_nonzero == 0:
        out["p_value"] = float("nan")
        out["note"] = "all differences are exactly zero; no test possible"
        return out
    out["p_value"] = float(stats.wilcoxon(x, y, alternative=alternative).pvalue)
    res = stats.bootstrap((diffs,), lambda d, axis=-1: stats.scoreatpercentile(d, 50, axis=axis),
                          confidence_level=0.95, n_resamples=10000,
                          method="percentile", rng=0)
    out["ci95_median_diff"] = (float(res.confidence_interval.low),
                              float(res.confidence_interval.high))
    return out


# --------------------------------------------------------------------------
# the retrospective-power guard: could this design ever have worked?
# --------------------------------------------------------------------------

def min_discordant_for_significance(n_pairs: int, alpha: float = 0.05,
                                    alternative: Alternative = "two-sided") -> int | None:
    """Smallest all-one-way discordant count reaching alpha, or None if impossible.

    Answers the question a thesis committee asks about an n=5 arm: *if the
    result had been maximally favourable, could it have been significant at
    all?* For a two-sided exact McNemar the answer is no until n_pairs >= 6.

    This is a statement about the DESIGN, computed from n alone, and is
    therefore legitimate to apply after the fact - unlike post-hoc "observed
    power", which is just a restatement of the p-value.
    """
    for d in range(1, n_pairs + 1):
        if stats.binomtest(d, d, 0.5, alternative=alternative).pvalue <= alpha:
            return d
    return None


def min_successes_for_gate(n: int, gate_p: float, alpha: float = 0.05) -> int | None:
    """Smallest k in k/n that beats gate_p at alpha (one-sided), or None."""
    for k in range(n + 1):
        if stats.binomtest(k, n, gate_p, alternative="greater").pvalue <= alpha:
            return k
    return None


# --------------------------------------------------------------------------
# multiplicity
# --------------------------------------------------------------------------

def holm_bonferroni(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm-Bonferroni step-down correction over a family of claims.

    This repo ran dozens of gated comparisons across six parts. Reporting each
    uncorrected invites the obvious objection that one in twenty clears by
    chance. Holm is used over Bonferroni because it is uniformly more powerful
    at the same family-wise error rate, and over Benjamini-Hochberg because
    these are confirmatory gates, not a screening exercise.

    NaN p-values (undefined tests) are excluded from the family: a test that did
    not happen must not consume alpha.
    """
    live = {k: v for k, v in pvalues.items() if v == v}  # drops NaN
    ordered = sorted(live.items(), key=lambda kv: kv[1])
    m = len(ordered)
    out: dict[str, dict] = {}
    running_max = 0.0
    for i, (key, p) in enumerate(ordered):
        adj = min(1.0, max(running_max, (m - i) * p))
        running_max = adj
        out[key] = {"p_raw": p, "p_holm": adj, "reject": adj <= alpha}
    for key in pvalues:
        if key not in out:
            out[key] = {"p_raw": float("nan"), "p_holm": float("nan"), "reject": False}
    return out


# --------------------------------------------------------------------------
# the claim record
# --------------------------------------------------------------------------

Design = Literal[
    "paired-binary", "unpaired-binary", "single-arm-binary",
    "paired-continuous", "descriptive",
]


@dataclass
class Claim:
    """One gated claim, with enough provenance to defend or retract it."""
    id: str
    part: str
    headline: str
    design: Design
    verdict: str                       # as recorded in the ledger at the time
    n_rows: int                        # rows in the raw data
    n_effective: int                   # independent observations; <= n_rows
    independence_note: str             # WHY they differ, in words
    data_status: Literal["per_item", "counts_only", "missing"]
    data_paths: list[str] = field(default_factory=list)
    # Path to the frozen scene/clip set the rows were drawn from, when one
    # exists. `independence_note` is prose and a reader has to trust it; this is
    # the machine anchor that lets a test count the distinct source clips itself
    # and refuse an n_effective the data does not support (R-4).
    scene_set: str | None = None
    # Which machine produced the number (R-2). `both` is the common and honest
    # answer across Parts IV-V: the VLM anchor ran on the Orin while the SAM2
    # carry ran on the 3090 under a rate cap. The thesis premise is edge
    # deployment, so a claim that cannot say where it was measured cannot be
    # cited in support of it. Derivation per claim:
    # experiments/2026-07-21-machine-disclosure/README.md.
    machine: Literal["jetson-orin-nano-8gb", "rtx-3090", "both", "n/a"] | None = None
    # design-specific payload
    counts: dict = field(default_factory=dict)
    gate_p: float | None = None
    caveats: str = ""


@dataclass
class Outcome:
    """What the test says, plus what it refuses to say."""
    claim_id: str
    test: str
    p_value: float
    ci: tuple[float, float] | None
    n_effective: int
    could_ever_reach_alpha: bool
    reading: str

    def line(self) -> str:
        p = "indefinido" if self.p_value != self.p_value else f"{self.p_value:.4g}"
        ci = f"[{self.ci[0]:.3f}, {self.ci[1]:.3f}]" if self.ci else "-"
        return f"{self.claim_id:28s} {self.test:18s} n={self.n_effective:<4d} p={p:<10s} CI95={ci:16s} {self.reading}"


def evaluate(claim: Claim) -> Outcome:
    """Run the right test for the claim's design, or refuse and say why.

    Code and docstrings here are English; every string that ends up in front of
    a reader is Spanish, because the only consumer is a Spanish thesis and a
    table with English cells in a Spanish document is a defect, not a detail.
    """
    if claim.data_status == "missing":
        return Outcome(claim.id, "ninguna", float("nan"), None, claim.n_effective, False,
                       "SIN DATOS - no se defiende; en cola de re-ejecución")

    if claim.design == "paired-binary":
        b_obs, c_obs = claim.counts["b"], claim.counts["c"]
        # R-3. The discordant counts must be put on the SAME effective scale as the
        # reachability floor below, which has used n_effective since day one. Deflating
        # only the floor and not the counts made every paired p-value too small - in the
        # direction that favours us - across the 16 deflated paired claims.
        b, _ = deflate_to_effective(b_obs, claim.n_rows, claim.n_effective)
        c, _ = deflate_to_effective(c_obs, claim.n_rows, claim.n_effective)
        p = mcnemar(b, c, "two-sided")
        note = "" if (b, c) == (b_obs, c_obs) else f" [deflactado desde b={b_obs}, c={c_obs}]"
        floor = min_discordant_for_significance(claim.n_effective)
        reachable = floor is not None
        if b + c == 0:
            reading = ("0 pares discordantes - los brazos son indistinguibles con estos datos. "
                       "No es equivalencia; es ausencia de prueba.")
        elif not reachable:
            reading = (f"n={claim.n_effective} pares no alcanzan alpha=0,05 bilateral "
                       "ni volteando todos. Diseño sin potencia por construcción.")
        elif p <= 0.05:
            reading = f"significativa (b={b}, c={c})"
        else:
            reading = (f"no significativa (b={b}, c={c}); hacían falta >={floor} discordantes "
                       f"en una dirección, hubo {max(b, c)}")
        return Outcome(claim.id, "McNemar exacta", p, None, claim.n_effective, reachable,
                       reading + note)

    if claim.design == "single-arm-binary":
        k_obs, n_obs = claim.counts["k"], claim.counts["n"]
        k, n = deflate_to_effective(k_obs, n_obs, claim.n_effective)
        ci = wilson_ci(k, n)
        note = "" if n == n_obs else f" [deflactado desde {k_obs}/{n_obs}: ver independence_note]"
        if claim.gate_p is None:
            return Outcome(claim.id, "IC de Wilson", float("nan"), ci, claim.n_effective, False,
                           "sin puerta pre-registrada; solo intervalo" + note)
        p = binomial_gate_test(k, n, claim.gate_p, "greater")
        need = min_successes_for_gate(n, claim.gate_p)
        reachable = need is not None and need <= n
        reading = (f"{k_obs}/{n_obs} contra puerta {claim.gate_p:.2f}; "
                   + (f"hacían falta >={need}/{n} para alpha=0,05" if need is not None
                      else "ningún k habría alcanzado alpha") + note)
        return Outcome(claim.id, "binomial exacta", p, ci, claim.n_effective, reachable, reading)

    if claim.design == "unpaired-binary":
        cn = claim.counts
        # R-3. Same correction as the paired branch. No registry claim needs it today
        # (the one unpaired claim is 12 -> 12), but a branch that silently ignores
        # n_effective is a trap for the next claim that does.
        k1, n1 = deflate_to_effective(cn["k1"], cn["n1"], claim.n_effective)
        k2, n2 = deflate_to_effective(cn["k2"], cn["n2"], claim.n_effective)
        p = fisher_exact(k1, n1, k2, n2)
        note = "" if (n1, n2) == (cn["n1"], cn["n2"]) else " [deflactado]"
        return Outcome(claim.id, "Fisher exacta", p, None, claim.n_effective, True,
                       f"{cn['k1']}/{cn['n1']} contra {cn['k2']}/{cn['n2']} "
                       f"(grupos independientes){note}")

    if claim.design == "paired-continuous":
        # Needs the per-item values. Several campaigns stored only a median or a
        # correlation coefficient, and a p-value cannot be reconstructed from
        # those - so this refuses rather than inventing one.
        x, y = claim.counts.get("x"), claim.counts.get("y")
        if not x or not y:
            return Outcome(claim.id, "ninguna", float("nan"), None, claim.n_effective, False,
                           "solo sobreviven estadísticos agregados; hacen falta los valores "
                           "por elemento para una prueba")
        if claim.n_effective < claim.n_rows:
            # R-3. A rank test cannot be deflated by rescaling a count, and picking
            # which rows to drop would be an arbitrary choice that moves the p-value.
            # Refusing is the honest option; the alternative is a Wilcoxon that
            # silently claims n_rows independent pairs.
            return Outcome(claim.id, "ninguna", float("nan"), None, claim.n_effective, False,
                           f"hay valores por elemento, pero n_effective={claim.n_effective} < "
                           f"n_rows={claim.n_rows} y un test de rangos no admite deflación por "
                           "reescalado; hace falta agregar por unidad independiente antes de probar")
        r = paired_continuous(x, y)
        return Outcome(claim.id, "Wilcoxon rangos con signo", r["p_value"], r["ci95_median_diff"],
                       claim.n_effective, True,
                       f"diferencia pareada mediana {r['median_diff']:.4g}")

    if claim.design == "descriptive":
        k_obs, n_obs = claim.counts.get("k", 0), claim.counts.get("n", 0)
        k, n = deflate_to_effective(k_obs, n_obs, claim.n_effective) if n_obs else (0, 0)
        ci = wilson_ci(k, n) if n else None
        note = "" if n == n_obs else f" [deflactado desde {k_obs}/{n_obs}]"
        return Outcome(claim.id, "descriptiva", float("nan"), ci, claim.n_effective, False,
                       "solo descriptiva - no se pre-registró ninguna hipótesis" + note)

    raise ValueError(f"unhandled design: {claim.design}")


# --------------------------------------------------------------------------
# self-check
# --------------------------------------------------------------------------

def _selfcheck() -> None:
    # Wilson beats Wald exactly where this repo lives: extreme proportions.
    lo, hi = wilson_ci(24, 25)
    assert 0.79 < lo < 0.81 and hi < 1.0, (lo, hi)
    lo, hi = wilson_ci(0, 6)
    assert lo == 0.0 and 0.3 < hi < 0.5, "0/6 must not imply certainty"

    # Exact McNemar against hand-computed binomials.
    assert abs(mcnemar(4, 0, "two-sided") - 2 * 0.5**4) < 1e-12
    assert abs(mcnemar(16, 0, "two-sided") - 2 * 0.5**16) < 1e-12
    assert abs(mcnemar(3, 0, "two-sided") - 0.25) < 1e-12
    assert abs(mcnemar(1, 0, "two-sided") - 1.0) < 1e-12
    assert mcnemar(0, 0) != mcnemar(0, 0), "0 discordant pairs must be NaN, not 1.0"

    # The retrospective-power guard: the headline design fact.
    assert min_discordant_for_significance(5) is None, "n=5 paired cannot reach 0.05 two-sided"
    assert min_discordant_for_significance(6) == 6
    assert min_discordant_for_significance(26) == 6

    # Pairing extraction, including the drop-unmatched rule.
    a = {"c1": 1, "c2": 1, "c3": 0, "c4": 1}
    b_ = {"c1": 0, "c2": 1, "c3": 1, "c5": 0}
    b, c, n = discordant_counts(a, b_)
    assert (b, c, n) == (1, 1, 3), (b, c, n)

    # Holm: monotone, and NaN never consumes alpha.
    h = holm_bonferroni({"a": 0.001, "b": 0.04, "c": 0.5, "d": float("nan")})
    assert h["a"]["p_holm"] <= h["b"]["p_holm"] <= h["c"]["p_holm"]
    assert h["a"]["reject"] and not h["c"]["reject"]
    assert not h["d"]["reject"]

    # A tie must report "no test", not "equal".
    tie = Claim(id="P5.10", part="V", headline="DD 24/24 vs RG 24/24",
                design="paired-binary", verdict="NO", n_rows=24, n_effective=24,
                independence_note="", data_status="counts_only", counts={"b": 0, "c": 0})
    o = evaluate(tie)
    assert o.p_value != o.p_value and "absence of a test" in o.reading

    # An underpowered design must be flagged even when the count looks decisive.
    weak = Claim(id="P5.1", part="V", headline="WARM 5/6 vs COLD 1/6",
                 design="paired-binary", verdict="YES", n_rows=6, n_effective=6,
                 independence_note="", data_status="counts_only", counts={"b": 4, "c": 0})
    assert abs(evaluate(weak).p_value - 0.125) < 1e-12

    # Paired continuous, with the all-zero-difference guard.
    r = paired_continuous([4.85, 4.90, 4.80], [1.85, 1.90, 1.80])
    assert r["p_value"] == r["p_value"] and abs(r["median_diff"] - 3.0) < 1e-9
    z = paired_continuous([1.0, 2.0], [1.0, 2.0])
    assert z["p_value"] != z["p_value"] and "no test possible" in z["note"]

    print("grounding.stats self-check OK")


if __name__ == "__main__":
    _selfcheck()
