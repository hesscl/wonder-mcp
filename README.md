# 🔬 CDC WONDER MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives AI assistants structured access to the [CDC WONDER](https://wonder.cdc.gov/) public health database — covering US mortality, natality, cancer statistics, and more.

> **Reproducibility first.** Every query returns the exact XML sent, a timestamp, and self-contained Python and R replication scripts so your results exist independently of any AI assistant.

---

## ✨ Features

- 📊 **Query CDC WONDER** — mortality (ICD-10), births, heat wave data, and more
- 🔁 **Reproducible by design** — every response embeds the exact request XML
- 🐍 **Code generation** — one-click Python and R scripts that replicate any query without this server
- 📐 **Rate ratios with CIs** — exact Poisson confidence intervals, delta method, no API call needed
- 🛡️ **Rate limiting built-in** — automatically enforces the ~2 min WONDER API cooldown
- 📚 **Variable codebook** — discover valid parameter codes before querying

---

## 🗄️ Supported Databases

| ID | Database | Years |
|---|---|---|
| **D76** | Detailed Mortality (ICD-10 underlying cause) | 1999–present |
| **D176** | Provisional Multiple Cause of Death | 2018–present (monthly updates) |
| **D66** | Natality | 2007–2024 |
| **D149** | Natality (expanded variables) | 2016–2024 |
| **D27** | Natality | 2003–2006 |
| **D10** | Natality | 1995–2002 |
| **D104** | Heat Wave Days | 1961–2010 |

> ⚠️ The CDC WONDER API returns **national-level data only.** State, county, and regional breakdowns require the [WONDER web interface](https://wonder.cdc.gov/).

---

## 🚀 Installation

**Requirements:** Python ≥ 3.11

```bash
# Clone and install
git clone <repo-url>
cd wonder-mcp

# Install into a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

---

## 🔌 MCP Server Configuration

Add this server to your MCP client's configuration. The server communicates over stdio.

### Generic configuration (most MCP clients)

```json
{
  "mcpServers": {
    "cdc-wonder": {
      "command": "/path/to/wonder-mcp/.venv/bin/python",
      "args": ["-m", "wonder_mcp.server"]
    }
  }
}
```

Replace `/path/to/wonder-mcp` with the absolute path where you cloned this repo.

### Using `wonder-mcp` script (after install)

If you installed with `pip install -e .`, you can use the entry point directly:

```json
{
  "mcpServers": {
    "cdc-wonder": {
      "command": "/path/to/wonder-mcp/.venv/bin/wonder-mcp"
    }
  }
}
```

---

## 🛠️ Tools

### `list_databases()`
Returns all known databases with IDs, year ranges, and descriptions. No API call — instant local lookup.

---

### `get_database_variables(database_id)`
Returns the valid group-by variables, measures, and filter codes for a database. Use this before building a query.

```
get_database_variables("D76")
→ {
    "group_by_vars": {"D76.V1-level1": "Year", "D76.V8": "Race", ...},
    "measure_vars":  {"D76.M1": "Deaths", "D76.M3": "Crude Rate", ...},
    "filter_vars":   {"D76.V7": "Gender (F=Female, M=Male)", ...}
  }
```

---

### `query_wonder(database_id, group_by, measures, filters?, options?, title?)`
Executes a WONDER query. Returns a structured result table plus caveats, footnotes, suppression count, the exact XML sent, and a timestamp.

```
query_wonder(
  database_id = "D76",
  group_by    = ["D76.V1-level1", "D76.V8"],
  measures    = ["D76.M1", "D76.M2", "D76.M3"],
  filters     = {"D76.V7": "F"},
  title       = "Female mortality by year and race"
)
```

**Returns:**
```json
{
  "rows": [{"Year": "1999", "Race": "White", "Deaths": "...", ...}, ...],
  "columns": ["Year", "Race", "Deaths", "Population", "Crude Rate"],
  "caveats": ["..."],
  "xml_sent": "<request-parameters>...</request-parameters>",
  "queried_at": "2026-02-28T12:00:00+00:00",
  "suppressed_count": 0
}
```

> ⏱️ This tool automatically waits if called within 2 minutes of the previous query.

**Common filter codes for D76:**

| Filter | Values |
|---|---|
| Gender (`D76.V7`) | `F` = Female, `M` = Male |
| Race (`D76.V8`) | `2106-3` = White, `2054-5` = Black, `1002-5` = AIAN, `A-PI` = Asian/PI |
| Hispanic Origin (`D76.V17`) | `2135-2` = Hispanic, `2186-2` = Not Hispanic |

---

### `generate_python_code(query_result)`
Generates a self-contained Python script that exactly replicates any query — no AI assistant needed.

```python
# CDC WONDER Query — Self-Contained Replication Script
# Database  : D76
# Queried at: 2026-02-28T12:00:00+00:00

import requests
from bs4 import BeautifulSoup

XML = """<request-parameters>...</request-parameters>"""

response = requests.post(
    "https://wonder.cdc.gov/controller/datarequest/D76",
    data={"request_xml": XML, "accept_datause_restrictions": "true"},
    timeout=360,
)
# ... parses and prints as CSV
```

Dependencies: `pip install requests beautifulsoup4 lxml`

---

### `generate_r_code(query_result)`
Same as above but produces an R script using `httr` + `xml2`.

Dependencies: `install.packages(c("httr", "xml2"))`

---

### `calculate_rate_ratio(group_1, group_2, alpha?)`
Computes a rate ratio with confidence interval. Fully deterministic — no API call.

```
calculate_rate_ratio(
  group_1 = {"count": 45000, "population": 150000000, "label": "Group A"},
  group_2 = {"count": 12000, "population":  40000000, "label": "Group B"},
  alpha   = 0.05
)
→ {
    "rate_ratio": 1.0,
    "ci_lower": 0.978,
    "ci_upper": 1.022,
    "method": "Poisson exact mid-p per group, delta method on log(RR) for CI",
    "interpretation": "The rate in Group A is 1.000 times the rate in Group B (0.0% higher). 95% CI: 0.978–1.022."
  }
```

**Input options per group:**
- `count` + `population` → exact Poisson CI computed
- `rate` + `rate_per` (default 100,000) → ratio computed but CI requires counts

---

## 🔁 Reproducibility Workflow

1. Run `query_wonder(...)` → get back a `QueryResult` with `xml_sent`
2. Run `generate_python_code(<result>)` or `generate_r_code(<result>)`
3. Save the output script — it embeds the complete request XML and produces identical data in any environment

The `xml_sent` field alone is sufficient to reproduce the query manually:

```bash
curl -s -X POST https://wonder.cdc.gov/controller/datarequest/D76 \
  --data-urlencode "request_xml@request.xml" \
  --data "accept_datause_restrictions=true"
```

---

## ⚠️ Important Limitations

| Limitation | Details |
|---|---|
| **Geography** | National-level only via API. No state, county, or regional data. |
| **Suppression** | Counts < 10 are suppressed and returned as `"Suppressed"`. Do not sum suppressed cells. |
| **Rate limit** | ~2 minutes between requests. This server enforces it automatically. |
| **Aggregates only** | No record-level microdata — returns summary statistics. |
| **Attribution** | Published outputs must credit CDC WONDER and include all footnotes/caveats. |

---

## 🧪 Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run the server directly (stdio mode)
python -m wonder_mcp.server
```

### Project structure

```
wonder-mcp/
├── pyproject.toml
├── src/wonder_mcp/
│   ├── server.py      # MCP tools (FastMCP entry point)
│   ├── client.py      # HTTP client, XML builder, response parser
│   ├── databases.py   # Database registry and variable codebooks
│   ├── codegen.py     # Python + R code generation
│   └── stats.py       # Rate ratio with Poisson CIs
└── tests/
    ├── test_client.py
    ├── test_codegen.py
    └── test_stats.py
```

---

## 📖 Data Attribution

All data returned by this server originates from CDC WONDER. When publishing results:

> _Source: Centers for Disease Control and Prevention, National Center for Health Statistics. CDC WONDER Online Database. [URL]. Accessed [date]._

Include all caveats and footnotes returned with each query.

---

## 🔗 References

- [CDC WONDER](https://wonder.cdc.gov/)
- [CDC WONDER API Documentation](https://wonder.cdc.gov/wonder/help/wonder-api.html)
- [CDC WONDER Datasets List](https://wonder.cdc.gov/datasets.html)
- [Model Context Protocol](https://modelcontextprotocol.io)
