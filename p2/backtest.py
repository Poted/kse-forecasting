"""Walidacja krocząca modeli zapotrzebowania netto i porównanie z prognozą PSE.

Modele:
- `naive_d1`  — „jak wczoraj”: ta sama godzina lokalna ostatniej pełnej doby (D−1 = T−2),
- `naive_week` — „jak tydzień temu”: ta sama godzina tej samej doby tygodnia (T−7 = D−6),
- `lightgbm`  — LightGBM na cechach z `p2/features.py`.
Benchmark: prognoza PSE z planu dobowego (`net_demand_pse`, publikowana ok. 16:00 dnia D).

Walidacja krocząca (decyzja 08.11): prognozy dla dób od 27.09.2024; LightGBM douczany
co miesiąc na rosnącym oknie od początku danych. Model dla dób miesiąca M uczony na dobach
docelowych ≤ D0 − 1, gdzie D0 = doba wykonania pierwszej prognozy w M (wartości rzeczywiste
tych dób są znane w chwili prognozy).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from p2 import features, metrics

FIRST_TEST_TARGET = date(2024, 9, 27)
FIRST_TRAIN_TARGET = date(2024, 6, 16)  # T−2 = 14.06.2024, pierwsza doba danych
SEED = 42
LGBM_PARAMS = {
    "objective": "regression",
    "n_estimators": 600,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": SEED,
    "n_jobs": 4,
    "deterministic": True,
    "force_row_wise": True,
    "verbose": -1,
}
MODELS = ("naive_d1", "naive_week", "lightgbm")
BASELINE_COLUMN = {"naive_d1": "net_lag2", "naive_week": "net_lag7"}

ACTUAL_SQL = """
SELECT hour_utc, business_date, net_demand, demand, pv
FROM v_wykonanie_h WHERE n_quarters = 4 ORDER BY hour_utc"""
WEATHER_SQL = """
SELECT time_utc, shortwave_radiation, cloud_cover, temperature_2m, wind_speed_100m
FROM v_pogoda_h ORDER BY time_utc"""
PSE_SQL = "SELECT hour_utc, net_demand_pse FROM v_plan_h WHERE n_quarters = 4"


def load_inputs(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with engine.connect() as conn:
        actual = pd.read_sql(sa.text(ACTUAL_SQL), conn)
        weather = pd.read_sql(sa.text(WEATHER_SQL), conn)
        pse = pd.read_sql(sa.text(PSE_SQL), conn)
    actual["hour_utc"] = pd.to_datetime(actual["hour_utc"], utc=True)
    actual["business_date"] = pd.to_datetime(actual["business_date"]).dt.date
    weather["time_utc"] = pd.to_datetime(weather["time_utc"], utc=True)
    pse["hour_utc"] = pd.to_datetime(pse["hour_utc"], utc=True)
    return actual, weather, pse


def last_complete_day(actual: pd.DataFrame) -> date:
    """Ostatnia doba z kompletem godzin wykonania."""
    counts = actual.groupby("business_date").size()
    expected = {d: len(features.target_hours(d)) for d in counts.index}
    full = [d for d, n in counts.items() if n == expected[d]]
    return max(full)


def monthly_blocks(first: date, last: date) -> list[tuple[date, date]]:
    blocks, cur = [], first
    while cur <= last:
        nxt = (pd.Timestamp(cur) + pd.offsets.MonthBegin(1)).date()
        blocks.append((cur, min(last, nxt - timedelta(days=1))))
        cur = nxt
    return blocks


def train_lgbm(train: pd.DataFrame) -> lgb.LGBMRegressor:
    train = train.dropna(subset=["y"])
    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(train[features.FEATURES], train["y"])
    return model


@dataclass
class BacktestResult:
    forecasts: pd.DataFrame  # target_date, hour_utc, y, net_demand_pse, <modele>
    train_info: list[dict] = field(default_factory=list)
    importance: pd.Series | None = None
    final_model: lgb.LGBMRegressor | None = None


def run_backtest(
    actual: pd.DataFrame,
    weather: pd.DataFrame,
    pse: pd.DataFrame,
    first_test: date = FIRST_TEST_TARGET,
    last_test: date | None = None,
) -> BacktestResult:
    last_test = last_test or last_complete_day(actual)
    data = features.build_dataset(actual, weather, FIRST_TRAIN_TARGET, last_test)
    test = data[data["target_date"] >= first_test].copy()
    for name, col in BASELINE_COLUMN.items():
        test[name] = test[col]
    test["lightgbm"] = np.nan

    info = []
    for start, end in monthly_blocks(first_test, last_test):
        cutoff = start - timedelta(days=2)  # doby docelowe ≤ D0 − 1, D0 = start − 1
        train = data[data["target_date"] <= cutoff]
        model = train_lgbm(train)
        mask = (test["target_date"] >= start) & (test["target_date"] <= end)
        test.loc[mask, "lightgbm"] = model.predict(test.loc[mask, features.FEATURES])
        info.append(
            {
                "test_from": str(start),
                "test_to": str(end),
                "train_to": str(cutoff),
                "train_rows": int(train["y"].notna().sum()),
            }
        )

    final = train_lgbm(data)
    importance = pd.Series(
        final.booster_.feature_importance("gain"), index=features.FEATURES
    ).sort_values(ascending=False)
    out = test.merge(pse, on="hour_utc", how="left")
    cols = [
        "target_date",
        "forecast_date",
        "hour_utc",
        "hour_local",
        "y",
        "net_demand_pse",
        *MODELS,
    ]
    return BacktestResult(out[cols], info, importance, final)


def evaluate(fc: pd.DataFrame) -> pd.DataFrame:
    """Metryki wszystkich modeli i PSE na wspólnym zbiorze godzin (y i wszystkie prognozy)."""
    names = [*MODELS, "net_demand_pse"]
    common = fc.dropna(subset=["y", *names])
    rows = {}
    for name in names:
        m = metrics.summary(common["y"], common[name])
        ext = metrics.daily_extremes_error(
            common.assign(business_date=common["target_date"]), "y", name
        )
        m["MAE_szczyt"] = float(ext["peak_error"].abs().mean())
        m["MAE_min_poludnie"] = float(ext["midday_min_error"].abs().mean())
        rows["PSE (plan dobowy)" if name == "net_demand_pse" else name] = m
    return pd.DataFrame(rows).T


def evaluate_periods(fc: pd.DataFrame) -> dict[str, pd.DataFrame]:
    td = pd.to_datetime(fc["target_date"])
    periods = {
        "całość": fc,
        "27.09–31.12.2024": fc[td.dt.year == 2024],
        "2025": fc[td.dt.year == 2025],
        "2026": fc[td.dt.year == 2026],
    }
    return {k: evaluate(v) for k, v in periods.items() if not v.empty}


def mae_by(fc: pd.DataFrame, by: str) -> pd.DataFrame:
    names = [*MODELS, "net_demand_pse"]
    common = fc.dropna(subset=["y", *names])
    key = pd.to_datetime(common["target_date"]).dt.to_period("M") if by == "month" else common[by]
    out = pd.DataFrame({n: (common[n] - common["y"]).abs().groupby(key).mean() for n in names})
    return out.rename(columns={"net_demand_pse": "PSE"})


def code_version() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


def save_runs(engine: Engine, result: BacktestResult, metrics_table: pd.DataFrame) -> dict:
    """Zapisuje przebiegi (po jednym na model) i prognozy historyczne. Zwraca {model: run_id}."""
    from common import db

    fc = result.forecasts
    moments = {d: features.forecast_moment_utc(d) for d in fc["forecast_date"].unique()}
    run_ids = {}
    with engine.begin() as conn:
        for name in MODELS:
            params = (
                {"lgbm": LGBM_PARAMS, "features": features.FEATURES}
                if name == "lightgbm"
                else {"column": BASELINE_COLUMN[name]}
            )
            train_info = {"blocks": result.train_info} if name == "lightgbm" else None
            run_id = conn.execute(
                sa.insert(db.model_run).returning(db.model_run.c.run_id),
                {
                    "model": name,
                    "code_version": code_version(),
                    "params": params,
                    "train_info": train_info,
                    "metrics": {
                        k: (None if pd.isna(v) else float(v))
                        for k, v in metrics_table.loc[name].items()
                    },
                },
            ).scalar_one()
            rows = fc.dropna(subset=[name])
            frame = pd.DataFrame(
                {
                    "run_id": run_id,
                    "hour_utc": rows["hour_utc"],
                    "target_date": rows["target_date"],
                    "forecast_date": rows["forecast_date"],
                    "forecast_moment_utc": rows["forecast_date"].map(moments),
                    "net_demand_hat": rows[name],
                }
            )
            db.upsert(conn, db.p2_forecast, frame)
            run_ids[name] = run_id
    return run_ids
