"""FastMCP entry point — exposes CDC WONDER tools to AI assistants."""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import FastMCP

from .client import QueryParams, QueryResult, WonderAPIError, query
from .codegen import generate_python, generate_r
from .databases import DATABASES, get_database
from .icd10 import get_icd10_codes
from .stats import (
    RateInput,
    calculate_apc,
    calculate_excess_deaths,
    calculate_kitagawa,
    calculate_smr,
    calculate_yll,
    build_life_table,
    rate_difference,
    rate_ratio,
)

mcp = FastMCP(
    name="CDC WONDER",
    instructions=(
        "Query CDC WONDER (Wide-ranging ONline Data for Epidemiologic Research) "
        "for US public health statistics: mortality, natality, cancer, and more. "
        "All data is national-level aggregate only — the API cannot return "
        "state or county data. Counts under 10 are suppressed by WONDER. "
        "Use list_databases() to discover available databases before querying."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: list_databases
# ---------------------------------------------------------------------------


@mcp.tool()
def list_databases() -> dict[str, Any]:
    """
    Return the registry of known CDC WONDER databases.

    No API call is made — this is a local lookup.
    Includes database IDs, labels, year ranges, and brief descriptions.
    """
    return {
        db_id: {
            "id": db.id,
            "label": db.label,
            "url_slug": db.url_slug,
            "years": db.years,
            "description": db.description,
        }
        for db_id, db in DATABASES.items()
    }


# ---------------------------------------------------------------------------
# Tool 2: get_database_variables
# ---------------------------------------------------------------------------


@mcp.tool()
def get_database_variables(database_id: str) -> dict[str, Any]:
    """
    Return the group-by variables, measures, and filter variables for a database.

    Use this to discover valid parameter codes before calling query_wonder.

    Args:
        database_id: Database ID (e.g. "D76", "D66"). Use list_databases() to find IDs.
    """
    try:
        db = get_database(database_id)
    except KeyError as e:
        return {"error": str(e)}

    return {
        "id": db.id,
        "label": db.label,
        "years": db.years,
        "group_by_vars": db.group_by_vars,
        "measure_vars": db.measure_vars,
        "filter_vars": db.filter_vars,
        "note": (
            "Pass group_by_vars keys as the group_by list, "
            "measure_vars keys as the measures list, "
            "and filter_vars keys in the filters dict when calling query_wonder."
        ),
    }


# ---------------------------------------------------------------------------
# Tool 3: query_wonder
# ---------------------------------------------------------------------------


@mcp.tool()
async def query_wonder(
    database_id: str,
    group_by: list[str],
    measures: list[str],
    filters: Optional[dict[str, Any]] = None,
    options: Optional[dict[str, str]] = None,
    title: str = "",
) -> dict[str, Any]:
    """
    Execute a CDC WONDER query and return a structured result.

    The result includes the data table, caveats, the exact XML sent,
    and a timestamp — everything needed to reproduce the query.

    IMPORTANT: The API enforces a ~2-minute rate limit between requests.
    This tool will automatically wait if called too soon after a previous query.

    Args:
        database_id: Database ID, e.g. "D76". Use list_databases() to find IDs.
        group_by: List of group-by variable codes (up to 5).
            Example: ["D76.V1-level1", "D76.V8"]
            Use get_database_variables() to find valid codes.
        measures: List of measure codes to return.
            Example: ["D76.M1", "D76.M2", "D76.M3"]
        filters: Optional dict of variable filters.
            Example: {"D76.V7": "F"} to filter to Female only.
            Values can be strings or lists of strings for multi-value filters.
        options: Optional O_ parameter overrides.
            Example: {"O_rate_per": "100000", "O_precision": "2"}
        title: Optional descriptive title for the query (appears in generated code).

    Returns:
        QueryResult with fields:
          - rows: list of dicts (the data table)
          - columns: column headers
          - caveats: list of WONDER caveats
          - footnotes: list of footnotes
          - suppressed_count: number of suppressed cells
          - xml_sent: exact XML submitted (use for replication)
          - queried_at: ISO timestamp

    Geographic limitation: Only national-level data is available via the API.
    Sub-national data (state, county) requires the WONDER web interface.
    """
    params = QueryParams(
        database_id=database_id,
        group_by=group_by,
        measures=measures,
        filters=filters or {},
        options=options or {},
        title=title,
    )
    try:
        result = await query(params)
    except WonderAPIError as e:
        return {
            "error": str(e),
            "raw_response_preview": e.raw_response[:1000] if e.raw_response else "",
        }

    return result.model_dump()


# ---------------------------------------------------------------------------
# Tool 4: generate_python_code
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_python_code(query_result: dict[str, Any]) -> str:
    """
    Generate a self-contained Python replication script from a QueryResult.

    The script embeds the exact XML and requires only requests + beautifulsoup4.
    It can be run in any Python environment without this MCP server.

    Args:
        query_result: The dict returned by query_wonder.

    Returns:
        A Python script as a string. Save to a .py file and run with `python script.py`.
    """
    result = QueryResult.model_validate(query_result)
    return generate_python(result)


# ---------------------------------------------------------------------------
# Tool 5: generate_r_code
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_r_code(query_result: dict[str, Any]) -> str:
    """
    Generate a self-contained R replication script from a QueryResult.

    The script embeds the exact XML and requires only httr + xml2.
    It does NOT depend on the wonderapi package or this MCP server.

    Args:
        query_result: The dict returned by query_wonder.

    Returns:
        An R script as a string. Save to a .R file and run with `Rscript script.R`.
    """
    result = QueryResult.model_validate(query_result)
    return generate_r(result)


# ---------------------------------------------------------------------------
# Tool 6: calculate_rate_ratio
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_rate_ratio(
    group_1: dict[str, Any],
    group_2: dict[str, Any],
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Compute a rate ratio (group_1 / group_2) with a confidence interval.

    This is a fully deterministic calculation — no API call is made.
    Uses the Poisson exact method per group and delta method for the ratio CI.

    Each group must provide EITHER:
      - count (int) + population (int): exact CI computed
      - rate (float) + rate_per (int, default 100000): CI not computable

    Args:
        group_1: Dict with keys: count, population, rate, rate_per (int), label (str)
        group_2: Dict with keys: same as group_1
        alpha: Significance level for CI (default 0.05 → 95% CI)

    Returns:
        Dict with:
          - rate_ratio: float
          - ci_lower, ci_upper: float (NaN if counts not provided)
          - alpha: float
          - method: description of the statistical method used
          - interpretation: plain-language summary
          - group_1, group_2: the input values

    Example:
        group_1 = {"count": 45000, "population": 150000000, "label": "Group A"}
        group_2 = {"count": 12000, "population": 40000000, "label": "Group B"}
        → rate_ratio ≈ 1.0, CI close to [0.98, 1.02]
    """
    try:
        r1 = RateInput.model_validate(group_1)
        r2 = RateInput.model_validate(group_2)
        result = rate_ratio(r1, r2, alpha=alpha)
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 7: calculate_apc
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_apc_tool(
    years: list[float],
    rates: list[float],
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Compute Annual Percent Change (APC) for a rate time series.

    Fits log(rate) ~ year via OLS. Returns APC, 95% CI, p-value, and trend label.
    This is the single-segment APC (not joinpoint regression).

    Typical workflow:
      1. Call query_wonder with group_by=["D76.V1-level1"] and measures=["D76.M3"] or ["D76.M4"]
      2. Extract the year and rate columns from the result rows
      3. Pass here as years and rates

    Args:
        years: List of year values (e.g. [2010, 2011, ..., 2020]).
        rates: List of rates corresponding to each year (must be positive).
        alpha: Significance level (default 0.05 → 95% CI).

    Returns:
        Dict with apc, ci_lower, ci_upper, p_value, trend, r_squared, interpretation.
    """
    try:
        result = calculate_apc(years=years, rates=rates, alpha=alpha)
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 8: calculate_rate_difference
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_rate_difference(
    group_1: dict[str, Any],
    group_2: dict[str, Any],
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Compute absolute rate difference (group_1 − group_2) with a confidence interval.

    Complements calculate_rate_ratio for absolute (not relative) comparisons.
    Uses Poisson variance when counts are available, or propagation of error for SE-based inputs.

    Each group must provide EITHER:
      - count (int) + population (int): Poisson variance CI
      - rate (float) + rate_se (float): propagation-of-error CI
      - rate (float) only: difference computed, CI not available

    Args:
        group_1: Dict with keys: count, population, rate, rate_se, rate_per, label
        group_2: Dict with same keys
        alpha: Significance level (default 0.05 → 95% CI)

    Returns:
        Dict with rate_difference, ci_lower, ci_upper, method, interpretation.
    """
    try:
        r1 = RateInput.model_validate(group_1)
        r2 = RateInput.model_validate(group_2)
        result = rate_difference(r1, r2, alpha=alpha)
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 9: calculate_smr
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_smr_tool(
    observed_deaths: int,
    expected_rate: float,
    population: int,
    rate_per: int = 100_000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Compute the Standardized Mortality Ratio (SMR) with exact Poisson CI.

    SMR = observed / expected, where expected = expected_rate × population / rate_per.

    Use case: "Did Black Americans die more than expected given the national average rate?"
      1. Query national mortality rate for the reference group (expected_rate)
      2. Query observed deaths and population for the study group
      3. Pass here — SMR > 1 means more deaths than expected

    Args:
        observed_deaths: Observed death count in the study population.
        expected_rate: Reference population rate (per rate_per).
        population: Study population size.
        rate_per: Denominator for expected_rate (default 100,000).
        alpha: Significance level (default 0.05 → 95% CI).

    Returns:
        Dict with smr, ci_lower, ci_upper, observed, expected, interpretation.
    """
    try:
        result = calculate_smr(
            observed_deaths=observed_deaths,
            expected_rate=expected_rate,
            population=population,
            rate_per=rate_per,
            alpha=alpha,
        )
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 10: calculate_yll
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_yll_tool(
    age_stratified_rows: list[dict[str, Any]],
    deaths_col: str = "Deaths",
    age_group_col: str = "Age Groups",
    max_age: float = 75.0,
    population: Optional[int] = None,
) -> dict[str, Any]:
    """
    Compute Years of Life Lost (YLL) from an age-stratified WONDER query result.

    Uses the WHO/CDC standard: YLL_i = deaths_i × max(0, max_age − midpoint_age_i).
    Supports standard WONDER D76.V5 age group labels automatically.

    Typical workflow:
      1. Call query_wonder with group_by including "D76.V5" (Age Groups)
      2. Pass the result rows directly as age_stratified_rows

    Args:
        age_stratified_rows: List of row dicts from query_wonder (must include age group).
        deaths_col: Column name for deaths (default "Deaths").
        age_group_col: Column name for age group (default "Age Groups").
        max_age: Life expectancy ceiling in years (default 75, WHO standard).
        population: Optional total population to compute YLL per 100,000.

    Returns:
        Dict with total_yll, yll_per_100k, breakdown by age group, and interpretation.
    """
    try:
        result = calculate_yll(
            age_stratified_rows=age_stratified_rows,
            deaths_col=deaths_col,
            age_group_col=age_group_col,
            max_age=max_age,
            population=population,
        )
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 11: calculate_excess_deaths
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_excess_deaths_tool(
    observed_series: list[dict[str, Any]],
    baseline_years: list[int],
    event_year: int,
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    year_col: str = "Year",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Estimate excess deaths by comparing observed deaths to a pre-event baseline trend.

    Fits a linear OLS trend to crude death rates in the baseline years,
    extrapolates to the event year, and computes excess = observed − expected.

    Use cases: COVID excess mortality (baseline 2015–2019, event 2020+),
    opioid crisis impact, policy intervention evaluation.

    Typical workflow:
      1. Call query_wonder with group_by=["D76.V1-level1"], measures=["D76.M1","D76.M2"]
         for a span of years covering baseline + event year(s)
      2. Pass the rows here with baseline_years and event_year

    Args:
        observed_series: List of row dicts with year, deaths, and population columns.
        baseline_years: List of year ints for pre-event baseline (e.g. [2015,2016,2017,2018,2019]).
        event_year: Year to evaluate (must be present in observed_series).
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        year_col: Column name for year (default "Year").
        alpha: Significance level for prediction interval (default 0.05 → 95% PI).

    Returns:
        Dict with observed_deaths, expected_deaths, excess_deaths, pct_excess,
        prediction interval, baseline fit stats, and interpretation.
    """
    try:
        result = calculate_excess_deaths(
            observed_series=observed_series,
            baseline_years=baseline_years,
            event_year=event_year,
            deaths_col=deaths_col,
            population_col=population_col,
            year_col=year_col,
            alpha=alpha,
        )
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 12: calculate_kitagawa
# ---------------------------------------------------------------------------


@mcp.tool()
def calculate_kitagawa_tool(
    group_1_rows: list[dict[str, Any]],
    group_2_rows: list[dict[str, Any]],
    label_1: str = "Group 1",
    label_2: str = "Group 2",
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    age_group_col: str = "Age Groups",
    rate_per: int = 100_000,
) -> dict[str, Any]:
    """
    Kitagawa decomposition: split the crude rate difference into composition vs. rates effects.

    The crude rate difference between two populations can arise from:
      1. Composition effect — differences in age structure (population shares)
      2. Rates effect — differences in age-specific mortality rates

    Use case: "How much of the Black/White mortality gap is due to age structure
    differences vs. higher age-specific rates among Black Americans?"

    Typical workflow:
      1. Call query_wonder twice — once filtering to each group (e.g. by D76.V8 race code),
         both with group_by including "D76.V5" (Age Groups) and measures ["D76.M1","D76.M2"]
      2. Pass the row lists here as group_1_rows and group_2_rows

    Args:
        group_1_rows: Row dicts from query_wonder for group 1 (age-stratified).
        group_2_rows: Row dicts from query_wonder for group 2 (age-stratified).
        label_1: Label for group 1 (e.g. "Black Americans").
        label_2: Label for group 2 (e.g. "White Americans").
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        age_group_col: Column name for age group (default "Age Groups").
        rate_per: Rate denominator (default 100,000).

    Returns:
        Dict with crude_rate_difference, composition_effect, rates_effect,
        composition_pct, rates_pct, per-age-group breakdown, and interpretation.
    """
    try:
        result = calculate_kitagawa(
            group_1_rows=group_1_rows,
            group_2_rows=group_2_rows,
            deaths_col=deaths_col,
            population_col=population_col,
            age_group_col=age_group_col,
            rate_per=rate_per,
            label_1=label_1,
            label_2=label_2,
        )
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 13: build_life_table
# ---------------------------------------------------------------------------


@mcp.tool()
def build_life_table_tool(
    age_stratified_rows: list[dict[str, Any]],
    deaths_col: str = "Deaths",
    population_col: str = "Population",
    age_group_col: str = "Age Groups",
    radix: int = 100_000,
) -> dict[str, Any]:
    """
    Construct an abridged period life table from age-specific mortality rates.

    Standard life table columns returned for each age group:
      nMx — age-specific death rate (deaths / population)
      nqx — probability of dying within the interval
      lx  — survivors at exact age x (starting from radix = 100,000)
      ndx — deaths in the interval
      nLx — person-years lived in the interval
      Tx  — total person-years above age x
      ex  — life expectancy at exact age x

    Life expectancy at birth (e₀) is returned as a top-level field.

    Conversion method: Reed-Merrell / Chiang nqx = n·nMx / (1 + (n−a_n)·nMx)
    Separation factors: a_1 = 0.07 (infants), a_{1-4} = 1.5, all others = n/2.

    Typical workflow:
      1. Call query_wonder with group_by=["D76.V5"] and measures=["D76.M1","D76.M2"]
         (Deaths and Population) — no additional filters to get the full population
      2. Pass the rows here

    Args:
        age_stratified_rows: Row dicts from query_wonder (must include age, deaths, population).
        deaths_col: Column name for deaths (default "Deaths").
        population_col: Column name for population (default "Population").
        age_group_col: Column name for age group label (default "Age Groups").
        radix: Starting cohort size (default 100,000).

    Returns:
        Dict with e0 (life expectancy at birth), rows (full life table), and interpretation.
    """
    try:
        result = build_life_table(
            age_stratified_rows=age_stratified_rows,
            deaths_col=deaths_col,
            population_col=population_col,
            age_group_col=age_group_col,
            radix=radix,
        )
        return result.model_dump()
    except (ValueError, Exception) as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 14: get_icd10_codes
# ---------------------------------------------------------------------------


@mcp.tool()
def get_icd10_codes_tool(search_term: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Search the local ICD-10-CM chapter and sub-chapter lookup table.

    Returns matching entries with their code ranges, labels, and WONDER filter hints.
    No API call is made — this is a local lookup from an embedded table.

    Use this to find ICD-10 codes before constructing query_wonder filters.
    The returned wonder_filter_key and wonder_filter_value can be used directly
    in the filters dict of query_wonder.

    Example:
      get_icd10_codes("heart")       → ischaemic heart diseases, hypertension, etc.
      get_icd10_codes("opioid")      → T40 (narcotics and psychodysleptics)
      get_icd10_codes("alzheimer")   → G30-G32 (degenerative diseases of nervous system)
      get_icd10_codes("COVID")       → U07, U07.1
      get_icd10_codes("suicide")     → X60-X84 (intentional self-harm)
      get_icd10_codes()              → all 100+ entries

    Args:
        search_term: Optional partial string to filter by code or label (case-insensitive).

    Returns:
        List of dicts with: code, label, level, chapter,
        wonder_group_by_chapter, wonder_group_by_subchapter,
        wonder_filter_key, wonder_filter_value, note.
    """
    return get_icd10_codes(search_term)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
