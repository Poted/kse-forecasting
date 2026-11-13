"""P2.6: wykresy dashboardu, prognoza na jutro, uruchomienie dashboardu (AppTest)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from app import charts
from app.run import DASHBOARD
from p2 import forecast
from tests.test_p2_features import synthetic_actual, synthetic_weather


def test_lines_colors_follow_series_not_position():
    a = charts.lines(pd.DataFrame({"LightGBM": [1, 2], "wykonanie": [1, 1]}), "t")
    b = charts.lines(pd.DataFrame({"wykonanie": [1, 1], "LightGBM": [1, 2]}), "t")
    color = {t.name: t.line.color for t in a.data}
    assert color == {t.name: t.line.color for t in b.data}
    assert color["LightGBM"] == charts.SERIES_COLOR["LightGBM"]
    assert color["wykonanie"] == charts.ACTUAL


def test_forecast_chart_skips_empty_series():
    hours = pd.date_range("2026-11-13 23:00", periods=24, freq="h", tz="UTC")
    table = pd.DataFrame(
        {"hour_utc": hours, "net_demand_hat": 1.0, "net_demand_pse": np.nan, "net_demand": np.nan}
    )
    fig = charts.forecast_chart(table, "t")
    assert [t.name for t in fig.data] == ["LightGBM"]
    assert list(fig.data[0].x)[0] == "00:00"


def test_make_forecast_for_tomorrow(monkeypatch):
    from p2 import backtest

    monkeypatch.setattr(backtest, "FIRST_TRAIN_TARGET", date(2025, 5, 3))
    actual, weather = synthetic_actual(), synthetic_weather()
    d = date(2025, 7, 10)
    pse = actual[["hour_utc"]].assign(net_demand_pse=1.0)
    res, info = forecast.make_forecast(actual, weather, pse, d)
    assert res.target_date == d + timedelta(days=1)
    assert len(res.table) == 24 and res.table["lightgbm"].notna().all()
    assert info["train_to"] == str(d - timedelta(days=1))
    assert res.warnings == []
    # niekompletne wykonanie za D−1 → ostrzeżenie
    from p2 import features

    late = actual["hour_utc"] >= features.day_start_utc(d) - pd.Timedelta(hours=3)
    cut = actual[~(late & (actual["business_date"] == d - timedelta(days=1)))]
    res2, _ = forecast.make_forecast(cut, weather, pse, d)
    assert any("niekompletne" in w for w in res2.warnings)


@pytest.fixture
def db_schema():
    from common import db
    from common.config import load_settings

    try:
        engine = db.make_engine(load_settings().database_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Brak bazy PostgreSQL: {exc}")
    schema = "test_app_fc"
    with engine.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    db.init_schema(engine, schema)
    yield engine, schema
    with engine.begin() as conn:
        conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def test_save_forecast_db(db_schema):
    engine, schema = db_schema
    hours = pd.date_range("2025-07-10 22:00", periods=24, freq="h", tz="UTC")
    res = forecast.ForecastResult(
        date(2025, 7, 10),
        date(2025, 7, 11),
        pd.DataFrame({"hour_utc": hours, "hour_local": range(24), "lightgbm": 15000.0}),
        ["uwaga testowa"],
    )
    run_id = forecast.save_forecast(
        engine, res, {"train_to": "2025-07-09", "train_rows": 10}, schema
    )
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        run = conn.execute(sa.text("SELECT model, train_info FROM model_run")).one()
        n = conn.execute(
            sa.text("SELECT count(*) FROM p2_forecast WHERE run_id = :r"), {"r": run_id}
        ).scalar_one()
    assert run.model == forecast.OPERATIONAL_MODEL
    assert run.train_info["warnings"] == ["uwaga testowa"]
    assert n == 24


def test_dashboard_starts():
    """Dashboard uruchamia się bez wyjątków na danych z bazy (pomijany bez bazy)."""
    from streamlit.testing.v1 import AppTest

    from common import db
    from common.config import load_settings

    try:
        with db.make_engine(load_settings().database_url).connect() as conn:
            conn.execute(sa.text("SELECT 1 FROM v_wykonanie_h LIMIT 1"))
    except Exception as exc:
        pytest.skip(f"Brak bazy z danymi: {exc}")
    at = AppTest.from_file(str(DASHBOARD), default_timeout=180).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Prognoza na jutro", "Jakość prognoz", "Analiza"]
    assert at.button[0].label == "Przelicz prognozę na jutro"
