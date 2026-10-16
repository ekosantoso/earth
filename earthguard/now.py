"""What is happening RIGHT NOW: live hotspots compared with the 25-year record.

Live hotspots arrive for a rectangle on the map, which also covers neighbours (the rectangle
around Indonesia includes northern Australia!). So first we find which province each hotspot
is in, and keep only the ones inside the chosen place.
"""

import numpy as np
import pandas as pd
import streamlit as st

from earthguard import burn_calendar, data, firms_live, ui
from earthguard.config import GRID_DEG, PROCESSED_DIR, PROVINCE_CELLS


@st.cache_data
def _cell_provinces() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "cell_provinces.parquet")


def locate(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Add province_id and country to every hotspot (both empty if the place is unknown)."""
    size = GRID_DEG * PROVINCE_CELLS
    keyed = hotspots.assign(kx=np.floor(hotspots["longitude"] / size).astype("int16"),
                            ky=np.floor(hotspots["latitude"] / size).astype("int16"))
    located = keyed.merge(_cell_provinces(), on=["kx", "ky"], how="left")
    located = located.rename(columns={"region_id": "province_id"}).drop(columns=["kx", "ky"])
    countries = data.regions()["country"]
    located["country"] = located["province_id"].astype(object).map(countries).fillna("")
    return located


def inside(located: pd.DataFrame, region_id: str) -> pd.DataFrame:
    """Only the hotspots inside the chosen place."""
    if region_id == "world":
        return located
    if region_id.startswith("country:"):
        return located[located["country"] == region_id.removeprefix("country:")]
    return located[located["province_id"] == region_id]


def times_normal(finished: pd.DataFrame, region_id: str, days: int) -> tuple[float, float]:
    """(activity now, × normal) for the last `days` complete days.

    Measured exactly like the history: one VIIRS satellite, ~1 km cells counted once per day,
    divided by this month's VIIRS/MODIS ratio, compared with a normal week at this time of year.
    """
    viirs = finished[finished["sensor"] == firms_live.COMPARE_WITH_HISTORY]
    cell_days = len(viirs.assign(cx=np.floor(viirs["longitude"] / GRID_DEG),
                                 cy=np.floor(viirs["latitude"] / GRID_DEG))
                         .drop_duplicates(["cx", "cy", "acq_date"]))
    activity = cell_days / data.ratios(region_id)["ratio"][ui.current_month()]
    weekly = data.analysis(region_id).weekly
    normal = burn_calendar.typical(weekly).get(ui.current_week(), 0.0) * days / 7
    return activity, activity / max(normal, 1)


def hottest_parts(finished: pd.DataFrame, region_id: str, days: int, top: int = 3) -> pd.DataFrame:
    """The provinces (of a country) or countries (of the world) with the most hotspots now."""
    if region_id.startswith("province:"):
        return pd.DataFrame()
    if region_id == "world":
        keys = "country:" + finished.loc[finished["country"] != "", "country"]
    else:
        keys = finished["province_id"].dropna().astype(str)
    counts = keys.value_counts().head(top)
    names = data.regions()["name"]
    rows = []
    for part_id, hotspots in counts.items():
        part = finished[(finished["province_id"] == part_id) if part_id.startswith("province:")
                        else (finished["country"] == part_id.removeprefix("country:"))]
        rows.append({"name": names[part_id].split(",")[0], "hotspots": hotspots,
                     "times": times_normal(part, part_id, days)[1]})
    return pd.DataFrame(rows)
