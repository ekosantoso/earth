# Stitch Prompts — EarthGuard (Global · Harmonization Challenge)

UI design prompts for [Stitch by Google](https://stitch.withgoogle.com) for **EarthGuard**, our answer to the NASA Space Apps Challenge 2026 challenge **["Harmonization of MODIS and VIIRS Hot Spots"](https://www.spaceappschallenge.org/2026/challenges/harmonization-of-modis-and-viirs-hot-spots/)**.

> **Before using these prompts**
> - **Timing:** Space Apps rules say teams may not start working on challenges before the hackathon (Nov 14–15, 2026). Generating final UI designs counts as challenge work, so **use these prompts during the event**, or confirm with your Local Lead first.
> - **Full challenge statement** comes out Oct 28. Re-check these prompts against its requirements and adjust wording.
> - **Participants under 18:** submissions must not include recognizable names, voices or likenesses of minors. The Team section uses **roles only**. Do not add real names or photos.
> - **Example numbers** (Riau, 4.1×, 0.62, etc.) are mockup placeholders, not real data.

## How each challenge requirement maps to a screen

| Challenge asks for | Where it lives |
|---|---|
| Web application | The whole app |
| Harmonize MODIS + VIIRS records | Prompt 2: **Harmonization** (method + proof); sensor toggle on every screen |
| Burning activity calendar | Prompt 0: **Burning Calendar** (main screen) |
| Selected area of interest | AOI picker in the sidebar on every screen |
| Historical fire patterns | Prompt 0 calendar + Prompt 1 seasonal profile |
| Unusual conditions | Prompt 1: anomaly highlights + "Unusual events" list |
| Critical periods | Prompt 1: critical-period band + per-year season table |
| Users: early warning/emergency responders, scientists, land managers | Audience line in Prompt 0, wording throughout |

## How to use

1. In Stitch, choose **Web** mode.
2. Paste **Prompt 0** first. It sets the design system and the main screen.
3. Then paste **Prompts 1–6** one at a time. Stitch works best with one screen per prompt.
4. For small changes, send short follow-ups (e.g. *"Make the calendar cells larger"*) instead of re-sending a long prompt.

## Moving the design into Streamlit

- Copy the colors into `.streamlit/config.toml`: `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, and set `st.set_page_config(layout="wide")`.
- **Burning calendar:** Plotly `go.Heatmap` (years × months, or years × weeks), with annotations for unusual cells.
- **Area of interest:**
  - Country/region select box (Natural Earth boundaries).
  - Optional rectangle drawing via `streamlit-folium` with the Draw plugin.
- **Maps with many points:** use pydeck.
- **Lower priority:** the before/after slider and the choropleth need extra components, so leave them for last.

---

## Prompt 0: design system + Burning Calendar (main screen)

```
Design a desktop web app called "EarthGuard" — built by a student team from Indonesia for the NASA Space Apps Challenge 2026, answering the challenge "Harmonization of MODIS and VIIRS Hot Spots".

Purpose: satellites have recorded active-fire hotspots for over 20 years, but the record is split between two sensors (MODIS since 2000, VIIRS since 2012) that cannot be compared directly. EarthGuard harmonizes both into one consistent record and turns it into a "burning activity calendar" for any area of interest in the world, so people can see historical fire patterns, unusual conditions and critical periods.

Audience: early-warning and emergency-response teams, scientists, land managers, plus the general public and hackathon judges. The main message must be clear within 10 seconds.

Visual style:
- Dark theme, calm and scientific, like a friendly mission-control dashboard.
- Background #0B1220, cards #131C2E, thin borders #22304A, text #E5E7EB, muted text #94A3B8.
- Sequential heat scale for activity: #1E293B (none) → #78350F → #F59E0B (amber) → #F97316 (orange) → #EF4444 (red).
- Teal #14B8A6 means "lower than usual". A white 2px outline marks "unusual" cells.
- Sensor colors used consistently everywhere: MODIS = sky blue #38BDF8, VIIRS = violet #A78BFA, Harmonized = amber #F59E0B.
- Fonts: Inter for UI, JetBrains Mono for numbers and coordinates.
- 12px rounded corners, generous spacing, no heavy gradients or glassmorphism.
- WCAG AA contrast. Never rely on color alone — always pair with a label, pattern or icon.

Layout constraints (this will be built with Python Streamlit):
- Fixed left sidebar (280px): app name "EarthGuard" with a small flame-and-orbit icon, page navigation (Burning Calendar, Unusual & Critical Periods, Harmonization, Live Map, Fire Season Stories, About the Data), then controls.
- Main area is one wide column with blocks stacked vertically; rows of 2–4 metric cards.
- Use only standard components: metric cards, heatmaps, line/bar charts, one map, tabs, tables, expanders, buttons, date pickers, select boxes, radio buttons. No custom animations.

Sidebar controls (shared by all analysis pages):
- "Area of interest" block: search box for country or province/state (example selected: "Riau, Indonesia"), a small locator map thumbnail showing the selected area, and a link "Draw a custom rectangle".
- Data source radio: "Harmonized MODIS + VIIRS (recommended)", "MODIS only (2000–now)", "VIIRS only (2012–now)".
- Year range slider 2001–2025.
- Measure select: "Hotspot count (MODIS-equivalent)", "Active-fire days", "Fire Radiative Power".
- Confidence filter: "Nominal + High" (default) / "All".

Wording rules:
- Say "hotspot", "active-fire detection" or "burning activity", never "confirmed fire".
- Footer on every page: "Satellite hotspots are not confirmed fires. EarthGuard supports planning and research; it is not an official alert system." and "Data: NASA FIRMS (MODIS, VIIRS)".
- Do not use the NASA logo.

Create the main screen: BURNING CALENDAR.
- Header: "Burning activity calendar — Riau, Indonesia", subtitle "Harmonized MODIS + VIIRS, 2001–2025".
- Row of 4 metric cards: "Peak month: September", "Typical critical period: Aug – Oct", "Most active year: 2015 (4.1× typical)", "Trend since 2001: ▼ 38%".
- The centerpiece: a large calendar heatmap. Rows = years 2001 (top) to 2025 (bottom), columns = months Jan–Dec. Cell color = harmonized burning activity on the sequential heat scale. Unusual cells (far above typical for that month) have a white outline and a small "!" marker. A thin horizontal divider between 2011 and 2012 labelled "VIIRS joins the record — harmonized from here". Hovering a cell shows: month/year, harmonized count, MODIS count, VIIRS count, and "×typical" ratio.
- Above the calendar, a toggle: "Months" / "Weeks" (weeks shows 52 narrower columns).
- To the right of the calendar: a vertical "Typical year" profile — a small bar chart of the average activity per month, with Aug–Oct shaded and labelled "Critical period".
- Below: a legend explaining the color scale, the white outline ("unusual"), and the VIIRS divider.
- Info callout: "How to read this: each row is one year. Darker red = more burning activity. Look for vertical bands (seasons that repeat every year) and outlined cells (unusual months)."
```

## Prompt 1: Unusual & Critical Periods

```
Using the same EarthGuard design system and sidebar, create the UNUSUAL & CRITICAL PERIODS screen.
- Header: "Unusual conditions and critical periods — Riau, Indonesia".
- Seasonal profile chart (main, full width): x-axis = week of year (1–52). Shaded grey band = typical range (10th–90th percentile, 2001–2025); dashed line = median; orange line = the selected year (year picker at top right, example 2015). Weeks where the selected year is above the 90th percentile are shaded red and labelled "Unusual". A translucent amber vertical band marks the "Critical period: weeks 31–43".
- Anomaly bar chart below: one bar per year 2001–2025 showing "× typical" for the critical period (1.0 = typical line). Bars above 2× are red and labelled; bars below 0.5× are teal.
- Two side-by-side cards:
  - "Unusual events" table: period, harmonized hotspots, × typical, note. Example rows: "Sep 2015 — 4.1× typical", "Sep 2019 — 2.8×", "Mar 2014 — 2.2× (off-season)".
  - "Critical period by year" table: year, start week, peak week, end week, length (weeks). Include a summary line: "The critical period now starts on average 2 weeks earlier than in the 2000s."
- "Planning outlook" card (not a forecast): "Based on 25 years of records, the critical period in this area usually begins in early August — about 6 weeks from today." with a small note "Historical pattern, not a prediction."
- Keep the same footer disclaimer and data credit.
```

## Prompt 2: Harmonization (method & proof)

```
Using the same EarthGuard design system and sidebar, create the HARMONIZATION screen — it explains and proves how MODIS and VIIRS are combined. This is the scientific core of the project.
- Header: "Why harmonize? Two sensors, one record".
- Explainer row of 3 cards with simple icons:
  1. "MODIS (Terra & Aqua) — 1 km pixels, since 2000."
  2. "VIIRS (S-NPP, NOAA-20, NOAA-21) — 375 m pixels, since 2012. Sees smaller fires, so it reports many more hotspots."
  3. "Harmonized — VIIRS converted to MODIS-equivalent values, so 2001 and 2025 can be compared fairly."
- Main chart: monthly time series 2001–2025 with three lines in sensor colors: MODIS raw (sky blue), VIIRS raw (violet, starting 2012, visibly much higher), Harmonized (amber, continuous across 2012). Shade 2012–2025 lightly and label it "Overlap period used for calibration".
- Calibration panel (two columns):
  - Left: scatter plot of monthly MODIS count (x) vs VIIRS count (y) during the overlap period, with a fitted line, the equation "VIIRS ≈ 3.6 × MODIS", and "R² = 0.91".
  - Right: "Method in 4 steps" numbered list — 1) put both sensors on the same 1 km grid, 2) count active-fire cells per day, 3) learn the VIIRS-to-MODIS ratio for this region and season from the overlap years, 4) apply it to build one continuous record.
- "Harmonization quality" row of 3 metric cards: "Overlap months: 168", "Fit R²: 0.91", "Typical error: ±12%".
- Expander "Limitations": sensor overpass times differ, MODIS satellites are aging and drifting, ratios differ by land cover and season, clouds and smoke hide fires from both sensors.
```

## Prompt 3: Live Map

```
Using the same EarthGuard design system and sidebar, create the LIVE MAP screen — current hotspots shown in the context of the calendar.
- Top row of 4 metric cards for the selected area: "Hotspots last 7 days: 214", "Typical for this week: 65", "Status: 3.3× typical — Unusual" (red badge with icon), "Inside critical period: Yes (week 36 of 31–43)".
- Large map (~60% of viewport height), dark basemap, the area of interest outlined in white. Hotspots as small glowing dots: circles for MODIS, diamonds for VIIRS, colored by confidence. Legend bottom-left. Layer toggle top-right: Hotspots / Density / Satellite imagery. Time window segmented control: 24h / 48h / 7 days.
- Hotspot popup example: date & time (UTC and local), latitude/longitude, sensor and satellite, confidence, Fire Radiative Power (MW).
- Right of the map: a compact "This year so far" mini calendar strip (12 month cells for 2026) using the same color scale as the main calendar, with the current month highlighted.
- Below: "Latest detections" table with 10 rows (local time, coordinates, sensor, confidence, FRP) and a "Download CSV" button.
- Add a "Whole world" variant of the map at low zoom showing a hexagon density layer and the note "Pick an area of interest to see its calendar".
```

## Prompt 4: Fire Season Stories

```
Using the same EarthGuard design system, create the FIRE SEASON STORIES screen — guided stories that show how to read the calendar.
- Top: a grid of four story cards — "Indonesia 2015: The Great Haze", "Amazon 2019: The Rainforest Burns", "Australia 2019–20: Black Summer", "Canada 2023: A Record Season". Each card has a satellite image thumbnail, a mini calendar strip of that year with the unusual months outlined, and one key stat (e.g. "4.1× typical").
- Story reader below, step-by-step:
  - Progress stepper "Step 2 of 5" with dots.
  - Left: a large true-color satellite image of a smoke plume, with a caption "NASA Terra/MODIS · 24 Sep 2015".
  - Right: a short narrative paragraph (60–80 words), one big key number (e.g. "2,914 hotspots in a single day"), and the area's burning calendar with the current month highlighted by a pulsing outline.
  - "← Previous" and "Next →" buttons.
- Show the final step as a second variant: a before/after comparison of two satellite images with a vertical drag handle, plus a button "Open this area's calendar".
```

## Prompt 5: About the Data & Method

```
Using the same EarthGuard design system, create the ABOUT THE DATA screen.
- "What is a hotspot?" — a simple 3-step illustration: satellite in orbit → detects unusual heat → hotspot on the map, with one sentence each.
- "Data sources" table: dataset, satellite/sensor, resolution, years available, coverage, provider. Rows: NASA FIRMS MODIS (Terra & Aqua, 1 km, 2000–now, global), NASA FIRMS VIIRS (S-NPP, NOAA-20, NOAA-21, 375 m, 2012–now, global), NASA GIBS satellite imagery (daily, global), Natural Earth boundaries (public domain).
- "How we harmonize" — short summary of the 4-step method with a link "See the Harmonization page".
- "How we define unusual and critical" — two formula cards: "Unusual = top 10% of years for that week and at least 2× typical" and "Critical period = weeks where typical activity (averaged over 5 weeks) is at least 50% of the peak week".
- "Limitations" — bullet list: clouds and smoke can hide fires, small fires may be missed, a hotspot can be a non-fire heat source (gas flares, volcanoes, industry), satellites pass only a few times a day, agricultural burning is common and seasonal in many regions, harmonization ratios are estimates.
- "References & licenses" — a list of every data source and open-source library used, each with its license.
- "Team" — 6 role cards with a simple icon (no names, no photos, no initials): Team Lead, Data Engineer, Data Analyst, App Developer, Maps & Visuals, Research & Storytelling. Caption: "A student team from Indonesia".
- Small line at the bottom: "Built for the NASA Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots."
```

## Prompt 6 (optional): Home

```
Using the same EarthGuard design system, create a HOME screen without the controls sidebar (navigation only).
- Hero: headline "When does your area burn?", subtext "25 years of NASA satellite fire records — MODIS and VIIRS harmonized into one calendar for any place on Earth."
- A large search box: "Search a country, province or state…" with example chips (Riau, Indonesia · Mato Grosso, Brazil · New South Wales, Australia · British Columbia, Canada · Central African Republic).
- Visual: a sample burning calendar heatmap glowing on a dark world-map background.
- Three feature cards: "Burning Calendar — see the seasons", "Unusual & Critical — spot the abnormal and the dangerous weeks", "Harmonized — two NASA sensors, one fair record".
- Two buttons: "Open the calendar" (primary, orange) and "Read fire season stories" (secondary).
- Footer disclaimer and data credit as on other pages.
```
