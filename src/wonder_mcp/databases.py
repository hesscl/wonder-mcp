"""Registry of known CDC WONDER databases with variable codebooks."""

from pydantic import BaseModel


class WonderDatabase(BaseModel):
    id: str
    label: str
    url_slug: str
    years: str
    description: str
    group_by_vars: dict[str, str]
    measure_vars: dict[str, str]
    filter_vars: dict[str, str]


# ---------------------------------------------------------------------------
# D76 — Detailed Mortality (ICD-10 Underlying Cause, 1999–present)
# ---------------------------------------------------------------------------

_D76_GROUP_BY = {
    "D76.V1-level1": "Year",
    "D76.V1-level2": "Month",
    "D76.V7": "Gender",
    "D76.V8": "Race",
    "D76.V17": "Hispanic Origin",
    "D76.V5": "Age Groups (5-year)",
    "D76.V51": "Age Groups (single-year, 0-85+)",
    "D76.V52": "Age Groups (infant)",
    "D76.V6": "Age Groups (10-year)",
    "D76.V2-level1": "ICD-10 Chapter",
    "D76.V2-level2": "ICD-10 Sub-chapter",
    "D76.V4": "ICD-10 List (113 leading causes)",
    "D76.V22": "Injury Intent",
    "D76.V23": "Injury Mechanism",
    "D76.V21": "Place of Death",
    "D76.V24": "Weekday",
    "D76.V25": "Autopsy",
    "D76.V27": "Education (2003 revision)",
    "D76.V9": "Education (1989 revision)",
}

_D76_MEASURES = {
    "D76.M1": "Deaths",
    "D76.M2": "Population",
    "D76.M3": "Crude Rate",
    "D76.M4": "Age-adjusted Rate",
    "D76.M9": "% of Total Deaths",
    "D76.M31": "Standard Error (Crude Rate)",
    "D76.M32": "Lower 95% CI (Crude Rate)",
    "D76.M33": "Upper 95% CI (Crude Rate)",
    "D76.M41": "Standard Error (Age-adjusted Rate)",
    "D76.M42": "Lower 95% CI (Age-adjusted Rate)",
    "D76.M43": "Upper 95% CI (Age-adjusted Rate)",
}

_D76_FILTERS = {
    "D76.V1": "Year (filter)",
    "D76.V7": "Gender (filter): F=Female, M=Male",
    "D76.V8": "Race (filter): 1002-5=AIAN, A-PI=Asian/PI, 2054-5=Black, 2106-3=White",
    "D76.V17": "Hispanic Origin: 2135-2=Hispanic, 2186-2=Not Hispanic, NS=Not Stated",
    "D76.V5": "Age Groups (filter)",
    "D76.V2": "ICD-10 Codes (filter)",
    "D76.V22": "Injury Intent (filter)",
    "D76.V21": "Place of Death (filter)",
}

# ---------------------------------------------------------------------------
# D176 — Provisional Multiple Cause of Death (updated monthly)
# ---------------------------------------------------------------------------

_D176_GROUP_BY = {
    "D176.V1-level1": "Year",
    "D176.V1-level2": "Month",
    "D176.V7": "Gender",
    "D176.V8": "Race",
    "D176.V17": "Hispanic Origin",
    "D176.V5": "Age Groups",
    "D176.V2-level1": "ICD-10 Chapter",
    "D176.V2-level2": "ICD-10 Sub-chapter",
    "D176.V22": "Injury Intent",
}

_D176_MEASURES = {
    "D176.M1": "Deaths",
    "D176.M2": "Population",
    "D176.M3": "Crude Rate",
}

_D176_FILTERS = {
    "D176.V1": "Year (filter)",
    "D176.V7": "Gender (filter)",
    "D176.V8": "Race (filter)",
    "D176.V17": "Hispanic Origin (filter)",
}

# ---------------------------------------------------------------------------
# D66 — Natality 2007–2024
# ---------------------------------------------------------------------------

_D66_GROUP_BY = {
    "D66.V1-level1": "Year",
    "D66.V1-level2": "Month",
    "D66.V6": "Mother's Race",
    "D66.V10": "Mother's Hispanic Origin",
    "D66.V11": "Mother's Age",
    "D66.V19": "Father's Race",
    "D66.V23": "Child's Gender",
    "D66.V24": "Gestational Age",
    "D66.V25": "Birth Weight",
    "D66.V2": "State",
}

_D66_MEASURES = {
    "D66.M1": "Births",
    "D66.M2": "Fertility Rate",
    "D66.M3": "Birth Rate",
}

_D66_FILTERS = {
    "D66.V1": "Year (filter)",
    "D66.V6": "Mother's Race (filter)",
    "D66.V10": "Mother's Hispanic Origin (filter)",
    "D66.V11": "Mother's Age (filter)",
    "D66.V23": "Child's Gender (filter)",
}

# ---------------------------------------------------------------------------
# D149 — Natality 2016–2024 (expanded)
# ---------------------------------------------------------------------------

_D149_GROUP_BY = {
    "D149.V1-level1": "Year",
    "D149.V6": "Mother's Race",
    "D149.V10": "Mother's Hispanic Origin",
    "D149.V11": "Mother's Age",
    "D149.V23": "Child's Gender",
    "D149.V24": "Gestational Age",
    "D149.V25": "Birth Weight",
    "D149.V30": "Mother's Education",
    "D149.V31": "WIC Recipient",
    "D149.V32": "Prenatal Care",
    "D149.V33": "Delivery Method",
}

_D149_MEASURES = {
    "D149.M1": "Births",
    "D149.M2": "Fertility Rate",
}

_D149_FILTERS = {
    "D149.V1": "Year (filter)",
    "D149.V6": "Mother's Race (filter)",
    "D149.V10": "Mother's Hispanic Origin (filter)",
}

# ---------------------------------------------------------------------------
# D10 — Natality 1995–2002
# ---------------------------------------------------------------------------

_D10_GROUP_BY = {
    "D10.V1-level1": "Year",
    "D10.V6": "Mother's Race",
    "D10.V11": "Mother's Age",
    "D10.V23": "Child's Gender",
}

_D10_MEASURES = {
    "D10.M1": "Births",
}

_D10_FILTERS = {
    "D10.V1": "Year (filter)",
    "D10.V6": "Mother's Race (filter)",
}

# ---------------------------------------------------------------------------
# D27 — Natality 2003–2006
# ---------------------------------------------------------------------------

_D27_GROUP_BY = {
    "D27.V1-level1": "Year",
    "D27.V6": "Mother's Race",
    "D27.V10": "Mother's Hispanic Origin",
    "D27.V11": "Mother's Age",
    "D27.V23": "Child's Gender",
}

_D27_MEASURES = {
    "D27.M1": "Births",
}

_D27_FILTERS = {
    "D27.V1": "Year (filter)",
    "D27.V6": "Mother's Race (filter)",
}

# ---------------------------------------------------------------------------
# D104 — Heat Wave Days
# ---------------------------------------------------------------------------

_D104_GROUP_BY = {
    "D104.V1": "Year",
    "D104.V2": "State",
    "D104.V3": "Month",
}

_D104_MEASURES = {
    "D104.M1": "Heat Wave Days",
    "D104.M2": "Cooling Degree Days",
}

_D104_FILTERS = {
    "D104.V1": "Year (filter)",
    "D104.V2": "State (filter)",
}

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DATABASES: dict[str, WonderDatabase] = {
    "D76": WonderDatabase(
        id="D76",
        label="Detailed Mortality (ICD-10)",
        url_slug="ucd-icd10",
        years="1999–2020+",
        description=(
            "Underlying cause of death data from death certificates filed in the "
            "50 states and the District of Columbia. Coded using ICD-10."
        ),
        group_by_vars=_D76_GROUP_BY,
        measure_vars=_D76_MEASURES,
        filter_vars=_D76_FILTERS,
    ),
    "D176": WonderDatabase(
        id="D176",
        label="Provisional Multiple Cause of Death",
        url_slug="mcd-icd10-provisional",
        years="2018–present (updated monthly)",
        description=(
            "Provisional multiple cause of death data, updated monthly. "
            "Includes both underlying and contributing causes."
        ),
        group_by_vars=_D176_GROUP_BY,
        measure_vars=_D176_MEASURES,
        filter_vars=_D176_FILTERS,
    ),
    "D66": WonderDatabase(
        id="D66",
        label="Natality 2007–2024",
        url_slug="natality-current",
        years="2007–2024",
        description=(
            "Birth certificate data for live births occurring within the United States. "
            "Covers 2007 through the most recent year."
        ),
        group_by_vars=_D66_GROUP_BY,
        measure_vars=_D66_MEASURES,
        filter_vars=_D66_FILTERS,
    ),
    "D149": WonderDatabase(
        id="D149",
        label="Natality 2016–2024 (expanded)",
        url_slug="natality-expanded-current",
        years="2016–2024",
        description=(
            "Expanded birth certificate data including additional maternal and "
            "infant health variables. Covers 2016 through the most recent year."
        ),
        group_by_vars=_D149_GROUP_BY,
        measure_vars=_D149_MEASURES,
        filter_vars=_D149_FILTERS,
    ),
    "D10": WonderDatabase(
        id="D10",
        label="Natality 1995–2002",
        url_slug="natality-v2002",
        years="1995–2002",
        description="Birth certificate data for live births, 1995–2002.",
        group_by_vars=_D10_GROUP_BY,
        measure_vars=_D10_MEASURES,
        filter_vars=_D10_FILTERS,
    ),
    "D27": WonderDatabase(
        id="D27",
        label="Natality 2003–2006",
        url_slug="natality-v2006",
        years="2003–2006",
        description="Birth certificate data for live births, 2003–2006.",
        group_by_vars=_D27_GROUP_BY,
        measure_vars=_D27_MEASURES,
        filter_vars=_D27_FILTERS,
    ),
    "D104": WonderDatabase(
        id="D104",
        label="Heat Wave Days",
        url_slug="NCA-heatwavedays-historic",
        years="1961–2010",
        description=(
            "Historical heat wave days and related climate data by state, "
            "from the National Climate Assessment."
        ),
        group_by_vars=_D104_GROUP_BY,
        measure_vars=_D104_MEASURES,
        filter_vars=_D104_FILTERS,
    ),
}


def get_database(database_id: str) -> WonderDatabase:
    """Return a database by ID, raising KeyError with a helpful message if not found."""
    if database_id not in DATABASES:
        known = ", ".join(sorted(DATABASES.keys()))
        raise KeyError(
            f"Unknown database '{database_id}'. Known databases: {known}"
        )
    return DATABASES[database_id]
