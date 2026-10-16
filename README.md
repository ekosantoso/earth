# 🔥 EarthGuard

**When does your area burn?** EarthGuard combines 25 years of NASA satellite fire records,
from MODIS (since 2000) and VIIRS (since 2012), into **one harmonized burning activity calendar**
for any country or province/state in the world.

It answers the NASA Space Apps Challenge 2026 challenge
[*Harmonization of MODIS and VIIRS Hot Spots*](https://www.spaceappschallenge.org/2026/challenges/harmonization-of-modis-and-viirs-hot-spots/).

> **Teaching reference.** This repository is a reference implementation for teaching. Space Apps
> rules say teams may not start working on the challenge before the hackathon (Nov 14–15, 2026)
> and that a team's submission must be its own work. Students should build their own version at
> the event.

## One page, three questions

Pick a place, and the page answers:

| Question | How it is shown |
|---|---|
| **Is it burning now, and is that unusual?** | "Right now" card (× normal) + live map of hotspots from the last 7 days and today, on top of the newest NASA satellite photo so smoke is visible (needs a FIRMS MAP_KEY) |
| **When is the fire season?** | "Fire season" card + 25-year calendar (years × months) with a normal year underneath |
| **Which years/months were worse than usual?** | "Worst year" card + white squares on the calendar + list of the most unusual months |

Two folded sections at the bottom are for judges: **How it works** (harmonization chart and
accuracy) and **About the data** (sources, limits, references).

## Quick start

```bash
# 1. Python 3.11+ environment
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt geopandas pytest

# 2. Data (only once, ~7 GB download, ~30-60 min)
python etl/download.py            # NASA FIRMS yearly archives -> data/raw/
#    Natural Earth provinces -> data/boundaries/ne_10m_admin_1_states_provinces.zip
#    https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip
python etl/build_cell_days.py     # raw detections -> active-fire cell-days (data/interim/)
python etl/build_regions.py       # cell-days -> small tables per region (data/processed/)

# 3. Run
streamlit run app.py

# 4. Tests
python -m pytest
```

For the Live Map, create `.streamlit/secrets.toml` containing `FIRMS_MAP_KEY = "..."`.
Get a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/. **Never commit this file.**

## How it works

```
FIRMS yearly zips (7 GB)
  └─ etl/build_cell_days.py   keep vegetation fires with nominal/high confidence,
                              snap to a ~1 km grid, count each cell once per day
      └─ etl/build_regions.py add up per world / country / province, per month and per week
          └─ data/processed/*.parquet  (a few MB, this is all the app needs)
              └─ app.py: harmonize.py -> burn_calendar.py -> charts.py + live map
```

**Harmonization in one sentence:** from 2012 to 2025 both sensors watched the same places, so we
learn how many VIIRS cell-days there are per MODIS cell-day (for each month of the year) and
divide VIIRS by that ratio, giving one continuous MODIS-equivalent record.

All method settings (grid size, thresholds, percentiles) live in `earthguard/config.py`.

## Project structure

| Path | Role in the team |
|---|---|
| `etl/` | Data Engineer: download and prepare the data |
| `earthguard/harmonize.py`, `earthguard/burn_calendar.py`, `tests/` | Data Analyst: the science |
| `app.py`, `earthguard/ui.py`, `earthguard/data.py`, `earthguard/firms_live.py` | App Developer |
| `earthguard/charts.py`, `earthguard/maps.py`, `.streamlit/config.toml` | Maps & Visuals |
| Text in `app.py`, `REFERENCES.md` | Research & Storytelling |
| `docs/` | PRD, implementation plan, Stitch design prompts |

## License

Apache-2.0 (see `LICENSE`). Data and library licenses are listed in [REFERENCES.md](REFERENCES.md).
