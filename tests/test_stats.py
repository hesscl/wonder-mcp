"""Tests for stats.py: rate ratio and confidence interval calculations."""

from __future__ import annotations

import math

import pytest

from wonder_mcp.stats import RateInput, RateRatioResult, rate_ratio


# ---------------------------------------------------------------------------
# RateInput validation
# ---------------------------------------------------------------------------


def test_rate_input_count_pop():
    r = RateInput(count=1000, population=100_000)
    assert r.crude_rate == pytest.approx(1000.0)  # per 100k by default


def test_rate_input_rate_only():
    r = RateInput(rate=12.5)
    assert r.crude_rate == 12.5


def test_rate_input_missing_raises():
    with pytest.raises(Exception):
        RateInput()  # no count/pop or rate


def test_rate_input_rate_per():
    r = RateInput(count=500, population=1_000_000, rate_per=1000)
    assert r.crude_rate == pytest.approx(0.5)


def test_rate_input_label():
    r = RateInput(count=100, population=1_000_000, label="Group A")
    assert r.label == "Group A"


# ---------------------------------------------------------------------------
# rate_ratio() — basic math
# ---------------------------------------------------------------------------


def _make(count: int, population: int, label: str = "") -> RateInput:
    return RateInput(count=count, population=population, label=label)


def test_rate_ratio_equal_rates():
    # 45000/150M vs 12000/40M: rate1 = 30/100k, rate2 = 30/100k → RR = 1.0
    r = rate_ratio(_make(45_000, 150_000_000), _make(12_000, 40_000_000))
    assert r.rate_ratio == pytest.approx(1.0, abs=1e-4)


def test_rate_ratio_higher_group1():
    r = rate_ratio(_make(2000, 100_000), _make(1000, 100_000))
    assert r.rate_ratio == pytest.approx(2.0, abs=1e-4)


def test_rate_ratio_ci_contains_true_value():
    """For large counts, CI should be narrow and contain the true RR."""
    r = rate_ratio(_make(50_000, 1_000_000), _make(25_000, 1_000_000))
    # True RR = 2.0
    assert r.ci_lower < 2.0 < r.ci_upper


def test_rate_ratio_ci_lower_lt_upper():
    r = rate_ratio(_make(5000, 200_000), _make(3000, 150_000))
    assert r.ci_lower < r.ci_upper


def test_rate_ratio_alpha_affects_ci_width():
    """Wider CI at lower alpha (e.g. 99% vs 95%)."""
    r95 = rate_ratio(_make(5000, 200_000), _make(3000, 150_000), alpha=0.05)
    r99 = rate_ratio(_make(5000, 200_000), _make(3000, 150_000), alpha=0.01)
    assert r99.ci_upper > r95.ci_upper
    assert r99.ci_lower < r95.ci_lower


def test_rate_ratio_rate_only_gives_nan_ci():
    r1 = RateInput(rate=15.0)
    r2 = RateInput(rate=10.0)
    r = rate_ratio(r1, r2)
    assert r.rate_ratio == pytest.approx(1.5, abs=1e-4)
    assert math.isnan(r.ci_lower)
    assert math.isnan(r.ci_upper)


def test_rate_ratio_zero_denominator_raises():
    with pytest.raises(ValueError, match="zero"):
        rate_ratio(_make(1000, 100_000), RateInput(rate=0.0))


def test_rate_ratio_interpretation_string():
    r = rate_ratio(
        _make(2000, 100_000, "Exposed"),
        _make(1000, 100_000, "Unexposed"),
    )
    assert "Exposed" in r.interpretation
    assert "Unexposed" in r.interpretation
    assert "2.0" in r.interpretation or "higher" in r.interpretation


def test_rate_ratio_method_named():
    r = rate_ratio(_make(5000, 200_000), _make(3000, 150_000))
    assert "Poisson" in r.method or "delta" in r.method.lower()


def test_rate_ratio_deterministic():
    """Same inputs → identical output."""
    g1 = _make(45_000, 150_000_000)
    g2 = _make(12_000, 40_000_000)
    r1 = rate_ratio(g1, g2)
    r2 = rate_ratio(g1, g2)
    assert r1.rate_ratio == r2.rate_ratio
    assert r1.ci_lower == r2.ci_lower
    assert r1.ci_upper == r2.ci_upper


def test_rate_ratio_result_is_pydantic():
    r = rate_ratio(_make(5000, 200_000), _make(3000, 150_000))
    assert isinstance(r, RateRatioResult)
    d = r.model_dump()
    assert "rate_ratio" in d
    assert "ci_lower" in d
    assert "ci_upper" in d
    assert "method" in d
    assert "interpretation" in d


def test_rate_ratio_one_zero_count():
    """Zero count in group 1 — should not raise (uses 0.5 adjustment)."""
    r = rate_ratio(_make(0, 100_000), _make(1000, 100_000))
    assert r.rate_ratio < 1.0
    # CI should still be computable (not NaN)
    assert not math.isnan(r.ci_lower)


# ---------------------------------------------------------------------------
# Verification scenario from plan
# ---------------------------------------------------------------------------


def test_plan_verification_example():
    """plan verification: count=45000/150M vs 12000/40M → RR ≈ 1.0."""
    r = rate_ratio(
        RateInput(count=45_000, population=150_000_000),
        RateInput(count=12_000, population=40_000_000),
    )
    # Both rates equal 30/100k → RR = 1.0
    assert r.rate_ratio == pytest.approx(1.0, abs=0.001)
    assert r.ci_lower < 1.0 < r.ci_upper
