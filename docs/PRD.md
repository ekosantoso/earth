# PRD — EarthGuard

> *"Is it burning now? When is the fire season? Is this worse than usual?"*
> 25 years of NASA satellite fire records, harmonized into one calendar, plus live hotspots and smoke.

| | |
|---|---|
| Status | **v2**, updated to match the teaching reference implementation (2026-10-16) |
| Event | **NASA Space Apps Challenge 2026**, November 14–15, 2026 |
| Challenge | **[Harmonization of MODIS and VIIRS Hot Spots](https://www.spaceappschallenge.org/2026/challenges/harmonization-of-modis-and-viirs-hot-spots/)** (Intermediate / Advanced, Earth Science + Software) |
| Team | 6 students, age 15, Python at intermediate level |
| Stack | Python · Streamlit · pandas · Plotly · pydeck (geopandas for data preparation only) |
| Companion docs | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [stitch-prompts.md](stitch-prompts.md) (still describes the earlier multi-page design) |

> ⚠️ **Space Apps rules forbid starting work on the challenge before Nov 14 (§11).** This PRD and the code in this repo are a **teaching reference** for coaches. At the event, students build their own version.
> The full challenge statement will be published Oct 28: re-check §3 against it then.

---

## 1. Problem

Satellites have detected active fires around the world for more than 20 years. That record is the best evidence we have of **when and where burning happens**, including wildfires and agricultural burning. But the record is split between two sensor families that cannot be compared directly:

| Sensor | Satellites | Pixel size | Record starts |
|---|---|---|---|
| **MODIS** | Terra, Aqua | 1 km | 2000 |
| **VIIRS** | Suomi NPP, NOAA-20, NOAA-21 | 375 m | 2012 |

VIIRS has smaller pixels, so it detects many more, and smaller, fires than MODIS. Put the two side by side and **burning appears to jump in 2012** for no real reason. Fire managers, early-warning teams, scientists, and land managers therefore lack a **consistent long-term picture** of fire seasons, unusual years, and critical periods. Without that picture, they also cannot tell whether **today's** fires are normal for the time of year.

## 2. Solution

EarthGuard is a **one-page web app**. The user picks any country or province in the world, and the page answers three questions:

| Question | Answer on the page |
|---|---|
| **Is it burning now, and is that unusual?** | Live NASA hotspots compared with the same time of year since 2001, shown on the newest NASA satellite photo with measured **smoke** |
| **When is the fire season here?** | The typical fire season, from a **harmonized MODIS + VIIRS calendar 2001–2025** |
| **Which years and months were worse than usual?** | The worst year and the most unusual months, marked on the calendar |

A short plain-language summary ties everything together, for example:

> **Right now:** 116,862 hotspots in the last 7 days in **Indonesia**, 7.3× normal for mid Oct, **unusually high**. Most are in **Kalimantan Tengah** (43,191 · 23.1× normal), Papua, and Sumatera Selatan.
> **Smoke/haze:** about 64% of Indonesia that satellites could see has smoky or hazy air. It is thickest over Jambi, Sumatera Utara, and Sumatera Barat.
> Fires here usually happen between early Aug and mid Oct. The usual season has **just ended**, so fires now are later than usual. The worst year since 2001 was **2015**.

**No AI/ML.** Everything is transparent statistics that a 15-year-old can explain to a judge.

## 3. Challenge requirements → features

| The challenge asks for… | EarthGuard answers with… |
|---|---|
| A **web application** | Streamlit app, one page, deployable at a public URL |
| **Harmonize** MODIS and VIIRS records | Common ~1 km grid + overlap-period calibration (§7.3). The *How it works* section shows raw vs harmonized lines and accuracy (R², error) |
| A **burning activity calendar** based on active fire hotspots | Year × month heatmap 2001–2025 for the selected place, with a "normal year" bar underneath |
| **Historical fire patterns** | Calendar + fire-season card + worst-year card |
| **Unusual conditions** | White squares on unusual months, a "most unusual months" list, and a live "× normal" for the current week |
| **Critical periods** | Typical fire season (critical period) per place, with "happening now / just ended / starts in N weeks" |
| **Selected area of interest** | Any country or province/state in the world (about 4,250 places) |
| Useful for **early warning/emergency responders, scientists, land managers** | Live "right now vs normal", hottest provinces, smoke coverage, CSV download of live hotspots |

## 4. Users

| Persona | Question they bring | What EarthGuard gives them |
|---|---|---|
| **Emergency/early-warning officer** (e.g. a provincial disaster agency) | "Is this week worse than normal? Where exactly? Is there smoke?" | Right-now card, hottest provinces, smoke sentence and smoke map |
| **Land manager / plantation or park manager** | "Which months are risky in my area?" | Fire-season card + calendar |
| **Scientist / student** | "Can I trust a 25-year record that mixes two sensors?" | *How it works* section: method, raw vs harmonized chart, leave-one-year-out accuracy |
| **Space Apps judges** | "Did they answer the challenge, and is it sound?" | Requirement-to-feature mapping (§3), honest limitations, live demo |

## 5. Goals & success metrics

The 2026 judging criteria are published Nov 13. Past years' criteria were **Impact, Creativity, Validity, Relevance, Presentation**.

| Goal | Metric | Criterion served |
|---|---|---|
| Answers the challenge completely | Every row in §3 is demonstrable in the demo | Relevance |
| Harmonization is scientifically defensible | Leave-one-year-out R² ≥ 0.8 for large regions, reported honestly per place (§8) | Validity |
| Works anywhere | Every country and province/state selectable | Impact |
| Fast | First load of a place < 15 s (live data + photos); repeat visits < 3 s (cached) | Presentation |
| Understandable in 10 seconds | Three cards + one summary paragraph; no menus | Presentation, Impact |
| Novel | Harmonized calendar + live "× normal" + smoke coverage is not available in FIRMS' own map | Creativity |

## 6. Scope

### Must-have (MVP)
1. **ETL pipeline**: download the FIRMS **Country Yearly Summary** archives (MODIS 2001–2025, VIIRS S-NPP 2012–2025), clean them, and aggregate to **active-fire cell-days** per world / country / province, per month and per week. Also save a cell → province lookup.
2. **Harmonization**: per-place, per-month-of-year VIIRS→MODIS ratio learned from the overlap years, with fallbacks (province → country → world).
3. **One page**, top to bottom:
   1. Place picker (search).
   2. **Three cards**: Right now (× normal), Fire season, Worst year since 2001.
   3. **Summary paragraph**: now, hottest parts, smoke, season, worst year.
   4. **Calendar** 2001–2025 with unusual months marked, plus a list of the most unusual months.
   5. Folded **How it works** (harmonization chart + accuracy) and **About the data** (sources, limits, references).
4. **Disclaimer + data credit** on the page. `LICENSE` (Apache-2.0) and `REFERENCES.md`.

### Should-have (in the reference implementation)
- **Live map**: hotspots of the last 7 days + today, **only those inside the chosen place**, drawn on the newest NASA satellite photo, with an optional **smoke (aerosol) layer**. Background choice: *Photo + smoke* / *Photo* / *Dark map*.
- **Smoke sentence**: share of the place covered by haze, and the thickest provinces.
- CSV download of the live hotspots.
- Deployment to Streamlit Community Cloud.

### Could-have
- Custom rectangle as area of interest.
- Compare two places side by side.
- Fire Season Stories (guided stories of 2015 Indonesia, 2019–20 Australia, with NASA GIBS imagery).
- Weekly calendar view.
- Bahasa Indonesia text.

### Won't-have
- AI/ML models or forecasts. "Starts in N weeks" is a historical pattern, not a prediction.
- Multiple pages or menus (deliberately removed: one page is easier for users and judges).
- Alerts/notifications, user accounts, or a database server.
- Harmonization of geostationary sensors (GOES, Himawari).

## 7. Data & methodology

### 7.1 Data sources

#### Core NASA data (must-have)

| # | NASA dataset | Satellite / sensor | Resolution | Period | Used for | Access |
|---|---|---|---|---|---|---|
| 1 | **FIRMS MODIS Active Fire**, Standard Processing (MCD14ML*) | Terra & Aqua | 1 km | 2001–2025 | Long-term record; the **reference unit** ("MODIS-equivalent") | [Country Yearly Summary](https://firms.modaps.eosdis.nasa.gov/country/): `modis_{year}_all_countries.zip`, ~2 GB total |
| 2 | **FIRMS VIIRS 375 m Active Fire**, Standard Processing (VNP14IMGML*) | Suomi NPP | 375 m | 20 Jan 2012–2025 | Converted to MODIS-equivalent; the overlap is the **calibration period** | `viirs-snpp_{year}_all_countries.zip`, ~5 GB total |

Downloads need no login. Each zip holds one CSV per country, e.g. `modis/2015/modis_2015_Indonesia.csv`.

#### Live NASA data (should-have)

| # | NASA dataset | Access | Used for |
|---|---|---|---|
| 3 | **FIRMS Near Real-Time**: `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `MODIS_NRT` | FIRMS Area API, free `MAP_KEY`, ≤ 5 days per request, `DATE` = first day of the range, dates in **UTC** | Live hotspots; "right now × normal" |
| 4 | **NASA GIBS** true colour: `MODIS_Terra_CorrectedReflectance_TrueColor`, `VIIRS_NOAA20_CorrectedReflectance_TrueColor` | GIBS WMS (EPSG:3857), no key | Satellite photo behind the live map |
| 5 | **NASA GIBS** aerosol: `MODIS_Terra_Aerosol_Optical_Depth_3km`, `MODIS_Aqua_Aerosol_Optical_Depth_3km`, colormap `MODIS_VIIRS_AOD.xml` | GIBS WMS + colormap XML | Smoke sentence and smoke layer |

#### Non-NASA supporting data

| Dataset | Used for | License status |
|---|---|---|
| **Natural Earth** admin-1 (provinces, states), 1:10m | Province of each fire cell (ETL only) | Public domain |
| CARTO Dark Matter basemap (OpenStreetMap data) | Map background outside the satellite photo | © CARTO, © OpenStreetMap (ODbL). **Check terms before public use** |

#### FIRMS columns used

| Column | Purpose |
|---|---|
| `latitude`, `longitude` | Location, snapped to the ~1 km grid |
| `acq_date`, `acq_time` | Observation date/time (UTC) |
| `confidence` | Keep *nominal* and *high* (MODIS ≥ 30, VIIRS `n`/`h`) |
| `type` (archive only) | Keep presumed vegetation fires (`0`); drop volcanoes, static/industrial sources, offshore |
| `frp` | Shown in the live hotspot list |

#### Data notes
- **Suomi NPP data delivery ended Nov 2, 2026.** Its archive (2012–2025) remains the calibration reference. Live VIIRS comes from NOAA-20/21.
- FIRMS posted a notice about a **bug in the VIIRS "Type" attribute** (Vxx14IMGML). Check it before trusting the `type` filter for VIIRS; if affected, drop the filter for VIIRS and document it.
- \*Product codes and DOIs must be **verified on the FIRMS citation page** before submitting.
- Space Apps requires **every source to be cited** (`REFERENCES.md` and the *About the data* section).

### 7.2 Cleaning
- Keep presumed **vegetation fires** only (`type == 0`). This removes gas flares, factories, and volcanoes.
- Keep confidence **nominal + high**.

### 7.3 Harmonization
1. **Common grid**: snap every detection to a ~1 km grid (0.01°). Count each cell **at most once per day per sensor**. These are *active-fire cell-days*, and they remove most of the "VIIRS sees several 375 m pixels where MODIS sees one" effect.
2. **Aggregate** cell-days per place (world, country, province) per month and per week.
3. **Calibrate** on the overlap period 2012–2025, using only months where **both** sensors observed fully. January 2012 is excluded because VIIRS started on 20 Jan 2012. For each place and month of year: `ratio = Σ VIIRS ÷ Σ MODIS`.
   - Fallbacks:
     - If MODIS has fewer than 50 cell-days in that month, use the place's all-months ratio.
     - If that is still too sparse, use the **parent's ratio** (province → country → world).
4. **Harmonized series** in MODIS-equivalent units: `VIIRS ÷ ratio` wherever VIIRS exists, MODIS otherwise (2001–2011 and Jan 2012).
5. **Validate (leave-one-year-out)**: for each overlap year, refit without that year, predict MODIS from VIIRS, and compare with real MODIS. Report **R²** and **median absolute % error** (months with ≥ 10 MODIS cell-days).

### 7.4 Calendar definitions

| Concept | Definition (explainable in one sentence) |
|---|---|
| **Normal (typical)** | Median of the same month (or week) across 2001–2025 |
| **× normal** | `value ÷ max(typical, 1)` |
| **Unusual month** | All three: **top 10% of years** for that month, **≥ 2× normal**, and big enough to see (≥ 10% of the worst month ever recorded there, and ≥ 10 cell-days) |
| **Fire season (critical period)** | Consecutive weeks around the peak where the typical week, **averaged over 5 weeks**, is ≥ **50% of the peak**. It may cross New Year |
| **Worst year** | Year with the most activity, and its ratio to the median year |

### 7.5 Right now vs normal
- **Window:** the last 7 complete days (2 for the whole world), **up to yesterday UTC**. Today is shown on the map but left out of the comparison, because it is unfinished and VIIRS arrives hours late.
- **Inside the place only:** the live API returns a rectangle (Indonesia's rectangle includes northern Australia). Each hotspot is matched to a province via a **0.05° cell → province lookup** built in the ETL, and only hotspots inside the chosen place are kept.
- **Same measurement as history:** only **one** VIIRS satellite (**NOAA-20**, same orbit as Suomi NPP), ~1 km cells counted once per day, divided by the place's ratio for the current month.
- **Normal for now:** the typical value for the current week × days/7. **Unusual now** means ≥ 2× normal and ≥ 10 cell-days.
- **Hottest parts:** the top 3 provinces (of a country) or countries (of the world) by hotspot count, each with its own × normal.

### 7.6 Satellite photo (newest pixels)
Download three NASA GIBS true-colour photos for the area around the place:
1. Yesterday afternoon (NOAA-20).
2. Today morning (Terra).
3. Today afternoon (NOAA-20).

Paste each newer photo over the older one wherever it has pixels (not black). The result is always complete and as new as possible. The page reports the share of the view photographed today.

### 7.7 Smoke (aerosol)
- **AOD** (Aerosol Optical Depth) from MODIS Aqua/Terra, 3 km. Today's passes come first, and yesterday's fill the gaps. Colours are converted back to AOD with the official GIBS colormap.
- **Haze** = AOD ≥ 0.5. **Thick smoke** = AOD ≥ 1.0.
- AOD is sampled at the centre of every province cell. The page reports the share of *measured* area that is hazy, the thickest provinces, and **the share that could not be measured**.
- Skipped for the whole world, because one picture would be too coarse.

### 7.8 Limitations (shown in the app)
- Clouds and smoke hide fires from both sensors; small or short fires may be missed.
- A hotspot is a heat signal, not a confirmed fire.
- Overpass times differ, and Terra/Aqua orbits have been drifting.
- Harmonization ratios are estimates that vary by land cover and season. Accuracy is shown per place.
- Provinces are matched on a ~5 km grid (border errors of a few km). The lookup only knows cells that burned since 2001, which covers almost every place that burns today.
- **Smoke under clouds cannot be measured**, and very thick smoke can be mistaken for cloud, so real smoke may be wider than reported.
- Live data and photos appear a few hours after each satellite pass.

## 8. Validation results (reference implementation, full data)

| Place | R² | Typical error |
|---|---|---|
| Whole world | 0.91 | ±3% |
| Brazil / Mato Grosso | 0.99 / 0.99 | ±8% / ±9% |
| Indonesia | 0.98 | ±12% |
| Australia / New South Wales | 0.98 / 0.91 | ±5% / ±16% |
| Canada | 0.97 | ±14% |
| India | 0.97 | ±9% |
| DR Congo | 0.97 | ±6% |
| Riau (Indonesia) | 0.93 | ±31% (small, cloudy region) |

The calendar recovers real events without being told about them:
- Riau: haze crises of 2005, June 2013, and Feb–Mar 2014.
- New South Wales: Black Summer, Dec 2019–Jan 2020.
- Canada: the record 2023 season.
- Indonesia: 2015.

## 9. UX

One page, no menus, dark theme (colours from `stitch-prompts.md`):

```
🔥 EarthGuard — "Is it burning now? When is the fire season? Is this year worse than usual?"
[ Place: 🏳️ Indonesia ▾ ]   (default)
┌ Right now: 7.3× normal ┐ ┌ Fire season: Aug – Oct ┐ ┌ Worst year: 2015 (3.1×) ┐
> Summary: now · hottest parts · smoke · season · worst year
🗺️ Hotspots and smoke right now   [Photo + smoke | Photo | Dark map]
   map + caption + ▸ list of latest hotspots (CSV)
📅 Fire calendar 2001–2025   heatmap + normal-year bars + "most unusual months"
▸ 🛰️ How it works — combining two NASA satellites
▸ ℹ️ About the data
⚠️ disclaimer · data credit
```

**Wording rules**
- Use "hotspot", "active-fire detection", or "burning", never "confirmed fire".
- Disclaimer: *"Satellite hotspots are not confirmed fires. EarthGuard supports planning and research; it is not an official alert system."*
- No NASA logo. The Space Apps logo may be used per its brand guidelines.

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ~7 GB download on event-day internet | No data | Start in **hour 0**, 4 parallel downloads (~2 MB/s → ~1 h), MODIS first |
| ETL too slow on student laptops | Late | pyarrow CSV reading, one file at a time, parallel years (full run ≈ 6 min on 16 cores) |
| FIRMS / GIBS API unavailable or slow | Live part empty | Every live part fails gracefully (message instead of crash); history part still works; results cached 1 h |
| Live counts contaminated by neighbours | Wrong "× normal" | Filter hotspots to the place via the cell → province lookup (§7.5) |
| "Today" incomplete | Fire looks like it is dropping | Compare complete days only (§7.5) |
| Smoke hidden by clouds | Under-reported smoke | Report the unmeasured share in the sentence |
| Streamlit Cloud memory (~1 GB) | Crash | Ship only aggregated tables (~20 MB), never raw points |
| Final challenge statement changes requirements | Rework | Re-map §3 at the start of the event |
| Minors' rules broken | Disqualification risk | No names, faces, or voices of under-18s anywhere (§11) |

## 11. Space Apps compliance (verified Oct 15, 2026)

| Rule | Source | Our action |
|---|---|---|
| **No work on the challenge before the hackathon** | Participant FAQ | This repo is a coach's teaching reference; students build their own at the event. Confirm with the Local Lead |
| Under-18s **registered by a parent/guardian** and **accompanied at all times** | FAQ, Terms | Parents register the team and attend |
| No recognizable **names, voices, or likenesses** of under-18s | Terms §Submissions, §Media Release | Screen-recorded demo with captions (or an adult narrator); team shown by roles only |
| Max **6 members**, **one challenge**, same Local Event (or Universal Event) | FAQ | 6 students, one event |
| Original work is **open source** (default Apache-2.0) | Terms §IP | `LICENSE` = Apache-2.0 |
| Non-NASA materials freely available/open, **licenses documented** | Terms §Third-party | `REFERENCES.md`; check the basemap terms |
| **Cite every source**, including libraries | Terms §Third-party | `REFERENCES.md` + *About the data* |
| No commercial promotion | Terms §Submissions | No product logos/ads |
| Submit via the **team project page** | FAQ | Submission guide published Nov 13 |
| AI tool usage | Expected in the Nov 13 guides | Disclose AI tools used in the project description |
