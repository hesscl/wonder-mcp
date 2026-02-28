"""Tests for calculate_kitagawa, build_life_table, and get_icd10_codes."""

from __future__ import annotations

import math

import pytest

from wonder_mcp.icd10 import get_icd10_codes
from wonder_mcp.stats import (
    KitagawaResult,
    LifeTableResult,
    build_life_table,
    calculate_kitagawa,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(age_group: str, deaths: float, population: int) -> dict:
    return {"Age Groups": age_group, "Deaths": deaths, "Population": population}


def _two_group_rows(spec: list[tuple[str, float, float, float, float]]):
    """Returns (g1_rows, g2_rows) from (age_group, d1, p1, d2, p2) tuples."""
    g1 = [_row(ag, d1, int(p1)) for ag, d1, p1, d2, p2 in spec]
    g2 = [_row(ag, d2, int(p2)) for ag, d1, p1, d2, p2 in spec]
    return g1, g2


# ---------------------------------------------------------------------------
# calculate_kitagawa
# ---------------------------------------------------------------------------


def test_kitagawa_identical_groups_zero_difference():
    """When rates AND structure are identical, both effects are zero."""
    g1, g2 = _two_group_rows([
        ("25-29 years", 100, 500_000, 100, 500_000),
        ("45-49 years", 500, 500_000, 500, 500_000),
        ("65-69 years", 2000, 500_000, 2000, 500_000),
    ])
    r = calculate_kitagawa(g1, g2)
    assert isinstance(r, KitagawaResult)
    assert r.crude_rate_difference == pytest.approx(0.0, abs=1e-6)
    assert r.composition_effect == pytest.approx(0.0, abs=1e-6)
    assert r.rates_effect == pytest.approx(0.0, abs=1e-6)


def test_kitagawa_rates_effect_only():
    """Same age structure, different rates → composition≈0, rates effect captures all."""
    # p1=p2 (same populations per group) but different death rates
    g1, g2 = _two_group_rows([
        ("25-29 years", 200, 500_000, 100, 500_000),
        ("45-49 years", 1000, 500_000, 500, 500_000),
        ("65-69 years", 4000, 500_000, 2000, 500_000),
    ])
    r = calculate_kitagawa(g1, g2)
    assert r.composition_effect == pytest.approx(0.0, abs=1e-6)
    assert r.rates_effect > 0
    assert r.crude_rate_difference > 0


def test_kitagawa_composition_effect_only():
    """Same age-specific rates, different age structures → rates≈0, composition captures all."""
    # Rates: 200/100k (young), 1000/100k (mid), 5000/100k (old) — same for both groups.
    # Deaths must be proportional to each group's population at those rates.
    # Group 1 (older): 10% young, 20% mid, 70% old
    # Group 2 (younger): 70% young, 20% mid, 10% old
    g1 = [
        _row("25-29 years",  200,   100_000),    # 200/100k
        _row("45-49 years", 2000,   200_000),    # 1000/100k
        _row("65-69 years", 35000,  700_000),    # 5000/100k
    ]
    g2 = [
        _row("25-29 years", 1400,   700_000),    # 200/100k (same rate)
        _row("45-49 years", 2000,   200_000),    # 1000/100k (same rate)
        _row("65-69 years", 5000,   100_000),    # 5000/100k (same rate)
    ]
    r = calculate_kitagawa(g1, g2, label_1="Older pop", label_2="Younger pop")
    assert r.rates_effect == pytest.approx(0.0, abs=1e-4)
    assert r.composition_effect > 0  # older group 1 has higher crude rate


def test_kitagawa_decomposition_sums_to_total():
    """composition + rates ≈ crude_rate_difference (residual ≈ 0)."""
    g1, g2 = _two_group_rows([
        ("25-29 years", 150, 400_000, 100, 600_000),
        ("45-49 years", 800, 400_000, 500, 400_000),
        ("65-69 years", 3000, 200_000, 2000, 200_000),
    ])
    r = calculate_kitagawa(g1, g2)
    assert r.residual == pytest.approx(0.0, abs=1e-6)
    assert (r.composition_effect + r.rates_effect) == pytest.approx(
        r.crude_rate_difference, abs=1e-4
    )


def test_kitagawa_pcts_sum_to_100():
    g1, g2 = _two_group_rows([
        ("25-29 years", 200, 500_000, 100, 500_000),
        ("45-49 years", 1000, 300_000, 500, 500_000),
        ("65-69 years", 5000, 200_000, 2000, 200_000),
    ])
    r = calculate_kitagawa(g1, g2)
    assert r.composition_pct + r.rates_pct == pytest.approx(100.0, abs=0.01)


def test_kitagawa_excludes_suppressed():
    g1 = [
        _row("25-29 years", "Suppressed", 500_000),
        _row("45-49 years", 800, 500_000),
        _row("65-69 years", 3000, 500_000),
    ]
    g2 = [
        _row("25-29 years", 100, 500_000),
        _row("45-49 years", 500, 500_000),
        _row("65-69 years", 2000, 500_000),
    ]
    r = calculate_kitagawa(g1, g2)
    assert "25-29 years" in r.age_groups_excluded
    assert r.n_age_groups == 2


def test_kitagawa_requires_2_common_age_groups():
    g1 = [_row("25-29 years", 100, 500_000)]
    g2 = [_row("45-49 years", 100, 500_000)]
    with pytest.raises(ValueError, match="2"):
        calculate_kitagawa(g1, g2)


def test_kitagawa_result_fields():
    g1, g2 = _two_group_rows([
        ("25-29 years", 150, 500_000, 100, 500_000),
        ("45-49 years", 800, 500_000, 500, 500_000),
        ("65-69 years", 3000, 500_000, 2000, 500_000),
    ])
    r = calculate_kitagawa(g1, g2, label_1="A", label_2="B")
    d = r.model_dump()
    assert all(k in d for k in (
        "crude_rate_1", "crude_rate_2", "crude_rate_difference",
        "composition_effect", "rates_effect", "composition_pct", "rates_pct",
        "residual", "age_groups", "interpretation",
    ))
    assert "A" in r.interpretation
    assert "B" in r.interpretation


def test_kitagawa_age_groups_in_result():
    g1, g2 = _two_group_rows([
        ("25-29 years", 150, 500_000, 100, 500_000),
        ("45-49 years", 800, 500_000, 500, 500_000),
    ])
    r = calculate_kitagawa(g1, g2)
    assert len(r.age_groups) == 2
    for ag in r.age_groups:
        assert ag.rate_1 > 0
        assert ag.rate_2 > 0


# ---------------------------------------------------------------------------
# build_life_table
# ---------------------------------------------------------------------------

# Realistic US-like age-specific death counts and populations
_US_LIKE_ROWS = [
    _row("< 1 year",    24000,    3_800_000),
    _row("1-4 years",    4500,   15_600_000),
    _row("5-9 years",    3200,   20_000_000),
    _row("10-14 years",  4200,   20_500_000),
    _row("15-19 years", 13000,   21_000_000),
    _row("20-24 years", 22000,   22_000_000),
    _row("25-29 years", 27000,   23_000_000),
    _row("30-34 years", 32000,   22_000_000),
    _row("35-39 years", 40000,   21_500_000),
    _row("40-44 years", 57000,   20_000_000),
    _row("45-49 years", 95000,   20_000_000),
    _row("50-54 years", 145000,  19_500_000),
    _row("55-59 years", 220000,  21_500_000),
    _row("60-64 years", 330000,  20_500_000),
    _row("65-69 years", 460000,  17_000_000),
    _row("70-74 years", 580000,  13_000_000),
    _row("75-79 years", 620000,   9_000_000),
    _row("80-84 years", 620000,   6_000_000),
    _row("85+ years",   950000,   6_500_000),
]


def test_life_table_returns_result():
    r = build_life_table(_US_LIKE_ROWS)
    assert isinstance(r, LifeTableResult)


def test_life_table_e0_plausible():
    """Life expectancy at birth should be in a plausible range (60–85 years for US-like data)."""
    r = build_life_table(_US_LIKE_ROWS)
    assert 60.0 < r.e0 < 85.0


def test_life_table_lx_starts_at_radix():
    r = build_life_table(_US_LIKE_ROWS)
    assert r.rows[0].lx == pytest.approx(r.radix, rel=1e-4)


def test_life_table_lx_decreasing():
    r = build_life_table(_US_LIKE_ROWS)
    lx_vals = [row.lx for row in r.rows]
    for i in range(1, len(lx_vals)):
        assert lx_vals[i] <= lx_vals[i - 1]


def test_life_table_qx_between_0_and_1():
    r = build_life_table(_US_LIKE_ROWS)
    for row in r.rows:
        assert 0.0 <= row.qx <= 1.0


def test_life_table_terminal_qx_is_1():
    r = build_life_table(_US_LIKE_ROWS)
    assert r.rows[-1].qx == pytest.approx(1.0, abs=1e-6)


def test_life_table_ex_decreasing_after_first():
    """ex should generally decrease with age (can increase at infant interval)."""
    r = build_life_table(_US_LIKE_ROWS)
    # From age 5 onward, ex should be strictly decreasing
    ex_from_5 = [row.ex for row in r.rows if row.age_group not in ("< 1 year", "1-4 years")]
    for i in range(1, len(ex_from_5)):
        assert ex_from_5[i] < ex_from_5[i - 1]


def test_life_table_tx_decreasing():
    r = build_life_table(_US_LIKE_ROWS)
    tx_vals = [row.Tx for row in r.rows]
    for i in range(1, len(tx_vals)):
        assert tx_vals[i] <= tx_vals[i - 1]


def test_life_table_mx_positive():
    r = build_life_table(_US_LIKE_ROWS)
    for row in r.rows:
        assert row.mx > 0


def test_life_table_custom_radix():
    r = build_life_table(_US_LIKE_ROWS, radix=10_000)
    assert r.radix == 10_000
    assert r.rows[0].lx == pytest.approx(10_000.0, rel=1e-4)


def test_life_table_85_years_and_over_alias():
    """WONDER may return '85 years and over' — should be normalised to '85+ years'."""
    rows = [r if r["Age Groups"] != "85+ years" else {**r, "Age Groups": "85 years and over"}
            for r in _US_LIKE_ROWS]
    r = build_life_table(rows)
    assert r.e0 > 0


def test_life_table_excludes_suppressed():
    rows = [r for r in _US_LIKE_ROWS]
    rows[0] = {**rows[0], "Deaths": "Suppressed"}
    r = build_life_table(rows)
    assert "< 1 year" in r.groups_excluded


def test_life_table_requires_at_least_3_groups():
    with pytest.raises(ValueError, match="3"):
        build_life_table([_row("25-29 years", 100, 500_000), _row("45-49 years", 500, 500_000)])


def test_life_table_result_fields():
    r = build_life_table(_US_LIKE_ROWS)
    d = r.model_dump()
    assert all(k in d for k in ("e0", "rows", "radix", "n_groups", "interpretation", "method"))


def test_life_table_interpretation_mentions_e0():
    r = build_life_table(_US_LIKE_ROWS)
    assert str(round(r.e0, 2)) in r.interpretation or "life expectancy" in r.interpretation.lower()


# ---------------------------------------------------------------------------
# get_icd10_codes
# ---------------------------------------------------------------------------


def test_icd10_no_filter_returns_all():
    results = get_icd10_codes()
    assert len(results) > 80  # at least 22 chapters + many sub-chapters


def test_icd10_all_have_required_keys():
    for entry in get_icd10_codes():
        assert "code" in entry
        assert "label" in entry
        assert "level" in entry
        assert "chapter" in entry
        assert "wonder_filter_key" in entry
        assert "wonder_filter_value" in entry


def test_icd10_search_heart():
    results = get_icd10_codes("heart")
    assert any("heart" in r["label"].lower() for r in results)


def test_icd10_search_opioid():
    results = get_icd10_codes("opioid")
    assert len(results) >= 1
    assert any("T40" in r["code"] for r in results)


def test_icd10_search_covid():
    results = get_icd10_codes("COVID")
    assert any("U07" in r["code"] for r in results)


def test_icd10_search_suicide():
    results = get_icd10_codes("suicide")
    assert any("X60" in r["code"] for r in results)


def test_icd10_search_alzheimer():
    results = get_icd10_codes("alzheimer")
    assert any("G30" in r["code"] for r in results)


def test_icd10_search_diabetes():
    results = get_icd10_codes("diabetes")
    assert any("E10" in r["code"] or "E14" in r["code"] for r in results)


def test_icd10_search_case_insensitive():
    upper = get_icd10_codes("HEART")
    lower = get_icd10_codes("heart")
    assert len(upper) == len(lower)


def test_icd10_search_by_code():
    results = get_icd10_codes("I20")
    assert any("I20" in r["code"] for r in results)


def test_icd10_chapters_present():
    chapters = [r for r in get_icd10_codes() if r["level"] == "chapter"]
    # All 22 chapters
    assert len(chapters) == 22


def test_icd10_wonder_filter_key_correct():
    for entry in get_icd10_codes():
        assert entry["wonder_filter_key"] == "D76.V2"


def test_icd10_filter_value_matches_code():
    for entry in get_icd10_codes():
        assert entry["wonder_filter_value"] == entry["code"]


def test_icd10_search_no_results():
    results = get_icd10_codes("ZZZNOTACODE99999")
    assert results == []


def test_icd10_circulatory_chapter():
    results = get_icd10_codes("I00-I99")
    assert len(results) >= 1
    assert results[0]["chapter"] == "IX"
