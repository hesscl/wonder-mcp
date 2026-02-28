"""WONDER HTTP client, XML builder, and response parser."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

WONDER_BASE_URL = "https://wonder.cdc.gov/controller/datarequest"
MIN_REQUEST_INTERVAL = 120.0  # seconds between API calls

_last_query_time: float = 0.0
_rate_limit_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class QueryParams(BaseModel):
    database_id: str
    group_by: list[str] = Field(default_factory=list, max_length=5)
    measures: list[str] = Field(default_factory=list)
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)
    title: str = ""


class QueryResult(BaseModel):
    database_id: str
    params: QueryParams
    xml_sent: str
    columns: list[str]
    rows: list[dict[str, Any]]
    caveats: list[str]
    footnotes: list[str]
    suppressed_count: int
    queried_at: str


# ---------------------------------------------------------------------------
# Database defaults
# ---------------------------------------------------------------------------
# Each entry is an ordered list of (param_name, value) pairs where value is
# either a str or a list[str] (for multi-value parameters like V_D76.V5).
# Source: socdatar/wonderapi D76_Defaults.xml (verbatim parameter list).
#
# WONDER requires ALL of these params to be present in every request — the web
# form's JavaScript normally fills them in; we must send them explicitly.
# Callers override specific entries via group_by / measures / filters / options.

_ParamList = list[tuple[str, str | list[str]]]

_D76_DEFAULTS: _ParamList = [
    ("accept_datause_restrictions", "true"),
    # Group-by slots (B_2–B_5 must be *None* when unused)
    ("B_1", "D76.V1-level1"),
    ("B_2", "*None*"),
    ("B_3", "*None*"),
    ("B_4", "*None*"),
    ("B_5", "*None*"),
    # Finder selections for hierarchical list controls
    ("F_D76.V1", "*All*"),
    ("F_D76.V10", "*All*"),
    ("F_D76.V2", "*All*"),
    ("F_D76.V27", "*All*"),
    ("F_D76.V9", "*All*"),
    # Currently-selected items shown in the finder UI
    ("I_D76.V1", "*All*"),
    ("I_D76.V10", "*All* (The United States)"),
    ("I_D76.V2", "*All*"),
    ("I_D76.V27", "*All* (The United States)"),
    ("I_D76.V9", "*All* (The United States)"),
    # Measures
    ("M_1", "D76.M1"),
    ("M_2", "D76.M2"),
    ("M_3", "D76.M3"),
    # Finder-mode options (required)
    ("O_V10_fmode", "freg"),
    ("O_V1_fmode", "freg"),
    ("O_V27_fmode", "freg"),
    ("O_V2_fmode", "freg"),
    ("O_V9_fmode", "freg"),
    # Output options
    ("O_aar", "aar_none"),
    ("O_aar_pop", "0000"),
    ("O_age", "D76.V5"),       # Must be set even when not grouping by age
    ("O_javascript", "on"),
    ("O_location", "D76.V9"),
    ("O_precision", "1"),
    ("O_rate_per", "100000"),
    ("O_show_totals", "false"),
    ("O_timeout", "300"),
    ("O_ucd", "D76.V2"),
    ("O_urban", "D76.V19"),
    # Age-adjusted rate population parameters
    ("VM_D76.M6_D76.V10", ""),
    ("VM_D76.M6_D76.V17", "*All*"),
    ("VM_D76.M6_D76.V1_S", "*All*"),
    ("VM_D76.M6_D76.V7", "*All*"),
    ("VM_D76.M6_D76.V8", "*All*"),
    # Variable filters — empty string means "all" for year/cause/location
    ("V_D76.V1", ""),
    ("V_D76.V10", ""),
    ("V_D76.V11", "*All*"),
    ("V_D76.V12", "*All*"),
    ("V_D76.V17", "*All*"),
    ("V_D76.V19", "*All*"),
    ("V_D76.V2", ""),
    ("V_D76.V20", "*All*"),
    ("V_D76.V21", "*All*"),
    ("V_D76.V22", "*All*"),
    ("V_D76.V23", "*All*"),
    ("V_D76.V24", "*All*"),
    ("V_D76.V25", "*All*"),
    ("V_D76.V27", ""),
    ("V_D76.V4", "*All*"),
    # Age groups (5-year) — all eleven categories must be explicitly listed
    ("V_D76.V5", ["1", "1-4", "5-14", "15-24", "25-34", "35-44", "45-54",
                  "55-64", "65-74", "75-84", "85+"]),
    ("V_D76.V51", "*All*"),
    ("V_D76.V52", "*All*"),
    ("V_D76.V6", "00"),
    ("V_D76.V7", "*All*"),
    ("V_D76.V8", "*All*"),
    ("V_D76.V9", ""),
    # Required action/stage boilerplate
    ("action-Send", "Send"),
    ("finder-stage-D76.V1", "codeset"),
    ("finder-stage-D76.V10", "codeset"),
    ("finder-stage-D76.V2", "codeset"),
    ("finder-stage-D76.V27", "codeset"),
    ("finder-stage-D76.V9", "codeset"),
    ("stage", "request"),
]

# Provisional mortality (D176) — same pattern, different variable codes.
# Derived from the D76 structure; adjust as needed from the D176 web UI.
_D176_DEFAULTS: _ParamList = [
    ("accept_datause_restrictions", "true"),
    ("B_1", "D176.V1-level1"),
    ("B_2", "*None*"),
    ("B_3", "*None*"),
    ("B_4", "*None*"),
    ("B_5", "*None*"),
    ("F_D176.V1", "*All*"),
    ("F_D176.V2", "*All*"),
    ("M_1", "D176.M1"),
    ("M_2", "D176.M2"),
    ("M_3", "D176.M3"),
    ("O_V1_fmode", "freg"),
    ("O_V2_fmode", "freg"),
    ("O_aar", "aar_none"),
    ("O_age", "D176.V5"),
    ("O_javascript", "on"),
    ("O_precision", "1"),
    ("O_rate_per", "100000"),
    ("O_show_totals", "false"),
    ("O_timeout", "300"),
    ("O_ucd", "D176.V2"),
    ("V_D176.V1", ""),
    ("V_D176.V17", "*All*"),
    ("V_D176.V2", ""),
    ("V_D176.V5", ["1", "1-4", "5-14", "15-24", "25-34", "35-44", "45-54",
                   "55-64", "65-74", "75-84", "85+"]),
    ("V_D176.V51", "*All*"),
    ("V_D176.V52", "*All*"),
    ("V_D176.V7", "*All*"),
    ("V_D176.V8", "*All*"),
    ("action-Send", "Send"),
    ("finder-stage-D176.V1", "codeset"),
    ("finder-stage-D176.V2", "codeset"),
    ("stage", "request"),
]

# Natality 2007–2024 (D66)
_D66_DEFAULTS: _ParamList = [
    ("accept_datause_restrictions", "true"),
    ("B_1", "D66.V1-level1"),
    ("B_2", "*None*"),
    ("B_3", "*None*"),
    ("B_4", "*None*"),
    ("B_5", "*None*"),
    ("F_D66.V1", "*All*"),
    ("M_1", "D66.M1"),
    ("O_V1_fmode", "freg"),
    ("O_javascript", "on"),
    ("O_precision", "1"),
    ("O_rate_per", "1000"),
    ("O_show_totals", "false"),
    ("O_timeout", "300"),
    ("V_D66.V1", ""),
    ("V_D66.V10", "*All*"),
    ("V_D66.V11", "*All*"),
    ("V_D66.V23", "*All*"),
    ("V_D66.V24", "*All*"),
    ("V_D66.V25", "*All*"),
    ("V_D66.V6", "*All*"),
    ("action-Send", "Send"),
    ("finder-stage-D66.V1", "codeset"),
    ("stage", "request"),
]

_DB_DEFAULTS: dict[str, _ParamList] = {
    "D76": _D76_DEFAULTS,
    "D176": _D176_DEFAULTS,
    "D66": _D66_DEFAULTS,
}


# ---------------------------------------------------------------------------
# XML builder
# ---------------------------------------------------------------------------


def _param_elem(name: str, value: str) -> ET.Element:
    p = ET.Element("parameter")
    n = ET.SubElement(p, "name")
    n.text = name
    v = ET.SubElement(p, "value")
    v.text = value
    return p


def _measure_ordinal(measure_code: str) -> str:
    """Extract numeric ordinal from a measure code: 'D76.M1' → '1'."""
    last = measure_code.split(".")[-1]
    return last[1:] if last and last[0].isalpha() else last


def build_xml(params: QueryParams) -> str:
    """Build a deterministic WONDER request XML from QueryParams.

    Uses per-database defaults (sourced from wonderapi's *_Defaults.xml files)
    as the base, then applies user overrides for group_by, measures, filters,
    and options.  This ensures the complete parameter set WONDER requires is
    always present.

    For databases without a pre-defined defaults template, a minimal generic
    parameter set is emitted instead.
    """
    db = params.database_id

    if db in _DB_DEFAULTS:
        return _build_xml_from_defaults(params)
    else:
        return _build_xml_generic(params)


def _build_xml_from_defaults(params: QueryParams) -> str:
    """Build XML by overlaying user params onto the database defaults template."""
    db = params.database_id
    defaults = _DB_DEFAULTS[db]

    # Build a mutable dict from defaults (last write wins for single-value params).
    # Multi-value params (list) are stored as-is and replaced atomically.
    param_dict: dict[str, str | list[str]] = {}
    for name, value in defaults:
        param_dict[name] = value

    # --- Apply group_by overrides (B_1 … B_5) ---
    for i in range(1, 6):
        idx = i - 1
        if idx < len(params.group_by):
            param_dict[f"B_{i}"] = params.group_by[idx]
        else:
            param_dict[f"B_{i}"] = "*None*"

    # --- Apply measure overrides (M_1 … M_N) ---
    # Remove all existing M_ params then re-add in order.
    for key in list(param_dict.keys()):
        if key.startswith("M_") and key[2:].isdigit():
            del param_dict[key]
    for i, measure in enumerate(params.measures, start=1):
        param_dict[f"M_{i}"] = measure

    # --- Apply filter overrides ---
    # User supplies full variable codes as keys (e.g. "D76.V8").
    # The param name in the XML is "V_D76.V8" (prefix "V_" + full code).
    for var_code, value in params.filters.items():
        param_name = f"V_{var_code}"
        param_dict[param_name] = value

    # --- Apply option overrides ---
    for key, value in params.options.items():
        param_dict[key] = value

    # --- Title ---
    if params.title:
        param_dict["O_title"] = params.title

    # --- Serialize in defaults order, then any extra keys appended ---
    root = ET.Element("request-parameters")
    emitted: set[str] = set()

    for name, _default_value in defaults:
        if name in emitted:
            continue
        value = param_dict.get(name, _default_value)
        if isinstance(value, list):
            for v in value:
                root.append(_param_elem(name, v))
        else:
            root.append(_param_elem(name, value))
        emitted.add(name)

    # Extra keys added by user (title, option overrides not in defaults)
    for name, value in sorted(param_dict.items()):
        if name in emitted:
            continue
        if isinstance(value, list):
            for v in value:
                root.append(_param_elem(name, v))
        else:
            root.append(_param_elem(name, value))

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _build_xml_generic(params: QueryParams) -> str:
    """Minimal XML builder for databases without a pre-defined defaults template."""
    root = ET.Element("request-parameters")
    root.append(_param_elem("accept_datause_restrictions", "true"))
    root.append(_param_elem("stage", "request"))
    root.append(_param_elem("action-Send", "Send"))

    if params.title:
        root.append(_param_elem("O_title", params.title))

    for i, var in enumerate(params.group_by, start=1):
        root.append(_param_elem(f"B_{i}", var))
        root.append(_param_elem(f"finder-stage-{var}", "codeset"))
    for i in range(len(params.group_by) + 1, 6):
        root.append(_param_elem(f"B_{i}", "*None*"))

    for i, measure in enumerate(params.measures, start=1):
        root.append(_param_elem(f"M_{i}", measure))

    for var_code in sorted(params.filters.keys()):
        value = params.filters[var_code]
        name = f"V_{var_code}"
        if isinstance(value, list):
            for v in value:
                root.append(_param_elem(name, v))
        else:
            root.append(_param_elem(name, value))

    default_opts = {
        "O_timeout": "300",
        "O_precision": "1",
        "O_show_totals": "false",
    }
    for key, val in sorted({**default_opts, **params.options}.items()):
        root.append(_param_elem(key, val))

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


class WonderAPIError(Exception):
    """Raised when WONDER returns an error response."""

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


def _parse_response(
    xml_text: str, params: QueryParams
) -> tuple[list[str], list[dict], list[str], list[str], int]:
    """Parse a WONDER XML response into (columns, rows, caveats, footnotes, suppressed_count)."""
    soup = BeautifulSoup(xml_text, features="xml")

    # WONDER error responses contain <error> tags
    error_tags = soup.find_all("error")
    if error_tags:
        messages = [e.get_text(strip=True) for e in error_tags]
        raise WonderAPIError("; ".join(messages), raw_response=xml_text)

    caveats = [c.get_text(strip=True) for c in soup.find_all("caveats")]
    footnotes = [f.get_text(strip=True) for f in soup.find_all("footnote")]

    # Column headers come from <th> elements; fall back to param codes
    th_tags = soup.find_all("th")
    if th_tags:
        columns = [th.get_text(strip=True) for th in th_tags]
    else:
        columns = params.group_by + params.measures

    rows: list[dict] = []
    suppressed_count = 0
    prev_row: dict[str, Any] = {}

    for row_tag in soup.find_all("r"):
        cells = row_tag.find_all("c")
        n_cells = len(cells)
        n_cols = len(columns)

        # WONDER omits leading group-by cells when the value hasn't changed
        # from the previous row (e.g., year appears only in the first row of
        # each year block).  Carry those values forward from prev_row.
        row: dict[str, Any] = {}
        if n_cells < n_cols and prev_row:
            skip = n_cols - n_cells
            for i in range(skip):
                col_name = columns[i]
                row[col_name] = prev_row.get(col_name, "")
        else:
            skip = 0

        for idx, cell in enumerate(cells):
            col_idx = skip + idx
            col_name = columns[col_idx] if col_idx < n_cols else f"col_{col_idx}"
            v_attr = cell.get("v")
            l_attr = cell.get("l")
            if v_attr is not None:
                row[col_name] = v_attr
            elif l_attr is not None:
                row[col_name] = l_attr
            else:
                row[col_name] = cell.get_text(strip=True)
            if cell.get("s") == "true" or (l_attr and "suppressed" in l_attr.lower()):
                suppressed_count += 1

        if row:
            rows.append(row)
            prev_row = row

    return columns, rows, caveats, footnotes, suppressed_count


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


async def _wait_for_rate_limit() -> None:
    """Enforce the minimum interval between WONDER API requests."""
    global _last_query_time
    async with _rate_limit_lock:
        elapsed = time.monotonic() - _last_query_time
        if _last_query_time > 0 and elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
        _last_query_time = time.monotonic()


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------


async def query(params: QueryParams) -> QueryResult:
    """Execute a WONDER query and return a structured QueryResult."""
    xml_sent = build_xml(params)
    url = f"{WONDER_BASE_URL}/{params.database_id}"

    await _wait_for_rate_limit()

    async with httpx.AsyncClient(timeout=360.0, follow_redirects=True) as client:
        response = await client.post(
            url,
            data={
                "request_xml": xml_sent,
                "accept_datause_restrictions": "true",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise WonderAPIError(
            f"HTTP {response.status_code} from WONDER API: {response.text[:500]}",
            raw_response=response.text,
        )

    columns, rows, caveats, footnotes, suppressed_count = _parse_response(
        response.text, params
    )

    return QueryResult(
        database_id=params.database_id,
        params=params,
        xml_sent=xml_sent,
        columns=columns,
        rows=rows,
        caveats=caveats,
        footnotes=footnotes,
        suppressed_count=suppressed_count,
        queried_at=datetime.now(timezone.utc).isoformat(),
    )
