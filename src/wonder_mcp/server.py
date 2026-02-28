"""FastMCP entry point — exposes CDC WONDER tools to AI assistants."""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import FastMCP

from .client import QueryParams, QueryResult, WonderAPIError, query
from .codegen import generate_python, generate_r
from .databases import DATABASES, get_database
from .stats import RateInput, rate_ratio

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
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
