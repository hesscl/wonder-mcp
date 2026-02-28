"""Tests for analytics functions: APC, rate difference, SMR, YLL, excess deaths."""

from __future__ import annotations

import math

import pytest

from wonder_mcp.stats import (
    APCResult,
    ExcessDeathsResult,
    RateInput,
    SMRResult,
    YLLResult,
    calculate_apc,
    calculate_excess_deaths,
    calculate_smr,
    calculate_yll,
    rate_difference,
)


# ---------------------------------------------------------------------------
# calculate_apc
# ---------------------------------------------------------------------------


def test_apc_flat_trend():
    """Flat rates → APC ≈ 0, trend = stable."""
    years = list(range(2010, 2021))
    rates = [10.0] * len(years)
    result = calculate_apc(years, rates)
    assert isinstance(result, APCResult)
    assert result.apc == pytest.approx(0.0, abs=0.01)
    assert result.trend == "stable"


def test_apc_increasing_trend():
    """Linearly increasing rates → positive APC, trend = increasing."""
    years = list(range(2010, 2021))
    # 5% annual increase
    rates = [10.0 * (1.05 ** i) for i in range(len(years))]
    result = calculate_apc(years, rates)
    assert result.apc == pytest.approx(5.0, abs=0.5)
    assert result.trend == "increasing"
    assert result.p_value < 0.05


def test_apc_decreasing_trend():
    """Linearly decreasing rates → negative APC, trend = decreasing."""
    years = list(range(2010, 2021))
    rates = [10.0 * (0.95 ** i) for i in range(len(years))]
    result = calculate_apc(years, rates)
    assert result.apc == pytest.approx(-5.0, abs=0.5)
    assert result.trend == "decreasing"
    assert result.p_value < 0.05


def test_apc_ci_contains_true_apc():
    years = list(range(2000, 2021))
    rates = [10.0 * (1.03 ** i) for i in range(len(years))]
    result = calculate_apc(years, rates)
    assert result.ci_lower <= result.apc <= result.ci_upper


def test_apc_ci_lower_lt_upper():
    years = list(range(2010, 2021))
    rates = [8.0 + 0.3 * i + 0.1 * (i % 3) for i in range(len(years))]
    result = calculate_apc(years, rates)
    assert result.ci_lower < result.ci_upper


def test_apc_wider_ci_at_99pct():
    # Use noisy data so slope_se > 0
    years = list(range(2010, 2021))
    noise = [0.0, 0.3, -0.2, 0.15, -0.1, 0.25, -0.05, 0.2, -0.15, 0.1, -0.05]
    rates = [10.0 * (1.03 ** i) + noise[i] for i in range(len(years))]
    r95 = calculate_apc(years, rates, alpha=0.05)
    r99 = calculate_apc(years, rates, alpha=0.01)
    assert r99.ci_lower < r95.ci_lower
    assert r99.ci_upper > r95.ci_upper


def test_apc_requires_positive_rates():
    with pytest.raises(ValueError, match="positive"):
        calculate_apc([2010, 2011, 2012], [10.0, -1.0, 12.0])


def test_apc_requires_at_least_3_points():
    with pytest.raises(ValueError, match="3"):
        calculate_apc([2010, 2011], [10.0, 11.0])


def test_apc_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        calculate_apc([2010, 2011, 2012], [10.0, 11.0])


def test_apc_result_is_pydantic():
    result = calculate_apc(list(range(2010, 2021)), [10.0 + i * 0.2 for i in range(11)])
    d = result.model_dump()
    assert "apc" in d and "ci_lower" in d and "ci_upper" in d and "p_value" in d
    assert "trend" in d and "interpretation" in d and "r_squared" in d


def test_apc_interpretation_contains_trend():
    years = list(range(2010, 2021))
    rates = [10.0 * (1.05 ** i) for i in range(len(years))]
    result = calculate_apc(years, rates)
    assert "increasing" in result.interpretation or "decreased" in result.interpretation or "increased" in result.interpretation


# ---------------------------------------------------------------------------
# rate_difference
# ---------------------------------------------------------------------------


def _ri(count: int, population: int, label: str = "") -> RateInput:
    return RateInput(count=count, population=population, label=label)


def test_rd_equal_rates():
    r = rate_difference(_ri(1000, 100_000), _ri(1000, 100_000))
    assert r.rate_difference == pytest.approx(0.0, abs=1e-6)


def test_rd_positive():
    r = rate_difference(_ri(2000, 100_000), _ri(1000, 100_000))
    assert r.rate_difference == pytest.approx(1000.0, abs=0.1)


def test_rd_negative():
    r = rate_difference(_ri(1000, 100_000), _ri(2000, 100_000))
    assert r.rate_difference == pytest.approx(-1000.0, abs=0.1)


def test_rd_ci_contains_zero_for_equal_rates():
    """For equal rates with large counts, CI should contain 0."""
    r = rate_difference(_ri(50_000, 1_000_000), _ri(50_000, 1_000_000))
    assert r.ci_lower < 0 < r.ci_upper


def test_rd_ci_lower_lt_upper():
    r = rate_difference(_ri(5000, 200_000), _ri(3000, 150_000))
    assert r.ci_lower < r.ci_upper


def test_rd_rate_only_gives_nan_ci():
    r1 = RateInput(rate=15.0)
    r2 = RateInput(rate=10.0)
    r = rate_difference(r1, r2)
    assert r.rate_difference == pytest.approx(5.0, abs=1e-6)
    assert math.isnan(r.ci_lower)
    assert math.isnan(r.ci_upper)


def test_rd_rate_se_method():
    r1 = RateInput(rate=15.0, rate_se=0.5)
    r2 = RateInput(rate=10.0, rate_se=0.4)
    r = rate_difference(r1, r2)
    assert r.rate_difference == pytest.approx(5.0, abs=1e-6)
    assert not math.isnan(r.ci_lower)
    expected_se = math.sqrt(0.5 ** 2 + 0.4 ** 2)
    from scipy import stats as sp_stats
    z = sp_stats.norm.ppf(0.975)
    assert r.ci_lower == pytest.approx(5.0 - z * expected_se, abs=1e-4)


def test_rd_wider_ci_at_99pct():
    r95 = rate_difference(_ri(5000, 200_000), _ri(3000, 150_000), alpha=0.05)
    r99 = rate_difference(_ri(5000, 200_000), _ri(3000, 150_000), alpha=0.01)
    assert r99.ci_upper > r95.ci_upper
    assert r99.ci_lower < r95.ci_lower


def test_rd_result_has_interpretation():
    r = rate_difference(_ri(2000, 100_000, "A"), _ri(1000, 100_000, "B"))
    assert "A" in r.interpretation
    assert "B" in r.interpretation


def test_rd_poisson_method_named():
    r = rate_difference(_ri(5000, 200_000), _ri(3000, 150_000))
    assert "Poisson" in r.method


# ---------------------------------------------------------------------------
# calculate_smr
# ---------------------------------------------------------------------------


def test_smr_equals_one_when_observed_equals_expected():
    # expected = 10.0 * 100000 / 100000 = 10.0; observed = 10
    r = calculate_smr(observed_deaths=10, expected_rate=10.0, population=100_000)
    assert isinstance(r, SMRResult)
    assert r.smr == pytest.approx(1.0, abs=1e-6)


def test_smr_gt_one_when_excess():
    # expected = 10/100k * 100k = 10; observed = 20 → SMR = 2
    r = calculate_smr(observed_deaths=20, expected_rate=10.0, population=100_000)
    assert r.smr == pytest.approx(2.0, abs=1e-4)


def test_smr_lt_one_when_deficit():
    r = calculate_smr(observed_deaths=5, expected_rate=10.0, population=100_000)
    assert r.smr == pytest.approx(0.5, abs=1e-4)


def test_smr_ci_lower_lt_upper():
    r = calculate_smr(observed_deaths=100, expected_rate=10.0, population=100_000)
    assert r.ci_lower < r.smr < r.ci_upper


def test_smr_zero_observed():
    r = calculate_smr(observed_deaths=0, expected_rate=10.0, population=100_000)
    assert r.smr == pytest.approx(0.0, abs=1e-6)
    assert r.ci_lower == pytest.approx(0.0, abs=1e-6)
    assert r.ci_upper > 0


def test_smr_ci_contains_null_when_smr_near_one():
    """With enough events and SMR=1, CI should straddle 1.0."""
    r = calculate_smr(observed_deaths=1000, expected_rate=100.0, population=1_000_000)
    assert r.ci_lower < 1.0 < r.ci_upper


def test_smr_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_smr(observed_deaths=-1, expected_rate=10.0, population=100_000)
    with pytest.raises(ValueError):
        calculate_smr(observed_deaths=10, expected_rate=0.0, population=100_000)
    with pytest.raises(ValueError):
        calculate_smr(observed_deaths=10, expected_rate=10.0, population=0)


def test_smr_wider_ci_at_99pct():
    r95 = calculate_smr(50, 10.0, 100_000, alpha=0.05)
    r99 = calculate_smr(50, 10.0, 100_000, alpha=0.01)
    assert r99.ci_lower < r95.ci_lower
    assert r99.ci_upper > r95.ci_upper


def test_smr_result_has_fields():
    r = calculate_smr(50, 10.0, 500_000)
    d = r.model_dump()
    assert all(k in d for k in ("smr", "ci_lower", "ci_upper", "observed", "expected", "interpretation"))


def test_smr_interpretation_mentions_direction():
    r = calculate_smr(200, 10.0, 100_000)
    assert "more" in r.interpretation


# ---------------------------------------------------------------------------
# calculate_yll
# ---------------------------------------------------------------------------


def _make_age_rows(age_deaths: dict[str, float]) -> list[dict]:
    return [{"Age Groups": ag, "Deaths": d} for ag, d in age_deaths.items()]


def test_yll_basic():
    rows = _make_age_rows({"25-29 years": 100, "35-39 years": 200})
    result = calculate_yll(rows)
    assert isinstance(result, YLLResult)
    # YLL = 100*(75-27) + 200*(75-37) = 100*48 + 200*38 = 4800 + 7600 = 12400
    assert result.total_yll == pytest.approx(12400.0, abs=1e-2)


def test_yll_excludes_ages_above_max():
    # Age group at or above max_age should contribute 0
    rows = _make_age_rows({"80-84 years": 500, "25-29 years": 100})
    result = calculate_yll(rows, max_age=75.0)
    # 80-84 midpoint=82 > 75 → 0 contribution; 25-29 midpoint=27 → 75-27=48
    assert result.total_yll == pytest.approx(100 * 48.0, abs=1e-2)


def test_yll_per_100k():
    rows = _make_age_rows({"25-29 years": 100})
    result = calculate_yll(rows, population=1_000_000)
    # YLL = 100 * (75-27) = 4800; per 100k = 4800/1000000*100000 = 480
    assert result.yll_per_100k == pytest.approx(480.0, abs=0.1)


def test_yll_no_population_gives_none():
    rows = _make_age_rows({"25-29 years": 100})
    result = calculate_yll(rows)
    assert result.yll_per_100k is None


def test_yll_suppressed_excluded():
    rows = [
        {"Age Groups": "25-29 years", "Deaths": "Suppressed"},
        {"Age Groups": "35-39 years", "Deaths": 100},
    ]
    result = calculate_yll(rows)
    assert "25-29 years" in result.groups_excluded
    assert result.total_yll == pytest.approx(100 * (75 - 37), abs=1e-2)


def test_yll_not_stated_excluded():
    rows = [
        {"Age Groups": "Not Stated", "Deaths": 50},
        {"Age Groups": "25-29 years", "Deaths": 100},
    ]
    result = calculate_yll(rows)
    assert "Not Stated" in result.groups_excluded


def test_yll_custom_max_age():
    rows = _make_age_rows({"25-29 years": 100})
    result_75 = calculate_yll(rows, max_age=75.0)
    result_65 = calculate_yll(rows, max_age=65.0)
    # 65-27=38 < 75-27=48
    assert result_65.total_yll < result_75.total_yll


def test_yll_result_fields():
    rows = _make_age_rows({"25-29 years": 100, "35-39 years": 200})
    result = calculate_yll(rows)
    d = result.model_dump()
    assert all(k in d for k in ("total_yll", "yll_per_100k", "age_groups", "interpretation", "method"))


def test_yll_interpretation_contains_total():
    rows = _make_age_rows({"25-29 years": 100})
    result = calculate_yll(rows)
    assert "4,800" in result.interpretation or "4800" in result.interpretation


# ---------------------------------------------------------------------------
# calculate_excess_deaths
# ---------------------------------------------------------------------------


def _make_series(year_deaths_pop: list[tuple[int, float, int]]) -> list[dict]:
    return [
        {"Year": yr, "Deaths": d, "Population": p}
        for yr, d, p in year_deaths_pop
    ]


def _flat_series(start=2015, end=2021, deaths=1000, pop=1_000_000):
    """Flat rate baseline + event year with same rate."""
    return _make_series([(yr, deaths, pop) for yr in range(start, end + 1)])


def test_excess_deaths_zero_excess_flat():
    """Flat baseline → predicted matches observed → ~0 excess."""
    series = _flat_series()
    result = calculate_excess_deaths(series, baseline_years=list(range(2015, 2020)), event_year=2020)
    assert isinstance(result, ExcessDeathsResult)
    assert result.excess_deaths == pytest.approx(0.0, abs=50.0)


def test_excess_deaths_positive_excess():
    """Event year deaths higher than baseline → positive excess."""
    series = _make_series(
        [(yr, 1000, 1_000_000) for yr in range(2015, 2020)]
        + [(2020, 1500, 1_000_000)]
    )
    result = calculate_excess_deaths(series, baseline_years=list(range(2015, 2020)), event_year=2020)
    assert result.excess_deaths == pytest.approx(500.0, abs=50.0)
    assert result.pct_excess > 0


def test_excess_deaths_negative_excess():
    """Event year deaths lower than baseline → negative excess."""
    series = _make_series(
        [(yr, 1000, 1_000_000) for yr in range(2015, 2020)]
        + [(2020, 700, 1_000_000)]
    )
    result = calculate_excess_deaths(series, baseline_years=list(range(2015, 2020)), event_year=2020)
    assert result.excess_deaths < 0


def test_excess_deaths_prediction_interval_contains_expected():
    # Use slightly noisy baseline so MSE > 0 → PI has width
    noise = [0, 10, -8, 5, -7]
    series = _make_series(
        [(2015 + i, 1000 + noise[i], 1_000_000) for i in range(5)]
        + [(2020, 1000, 1_000_000)]
    )
    result = calculate_excess_deaths(series, list(range(2015, 2020)), event_year=2020)
    assert result.pred_interval_lower < result.expected_deaths < result.pred_interval_upper


def test_excess_deaths_missing_event_year_raises():
    series = _make_series([(yr, 1000, 1_000_000) for yr in range(2015, 2020)])
    with pytest.raises(ValueError, match="2025"):
        calculate_excess_deaths(series, list(range(2015, 2019)), event_year=2025)


def test_excess_deaths_missing_baseline_year_raises():
    series = _make_series([(yr, 1000, 1_000_000) for yr in range(2016, 2021)])
    with pytest.raises(ValueError, match="2015"):
        calculate_excess_deaths(series, [2015, 2016, 2017, 2018, 2019], event_year=2020)


def test_excess_deaths_requires_2_baseline_years():
    series = _make_series([(2019, 1000, 1_000_000), (2020, 1100, 1_000_000)])
    with pytest.raises(ValueError, match="2"):
        calculate_excess_deaths(series, [2019], event_year=2020)


def test_excess_deaths_result_fields():
    series = _flat_series()
    result = calculate_excess_deaths(series, list(range(2015, 2020)), event_year=2020)
    d = result.model_dump()
    assert all(k in d for k in (
        "excess_deaths", "expected_deaths", "observed_deaths", "pct_excess",
        "pred_interval_lower", "pred_interval_upper", "baseline_years",
        "r_squared", "interpretation",
    ))


def test_excess_deaths_interpretation_mentions_year():
    series = _flat_series()
    result = calculate_excess_deaths(series, list(range(2015, 2020)), event_year=2020)
    assert "2020" in result.interpretation


def test_excess_deaths_trending_baseline():
    """Upward trending baseline: excess should still be computable."""
    # Rate increases 1% per year
    series = _make_series(
        [(yr, 1000 * (1.01 ** (yr - 2015)), 1_000_000) for yr in range(2015, 2020)]
        + [(2020, 1200, 1_000_000)]
    )
    result = calculate_excess_deaths(series, list(range(2015, 2020)), event_year=2020)
    assert result.excess_deaths > 0
