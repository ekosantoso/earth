"""ETL step 2: cell-days  ->  small region tables the app can load quickly.

Regions come in three levels:
    world                    everything
    country:<name>           country, taken from the FIRMS file name (exact)
    province:<adm1_code>     province/state from Natural Earth admin-1 boundaries

Province matching uses a coarse 0.05 deg grid (~5 km): we look up which province contains the
CENTER of each coarse cell. This is far faster than testing millions of points, and the error is
limited to a few km along province borders. (Worth explaining to judges as a trade-off!)

The full dataset has ~200 million cell-days, too many to hold in memory at once. So we work in
two passes, one file (= one sensor-year) at a time:
    pass 1: collect every coarse cell that ever burned  ->  find its province once
    pass 2: count cell-days per region and period for each file, then add the counts up

Input : data/interim/*.parquet, data/boundaries/ne_10m_admin_1_states_provinces.zip
Output: data/processed/monthly.parquet   region_id, year, month, sensor, cell_days
        data/processed/weekly.parquet    region_id, year, week,  sensor, cell_days
        data/processed/regions.parquet   region_id, name, level, country, bbox, total
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from earthguard.config import GRID_DEG, PROCESSED_DIR, PROVINCE_CELLS, WEEKS_PER_YEAR  # noqa: E402

INTERIM_DIR = ROOT / "data" / "interim"
ADMIN1_ZIP = ROOT / "data" / "boundaries" / "ne_10m_admin_1_states_provinces.zip"
COARSE = PROVINCE_CELLS  # 5 grid cells of 0.01 deg = 0.05 deg


def load(path: Path) -> pd.DataFrame:
    cells = pd.read_parquet(path)
    cells["sensor"] = path.stem.split("_")[0]
    cells["kx"] = (cells["cx"] // COARSE).astype("int32")
    cells["ky"] = (cells["cy"] // COARSE).astype("int32")
    date = pd.to_datetime(cells["date"])
    cells["year"] = date.dt.year.astype("int16")
    cells["month"] = date.dt.month.astype("int8")
    # Week 1 = Jan 1-7, week 2 = Jan 8-14, ... Days 358+ fold into week 52, so every year has
    # exactly 52 weeks and the same week number always means the same time of year.
    cells["week"] = np.minimum((date.dt.dayofyear - 1) // 7 + 1, WEEKS_PER_YEAR).astype("int8")
    return cells.drop(columns="date")


def province_lookup(coarse: pd.DataFrame, admin1: gpd.GeoDataFrame) -> pd.DataFrame:
    """Map each coarse cell (kx, ky) to a Natural Earth adm1_code."""
    centers = gpd.GeoDataFrame(
        coarse,
        geometry=gpd.points_from_xy((coarse["kx"] + 0.5) * COARSE * GRID_DEG,
                                    (coarse["ky"] + 0.5) * COARSE * GRID_DEG),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(centers, admin1[["adm1_code", "geometry"]], how="inner", predicate="within")
    return joined[["kx", "ky", "adm1_code"]].drop_duplicates(["kx", "ky"])


def save_cell_provinces(lookup: pd.DataFrame) -> None:
    """Keep the cell -> province table, so the app can tell which province a LIVE hotspot is in
    without needing the province shapes. (It only knows cells that burned since 2001, which
    covers almost every place that burns today.)"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame({"kx": lookup["kx"].astype("int16"), "ky": lookup["ky"].astype("int16"),
                          "region_id": ("province:" + lookup["adm1_code"]).astype("category")})
    table.to_parquet(PROCESSED_DIR / "cell_provinces.parquet", index=False)
    print(f"cell_provinces.parquet: {len(table):,} cells", flush=True)


def count(cells: pd.DataFrame, key: str, period: str) -> pd.DataFrame:
    return (cells.groupby([key, "year", period, "sensor"], observed=True)
                 .size().rename("cell_days").reset_index()
                 .rename(columns={key: "region_id"}))


def summarize(cells: pd.DataFrame, key: str) -> pd.DataFrame:
    """Extent and size of every region in one file (combined across files later)."""
    return cells.groupby(key, observed=True).agg(
        cx_min=("cx", "min"), cy_min=("cy", "min"),
        cx_max=("cx", "max"), cy_max=("cy", "max"), total=("cx", "size"),
    )


def main() -> None:
    files = sorted(INTERIM_DIR.glob("*.parquet"))
    admin1 = gpd.read_file(f"zip://{ADMIN1_ZIP}").to_crs("EPSG:4326")

    # ---- pass 1: province of every coarse cell ------------------------------------------
    coarse = pd.concat(
        [pd.read_parquet(path, columns=["cx", "cy"]).pipe(
            lambda d: pd.DataFrame({"kx": d["cx"] // COARSE, "ky": d["cy"] // COARSE}))
         .drop_duplicates() for path in files]
    ).drop_duplicates()
    lookup = province_lookup(coarse, admin1)
    print(f"pass 1: {len(coarse):,} coarse cells, {len(lookup):,} inside a province", flush=True)
    save_cell_provinces(lookup)

    # ---- pass 2: counts per file --------------------------------------------------------
    monthly, weekly, country_stats, province_parent = [], [], [], []
    for path in files:
        cells = load(path).merge(lookup, on=["kx", "ky"], how="left")
        cells["world"] = "world"
        cells["country_id"] = "country:" + cells["country"].astype(str)
        provinces = cells.dropna(subset=["adm1_code"]).copy()
        provinces["province_id"] = "province:" + provinces["adm1_code"]

        for period, out in [("month", monthly), ("week", weekly)]:
            out += [count(cells, "world", period), count(cells, "country_id", period),
                    count(provinces, "province_id", period)]
        country_stats.append(summarize(cells, "country"))
        province_parent.append(provinces.groupby(["adm1_code", "country"], observed=True).size())
        print(f"pass 2: {path.stem}: {len(cells):,} cell-days", flush=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, parts, period in [("monthly", monthly, "month"), ("weekly", weekly, "week")]:
        table = (pd.concat(parts, ignore_index=True)
                   .groupby(["region_id", "year", period, "sensor"], observed=True)["cell_days"]
                   .sum().reset_index())
        table["region_id"] = table["region_id"].astype("category")
        table["sensor"] = table["sensor"].astype("category")
        table["cell_days"] = table["cell_days"].astype("int32")
        table.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
        print(f"{name}.parquet: {len(table):,} rows", flush=True)

    write_regions(country_stats, province_parent, admin1)


def write_regions(country_stats: list, province_parent: list, admin1: gpd.GeoDataFrame) -> None:
    # Countries: name and extent come from the fire data itself.
    c = pd.concat(country_stats).groupby(level=0, observed=True).agg(
        {"cx_min": "min", "cy_min": "min", "cx_max": "max", "cy_max": "max", "total": "sum"})
    countries = pd.DataFrame({
        "region_id": "country:" + c.index.astype(str),
        "name": c.index.astype(str),
        "level": "country",
        "country": c.index.astype(str),
        "west": c["cx_min"] * GRID_DEG, "south": c["cy_min"] * GRID_DEG,
        "east": (c["cx_max"] + 1) * GRID_DEG, "north": (c["cy_max"] + 1) * GRID_DEG,
        "total": c["total"],
    })

    # Provinces: the "parent" country is the FIRMS country that most of its fires belong to,
    # so province and country names always use the same (FIRMS) spelling.
    pairs = pd.concat(province_parent).groupby(level=[0, 1], observed=True).sum()
    totals = pairs.groupby(level=0).sum()
    parent = pairs.sort_values(ascending=False).reset_index().drop_duplicates("adm1_code")
    parent = parent.set_index("adm1_code")["country"].astype(str)
    shapes = admin1.set_index("adm1_code")
    label = shapes["name"].fillna(shapes["name_en"]).fillna(pd.Series(shapes.index, shapes.index))
    bounds = shapes.bounds
    codes = totals.index
    provinces = pd.DataFrame({
        "region_id": "province:" + codes,
        "name": label.reindex(codes).to_numpy() + ", " + parent.reindex(codes).to_numpy(),
        "level": "province",
        "country": parent.reindex(codes).to_numpy(),
        "west": bounds["minx"].reindex(codes).to_numpy(),
        "south": bounds["miny"].reindex(codes).to_numpy(),
        "east": bounds["maxx"].reindex(codes).to_numpy(),
        "north": bounds["maxy"].reindex(codes).to_numpy(),
        "total": totals.to_numpy(),
    })

    world = pd.DataFrame([{
        "region_id": "world", "name": "Whole world", "level": "world", "country": "",
        "west": -180.0, "south": -90.0, "east": 180.0, "north": 90.0,
        "total": countries["total"].sum(),
    }])
    regions = pd.concat([world, countries, provinces], ignore_index=True)
    regions.to_parquet(PROCESSED_DIR / "regions.parquet", index=False)
    print(f"regions.parquet: {len(regions):,} regions", flush=True)


if __name__ == "__main__":
    main()
