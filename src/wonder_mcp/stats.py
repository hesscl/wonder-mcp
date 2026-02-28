"""Deterministic epidemiological calculations with Poisson confidence intervals."""

from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, model_validator
from scipy import stats


class RateInput(BaseModel):
    """Flexible rate input supporting three CI methods.

    Priority (highest to lowest):
      1. count + population  → exact Poisson CI per group, delta method on log(RR)
      2. rate + rate_se      → delta method on log(RR) using provided SE
                               (use with WONDER's age-adjusted rate + D76.M41 SE)
      3. rate only           → ratio computed, CI not available
    """

    count: Optional[int] = None
    population: Optional[int] = None
    rate: Optional[float] = None
    rate_se: Optional[float] = None   # standard error of the rate (e.g. D76.M41)
    rate_per: int = 100_000
    label: str = ""

    @model_validator(mode="after")
    def check_inputs(self) -> "RateInput":
        has_count_pop = self.count is not None and self.population is not None
        has_rate = self.rate is not None
        if not has_count_pop and not has_rate:
            raise ValueError(
                "Provide either (count + population), or (rate), or (rate + rate_se)."
            )
        return self

    @property
    def effective_rate(self) -> float:
        """Rate in the specified rate_per units."""
        if self.rate is not None:
            return self.rate
        if self.count is not None and self.population is not None:
            return (self.count / self.population) * self.rate_per
        raise ValueError("Cannot compute rate: insufficient inputs.")

    # Keep crude_rate as alias for backward compatibility
    @property
    def crude_rate(self) -> float:
        return self.effective_rate

    @property
    def effective_count(self) -> Optional[float]:
        if self.count is not None:
            return float(self.count)
        return None

    @property
    def effective_population(self) -> Optional[float]:
        if self.population is not None:
            return float(self.population)
        return None


class RateRatioResult(BaseModel):
    rate_ratio: float
    ci_lower: float
    ci_upper: float
    alpha: float
    method: str
    group_1: RateInput
    group_2: RateInput
    interpretation: str


def _poisson_rate_ci(
    count: float, population: float, rate_per: float, alpha: float
) -> tuple[float, float]:
    """
    Exact Poisson confidence interval for an observed count, expressed as a rate.

    Uses the chi-squared exact method (equivalent to gamma distribution quantiles).
    Lower CI: chi2(2*count, alpha/2) / (2 * population) * rate_per
    Upper CI: chi2(2*count + 2, 1 - alpha/2) / (2 * population) * rate_per
    """
    if count == 0:
        lower_count = 0.0
    else:
        lower_count = stats.chi2.ppf(alpha / 2, 2 * count) / 2
    upper_count = stats.chi2.ppf(1 - alpha / 2, 2 * count + 2) / 2

    lower = (lower_count / population) * rate_per
    upper = (upper_count / population) * rate_per
    return lower, upper


def rate_ratio(
    r1: RateInput,
    r2: RateInput,
    alpha: float = 0.05,
) -> RateRatioResult:
    """
    Compute a rate ratio (group_1 / group_2) with a confidence interval.

    CI method selected automatically based on available inputs:

    1. count + population (both groups)
       → Exact Poisson CI per group, delta method on log(RR).
       Best for crude rates computed from raw counts.

    2. rate + rate_se (both groups)
       → Delta method on log(RR) using the provided standard errors.
       Use with WONDER's age-adjusted rate (D76.M4) and its SE (D76.M41).
       Formula: Var(log RR) = (SE1/rate1)² + (SE2/rate2)²

    3. rate only
       → Ratio computed; CI not available without SE or counts.
    """
    rate1 = r1.effective_rate
    rate2 = r2.effective_rate

    if rate2 == 0:
        raise ValueError("Group 2 rate is zero; rate ratio is undefined.")

    rr = rate1 / rate2
    z = stats.norm.ppf(1 - alpha / 2)
    log_rr = math.log(rr if rr > 0 else 1e-10)

    # --- Determine CI method ---
    if (
        r1.effective_count is not None
        and r1.effective_population is not None
        and r2.effective_count is not None
        and r2.effective_population is not None
    ):
        # Method 1: exact Poisson per group, delta method on log(RR)
        c1 = r1.effective_count
        c2 = r2.effective_count
        c1_adj = max(c1, 0.5)   # mid-p adjustment for zero counts
        c2_adj = max(c2, 0.5)

        se_log_rr = math.sqrt(1.0 / c1_adj + 1.0 / c2_adj)
        ci_lower = math.exp(log_rr - z * se_log_rr)
        ci_upper = math.exp(log_rr + z * se_log_rr)
        method = "Poisson exact mid-p per group, delta method on log(RR) for CI"

    elif r1.rate_se is not None and r2.rate_se is not None:
        # Method 2: delta method using WONDER-supplied standard errors
        # Var(log RR) = (SE1/rate1)^2 + (SE2/rate2)^2
        se_log_rr = math.sqrt((r1.rate_se / rate1) ** 2 + (r2.rate_se / rate2) ** 2)
        ci_lower = math.exp(log_rr - z * se_log_rr)
        ci_upper = math.exp(log_rr + z * se_log_rr)
        method = "Delta method on log(RR) using supplied rate standard errors"

    else:
        # Method 3: no SE or counts — ratio only
        ci_lower = float("nan")
        ci_upper = float("nan")
        method = (
            "Rate ratio computed from rates only; CIs require count+population "
            "or rate+rate_se."
        )

    # --- Plain-language interpretation ---
    pct = abs(rr - 1) * 100
    direction = "higher" if rr >= 1 else "lower"
    label1 = r1.label or "Group 1"
    label2 = r2.label or "Group 2"
    conf_pct = int((1 - alpha) * 100)

    if math.isnan(ci_lower):
        ci_str = "CI not computable without event counts"
    else:
        ci_str = f"{conf_pct}% CI: {ci_lower:.3f}–{ci_upper:.3f}"

    interpretation = (
        f"The rate in {label1} is {rr:.3f} times the rate in {label2} "
        f"({pct:.1f}% {direction}). {ci_str}."
    )

    return RateRatioResult(
        rate_ratio=round(rr, 6),
        ci_lower=round(ci_lower, 6) if not math.isnan(ci_lower) else float("nan"),
        ci_upper=round(ci_upper, 6) if not math.isnan(ci_upper) else float("nan"),
        alpha=alpha,
        method=method,
        group_1=r1,
        group_2=r2,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Annual Percent Change (APC)
# ---------------------------------------------------------------------------


class APCResult(BaseModel):
    apc: float
    ci_lower: float
    ci_upper: float
    p_value: float
    alpha: float
    slope: float
    slope_se: float
    r_squared: float
    n_years: int
    trend: str
    method: str
    interpretation: str


def calculate_apc(
    years: list[float],
    rates: list[float],
    alpha: float = 0.05,
) -> APCResult:
    """
    Compute Annual Percent Change (APC) via log-linear regression.

    Fits log(rate) ~ year using OLS (scipy.stats.linregress).
    APC = (exp(slope) - 1) * 100.

    Args:
        years: List of year values (e.g. [2010, 2011, ..., 2020]).
        rates: List of rates corresponding to each year.
        alpha: Significance level for CI (default 0.05 → 95% CI).

    Returns:
        APCResult with APC, CI, p-value, trend label, and interpretation.
    """
    if len(years) != len(rates):
        raise ValueError("years and rates must have the same length.")
    if len(years) < 3:
        raise ValueError("At least 3 data points required for APC.")
    if any(r <= 0 for r in rates):
        raise ValueError("All rates must be positive for log-linear regression.")

    log_rates = [math.log(r) for r in rates]
    result = stats.linregress(years, log_rates)
    slope = float(result.slope)
    slope_se = float(result.stderr)
    p_value = float(result.pvalue)
    r_sq = float(result.rvalue ** 2)
    n = len(years)

    z = stats.norm.ppf(1 - alpha / 2)
    apc = (math.exp(slope) - 1) * 100
    ci_lower = (math.exp(slope - z * slope_se) - 1) * 100
    ci_upper = (math.exp(slope + z * slope_se) - 1) * 100

    conf_pct = int((1 - alpha) * 100)
    if p_value < alpha:
        trend = "increasing" if apc > 0 else "decreasing"
    else:
        trend = "stable"

    direction_str = "increased" if apc > 0 else "decreased"
    sig_str = f"(p={p_value:.4f}, statistically significant)" if p_value < alpha else f"(p={p_value:.4f}, not statistically significant)"
    interpretation = (
        f"Rates {direction_str} by {abs(apc):.2f}% per year on average "
        f"({conf_pct}% CI: {ci_lower:.2f}% to {ci_upper:.2f}%) {sig_str}. "
        f"Trend classified as '{trend}'."
    )

    return APCResult(
        apc=round(apc, 4),
        ci_lower=round(ci_lower, 4),
        ci_upper=round(ci_upper, 4),
        p_value=round(p_value, 6),
        alpha=alpha,
        slope=round(slope, 8),
        slope_se=round(slope_se, 8),
        r_squared=round(r_sq, 6),
        n_years=n,
        trend=trend,
        method="Log-linear OLS regression (log(rate) ~ year); APC = (exp(slope) - 1) * 100",
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Rate Difference
# ---------------------------------------------------------------------------


class RateDifferenceResult(BaseModel):
    rate_difference: float
    ci_lower: float
    ci_upper: float
    alpha: float
    method: str
    group_1: RateInput
    group_2: RateInput
    interpretation: str


def rate_difference(
    r1: RateInput,
    r2: RateInput,
    alpha: float = 0.05,
) -> RateDifferenceResult:
    """
    Compute absolute rate difference (group_1 - group_2) with CI.

    CI method selected based on available inputs:
      1. count + population → Poisson variance per group: Var(r) = rate_per^2 * count/pop^2
      2. rate + rate_se → propagation of error: SE(RD) = sqrt(se1^2 + se2^2)
      3. rate only → difference computed, CI not available

    Args:
        r1: RateInput for group 1.
        r2: RateInput for group 2.
        alpha: Significance level (default 0.05 → 95% CI).
    """
    rate1 = r1.effective_rate
    rate2 = r2.effective_rate
    rd = rate1 - rate2
    z = stats.norm.ppf(1 - alpha / 2)

    if (
        r1.effective_count is not None
        and r1.effective_population is not None
        and r2.effective_count is not None
        and r2.effective_population is not None
    ):
        # Poisson variance: Var(rate) = rate_per^2 * count / pop^2
        rp = float(r1.rate_per)
        var1 = (rp ** 2) * r1.effective_count / (r1.effective_population ** 2)
        var2 = (rp ** 2) * r2.effective_count / (r2.effective_population ** 2)
        se_rd = math.sqrt(var1 + var2)
        method = "Poisson variance per group (rate_per² × count / pop²); RD ± z·SE"

    elif r1.rate_se is not None and r2.rate_se is not None:
        se_rd = math.sqrt(r1.rate_se ** 2 + r2.rate_se ** 2)
        method = "Propagation of error using supplied rate SEs; SE(RD) = sqrt(se1²+se2²)"

    else:
        se_rd = float("nan")
        method = "Rate difference computed from rates only; CIs require count+population or rate+rate_se."

    if math.isnan(se_rd):
        ci_lower = float("nan")
        ci_upper = float("nan")
    else:
        ci_lower = rd - z * se_rd
        ci_upper = rd + z * se_rd

    conf_pct = int((1 - alpha) * 100)
    label1 = r1.label or "Group 1"
    label2 = r2.label or "Group 2"
    direction = "higher" if rd >= 0 else "lower"
    abs_rd = abs(rd)

    if math.isnan(ci_lower):
        ci_str = "CI not computable without event counts or rate SEs"
    else:
        ci_str = f"{conf_pct}% CI: {ci_lower:.3f} to {ci_upper:.3f}"

    interpretation = (
        f"The rate in {label1} is {abs_rd:.3f} per {r1.rate_per:,} {direction} "
        f"than in {label2} (RD = {rd:.3f}). {ci_str}."
    )

    return RateDifferenceResult(
        rate_difference=round(rd, 6),
        ci_lower=round(ci_lower, 6) if not math.isnan(ci_lower) else float("nan"),
        ci_upper=round(ci_upper, 6) if not math.isnan(ci_upper) else float("nan"),
        alpha=alpha,
        method=method,
        group_1=r1,
        group_2=r2,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Standardized Mortality Ratio (SMR)
# ---------------------------------------------------------------------------


class SMRResult(BaseModel):
    observed: int
    expected: float
    smr: float
    ci_lower: float
    ci_upper: float
    alpha: float
    method: str
    interpretation: str


def calculate_smr(
    observed_deaths: int,
    expected_rate: float,
    population: int,
    rate_per: int = 100_000,
    alpha: float = 0.05,
) -> SMRResult:
    """
    Compute the Standardized Mortality Ratio with exact Poisson CI.

    SMR = observed / expected, where expected = expected_rate * population / rate_per.
    CI is obtained by computing exact Poisson CI on the observed count
    and dividing by expected.

    Args:
        observed_deaths: Observed number of deaths in the study population.
        expected_rate: Expected rate in the reference population (per rate_per).
        population: Size of the study population.
        rate_per: Denominator for expected_rate (default 100,000).
        alpha: Significance level (default 0.05 → 95% CI).
    """
    if observed_deaths < 0:
        raise ValueError("observed_deaths must be non-negative.")
    if expected_rate <= 0:
        raise ValueError("expected_rate must be positive.")
    if population <= 0:
        raise ValueError("population must be positive.")

    expected = expected_rate * population / rate_per
    if expected == 0:
        raise ValueError("Expected deaths is zero; SMR is undefined.")

    smr = observed_deaths / expected

    # Exact Poisson CI on observed count, then scale by 1/expected
    count = float(observed_deaths)
    if count == 0:
        lower_count = 0.0
    else:
        lower_count = stats.chi2.ppf(alpha / 2, 2 * count) / 2
    upper_count = stats.chi2.ppf(1 - alpha / 2, 2 * count + 2) / 2

    ci_lower = lower_count / expected
    ci_upper = upper_count / expected

    conf_pct = int((1 - alpha) * 100)
    direction = "more" if smr > 1 else "fewer"
    pct_diff = abs(smr - 1) * 100
    sig = "significantly " if (ci_lower > 1 or ci_upper < 1) else ""

    interpretation = (
        f"SMR = {smr:.3f}: the study population experienced {sig}{pct_diff:.1f}% "
        f"{direction} deaths than expected based on the reference rate "
        f"({observed_deaths} observed vs {expected:.1f} expected). "
        f"{conf_pct}% CI: {ci_lower:.3f}–{ci_upper:.3f}."
    )

    return SMRResult(
        observed=observed_deaths,
        expected=round(expected, 4),
        smr=round(smr, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        alpha=alpha,
        method="Exact Poisson CI on observed count divided by expected; SMR = observed/expected",
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Years of Life Lost (YLL)
# ---------------------------------------------------------------------------

# Standard WONDER D76.V5 age-group midpoints (years)
_AGE_GROUP_MIDPOINTS: dict[str, float] = {
    "< 1 year": 0.5,
    "1-4 years": 2.5,
    "5-9 years": 7.0,
    "10-14 years": 12.0,
    "15-19 years": 17.0,
    "20-24 years": 22.0,
    "25-29 years": 27.0,
    "30-34 years": 32.0,
    "35-39 years": 37.0,
    "40-44 years": 42.0,
    "45-49 years": 47.0,
    "50-54 years": 52.0,
    "55-59 years": 57.0,
    "60-64 years": 62.0,
    "65-69 years": 67.0,
    "70-74 years": 72.0,
    "75-79 years": 77.0,
    "80-84 years": 82.0,
    "85+ years": 87.5,
    "85 years and over": 87.5,
    "Not Stated": float("nan"),
}


class YLLAgeGroup(BaseModel):
    age_group: str
    deaths: float
    midpoint_age: float
    years_lost_per_death: float
    yll: float


class YLLResult(BaseModel):
    total_yll: float
    yll_per_100k: Optional[float]
    max_age: float
    n_groups: int
    groups_excluded: list[str]
    age_groups: list[YLLAgeGroup]
    method: str
    interpretation: str


def calculate_yll(
    age_stratified_rows: list[dict[str, Any]],
    deaths_col: str = "Deaths",
    age_group_col: str = "Age Groups",
    max_age: float = 75.0,
    population: Optional[int] = None,
) -> YLLResult:
    """
    Compute Years of Life Lost (YLL) from age-stratified WONDER query rows.

    Uses the standard WHO/CDC method: YLL_i = deaths_i × max(0, max_age - midpoint_i).

    Args:
        age_stratified_rows: List of row dicts from query_wonder (must include age group).
        deaths_col: Column name for death counts (default "Deaths").
        age_group_col: Column name for age group labels (default "Age Groups").
        max_age: Standard life expectancy ceiling (default 75 years, WHO standard).
        population: Optional total population; enables YLL per 100,000.

    Returns:
        YLLResult with total YLL, per-100k rate, and breakdown by age group.
    """
    age_groups: list[YLLAgeGroup] = []
    excluded: list[str] = []
    total_yll = 0.0

    for row in age_stratified_rows:
        age_label = str(row.get(age_group_col, "")).strip()
        deaths_raw = row.get(deaths_col)

        if deaths_raw is None or str(deaths_raw).strip() in ("", "Suppressed", "Missing"):
            excluded.append(age_label or "(unknown)")
            continue

        try:
            deaths = float(str(deaths_raw).replace(",", ""))
        except (ValueError, TypeError):
            excluded.append(age_label)
            continue

        midpoint = _AGE_GROUP_MIDPOINTS.get(age_label)
        if midpoint is None:
            excluded.append(age_label)
            continue
        if math.isnan(midpoint):
            excluded.append(age_label)
            continue

        years_lost = max(0.0, max_age - midpoint)
        yll_i = deaths * years_lost
        total_yll += yll_i

        age_groups.append(YLLAgeGroup(
            age_group=age_label,
            deaths=deaths,
            midpoint_age=midpoint,
            years_lost_per_death=years_lost,
            yll=round(yll_i, 2),
        ))

    yll_per_100k = round(total_yll / population * 100_000, 2) if population else None

    rate_str = f"; YLL per 100,000: {yll_per_100k:,.1f}" if yll_per_100k is not None else ""
    interpretation = (
        f"Total YLL = {total_yll:,.1f} years lost before age {max_age:.0f}"
        f"{rate_str}. "
        f"Based on {len(age_groups)} age groups"
        + (f"; {len(excluded)} group(s) excluded (suppressed/missing/not-stated)." if excluded else ".")
    )

    return YLLResult(
        total_yll=round(total_yll, 2),
        yll_per_100k=yll_per_100k,
        max_age=max_age,
        n_groups=len(age_groups),
        groups_excluded=excluded,
        age_groups=age_groups,
        method=f"WHO/CDC standard: YLL_i = deaths_i × max(0, {max_age:.0f} - midpoint_age_i)",
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Excess Deaths
# ---------------------------------------------------------------------------


class ExcessDeathsResult(BaseModel):
    event_year: int
    observed_deaths: float
    expected_deaths: float
    excess_deaths: float
    excess_rate: Optional[float]
    pct_excess: float
    pred_interval_lower: float
    pred_interval_upper: float
    baseline_years: list[int]
    baseline_slope: float
    baseline_intercept: float
    r_squared: float
    alpha: float
    method: str
    interpretation: str


class ObservedYearRecord(BaseModel):
    year: int
    deaths: float
    population: int


def calculate_excess_deaths(
    observed_series: list[dict[str, Any]],
    baseline_years: list[int],
    event_year: int,
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    year_col: str = "Year",
    alpha: float = 0.05,
) -> ExcessDeathsResult:
    """
    Estimate excess deaths by comparing observed deaths to a pre-event baseline trend.

    Fits a linear OLS trend to the crude death rates of the baseline years,
    extrapolates to the event year, and computes excess = observed − expected.

    Args:
        observed_series: List of row dicts with year, deaths, and population columns.
        baseline_years: List of year ints to use as the pre-event baseline (e.g. [2015..2019]).
        event_year: The year to compare against the baseline trend.
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        year_col: Column name for year (default "Year").
        alpha: Significance level for prediction interval (default 0.05 → 95% PI).

    Returns:
        ExcessDeathsResult with expected deaths, excess deaths, % excess, prediction interval.
    """
    # Parse observed series
    records: dict[int, ObservedYearRecord] = {}
    for row in observed_series:
        try:
            yr = int(str(row[year_col]).strip())
            d = float(str(row[deaths_col]).replace(",", ""))
            p = int(str(row[population_col]).replace(",", ""))
            records[yr] = ObservedYearRecord(year=yr, deaths=d, population=p)
        except (KeyError, ValueError, TypeError):
            continue

    # Build baseline
    baseline_x: list[float] = []
    baseline_y: list[float] = []
    for yr in sorted(baseline_years):
        rec = records.get(yr)
        if rec is None:
            raise ValueError(f"Baseline year {yr} not found in observed_series.")
        rate = rec.deaths / rec.population * 100_000
        baseline_x.append(float(yr))
        baseline_y.append(rate)

    if len(baseline_x) < 2:
        raise ValueError("At least 2 baseline years with data are required.")

    lr = stats.linregress(baseline_x, baseline_y)
    slope = float(lr.slope)
    intercept = float(lr.intercept)
    r_sq = float(lr.rvalue ** 2)
    n_b = len(baseline_x)

    # Predicted rate at event year
    predicted_rate = slope * event_year + intercept

    # Event year observed
    event_rec = records.get(event_year)
    if event_rec is None:
        raise ValueError(f"event_year {event_year} not found in observed_series.")

    observed_rate = event_rec.deaths / event_rec.population * 100_000
    expected_deaths = predicted_rate * event_rec.population / 100_000
    excess_deaths = event_rec.deaths - expected_deaths
    excess_rate = observed_rate - predicted_rate
    pct_excess = (excess_deaths / expected_deaths) * 100 if expected_deaths != 0 else float("nan")

    # Prediction interval for event year rate
    # SE_pred = se_regression * sqrt(1 + 1/n + (x* - x_bar)^2 / S_xx)
    x_bar = sum(baseline_x) / n_b
    s_xx = sum((x - x_bar) ** 2 for x in baseline_x)
    residuals = [baseline_y[i] - (slope * baseline_x[i] + intercept) for i in range(n_b)]
    mse = sum(r ** 2 for r in residuals) / max(n_b - 2, 1)
    se_pred = math.sqrt(mse * (1 + 1 / n_b + (event_year - x_bar) ** 2 / s_xx)) if s_xx > 0 else math.sqrt(mse)

    t_crit = stats.t.ppf(1 - alpha / 2, df=n_b - 2)
    pi_lower_rate = predicted_rate - t_crit * se_pred
    pi_upper_rate = predicted_rate + t_crit * se_pred
    pi_lower_deaths = pi_lower_rate * event_rec.population / 100_000
    pi_upper_deaths = pi_upper_rate * event_rec.population / 100_000

    conf_pct = int((1 - alpha) * 100)
    direction = "above" if excess_deaths >= 0 else "below"
    interpretation = (
        f"In {event_year}, {event_rec.deaths:,.0f} deaths were observed vs "
        f"{expected_deaths:,.1f} expected (from baseline trend {min(baseline_years)}–{max(baseline_years)}). "
        f"Excess deaths: {excess_deaths:+,.1f} ({pct_excess:+.1f}% {direction} expected). "
        f"{conf_pct}% prediction interval: {pi_lower_deaths:,.1f} to {pi_upper_deaths:,.1f} expected deaths."
    )

    return ExcessDeathsResult(
        event_year=event_year,
        observed_deaths=round(event_rec.deaths, 1),
        expected_deaths=round(expected_deaths, 1),
        excess_deaths=round(excess_deaths, 1),
        excess_rate=round(excess_rate, 4),
        pct_excess=round(pct_excess, 2),
        pred_interval_lower=round(pi_lower_deaths, 1),
        pred_interval_upper=round(pi_upper_deaths, 1),
        baseline_years=sorted(baseline_years),
        baseline_slope=round(slope, 6),
        baseline_intercept=round(intercept, 4),
        r_squared=round(r_sq, 6),
        alpha=alpha,
        method=(
            "Linear OLS trend on crude death rates (per 100k) in baseline years; "
            "excess = observed − (predicted_rate × population / 100k); "
            "prediction interval via t-distribution"
        ),
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Kitagawa Decomposition
# ---------------------------------------------------------------------------


class KitagawaAgeGroupResult(BaseModel):
    age_group: str
    rate_1: float
    rate_2: float
    pop_share_1: float
    pop_share_2: float
    composition_component: float
    rates_component: float


class KitagawaResult(BaseModel):
    crude_rate_1: float
    crude_rate_2: float
    crude_rate_difference: float
    composition_effect: float
    rates_effect: float
    composition_pct: float
    rates_pct: float
    residual: float
    rate_per: int
    label_1: str
    label_2: str
    n_age_groups: int
    age_groups_excluded: list[str]
    age_groups: list[KitagawaAgeGroupResult]
    method: str
    interpretation: str


def calculate_kitagawa(
    group_1_rows: list[dict[str, Any]],
    group_2_rows: list[dict[str, Any]],
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    age_group_col: str = "Age Groups",
    rate_per: int = 100_000,
    label_1: str = "Group 1",
    label_2: str = "Group 2",
) -> KitagawaResult:
    """
    Kitagawa decomposition of the crude rate difference between two populations.

    Splits the crude rate difference into:
      - Composition effect: due to differences in age structure (population shares)
      - Rates effect: due to differences in age-specific mortality rates

    Formula:
      RD_composition = Σ [(p1_i - p2_i) × (r1_i + r2_i) / 2]
      RD_rates       = Σ [(r1_i - r2_i) × (p1_i + p2_i) / 2]
      RD_total       = RD_composition + RD_rates  (exact)

    Use case: "How much of the Black/White mortality gap is explained by age
    structure vs. higher age-specific death rates?"

    Args:
        group_1_rows: Row dicts from query_wonder for group 1 (must include age group).
        group_2_rows: Row dicts from query_wonder for group 2 (must include age group).
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        age_group_col: Column name for age group label (default "Age Groups").
        rate_per: Rate denominator (default 100,000).
        label_1: Label for group 1 (e.g. "Black Americans").
        label_2: Label for group 2 (e.g. "White Americans").
    """

    def _parse(rows: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
        out: dict[str, tuple[float, float]] = {}
        for row in rows:
            ag = str(row.get(age_group_col, "")).strip()
            d_raw = row.get(deaths_col)
            p_raw = row.get(population_col)
            if d_raw is None or p_raw is None:
                continue
            if str(d_raw).strip() in ("Suppressed", "Missing", ""):
                continue
            try:
                d = float(str(d_raw).replace(",", ""))
                p = float(str(p_raw).replace(",", ""))
            except (ValueError, TypeError):
                continue
            if p > 0:
                out[ag] = (d, p)
        return out

    g1 = _parse(group_1_rows)
    g2 = _parse(group_2_rows)
    common = sorted(set(g1) & set(g2))
    excluded = sorted((set(g1) | set(g2)) - set(common))

    if len(common) < 2:
        raise ValueError(
            f"At least 2 common age groups required; found {len(common)}. "
            "Ensure both groups are from an age-stratified WONDER query."
        )

    n1 = sum(g1[ag][1] for ag in common)
    n2 = sum(g2[ag][1] for ag in common)
    d1_total = sum(g1[ag][0] for ag in common)
    d2_total = sum(g2[ag][0] for ag in common)

    crude1 = d1_total / n1 * rate_per
    crude2 = d2_total / n2 * rate_per
    crude_rd = crude1 - crude2

    comp_total = 0.0
    rates_total = 0.0
    age_results: list[KitagawaAgeGroupResult] = []

    for ag in common:
        d1_i, p1_i = g1[ag]
        d2_i, p2_i = g2[ag]
        r1_i = d1_i / p1_i * rate_per
        r2_i = d2_i / p2_i * rate_per
        ps1_i = p1_i / n1
        ps2_i = p2_i / n2
        comp_i = (ps1_i - ps2_i) * (r1_i + r2_i) / 2
        rate_i = (r1_i - r2_i) * (ps1_i + ps2_i) / 2
        comp_total += comp_i
        rates_total += rate_i
        age_results.append(KitagawaAgeGroupResult(
            age_group=ag,
            rate_1=round(r1_i, 4),
            rate_2=round(r2_i, 4),
            pop_share_1=round(ps1_i, 6),
            pop_share_2=round(ps2_i, 6),
            composition_component=round(comp_i, 6),
            rates_component=round(rate_i, 6),
        ))

    residual = crude_rd - (comp_total + rates_total)

    def _pct(c: float) -> float:
        return round(c / crude_rd * 100, 2) if crude_rd != 0 else float("nan")

    direction = "higher" if crude_rd > 0 else "lower"
    comp_struct = "older" if comp_total > 0 else "younger"
    rate_dir = "higher" if rates_total > 0 else "lower"

    interpretation = (
        f"{label_1} crude rate ({crude1:.2f}/{rate_per:,}) is "
        f"{abs(crude_rd):.2f}/{rate_per:,} {direction} than {label_2} ({crude2:.2f}/{rate_per:,}). "
        f"Composition effect: {comp_total:.4f} ({_pct(comp_total):.1f}% of RD) — "
        f"{label_1} has a {comp_struct} age structure. "
        f"Rates effect: {rates_total:.4f} ({_pct(rates_total):.1f}% of RD) — "
        f"{label_1} has {rate_dir} age-specific rates."
    )

    return KitagawaResult(
        crude_rate_1=round(crude1, 4),
        crude_rate_2=round(crude2, 4),
        crude_rate_difference=round(crude_rd, 6),
        composition_effect=round(comp_total, 6),
        rates_effect=round(rates_total, 6),
        composition_pct=_pct(comp_total),
        rates_pct=_pct(rates_total),
        residual=round(residual, 8),
        rate_per=rate_per,
        label_1=label_1,
        label_2=label_2,
        n_age_groups=len(common),
        age_groups_excluded=list(excluded),
        age_groups=age_results,
        method=(
            "Kitagawa (1955) exact decomposition: "
            "RD_composition = Σ[(p1_i−p2_i)(r1_i+r2_i)/2]; "
            "RD_rates = Σ[(r1_i−r2_i)(p1_i+p2_i)/2]"
        ),
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Abridged Period Life Table
# ---------------------------------------------------------------------------

# Standard age-group interval widths (n) for the abridged table.
# WONDER D76.V5 scheme. Key: age-group label → (n, midpoint)
# n is the interval width in years; used for nLx computation.
_LT_AGE_INTERVALS: list[tuple[str, float, float]] = [
    # (label, n, midpoint)
    ("< 1 year",       1.0,  0.5),
    ("1-4 years",      4.0,  2.5),
    ("5-9 years",      5.0,  7.0),
    ("10-14 years",    5.0, 12.0),
    ("15-19 years",    5.0, 17.0),
    ("20-24 years",    5.0, 22.0),
    ("25-29 years",    5.0, 27.0),
    ("30-34 years",    5.0, 32.0),
    ("35-39 years",    5.0, 37.0),
    ("40-44 years",    5.0, 42.0),
    ("45-49 years",    5.0, 47.0),
    ("50-54 years",    5.0, 52.0),
    ("55-59 years",    5.0, 57.0),
    ("60-64 years",    5.0, 62.0),
    ("65-69 years",    5.0, 67.0),
    ("70-74 years",    5.0, 72.0),
    ("75-79 years",    5.0, 77.0),
    ("80-84 years",    5.0, 82.0),
    ("85+ years",     float("inf"), 87.5),
    ("85 years and over", float("inf"), 87.5),
]
_LT_LABEL_TO_META: dict[str, tuple[float, float]] = {
    label: (n, mid) for label, n, mid in _LT_AGE_INTERVALS
}
_LT_ORDERED_LABELS: list[str] = [
    "< 1 year", "1-4 years", "5-9 years", "10-14 years", "15-19 years",
    "20-24 years", "25-29 years", "30-34 years", "35-39 years", "40-44 years",
    "45-49 years", "50-54 years", "55-59 years", "60-64 years", "65-69 years",
    "70-74 years", "75-79 years", "80-84 years", "85+ years",
]

# Separation factor a_n for the first two intervals (Reed-Merrell approximation)
_LT_SEPARATION: dict[str, float] = {
    "< 1 year": 0.07,   # a_1 for infant interval (sex-neutral approximation)
    "1-4 years": 1.5,   # a_4 mid-interval default
}


class LifeTableRow(BaseModel):
    age_group: str
    n: float                # interval width (years; inf for open interval)
    mx: float               # age-specific death rate (per 1, not per 100k)
    qx: float               # probability of dying in interval
    px: float               # probability of surviving interval
    lx: float               # survivors at start of interval (radix = 100,000)
    dx: float               # deaths in interval
    Lx: float               # person-years lived in interval
    Tx: float               # total person-years above age x
    ex: float               # life expectancy at age x


class LifeTableResult(BaseModel):
    radix: int
    e0: float               # life expectancy at birth
    rows: list[LifeTableRow]
    age_group_col: str
    deaths_col: str
    population_col: str
    n_groups: int
    groups_excluded: list[str]
    method: str
    interpretation: str


def build_life_table(
    age_stratified_rows: list[dict[str, Any]],
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    age_group_col: str = "Age Groups",
    radix: int = 100_000,
) -> LifeTableResult:
    """
    Construct an abridged period life table from age-specific mortality rates.

    Standard actuarial/demographic columns:
      nMx  — age-specific death rate (deaths / person-years ≈ deaths / population)
      nqx  — probability of dying within the age interval
      npx  — probability of surviving
      lx   — survivors at exact age x (starting from radix, default 100,000)
      ndx  — deaths within interval
      nLx  — person-years lived in interval
      Tx   — total person-years above age x
      ex   — life expectancy at exact age x

    Conversion from nMx to nqx uses the standard Reed-Merrell / actuarial formula:
      nqx = n·nMx / (1 + (n - n·a_n)·nMx)
    where a_n is the within-interval mean age at death (separation factor).

    The open terminal interval (85+) uses: q_{85} = 1.0 and e_{85} = 1/M_{85}.

    Args:
        age_stratified_rows: Row dicts from query_wonder with age, deaths, population.
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        age_group_col: Column name for age group label (default "Age Groups").
        radix: Starting cohort size (default 100,000).
    """
    # Parse rows
    raw: dict[str, tuple[float, float]] = {}
    skipped: set[str] = set()
    for row in age_stratified_rows:
        ag = str(row.get(age_group_col, "")).strip()
        d_raw = row.get(deaths_col)
        p_raw = row.get(population_col)
        if d_raw is None or p_raw is None:
            if ag:
                skipped.add(ag)
            continue
        if str(d_raw).strip() in ("Suppressed", "Missing", ""):
            skipped.add(ag)
            continue
        try:
            d = float(str(d_raw).replace(",", ""))
            p = float(str(p_raw).replace(",", ""))
        except (ValueError, TypeError):
            skipped.add(ag)
            continue
        if p > 0:
            raw[ag] = (d, p)
        else:
            skipped.add(ag)

    # Normalise "85 years and over" → "85+ years"
    if "85 years and over" in raw and "85+ years" not in raw:
        raw["85+ years"] = raw.pop("85 years and over")

    ordered = [ag for ag in _LT_ORDERED_LABELS if ag in raw]
    # excluded: non-standard labels that parsed OK + skipped labels
    excluded = sorted((set(raw) - set(ordered)) | skipped)

    if len(ordered) < 3:
        raise ValueError(
            f"At least 3 age groups required for a life table; found {len(ordered)}. "
            "Query WONDER with group_by=['D76.V5'] to get age-stratified data."
        )

    has_open = ordered[-1] in ("85+ years",)

    # Step 1: compute nMx (per person, not per 100k)
    mx_map: dict[str, float] = {}
    for ag in ordered:
        d, p = raw[ag]
        mx_map[ag] = d / p

    # Step 2: compute nqx
    qx_map: dict[str, float] = {}
    for ag in ordered:
        n_i, _ = _LT_LABEL_TO_META[ag]
        mx_i = mx_map[ag]
        if math.isinf(n_i):
            # Open terminal interval: everyone dies
            qx_map[ag] = 1.0
        else:
            a_n = _LT_SEPARATION.get(ag, n_i / 2)
            denom = 1 + (n_i - a_n) * mx_i
            qx_map[ag] = min((n_i * mx_i) / denom, 1.0)

    # Step 3: build table columns forward
    rows: list[LifeTableRow] = []
    lx = float(radix)

    for ag in ordered:
        n_i, _ = _LT_LABEL_TO_META[ag]
        mx_i = mx_map[ag]
        qx_i = qx_map[ag]
        px_i = 1.0 - qx_i
        dx_i = lx * qx_i

        if math.isinf(n_i):
            # Open interval: Lx = survivors / Mx; Tx computed below
            a_n = 1.0 / mx_i if mx_i > 0 else 0.0
            Lx_i = lx * a_n
        else:
            a_n = _LT_SEPARATION.get(ag, n_i / 2)
            Lx_i = n_i * (lx - dx_i) + a_n * dx_i

        rows.append(LifeTableRow(
            age_group=ag,
            n=n_i,
            mx=round(mx_i, 8),
            qx=round(qx_i, 8),
            px=round(px_i, 8),
            lx=round(lx, 4),
            dx=round(dx_i, 4),
            Lx=round(Lx_i, 4),
            Tx=0.0,   # filled below
            ex=0.0,   # filled below
        ))

        lx = lx - dx_i  # survivors to next interval

    # Step 4: compute Tx and ex backwards
    Tx = 0.0
    for row in reversed(rows):
        Tx += row.Lx
        row.Tx = round(Tx, 4)
        row.ex = round(Tx / row.lx, 4) if row.lx > 0 else 0.0

    e0 = rows[0].ex

    interpretation = (
        f"Life expectancy at birth (e₀) = {e0:.2f} years "
        f"based on {len(ordered)} age groups. "
        + (f"{len(excluded)} group(s) excluded (suppressed/unknown). " if excluded else "")
        + f"Computed from {deaths_col}/{population_col} columns using standard "
        f"abridged period life table methods."
    )

    return LifeTableResult(
        radix=radix,
        e0=round(e0, 4),
        rows=rows,
        age_group_col=age_group_col,
        deaths_col=deaths_col,
        population_col=population_col,
        n_groups=len(ordered),
        groups_excluded=list(excluded),
        method=(
            "Abridged period life table (Chiang 1984 / Preston et al. 2001). "
            "nqx = n·nMx / (1 + (n−a_n)·nMx); "
            "a_n: infant=0.07, 1-4=1.5, all others=n/2. "
            "Terminal interval: q=1, L=l/M."
        ),
        interpretation=interpretation,
    )
