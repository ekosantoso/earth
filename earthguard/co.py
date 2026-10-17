"""Carbon monoxide (CO) around the whole Earth, for the 3D globe — like NASA's "Eyes on the Earth".

Burning forests and peat release CO. The smoke gas rises and travels with the wind for days,
so a map of CO shows where fire smoke spreads, far beyond the fires themselves.

AIRS (Atmospheric Infrared Sounder) on NASA's Aqua satellite measures CO at about 5.5 km
height (500 hPa, ~18,000 ft) in infrared light, which also works at night and through thin
cloud. One day covers only strips of the Earth, so we combine the last few days: newer
measurements are pasted over older ones (the same trick as satellite.newest_photo).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urlencode

import numpy as np
import requests
import streamlit as st
from PIL import Image

from earthguard.maps import to_data_url
from earthguard.smoke import colormap, to_values

WMS_URL = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"   # plain lon/lat grid
COLORMAP_URL = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/AIRS_Carbon_Monoxide_Volume_Mixing_Ratio.xml"
LAYERS = ["AIRS_L2_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Night",
          "AIRS_L2_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Day"]
DAYS = 4                       # today + the 3 days before
WIDTH, HEIGHT = 1440, 720      # 0.25 degree per pixel, the whole world
# ppbv shown from blue (clean) to dark red. Clean air is ~60-90 ppbv; thick fire smoke over
# Indonesia reaches 350 (the most AIRS reports), so the scale must go that high to show detail.
LOW, HIGH = 60.0, 350.0
NO_DATA = (30, 41, 59)         # dark slate where no measurement exists
SMOOTH_PX = 3                  # blur radius in pixels (0.75 deg) to hide blocks and swath seams

# Colour stops like NASA Eyes: blue -> green -> yellow -> orange -> red -> dark red
STOPS = [(0.00, (43, 131, 186)), (0.12, (102, 194, 165)), (0.25, (171, 221, 164)),
         (0.40, (254, 224, 139)), (0.55, (253, 174, 97)), (0.72, (215, 25, 28)),
         (1.00, (103, 0, 31))]


def _box_blur(a: np.ndarray, radius: int) -> np.ndarray:
    """Average of each pixel's (2r+1) x (2r+1) neighbourhood. East-west wraps around the globe."""
    padded = np.concatenate([a[:, -radius:], a, a[:, :radius]], axis=1)
    padded = np.pad(padded, ((radius, radius), (0, 0)), mode="edge")
    for axis in (0, 1):
        c = np.cumsum(np.insert(padded, 0, 0, axis=axis), axis=axis)
        n = padded.shape[axis] - 2 * radius
        padded = (np.take(c, range(2 * radius + 1, 2 * radius + 1 + n), axis=axis)
                  - np.take(c, range(0, n), axis=axis)) / (2 * radius + 1)
    return padded


def smooth(values: np.ndarray, radius: int = SMOOTH_PX) -> np.ndarray:
    """Blur that ignores missing pixels: average only the measured neighbours. Running it
    twice gives a soft, Gaussian-like result; small gaps are filled, big gaps stay empty."""
    measured = np.isfinite(values).astype(float)
    total, count = np.nan_to_num(values), measured
    for _ in range(2):
        total, count = _box_blur(total, radius), _box_blur(count, radius)
    result = total / np.where(count > 0, count, 1)
    result[count < 0.15] = np.nan
    return result


def _download(layer: str, day: date) -> np.ndarray:
    query = urlencode({
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer, "STYLES": "",
        "CRS": "EPSG:4326", "BBOX": "-90,-180,90,180",   # WMS 1.3.0 + EPSG:4326 = latitude first
        "WIDTH": WIDTH, "HEIGHT": HEIGHT, "FORMAT": "image/png", "TRANSPARENT": "TRUE",
        "TIME": day.isoformat(),
    })
    response = requests.get(f"{WMS_URL}?{query}", timeout=90)
    response.raise_for_status()
    return to_values(response.content, colormap(COLORMAP_URL))


def colour(values: np.ndarray) -> np.ndarray:
    """CO numbers (ppbv) -> RGB picture with our colour scale; dark slate where unknown."""
    share = np.clip((np.nan_to_num(values, nan=LOW) - LOW) / (HIGH - LOW), 0, 1)
    positions, colours = zip(*STOPS)
    rgb = np.stack([np.interp(share, positions, [c[i] for c in colours]) for i in range(3)], -1)
    rgb[np.isnan(values)] = NO_DATA
    return rgb.astype(np.uint8)


@st.cache_data(ttl=3 * 3600, show_spinner="Getting NASA AIRS carbon monoxide data…")
def world_map(today: date) -> tuple[str, str, float]:
    """Returns (picture of the whole Earth as a data URL, dates covered, share with data)."""
    days = [today - timedelta(days=back) for back in range(DAYS - 1, -1, -1)]   # oldest first
    jobs = [(layer, day) for day in days for layer in LAYERS]

    def fetch(job):
        try:
            return _download(*job)
        except requests.RequestException:
            return None

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        pictures = [p for p in pool.map(fetch, jobs) if p is not None]
    if not pictures:
        raise RuntimeError("NASA AIRS carbon monoxide data is not available right now")

    values = np.full((HEIGHT, WIDTH), np.nan)
    for picture in pictures:                      # newer measurements replace older ones
        values = np.where(np.isnan(picture), values, picture)
    period = f"{days[0]:%d %b} – {days[-1]:%d %b %Y}"
    picture = Image.fromarray(colour(smooth(values)))
    return to_data_url(picture), period, float(np.isfinite(values).mean())
