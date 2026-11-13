"""Metryki błędu prognoz zapotrzebowania netto.

Błąd = prognoza − wykonanie [MW] (dodatni: przeszacowanie).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(np.abs(y_pred - y_true)))


def rmse(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.sqrt(np.mean((y_pred - y_true) ** 2)))


def mape(y_true: pd.Series, y_pred: pd.Series) -> float:
    """Średni bezwzględny błąd procentowy [%]. Wymaga y_true ≠ 0."""
    if (y_true == 0).any():
        raise ValueError("MAPE niezdefiniowane dla wartości rzeczywistych równych 0")
    return float(np.mean(np.abs((y_pred - y_true) / y_true)) * 100)


def bias(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(y_pred - y_true))


def summary(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    return {
        "MAE": mae(y_true, y_pred),
        "RMSE": rmse(y_true, y_pred),
        "MAPE": mape(y_true, y_pred),
        "bias": bias(y_true, y_pred),
        "n": float(len(y_true)),
    }


def daily_extremes_error(
    df: pd.DataFrame,
    actual: str,
    forecast: str,
    day: str = "business_date",
    hour: str = "hour_local",
    midday: tuple[int, int] = (9, 16),
) -> pd.DataFrame:
    """Błąd w szczycie dobowym i w minimum południowym, dla każdej doby.

    Szczyt: godzina z maksymalnym wykonaniem w dobie. Minimum południowe: godzina
    z minimalnym wykonaniem w godzinach lokalnych [midday[0], midday[1]].
    Prognoza brana z tej samej godziny. Zwraca kolumny `peak_error`, `midday_min_error`.
    """
    rows = []
    for d, g in df.groupby(day):
        peak = g.loc[g[actual].idxmax()]
        mid = g[(g[hour] >= midday[0]) & (g[hour] <= midday[1])]
        rec = {day: d, "peak_error": peak[forecast] - peak[actual]}
        if not mid.empty:
            m = mid.loc[mid[actual].idxmin()]
            rec["midday_min_error"] = m[forecast] - m[actual]
        rows.append(rec)
    return pd.DataFrame(rows)
