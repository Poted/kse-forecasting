"""Wykresy Plotly dla dashboardu.

Kolory przypisane do serii na stałe (ta sama paleta co wykresy w `docs/fig`, sprawdzona
walidatorem palety): seria zawsze ma ten sam kolor, niezależnie od filtra. Wykonanie —
neutralna ciemna linia. Etykiety osi i legendy w kolorach tekstu.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
ACTUAL = "#3d3d3a"
TEXT_2 = "#52514e"
GRID = "#e4e3df"

SERIES_COLOR = {
    "LightGBM": PALETTE[0],
    "PSE (plan dobowy)": PALETTE[1],
    "naive D−1": PALETTE[2],
    "naive T−7": PALETTE[3],
    "wykonanie": ACTUAL,
}
MODEL_LABEL = {
    "lightgbm": "LightGBM",
    "net_demand_pse": "PSE (plan dobowy)",
    "naive_d1": "naive D−1",
    "naive_week": "naive T−7",
    "y": "wykonanie",
}


def _layout(fig: go.Figure, title: str, xaxis: str = "", yaxis: str = "MW") -> go.Figure:
    fig.update_layout(
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "y": 0.98,
            "yref": "container",
            "yanchor": "top",
        },
        template="plotly_white",
        hovermode="x unified",
        dragmode=False,  # bez przybliżania przeciąganiem (na telefonie blokowało przewijanie)
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 10, "r": 10, "t": 105, "b": 10},
        height=450,
        separators=", ",
    )
    fig.update_xaxes(title=xaxis, gridcolor=GRID, color=TEXT_2, fixedrange=True)
    fig.update_yaxes(title=yaxis, gridcolor=GRID, color=TEXT_2, tickformat=",.0f", fixedrange=True)
    return fig


def lines(
    frame: pd.DataFrame,
    title: str,
    xaxis: str = "",
    colors: dict | None = None,
    markers: bool = False,
) -> go.Figure:
    """Wykres liniowy: indeks = oś X, kolumny = serie."""
    colors = colors or {}
    fig = go.Figure()
    for i, col in enumerate(frame.columns):
        color = colors.get(col) or SERIES_COLOR.get(col) or PALETTE[i % len(PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[col],
                name=str(col),
                mode="lines+markers" if markers else "lines",
                line={"color": color, "width": 2},
                marker={"size": 8},
                hovertemplate="%{y:,.0f} MW<extra>" + str(col) + "</extra>",
            )
        )
    return _layout(fig, title, xaxis)


def forecast_chart(table: pd.DataFrame, title: str) -> go.Figure:
    """Prognoza na jutro: LightGBM, PSE (jeśli opublikowany), wykonanie (jeśli już znane)."""
    x = table["hour_utc"].dt.tz_convert("Europe/Warsaw").dt.strftime("%H:%M")
    frame = pd.DataFrame(index=x)
    for col in ("net_demand_hat", "net_demand_pse", "net_demand"):
        if col in table and table[col].notna().any():
            label = {
                "net_demand_hat": "LightGBM",
                "net_demand_pse": "PSE (plan dobowy)",
                "net_demand": "wykonanie",
            }[col]
            frame[label] = table[col].to_numpy()
    return lines(frame, title, "godzina (czas lokalny)", markers=True)


def by_group_mae(frame: pd.DataFrame, title: str, xaxis: str) -> go.Figure:
    return lines(
        frame.rename(columns=MODEL_LABEL | {"PSE": "PSE (plan dobowy)"}), title, xaxis, markers=True
    )


SEASON_COLORS = dict(zip(["zima", "wiosna", "lato", "jesień"], PALETTE, strict=True))
