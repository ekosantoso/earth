"""ETL step 1: yearly FIRMS zip  ->  cleaned "active-fire cell-days".

Why cell-days?
    VIIRS pixels (375 m) are much smaller than MODIS pixels (1 km). One fire that MODIS sees as
    1 hotspot can show up as 4-8 VIIRS hotspots. If we simply counted hotspots, burning would
    seem to "jump" in 2012 when VIIRS starts. So we snap every hotspot to a ~1 km grid cell and
    count each cell at most ONCE per day. Both sensors are then measured in the same unit.

Input : data/raw/{sensor}_{year}_all_countries.zip   (one CSV per country inside)
Output: data/interim/{SENSOR}_{year}.parquet         columns: country, cx, cy, date

Run from the repo root:
    python etl/build_cell_days.py          # every downloaded zip that is not processed yet
    python etl/build_cell_days.py --force  # rebuild everything
"""

import io
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from earthguard.config import GRID_DEG, MODIS, VIIRS  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
COLUMNS = ["latitude", "longitude", "acq_date", "confidence", "type"]
SENSOR_OF_PREFIX = {"modis": MODIS, "viirs-snpp": VIIRS}
WORKERS = 6  # each worker holds one year in memory (VIIRS ~1-2 GB), so keep this moderate


def clean(df: pd.DataFrame, sensor: str) -> pd.DataFrame:
    """Keep only detections we trust to be vegetation fires."""
    # type: 0 = presumed vegetation fire, 1 = volcano, 2 = other static land source (e.g. gas
    # flares, factories), 3 = offshore. Only 0 belongs in a burning calendar.
    if "type" in df.columns:
        df = df[df["type"] == 0]
    # Confidence is a number 0-100 for MODIS, and a letter (l / n / h) for VIIRS.
    if sensor == MODIS:
        df = df[pd.to_numeric(df["confidence"], errors="coerce") >= 30]
    else:
        level = df["confidence"].astype(str).str.lower().str[0]
        df = df[level.isin(["n", "h"])]
    return df


def to_cell_days(df: pd.DataFrame) -> pd.DataFrame:
    """Snap detections to the grid and keep one row per (cell, day)."""
    return pd.DataFrame({
        "cx": np.floor(df["longitude"].to_numpy() / GRID_DEG).astype("int32"),
        "cy": np.floor(df["latitude"].to_numpy() / GRID_DEG).astype("int32"),
        "date": pd.to_datetime(df["acq_date"]).to_numpy(dtype="datetime64[D]"),
    }).drop_duplicates()


def country_from_member(member: str) -> str:
    """'modis/2001/modis_2001_Burkina_Faso.csv' -> 'Burkina Faso'."""
    stem = Path(member).stem                  # modis_2001_Burkina_Faso
    return stem.split("_", 2)[2].replace("_", " ")


def build_year(zip_path: Path) -> Path:
    prefix, year, _ = zip_path.name.split("_", 2)   # e.g. ('viirs-snpp', '2015', ...)
    sensor = SENSOR_OF_PREFIX[prefix]
    target = INTERIM_DIR / f"{sensor}_{year}.parquet"

    parts = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if not member.endswith(".csv"):
                continue
            data = archive.read(member)
            header = data.split(b"\n", 1)[0].decode().strip().split(",")
            raw = pd.read_csv(io.BytesIO(data), engine="pyarrow",
                              usecols=[column for column in COLUMNS if column in header])
            cells = to_cell_days(clean(raw, sensor))
            cells["country"] = country_from_member(member)
            parts.append(cells)

    result = pd.concat(parts, ignore_index=True)
    result["country"] = result["country"].astype("category")
    result.to_parquet(target, index=False)
    print(f"{target.name}: {len(result):,} cell-days", flush=True)
    return target


def main(force: bool) -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    todo = [
        path for path in sorted(RAW_DIR.glob("*_all_countries.zip"))
        if force or not (INTERIM_DIR / "{}_{}.parquet".format(
            SENSOR_OF_PREFIX[path.name.split("_")[0]], path.name.split("_")[1])).exists()
    ]
    print(f"{len(todo)} zip files to process", flush=True)
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(build_year, todo))


if __name__ == "__main__":
    main(force="--force" in sys.argv)
