"""Load the processed tables and run the analysis for one region.

st.cache_data remembers results, so picking a region you already looked at is instant.
"""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from earthguard import burn_calendar, harmonize
from earthguard.config import PROCESSED_DIR


@st.cache_data
def regions() -> pd.DataFrame:
    table = pd.read_parquet(PROCESSED_DIR / "regions.parquet")
    order = {"world": 0, "country": 1, "province": 2}
    return (table.assign(order=table["level"].map(order))
                 .sort_values(["order", "name"]).drop(columns="order")
                 .set_index("region_id"))


@st.cache_data
def _table(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")


def _rows(name: str, region_id: str) -> pd.DataFrame:
    table = _table(name)
    return table[table["region_id"] == region_id]


def parent_of(region_id: str) -> str | None:
    """province -> its country, country -> world, world -> nothing."""
    if region_id == "world":
        return None
    if region_id.startswith("country:"):
        return "world"
    return "country:" + regions().loc[region_id, "country"]


@st.cache_data
def ratios(region_id: str) -> pd.DataFrame:
    """VIIRS/MODIS ratio per month for a region, borrowing from its parent where data is thin."""
    parent_id = parent_of(region_id)
    parent = ratios(parent_id)["ratio"] if parent_id else None
    return harmonize.fit_ratios(harmonize.monthly_table(_rows("monthly", region_id)), parent)


@dataclass
class Analysis:
    monthly_table: pd.DataFrame     # raw MODIS and VIIRS cell-days per month
    harmonized_monthly: pd.Series   # one continuous MODIS-equivalent series
    monthly: pd.DataFrame           # calendar: years x months (harmonized)
    weekly: pd.DataFrame            # calendar: years x weeks (harmonized)


@st.cache_data
def analysis(region_id: str) -> Analysis:
    monthly_table = harmonize.monthly_table(_rows("monthly", region_id))
    weekly_table = harmonize.weekly_table(_rows("weekly", region_id))
    region_ratios = ratios(region_id)["ratio"]
    harmonized_monthly = harmonize.harmonize(monthly_table, region_ratios)
    harmonized_weekly = harmonize.harmonize_weekly(weekly_table, region_ratios)
    return Analysis(
        monthly_table, harmonized_monthly,
        burn_calendar.to_matrix(harmonized_monthly, "month"),
        burn_calendar.to_matrix(harmonized_weekly, "week"),
    )


@st.cache_data
def validation(region_id: str) -> dict:
    parent_id = parent_of(region_id)
    parent = ratios(parent_id)["ratio"] if parent_id else None
    return harmonize.validate(harmonize.monthly_table(_rows("monthly", region_id)), parent)
