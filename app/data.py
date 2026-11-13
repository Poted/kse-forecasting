"""Dane dla dashboardu (zapytania do bazy; bez Streamlit — testowalne)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from p2 import analysis, backtest, features

QUALITY_SQL = """
SELECT f.model, f.hour_utc, f.target_date, f.net_demand_hat, w.net_demand AS y,
       p.net_demand_pse
FROM v_p2_forecast_latest f
JOIN v_wykonanie_h w ON w.hour_utc = f.hour_utc AND w.n_quarters = 4
LEFT JOIN v_plan_h p ON p.hour_utc = f.hour_utc AND p.n_quarters = 4
WHERE f.model = ANY(:models) AND f.target_date BETWEEN :start AND :end
"""

RUN_SQL = (
    "SELECT run_id, model, created_at, code_version, train_info FROM model_run WHERE run_id = :id"
)


def quality_frame(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Prognozy historyczne (walidacja krocząca) w układzie szerokim: jedna kolumna na model."""
    with engine.connect() as conn:
        long = pd.read_sql(
            sa.text(QUALITY_SQL),
            conn,
            params={"models": list(backtest.MODELS), "start": start, "end": end},
        )
    if long.empty:
        return pd.DataFrame(
            columns=[
                "target_date",
                "hour_utc",
                "hour_local",
                "y",
                "net_demand_pse",
                *backtest.MODELS,
            ]
        )
    long["hour_utc"] = pd.to_datetime(long["hour_utc"], utc=True)
    wide = long.pivot_table(
        index=["hour_utc", "target_date"], columns="model", values="net_demand_hat"
    ).reset_index()
    base = long.drop_duplicates("hour_utc")[["hour_utc", "y", "net_demand_pse"]]
    wide = wide.merge(base, on="hour_utc")
    wide["hour_local"] = wide["hour_utc"].dt.tz_convert(features.TZ).dt.hour
    wide["target_date"] = pd.to_datetime(wide["target_date"]).dt.date
    return wide.sort_values("hour_utc").reset_index(drop=True)


def quality_range(engine: Engine) -> tuple[date, date] | None:
    """Zakres dób z prognozami walidacji kroczącej (bez prognoz operacyjnych na jutro)."""
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT min(target_date), max(target_date) FROM v_p2_forecast_latest "
                "WHERE model = ANY(:models)"
            ),
            {"models": list(backtest.MODELS)},
        ).one()
    return None if row[0] is None else (row[0], row[1])


def run_info(engine: Engine, run_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(sa.text(RUN_SQL), {"id": run_id}).mappings().first()
    return dict(row) if row else None


def hourly_analysis(engine: Engine) -> pd.DataFrame:
    return analysis.load_hourly(engine)
