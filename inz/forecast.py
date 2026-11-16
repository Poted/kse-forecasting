"""Prognoza ryzyka nadpodaży na jutro (FR-15): doba D → kwadranse doby T = D+1.

- Cel 2 (ujemna cena RCE): informacje z 12:00 dnia D; model LightGBM uczony na dobach ≤ D−1.
- Cel 1 (ograniczenie bilansowe PV): po publikacji planu PSE na T (ok. 16:00 dnia D); model
  LightGBM z regresją dwuetapową (decyzja 16.11), uczony na dobach ≤ D − 30 dni — dane
  o ograniczeniach są publikowane z opóźnieniem (`docs/etapy/I1.md`).
Cechy doby T buduje ten sam kod co zbiór uczący (`inz.dataset.build_day`, `inz.c2.add_features`),
więc obowiązują te same reguły dostępności informacji. Wymaga prognozy P2 na dobę T
(`uv run kse-p2 forecast` albo codzienny przebieg automatyczny).

Zapis: `model_run` (modele `OPERATIONAL`) i `inz_prediction`.
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
from inz import c2, dataset, experiment, models
from p2.backtest import code_version
from p2.forecast import today_local

log = logging.getLogger(__name__)

C1_TARGET = models.TARGETS["balance"]
OPERATIONAL = {
    "c1": "inz_c1_balance_lightgbm_2etapy_operacyjny",
    "c2": "inz_c2_rce_neg_lightgbm_operacyjny",
}
LABEL_DELAY_DAYS = 30  # cel 1: doby treningowe ≤ D − 30
REFRESH_DAYS = 10
DATASET_REFRESH_DAYS = 45  # tyle ostatnich dób zbioru aktualizujemy w bazie przy prognozie


def refresh_data(engine: Engine, data_dir: Path, d: date) -> None:
    """Ostatnie doby wszystkich raportów PSE i pogoda do D+2 → baza (upsert)."""
    from common import cli, pse

    start = d - timedelta(days=REFRESH_DAYS)
    cli.download_pse(data_dir, list(pse.REPORTS), start, None)
    cli.download_weather(data_dir, start, d + timedelta(days=2))
    db.load_all(engine, data_dir, since=start)


@dataclass
class GoalForecast:
    goal: str
    table: pd.DataFrame  # dtime_utc, business_date, p_hat, mw_hat
    train_to: date
    train_rows: int
    params: dict


@dataclass
class ForecastResult:
    forecast_date: date
    target_date: date
    goals: dict[str, GoalForecast] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    run_ids: dict[str, int] = field(default_factory=dict)
    data: pd.DataFrame | None = None  # zbiór z dobą T (do aktualizacji tabeli inz_dataset)


def make_forecast(inputs: dict[str, pd.DataFrame], rce: pd.DataFrame, d: date) -> ForecastResult:
    """Prognozy obu celów na dobę D+1 z danych dostępnych w dniu D (bez zapisu)."""
    t = d + timedelta(days=1)
    data = dataset.build_dataset(**inputs, last_target=t)
    result = ForecastResult(d, t, data=data)
    day = data[data["business_date"] == t]
    if day["p2_net_demand_hat"].isna().any():
        result.warnings.append(
            f"Brak prognozy P2 na {t} wykonanej w dniu {d} — najpierw `uv run kse-p2 forecast`."
        )

    # cel 2 — 12:00 dnia D
    data2 = c2.add_features(data, rce)
    rows2 = data2[data2["business_date"] == t]
    train2 = data2[(data2["business_date"] <= d - timedelta(days=1)) & data2["y_rce_neg"].notna()]
    if rows2.empty:
        result.warnings.append("Cel 2 (ceny ujemne): brak cech doby prognozy — pominięty.")
    else:
        train2 = train2.assign(**{c2.TARGET.mw: 0.0, "y_rce_neg": train2["y_rce_neg"].astype(int)})
        model = c2.LightGBMC2().fit(train2, c2.TARGET)
        result.goals["c2"] = _goal("c2", rows2, model, train2)
        missing = rows2[c2.RCE_FEATURES[:1]].isna().any().any()
        if missing:
            result.warnings.append(f"Cel 2: brak cen RCE doby {d} opublikowanych przed 12:00.")

    # cel 1 — po publikacji planu PSE na T
    if day["kse_pow_dem"].isna().any():
        result.warnings.append(
            f"Plan PSE na {t} nie jest jeszcze opublikowany (ok. 16:00) — cel 1 pominięty."
        )
    else:
        known = experiment.prepare(data, C1_TARGET)
        train1 = known[known["business_date"] <= d - timedelta(days=LABEL_DELAY_DAYS)]
        rows1 = models.add_derived(day)
        model = models.LightGBMTwoStage().fit(train1, C1_TARGET)
        result.goals["c1"] = _goal("c1", rows1, model, train1)
    return result


def _goal(goal: str, rows: pd.DataFrame, model, train: pd.DataFrame) -> GoalForecast:
    out = model.predict(rows)
    table = pd.DataFrame(
        {
            "dtime_utc": rows["dtime_utc"].to_numpy(),
            "business_date": rows["business_date"].to_numpy(),
            "p_hat": out["p_hat"].to_numpy(),
            "mw_hat": out["mw_hat"].to_numpy(),
        }
    )
    return GoalForecast(goal, table, train["business_date"].max(), len(train), model.params)


def experiment_threshold(engine: Engine, schema: str | None = None) -> float | None:
    """Próg decyzyjny celu 1 z ostatniego eksperymentu (`kse-inz c1`), jeśli jest w bazie."""
    sql = "SELECT params FROM model_run WHERE model = :m ORDER BY run_id DESC LIMIT 1"
    name = experiment.run_name(C1_TARGET, models.LightGBMTwoStage.name, "staly")
    with engine.connect() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        row = conn.execute(sa.text(sql), {"m": name}).first()
    return float(row[0]["threshold"]) if row else None


def save_forecast(engine: Engine, result: ForecastResult, schema: str | None = None) -> dict:
    threshold = experiment_threshold(engine, schema)
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        for goal, fc in result.goals.items():
            params = {**fc.params, "goal": goal}
            if goal == "c1":
                params["threshold"] = threshold
            run_id = conn.execute(
                sa.insert(db.model_run).returning(db.model_run.c.run_id),
                {
                    "model": OPERATIONAL[goal],
                    "code_version": code_version(),
                    "params": params,
                    "train_info": {
                        "forecast_date": str(result.forecast_date),
                        "target_date": str(result.target_date),
                        "train_to": str(fc.train_to),
                        "train_rows": fc.train_rows,
                        "warnings": result.warnings,
                    },
                    "metrics": None,
                },
            ).scalar_one()
            db.upsert(conn, db.inz_prediction, fc.table.assign(run_id=run_id))
            result.run_ids[goal] = run_id
    return result.run_ids


def has_forecast(engine: Engine, goal: str, d: date) -> bool:
    """Czy w dniu D zapisano już prognozę celu na dobę D+1."""
    sql = """SELECT count(*) FROM model_run
             WHERE model = :m AND train_info->>'forecast_date' = :d"""
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), {"m": OPERATIONAL[goal], "d": str(d)}).scalar_one() > 0


def run(
    engine: Engine,
    data_dir: Path = storage.DEFAULT_DATA_DIR,
    update: bool = True,
    d: date | None = None,
    force: bool = False,
) -> ForecastResult:
    """Prognoza na jutro z zapisem. Cel 2 liczony raz dziennie (pierwsze uruchomienie = moment
    12:00); kolejne uruchomienia tego dnia dopisują cel 1, chyba że `force`."""
    d = d or today_local()
    db.init_schema(engine)
    if update:
        refresh_data(engine, data_dir, d)
    result = make_forecast(dataset.load_inputs(engine), c2.load_rce(engine), d)
    if not force:
        for goal in list(result.goals):
            if has_forecast(engine, goal, d):
                del result.goals[goal]
                log.info("Prognoza celu %s z dnia %s już jest w bazie — bez zmian.", goal, d)
    save_forecast(engine, result)
    dataset.save_recent(engine, result.data, d - timedelta(days=DATASET_REFRESH_DAYS))
    for w in result.warnings:
        log.warning(w)
    return result


# --- odczyt dla dashboardu ----------------------------------------------------

LATEST_SQL = """
SELECT p.run_id, r.created_at, r.code_version, r.params, r.train_info,
       p.dtime_utc, p.business_date, p.p_hat, p.mw_hat
FROM inz_prediction p JOIN model_run r USING (run_id)
WHERE p.run_id = (SELECT max(run_id) FROM model_run WHERE model = :model)
ORDER BY p.dtime_utc
"""


def latest(engine: Engine, goal: str) -> pd.DataFrame:
    """Ostatnia prognoza operacyjna celu (pusta ramka, jeśli brak)."""
    with engine.connect() as conn:
        df = pd.read_sql(sa.text(LATEST_SQL), conn, params={"model": OPERATIONAL[goal]})
    if not df.empty:
        df["dtime_utc"] = pd.to_datetime(df["dtime_utc"], utc=True)
    return df
