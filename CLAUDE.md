# CDC WONDER MCP Server

An MCP (Model Context Protocol) server that provides tools for querying the CDC WONDER (Wide-ranging ONline Data for Epidemiologic Research) API, enabling demographic and epidemiological research via AI assistants.

## Project Purpose

This server wraps the CDC WONDER Data Query Web Service, giving LLMs structured access to US public health data: mortality, natality, cancer statistics, and more.

## CDC WONDER API Reference

### Endpoint
```
POST https://wonder.cdc.gov/controller/datarequest/{database_id}
```

### Authentication
None required. All requests must include `accept_datause_restrictions=true`.

### POST Parameters
| Parameter | Value |
|---|---|
| `request_xml` | XML string (see format below) |
| `accept_datause_restrictions` | `"true"` |

### XML Request Format
```xml
<request-parameters>
  <parameter>
    <name>B_1</name>
    <value>D76.V1-level1</value>
  </parameter>
  <parameter>
    <name>M_1</name>
    <value>D76.M1</value>
  </parameter>
  ...
</request-parameters>
```

### Parameter Prefixes
| Prefix | Purpose |
|---|---|
| `B_1` … `B_5` | Group By (cross-tabulation) fields — up to 5 |
| `M_` | Measures to return (deaths, rates, population, etc.) |
| `V_` | WHERE clause value filters |
| `F_` | Finder control selections (hierarchical list values) |
| `O_` | Other options (radio buttons, age grouping, precision) |
| `VM_` | Non-standard age-adjusted rate population values |
| `I_` | Currently selected items from Finder controls |

### Key O_ Parameters
| Parameter | Values | Description |
|---|---|---|
| `O_aar` | `aar_none`, `aar_std`, `aar_nonstd` | Age-adjusted rate mode |
| `O_rate_per` | `1000`, `10000`, `100000`, `1000000` | Rate denominator |
| `O_precision` | `0`–`9` | Decimal places |
| `O_timeout` | `60`–`900` | Timeout in seconds |
| `O_show_totals` | `true`/`false` | Include totals row |
| `O_show_zeros` | `true`/`false` | Include zero-count rows |
| `O_show_suppressed` | `true`/`false` | Show suppressed values |
| `O_age` | `V5`, `V51`, `V52`, `V6` | Age grouping scheme |

### Response Format
XML with:
- `<r>` rows containing `<c>` cells
- `<v>` attribute = numeric value, `<l>` attribute = label
- Caveats, footnotes, and suppression indicators

### Response Parsing (Python example)
```python
import requests
from bs4 import BeautifulSoup

url = "https://wonder.cdc.gov/controller/datarequest/D76"
resp = requests.post(url, data={
    "request_xml": xml_string,
    "accept_datause_restrictions": "true"
})

soup = BeautifulSoup(resp.text, "lxml")
rows = soup.find_all("r")
for row in rows:
    for cell in row.find_all("c"):
        val = cell.attrs.get("v") or cell.attrs.get("l")
```

---

## Available Databases

| Database Label | dbname (URL slug) | Database ID | Notes |
|---|---|---|---|
| Natality 1995–2002 | `natality-v2002` | **D10** | Birth certificates |
| Natality 2003–2006 | `natality-v2006` | **D27** | Birth certificates |
| Natality 2007–2024 | `natality-current` | **D66** | Birth certificates |
| Natality 2016–2024 (expanded) | `natality-expanded-current` | **D149** | Expanded birth vars |
| Detailed Mortality (1999–2020+) | `ucd-icd10` | **D76** | ICD-10 underlying cause |
| Provisional Multiple Cause of Death | `mcd-icd10-provisional` | **D176** | Updated monthly |
| Heat Wave Days | `NCA-heatwavedays-historic` | **D104** | Environmental |

Additional databases accessible via the web UI (but require discovering their IDs from HTML source):
- Cancer Incidence (USCS, 1999–2022) — `/cancer-v2022.html`
- Cancer Mortality Bridged Race (1999–2021) — `/cancermort-v2021.html`
- Cancer Mortality Single Race (2018–2023) — `/cancermort-v2022_SR.html`
- Multiple Cause of Death 1999–2020 — `/mcd-icd10.html`
- Compressed Mortality — `/mortsql.html`
- Infant Deaths / Linked Birth — `/lbd.html`
- Bridged-Race Population — `/bridged-race-population.html`
- Single-Race Population — `/single-race-population.html`
- STD Morbidity, TB, VAERS, AIDS, Fetal Deaths

To find an unlisted database's ID: open its query page in a browser, submit a query, click "API Options" to get the XML — the endpoint URL contains the ID.

---

## D76 (Detailed Mortality) Variable Reference

### Common B_ (Group By) Values
| Value | Meaning |
|---|---|
| `D76.V1-level1` | Year |
| `D76.V1-level2` | Month |
| `D76.V7` | Gender |
| `D76.V8` | Race |
| `D76.V17` | Hispanic Origin |
| `D76.V5` | Age Groups (standard) |
| `D76.V2-level1` | ICD-10 Chapter |
| `D76.V2-level2` | ICD-10 Sub-chapter |
| `D76.V4` | ICD-10 List (leading causes) |
| `D76.V22` | Injury Intent |
| `D76.V21` | Place of Death |
| `D76.V24` | Weekday |

### Common M_ (Measure) Values
| Value | Meaning |
|---|---|
| `D76.M1` | Deaths |
| `D76.M2` | Population |
| `D76.M3` | Crude Rate |
| `D76.M4` | Age-adjusted Rate |
| `D76.M9` | % of Total Deaths |

### Code Values
| Variable | Code | Label |
|---|---|---|
| Gender | `F` | Female |
| Gender | `M` | Male |
| Hispanic | `2135-2` | Hispanic |
| Hispanic | `2186-2` | Not Hispanic |
| Hispanic | `NS` | Not Stated |
| Race | `1002-5` | American Indian / Alaska Native |
| Race | `A-PI` | Asian or Pacific Islander |
| Race | `2054-5` | Black or African American |
| Race | `2106-3` | White |

---

## API Constraints

- **Geographic limitation**: Only **national-level** data via API. Cannot group or filter by State, County, Region, Division, or Urbanization. Use the web interface for sub-national data.
- **Rate limit**: One query per ~2 minutes recommended; sequential (not parallel) queries required.
- **No record-level data**: Returns aggregate statistics only.
- **Data attribution**: Published outputs must credit "CDC WONDER" and include all footnotes and caveats.
- **Suppression**: Counts < 10 are suppressed; suppressed cells must not be summed or reassembled.

---

## MCP Server Design

### Recommended Tools to Expose

1. **`query_mortality`** — Query D76/D176 mortality data by year, cause (ICD-10), demographics
2. **`query_natality`** — Query D66/D149 birth data by year, demographics, birth characteristics
3. **`list_databases`** — Return known database IDs and descriptions
4. **`build_xml_request`** — Helper: construct a valid `request_xml` string from structured params
5. **`get_icd10_codes`** — Return ICD-10 chapter/sub-chapter codes for cause-of-death filtering
6. **`query_raw`** — Low-level: accept a database ID and raw XML, return parsed table

### Response Handling
- Parse XML response into a clean table (list of dicts or DataFrame-like structure)
- Extract and surface caveats/footnotes as metadata
- Return suppression warnings when cells are masked
- Handle HTTP errors and WONDER's XML error responses (check for `<error>` tags)

### Rate Limiting
Implement a per-session rate limiter enforcing ≥2 minute gaps between requests. Queue requests if needed rather than dropping them.

---

## Development Notes

- Discover new database IDs by inspecting HTML source of WONDER query pages, or by clicking "API Options" after a web UI query
- XML parameter names are database-specific (e.g., `D76.V1` is Year only in D76; D66 uses different variable codes)
- Use HTTPS always — HTTP requests are rejected
- The `finder-stage-D76.V[n]` and `stage=request` parameters are required boilerplate for most D76 queries
- Test queries against the live API; WONDER does not provide a sandbox

## Sources
- [CDC WONDER API Documentation](https://wonder.cdc.gov/wonder/help/wonder-api.html)
- [wonderapi R package](https://socdatar.github.io/wonderapi/)
- [alipphardt/cdc-wonder-api Python examples](https://github.com/alipphardt/cdc-wonder-api)
- [CDC WONDER datasets list](https://wonder.cdc.gov/datasets.html)
