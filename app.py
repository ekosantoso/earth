"""EarthGuard — one page.  Run:  streamlit run app.py

Pick a place, and the page answers three questions:
    1. Is it burning there right now, and is that more than usual?   (live NASA FIRMS data)
    2. When is the fire season there?                                (25-year harmonized record)
    3. Which months and years were unusually bad?
"""

from datetime import datetime, timezone

import numpy as np
import streamlit as st

from earthguard import burn_calendar, charts, co, data, firms_live, maps, now, satellite, smoke, ui
from earthguard.config import DATA_CREDIT, DISCLAIMER, ROOT

st.set_page_config(page_title="EarthGuard", page_icon="🔥", layout="wide")
st.markdown(
    """
    <style>
      [data-testid="stMetric"] {
        background: #131C2E; border: 1px solid #22304A; border-radius: 12px; padding: 14px 16px;
      }
      [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)
DEFAULT_PLACE = "country:Indonesia"

# ---- 0. pick a place --------------------------------------------------------------------
st.title("🔥 EarthGuard")
st.markdown("**Is it burning now? When is the fire season? Is this year worse than usual?**  \n"
            "Pick any country or province — answers come from 25 years of NASA satellite fire "
            "data (MODIS + VIIRS).")

regions = data.regions()
icons = {"world": "🌍", "country": "🏳️", "province": "📍"}
region_id = st.selectbox(
    "Place", list(regions.index), index=list(regions.index).index(DEFAULT_PLACE),
    format_func=lambda rid: f"{icons[regions.loc[rid, 'level']]} {regions.loc[rid, 'name']}",
    help="Type to search. Provinces are listed as 'Province, Country'.",
)
region = regions.loc[region_id]
bbox = (region["west"], region["south"], region["east"], region["north"])

result = data.analysis(region_id)
monthly, weekly = result.monthly, result.weekly
if np.nansum(monthly.to_numpy()) < 10:
    st.info("Satellites have seen almost no fires here since 2001. Try another place.")
    st.stop()

season = burn_calendar.critical_period(weekly)
week_now = ui.current_week()
in_season = week_now in burn_calendar.weeks_in(season)
bad_year, bad_times = burn_calendar.worst_year(monthly)

# ---- 1. live hotspots: what is happening now? ------------------------------------------
days = 2 if region_id == "world" else 7  # the whole world for a week is too much data
window = f"{days} days"
live, live_error = None, None
if firms_live.map_key():
    try:
        # The request is a rectangle, so keep only hotspots inside the chosen place.
        live = now.inside(now.locate(firms_live.recent_hotspots(bbox, days)), region_id)
    except Exception as error:  # show the reason (e.g. invalid key) instead of crashing
        live_error = str(error)

if live is not None:
    finished = firms_live.complete_days(live)   # today is unfinished: leave it out of the maths
    activity_now, now_times = now.times_normal(finished, region_id, days)
    parts = now.hottest_parts(finished, region_id, days)

# Smoke: NASA aerosol data (skipped for the whole world: one picture would be too coarse).
today_utc = datetime.now(timezone.utc).date()
aod, smoke_text = None, None
if region_id != "world":
    try:
        aod, smoke_bounds = smoke.smoke_map(bbox, today_utc)
        smoke_text = smoke.describe(aod, smoke_bounds, region_id, region["name"])
    except Exception as error:  # no smoke data is not a reason to stop the page
        smoke_text = f"*(Smoke data unavailable: {error})*"

# ---- 2. the three answers ----------------------------------------------------------------
c1, c2, c3 = st.columns(3)
if live is not None:
    unusual_now = now_times >= 2 and activity_now >= 10
    c1.metric(f"Right now (last {window})", f"{now_times:.1f}× normal",
              "Unusual" if unusual_now else "Normal",
              delta_color="inverse" if unusual_now else "off", delta_arrow="off",
              help=f"{len(finished):,} hotspots in the last {window} (complete days, up to "
                   "yesterday UTC), compared with this time of year since 2001.")
else:
    c1.metric("Right now", "—", "Live data off", delta_color="off", delta_arrow="off",
              help="Add a free NASA FIRMS MAP_KEY to see live hotspots (see below).")
c2.metric("Fire season", ui.season_months(season),
          "Happening now" if in_season
          else f"Starts in {burn_calendar.weeks_until(week_now, season[0])} weeks",
          delta_color="inverse" if in_season else "off", delta_arrow="off",
          help=f"Usually {ui.week_label(season[0])} to {ui.week_label(season[1])}.")
c3.metric("Worst year since 2001", str(bad_year), f"{bad_times:.1f}× a normal year",
          delta_color="off", delta_arrow="off")

# One short story: first what is happening now, then how that compares with history.
story = []
if live is not None and len(finished):
    level = "**unusually high**" if unusual_now else "within the normal range"
    story.append(f"**Right now:** {len(finished):,} hotspots in the last {window} in "
                 f"**{region['name']}** — {now_times:.1f}× normal for {ui.week_label(week_now)}, "
                 f"{level}.")
    if not parts.empty:
        story.append("Most are in " + ", ".join(
            f"**{row.name}** ({row.hotspots:,} · {row.times:.1f}× normal)"
            for row in parts.itertuples()) + ".")
elif live is not None:
    story.append(f"**Right now:** no hotspots in **{region['name']}** in the last {window}.")
if smoke_text:
    story.append(smoke_text)
weeks_since_season = burn_calendar.weeks_until(season[1], week_now)
if in_season:
    season_text = "we are **in** the usual fire season now"
elif weeks_since_season <= 6:
    season_text = "the usual season has **just ended**, so fires now are later than usual"
else:
    season_text = (f"the next season usually starts in about "
                   f"{burn_calendar.weeks_until(week_now, season[0])} weeks")
story.append(f"Fires here usually happen between **{ui.week_label(season[0])}** and "
             f"**{ui.week_label(season[1])}** — {season_text}. The worst year since 2001 was "
             f"**{bad_year}**, with {bad_times:.1f}× the burning of a normal year.")
st.markdown("> " + "  \n> ".join(story))

# ---- 3. live map -------------------------------------------------------------------------
st.subheader("🗺️ Hotspots and smoke right now")
FLAT, GLOBE = "Flat map", "Globe 3D (carbon monoxide)"
view = st.segmented_control("View", [FLAT, GLOBE], default=FLAT)

if view == GLOBE:
    # The whole Earth with the smoke gas CO from NASA AIRS, like NASA's "Eyes on the Earth".
    try:
        co_picture, co_period, co_share = co.world_map(today_utc)
        co_note = (f"Carbon monoxide (CO) at ~5.5 km height (500 hPa, ~18,000 ft) from AIRS on "
                   f"NASA's Aqua satellite, {co_period}. Blue/green = clean air, yellow → dark red "
                   f"= more CO, mostly smoke from fires (scale {co.LOW:.0f}–{co.HIGH:.0f}+ ppbv). "
                   f"Dark grey = no measurement. Drag to spin the globe, scroll to zoom.")
    except Exception as error:  # no CO data is not a reason to hide the globe
        co_picture, co_note = None, f"(Carbon monoxide data unavailable: {error})"
    st.pydeck_chart(maps.globe_map(live, bbox, co_picture, co.WIDTH), height=560)
    st.caption(co_note + (f" Dots: {len(live):,} hotspots in {region['name']} (last {window} "
                          "+ today)." if live is not None else ""))
else:
    # Background: a real NASA satellite photo, so you can see smoke plumes next to the hotspots,
    # optionally with the measured smoke (aerosol) painted on top.
    WITH_SMOKE, PHOTO, DARK = "Photo + smoke", "Photo", "Dark map"
    background = st.segmented_control("Background", [WITH_SMOKE, PHOTO, DARK],
                                      default=WITH_SMOKE)
    pictures, photo_note, max_zoom = [], "", maps.DARK_MAP_MAX_ZOOM
    if background in (WITH_SMOKE, PHOTO):
        try:
            image, bounds, today_share = satellite.newest_photo(bbox, today_utc)
            pictures.append(maps.photo_layer(image, bounds))
            # Stop zooming in where the photo would start to look blocky.
            max_zoom = maps.sharp_zoom_limit(bounds, satellite.WIDTH)
            photo_note = (f" Photo: NASA satellites — {today_share:.0%} of this view was "
                          "photographed today, the rest yesterday afternoon. Grey-brown haze is "
                          "smoke; bright white is cloud.")
        except Exception as error:  # no photo is not a reason to hide the hotspots
            photo_note = f" (Satellite photo unavailable: {error})"
    if background == WITH_SMOKE and aod is not None:
        pictures.append(maps.photo_layer(smoke.overlay(aod, smoke_bounds), smoke_bounds))
        photo_note += (" Yellow-to-red shading = smoke/haze measured by NASA (aerosol); "
                       "no shading = clean air or not measured (clouds).")
    if live is not None:
        st.pydeck_chart(maps.hotspot_map(live, bbox, pictures, max_zoom), height=520)
        today_count = len(live) - len(finished)
        st.caption(f"{len(finished):,} hotspots in the last {window} + {today_count:,} today so "
                   "far (UTC; new satellite passes appear within a few hours). "
                   + maps.legend(live) + photo_note)

if live is not None:
    with st.expander("List of the latest hotspots"):
        latest = live.sort_values(["acq_date", "acq_time"], ascending=False)
        columns = ["time_utc", "latitude", "longitude", "sensor", "confidence_level", "frp"]
        st.dataframe(latest[columns].head(50), hide_index=True, width="stretch")
        st.download_button("Download all as CSV", latest[columns].to_csv(index=False).encode(),
                           file_name="earthguard_live_hotspots.csv", mime="text/csv")
elif live_error:
    st.error(f"Could not load live data from NASA FIRMS: {live_error}")
else:
    st.info("**Live map is off.** Get a free key at "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key/, then create "
            "`.streamlit/secrets.toml` containing `FIRMS_MAP_KEY = \"your key\"` and restart.")

# ---- 4. the 25-year calendar ---------------------------------------------------------------
st.subheader("📅 Fire calendar, 2001–2025")
st.plotly_chart(charts.calendar_heatmap(monthly, season), width="stretch")
st.caption("Each row is a year, each column a month. **Darker red = more fire.** "
           "A white square marks an unusually bad month (at least twice the normal amount). "
           "The bars at the bottom show a normal year; red bars = fire season.")

events = burn_calendar.unusual_events(monthly, limit=6)
if not events.empty:
    st.markdown("**Most unusual months:**  " + " · ".join(
        f"{ui.MONTH_NAMES[month - 1]} {year} (**{row.times_typical:.1f}×** normal)"
        for (year, month), row in events.iterrows()))

# ---- 5. for judges: how it works and where the data comes from -------------------------
with st.expander("🛰️ How it works — combining two NASA satellites"):
    st.markdown(
        "NASA has watched fires from space with **MODIS** since 2000 and with **VIIRS** since 2012. "
        "VIIRS has sharper eyes (375 m vs 1 km), so it reports more hotspots — the raw numbers "
        "would make fire look like it suddenly jumped in 2012. EarthGuard fixes this:\n"
        "1. Put both satellites on the same ~1 km grid and count each cell once per day.\n"
        "2. In 2012–2025, when both watched together, learn how many times more VIIRS sees "
        "(separately for each month).\n"
        "3. Divide VIIRS by that number → one fair record from 2001 to 2025."
    )
    st.plotly_chart(charts.harmonization_lines(result.monthly_table, result.harmonized_monthly),
                    width="stretch")
    check = data.validation(region_id)
    v1, v2 = st.columns(2)
    v1.metric("Accuracy (R²)", f"{check['r2']:.2f}" if np.isfinite(check["r2"]) else "n/a",
              help="Test: hide one year, predict MODIS from VIIRS, compare. 1.0 = perfect.")
    v2.metric("Typical error", f"±{check['median_error']:.0%}"
              if np.isfinite(check["median_error"]) else "n/a")

with st.expander("ℹ️ About the data"):
    st.markdown(
        "- **History:** NASA FIRMS MODIS (2001–2025) and VIIRS Suomi NPP (2012–2025).\n"
        "- **Live:** NASA FIRMS near-real-time API (VIIRS NOAA-20/21, MODIS).\n"
        "- **Satellite photo:** NASA GIBS true colour (MODIS Terra, VIIRS NOAA-20), newest pass.\n"
        "- **Provinces:** Natural Earth (public domain).\n"
        "- Only detections labelled *vegetation fire* with nominal/high confidence are used.\n"
        "- Limits: clouds and smoke can hide fires; a hotspot is a heat signal, not a confirmed "
        "fire; small fires may be missed; farm burning is normal and seasonal in many places."
    )
    st.markdown((ROOT / "REFERENCES.md").read_text(encoding="utf-8").split("\n", 2)[2])

st.divider()
st.caption(f"⚠️ {DISCLAIMER}  \n{DATA_CREDIT} · Built for the NASA Space Apps Challenge 2026.")
