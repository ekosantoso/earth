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


BLUE_MARBLE = "BlueMarble_NextGeneration"   # NASA's cloud-free picture of the whole Earth
WORLD = [-180.0, -85.0511, 180.0, 85.0511]   # where the square web map ends
WORLD_WIDTH = 2048                           # pixels for the whole-world background


def _download(layer: str, day: date | None, bounds: list[float], width: int) -> np.ndarray:
    west, south, east, north = bounds
    (x0, y0), (x1, y1) = _mercator(west, south), _mercator(east, north)
    height = max(200, min(width, round(width * (y1 - y0) / (x1 - x0))))
    query = {
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer,
        "STYLES": "", "CRS": "EPSG:3857", "BBOX": f"{x0},{y0},{x1},{y1}",
        "WIDTH": width, "HEIGHT": height, "FORMAT": "image/jpeg",
    }
    if day is not None:          # Blue Marble has no date
        query["TIME"] = day.isoformat()
    response = requests.get(WMS_URL + "?" + urlencode(query), timeout=120)
    response.raise_for_status()
    return np.asarray(Image.open(io.BytesIO(response.content)).convert("RGB"))


def _newest(bounds: list[float], today: date, width: int) -> tuple[str, float]:
    """Paste the newest satellite pixels over each other, oldest first:
    Blue Marble (cloud-free, never empty) -> yesterday afternoon -> today morning ->
    today afternoon. The world background and the sharp photo are made exactly the same way,
    so clouds and smoke continue seamlessly from one into the other."""
    passes = [(BLUE_MARBLE, None), (AFTERNOON, today - timedelta(days=1)),
              (MORNING, today), (AFTERNOON, today)]
    with ThreadPoolExecutor(max_workers=len(passes)) as pool:   # download all at once
        pictures = list(pool.map(lambda p: _download(p[0], p[1], bounds, width), passes))

    photo, today_share = pictures[0].copy(), 0.0
    for picture in pictures[1:]:
        photographed = picture.max(axis=2) > BLACK
        photo[photographed] = picture[photographed]
        if picture is not pictures[1]:
            today_share = max(today_share, photographed.mean())
    return to_data_url(Image.fromarray(photo)), float(today_share)


@st.cache_data(ttl=3600, show_spinner="Getting the newest NASA satellite photo…")
def newest_photo(bbox: tuple, today: date) -> tuple[str, list[float], float]:
    """Sharp photo of the area around the place: (data URL, bounds, share photographed today)."""
    bounds = frame(bbox)
    image, today_share = _newest(bounds, today, WIDTH)
    return image, bounds, today_share


@st.cache_data(ttl=3600, show_spinner="Getting the newest NASA satellite photo of the world…")
def world_photo(today: date) -> tuple[str, list[float]]:
    """The same newest photo for the whole world, less sharp, used as the map background."""
    image, _ = _newest(WORLD, today, WORLD_WIDTH)
    return image, WORLD
