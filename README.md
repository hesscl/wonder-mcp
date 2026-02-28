# 🔬 CDC WONDER MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives AI assistants structured access to the [CDC WONDER](https://wonder.cdc.gov/) public health database — covering US mortality, natality, cancer statistics, and more.

> **Reproducibility first.** Every query returns the exact XML sent, a timestamp, and self-contained Python and R replication scripts so your results exist independently of any AI assistant.

---

## ✨ Features

- 📊 **Query CDC WONDER** — mortality (ICD-10), births, heat wave data, and more
- 🔁 **Reproducible by design** — every response embeds the exact request XML
- 🐍 **Code generation** — one-click Python and R scripts that replicate any query without this server
- 📐 **Rate ratios with CIs** — exact Poisson confidence intervals, delta method, no API call needed
- 📈 **Trend analysis** — Annual Percent Change (APC) via log-linear regression
- ⚖️ **Rate difference** — absolute rate difference with CI (Poisson or SE propagation)
- 🎯 **SMR** — Standardized Mortality Ratio with exact Poisson CI
- ⏳ **YLL** — Years of Life Lost (WHO/CDC method) from age-stratified data
- 📉 **Excess deaths** — observed vs. linear baseline trend with prediction intervals
- 🔬 **Kitagawa decomposition** — split crude rate differences into composition vs. rates effects
- 🧮 **Life tables** — abridged period life tables with e₀ and standard columns (nMx, nqx, lx, …)
- 🔍 **ICD-10 lookup** — search chapter/sub-chapter codes for cause-of-death filtering
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

> 🚧 **Geographic limitation:** The CDC WONDER API returns **national-level data only.** State, county, MSA, and regional breakdowns are not available through the API — only through the [WONDER web interface](https://wonder.cdc.gov/). This is a hard constraint of the WONDER service itself, not this server. See [§ Geographic Limitation](#-geographic-limitation) for alternatives.

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
- `rate` + `rate_se` → delta method CI using supplied standard error (e.g. `D76.M41`)
- `rate` only → ratio computed, CI not available

---

### `calculate_apc_tool(years, rates, alpha?)`
Fits log-linear OLS to compute Annual Percent Change. Trend labelled as increasing / decreasing / stable.

```
calculate_apc_tool(
  years = [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020],
  rates = [750.1, 740.3, 731.5, 718.2, 704.9, 693.0, 681.8, 667.5, 659.2, 649.8, 828.7]
)
→ {
    "apc": 0.8,
    "ci_lower": -0.5,
    "ci_upper": 2.2,
    "trend": "No significant trend (p = 0.271)",
    "interpretation": "The annual percent change is 0.8% (95% CI: -0.5% to 2.2%) ..."
  }
```

---

### `calculate_rate_difference(group_1, group_2, alpha?)`
Computes the absolute rate difference (group 1 − group 2) with CI. Accepts the same `count`/`population` or `rate`/`rate_se` inputs as `calculate_rate_ratio`.

```
calculate_rate_difference(
  group_1 = {"rate": 1067.16, "rate_se": 1.61, "label": "Black or African American"},
  group_2 = {"rate":  825.86, "rate_se": 0.50, "label": "White"},
)
→ {
    "rate_difference": 241.30,
    "ci_lower": 238.0,
    "ci_upper": 244.6,
    "method": "SE propagation",
    "interpretation": "The rate in Black or African American exceeds White by 241.30 per 100,000 ..."
  }
```

---

### `calculate_smr_tool(observed_deaths, expected_rate, population, rate_per?, alpha?)`
Standardized Mortality Ratio with exact Poisson CI. SMR = observed / expected, where expected = expected_rate × population / rate_per.

```
calculate_smr_tool(
  observed_deaths = 1250,
  expected_rate   = 800.0,
  population      = 150000,
  rate_per        = 100000,
)
→ {
    "smr": 1.042,
    "ci_lower": 0.984,
    "ci_upper": 1.103,
    "interpretation": "The observed deaths are 1.042 times the expected (4.2% excess). 95% CI: 0.984–1.103."
  }
```

---

### `calculate_yll_tool(age_stratified_rows, deaths_col?, age_group_col?, max_age?, population?)`
Years of Life Lost (WHO/CDC method): YLL = Σ deaths × max(0, max_age − midpoint). Accepts rows directly from `query_wonder` grouped by `D76.V5` (standard age groups). Set `max_age=75` (default) for the WHO standard or `max_age=80` for the US standard.

```
calculate_yll_tool(
  age_stratified_rows = [...],   # rows from query_wonder with age groups
  deaths_col          = "Deaths",
  population          = 330000000,
  max_age             = 75
)
→ {
    "total_yll": 7234891,
    "yll_per_100k": 2192.4,
    "n_groups": 14,
    "interpretation": "Total YLL = 7,234,891 (2,192.4 per 100,000). ..."
  }
```

---

### `calculate_excess_deaths_tool(observed_series, baseline_years, event_year, ...)`
Estimates excess deaths by fitting a linear OLS trend to baseline crude rates and extrapolating to an event year. Prediction interval uses the t-distribution.

```
calculate_excess_deaths_tool(
  observed_series = [...],          # rows with year, deaths, population columns
  baseline_years  = [2015, 2016, 2017, 2018, 2019],
  event_year      = 2020,
  deaths_col      = "Deaths",
  population_col  = "Population",
  year_col        = "Year"
)
→ {
    "event_year": 2020,
    "observed_deaths": 3383729,
    "expected_deaths": 2981000,
    "excess_deaths": 402729,
    "pct_excess": 13.5,
    "pred_interval_lower": 2901000,
    "pred_interval_upper": 3061000,
    "interpretation": "In 2020, observed deaths (3,383,729) exceeded the projected baseline (2,981,000) by 402,729 (13.5%). ..."
  }
```

---

### `calculate_kitagawa_tool(group_1_rows, group_2_rows, label_1?, label_2?, ...)`
Kitagawa decomposition of the crude rate difference between two populations into:
- **Composition effect** — due to differences in age structure
- **Rates effect** — due to differences in age-specific mortality rates

Accepts age-stratified rows from `query_wonder` (must include deaths, population, and age group columns).

```
calculate_kitagawa_tool(
  group_1_rows = [...],   # age-stratified rows for group 1
  group_2_rows = [...],   # age-stratified rows for group 2
  label_1      = "Black or African American",
  label_2      = "White"
)
→ {
    "crude_rate_difference": 241.30,
    "composition_effect": -82.4,   # negative: group 1 is younger → suppresses crude rate
    "rates_effect":        323.7,  # true age-specific rate gap
    "composition_pct":    -34.2,
    "rates_pct":          134.2,
    "interpretation": "Of the 241.30/100k crude rate difference, -34.2% is explained by age composition and 134.2% by age-specific rates. ..."
  }
```

---

### `build_life_table_tool(age_stratified_rows, deaths_col?, population_col?, age_group_col?, radix?)`
Constructs an abridged period life table from age-stratified WONDER data. Uses the Reed-Merrell formula to convert nMx → nqx. Returns life expectancy at birth (e₀) and the full table with nMx, nqx, lx, dx, nLx, Tx, and ex columns.

```
build_life_table_tool(
  age_stratified_rows = [...],   # rows from query_wonder grouped by D76.V5
  radix               = 100000
)
→ {
    "e0": 77.3,
    "rows": [
      {"age_group": "< 1 year",   "nMx": 0.00522, "nqx": 0.00520, "lx": 100000, ...},
      {"age_group": "1-4 years",  "nMx": 0.00025, "nqx": 0.00099, "lx":  99480, ...},
      ...
      {"age_group": "85+ years",  "nMx": 0.14700, "nqx": 1.00000, "lx":  12450, ...}
    ],
    "interpretation": "Life expectancy at birth (e₀) = 77.3 years."
  }
```

---

### `get_icd10_codes_tool(search_term?)`
Searches the local ICD-10 chapter and sub-chapter table (100+ entries). Returns codes, labels, and WONDER filter hints (`wonder_filter_key`, `wonder_filter_value`). Call with no argument to list all chapters.

```
get_icd10_codes_tool(search_term = "heart")
→ [
    {"code": "I00-I09", "label": "Acute rheumatic fever",         "wonder_filter_value": "I00-I09", ...},
    {"code": "I20-I25", "label": "Ischaemic heart diseases",      "wonder_filter_value": "I20-I25", ...},
    {"code": "I30-I52", "label": "Other forms of heart disease",  "wonder_filter_value": "I30-I52", ...},
    ...
  ]
```

Use the returned `wonder_filter_value` as a filter in `query_wonder`:
```
query_wonder(
  database_id = "D76",
  group_by    = ["D76.V1-level1"],
  measures    = ["D76.M1", "D76.M3"],
  filters     = {"D76.V2": "I20-I25"},   # Ischaemic heart diseases
  title       = "Ischaemic heart disease mortality by year"
)
```

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

## 🗺️ Geographic Limitation

**The CDC WONDER API only returns national-level data.** You cannot filter or group by state, county, MSA, census region, or urbanization category through the API. This is enforced server-side by CDC — it is not a limitation of this MCP server.

If you need sub-national data, your options are:

| Option | Geography | Notes |
|---|---|---|
| **WONDER web UI** | State, county, MSA | [wonder.cdc.gov](https://wonder.cdc.gov) — manual queries, downloadable CSV |
| **CDC PLACES** | County, census tract, ZIP | Health measures via [Socrata API](https://www.cdc.gov/places) |
| **NCHS compressed mortality files** | County | Bulk download, requires SAS/R/Python to process |
| **State vital statistics offices** | County, city | Vary by state; some have public APIs |

> **Example:** Bexar County, TX (San Antonio) mortality data is not available via this API. Use the WONDER web UI and filter to Texas → Bexar County, or use CDC PLACES for county health indicators.

---

## ⚠️ Other Limitations

| Limitation | Details |
|---|---|
| **Suppression** | Counts < 10 are suppressed and returned as `"Suppressed"`. Do not sum suppressed cells. |
| **Rate limit** | ~2 minutes between requests. This server enforces it automatically. |
| **Aggregates only** | No record-level microdata — returns summary statistics. |
| **Crude vs age-adjusted rates** | Crude rates reflect age structure, not underlying risk. Use `D76.M4` + `O_aar=aar_std` for age-adjusted rates, and pass the returned SE (`D76.M41`) to `calculate_rate_ratio` as `rate_se` for proper CIs. See the demo above. |
| **Attribution** | Published outputs must credit CDC WONDER and include all footnotes/caveats. |

---

## 🎬 Demo

### Demo 1: Age-adjusted mortality by race with rate ratio

US age-adjusted mortality by year and race, with a Black/White rate ratio for 2018–2020.

```
query_wonder(
  database_id = "D76",
  group_by    = ["D76.V1-level1", "D76.V8"],
  measures    = ["D76.M1", "D76.M4", "D76.M41"],
  options     = {"O_aar": "aar_std"},
  title       = "US Age-Adjusted Mortality by Year and Race 1999-2020"
)
```

```
Year   Race                             Deaths   AAR/100k       SE
-------------------------------------------------------------------
1999   American Indian or Alaska Native  11,311     780.89     8.18
1999   Asian or Pacific Islander         33,668     519.65     3.03
1999   Black or African American        284,987   1,135.67     2.18
1999   White                          2,061,077     854.64     0.60
  ...
2020   American Indian or Alaska Native  28,602     727.22     4.48
2020   Asian or Pacific Islander        101,811     469.18     1.49
2020   Black or African American        459,510   1,067.16     1.61
2020   White                          2,793,690     825.86     0.50
```

Then pool the 2018–2020 age-adjusted rates and compute a rate ratio using WONDER's supplied standard errors:

```
calculate_rate_ratio(
  group_1 = {"rate": 934.75, "rate_se": 0.89, "label": "Black or African American"},
  group_2 = {"rate": 759.81, "rate_se": 0.28, "label": "White"},
)
```

```
Age-Adjusted Rate Ratio : 1.230
95% CI                  : 1.228 – 1.233
Method                  : Delta method on log(RR) using supplied rate standard errors

The rate in Black or African American is 1.230 times the rate in White
(23.0% higher). 95% CI: 1.228–1.233.
```

> 💡 **Why age-adjustment matters:** The crude Black/White mortality rate ratio is ~0.88 (Black *lower*) because White Americans have an older age distribution, mechanically inflating their crude rates. After adjusting to the 2000 US standard population, the true picture emerges — Black mortality is **23% higher**. Always prefer age-adjusted rates for cross-group comparisons (`D76.M4` + `O_aar=aar_std`).

---

### Demo 2: All-cause mortality trend with APC + life expectancy at birth

Query all-cause age-stratified mortality, compute APC over the decade, and build a life table.

**Step 1** — Query age-stratified mortality for a single year to build a life table:

```
query_wonder(
  database_id = "D76",
  group_by    = ["D76.V5"],
  measures    = ["D76.M1", "D76.M2"],
  title       = "US All-Cause Mortality by Age Group 2019"
)
```

**Step 2** — Build the life table:

```
build_life_table_tool(
  age_stratified_rows = <rows from above>,
  deaths_col          = "Deaths",
  population_col      = "Population"
)
→ {
    "e0": 78.8,
    "rows": [
      {"age_group": "< 1 year",  "nMx": 0.00524, "lx": 100000, "ex": 78.8},
      {"age_group": "1-4 years", "nMx": 0.00024, "lx":  99476, "ex": 78.2},
      ...
    ]
  }
```

**Step 3** — Query annual crude rates 2010–2019, then measure the trend:

```
query_wonder(
  database_id = "D76",
  group_by    = ["D76.V1-level1"],
  measures    = ["D76.M1", "D76.M3"],
  title       = "US All-Cause Mortality by Year 2010-2019"
)
```

```
calculate_apc_tool(
  years = [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019],
  rates = [747.0, 741.3, 732.8, 724.6, 723.2, 733.1, 728.8, 731.9, 723.6, 715.2]
)
→ {
    "apc":      -0.4,
    "ci_lower": -0.7,
    "ci_upper": -0.1,
    "trend":    "Significantly decreasing (p = 0.014)",
    "interpretation": "Crude mortality declined by 0.4%/year (95% CI: -0.7% to -0.1%) over 2010–2019."
  }
```

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
│   ├── server.py      # MCP tools (FastMCP entry point) — 14 tools
│   ├── client.py      # HTTP client, XML builder, response parser
│   ├── databases.py   # Database registry and variable codebooks
│   ├── codegen.py     # Python + R code generation
│   ├── icd10.py       # Local ICD-10 chapter/sub-chapter lookup table
│   └── stats.py       # Epidemiological stats (rate ratio, APC, SMR, YLL, excess deaths, Kitagawa, life table)
└── tests/
    ├── test_client.py
    ├── test_codegen.py
    ├── test_stats.py
    ├── test_analytics.py
    └── test_kitagawa_lifetable_icd10.py
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
