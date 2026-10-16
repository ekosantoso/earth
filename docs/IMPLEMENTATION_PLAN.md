# Implementation Plan — EarthGuard (Harmonization of MODIS and VIIRS Hot Spots)

Companion to [PRD.md](PRD.md). Updated 2026-10-16 to match the **teaching reference implementation** in this repo.

> ⚠️ **Space Apps rule:** teams may not start working on the challenge before **Nov 14, 2026**. The code here is a coach's reference for teaching. At the event, students rebuild it themselves, using this plan (§6–§7) as a guide. Before the event they only do general learning and setup (§10).

---

## 1. Architecture

```
          ETL (run once, on a laptop: ~1 h download + ~6 min processing)
┌───────────────────────────────────────────────────────────────────────┐
│ FIRMS yearly zips (6.5 GB) ─► clean ─► cell-days (≈245 M) ─► per place │
│                                                                       │
│ data/processed/  monthly.parquet  weekly.parquet  regions.parquet     │
│                  cell_provinces.parquet               (≈ 20 MB total) │
└──────────────────────────────────┬────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼────────────────────────────────────┐
│ app.py — ONE Streamlit page                                           │
│                                                                       │
│  history:  data.py ─► harmonize.py ─► burn_calendar.py ─► charts.py   │
│  live:     firms_live.py (FIRMS API) ─► now.py (inside place, ×normal)│
│  pictures: satellite.py (GIBS photo) · smoke.py (GIBS aerosol)        │
│            └─► maps.py (pydeck); images sent inside the map as data URLs│
└───────────────────────────────────────────────────────────────────────┘
```

**Principles**
- The heavy work (gigabytes) happens **once** in the ETL. The app reads small tables only.
- Every live part (FIRMS, GIBS) **fails gracefully**: a message instead of a crash, while the history part still works.
- Everything slow is cached with `st.cache_data` (live data, photos, and smoke for 1 hour).

## 2. Repo structure & file ownership

Each file has one owner (role numbers as in §5), so students do not overwrite each other in Git.

```
earth/                                (repo root)
├── app.py                        #4  the one page: picker, cards, summary, map, calendar, expanders
├── earthguard/
│   ├── config.py                 #1  every number of the method in one place
│   ├── data.py                   #4  load tables, per-place analysis (cached)
│   ├── harmonize.py              #3  ratios, harmonized series, leave-one-year-out validation
│   ├── burn_calendar.py          #3  normal, unusual, fire season, worst year
│   ├── now.py                    #3  live hotspots: inside the place, × normal, hottest parts
│   ├── firms_live.py             #2  FIRMS NRT API client (parallel requests, UTC days)
│   ├── satellite.py              #5  newest GIBS true-colour photo (composite)
│   ├── smoke.py                  #5  GIBS aerosol → AOD numbers → smoke sentence + layer
│   ├── maps.py                   #5  pydeck map: pictures + hotspots (or grid cells if many)
│   ├── charts.py                 #5  Plotly: calendar heatmap, harmonization lines
│   └── ui.py                     #6  week numbers → words ("early Aug")
├── etl/
│   ├── download.py               #2  FIRMS yearly zips, 4 in parallel, resumable
│   ├── build_cell_days.py        #2  zip → cleaned cell-days per sensor-year
│   └── build_regions.py          #2  cell-days → place tables + cell→province lookup
├── tests/                        #3 + #1  15 tests with made-up data where the answer is known
├── data/processed/               #2  the only data the app needs (committed)
├── .streamlit/config.toml        #5  theme colours
├── .streamlit/secrets.toml       #2  FIRMS_MAP_KEY (gitignored!)
├── REFERENCES.md                 #6  every dataset + library + license
├── README.md, LICENSE            #1 + #6
└── docs/                         PRD, this plan, Stitch prompts
```

## 3. How each part works

Short descriptions are given here. The code is the full explanation, and every module starts with a plain-English docstring.

### 3.1 ETL
| Step | Script | What it does | Watch out |
|---|---|---|---|
| Download | `etl/download.py` | `https://firms.modaps.eosdis.nasa.gov/data/country/zips/{modis\|viirs-snpp}_{year}_all_countries.zip`, 4 in parallel, skips finished files | One connection is only ~0.6 MB/s |
| Cell-days | `etl/build_cell_days.py` | Per country CSV inside the zip: keep `type == 0` and nominal/high confidence, snap to 0.01°, dedupe (cell, day) | pyarrow `read_csv` does not accept a function for `usecols`: read the header first |
| Places | `etl/build_regions.py` | Pass 1: every 0.05° cell that ever burned → Natural Earth province (spatial join of cell centres). Pass 2: count per world/country/province × month/week, **one file at a time** | Loading all ≈245 M rows at once runs out of memory |

### 3.2 Harmonization (`harmonize.py`)
- `monthly_table` / `weekly_table`: MODIS and VIIRS cell-days per month/week. No rows means 0 fires. VIIRS before **20 Jan 2012** (including all of Jan 2012) is NaN, not 0.
- `fit_ratios`: VIIRS ÷ MODIS per month of year, over overlap months where both sensors exist. Fallbacks: all months, then parent place.
- `harmonize`: VIIRS ÷ ratio where VIIRS exists, MODIS otherwise.
- `validate`: leave-one-year-out → R², median % error.

### 3.3 Calendar (`burn_calendar.py`)
- `typical` = median; `times_typical`; `unusual` (3 rules); `critical_period` (5-week smoothed typical, ≥ 50% of peak, wraps around New Year); `worst_year`; `unusual_events`; `weeks_until`.

### 3.4 Live (`firms_live.py`, `now.py`)
- `recent_hotspots(bbox, days)`: requests `days` complete days + today, all sources in parallel. The FIRMS `DATE` parameter is the **first** day of the range, and dates are UTC.
- `complete_days`: drops today (unfinished) before any comparison.
- `now.locate` + `now.inside`: hotspot → province via `cell_provinces.parquet` → keep only hotspots inside the place.
- `now.times_normal`: NOAA-20 only, cell-days ÷ ratio, compared with the typical week × days/7.
- `now.hottest_parts`: top 3 provinces (country) or countries (world).

### 3.5 Pictures (`satellite.py`, `smoke.py`, `maps.py`)
- **Photo**: GIBS WMS in EPSG:3857 for the place's area + 50% margin. Photos: yesterday NOAA-20 → today Terra → today NOAA-20, newest non-black pixel wins.
- **Smoke**: GIBS AOD PNGs (Aqua/Terra, today then yesterday). Colours → AOD via `MODIS_VIIRS_AOD.xml`. Sampled at province cell centres; haze ≥ 0.5, thick ≥ 1.0; a yellow-to-red transparent overlay for the map.
- **Sending images**: each picture is encoded as a **data URL** (`data:image/jpeg;base64,…`) and passed to pydeck **wrapped in double quotes**, so pydeck treats it as plain text. No files, no web addresses: works locally and on Streamlit Community Cloud.
- **Map**: `BitmapLayer`s (photo, smoke), the place's rectangle, then hotspots. Hotspots in the same ~1 km square become **one dot at their average position** (coarser squares, 5/11/55 km, only if there would be more than 35,000 dots). Dots have a fixed size **in pixels**, so zooming in spreads them apart. Colour and size are computed in the browser from a confidence number (deck.gl expressions), which keeps Indonesia's map at about 4 MB instead of 26 MB.

### 3.6 Lessons learned while building the reference (teach these!)
| Problem we hit | Cause | Fix |
|---|---|---|
| Rectangle around Indonesia counted fires in **northern Australia** | The API returns a rectangle, not a country | Match each hotspot to its province and keep only those inside |
| "Last 24 hours" showed **0 hotspots** in the morning | FIRMS days are UTC; today's VIIRS data arrives hours later | Compare complete days only; show today separately |
| Live "× normal" too high | Two live VIIRS satellites vs one in the history | Use only NOAA-20 for the comparison |
| January ratio biased | VIIRS started 20 Jan 2012 | Treat Jan 2012 VIIRS as unknown |
| Critical period only 1 week long | Median weeks are spiky | Smooth over 5 weeks first |
| Too many "unusual" squares on dark cells | Quiet months doubling from tiny numbers | Require ≥ 10% of the worst month ever recorded there |
| Satellite photo did not show with pydeck `TileLayer` or a Mapbox style | Not supported by pydeck inside Streamlit | One `BitmapLayer` image per place |
| `data:` image URLs crashed the map | pydeck turns plain strings into JavaScript expressions | Wrap the data URL in double quotes (`image=f'"{url}"'`) |
| Photo worked locally but **not on Streamlit Cloud** | Earlier version saved images in a gitignored `static/` folder; Streamlit only serves `static/` if it exists at start-up, and app URLs differ behind the Cloud proxy | Send pictures as data URLs inside the map instead of files |
| Map dots were big blobs that **grew when zooming** | More than 30,000 hotspots were grouped into 55 km circles sized in metres | Merge per ~1 km square at the exact average position, size dots in pixels, send compact data |
| Black areas in today's photo | Satellite has not passed there yet | Composite newest pixels over yesterday's photo |
| Code changes "not applied" | Streamlit keeps imported modules in memory | Restart the server after changing modules |

## 4. Configuration & secrets

| File | Content |
|---|---|
| `earthguard/config.py` | Grid size, overlap years, thresholds (unusual, fire season), colours, disclaimer |
| `.streamlit/config.toml` | Dark theme colours |
| `.streamlit/secrets.toml` | `FIRMS_MAP_KEY = "..."` (free key from https://firms.modaps.eosdis.nasa.gov/api/map_key/). **Never commit** |

## 5. Team roles (6 students)

| # | Role | Owns | Event-day focus |
|---|---|---|---|
| 1 | **Team Lead & Submission** | `config.py`, `LICENSE`, README, tests (with #3) | Map the final challenge statement to features, check-ins, QA, project page + submission |
| 2 | **Data Engineer** | `etl/*`, `firms_live.py`, `data/` | Downloads, ETL, live API |
| 3 | **Data Analyst** | `harmonize.py`, `burn_calendar.py`, `now.py`, tests | Harmonization, validation numbers, unusual/season/now logic |
| 4 | **App Developer** | `app.py`, `data.py`, `requirements.txt` | The one page, caching, deployment |
| 5 | **Maps & Visuals** | `maps.py`, `charts.py`, `satellite.py`, `smoke.py`, theme | Calendar chart, live map, satellite photo, smoke layer |
| 6 | **Research & Storytelling** | `ui.py`, summary wording, `REFERENCES.md`, About text | Science background, plain-language summary, references, demo video script |

**Backup pairs:** 2↔3, 4↔5, 1↔6. Everyone must be able to explain the calendar, the harmonization, and the "× normal" in their own words.

## 6. Event plan: Day 1 (Nov 14)

Hours are **working hours**. Adjust to your Local Event. Under-18s must be accompanied at all times, and **plan for sleep**.

| Hours | #1 Lead | #2 Data | #3 Analyst | #4 App | #5 Visual | #6 Research |
|---|---|---|---|---|---|---|
| 0–1 | **Whole team**: read the challenge statement, update PRD §3, agree on the MVP | Start **all downloads** (4 parallel) | ″ | ″ | ″ | ″ |
| 1–3 | Repo, `LICENSE`, board | Open one zip, confirm layout/columns, write `build_cell_days.py` | `harmonize.py` + `burn_calendar.py` on **made-up data** + tests | `app.py` skeleton: picker, 3 cards (fake numbers), deploy "hello" | Theme; calendar heatmap on fake data | Plain-language wording, `REFERENCES.md` |
| 3–6 | Tests | Run ETL (MODIS first), then `build_regions.py` | Validation function, ratio fallbacks | Calendar section with real data | `harmonization_lines` chart | About text, limitations |
| 6–8 | Checkpoint review | Fix data issues, `cell_provinces.parquet` | Check validation numbers for 5 places | Summary paragraph (history part) | Polish the calendar | Demo script draft |
| **End of Day 1** | ✅ **Checkpoint:** calendar + harmonization + summary with real data for any place | | | | | |

## 7. Event plan: Day 2 (Nov 15)

| Hours | #1 Lead | #2 Data | #3 Analyst | #4 App | #5 Visual | #6 Research |
|---|---|---|---|---|---|---|
| 0–3 | QA pass | `firms_live.py` (UTC days, parallel) | `now.py`: inside place, × normal, hottest parts | "Right now" card + summary sentence | `maps.py` live map (dark background first) | Check live numbers against the FIRMS map |
| 3–5 | Project page draft (challenge mapping, NASA data list, AI disclosure) | Help #5 with GIBS requests | Unusual-now rule tests | Error handling (no key, API down) | `satellite.py` photo, then `smoke.py` (should-have) | Smoke sentence wording + limits |
| 5–7 | Full run-through with a "judge" (parent) | Fix bugs | Sanity-check numbers | Speed (caching) | Final visual polish | **Record demo video**: screen recording + captions, no kids' faces/voices/names |
| 7–8 | **CODE FREEZE → deploy → submit early** | | | | | |

**Scope-cut rule:** if the Day 1 checkpoint is missed, drop smoke and the satellite photo (keep the live map on the dark background). If still late, drop the live part entirely. Calendar + harmonization + summary already answer the challenge.

## 8. Measured performance (reference implementation, 16-core laptop)

| Item | Result |
|---|---|
| Download | 39 files, 6.5 GB, ~1 h at ~2 MB/s with 4 connections |
| `build_cell_days.py` + `build_regions.py` | ~6 min; ≈245 M cell-days → 4,453 places |
| Processed data | monthly 2.2 MB, weekly 5.8 MB, regions 0.3 MB, cell_provinces 12 MB |
| First load of a place | ~10–15 s (FIRMS + photo + smoke, all in parallel); then cached |
| Satellite photo | ~0.3 MB (province) to ~0.9 MB (world) |
| Tests | 15 passing, < 1 s |

## 9. Test & submission checklist

### App
- [ ] Works for a province, a country and the whole world (e.g. Riau, Indonesia, Brazil, New South Wales, Whole world).
- [ ] Indonesia's live count does **not** include Australian fires (filter inside place).
- [ ] The harmonized line has no visible jump at 2012; R² and error are shown honestly.
- [ ] Known events appear as unusual (Riau 2014, NSW Dec 2019, Canada 2023, Indonesia 2015).
- [ ] Places with almost no fire show a friendly message; no MAP_KEY / API down shows a message, not a crash.
- [ ] All three map backgrounds work; the smoke sentence mentions the unmeasured share.
- [ ] Disclaimer and "Data: NASA FIRMS" are visible.

### Rules
- [ ] No names, faces, or voices of under-18s anywhere (app, video, project page, avatars).
- [ ] `LICENSE` (Apache-2.0); `REFERENCES.md` lists every dataset and library with its license (verify DOIs and basemap terms).
- [ ] `secrets.toml` is gitignored; the MAP_KEY is not in the repo.
- [ ] The project page states the challenge, NASA datasets used, and AI tools used.
- [ ] Submitted before the Local Event deadline.

## 10. Before the event (Oct 16 – Nov 13): learning & setup only

General skills only, practised on **unrelated datasets**.

| Who | Learn | Practice idea (not the challenge) |
|---|---|---|
| All | Git & GitHub: branch, commit, pull request | Shared "hello" repo |
| #1 Lead | Team workflow, GitHub Projects, README writing | Plan a pretend project |
| #2 Data | pandas `read_csv` (pyarrow), `groupby`, parquet; calling a web API with `requests` | Any public CSV + any free JSON API |
| #3 Analyst | Median, percentiles, ratios, R², cross-validation; writing pytest tests | Analyse a sports or weather dataset |
| #4 App | Streamlit: layout, `st.metric`, `st.cache_data`, `st.secrets`, deploy | A small personal dashboard |
| #5 Visual | Plotly heatmaps, pydeck `ScatterplotLayer` / `BitmapLayer`, Pillow basics | Map any open dataset |
| #6 Research | How satellites see fire and smoke (general reading), citing sources, licenses | A one-page explainer on any science topic |

### Setup checklist (accounts only)
- [ ] Parent/guardian registers each student in the **same Local Event**; team formed; challenge selected.
- [ ] GitHub and Streamlit Community Cloud accounts.
- [ ] Free FIRMS `MAP_KEY`.
- [ ] Laptops: Python 3.11+, `pip install -r requirements.txt geopandas pytest`, ≥ 15 GB free disk.
- [ ] Fast internet available at the venue for the 6.5 GB download.
- [ ] Read the full challenge statement (**Oct 28**) and the Submission + Judging guides (**Nov 13**).

## 11. Running the reference implementation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt geopandas pytest
python etl/download.py          # ~6.5 GB
#   + Natural Earth admin-1 zip into data/boundaries/ (see README)
python etl/build_cell_days.py
python etl/build_regions.py
streamlit run app.py
python -m pytest
```
