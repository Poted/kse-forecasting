"""Cechy P2 i test braku przecieku informacji (dane syntetyczne, bez bazy)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from p2 import backtest, features

START = date(2025, 5, 1)
END = date(2025, 7, 15)


def synthetic_actual(start=START, end=END) -> pd.DataFrame:
    hours = pd.date_range(
        features.day_start_utc(start),
        features.day_start_utc(end + timedelta(days=1)),
        freq="h",
        inclusive="left",
    )
    local = hours.tz_convert(features.TZ)
    rng = np.random.default_rng(0)
    demand = 18000 + 2000 * np.sin(2 * np.pi * local.hour / 24) + rng.normal(0, 100, len(hours))
    pv = np.clip(6000 * np.sin(np.pi * (local.hour - 5) / 15), 0, None)
    return pd.DataFrame(
        {
            "hour_utc": hours,
            "business_date": local.date,
            "demand": demand,
            "pv": pv,
            "net_demand": demand - pv,
        }
    )


def synthetic_weather(start=START, end=END) -> pd.DataFrame:
    t = pd.date_range(
        pd.Timestamp(start - timedelta(days=1), tz="UTC"),
        pd.Timestamp(end + timedelta(days=2), tz="UTC"),
        freq="h",
    )
    return pd.DataFrame(
        {
            "time_utc": t,
            "shortwave_radiation": np.arange(len(t), dtype=float),
            "cloud_cover": 50.0,
            "temperature_2m": 20.0 + np.arange(len(t)) % 7,
            "wind_speed_100m": 10.0,
        }
    )


def test_target_hours_dst():
    assert len(features.target_hours(date(2025, 3, 30))) == 23
    assert len(features.target_hours(date(2025, 10, 26))) == 25
    th = features.target_hours(date(2025, 6, 15))
    assert len(th) == 24 and th["hour_local"].tolist() == list(range(24))
    assert th["hour_utc"].iloc[0] == pd.Timestamp("2025-06-14 22:00", tz="UTC")


def test_forecast_moment_is_noon_local():
    assert features.forecast_moment_utc(date(2025, 6, 14)) == pd.Timestamp(
        "2025-06-14 10:00", tz="UTC"
    )
    assert features.forecast_moment_utc(date(2025, 12, 14)) == pd.Timestamp(
        "2025-12-14 11:00", tz="UTC"
    )


def test_no_pse_plan_in_features():
    assert not [f for f in features.FEATURES if "pse" in f or "kse_pow" in f or "gen_fv" in f]


@pytest.mark.parametrize("d", [date(2025, 6, 10), date(2025, 7, 1)])
def test_no_leakage(d):
    """Zmiana wszystkich danych niedostępnych o 12:00 dnia D nie zmienia cech prognozy."""
    actual, weather = synthetic_actual(), synthetic_weather()
    base = features.build_day(d, actual, weather)

    cut_actual = features.day_start_utc(d)
    moment = features.forecast_moment_utc(d)
    a2, w2 = actual.copy(), weather.copy()
    late_a = a2["hour_utc"] >= cut_actual
    a2.loc[late_a, ["demand", "pv", "net_demand"]] *= 10  # wykonanie z doby D i później
    late_w = w2["time_utc"] - features.WEATHER_LEAD > moment
    w2.loc[late_w, list(features.WEATHER_VARS)] *= 10  # pogoda wydana po 12:00 dnia D
    assert late_a.sum() > 0 and late_w.sum() > 0

    pd.testing.assert_frame_equal(base, features.build_day(d, a2, w2))


def test_available_data_is_used():
    """Kontrola czułości: dane dostępne (D−1, pogoda wydana przed 12:00) zmieniają cechy."""
    d = date(2025, 6, 10)
    actual, weather = synthetic_actual(), synthetic_weather()
    base = features.build_day(d, actual, weather)
    a2 = actual.copy()
    a2.loc[a2["business_date"] == d - timedelta(days=1), "net_demand"] += 500
    assert (features.build_day(d, a2, weather)["net_lag2"] - base["net_lag2"]).eq(500).all()
    w2 = weather.copy()
    w2["temperature_2m"] += 1
    assert not features.build_day(d, actual, w2)["temperature_2m"].equals(base["temperature_2m"])
    assert base[features.FEATURES].notna().all().all()


def test_radiation_uses_preceding_hour_convention():
    d = date(2025, 6, 10)
    weather = synthetic_weather()
    rows = features.build_day(d, synthetic_actual(), weather)
    w = weather.set_index("time_utc")
    first = rows.iloc[0]
    assert (
        first["shortwave_radiation"]
        == w.loc[first["hour_utc"] + pd.Timedelta(hours=1), "shortwave_radiation"]
    )


def test_lags_same_local_hour():
    d = date(2025, 6, 10)
    actual = synthetic_actual()
    rows = features.build_day(d, actual, synthetic_weather())
    t = d + timedelta(days=1)
    src = actual[actual["business_date"] == t - timedelta(days=7)]
    src = src.set_index(src["hour_utc"].dt.tz_convert(features.TZ).dt.hour)
    assert rows.loc[5, "net_lag7"] == pytest.approx(src.loc[5, "net_demand"])


def test_monthly_blocks():
    assert backtest.monthly_blocks(date(2024, 9, 27), date(2024, 11, 3)) == [
        (date(2024, 9, 27), date(2024, 9, 30)),
        (date(2024, 10, 1), date(2024, 10, 31)),
        (date(2024, 11, 1), date(2024, 11, 3)),
    ]


def test_backtest_trains_only_on_known_days(monkeypatch):
    monkeypatch.setattr(backtest, "FIRST_TRAIN_TARGET", date(2025, 5, 3))
    actual, weather = synthetic_actual(), synthetic_weather()
    pse = actual[["hour_utc"]].assign(net_demand_pse=actual["net_demand"] + 100)
    res = backtest.run_backtest(actual, weather, pse, date(2025, 6, 20), date(2025, 7, 10))
    for block in res.train_info:
        first_forecast_day = date.fromisoformat(block["test_from"]) - timedelta(days=1)
        assert date.fromisoformat(block["train_to"]) <= first_forecast_day - timedelta(days=1)
    fc = res.forecasts
    assert fc[list(backtest.MODELS)].notna().all().all()
    table = backtest.evaluate(fc)
    assert table.loc["PSE (plan dobowy)", "MAE"] == pytest.approx(100)
    assert set(table.index) == {"naive_d1", "naive_week", "lightgbm", "PSE (plan dobowy)"}
