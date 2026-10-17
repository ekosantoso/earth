"""pydeck maps. pydeck draws with the graphics card (WebGL), so many points stay smooth."""

import base64
import io
import math

import numpy as np
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from PIL import Image

LEVELS = ["low", "nominal", "high"]
LEVEL_COLORS = [[245, 158, 11, 170], [249, 115, 22, 210], [239, 68, 68, 235]]  # amber, orange, red

# Sending every hotspot to the browser can be 25+ MB (Indonesia has 100k+ in a busy week).
# So hotspots in the same small grid square become ONE dot at their average position. We use
# the same ~1 km grid as the history; only if there are still too many dots, a coarser one.
SPOT_GRIDS = [(0.01, "~1 km"), (0.05, "~5 km"), (0.1, "~11 km"), (0.5, "~55 km")]
MAX_SPOTS = 35_000


DARK_MAP_MAX_ZOOM = 12   # the dark basemap is sharp at every zoom; this just keeps it sensible


def sharp_zoom_limit(bounds: list[float], width_px: int, overzoom: float = 1.0) -> float:
    """The deepest zoom before a picture of `width_px` pixels over `bounds` starts to look blocky.

    At zoom z a web map shows the whole world 512 * 2**z screen pixels wide, so one screen pixel
    covers 360 / (512 * 2**z) degrees. The picture has (east - west) / width_px degrees per
    pixel. They are equal at z = log2(360 * width_px / (512 * (east - west))). We allow
    `overzoom` more zoom levels (1 = each picture pixel may become 2 x 2 screen pixels).
    """
    west, _, east, _ = bounds
    return math.log2(360 * width_px / (512 * max(east - west, 1e-6))) + overzoom


def view_for(bbox: tuple, max_zoom: float = DARK_MAP_MAX_ZOOM) -> pdk.ViewState:
    west, south, east, north = bbox
    span = max(east - west, north - south, 0.1)
    zoom = max(0.5, min(10, math.log2(360 / span) - 0.5, max_zoom))
    return pdk.ViewState(longitude=(west + east) / 2, latitude=(south + north) / 2, zoom=zoom,
                         max_zoom=max_zoom)


def merge_spots(hotspots: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """One row per grid square: average position, number of hotspots, highest confidence,
    newest time. Returns the table and the grid size in words (e.g. "~1 km")."""
    level = hotspots["confidence_level"].map({name: i for i, name in enumerate(LEVELS)})
    hotspots = hotspots.assign(level=level.fillna(1).astype(int))
    for size, words in SPOT_GRIDS:
        spots = (hotspots.assign(x=np.floor(hotspots["longitude"] / size),
                                 y=np.floor(hotspots["latitude"] / size))
                         .groupby(["x", "y"])
                         .agg(longitude=("longitude", "mean"), latitude=("latitude", "mean"),
                              hotspots=("latitude", "size"), level=("level", "max"),
                              latest=("time_utc", "max"))
                         .reset_index(drop=True))
        if len(spots) <= MAX_SPOTS:
            break
    return spots, words


def legend(hotspots: pd.DataFrame) -> str:
    _, words = merge_spots(hotspots)
    return (f"Each dot = the hotspots inside one {words} square, at their exact average "
            "position; dots keep their size when you zoom. Red = high confidence, "
            "orange = nominal, amber = low; bigger dot = more hotspots in that square.")


def _spots_layer(hotspots: pd.DataFrame) -> pdk.Layer:
    spots, _ = merge_spots(hotspots)
    # Keep the data small: short column names, rounded numbers, colour and size worked out in
    # the browser from the confidence level (0, 1, 2) instead of sent for every dot.
    small = pd.DataFrame({
        "lon": spots["longitude"].round(3), "lat": spots["latitude"].round(3),
        "n": spots["hotspots"], "c": spots["level"],
        "t": spots["latest"].astype(str).str[5:],          # "2026-10-15 06:12" -> "10-15 06:12"
    })
    low, nominal, high = LEVEL_COLORS
    colour = f"c == 2 ? {high} : (c == 1 ? {nominal} : {low})"
    # Radius in PIXELS: zooming in spreads the dots apart instead of making them bigger.
    # A thin dark outline keeps them visible on top of bright clouds in the satellite photo.
    return pdk.Layer("ScatterplotLayer", small, get_position=["lon", "lat"],
                     get_fill_color=colour, get_radius="n > 15 ? 7 : (n > 3 ? 5 : 3.5)",
                     radius_units="'pixels'", stroked=True, get_line_color=[0, 0, 0, 200],
                     line_width_min_pixels=1, pickable=True)


def photo_layer(image: str, bounds: list[float]) -> pdk.Layer:
    """Show a picture (a data URL) stretched over bounds = [west, south, east, north].

    pydeck treats plain strings as JavaScript expressions. Wrapping the text in double quotes
    tells it "this is just text", so the picture travels inside the map data itself and needs
    no file or web address (which also works on Streamlit Community Cloud).
    """
    return pdk.Layer("BitmapLayer", data=None, image=f'"{image}"', bounds=bounds)


def to_data_url(picture: Image.Image, fmt: str = "JPEG") -> str:
    """A picture as text ("data:image/...;base64,...") that a browser can show directly."""
    buffer = io.BytesIO()
    picture.save(buffer, format=fmt, **({"quality": 85} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buffer.getvalue()).decode()


GLOBE_ZOOM = 1.6
BORDERS_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
               "ne_110m_admin_0_countries.geojson")   # Natural Earth, public domain


@st.cache_data(ttl=7 * 24 * 3600)
def _borders() -> dict:
    """Country outlines for the globe (the globe has no map underneath, unlike the flat map)."""
    return requests.get(BORDERS_URL, timeout=60).json()


def globe_map(hotspots: pd.DataFrame | None, bbox: tuple, picture: str | None,
              width_px: int = 1440) -> pdk.Deck:
    """A 3D globe you can spin: a whole-Earth picture (e.g. carbon monoxide), country borders
    and the hotspots on top. deck.gl calls this view "_GlobeView" (still experimental)."""
    layers = []
    if picture:   # a picture of the whole Earth in plain longitude/latitude
        layers.append(pdk.Layer("BitmapLayer", data=None, image=f'"{picture}"',
                                bounds=[-180, -90, 180, 90]))
    layers.append(pdk.Layer("GeoJsonLayer", _borders(), stroked=True, filled=False,
                            get_line_color=[20, 20, 20, 220], line_width_min_pixels=1))
    if hotspots is not None and len(hotspots):
        layers.append(_spots_layer(hotspots))
    view = view_for(bbox)
    return pdk.Deck(
        layers=layers, views=[pdk.View(type="_GlobeView", controller=True)],
        # Start far enough away to see the whole globe, turned towards the chosen place.
        # The CO picture covers the world in `width_px` pixels: stop zooming before it gets blocky.
        initial_view_state=pdk.ViewState(longitude=view.longitude, latitude=view.latitude,
                                         zoom=GLOBE_ZOOM,
                                         max_zoom=sharp_zoom_limit([-180, -90, 180, 90], width_px)),
        map_provider=None, map_style=None, parameters={"cull": True},
        tooltip={"html": "<b>{n}</b> hotspot(s) here<br>{lat}, {lon}<br>newest: {t} UTC"},
    )


def hotspot_map(hotspots: pd.DataFrame, bbox: tuple, pictures: list[pdk.Layer] | None = None,
                max_zoom: float = DARK_MAP_MAX_ZOOM) -> pdk.Deck:
    """Hotspots on top of background pictures (bottom first, e.g. [satellite photo, smoke]).

    max_zoom: how far users may zoom in (see sharp_zoom_limit, so photos never look blocky)."""
    west, south, east, north = bbox
    outline = pd.DataFrame({"path": [[[west, south], [east, south], [east, north],
                                      [west, north], [west, south]]]})
    layers = [
        *(pictures or []),
        pdk.Layer("PathLayer", outline, get_path="path", get_color=[255, 255, 255, 180],
                  width_min_pixels=1),
        _spots_layer(hotspots),
    ]
    tooltip = {"html": "<b>{n}</b> hotspot(s) here<br>{lat}, {lon}<br>newest: {t} UTC<br>"
                       "confidence level: {c} (0 low · 1 nominal · 2 high)"}
    return pdk.Deck(layers=layers, initial_view_state=view_for(bbox, max_zoom), tooltip=tooltip,
                    map_style=pdk.map_styles.CARTO_DARK)
