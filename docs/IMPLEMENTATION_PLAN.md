# Implementation Plan — EarthGuard (Harmonization of MODIS and VIIRS Hot Spots)

Companion to [PRD.md](PRD.md). Visual design: [stitch-prompts.md](stitch-prompts.md).

> ⚠️ **Space Apps rule:** teams may not start working on the challenge before **Nov 14, 2026**. Everything in §5–§8 happens **during the event**. Before the event, the team only does the general learning and setup in §9. If anything is unclear, ask your Local Lead.

---

## 1. Architecture

```
          (run once at the event, on team laptops)
┌──────────────────────── ETL (etl/) ────────────────────────┐
│ FIRMS Country Yearly Summary .zip  ──►  clean  ──►  cell-days │
│ (MODIS 2000–2025, VIIRS S-NPP 2012–2025)    (≈1 km grid, 1/day) │
│                         │                                     │
│                         ▼                                     │
│            region × day × sensor  ──►  data/processed/*.parquet │
└──────────────────────────────┬─────────────────────────────┘
                               │ (small aggregated files, committed)
┌──────────────────────────────▼─────────────────────────────┐
│ Streamlit app (Streamlit Community Cloud)                     │
│  earthguard/harmonize.py   ratio fit · apply · validate        │
│  earthguard/burn_calendar.py  calendar · typical · unusual ·   │
│                               critical periods                 │
│  earthguard/charts.py · maps.py · firms_live.py (NRT API)      │
│  pages/  calendar · unusual · harmonization · live_map ·       │
│          stories · about                                       │
└─────────────────────────────────────────────────────────────┘
```

**Principle:** heavy work (gigabytes) happens **once** in the ETL. The deployed app reads only small aggregated files, so it stays fast and fits Streamlit Cloud's memory.

## 2. Repo structure & file ownership

Each file has one owner (the role numbers match the team table in §4), so people do not overwrite each other's work in Git.

```
earthguard/                         (repo root)
├── app.py                          #4  entry: st.navigation, theme, shared sidebar
├── pages/
│   ├── calendar.py                 #4  Burning Calendar
│   ├── unusual.py                  #4  Unusual & Critical Periods
│   ├── harmonization.py            #3  Harmonization (method & proof)
│   ├── live_map.py                 #5  Live Map (should-have)
│   ├── stories.py                  #6  Fire Season Stories (should-have)
│   └── about.py                    #6  About the Data
├── earthguard/
│   ├── config.py                   #1  constants: paths, thresholds, source names
│   ├── aoi.py                      #2  region list, search, bounding boxes
│   ├── harmonize.py                #3  fit ratios, apply, validate
│   ├── burn_calendar.py            #3  calendar matrix, typical, unusual, critical
│   ├── charts.py                   #5  Plotly figures (heatmap, profile, scatter…)
│   ├── maps.py                     #5  pydeck layers
│   ├── firms_live.py               #2  NRT API client (should-have)
│   └── gibs.py                     #5  NASA GIBS image URLs (should-have)
├── etl/
│   ├── download.py                 #2  fetch yearly zips
│   ├── build_cell_days.py          #2  zip → cleaned cell-days per year
│   └── build_regions.py            #2  cell → admin-1 mapping, region × day parquet
├── content/stories/*.md            #6  story text
├── data/
│   ├── boundaries/                 #2  Natural Earth admin-0 / admin-1
│   └── processed/                  #2  daily_regions.parquet, ratios.parquet (committed)
├── tests/                          #3 + #1
├── .streamlit/config.toml          #5  theme colors from Stitch
├── .streamlit/secrets.toml         #2  FIRMS MAP_KEY (gitignored!)
├── requirements.txt                #4
├── LICENSE                         #1  Apache-2.0
├── REFERENCES.md                   #6  every dataset + library + license
└── README.md                       #1 + #6
```

> Do **not** name a module `calendar.py` inside the `earthguard/` package. That name shadows Python's built-in `calendar` module. The page file is fine because it lives in `pages/`. Name the module `burn_calendar.py`.

## 3. Core logic (reference snippets)

These snippets are starting points written from the documented FIRMS formats. **Inspect one real zip first**, because file names and columns may differ slightly.

### 3.1 `etl/build_cell_days.py`: zip → cell-days
```python
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

GRID = 0.01  # degrees, ≈1.1 km at the equator, close to the MODIS pixel size
COLS = ["latitude", "longitude", "acq_date", "confidence", "type"]


def clean(df: pd.DataFrame, sensor: str) -> pd.DataFrame:
    if "type" in df:
        df = df[df["type"] == 0]                                  # vegetation fires only
    if sensor == "MODIS":
        df = df[pd.to_numeric(df["confidence"], errors="coerce") >= 30]
    else:
        df = df[df["confidence"].isin(["n", "h", "nominal", "high"])]
    return df


def to_cell_days(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "cx": np.floor(df["longitude"] / GRID).astype("int32"),
        "cy": np.floor(df["latitude"] / GRID).astype("int32"),
        "date": pd.to_datetime(df["acq_date"]),
    }).drop_duplicates()                                          # one count per cell per day


def build_year(zip_path: Path, sensor: str) -> pd.DataFrame:
    parts = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            country = Path(name).stem.split("_")[-1]              # verify naming on day 1
            for chunk in pd.read_csv(zf.open(name), usecols=lambda c: c in COLS,
                                     chunksize=500_000):
                cells = to_cell_days(clean(chunk, sensor))
                cells["country"] = country
                parts.append(cells)
    out = pd.concat(parts).drop_duplicates()
    out["sensor"] = sensor
    return out   # save as data/interim/{sensor}_{year}.parquet
```

### 3.2 `earthguard/harmonize.py`
```python
import pandas as pd

OVERLAP = ("2012-01-01", "2025-12-31")
MIN_MODIS = 50  # cell-days needed before we trust a month-of-year ratio


def fit_ratios(daily: pd.DataFrame) -> pd.DataFrame:
    """daily: columns region_id, date, sensor ('MODIS'/'VIIRS'), cell_days."""
    d = daily[daily["date"].between(*OVERLAP)]
    m = (d.assign(moy=d["date"].dt.month)
           .pivot_table(index=["region_id", "moy"], columns="sensor",
                        values="cell_days", aggfunc="sum", fill_value=0))
    by_moy = m["VIIRS"] / m["MODIS"].where(m["MODIS"] >= MIN_MODIS)
    overall = m.groupby("region_id").sum()
    by_region = overall["VIIRS"] / overall["MODIS"].where(overall["MODIS"] >= MIN_MODIS)
    ratio = by_moy.fillna(by_region.reindex(by_moy.index.get_level_values(0)).to_numpy())
    global_ratio = m["VIIRS"].sum() / m["MODIS"].sum()
    return ratio.fillna(global_ratio).rename("ratio").reset_index()


def harmonize(series: pd.DataFrame, ratios: pd.DataFrame) -> pd.Series:
    """series: monthly MODIS and VIIRS cell-days for ONE region (index = month start)."""
    r = series.index.month.map(ratios.set_index("moy")["ratio"])
    viirs_eq = series["VIIRS"] / r
    return series["MODIS"].where(series.index.year < 2012, viirs_eq).rename("harmonized")
```
**Validation** (`validate()`): for each year 2012–2025, refit the ratios without that year, predict MODIS-equivalent values for that year, then compute **R²** and **median absolute % error** against real MODIS. These numbers appear on the Harmonization page.

### 3.3 `earthguard/burn_calendar.py`
```python
import pandas as pd

MIN_COUNT = 10  # avoid calling "3 vs 1 hotspots" unusual


def calendar_matrix(monthly: pd.Series) -> pd.DataFrame:
    """rows = years, columns = months 1..12 (for go.Heatmap)."""
    return (monthly.to_frame("v")
            .assign(year=monthly.index.year, month=monthly.index.month)
            .pivot(index="year", columns="month", values="v"))


def typical_and_unusual(mat: pd.DataFrame):
    typical = mat.median()                  # per month
    p90 = mat.quantile(0.90)
    unusual = (mat > p90) & (mat >= MIN_COUNT)
    times_typical = mat / typical.clip(lower=1)
    return typical, unusual, times_typical


def critical_window(weekly_typical: pd.Series) -> list[int]:
    """Weeks where typical activity >= 50% of the peak week."""
    return weekly_typical.index[weekly_typical >= 0.5 * weekly_typical.max()].tolist()


def season_by_year(weekly: pd.DataFrame) -> pd.DataFrame:
    """weekly: rows = years, columns = weeks 1..52 -> start/peak/end per year."""
    cum = weekly.cumsum(axis=1).div(weekly.sum(axis=1), axis=0)
    return pd.DataFrame({
        "start": (cum >= 0.10).idxmax(axis=1),
        "peak": weekly.idxmax(axis=1),
        "end": (cum >= 0.90).idxmax(axis=1),
    })
```

### 3.4 `earthguard/firms_live.py` (should-have)
```python
import io

import pandas as pd
import requests
import streamlit as st

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCES = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "MODIS_NRT"]  # S-NPP ended Nov 2, 2026


@st.cache_data(ttl=3600)
def recent_hotspots(bbox: tuple[float, float, float, float], days: int = 1) -> pd.DataFrame:
    west, south, east, north = bbox
    key = st.secrets["FIRMS_MAP_KEY"]
    frames = []
    for source in SOURCES:
        url = f"{BASE}/{key}/{source}/{west},{south},{east},{north}/{min(days, 5)}"
        frames.append(pd.read_csv(io.StringIO(requests.get(url, timeout=60).text)))
    return pd.concat(frames, ignore_index=True)
```

## 4. Team roles (6 students)

| # | Role | Owns | Event-day focus |
|---|---|---|---|
| 1 | **Team Lead & Submission** | `config.py`, `LICENSE`, README, tests (with #3) | Map the final challenge statement to features, run check-ins, QA, project page + submission |
| 2 | **Data Engineer** | `etl/*`, `aoi.py`, `firms_live.py`, `data/` | Downloads, ETL, region mapping, parquet outputs |
| 3 | **Data Analyst** | `harmonize.py`, `burn_calendar.py`, `pages/harmonization.py` | Harmonization method, validation numbers, unusual/critical logic |
| 4 | **App Developer** | `app.py`, `pages/calendar.py`, `pages/unusual.py`, `requirements.txt` | App skeleton, shared sidebar state, deployment |
| 5 | **Maps & Visuals** | `charts.py`, `maps.py`, `gibs.py`, theme | Stitch mockups → Streamlit theme, all charts, live map |
| 6 | **Research & Storytelling** | `about.py`, `stories.py`, `content/`, `REFERENCES.md` | Science background, wording, references/licenses, demo video script |

**Backup pairs:** 2↔3, 4↔5, 1↔6. Everyone must be able to explain the calendar and the harmonization in their own words, because judges may ask anyone.

## 5. Event plan: Day 1 (Nov 14)

Hours are **working hours**. Adjust to your Local Event's schedule. Under-18s must be accompanied at all times, and **plan for sleep**.

| Hours | #1 Lead | #2 Data | #3 Analyst | #4 App | #5 Visual | #6 Research |
|---|---|---|---|---|---|---|
| 0–1 | **Whole team**: read the final challenge statement, update the PRD §3 table, agree on MVP | Start **all downloads** (MODIS first) on the fastest connection | ″ | ″ | ″ | ″ |
| 1–3 | Create repo, `LICENSE`, board, branch rules | Open one zip and confirm file names + columns. Write `build_cell_days.py` | Write `harmonize.py` + `burn_calendar.py` against **fake data** | `app.py` skeleton, sidebar state, empty pages, deploy "hello" | Stitch: Prompt 0 → theme in `config.toml` | Research fire seasons, write About-page text, start `REFERENCES.md` |
| 3–6 | Tests for calendar/harmonize functions | Run ETL on MODIS years. **Split VIIRS years across 2–3 laptops** | Unit tests, validation function | Calendar page using fake data | `charts.py`: calendar heatmap, profile chart | Wording rules, limitations text, story outline |
| 6–8 | Checkpoint review | `build_regions.py`: cell → admin-1. Write `daily_regions.parquet` | Fit ratios on real data, first validation numbers | Swap fake data for real parquet | Harmonization charts (3-line + scatter) | Demo-video script draft |
| **End of Day 1** | ✅ **Checkpoint:** calendar shows real harmonized data for at least the featured countries | | | | | |

## 6. Event plan: Day 2 (Nov 15)

| Hours | #1 Lead | #2 Data | #3 Analyst | #4 App | #5 Visual | #6 Research |
|---|---|---|---|---|---|---|
| 0–3 | QA pass, bug list | Finish remaining countries, AOI search (`aoi.py`) | Unusual & critical logic on real data | Unusual & Critical page | Polish charts, legends, captions | About page + references complete |
| 3–5 | Project page draft (challenge mapping, NASA data list, AI disclosure) | `firms_live.py` (should-have) | Harmonization page text + metrics | Live Map page (should-have) | pydeck map (should-have) | 1–2 Fire Season Stories (should-have) |
| 5–7 | Full run-through with a "judge" (parent) | Fix data bugs | Sanity-check numbers vs FIRMS map | Performance (< 3 s), mobile check | Final visual polish | **Record demo video**: screen recording + captions, no kids' faces/voices/names |
| 7–8 | **CODE FREEZE → deploy → submit early** | | | | | |

**Scope-cut rule:** if the Day 1 checkpoint is missed, drop the Live Map and Stories and keep only Calendar + Unusual & Critical + Harmonization + About. Those four answer the challenge.

## 7. Performance & data-size targets

| Item | Target |
|---|---|
| Raw download | ~7 GB (MODIS ~2 GB + VIIRS S-NPP ~5 GB), stays on laptops, **never committed** |
| `daily_regions.parquet` (region × day × sensor) | < 100 MB (GitHub file limit). If larger, aggregate to weekly or split by continent |
| App memory on Streamlit Cloud | Load with `st.cache_data`, filter by region before plotting |
| Calendar render | < 3 s per region |

## 8. Test & submission checklist

### App
- [ ] Calendar works for the featured regions (Riau, Mato Grosso, New South Wales, British Columbia) and 5 random countries.
- [ ] The harmonized line has no visible jump at 2012. Validation R² and error are shown honestly.
- [ ] Unusual cells and critical windows make sense (e.g. 2015 Indonesia and 2019–20 Australia stand out).
- [ ] Regions with almost no fires show a friendly "too little data" message, not an error.
- [ ] The footer disclaimer and "Data: NASA FIRMS" appear on every page.

### Rules
- [ ] No names, faces, or voices of under-18s anywhere (app, video, project page, avatars).
- [ ] `LICENSE` (Apache-2.0) and `REFERENCES.md` list every dataset and library with its license.
- [ ] `secrets.toml` is gitignored, and the MAP_KEY is not in the repo.
- [ ] The project page states the challenge, the NASA datasets used, and the AI tools used (if any).
- [ ] Submitted before the Local Event's deadline.

## 9. Before the event (Oct 15 – Nov 13): learning & setup only

General skills only, practiced on **unrelated datasets**. Do not build EarthGuard or process FIRMS data for the project.

| Who | Learn | Practice idea (not the challenge) |
|---|---|---|
| All | Git & GitHub basics: branch, commit, pull request | Shared "hello" repo |
| #1 Lead | Team workflow, GitHub Projects, writing a README | Plan a pretend project |
| #2 Data | pandas: `read_csv` with `chunksize`, `groupby`, `parquet` | Any large public CSV (e.g. weather or transport data) |
| #3 Analyst | Percentiles, median, R², cross-validation basics | Analyse a sports or weather dataset |
| #4 App | Streamlit: multipage apps, `st.session_state`, `st.cache_data`, deploy to Streamlit Cloud | A small personal dashboard |
| #5 Visual | Plotly heatmaps/line charts, pydeck basics, Streamlit theming | Chart any open dataset |
| #6 Research | How satellites detect fire (general reading), citing sources, open-source licenses | Write a 1-page explainer on any science topic |

### Setup checklist (accounts only)
- [ ] Parent/guardian registers each student and picks the **same Local Event**. Team formed on spaceappschallenge.org, challenge selected.
- [ ] GitHub accounts, Streamlit Community Cloud account.
- [ ] Free FIRMS `MAP_KEY` and NASA Earthdata Login (in case downloads require it).
- [ ] Laptops: Python 3.11+, `pip install streamlit pandas pyarrow plotly pydeck geopandas requests`, at least 15 GB free disk.
- [ ] Find the fastest internet available at the event venue (or plan where downloads will run).
- [ ] Read the full challenge statement on **Oct 28**, and the Submission + Judging guides on **Nov 13**.
