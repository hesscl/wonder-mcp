"""Tests for codegen.py: Python and R code generation."""

from __future__ import annotations

from wonder_mcp.client import QueryParams, QueryResult
from wonder_mcp.codegen import generate_python, generate_r


def _sample_result() -> QueryResult:
    params = QueryParams(
        database_id="D76",
        group_by=["D76.V1-level1", "D76.V8"],
        measures=["D76.M1", "D76.M2", "D76.M3"],
        filters={"D76.V7": "F"},
        title="Deaths by Year and Race (Female)",
    )
    return QueryResult(
        database_id="D76",
        params=params,
        xml_sent="<request-parameters><parameter><name>B_1</name><value>D76.V1-level1</value></parameter></request-parameters>",
        columns=["Year", "Race", "Deaths", "Population", "Crude Rate"],
        rows=[
            {"Year": "1999", "Race": "White", "Deaths": "1200000", "Population": "200000000", "Crude Rate": "6.0"},
            {"Year": "2000", "Race": "Black", "Deaths": "300000", "Population": "35000000", "Crude Rate": "8.6"},
        ],
        caveats=["Data sourced from death certificates."],
        footnotes=["Source: CDC WONDER"],
        suppressed_count=0,
        queried_at="2026-02-28T12:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Python code generation
# ---------------------------------------------------------------------------


def test_generate_python_contains_database_id():
    result = _sample_result()
    code = generate_python(result)
    assert "D76" in code


def test_generate_python_contains_url():
    result = _sample_result()
    code = generate_python(result)
    assert "wonder.cdc.gov/controller/datarequest/D76" in code


def test_generate_python_contains_xml():
    result = _sample_result()
    code = generate_python(result)
    assert result.xml_sent in code


def test_generate_python_contains_timestamp():
    result = _sample_result()
    code = generate_python(result)
    assert result.queried_at in code


def test_generate_python_contains_accept_restrictions():
    result = _sample_result()
    code = generate_python(result)
    assert "accept_datause_restrictions" in code


def test_generate_python_is_valid_syntax():
    """The generated Python should be parseable."""
    import ast
    result = _sample_result()
    code = generate_python(result)
    # Should not raise
    ast.parse(code)


def test_generate_python_contains_caveats():
    result = _sample_result()
    code = generate_python(result)
    assert "death certificates" in code.lower()


def test_generate_python_no_wonder_mcp_import():
    """Generated script must be self-contained (no wonder_mcp import)."""
    result = _sample_result()
    code = generate_python(result)
    assert "wonder_mcp" not in code


# ---------------------------------------------------------------------------
# R code generation
# ---------------------------------------------------------------------------


def test_generate_r_contains_database_id():
    result = _sample_result()
    code = generate_r(result)
    assert "D76" in code


def test_generate_r_contains_url():
    result = _sample_result()
    code = generate_r(result)
    assert "wonder.cdc.gov/controller/datarequest/D76" in code


def test_generate_r_contains_xml():
    result = _sample_result()
    code = generate_r(result)
    assert "request-parameters" in code


def test_generate_r_contains_timestamp():
    result = _sample_result()
    code = generate_r(result)
    assert result.queried_at in code


def test_generate_r_uses_httr():
    result = _sample_result()
    code = generate_r(result)
    assert "library(httr)" in code
    assert "library(xml2)" in code


def test_generate_r_no_wonderapi():
    """Generated R script must not depend on wonderapi."""
    result = _sample_result()
    code = generate_r(result)
    assert "wonderapi" not in code.lower()


def test_generate_r_contains_accept_restrictions():
    result = _sample_result()
    code = generate_r(result)
    assert "accept_datause_restrictions" in code


def test_generate_r_contains_title():
    result = _sample_result()
    code = generate_r(result)
    assert result.params.title in code
