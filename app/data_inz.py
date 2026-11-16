"""Dane widoków inż w dashboardzie (zapytania do bazy; bez Streamlit — testowalne)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from inz import c2, experiment, forecast, models

TZ = "Europe/Warsaw"
# Prognoza pokazywana dla doby historycznej: operacyjna (jeśli była), inaczej z walidacji kroczącej.
SOURCES = {
    "c1": (forecast.OPERATIONAL["c1"], "inz_c1_balance_lightgbm_2etapy_kroczacy"),
    "c2": (forecast.OPERATIONAL["c2"], "inz_c2_rce_neg_lightgbm_kroczacy"),
}

PREDICTION_SQL = """
WITH runs AS (
    SELECT run_id, CASE WHEN model = :operational THEN 1 ELSE 2 END AS priority
    FROM model_run WHERE model IN (:operational, :experiment)
), pick AS (
    SELECT DISTINCT ON (p.business_date) p.business_date, p.run_id
    FROM inz_prediction p JOIN runs USING (run_id)
    WHERE p.business_date BETWEEN :start AND :end
    ORDER BY p.business_date, runs.priority, p.run_id DESC
)
SELECT p.dtime_utc, p.p_hat, p.mw_hat
FROM inz_prediction p JOIN pick USING (business_date, run_id)
"""
ACTUAL_SQL = """
SELECT dtime_utc, business_date, gen_fv, pv_red_balance_mw, y_red_balance, rce_pln, y_rce_neg
FROM inz_dataset WHERE business_date BETWEEN :start AND :end ORDER BY dtime_utc
"""


def dataset_range(engine: Engine) -> tuple[date, date] | None:
    """Zakres dób zbioru z określonymi celami ograniczeń."""
    sql = (
        "SELECT min(business_date), max(business_date) FROM inz_dataset "
        "WHERE y_red_balance IS NOT NULL"
    )
    with engine.connect() as conn:
        row = conn.execute(sa.text(sql)).one()
    return None if row[0] is None else (row[0], row[1])


def quarters(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Kwadranse z wykonaniem (ograniczenia, ceny) i prognozami obu celów."""
    span = {"start": start, "end": end}
    with engine.connect() as conn:
        df = pd.read_sql(sa.text(ACTUAL_SQL), conn, params=span)
        preds = {}
        for goal, (operational, exp) in SOURCES.items():
            preds[goal] = pd.read_sql(
                sa.text(PREDICTION_SQL),
                conn,
                params={**span, "operational": operational, "experiment": exp},
            )
    df["dtime_utc"] = pd.to_datetime(df["dtime_utc"], utc=True)
    for goal, pred in preds.items():
        pred["dtime_utc"] = pd.to_datetime(pred["dtime_utc"], utc=True)
        cols = {"p_hat": f"p_{goal}", "mw_hat": f"mw_{goal}"}
        df = df.merge(pred.rename(columns=cols), on="dtime_utc", how="left")
    for col in df.columns.difference(["dtime_utc", "business_date"]):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df.drop(columns="mw_c2")


def episodes(frame: pd.DataFrame) -> pd.DataFrame:
    """Doby z ograniczeniem bilansowym PV: energia, maksimum, czas trwania, ceny, prognoza."""
    if frame.empty:
        return pd.DataFrame()
    g = frame.groupby("business_date")
    out = pd.DataFrame(
        {
            "energia_mwh": g["pv_red_balance_mw"].sum() * 0.25,
            "maks_mw": g["pv_red_balance_mw"].max(),
            "kwadranse": g["y_red_balance"].sum(),
            "kwadranse_rce_ujemne": g["y_rce_neg"].sum(),
            "rce_min": g["rce_pln"].min(),
            "prognoza_mwh": g["mw_c1"].sum(min_count=1) * 0.25,
            "prognoza_maks_p": g["p_c1"].max(),
        }
    )
    out = out[out["kwadranse"] > 0]
    return out.sort_values("energia_mwh", ascending=False).reset_index()


def local_time(dtime_utc: pd.Series) -> pd.Series:
    """Początek kwadransu w czasie lokalnym (`dtime_utc` to koniec interwału)."""
    return (dtime_utc - pd.Timedelta(minutes=15)).dt.tz_convert(TZ)


def comparison(engine: Engine) -> dict[str, pd.DataFrame]:
    """Metryki ostatnich przebiegów eksperymentów: cel 1 (bilansowe) i cel 2."""
    tables = {}
    for key, target in (("c1", models.TARGETS["balance"]), ("c2", c2.TARGET)):
        tables[key] = experiment.latest_metrics(engine, target)
    return tables


def risk_periods(table: pd.DataFrame, threshold: float) -> list[tuple[str, str]]:
    """Ciągłe okresy z `p_hat` ≥ próg jako pary (początek, koniec) czasu lokalnego HH:MM."""
    start = local_time(table["dtime_utc"])
    end = table["dtime_utc"].dt.tz_convert(TZ)
    hot = (table["p_hat"] >= threshold).to_numpy()
    periods, begin = [], None
    for i, flag in enumerate(hot):
        if flag and begin is None:
            begin = i
        if begin is not None and (not flag or i == len(hot) - 1):
            last = i if flag else i - 1
            periods.append((f"{start.iloc[begin]:%H:%M}", f"{end.iloc[last]:%H:%M}"))
            begin = None
    return periods
