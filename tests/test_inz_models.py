"""Modele celu 1 (I2): modele bazowe, LightGBM, metryki, schematy walidacji (dane syntetyczne)."""

import uuid
from datetime import date

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from common import db
from common.config import load_settings
from inz import dataset, evaluate, experiment, models

TARGET = models.TARGETS["balance"]
FIRST, LAST = date(2025, 1, 1), date(2026, 3, 31)


def synthetic_dataset(first=FIRST, last=LAST, seed=0) -> pd.DataFrame:
    """Zbiór o strukturze `inz_dataset`: ograniczenie, gdy zapotrzebowanie − PV − wiatr < 9 GW."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in pd.date_range(first, last, freq="D").date:
        q = dataset.quarters(d)
        q.insert(1, "business_date", d)
        ts = pd.Timestamp(d)
        q["dow"], q["month"] = ts.day_of_week, ts.month
        q["doy_sin"] = np.sin(2 * np.pi * ts.day_of_year / 365.25)
        q["doy_cos"] = np.cos(2 * np.pi * ts.day_of_year / 365.25)
        q["is_holiday"], q["is_weekend"] = 0, int(ts.day_of_week >= 5)
        sun = np.clip(np.sin(np.pi * (q["quarter_local"] - 24) / 48), 0, None)
        q["gen_fv"] = sun * rng.uniform(2000, 12000)
        q["gen_wi"] = rng.uniform(500, 6000)
        q["kse_pow_dem"] = 18000 + 2000 * np.sin(2 * np.pi * q["quarter_local"] / 96)
        frames.append(q)
    df = pd.concat(frames, ignore_index=True)
    n = len(df)
    for col in ("rez_under", "rez_over_demand", "dom_balance_exchange_non_par", "ogr_mwe"):
        df[col] = rng.uniform(0, 1000, n)
    df["dom_balance_exchange_par"] = rng.uniform(-500, 500, n)
    df["gen_jgw_jgm_jgz_jga"] = rng.uniform(5000, 9000, n)
    df["p2_net_demand_hat"] = df["kse_pow_dem"] - df["gen_fv"] + rng.normal(0, 300, n)
    for col in dataset.WEATHER:
        df[col] = rng.uniform(0, 100, n)
    res = df["kse_pow_dem"] - df["gen_fv"] - df["gen_wi"] + rng.normal(0, 300, n)
    df["pv_red_balance_mw"] = np.where(df["gen_fv"] > 0, np.clip(9000 - res, 0, None), 0.0)
    df["y_red_balance"] = (df["pv_red_balance_mw"] > 0).astype("Int64")
    df["pv_red_network_mw"] = 0.0
    df["y_red_network"] = pd.array([0] * n, dtype="Int64")
    return df


@pytest.fixture(scope="module")
def data():
    return synthetic_dataset()


@pytest.fixture
def fast_lgbm(monkeypatch):
    monkeypatch.setitem(models.LGBM_PARAMS, "n_estimators", 20)
    monkeypatch.setitem(models.LGBM_PARAMS, "learning_rate", 0.2)
    monkeypatch.setitem(models.LGBM_PARAMS, "n_jobs", 1)


# --- cechy -------------------------------------------------------------------


def test_model_features_have_no_targets_or_actuals():
    forbidden = {*dataset.TARGETS, "rce_pln", "red_pv0_anomaly", "pv", "demand", "wi"}
    assert not forbidden & set(models.FEATURES)
    assert set(dataset.FEATURES_C1) < set(models.FEATURES)


def test_add_derived(data):
    df = models.add_derived(data)
    row = df.iloc[50]
    assert row["res_load"] == row["kse_pow_dem"] - row["gen_fv"] - row["gen_wi"]
    assert row["res_load_exch"] == row["res_load"] + row["dom_balance_exchange_par"]
    assert row["pv_share"] == row["gen_fv"] / row["kse_pow_dem"]
    day = df[df["business_date"] == row["business_date"]]
    assert (day["res_load_day_min"] == day["res_load"].min()).all()
    assert (day["gen_fv_day_max"] == day["gen_fv"].max()).all()
    # agregaty dobowe tylko z własnej doby: zmiana innej doby ich nie zmienia
    other = data.copy()
    other.loc[other["business_date"] != row["business_date"], "gen_fv"] *= 2
    day2 = models.add_derived(other)
    day2 = day2[day2["business_date"] == row["business_date"]]
    assert np.array_equal(day2["gen_fv_day_max"], day["gen_fv_day_max"])


# --- modele ------------------------------------------------------------------


def test_calendar_baseline_frequencies_and_fallback(data):
    df = experiment.prepare(data, TARGET)
    train = df[df["business_date"] <= date(2025, 6, 30)]
    model = models.CalendarBaseline().fit(train, TARGET)
    cell = train[(train["month"] == 6) & (train["quarter_local"] == 48)]
    june = df[(df["business_date"] == date(2025, 6, 10)) & (df["quarter_local"] == 48)]
    out = model.predict(june)
    assert out["p_hat"].iloc[0] == pytest.approx(cell["y_red_balance"].mean())
    assert out["mw_hat"].iloc[0] == pytest.approx(cell["pv_red_balance_mw"].mean())
    # miesiąc spoza treningu (wrzesień): średnia wg kwadransu doby
    sept = df[(df["business_date"] == date(2025, 9, 10)) & (df["quarter_local"] == 48)]
    expected = train.loc[train["quarter_local"] == 48, "y_red_balance"].mean()
    assert model.predict(sept)["p_hat"].iloc[0] == pytest.approx(expected)
    assert model.predict(df[df["quarter_local"] == 0])["p_hat"].max() == 0.0  # noc


def test_plan_rule_is_monotone_and_zero_without_pv(data):
    df = experiment.prepare(data, TARGET)
    model = models.PlanRuleBaseline().fit(df, TARGET)
    grid = pd.DataFrame({"res_load": np.linspace(0, 20000, 50), "gen_fv": 1.0})
    out = model.predict(grid)
    assert (np.diff(out["p_hat"]) <= 0).all() and (np.diff(out["mw_hat"]) <= 0).all()
    assert out["p_hat"].iloc[0] > 0.9 and out["p_hat"].iloc[-1] < 0.1
    night = model.predict(grid.assign(gen_fv=0.0))
    assert (night["p_hat"] == 0).all() and (night["mw_hat"] == 0).all()


@pytest.mark.parametrize("cls", [models.LightGBMModel, models.LightGBMTwoStage])
def test_lightgbm_learns_synthetic_rule(data, fast_lgbm, cls):
    df = experiment.prepare(data, TARGET)
    train = df[df["business_date"] <= date(2025, 12, 31)]
    test = df[df["business_date"] > date(2025, 12, 31)]
    out = cls().fit(train, TARGET).predict(test)
    assert out["p_hat"].between(0, 1).all() and (out["mw_hat"] >= 0).all()
    m = evaluate.metrics(
        test["y_red_balance"], test["pv_red_balance_mw"], out["p_hat"], out["mw_hat"], 0.5
    )
    assert m["AUC"] > 0.95 and m["MAE"] < test["pv_red_balance_mw"].mean()


# --- metryki -----------------------------------------------------------------


def test_metrics_and_threshold():
    y = np.array([0, 0, 0, 1, 1, 1])
    p = np.array([0.1, 0.2, 0.6, 0.5, 0.8, 0.9])
    mw = np.array([0, 0, 0, 100, 200, 300.0])
    m = evaluate.metrics(y, mw, p, mw + 10, threshold=0.55)
    assert m["precyzja"] == pytest.approx(2 / 3) and m["czułość"] == pytest.approx(2 / 3)
    assert m["F1"] == pytest.approx(2 / 3)
    assert m["AUC"] == pytest.approx(8 / 9)
    assert m["MAE"] == pytest.approx(10) and m["MAE_ogr"] == pytest.approx(10)
    assert m["n"] == 6 and m["n_ogr"] == 3
    # najlepszy próg: 0,5 → 3 trafienia, 1 fałszywy alarm (F1 = 6/7)
    assert evaluate.best_f1_threshold(y, p) == 0.5
    single = evaluate.metrics(np.zeros(4), np.zeros(4), np.full(4, 0.1), np.zeros(4), 0.5)
    assert np.isnan(single["AUC"]) and single["F1"] == 0.0 and np.isnan(single["MAE_ogr"])


# --- schematy walidacji ------------------------------------------------------


def test_walk_cutoff_is_end_of_month_minus_two():
    assert experiment.walk_cutoff(date(2026, 1, 1)) == date(2025, 11, 30)
    assert experiment.walk_cutoff(date(2026, 3, 1)) == date(2026, 1, 31)
    assert experiment.walk_cutoff(date(2026, 3, 17)) == date(2026, 1, 31)


def test_prepare_keeps_only_complete_days(data):
    part = data.copy()
    part["y_red_balance"] = part["y_red_balance"].astype("Int64")
    last = part["business_date"] == LAST
    part.loc[last & (part["quarter_local"] > 50), "y_red_balance"] = pd.NA  # doba w toku
    out = experiment.prepare(part, TARGET)
    assert out["business_date"].max() == date(2026, 3, 30)
    assert "res_load" in out and out["y_red_balance"].dtype == int


@pytest.fixture(scope="module")
def result(data):
    old = dict(models.LGBM_PARAMS)
    models.LGBM_PARAMS.update(n_estimators=20, learning_rate=0.2, n_jobs=1)
    try:
        yield experiment.run(data, TARGET)
    finally:
        models.LGBM_PARAMS.clear()
        models.LGBM_PARAMS.update(old)


def test_experiment_structure(result, data):
    pred = result.predictions
    n_test = int((data["business_date"] > experiment.TRAIN_END).sum())
    names = [m.name for m in models.MODELS]
    assert pred["business_date"].min() == date(2026, 1, 1)
    counts = pred.groupby(["model", "schemat"]).size()
    assert len(counts) == len(names) * 2 and (counts == n_test).all()
    assert list(result.metrics.index) == [(m, s) for m in names for s in experiment.SCHEMES]
    # walidacja krocząca: trening kończy się na końcu miesiąca M−2
    for blocks in result.train_info.values():
        assert [b["train_to"] for b in blocks] == ["2025-11-30", "2025-12-31", "2026-01-31"]
        assert all(b["train_to"] < b["test_from"] for b in blocks)
    m = result.metrics
    assert m.loc[("lightgbm", "staly"), "AUC"] > m.loc[("baseline_kalendarz", "staly"), "AUC"]
    assert result.zero_mae["MAE"] > m.loc[("lightgbm", "staly"), "MAE"]
    assert (result.metrics_day["n"] < m["n"]).all()


def test_static_scheme_and_thresholds_do_not_use_test_targets(result, data):
    """Zmiana celów w okresie testowym nie zmienia progów ani prognoz modelu stałego."""
    changed = data.copy()
    test = changed["business_date"] > experiment.TRAIN_END
    changed.loc[test, "pv_red_balance_mw"] = 123.0
    changed.loc[test, "y_red_balance"] = 1
    old = dict(models.LGBM_PARAMS)
    models.LGBM_PARAMS.update(n_estimators=20, learning_rate=0.2, n_jobs=1)
    try:
        other = experiment.run(changed, TARGET)
    finally:
        models.LGBM_PARAMS.clear()
        models.LGBM_PARAMS.update(old)
    assert other.thresholds == result.thresholds
    a = result.predictions[result.predictions["schemat"] == "staly"].reset_index(drop=True)
    b = other.predictions[other.predictions["schemat"] == "staly"].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


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


def test_save_runs_and_predictions(engine_schema, result):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    run_ids = experiment.save(engine, result, schema)
    assert len(run_ids) == len(models.MODELS) * 2
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        runs = pd.read_sql(sa.text("SELECT * FROM model_run ORDER BY run_id"), conn)
        n = pd.read_sql(
            sa.text("SELECT run_id, count(*) AS n FROM inz_prediction GROUP BY 1"), conn
        )
    assert "inz_c1_balance_lightgbm_kroczacy" in set(runs["model"])
    row = runs[runs["model"] == "inz_c1_balance_lightgbm_staly"].iloc[0]
    assert row["params"]["target"] == "balance" and 0 < row["params"]["threshold"] < 1
    assert row["metrics"]["AUC"] > 0.9
    assert len(n) == len(run_ids) and n["n"].nunique() == 1
    # metryki ostatnich przebiegów: indeks (model, schemat) jak w tabeli eksperymentu
    latest = experiment.latest_metrics(engine, TARGET, schema)
    assert set(latest.index) == set(result.metrics.index)
    key = ("lightgbm_2etapy", "kroczacy")
    assert latest.loc[key, "AP"] == pytest.approx(result.metrics.loc[key, "AP"])
