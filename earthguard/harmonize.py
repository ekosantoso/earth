"""Harmonization: turn MODIS + VIIRS into ONE consistent record, in MODIS-equivalent units.

The idea in one sentence:
    From 2012 to 2025 both sensors watched the same places at the same time, so we can measure
    "how many times more cell-days VIIRS sees than MODIS" (the ratio), then divide VIIRS by
    that ratio to make it comparable with the MODIS years before 2012.

The ratio is learned separately for each month of the year, because it changes with the
season (e.g. small agricultural fires that only VIIRS can see happen in certain months).
If a region has too little data for a month, we fall back to a broader estimate:
    this month in this region  ->  all months in this region  ->  the parent region's ratio
"""

import numpy as np
import pandas as pd

from earthguard.config import (FIRST_YEAR, LAST_YEAR, MIN_MODIS_FOR_RATIO, MODIS,
                               OVERLAP_YEARS, VIIRS, VIIRS_FIRST_DAY, WEEKS_PER_YEAR)

MONTHS = range(1, 13)


def monthly_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Long rows (year, month, sensor, cell_days) -> wide table, one row per month.

    Index: first day of each month, 2001-01 .. 2025-12. Columns: MODIS, VIIRS.
    A month with no rows means "the satellite looked and saw no fire" -> 0.
    Before VIIRS started (20 Jan 2012) its value is NaN (unknown), not 0. That includes
    January 2012, which VIIRS only partly observed.
    """
    index = pd.date_range(f"{FIRST_YEAR}-01-01", f"{LAST_YEAR}-12-01", freq="MS")
    table = (rows.assign(date=pd.to_datetime(dict(year=rows["year"], month=rows["month"], day=1)))
                 .pivot_table(index="date", columns="sensor", values="cell_days",
                              aggfunc="sum", observed=True)
                 .reindex(index=index, columns=[MODIS, VIIRS])
                 .fillna(0.0))
    table.loc[table.index <= pd.Timestamp(VIIRS_FIRST_DAY), VIIRS] = np.nan
    return table


def fit_ratios(monthly: pd.DataFrame, parent: pd.Series | None = None,
               exclude_year: int | None = None) -> pd.DataFrame:
    """Learn the VIIRS / MODIS ratio for each month of the year (1..12).

    Returns a table indexed by month with two columns:
        ratio   how many VIIRS cell-days per MODIS cell-day
        basis   where the number came from: "this month", "all months" or "parent region"
    """
    first, last = OVERLAP_YEARS
    years = monthly.index.year
    overlap = monthly[(years >= first) & (years <= last) & (years != exclude_year)].dropna()
    sums = overlap.groupby(overlap.index.month)[[MODIS, VIIRS]].sum().reindex(MONTHS, fill_value=0)

    own_month = (sums[VIIRS] / sums[MODIS]).where(sums[MODIS] >= MIN_MODIS_FOR_RATIO)
    total_modis, total_viirs = sums[MODIS].sum(), sums[VIIRS].sum()
    own_total = total_viirs / total_modis if total_modis >= MIN_MODIS_FOR_RATIO else np.nan

    result = pd.DataFrame({"ratio": own_month, "basis": "this month"}, index=MONTHS)
    use_total = result["ratio"].isna() & pd.notna(own_total)
    result.loc[use_total, ["ratio", "basis"]] = [own_total, "all months"]
    if parent is not None:
        use_parent = result["ratio"].isna()
        result.loc[use_parent, "ratio"] = parent.reindex(MONTHS)[use_parent]
        result.loc[use_parent, "basis"] = "parent region"
    result["ratio"] = result["ratio"].astype(float)
    return result


def harmonize(monthly: pd.DataFrame, ratios: pd.Series) -> pd.Series:
    """One continuous MODIS-equivalent series: VIIRS / ratio where VIIRS exists, else MODIS."""
    viirs_as_modis = monthly[VIIRS] / monthly.index.month.map(ratios).to_numpy()
    return viirs_as_modis.fillna(monthly[MODIS]).rename("harmonized")


# Which month each week mostly falls in (week 1 = Jan 1-7 -> January, ...), so weekly data can
# use the monthly ratios. Day 3 of the week is its middle.
WEEK_TO_MONTH = pd.Series(
    (pd.Timestamp("2001-01-01") + pd.to_timedelta((np.arange(WEEKS_PER_YEAR)) * 7 + 3, "D")).month,
    index=range(1, WEEKS_PER_YEAR + 1),
)


def weekly_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Like monthly_table, but indexed by (year, week). Columns: MODIS, VIIRS."""
    index = pd.MultiIndex.from_product(
        [range(FIRST_YEAR, LAST_YEAR + 1), range(1, WEEKS_PER_YEAR + 1)], names=["year", "week"])
    table = (rows.pivot_table(index=["year", "week"], columns="sensor", values="cell_days",
                              aggfunc="sum", observed=True)
                 .reindex(index=index, columns=[MODIS, VIIRS])
                 .fillna(0.0))
    week_start = (pd.to_datetime(table.index.get_level_values("year").astype(str) + "-01-01")
                  + pd.to_timedelta((table.index.get_level_values("week") - 1) * 7, "D"))
    table.loc[week_start <= pd.Timestamp(VIIRS_FIRST_DAY), VIIRS] = np.nan
    return table


def harmonize_weekly(weekly: pd.DataFrame, ratios: pd.Series) -> pd.Series:
    month = WEEK_TO_MONTH.reindex(weekly.index.get_level_values("week")).to_numpy()
    viirs_as_modis = weekly[VIIRS] / ratios.reindex(month).to_numpy()
    return viirs_as_modis.fillna(weekly[MODIS]).rename("harmonized")


def validate(monthly: pd.DataFrame, parent: pd.Series | None = None) -> dict:
    """Leave-one-year-out test: can VIIRS / ratio predict what MODIS really saw?

    For every overlap year we learn the ratios WITHOUT that year, predict that year's
    MODIS values from VIIRS, and compare with the real MODIS values. A ratio that only works
    on the data it was learned from would score badly here.
    """
    first, last = OVERLAP_YEARS
    predicted, actual = [], []
    for year in range(first, last + 1):
        ratios = fit_ratios(monthly, parent, exclude_year=year)["ratio"]
        months = monthly[monthly.index.year == year]
        predicted.append(months[VIIRS] / months.index.month.map(ratios).to_numpy())
        actual.append(months[MODIS])
    predicted, actual = pd.concat(predicted), pd.concat(actual)

    valid = predicted.notna() & actual.notna()
    predicted, actual = predicted[valid], actual[valid]
    total_variation = ((actual - actual.mean()) ** 2).sum()
    r2 = 1 - ((actual - predicted) ** 2).sum() / total_variation if total_variation > 0 else np.nan
    # Percentage error only where MODIS saw enough fire for a percentage to mean something.
    enough = actual >= 10
    error = ((predicted[enough] - actual[enough]).abs() / actual[enough]).median()
    return {"months": int(valid.sum()), "r2": r2, "median_error": error,
            "predicted": predicted, "actual": actual}
