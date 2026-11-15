from datetime import date

import numpy as np
import pandas as pd
import pytest

from p2 import analysis, metrics


def test_metrics_values():
    y = pd.Series([100.0, 200.0, 400.0])
    p = pd.Series([110.0, 180.0, 400.0])
    assert metrics.mae(y, p) == pytest.approx(10.0)
    assert metrics.rmse(y, p) == pytest.approx(np.sqrt((100 + 400) / 3))
    assert metrics.mape(y, p) == pytest.approx((10 + 10 + 0) / 3)
    assert metrics.bias(y, p) == pytest.approx(-10 / 3)
    with pytest.raises(ValueError):
        metrics.mape(pd.Series([0.0]), pd.Series([1.0]))


def hourly_frame(days: int = 3, start: str = "2026-06-01") -> pd.DataFrame:
    """Syntetyczne godziny w UTC dla dób lokalnych; netto z dołkiem w południe."""
    rows = []
    for d in pd.date_range(start, periods=days, freq="D"):
        local = pd.date_range(d, periods=24, freq="h", tz="Europe/Warsaw")
        for t in local:
            h = t.hour
            pv = max(0.0, 8000 - 800 * abs(h - 12))
            demand = 18000.0 + 100 * h
            rows.append(
                {
                    "hour_utc": t.tz_convert("UTC"),
                    "business_date": d.date(),
                    "demand": demand,
                    "pv": pv,
                    "net_demand": demand - pv,
                    "kse_pow_dem": demand + 100,
                    "gen_fv": pv,
                    "net_demand_pse": demand + 100 - pv,
                }
            )
    return analysis.add_calendar(pd.DataFrame(rows))


def test_add_calendar_local_hour_and_season():
    df = hourly_frame(1)
    assert df["hour_local"].tolist() == list(range(24))
    assert (df["season"] == "lato").all()
    assert df["month"].iloc[0] == pd.Period("2026-06", "M")


def test_daily_profile_and_duck_depth():
    df = hourly_frame(3)
    prof = analysis.daily_profile(df, "season")
    assert prof.loc[12, "lato"] == pytest.approx(18000 + 1200 - 8000)
    duck = analysis.duck_depth(df)
    # min w 9–16: godzina 12 (11 200); max w 17–22: godzina 22 (20 200, pv = 0)
    assert duck["midday_min"].iloc[0] == pytest.approx(11200)
    assert duck["evening_max"].iloc[0] == pytest.approx(20200)
    assert duck["depth"].iloc[0] == pytest.approx(9000)


def test_pse_errors_and_summary():
    df = hourly_frame(2)
    err = analysis.pse_errors(df)
    assert (err["err_net"] == 100).all()
    summary = analysis.pse_summary(err)
    assert summary.loc["netto", "MAE"] == pytest.approx(100)
    assert summary.loc["netto", "bias"] == pytest.approx(100)
    assert summary.loc["PV", "MAE"] == pytest.approx(0)
    assert summary.loc["netto — szczyt dobowy", "n"] == 2
    by_hour = analysis.error_by(err, "hour_local")
    assert len(by_hour) == 24 and (by_hour["MAE"] == 100).all()


def test_daily_extremes_error_picks_actual_extremes():
    df = pd.DataFrame(
        {
            "business_date": [date(2026, 6, 1)] * 4,
            "hour_local": [10, 12, 14, 20],
            "a": [9000.0, 8000.0, 9500.0, 19000.0],
            "f": [9100.0, 8300.0, 9400.0, 18800.0],
        }
    )
    ext = metrics.daily_extremes_error(df, "a", "f")
    assert ext["peak_error"].iloc[0] == pytest.approx(-200)
    assert ext["midday_min_error"].iloc[0] == pytest.approx(300)


def test_render_all_writes_files(tmp_path):
    from p2 import plots

    df = pd.concat([hourly_frame(3, "2025-06-01"), hourly_frame(3, "2026-06-01")])
    tables = plots.render_all(df, tmp_path)
    assert len(list(tmp_path.glob("*.png"))) == 7
    assert (tmp_path / "p2_4_tabele.md").exists()
    assert list(tables["kaczka_czerwiec"].columns) == [2025, 2026]


def test_evaluate_rmse_not_below_mae():
    from tests.test_p2_features import synthetic_actual

    a = synthetic_actual(date(2025, 6, 1), date(2025, 6, 10))
    rng = np.random.default_rng(1)
    fc = pd.DataFrame(
        {
            "target_date": a["business_date"],
            "hour_utc": a["hour_utc"],
            "hour_local": a["hour_utc"].dt.tz_convert("Europe/Warsaw").dt.hour,
            "y": a["net_demand"],
        }
    )
    for i, col in enumerate(["naive_d1", "naive_week", "lightgbm", "net_demand_pse"]):
        fc[col] = fc["y"] + rng.normal(0, 100 * (i + 1), len(fc))
    from p2 import backtest

    t = backtest.evaluate(fc)
    assert (t["RMSE"] >= t["MAE"]).all()
    assert t.loc["PSE (plan dobowy)", "MAE"] == pytest.approx(
        (fc["net_demand_pse"] - fc["y"]).abs().mean()
    )
