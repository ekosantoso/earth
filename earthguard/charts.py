"""Plotly figures. Each function takes plain tables and returns a figure."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from earthguard import burn_calendar
from earthguard.config import (COLOR_HARMONIZED, COLOR_MODIS, COLOR_MUTED, COLOR_UNUSUAL,
                               COLOR_VIIRS, HEAT_SCALE, MODIS, OVERLAP_YEARS, VIIRS,
                               VIIRS_FIRST_YEAR)
from earthguard.ui import MONTH_NAMES

LAYOUT = dict(
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#E5E7EB"),
    margin=dict(l=10, r=10, t=40, b=10), hoverlabel=dict(font_family="JetBrains Mono, monospace"),
)
HEAT_COLORSCALE = [[i / (len(HEAT_SCALE) - 1), c] for i, c in enumerate(HEAT_SCALE)]


def calendar_heatmap(monthly: pd.DataFrame, season: tuple[int, int] | None) -> go.Figure:
    """Years (rows) x months (columns). Unusual months get a white outline.

    Underneath: a typical year, with the fire-season months in red.
    """
    flags = burn_calendar.unusual(monthly)
    ratio = burn_calendar.times_typical(monthly)
    profile = burn_calendar.typical(monthly)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2],
                        vertical_spacing=0.03)
    fig.add_trace(go.Heatmap(
        z=monthly.to_numpy(), x=MONTH_NAMES, y=monthly.index, customdata=ratio.to_numpy(),
        colorscale=HEAT_COLORSCALE, zmin=0, xgap=1, ygap=1,
        hovertemplate="<b>%{x} %{y}</b><br>%{customdata:.1f}× a normal %{x}<extra></extra>",
        colorbar=dict(title=dict(text="burning", side="right"), thickness=10, len=0.75, y=0.62),
    ), row=1, col=1)

    years, months = np.nonzero(flags.to_numpy())
    fig.add_trace(go.Scatter(
        x=[MONTH_NAMES[m] for m in months], y=monthly.index[years], mode="markers",
        marker=dict(symbol="square-open", size=14, color="white", line=dict(width=2)),
        hoverinfo="skip",
    ), row=1, col=1)

    fig.add_hline(y=VIIRS_FIRST_YEAR - 0.5, line=dict(color="white", dash="dot", width=1),
                  annotation_text="VIIRS joins — harmonized from here",
                  annotation_position="bottom right", row=1, col=1)

    # A month is part of the fire season if any of its weeks is.
    season_weeks = set(burn_calendar.weeks_in(season)) if season else set()
    colors = [COLOR_UNUSUAL if season_weeks & set(range((m - 1) * 52 // 12 + 1, m * 52 // 12 + 1))
              else COLOR_MUTED for m in range(1, 13)]
    fig.add_trace(go.Bar(x=MONTH_NAMES, y=profile.to_numpy(), marker_color=colors,
                         hovertemplate="normal %{x}: %{y:,.0f}<extra></extra>"), row=2, col=1)

    fig.update_yaxes(autorange="reversed", dtick=2, row=1, col=1)
    fig.update_yaxes(title_text="normal year", showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=True, side="top", row=1, col=1)
    fig.update_layout(**LAYOUT, height=700, showlegend=False)
    return fig


def harmonization_lines(monthly_table: pd.DataFrame, harmonized: pd.Series) -> go.Figure:
    """Raw MODIS, raw VIIRS and the harmonized record on one chart."""
    fig = go.Figure()
    for name, series, color, width in [(f"{MODIS} (raw)", monthly_table[MODIS], COLOR_MODIS, 1.5),
                                       (f"{VIIRS} (raw)", monthly_table[VIIRS], COLOR_VIIRS, 1.5),
                                       ("Harmonized", harmonized, COLOR_HARMONIZED, 3)]:
        fig.add_trace(go.Scatter(x=series.index, y=series, name=name,
                                 line=dict(color=color, width=width)))
    first, last = OVERLAP_YEARS
    fig.add_vrect(x0=f"{first}-01-01", x1=f"{last}-12-31", fillcolor="white", opacity=0.05,
                  line_width=0, annotation_text="Both satellites (used to calibrate)",
                  annotation_position="top left")
    fig.update_layout(**LAYOUT, height=380, yaxis_title="burning per month",
                      legend=dict(orientation="h", y=-0.2))
    return fig
