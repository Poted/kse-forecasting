"""Cechy modelu zapotrzebowania netto z kontrolą momentu dostępności informacji.

Prognoza wykonywana w dniu D o 12:00 (czas lokalny) na wszystkie godziny doby T = D+1
(23, 24 lub 25 godzin). Dostępne w chwili prognozy (`context/00_fundament.md` sekcja 3,
decyzje 13.11):
- wykonanie KSE: pełne doby do D−1 włącznie (godziny o `hour_utc` < początek doby D),
- pogoda Open-Meteo `_previous_day2`: wartość dla godziny t wydana 48 h wcześniej;
  używana tylko, jeśli t − 48 h ≤ moment prognozy,
- kalendarz.
Plan dobowy PSE (publikowany ok. 16:00 dnia D) NIE jest cechą — tylko benchmark.

Każda doba prognozy budowana jest funkcją `build_day`, która sama odcina dane niedostępne
w chwili prognozy. Test braku przecieku: `tests/test_p2_features.py`.
"""

from __future__ import annotations

from datetime import date, timedelta

import holidays
import numpy as np
import pandas as pd

TZ = "Europe/Warsaw"
FORECAST_HOUR = 12  # godzina lokalna wykonania prognozy w dniu D
WEATHER_LEAD = pd.Timedelta(hours=48)  # _previous_day2
WEATHER_VARS = ("shortwave_radiation", "cloud_cover", "temperature_2m", "wind_speed_100m")

PL_HOLIDAYS = holidays.Poland(years=range(2023, 2031))

LAG_DAYS = (2, 3, 7, 14)  # względem doby docelowej T; T−2 = D−1 (ostatnia pełna doba)
FEATURES = [
    "hour_local",
    "dow",
    "month",
    "doy_sin",
    "doy_cos",
    "is_holiday",
    "is_weekend",
    *[f"net_lag{k}" for k in LAG_DAYS],
    "demand_lag2",
    "pv_lag2",
    "net_mean7",
    "net_daymean_lag2",
    *WEATHER_VARS,
    "rad_day_mean",
]


def day_start_utc(d: date) -> pd.Timestamp:
    return pd.Timestamp(d).tz_localize(TZ).tz_convert("UTC")


def forecast_moment_utc(d: date) -> pd.Timestamp:
    """Moment prognozy: dzień D, 12:00 czasu lokalnego, w UTC."""
    return (pd.Timestamp(d) + pd.Timedelta(hours=FORECAST_HOUR)).tz_localize(TZ).tz_convert("UTC")


def target_hours(t: date) -> pd.DataFrame:
    """Godziny doby handlowej T (UTC, początek godziny) i godzina lokalna."""
    hours = pd.date_range(
        day_start_utc(t), day_start_utc(t + timedelta(days=1)), freq="h", inclusive="left"
    )
    return pd.DataFrame({"hour_utc": hours, "hour_local": hours.tz_convert(TZ).hour})


def available_actuals(actual: pd.DataFrame, d: date) -> pd.DataFrame:
    """Wykonanie dostępne w chwili prognozy w dniu D: doby do D−1 włącznie."""
    return actual[actual["hour_utc"] < day_start_utc(d)]


def available_weather(weather: pd.DataFrame, d: date) -> pd.DataFrame:
    """Pogoda dostępna w chwili prognozy: wydana (time_utc − 48 h) najpóźniej o 12:00 dnia D."""
    return weather[weather["time_utc"] - WEATHER_LEAD <= forecast_moment_utc(d)]


def _by_day_hour(actual: pd.DataFrame, column: str) -> pd.DataFrame:
    """Tabela doba × godzina lokalna. Doba 25 h: średnia z powtórzonej godziny;
    doba 23 h: brakująca godzina interpolowana z sąsiednich."""
    local_hour = actual["hour_utc"].dt.tz_convert(TZ).dt.hour
    table = actual.assign(h=local_hour).pivot_table(
        index="business_date", columns="h", values=column, aggfunc="mean"
    )
    table = table.reindex(columns=range(24))
    return table.interpolate(axis=1, limit_area="inside")


def _weather_for_hours(weather: pd.DataFrame, hours: pd.Series) -> pd.DataFrame:
    """Pogoda dla godzin [t, t+1): promieniowanie — znacznik t+1 h (średnia z godziny
    poprzedzającej znacznik); zmienne chwilowe — średnia ze znaczników t i t+1 h."""
    w = weather.set_index("time_utc")
    nxt = hours + pd.Timedelta(hours=1)
    out = pd.DataFrame(index=hours.index)
    out["shortwave_radiation"] = w["shortwave_radiation"].reindex(nxt).to_numpy()
    for v in ("cloud_cover", "temperature_2m", "wind_speed_100m"):
        out[v] = (w[v].reindex(hours).to_numpy() + w[v].reindex(nxt).to_numpy()) / 2
    return out


def build_day(d: date, actual: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Cechy dla wszystkich godzin doby T = D+1, z prognozy wykonanej w dniu D o 12:00.

    `actual`: kolumny `hour_utc`, `business_date`, `net_demand`, `demand`, `pv` (pełne godziny).
    `weather`: kolumny `time_utc` i zmienne pogodowe (średnia z punktów).
    """
    t = d + timedelta(days=1)
    rows = target_hours(t)
    rows.insert(0, "target_date", t)
    rows.insert(1, "forecast_date", d)

    act = available_actuals(actual, d)
    act = act[act["business_date"] >= t - timedelta(days=max(LAG_DAYS) + 7)]
    net = _by_day_hour(act, "net_demand")
    demand = _by_day_hour(act, "demand")
    pv = _by_day_hour(act, "pv")

    def lag(table: pd.DataFrame, k: int) -> np.ndarray:
        day = t - timedelta(days=k)
        if day not in table.index:
            return np.full(len(rows), np.nan)
        return table.loc[day].reindex(rows["hour_local"]).to_numpy()

    for k in LAG_DAYS:
        rows[f"net_lag{k}"] = lag(net, k)
    rows["demand_lag2"] = lag(demand, 2)
    rows["pv_lag2"] = lag(pv, 2)
    last7 = [t - timedelta(days=k) for k in range(2, 9)]
    rows["net_mean7"] = net.reindex(last7).mean().reindex(rows["hour_local"]).to_numpy()
    day2 = t - timedelta(days=2)
    rows["net_daymean_lag2"] = float(net.loc[day2].mean()) if day2 in net.index else np.nan

    wx = _weather_for_hours(available_weather(weather, d), rows["hour_utc"])
    for v in WEATHER_VARS:
        rows[v] = wx[v].to_numpy()
    rows["rad_day_mean"] = rows["shortwave_radiation"].mean()

    ts = pd.Timestamp(t)
    rows["dow"] = ts.day_of_week
    rows["month"] = ts.month
    rows["doy_sin"] = np.sin(2 * np.pi * ts.day_of_year / 365.25)
    rows["doy_cos"] = np.cos(2 * np.pi * ts.day_of_year / 365.25)
    rows["is_holiday"] = int(t in PL_HOLIDAYS)
    rows["is_weekend"] = int(ts.day_of_week >= 5)
    return rows


def build_dataset(
    actual: pd.DataFrame, weather: pd.DataFrame, first_target: date, last_target: date
) -> pd.DataFrame:
    """Cechy dla dób docelowych [first_target, last_target] + wartość rzeczywista (`y`)."""
    days = pd.date_range(first_target, last_target, freq="D").date
    frames = [build_day(t - timedelta(days=1), actual, weather) for t in days]
    data = pd.concat(frames, ignore_index=True)
    y = actual[["hour_utc", "net_demand"]].rename(columns={"net_demand": "y"})
    return data.merge(y, on="hour_utc", how="left")
