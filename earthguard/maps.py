"""pydeck maps. pydeck draws with the graphics card (WebGL), so many points stay smooth."""

import math

import numpy as np
import pandas as pd
import pydeck as pdk

CONFIDENCE_COLORS = {
    "high": [239, 68, 68, 220],      # red
    "nominal": [249, 115, 22, 200],  # orange
    "low": [245, 158, 11, 140],      # amber
}
# Above this many hotspots (e.g. the whole world) we draw grid cells instead of single points,
# otherwise the browser has to download and draw hundreds of thousands of dots.
MAX_POINTS = 30_000
CELL_DEG = 0.5


def view_for(bbox: tuple) -> pdk.ViewState:
    west, south, east, north = bbox
    span = max(east - west, north - south, 0.1)
    zoom = max(0.5, min(10, math.log2(360 / span) - 0.5))
    return pdk.ViewState(longitude=(west + east) / 2, latitude=(south + north) / 2, zoom=zoom)


def legend(hotspots: pd.DataFrame) -> str:
    if len(hotspots) > MAX_POINTS:
        return (f"Too many to draw one by one: each dot is a {CELL_DEG}° area, "
                "bigger and redder = more hotspots.")
    return ("Red = high confidence, orange = nominal, amber = low. "
            "Bigger dots = MODIS (1 km), smaller = VIIRS (375 m).")


def _points_layer(hotspots: pd.DataFrame) -> pdk.Layer:
    points = hotspots.assign(
        color=hotspots["confidence_level"].map(CONFIDENCE_COLORS).apply(
            lambda c: c if isinstance(c, list) else [148, 163, 184, 120]),
        radius=hotspots["sensor"].map(lambda s: 1000 if s == "MODIS" else 375),
    )
    # A thin dark outline keeps the dots visible on top of bright clouds in the satellite photo.
    return pdk.Layer("ScatterplotLayer", points, get_position=["longitude", "latitude"],
                     get_fill_color="color", get_radius="radius", radius_min_pixels=4,
                     radius_max_pixels=12, stroked=True, get_line_color=[0, 0, 0, 220],
                     line_width_min_pixels=1, pickable=True)


def _cells_layer(hotspots: pd.DataFrame) -> pdk.Layer:
    cells = (hotspots.assign(longitude=(np.floor(hotspots["longitude"] / CELL_DEG) + 0.5) * CELL_DEG,
                             latitude=(np.floor(hotspots["latitude"] / CELL_DEG) + 0.5) * CELL_DEG)
                     .groupby(["longitude", "latitude"]).size().rename("hotspots").reset_index())
    share = (np.log1p(cells["hotspots"]) / np.log1p(cells["hotspots"].max())).to_numpy()
    cells["color"] = [[239, int(200 - 130 * s), 68, int(90 + 150 * s)] for s in share]
    cells["radius"] = 8000 + 22000 * share
    return pdk.Layer("ScatterplotLayer", cells, get_position=["longitude", "latitude"],
                     get_fill_color="color", get_radius="radius", radius_min_pixels=2,
                     stroked=True, get_line_color=[0, 0, 0, 160], line_width_min_pixels=1,
                     pickable=True)


def photo_layer(image: str, bounds: list[float]) -> pdk.Layer:
    """Show a picture (URL or data URL) stretched over bounds = [west, south, east, north]."""
    return pdk.Layer("BitmapLayer", data=None, image=image, bounds=bounds)


def hotspot_map(hotspots: pd.DataFrame, bbox: tuple,
                pictures: list[pdk.Layer] | None = None) -> pdk.Deck:
    """Hotspots on top of background pictures (bottom first, e.g. [satellite photo, smoke])."""
    west, south, east, north = bbox
    outline = pd.DataFrame({"path": [[[west, south], [east, south], [east, north],
                                      [west, north], [west, south]]]})
    many = len(hotspots) > MAX_POINTS
    layers = [
        *(pictures or []),
        pdk.Layer("PathLayer", outline, get_path="path", get_color=[255, 255, 255, 180],
                  width_min_pixels=1),
        _cells_layer(hotspots) if many else _points_layer(hotspots),
    ]
    tooltip = ({"html": "<b>{hotspots}</b> hotspots in this area"} if many else
               {"html": "<b>{sensor}</b><br>{time_utc} UTC<br>{latitude}, {longitude}<br>"
                        "confidence: {confidence_level}<br>FRP: {frp} MW"})
    return pdk.Deck(layers=layers, initial_view_state=view_for(bbox), tooltip=tooltip,
                    map_style=pdk.map_styles.CARTO_DARK)
