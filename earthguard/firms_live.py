"""Near-real-time hotspots from the NASA FIRMS Area API.

Needs a free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
Put it in .streamlit/secrets.toml as   FIRMS_MAP_KEY = "..."   (never commit that file),
or in an environment variable FIRMS_MAP_KEY.

Suomi NPP stopped delivering data on Nov 2, 2026, so live VIIRS comes from NOAA-20 and NOAA-21.
"""

import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCES = {
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20",
    "VIIRS_NOAA21_NRT": "VIIRS NOAA-21",
    "MODIS_NRT": "MODIS",
}
# Our history was calibrated with ONE VIIRS satellite (Suomi NPP). To compare "now" with
# "normal" fairly we must also count only one: NOAA-20 flies the same orbit as Suomi NPP.
COMPARE_WITH_HISTORY = "VIIRS NOAA-20"
MAX_DAYS_PER_REQUEST = 5  # an API limit


def map_key() -> str | None:
    try:
        return st.secrets["FIRMS_MAP_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("FIRMS_MAP_KEY")


def _fetch(key: str, source: str, bbox: tuple, days: int, start: date | None) -> pd.DataFrame:
    west, south, east, north = bbox
    url = f"{BASE_URL}/{key}/{source}/{west:.4f},{south:.4f},{east:.4f},{north:.4f}/{days}"
    if start is not None:
        url += f"/{start.isoformat()}"
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    if not response.text.startswith("latitude"):
        raise RuntimeError(response.text.strip()[:200])  # e.g. "Invalid MAP_KEY."
    return pd.read_csv(io.StringIO(response.text))


@st.cache_data(ttl=3600, show_spinner="Asking NASA FIRMS for the latest hotspots…")
def recent_hotspots(bbox: tuple, days: int) -> pd.DataFrame:
    """All live hotspots inside bbox for the last `days` complete days PLUS today so far (UTC).

    Today is still incomplete (FIRMS dates are UTC and VIIRS data arrives hours late), so it is
    good for the map but not for comparing with "normal": use complete_days() for that.
    The API's DATE is the FIRST day of the range, and one request covers at most 5 days.
    """
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days)
    total = days + 1  # ...including today
    chunks = [(first_day + timedelta(days=offset), min(MAX_DAYS_PER_REQUEST, total - offset))
              for offset in range(0, total, MAX_DAYS_PER_REQUEST)]

    key = map_key()
    requests_to_send = [(source, label, start, length)
                        for source, label in SOURCES.items() for start, length in chunks]

    def fetch(job):
        source, label, start, length = job
        return _fetch(key, source, bbox, length, start).assign(sensor=label)

    # The requests do not depend on each other, so send them all at once instead of waiting.
    with ThreadPoolExecutor(max_workers=len(requests_to_send)) as pool:
        frames = list(pool.map(fetch, requests_to_send))
    return normalize(pd.concat(frames, ignore_index=True))


def complete_days(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Only the finished days (up to yesterday, UTC), for a fair comparison with history."""
    today = datetime.now(timezone.utc).date().isoformat()
    return hotspots[hotspots["acq_date"].astype(str) < today]


def normalize(hotspots: pd.DataFrame) -> pd.DataFrame:
    """Same confidence words for both sensors: low / nominal / high."""
    confidence = hotspots["confidence"].astype(str).str.lower()
    numeric = pd.to_numeric(confidence, errors="coerce")
    words = confidence.str[0].map({"l": "low", "n": "nominal", "h": "high"})
    from_number = pd.cut(numeric, [-1, 29, 79, 100], labels=["low", "nominal", "high"]).astype(str)
    hotspots["confidence_level"] = words.where(numeric.isna(), from_number)
    hotspots["time_utc"] = (hotspots["acq_date"].astype(str) + " "
                            + hotspots["acq_time"].astype(str).str.zfill(4).str[:2] + ":"
                            + hotspots["acq_time"].astype(str).str.zfill(4).str[2:])
    return hotspots
