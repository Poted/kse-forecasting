"""Cel 2 (I4): ryzyko ujemnej ceny RCE na kwadrans doby T = D+1, prognoza o 12:00 dnia D.

Cechy (`FEATURES`), wszystkie dostępne o 12:00 dnia D:
- `inz.dataset.FEATURES_C2`: kalendarz, prognoza P2 netto, pogoda `_previous_day2`
  (bez planu PSE na T — publikowany ok. 16:00 dnia D),
- ceny RCE dób już opublikowanych: doba D (= T−1; RCE na dobę D jest publikowane ok. 14:00
  dnia D−1) i doba T−7. Użyta jest tylko wersja opublikowana przed 12:00 dnia D,
- agregaty dobowe prognozy P2 i pogody doby T.
Ceny doby T (cel) nie wchodzą do cech — `add_features` bierze dla doby T wyłącznie doby < T.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from inz import dataset, models
from p2 import features as p2f

TARGET = models.Target(
    "rce_neg", "ujemna cena RCE", "y_rce_neg", models.NO_REGRESSION, goal="c2", label_lag="day"
)
LAGS = (1, 7)  # doby wstecz względem T; T−1 = D
RCE_FEATURES = [
    *[f"rce_lag{k}" for k in LAGS],  # cena w tym samym kwadransie doby
    *[f"rce_neg_share_lag{k}" for k in LAGS],  # udział kwadransów z ceną < 0 w dobie
    *[f"rce_day_min_lag{k}" for k in LAGS],  # minimum ceny w dobie
]
DAY_FEATURES = ["p2_day_min", "rad_day_max", "wind_day_mean"]
FEATURES = [*dataset.FEATURES_C2, *RCE_FEATURES, *DAY_FEATURES]

RCE_SQL = "SELECT dtime_utc, business_date, rce_pln, publication_ts_utc FROM pse_rce_pln"


def load_rce(engine: Engine, schema: str | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        df = pd.read_sql(sa.text(RCE_SQL), conn)
    for col in ("dtime_utc", "publication_ts_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df


def add_features(data: pd.DataFrame, rce: pd.DataFrame) -> pd.DataFrame:
    """Dodaje cechy celu 2 do zbioru (`inz_dataset`). Zwraca tylko doby z prognozą P2."""
    df = data.copy()
    local = (rce["dtime_utc"] - dataset.QUARTER).dt.tz_convert(dataset.TZ)
    hist = rce.assign(quarter_local=local.dt.hour * 4 + local.dt.minute // 15)
    by_quarter = hist.groupby(["business_date", "quarter_local"])["rce_pln"].mean()
    by_day = hist.groupby("business_date").agg(
        day_min=("rce_pln", "min"),
        neg_share=("rce_pln", lambda v: float((v < 0).mean())),
        published=("publication_ts_utc", "max"),
    )
    targets = df["business_date"]
    # moment prognozy doby T: 12:00 czasu lokalnego dnia D = T−1
    moment = targets.map(
        {t: p2f.forecast_moment_utc(t - timedelta(days=1)) for t in targets.unique()}
    )
    for k in LAGS:
        source = targets.map(lambda t, k=k: t - timedelta(days=k))
        published = pd.to_datetime(source.map(by_day["published"]), utc=True)
        ok = (published < moment).to_numpy()  # tylko wersja znana w chwili prognozy
        keys = pd.MultiIndex.from_arrays([source, df["quarter_local"]])
        df[f"rce_lag{k}"] = np.where(ok, by_quarter.reindex(keys).to_numpy(), np.nan)
        df[f"rce_neg_share_lag{k}"] = np.where(ok, source.map(by_day["neg_share"]), np.nan)
        df[f"rce_day_min_lag{k}"] = np.where(ok, source.map(by_day["day_min"]), np.nan)
    day = df.groupby("business_date")
    df["p2_day_min"] = day["p2_net_demand_hat"].transform("min")
    df["rad_day_max"] = day["shortwave_radiation"].transform("max")
    df["wind_day_mean"] = day["wind_speed_100m"].transform("mean")
    has_p2 = day["p2_net_demand_hat"].transform(lambda v: v.notna().all())
    return df[has_p2].reset_index(drop=True)


class PersistenceBaseline:
    """„Jak dziś”: ryzyko = czy cena w tym samym kwadransie doby D (znanej o 12:00) była < 0."""

    name = "baseline_jak_dzis"
    params = {"column": "rce_lag1", "rule": "rce_lag1 < 0"}

    def fit(self, train: pd.DataFrame, target: models.Target) -> PersistenceBaseline:
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        p = (frame["rce_lag1"] < 0).astype(float)
        return models._output(frame, p, np.zeros(len(frame)))


class LightGBMC2(models.LightGBMModel):
    features = FEATURES


MODELS = (models.CalendarBaseline, PersistenceBaseline, LightGBMC2)
