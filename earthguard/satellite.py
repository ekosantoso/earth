"""The newest NASA satellite photo of an area, to see smoke next to the hotspots.

NASA GIBS publishes a true-colour photo of the whole Earth for every satellite pass, a few hours
after the satellite flies over. Each satellite photographs a strip at a time, so for "today"
some areas are still black (not photographed yet).

Our trick, in one sentence: start with yesterday afternoon's full photo, then paste on top every
pixel that a satellite has already photographed today. The result is always complete, and as
new as possible.
"""

import io
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urlencode

import numpy as np
import requests
import streamlit as st
from PIL import Image

from earthguard.maps import to_data_url

WMS_URL = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi"
MORNING = "MODIS_Terra_CorrectedReflectance_TrueColor"      # passes ~10:30 local time
AFTERNOON = "VIIRS_NOAA20_CorrectedReflectance_TrueColor"   # passes ~13:30 local time

EARTH_HALF_WIDTH_M = 20037508.34  # half the width of the web map, in metres
MAX_LAT = 85.0                    # web maps stop near the poles
WIDTH = 1600                      # pixels
BLACK = 3                         # a pixel this dark in every colour = "not photographed yet"


def _mercator(lon: float, lat: float) -> tuple[float, float]:
    """Longitude/latitude -> web-map metres (EPSG:3857), the projection the map is drawn in."""
    x = lon * EARTH_HALF_WIDTH_M / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * EARTH_HALF_WIDTH_M / math.pi
    return x, y


def frame(bbox: tuple) -> list[float]:
    """The area to photograph: the region plus half its size on every side, so the edges of
    the map view are covered too."""
    west, south, east, north = bbox
    pad_x, pad_y = (east - west) * 0.5, (north - south) * 0.5
    return [max(west - pad_x, -180.0), max(south - pad_y, -MAX_LAT),
            min(east + pad_x, 180.0), min(north + pad_y, MAX_LAT)]


def _download(layer: str, day: date, bounds: list[float]) -> np.ndarray:
    west, south, east, north = bounds
    (x0, y0), (x1, y1) = _mercator(west, south), _mercator(east, north)
    height = max(200, min(WIDTH, round(WIDTH * (y1 - y0) / (x1 - x0))))
    url = WMS_URL + "?" + urlencode({
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer,
        "STYLES": "", "CRS": "EPSG:3857", "BBOX": f"{x0},{y0},{x1},{y1}",
        "WIDTH": WIDTH, "HEIGHT": height, "FORMAT": "image/jpeg", "TIME": day.isoformat(),
    })
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    return np.asarray(Image.open(io.BytesIO(response.content)).convert("RGB"))


@st.cache_data(ttl=3600, show_spinner="Getting the newest NASA satellite photo…")
def newest_photo(bbox: tuple, today: date) -> tuple[str, list[float], float]:
    """Returns (image as a data URL, its bounds, share of the area photographed today)."""
    bounds = frame(bbox)
    # Oldest first: each newer photo is pasted over the older ones where it has pixels.
    passes = [(AFTERNOON, today - timedelta(days=1)), (MORNING, today), (AFTERNOON, today)]
    with ThreadPoolExecutor(max_workers=len(passes)) as pool:   # download all 3 at once
        pictures = list(pool.map(lambda p: _download(p[0], p[1], bounds), passes))

    photo, today_share = None, 0.0
    for picture in pictures:
        photographed = picture.max(axis=2) > BLACK
        if photo is None:
            photo = picture.copy()
        else:
            photo[photographed] = picture[photographed]
            today_share = max(today_share, photographed.mean())

    return to_data_url(Image.fromarray(photo)), bounds, float(today_share)


WORLD_LAT = 85.0511   # where the square web map ends (north and south)
WORLD_WIDTH = 2048    # pixels for the whole-world background


@st.cache_data(ttl=30 * 24 * 3600, show_spinner=False)
def blue_marble() -> tuple[str, list[float]]:
    """NASA's "Blue Marble": a cloud-free picture of the whole Earth, used as the background
    everywhere outside today's sharp photo (like Google Earth when zoomed out)."""
    query = urlencode({
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0",
        "LAYERS": "BlueMarble_NextGeneration", "STYLES": "", "CRS": "EPSG:3857",
        "BBOX": f"{-EARTH_HALF_WIDTH_M},{-EARTH_HALF_WIDTH_M},{EARTH_HALF_WIDTH_M},{EARTH_HALF_WIDTH_M}",
        "WIDTH": WORLD_WIDTH, "HEIGHT": WORLD_WIDTH, "FORMAT": "image/jpeg",
    })
    response = requests.get(f"{WMS_URL}?{query}", timeout=120)
    response.raise_for_status()
    picture = Image.open(io.BytesIO(response.content)).convert("RGB")
    return to_data_url(picture), [-180.0, -WORLD_LAT, 180.0, WORLD_LAT]
