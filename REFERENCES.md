# References & licenses

Space Apps requires every source to be cited, including open-source libraries.
**Before submitting, check each DOI/citation against the official FIRMS citation page.**

## NASA data

| Source | Used for | Citation / link |
|---|---|---|
| NASA FIRMS — MODIS active fire detections (Terra & Aqua), Standard Processing, Country Yearly Summary | Historical record 2001–2025 | NASA FIRMS, https://firms.modaps.eosdis.nasa.gov/country/ — MODIS Collection 6.1 Hotspot / Active Fire Detections MCD14ML. DOI: 10.5067/FIRMS/MODIS/MCD14ML *(verify)* |
| NASA FIRMS — VIIRS 375 m active fire detections (Suomi NPP), Standard Processing, Country Yearly Summary | Historical record 2012–2025, calibration | NASA FIRMS, https://firms.modaps.eosdis.nasa.gov/country/ — VIIRS (S-NPP) I-Band 375 m Active Fire. *(add DOI from the FIRMS citation page)* |
| NASA FIRMS — Near Real-Time API (VIIRS NOAA-20, VIIRS NOAA-21, MODIS) | Live Map | https://firms.modaps.eosdis.nasa.gov/api/area/ |
| NASA GIBS — MODIS Terra and VIIRS NOAA-20 Corrected Reflectance (True Color) | Satellite photo behind the live map (smoke) | https://nasa-gibs.github.io/gibs-api-docs/ |
| NASA GIBS — MODIS Terra/Aqua Aerosol Optical Depth 3 km | Smoke/haze sentence and smoke layer | https://nasa-gibs.github.io/gibs-api-docs/ |
| NASA GIBS — AIRS (Aqua) Carbon Monoxide 500 hPa, Level 2 Day/Night | Globe 3D: carbon monoxide (smoke gas) around the Earth | https://nasa-gibs.github.io/gibs-api-docs/ |

Acknowledgement requested by FIRMS: *We acknowledge the use of data and imagery from NASA's Fire
Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and
Information System (ESDIS).* — Citation guidelines:
https://www.earthdata.nasa.gov/data/projects/lance#ed-firms-citation

## Other data

| Source | Used for | License |
|---|---|---|
| Natural Earth — Admin 1 states/provinces, 1:10m | Province/state areas of interest | Public domain — https://www.naturalearthdata.com/about/terms-of-use/ |
| Natural Earth — Admin 0 countries, 1:110m (GeoJSON from github.com/nvkelso/natural-earth-vector) | Country borders on the Globe 3D | Public domain |
| CARTO Dark Matter basemap (OpenStreetMap data) | Background of the Live Map | © CARTO, © OpenStreetMap contributors (ODbL). *Check CARTO basemap terms before public use.* |

## Software

| Library | License |
|---|---|
| Python | PSF License |
| Streamlit | Apache-2.0 |
| pandas | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| PyArrow | Apache-2.0 |
| Plotly | MIT |
| pydeck | Apache-2.0 |
| Requests | Apache-2.0 |
| GeoPandas (data preparation only) | BSD-3-Clause |
| pytest (tests only) | MIT |

## Tools

| Tool | Used for |
|---|---|
| Stitch by Google | UI mockups (see docs/stitch-prompts.md) |
| Claude (Anthropic) | Reference implementation used for teaching |
