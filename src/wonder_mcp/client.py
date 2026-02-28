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
# Request model
# ---------------------------------------------------------------------------


class QueryParams(BaseModel):
    database_id: str
    group_by: list[str] = Field(default_factory=list, max_length=5)
    measures: list[str] = Field(default_factory=list)
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)
    title: str = ""


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


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
# XML builder
# ---------------------------------------------------------------------------


def _var_suffix(code: str) -> str:
    """Extract numeric/code suffix from a WONDER variable code.

    Examples:
        "D76.V8"       → "8"
        "D76.V1-level1"→ "1-level1"
        "D76.M1"       → "1"
    """
    last = code.split(".")[-1]
    # Strip the leading letter (V, M, B, …) to get the numeric portion
    if last and last[0].isalpha():
        return last[1:]
    return last


def _param(name: str, value: str) -> ET.Element:
    p = ET.Element("parameter")
    n = ET.SubElement(p, "name")
    n.text = name
    v = ET.SubElement(p, "value")
    v.text = value
    return p


def build_xml(params: QueryParams) -> str:
    """Build a deterministic WONDER request XML string from QueryParams."""
    root = ET.Element("request-parameters")

    # --- Required boilerplate ---
    root.append(_param("accept_datause_restrictions", "true"))
    root.append(_param("stage", "request"))
    root.append(_param("action-Send", "Send"))

    if params.title:
        root.append(_param("O_title", params.title))

    # --- Group By (B_1 … B_5) ---
    for i, var in enumerate(params.group_by, start=1):
        root.append(_param(f"B_{i}", var))
        # Required finder-stage param for each group-by variable
        root.append(_param(f"finder-stage-{var}", "codeset"))

    # --- Measures (M_) ---
    # WONDER expects M_1, M_2, etc. from full codes like D76.M1
    for measure in params.measures:
        suffix = _var_suffix(measure)
        root.append(_param(f"M_{suffix}", measure))

    # --- Filters (V_ and F_) ---
    # WONDER expects V_8, V_17, etc. from full codes like D76.V8
    for key in sorted(params.filters.keys()):
        value = params.filters[key]
        suffix = _var_suffix(key)
        if isinstance(value, list):
            for v in value:
                root.append(_param(f"V_{suffix}", v))
        else:
            root.append(_param(f"V_{suffix}", value))

    # --- Options (O_) ---
    default_options: dict[str, str] = {
        "O_timeout": "300",
        "O_precision": "1",
        "O_show_totals": "false",
        "O_show_zeros": "false",
        "O_show_suppressed": "false",
    }
    merged_options = {**default_options, **params.options}
    for key in sorted(merged_options.keys()):
        root.append(_param(key, merged_options[key]))

    return ET.tostring(root, encoding="unicode", xml_declaration=False)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


class WonderAPIError(Exception):
    """Raised when WONDER returns an error response."""

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


def _parse_response(xml_text: str, params: QueryParams) -> tuple[list[str], list[dict], list[str], list[str], int]:
    """Parse WONDER XML response into (columns, rows, caveats, footnotes, suppressed_count)."""
    soup = BeautifulSoup(xml_text, features="xml")

    # Check for error responses
    error_tags = soup.find_all("error")
    if error_tags:
        messages = [e.get_text(strip=True) for e in error_tags]
        raise WonderAPIError("; ".join(messages), raw_response=xml_text)

    # Extract caveats and footnotes
    caveats = [c.get_text(strip=True) for c in soup.find_all("caveats")]
    footnotes = [f.get_text(strip=True) for f in soup.find_all("footnote")]

    # Build column headers from measure labels
    # Columns come from the <th> elements in the response, or we infer from group_by + measures
    th_tags = soup.find_all("th")
    if th_tags:
        columns = [th.get_text(strip=True) for th in th_tags]
    else:
        columns = params.group_by + params.measures

    # Parse data rows
    rows: list[dict] = []
    suppressed_count = 0

    for row_tag in soup.find_all("r"):
        cells = row_tag.find_all("c")
        row: dict[str, Any] = {}
        for idx, cell in enumerate(cells):
            col_name = columns[idx] if idx < len(columns) else f"col_{idx}"
            # WONDER uses 'v' for numeric value and 'l' for label
            v_attr = cell.get("v")
            l_attr = cell.get("l")
            if v_attr is not None:
                row[col_name] = v_attr
            elif l_attr is not None:
                row[col_name] = l_attr
            else:
                text = cell.get_text(strip=True)
                row[col_name] = text
            # Count suppressed cells
            if cell.get("s") == "true" or (l_attr and "suppressed" in l_attr.lower()):
                suppressed_count += 1
        if row:
            rows.append(row)

    return columns, rows, caveats, footnotes, suppressed_count


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


async def _wait_for_rate_limit() -> None:
    """Enforce minimum interval between WONDER API requests."""
    global _last_query_time
    async with _rate_limit_lock:
        elapsed = time.monotonic() - _last_query_time
        if _last_query_time > 0 and elapsed < MIN_REQUEST_INTERVAL:
            wait_secs = MIN_REQUEST_INTERVAL - elapsed
            await asyncio.sleep(wait_secs)
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
