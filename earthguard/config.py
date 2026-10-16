"""Shared constants. Change a number here and every page uses the new value.

Keeping "magic numbers" in one place makes it easy to explain (and tune) the method.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

# ---- Sensors -------------------------------------------------------------------------
MODIS = "MODIS"
VIIRS = "VIIRS"

FIRST_YEAR = 2001          # MODIS (Terra) starts in Nov 2000, so 2001 is the first full year
VIIRS_FIRST_YEAR = 2012    # VIIRS on Suomi NPP starts in Jan 2012...
VIIRS_FIRST_DAY = "2012-01-20"  # ...on Jan 20, so January 2012 is incomplete for VIIRS
LAST_YEAR = 2025

# The years both sensors observed together. We learn the VIIRS -> MODIS ratio here.
OVERLAP_YEARS = (VIIRS_FIRST_YEAR, LAST_YEAR)

# ---- Grid ----------------------------------------------------------------------------
# Each detection is snapped to a grid cell of this size (degrees). 0.01 deg is about 1.1 km at
# the equator, close to one MODIS pixel. A cell is counted at most once per day per sensor:
# this is an "active-fire cell-day".
GRID_DEG = 0.01
# Provinces are looked up on a coarser grid: 5 x 5 cells = 0.05 deg (~5 km).
PROVINCE_CELLS = 5

# ---- Harmonization -------------------------------------------------------------------
# A month-of-year ratio is trusted only when MODIS saw at least this many cell-days in it
# (summed over the overlap years). Otherwise we fall back to a broader ratio.
MIN_MODIS_FOR_RATIO = 50

# ---- Calendar ------------------------------------------------------------------------
# "Unusual" needs all three:
UNUSUAL_PERCENTILE = 0.90   # 1. in the top 10% of years for that month/week
UNUSUAL_MIN_TIMES = 2.0     # 2. at least twice the typical amount
UNUSUAL_MIN_SHARE = 0.10    # 3. big enough to see: at least 10% of the worst month ever here...
MIN_UNUSUAL_COUNT = 10      #    ...and at least this many cell-days ("3 instead of 1" is not news)
CRITICAL_SHARE_OF_PEAK = 0.5  # critical period = weeks with >= 50% of the peak week's activity
CRITICAL_SMOOTHING_WEEKS = 5  # ...after averaging each week with its neighbours (5-week window)
WEEKS_PER_YEAR = 52

# ---- Text ----------------------------------------------------------------------------
DISCLAIMER = (
    "Satellite hotspots are not confirmed fires. EarthGuard supports planning and research; "
    "it is not an official alert system."
)
DATA_CREDIT = "Data: NASA FIRMS (MODIS, VIIRS)"

# ---- Colors (from docs/stitch-prompts.md) --------------------------------------------
COLOR_MODIS = "#38BDF8"
COLOR_VIIRS = "#A78BFA"
COLOR_HARMONIZED = "#F59E0B"
COLOR_UNUSUAL = "#EF4444"
COLOR_MUTED = "#94A3B8"
HEAT_SCALE = ["#1E293B", "#78350F", "#F59E0B", "#F97316", "#EF4444"]
