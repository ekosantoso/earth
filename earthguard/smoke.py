"""How much of a place is covered by smoke or haze, from NASA satellite aerosol data.

Aerosol Optical Depth (AOD) measures how much the air blocks sunlight because of particles in
it: smoke, dust, pollution. Clean air is about 0.1; thick smoke is 1 or more.
MODIS on Terra (morning) and Aqua (afternoon) measure it every day on a ~3 km grid.

NASA GIBS sends AOD as a coloured picture. Its colour legend (the "colormap") tells us which
colour means which AOD value, so we can turn the picture back into numbers.

Limits worth explaining: satellites cannot measure AOD under clouds, and very thick smoke is
sometimes mistaken for cloud. So "covered by smoke" is a share of the area the satellites
could SEE, and real smoke can be larger.
"""

import io
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests
import streamlit as st
from PIL import Image

from earthguard import data
from earthguard.config import GRID_DEG, PROCESSED_DIR, PROVINCE_CELLS
from earthguard.maps import to_data_url
from earthguard.satellite import WMS_URL, _mercator, frame

COLORMAP_URL = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/MODIS_VIIRS_AOD.xml"
TERRA = "MODIS_Terra_Aerosol_Optical_Depth_3km"
AQUA = "MODIS_Aqua_Aerosol_Optical_Depth_3km"
WIDTH = 1600          # pixels, same as the satellite photo so both stay sharp to the zoom limit
HAZE = 0.5            # AOD at or above this = smoky / hazy air
THICK = 1.0           # AOD at or above this = thick smoke


@st.cache_data(ttl=24 * 3600)
def colormap(url: str = COLORMAP_URL) -> dict[int, float]:
    """A GIBS colour legend: colour (packed as one number) -> value (lower edge of its range)."""
    xml = requests.get(url, timeout=60).text
    table = {}
    for entry in re.findall(r"<ColorMapEntry[^>]*>", xml):
        rgb = re.search(r'rgb="(\d+),(\d+),(\d+)"', entry)
        value = re.search(r'value="\[?(-?[\d.]+)', entry)
        if rgb and value:
            r, g, b = map(int, rgb.groups())
            table[(r << 16) | (g << 8) | b] = float(value.group(1))
    return table


def to_values(png: bytes, lookup: dict[int, float]) -> np.ndarray:
    """A GIBS picture -> numbers, using its colour legend. NaN where there is no measurement."""
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).astype(np.int32)
    packed = (pixels[..., 0] << 16) | (pixels[..., 1] << 8) | pixels[..., 2]
    values = np.vectorize(lambda colour: lookup.get(colour, np.nan), otypes=[float])(packed)
    values[pixels[..., 3] == 0] = np.nan   # transparent = no measurement (cloud, night, gap)
    return values


def _download(layer: str, day: date, bounds: list[float]) -> np.ndarray:
    """One AOD picture turned into numbers (NaN where there is no measurement)."""
    west, south, east, north = bounds
    (x0, y0), (x1, y1) = _mercator(west, south), _mercator(east, north)
    height = max(100, min(WIDTH, round(WIDTH * (y1 - y0) / (x1 - x0))))
    url = WMS_URL + "?" + urlencode({
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer,
        "STYLES": "", "CRS": "EPSG:3857", "BBOX": f"{x0},{y0},{x1},{y1}", "WIDTH": WIDTH,
        "HEIGHT": height, "FORMAT": "image/png", "TRANSPARENT": "TRUE", "TIME": day.isoformat(),
    })
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    return to_values(response.content, colormap())


@st.cache_data(ttl=3600, show_spinner="Measuring smoke from NASA aerosol data…")
def smoke_map(bbox: tuple, today: date) -> tuple[np.ndarray, list[float]]:
    """Newest AOD for every pixel: today's passes first, yesterday's where today has a gap."""
    bounds = frame(bbox)
    passes = [(AQUA, today), (TERRA, today), (AQUA, today - timedelta(days=1)),
              (TERRA, today - timedelta(days=1))]   # newest first
    def fetch(job):
        try:
            return _download(job[0], job[1], bounds)
        except requests.RequestException:
            return None

    with ThreadPoolExecutor(max_workers=len(passes)) as pool:   # download all 4 at once
        pictures = [p for p in pool.map(fetch, passes) if p is not None]
    if not pictures:
        raise RuntimeError("NASA aerosol data is not available right now")
    aod = pictures[0]
    for picture in pictures[1:]:                                 # fill gaps with older passes
        aod = np.where(np.isnan(aod), picture, aod)
    return aod, bounds


def overlay(aod: np.ndarray, bounds: list[float]) -> str:
    """A see-through smoke picture for the map (yellow = haze ... red = thick smoke),
    as a data URL like satellite.newest_photo()."""
    strength = np.clip((np.nan_to_num(aod, nan=0.0) - HAZE / 2) / (2.0 - HAZE / 2), 0, 1)
    rgba = np.zeros(aod.shape + (4,), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = (220 * (1 - strength)).astype(np.uint8)
    rgba[..., 2] = 40
    rgba[..., 3] = np.where(np.nan_to_num(aod, nan=0.0) >= HAZE / 2, 90 + 140 * strength, 0)
    return to_data_url(Image.fromarray(rgba, "RGBA"), "PNG")


@st.cache_data
def _cells() -> pd.DataFrame:
    """Centres of every ~5 km cell with a known province (from the fire record)."""
    cells = pd.read_parquet(PROCESSED_DIR / "cell_provinces.parquet")
    size = GRID_DEG * PROVINCE_CELLS
    cells["lon"], cells["lat"] = (cells["kx"] + 0.5) * size, (cells["ky"] + 0.5) * size
    cells["country"] = cells["region_id"].astype(object).map(data.regions()["country"])
    return cells


def by_province(aod: np.ndarray, bounds: list[float], region_id: str) -> pd.DataFrame:
    """For every province in the place: share of its seen area that is hazy, and mean AOD.

    We sample the AOD picture at the centre of each province cell, like dropping pins.
    """
    cells = _cells()
    if region_id.startswith("country:"):
        cells = cells[cells["country"] == region_id.removeprefix("country:")]
    elif region_id.startswith("province:"):
        cells = cells[cells["region_id"] == region_id]
    west, south, east, north = bounds
    (x0, y0), (x1, y1) = _mercator(west, south), _mercator(east, north)
    xs, ys = zip(*(_mercator(lon, lat) for lon, lat in zip(cells["lon"], cells["lat"])))
    height, width = aod.shape
    col = ((np.array(xs) - x0) / (x1 - x0) * width).astype(int)
    row = ((y1 - np.array(ys)) / (y1 - y0) * height).astype(int)
    ok = (col >= 0) & (col < width) & (row >= 0) & (row < height)
    sampled = cells[ok].assign(aod=aod[row[ok], col[ok]])
    seen = sampled.dropna(subset=["aod"])
    if seen.empty:
        return pd.DataFrame()
    table = seen.groupby("region_id", observed=True).agg(
        hazy=("aod", lambda v: (v >= HAZE).mean()), aod=("aod", "mean"), seen=("aod", "size"))
    table["total"] = sampled.groupby("region_id", observed=True).size()
    table["name"] = data.regions()["name"].reindex(table.index).str.split(",").str[0]
    return table.sort_values("aod", ascending=False)


def describe(aod: np.ndarray, bounds: list[float], region_id: str, place: str) -> str:
    """One or two sentences about smoke for the summary."""
    table = by_province(aod, bounds, region_id)
    if table.empty or table["seen"].sum() < 20:
        return ("**Smoke/haze:** satellites could not measure the air over "
                f"{place} today or yesterday (clouds, or smoke too thick to see through).")
    seen = table["seen"].sum()
    hazy = (table["hazy"] * table["seen"]).sum() / seen
    seen_share = seen / table["total"].sum()
    sentence = (f"**Smoke/haze:** about **{hazy:.0%}** of {place} that satellites could see "
                f"has smoky or hazy air (aerosol ≥ {HAZE}).")
    worst = table[(table["aod"] >= HAZE) & (table["seen"] >= 5)].head(3)
    if len(worst) and not region_id.startswith("province:"):
        sentence += " Thickest over " + ", ".join(
            f"**{row.name}** ({'thick smoke' if row.aod >= THICK else 'haze'}, AOD {row.aod:.1f})"
            for row in worst.itertuples()) + "."
    if seen_share < 0.5:
        sentence += (f" {1 - seen_share:.0%} of the area could not be measured (clouds, or smoke "
                     "too thick to see through), so the smoke may be wider.")
    return sentence
