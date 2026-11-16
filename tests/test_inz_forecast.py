"""Prognoza ryzyka na jutro (I5) i dane widoków inż — dane syntetyczne."""

import uuid
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from app import data_inz
from common import db
from common.config import load_settings
from inz import dataset, forecast, models
from p2 import features as p2f
from tests.test_inz_c2 import synthetic_rce
from tests.test_inz_models import synthetic_dataset

FIRST, D = date(2025, 4, 1), date(2025, 7, 10)
T = D + timedelta(days=1)


def synthetic_inputs(last=T, plan_for_target=True):
    """Tabele wejściowe `dataset.build_dataset` odtworzone ze zbioru syntetycznego."""
    data = synthetic_dataset(FIRST, last)
    day_start = data["business_date"].map(p2f.day_start_utc)
    plan = data[["dtime_utc", "business_date", *dataset.PLAN]].assign(
        publication_ts_utc=day_start - pd.Timedelta(hours=8)
    )
    if not plan_for_target:
        plan = plan[plan["business_date"] < last]
    hours = dataset.hour_of(data["dtime_utc"])
    p2 = (
        data.assign(hour_utc=hours)
        .groupby(["hour_utc", "business_date"], as_index=False)["p2_net_demand_hat"]
        .mean()
        .rename(columns={"business_date": "target_date", "p2_net_demand_hat": "net_demand_hat"})
    )
    p2["forecast_moment_utc"] = p2["target_date"].map(
        lambda t: p2f.forecast_moment_utc(t - timedelta(days=1))
    )
    t = pd.date_range(
        pd.Timestamp(FIRST - timedelta(days=1), tz="UTC"),
        pd.Timestamp(last + timedelta(days=2), tz="UTC"),
        freq="h",
    )
    rng = np.random.default_rng(3)
    weather = pd.DataFrame(
        {"time_utc": t} | {v: rng.uniform(1, 100, len(t)) for v in dataset.WEATHER}
    )
    known = data[data["business_date"] <= D - timedelta(days=1)]  # wykonanie do D−1
    redoze = pd.DataFrame(
        {
            "dtime_utc": data["dtime_utc"],
            "pv_red_balance": -data["pv_red_balance_mw"].where(data["pv_red_balance_mw"] > 0),
            "pv_red_network": np.nan,
            "publication_ts_utc": data["dtime_utc"],
        }
    )
    rce = synthetic_rce(data)
    rce = rce[rce["business_date"] <= D]  # RCE na D+1 jeszcze nieopublikowane
    actual = pd.DataFrame({"dtime_utc": known["dtime_utc"], "pv": known["gen_fv"] + 1.0})
    inputs = {
        "plan": plan,
        "p2_forecast": p2,
        "weather": weather,
        "redoze": redoze,
        "rce": rce[["dtime_utc", "rce_pln"]],
        "actual": actual,
    }
    return inputs, rce


@pytest.fixture
def fast_lgbm(monkeypatch):
    monkeypatch.setitem(models.LGBM_PARAMS, "n_estimators", 20)
    monkeypatch.setitem(models.LGBM_PARAMS, "learning_rate", 0.2)
    monkeypatch.setitem(models.LGBM_PARAMS, "n_jobs", 1)


def test_make_forecast_both_goals(fast_lgbm):
    inputs, rce = synthetic_inputs()
    res = forecast.make_forecast(inputs, rce, D)
    assert res.target_date == T and res.warnings == []
    c1, c2 = res.goals["c1"], res.goals["c2"]
    for fc in (c1, c2):
        assert len(fc.table) == 96 and (fc.table["business_date"] == T).all()
        assert fc.table["p_hat"].between(0, 1).all()
    # cel 1: trening tylko na dobach starszych niż opóźnienie publikacji ograniczeń
    assert c1.train_to == D - timedelta(days=forecast.LABEL_DELAY_DAYS)
    assert c1.params["regression"] and (c1.table["mw_hat"] >= 0).all()
    # cel 2: trening do D−1; doba D (cena znana, ale doba trwa) — tylko jako cecha
    assert c2.train_to == D - timedelta(days=1)
    assert (c2.table["mw_hat"] == 0).all()


def test_goal_1_skipped_before_plan_publication(fast_lgbm):
    inputs, rce = synthetic_inputs(plan_for_target=False)
    res = forecast.make_forecast(inputs, rce, D)
    assert list(res.goals) == ["c2"]
    assert any("Plan PSE" in w for w in res.warnings)


def test_missing_p2_forecast_gives_warning(fast_lgbm):
    inputs, rce = synthetic_inputs()
    inputs["p2_forecast"] = inputs["p2_forecast"][inputs["p2_forecast"]["target_date"] < T]
    res = forecast.make_forecast(inputs, rce, D)
    assert "c2" not in res.goals  # cechy celu 2 wymagają prognozy P2
    assert any("Brak prognozy P2" in w for w in res.warnings)


def test_risk_periods():
    ends = pd.date_range("2026-06-14 22:15", periods=96, freq="15min", tz="UTC")
    p = np.zeros(96)
    p[40:44] = 0.9  # 10:00–11:00 czasu lokalnego (lato: UTC+2)
    p[95] = 0.8
    table = pd.DataFrame({"dtime_utc": ends, "p_hat": p})
    assert data_inz.risk_periods(table, 0.5) == [("10:00", "11:00"), ("23:45", "00:00")]
    assert data_inz.risk_periods(table, 0.95) == []


def test_episodes_summary():
    ends = pd.date_range("2026-06-14 22:15", periods=192, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "dtime_utc": ends,
            "business_date": [date(2026, 6, 15)] * 96 + [date(2026, 6, 16)] * 96,
            "pv_red_balance_mw": [0.0] * 40 + [400.0] * 8 + [0.0] * 144,
            "y_red_balance": [0.0] * 40 + [1.0] * 8 + [0.0] * 144,
            "y_rce_neg": [0.0] * 44 + [1.0] * 4 + [0.0] * 144,
            "rce_pln": [300.0] * 44 + [-20.0] * 4 + [300.0] * 144,
            "mw_c1": [np.nan] * 96 + [10.0] * 96,
            "p_c1": [np.nan] * 96 + [0.2] * 96,
        }
    )
    table = data_inz.episodes(frame)
    assert list(table["business_date"]) == [date(2026, 6, 15)]  # tylko doby z ograniczeniem
    row = table.iloc[0]
    assert row["energia_mwh"] == 800.0 and row["maks_mw"] == 400.0 and row["kwadranse"] == 8
    assert row["kwadranse_rce_ujemne"] == 4 and row["rce_min"] == -20.0
    assert np.isnan(row["prognoza_mwh"])  # brak prognozy dla tej doby
    assert data_inz.episodes(frame.iloc[0:0]).empty


# --- z bazą -----------------------------------------------------------------


@pytest.fixture
def engine_schema():
    try:
        engine = db.make_engine(load_settings().database_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Brak bazy PostgreSQL: {exc}")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield engine, schema
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_save_forecast_and_recent_dataset(engine_schema, fast_lgbm):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    inputs, rce = synthetic_inputs()
    res = forecast.make_forecast(inputs, rce, D)
    run_ids = forecast.save_forecast(engine, res, schema)
    assert set(run_ids) == {"c1", "c2"}
    n = dataset.save_recent(engine, res.data, D - timedelta(days=5), schema)
    assert n == 7 * 96  # doby D−5 … D+1
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        runs = pd.read_sql(sa.text("SELECT * FROM model_run ORDER BY run_id"), conn)
        preds = pd.read_sql(
            sa.text("SELECT run_id, count(*) n FROM inz_prediction GROUP BY 1"), conn
        )
        stored = pd.read_sql(
            sa.text("SELECT count(*) n, max(business_date) d FROM inz_dataset"), conn
        )
    assert set(runs["model"]) == set(forecast.OPERATIONAL.values())
    info = runs.iloc[0]["train_info"]
    assert info["forecast_date"] == str(D) and info["target_date"] == str(T)
    c1 = runs[runs["model"] == forecast.OPERATIONAL["c1"]].iloc[0]
    assert c1["params"]["threshold"] is None  # brak eksperymentu w pustym schemacie
    assert (preds["n"] == 96).all() and stored["n"].iloc[0] == 7 * 96 and stored["d"].iloc[0] == T
