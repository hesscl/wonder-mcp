"""Deterministic rate ratio calculation with Poisson confidence intervals."""

from __future__ import annotations

import math
from typing import Optional

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
