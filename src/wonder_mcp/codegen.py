"""Generate self-contained Python and R replication scripts from QueryResult."""

from __future__ import annotations

from .client import QueryResult


def generate_python(result: QueryResult) -> str:
    """Return a self-contained Python script that replicates the query."""
    db = result.database_id
    url = f"https://wonder.cdc.gov/controller/datarequest/{db}"
    # Escape triple-quotes inside the XML (extremely unlikely but safe)
    safe_xml = result.xml_sent.replace('"""', r'\"\"\"')
    columns_repr = repr(result.columns)
    caveats_block = "\n".join(f"#   {c}" for c in result.caveats) if result.caveats else "#   (none)"

    return f'''\
#!/usr/bin/env python3
"""
CDC WONDER Query — Self-Contained Replication Script
Database  : {result.database_id}
Title     : {result.params.title or "(no title)"}
Queried at: {result.queried_at}

Dependencies: requests, beautifulsoup4, lxml
  pip install requests beautifulsoup4 lxml

Caveats from original query:
{caveats_block}

This script is fully self-contained.  It does not depend on wonder-mcp.
"""

import csv
import sys
import requests
from bs4 import BeautifulSoup

URL = {url!r}

XML = """{safe_xml}"""

COLUMNS = {columns_repr}


def main() -> None:
    response = requests.post(
        URL,
        data={{"request_xml": XML, "accept_datause_restrictions": "true"}},
        timeout=360,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Surface any error messages
    errors = soup.find_all("error")
    if errors:
        for err in errors:
            print("ERROR:", err.get_text(strip=True), file=sys.stderr)
        sys.exit(1)

    # Print caveats
    for caveat in soup.find_all("caveats"):
        print("# CAVEAT:", caveat.get_text(strip=True), file=sys.stderr)

    # Parse rows
    rows = []
    for row_tag in soup.find_all("r"):
        cells = row_tag.find_all("c")
        row = {{}}
        for idx, cell in enumerate(cells):
            col = COLUMNS[idx] if idx < len(COLUMNS) else f"col_{{idx}}"
            v_attr = cell.get("v")
            l_attr = cell.get("l")
            row[col] = v_attr if v_attr is not None else (l_attr or cell.get_text(strip=True))
        if row:
            rows.append(row)

    if not rows:
        print("# No data rows returned.", file=sys.stderr)
        return

    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()
'''


def generate_r(result: QueryResult) -> str:
    """Return a self-contained R script that replicates the query."""
    db = result.database_id
    url = f"https://wonder.cdc.gov/controller/datarequest/{db}"
    # Escape single quotes inside the XML for embedding in R single-quoted string
    safe_xml = result.xml_sent.replace("'", "\\'")
    caveats_block = "\n".join(f"# {c}" for c in result.caveats) if result.caveats else "# (none)"

    return f'''\
# CDC WONDER Query — Self-Contained Replication Script
# Database  : {result.database_id}
# Title     : {result.params.title or "(no title)"}
# Queried at: {result.queried_at}
#
# Dependencies: httr, xml2
#   install.packages(c("httr", "xml2"))
#
# Caveats from original query:
{caveats_block}
#
# This script is fully self-contained and requires no external R packages beyond httr and xml2.

library(httr)
library(xml2)

url <- {url!r}

xml_body <- \'{safe_xml}\'

resp <- POST(
  url,
  body = list(
    request_xml = xml_body,
    accept_datause_restrictions = "true"
  ),
  encode = "form"
)

stop_for_status(resp)

raw_xml <- content(resp, as = "text", encoding = "UTF-8")
doc <- read_xml(raw_xml)

# Surface errors
errors <- xml_find_all(doc, "//error")
if (length(errors) > 0) {{
  stop(paste(xml_text(errors), collapse = "; "))
}}

# Print caveats
caveats <- xml_find_all(doc, "//caveats")
for (cav in caveats) {{
  message("CAVEAT: ", xml_text(cav))
}}

# Parse rows
row_nodes <- xml_find_all(doc, "//r")

parse_row <- function(row_node) {{
  cells <- xml_find_all(row_node, "c")
  vals <- sapply(cells, function(cell) {{
    v_attr <- xml_attr(cell, "v")
    l_attr <- xml_attr(cell, "l")
    if (!is.na(v_attr)) v_attr else if (!is.na(l_attr)) l_attr else xml_text(cell)
  }})
  vals
}}

if (length(row_nodes) == 0) {{
  message("No data rows returned.")
}} else {{
  data_list <- lapply(row_nodes, parse_row)
  df <- as.data.frame(do.call(rbind, data_list), stringsAsFactors = FALSE)
  print(df)
  # To export as CSV:
  # write.csv(df, "wonder_results.csv", row.names = FALSE)
}}
'''
