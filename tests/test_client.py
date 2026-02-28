"""Tests for client.py: XML building and response parsing."""

from __future__ import annotations

import pytest
from xml.etree import ElementTree as ET

from wonder_mcp.client import (
    QueryParams,
    WonderAPIError,
    build_xml,
    _parse_response,
)


# ---------------------------------------------------------------------------
# XML builder tests
# ---------------------------------------------------------------------------


def test_build_xml_basic():
    params = QueryParams(
        database_id="D76",
        group_by=["D76.V1-level1", "D76.V8"],
        measures=["D76.M1", "D76.M2"],
        filters={},
        title="Test Query",
    )
    xml_str = build_xml(params)
    root = ET.fromstring(xml_str)

    names = [p.find("name").text for p in root.findall("parameter")]
    values = {p.find("name").text: p.find("value").text for p in root.findall("parameter")}

    assert "accept_datause_restrictions" in names
    assert values["accept_datause_restrictions"] == "true"
    assert "stage" in names
    assert values["stage"] == "request"
    assert "action-Send" in names
    assert "B_1" in names
    assert values["B_1"] == "D76.V1-level1"
    assert "B_2" in names
    assert values["B_2"] == "D76.V8"
    assert "O_title" in names
    assert values["O_title"] == "Test Query"


def test_build_xml_deterministic():
    """Same params → identical XML on multiple calls."""
    params = QueryParams(
        database_id="D76",
        group_by=["D76.V7"],
        measures=["D76.M1"],
        filters={"D76.V8": "2106-3"},
    )
    assert build_xml(params) == build_xml(params)


def test_build_xml_no_more_than_5_group_by():
    """Pydantic should reject > 5 group-by variables."""
    with pytest.raises(Exception):
        QueryParams(
            database_id="D76",
            group_by=["A", "B", "C", "D", "E", "F"],
            measures=[],
        )


def test_build_xml_filter_list():
    """Multi-value filters emit multiple V_ parameters."""
    params = QueryParams(
        database_id="D76",
        group_by=[],
        measures=["D76.M1"],
        filters={"D76.V8": ["2054-5", "2106-3"]},
    )
    xml_str = build_xml(params)
    root = ET.fromstring(xml_str)
    # Count V_8 occurrences
    v8_params = [
        p for p in root.findall("parameter") if p.find("name").text == "V_8"
    ]
    assert len(v8_params) == 2


def test_build_xml_default_options():
    """Default O_ options are always emitted."""
    params = QueryParams(
        database_id="D76",
        group_by=[],
        measures=[],
    )
    xml_str = build_xml(params)
    root = ET.fromstring(xml_str)
    names = {p.find("name").text for p in root.findall("parameter")}
    assert "O_timeout" in names
    assert "O_precision" in names
    assert "O_show_totals" in names


def test_build_xml_option_override():
    """Custom options override defaults."""
    params = QueryParams(
        database_id="D76",
        group_by=[],
        measures=[],
        options={"O_precision": "3", "O_timeout": "900"},
    )
    xml_str = build_xml(params)
    root = ET.fromstring(xml_str)
    values = {p.find("name").text: p.find("value").text for p in root.findall("parameter")}
    assert values["O_precision"] == "3"
    assert values["O_timeout"] == "900"


def test_build_xml_finder_stage_per_group_by():
    """Each group-by variable gets a finder-stage-* boilerplate parameter."""
    params = QueryParams(
        database_id="D76",
        group_by=["D76.V1-level1", "D76.V7"],
        measures=[],
    )
    xml_str = build_xml(params)
    root = ET.fromstring(xml_str)
    names = {p.find("name").text for p in root.findall("parameter")}
    assert "finder-stage-D76.V1-level1" in names
    assert "finder-stage-D76.V7" in names


# ---------------------------------------------------------------------------
# Response parser tests
# ---------------------------------------------------------------------------


SAMPLE_WONDER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <caveats>Data are based on a 50-state registry.</caveats>
  <footnote>Source: CDC WONDER</footnote>
  <datatable>
    <r>
      <c v="1999" l="1999"/>
      <c v="45000" l="45,000"/>
      <c v="280000000" l="280,000,000"/>
    </r>
    <r>
      <c v="2000" l="2000"/>
      <c v="46000" l="46,000"/>
      <c v="285000000" l="285,000,000"/>
    </r>
  </datatable>
</response>
"""

ERROR_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>
  <error>The query exceeded the cell suppression threshold.</error>
</response>
"""


def _make_params(**kwargs) -> QueryParams:
    defaults = dict(database_id="D76", group_by=[], measures=[], filters={})
    defaults.update(kwargs)
    return QueryParams(**defaults)


def test_parse_response_rows():
    params = _make_params(
        group_by=["D76.V1-level1"],
        measures=["D76.M1", "D76.M2"],
    )
    columns, rows, caveats, footnotes, suppressed = _parse_response(
        SAMPLE_WONDER_XML, params
    )
    assert len(rows) == 2
    assert rows[0] is not None


def test_parse_response_caveats():
    params = _make_params()
    _, _, caveats, footnotes, _ = _parse_response(SAMPLE_WONDER_XML, params)
    assert any("50-state" in c for c in caveats)
    assert any("CDC WONDER" in f for f in footnotes)


def test_parse_response_error_raises():
    params = _make_params()
    with pytest.raises(WonderAPIError) as exc_info:
        _parse_response(ERROR_XML, params)
    assert "suppression" in str(exc_info.value).lower()


def test_parse_response_suppressed_count():
    suppressed_xml = """\
    <response>
      <datatable>
        <r><c s="true" l="Suppressed"/><c v="100000"/></r>
        <r><c v="5000"/><c v="200000"/></r>
      </datatable>
    </response>
    """
    params = _make_params()
    _, _, _, _, count = _parse_response(suppressed_xml, params)
    assert count >= 1
