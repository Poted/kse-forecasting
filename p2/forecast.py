"""Prognoza zapotrzebowania netto na jutro (FR-10), uruchamiana ręcznie (decyzja 08.11).

Kroki:
1. Odświeżenie danych: wykonanie i plan PSE z ostatnich dób, pogoda `_previous_day2` do D+1;
   załadowanie zmienionych miesięcy do bazy (upsert).
2. Trening LightGBM na wszystkich dobach docelowych ≤ D−1 (wykonanie znane w dniu D).
3. Cechy dla doby D+1 tą samą funkcją co w walidacji (`features.build_day`) — te same reguły
   dostępności informacji co w P2.5.
4. Zapis: przebieg `model_run` (model `lightgbm_operacyjny`) i prognozy w `p2_forecast`.

D = bieżąca doba czasu lokalnego. Prognoza uruchomiona przed 12:00 korzysta z danych dostępnych
w chwili uruchomienia (wszystkie są wydane przed 12:00 dnia D).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from common import db, storage
from p2 import backtest, features

log = logging.getLogger(__name__)
OPERATIONAL_MODEL = "lightgbm_operacyjny"
REFRESH_DAYS = 10  # tyle ostatnich dób PSE pobieramy ponownie (korekty wsteczne)


def today_local() -> date:
    return pd.Timestamp.now(tz=features.TZ).date()


def refresh_data(engine: Engine, data_dir: Path, d: date) -> None:
    """Pobiera ostatnie doby PSE i pogodę do D+2 oraz ładuje zmienione miesiące do bazy."""
    from common import cli

    start = d - timedelta(days=REFRESH_DAYS)
    cli.download_pse(data_dir, ["his-wlk-cal", "pdgopkd"], start, None)
    cli.download_weather(data_dir, start, d + timedelta(days=2))
    db.load_all(engine, data_dir, since=start)


@dataclass
class ForecastResult:
    forecast_date: date
    target_date: date
    table: pd.DataFrame  # hour_utc, hour_local, lightgbm, net_demand_pse (jeśli opublikowany)
    warnings: list[str] = field(default_factory=list)
    run_id: int | None = None


def check_inputs(d: date, actual: pd.DataFrame, rows: pd.DataFrame) -> list[str]:
    warnings = []
    prev = d - timedelta(days=1)
    have = int((actual["business_date"] == prev).sum())
    need = len(features.target_hours(prev))
    if have < need:
        warnings.append(f"Wykonanie za {prev} niekompletne: {have} z {need} godzin.")
    missing = rows[features.FEATURES].isna().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        warnings.append(
            "Brakujące wartości cech: " + ", ".join(f"{k} ({v})" for k, v in missing.items())
        )
    return warnings


def make_forecast(
    actual: pd.DataFrame, weather: pd.DataFrame, pse: pd.DataFrame, d: date
) -> tuple[ForecastResult, dict]:
    """Prognoza na dobę D+1 z danych dostępnych w dniu D (bez zapisu)."""
    train = features.build_dataset(
        actual, weather, backtest.FIRST_TRAIN_TARGET, d - timedelta(days=1)
    )
    model = backtest.train_lgbm(train)
    rows = features.build_day(d, actual, weather)
    rows["lightgbm"] = model.predict(rows[features.FEATURES])
    table = rows[["hour_utc", "hour_local", "lightgbm"]].merge(pse, on="hour_utc", how="left")
    info = {
        "train_to": str(d - timedelta(days=1)),
        "train_rows": int(train["y"].notna().sum()),
        "model": model,
    }
    result = ForecastResult(d, d + timedelta(days=1), table, check_inputs(d, actual, rows))
    return result, info


def save_forecast(
    engine: Engine, result: ForecastResult, info: dict, schema: str | None = None
) -> int:
    moment = features.forecast_moment_utc(result.forecast_date)
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        run_id = conn.execute(
            sa.insert(db.model_run).returning(db.model_run.c.run_id),
            {
                "model": OPERATIONAL_MODEL,
                "code_version": backtest.code_version(),
                "params": {"lgbm": backtest.LGBM_PARAMS, "features": features.FEATURES},
                "train_info": {
                    "train_to": info["train_to"],
                    "train_rows": info["train_rows"],
                    "warnings": result.warnings,
                },
                "metrics": None,
            },
        ).scalar_one()
        frame = pd.DataFrame(
            {
                "run_id": run_id,
                "hour_utc": result.table["hour_utc"],
                "target_date": result.target_date,
                "forecast_date": result.forecast_date,
                "forecast_moment_utc": moment,
                "net_demand_hat": result.table["lightgbm"],
            }
        )
        db.upsert(conn, db.p2_forecast, frame)
    return run_id


def run(
    engine: Engine,
    data_dir: Path = storage.DEFAULT_DATA_DIR,
    update: bool = True,
    d: date | None = None,
    model_path: Path | None = None,
) -> ForecastResult:
    d = d or today_local()
    db.init_schema(engine)
    if update:
        refresh_data(engine, data_dir, d)
    actual, weather, pse = backtest.load_inputs(engine)
    result, info = make_forecast(actual, weather, pse, d)
    result.run_id = save_forecast(engine, result, info)
    if model_path:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        info["model"].booster_.save_model(str(model_path))
    for w in result.warnings:
        log.warning(w)
    return result


LATEST_OPERATIONAL_SQL = """
SELECT f.run_id, r.created_at, f.forecast_date, f.target_date, f.hour_utc, f.net_demand_hat,
       p.net_demand_pse, w.net_demand
FROM p2_forecast f
JOIN model_run r USING (run_id)
LEFT JOIN v_plan_h p ON p.hour_utc = f.hour_utc AND p.n_quarters = 4
LEFT JOIN v_wykonanie_h w ON w.hour_utc = f.hour_utc AND w.n_quarters = 4
WHERE f.run_id = (SELECT max(run_id) FROM model_run WHERE model = :model)
ORDER BY f.hour_utc
"""


def latest_operational(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(sa.text(LATEST_OPERATIONAL_SQL), conn, params={"model": OPERATIONAL_MODEL})
    if not df.empty:
        df["hour_utc"] = pd.to_datetime(df["hour_utc"], utc=True)
    for col in ("net_demand_hat", "net_demand_pse", "net_demand"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)  # NULL → NaN
    return df
