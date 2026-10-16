"""Download the NASA FIRMS "Country Yearly Summary" archives.

Each file is one year of active-fire detections for every country, as a zip of CSVs.
Source page: https://firms.modaps.eosdis.nasa.gov/country/

Run from the repo root:
    python etl/download.py            # everything (~7 GB)
    python etl/download.py 2015 2019  # only these years

Files that are already complete are skipped, so it is safe to re-run after an interruption.
"""

import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/data/country/zips"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PARALLEL_DOWNLOADS = 4

# MODIS starts in November 2000, so 2001 is the first full year.
# VIIRS on Suomi NPP starts in January 2012.
SENSORS = {
    "modis": range(2001, 2026),
    "viirs-snpp": range(2012, 2026),
}


def remote_size(url: str) -> int:
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:
        return int(response.headers["Content-Length"])


def download(url: str, target: Path) -> None:
    size = remote_size(url)
    if target.exists() and target.stat().st_size == size:
        print(f"skip  {target.name} (already complete)", flush=True)
        return

    # Download to a temporary name first, so a half-finished file is never mistaken for a full one.
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, "wb") as out:
        done = 0
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            done += len(chunk)
    if done != size:
        raise IOError(f"{target.name}: got {done} bytes, expected {size}")
    partial.replace(target)
    print(f"done  {target.name} ({size / 1e6:.0f} MB)", flush=True)


def download_safely(name: str) -> None:
    try:
        download(f"{BASE_URL}/{name}", RAW_DIR / name)
    except Exception as error:  # keep going; re-running later retries failures
        print(f"FAIL  {name}: {error}", flush=True)


def main(years: list[int]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # MODIS first: it is smaller and already enough for a MODIS-only calendar.
    names = [
        f"{sensor}_{year}_all_countries.zip"
        for sensor, available in SENSORS.items()
        for year in available
        if not years or year in years
    ]
    # One connection is slow (~0.6 MB/s), so download a few files at the same time.
    with ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as pool:
        list(pool.map(download_safely, names))


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]])
