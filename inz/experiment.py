"""Eksperyment celu 1 (I2): trening ≤ 31.12.2025, test 2026; walidacja krocząca na 2026.

Schematy:
- `staly`    — jeden model uczony na dobach ≤ 31.12.2025, prognozy dla całego 2026.
- `kroczacy` — model douczany co miesiąc na rosnącym oknie. Model dla miesiąca M uczony na
  dobach do końca miesiąca M−2: dane o ograniczeniach (`poze-redoze`) są publikowane
  z opóźnieniem (mediana ok. 3 tygodnie, `context/00_fundament.md` sekcja 3), więc doby
  z miesiąca M−1 nie są w całości znane w chwili prognozy.
Próg decyzyjny (F1): wyznaczany wyłącznie na okresie treningowym — prognozy krzyżowe
(5 części, grupy = miesiące kalendarzowe), próg maksymalizujący F1; ten sam próg w obu schematach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sklearn.model_selection import GroupKFold
from sqlalchemy.engine import Engine

from common import db
from inz import evaluate, models
from p2.backtest import code_version, monthly_blocks

TRAIN_END = date(2025, 12, 31)
CV_FOLDS = 5
SCHEMES = ("staly", "kroczacy")


def prepare(data: pd.DataFrame, target: models.Target) -> pd.DataFrame:
    """Doby z kompletem celów i planu; cechy pochodne."""
    df = models.add_derived(data)
    ok = df[target.flag].notna() & df["kse_pow_dem"].notna()
    full_days = ok.groupby(df["business_date"]).transform("all")
    df = df[full_days].copy()
    df[target.flag] = df[target.flag].astype(int)
    return df.reset_index(drop=True)


def walk_cutoff(block_start: date) -> date:
    """Ostatnia doba treningowa dla bloku miesiąca M: koniec miesiąca M−2."""
    first_of_month = block_start.replace(day=1)
    prev_month_first = (first_of_month - timedelta(days=1)).replace(day=1)
    return prev_month_first - timedelta(days=1)


@dataclass
class Result:
    target: models.Target
    predictions: pd.DataFrame  # dtime_utc, business_date, cel, model, schemat, p_hat, mw_hat
    metrics: pd.DataFrame  # wiersz: (model, schemat)
    metrics_day: pd.DataFrame  # tylko kwadranse z planowaną generacją PV > 0
    thresholds: dict[str, float]
    train_info: dict[str, list[dict]]
    importance: pd.DataFrame
    final_model: models.LightGBMModel
    zero_mae: dict[str, float]  # MAE prognozy zerowej (punkt odniesienia)
    test: pd.DataFrame  # dtime_utc, business_date, cele, gen_fv
    params: dict[str, dict] = field(default_factory=dict)


def run(data: pd.DataFrame, target: models.Target, test_end: date | None = None) -> Result:
    df = prepare(data, target)
    days = df["business_date"]
    train = df[days <= TRAIN_END]
    test = df[(days > TRAIN_END) & (days <= (test_end or days.max()))]
    blocks = monthly_blocks(test["business_date"].min(), test["business_date"].max())

    preds, thresholds, info, params = [], {}, {}, {}
    final = None
    for cls in models.MODELS:
        name = cls.name
        params[name] = cls.params
        thresholds[name] = cv_threshold(cls, train, target)

        static = cls().fit(train, target)
        preds.append(_frame(test, static.predict(test), name, "staly"))
        info[name] = []
        for start, end in blocks:
            cutoff = walk_cutoff(start)
            part = df[days <= cutoff]
            block = test[(test["business_date"] >= start) & (test["business_date"] <= end)]
            preds.append(_frame(block, cls().fit(part, target).predict(block), name, "kroczacy"))
            info[name].append(
                {
                    "test_from": str(start),
                    "test_to": str(end),
                    "train_to": str(cutoff),
                    "train_rows": len(part),
                }
            )
        if cls is models.LightGBMModel:
            final = static
    zero = test[target.mw]
    zero_mae = {"MAE": float(zero.mean()), "MAE_ogr": float(zero[test[target.flag] == 1].mean())}
    predictions = pd.concat(preds, ignore_index=True)
    predictions.insert(2, "cel", target.key)

    truth = test[["dtime_utc", target.flag, target.mw, "gen_fv"]]
    joined = predictions.merge(truth, on="dtime_utc")
    return Result(
        target=target,
        predictions=predictions,
        metrics=_table(joined, target, thresholds),
        metrics_day=_table(joined[joined["gen_fv"] > 0], target, thresholds),
        thresholds=thresholds,
        train_info=info,
        importance=final.importance(),
        final_model=final,
        zero_mae=zero_mae,
        test=test[["dtime_utc", "business_date", target.flag, target.mw, "gen_fv"]],
        params=params,
    )


def cv_threshold(cls, train: pd.DataFrame, target: models.Target) -> float:
    """Próg F1 z prognoz krzyżowych na okresie treningowym (grupy = miesiące)."""
    months = pd.to_datetime(train["business_date"]).dt.to_period("M").astype(str)
    oof = np.zeros(len(train))
    for fit_idx, val_idx in GroupKFold(CV_FOLDS).split(train, groups=months):
        model = cls().fit(train.iloc[fit_idx], target)
        oof[val_idx] = model.predict(train.iloc[val_idx])["p_hat"]
    return evaluate.best_f1_threshold(train[target.flag].to_numpy(), oof)


def _frame(part: pd.DataFrame, out: pd.DataFrame, model: str, scheme: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dtime_utc": part["dtime_utc"].to_numpy(),
            "business_date": part["business_date"].to_numpy(),
            "model": model,
            "schemat": scheme,
            "p_hat": out["p_hat"].to_numpy(),
            "mw_hat": out["mw_hat"].to_numpy(),
        }
    )


def _table(joined: pd.DataFrame, target: models.Target, thresholds: dict) -> pd.DataFrame:
    rows = {
        key: evaluate.metrics(
            g[target.flag], g[target.mw], g["p_hat"], g["mw_hat"], thresholds[key[0]]
        )
        for key, g in joined.groupby(["model", "schemat"], sort=False)
    }
    table = pd.DataFrame(rows).T
    table.index.names = ["model", "schemat"]
    return table


def run_name(target: models.Target, model: str, scheme: str) -> str:
    return f"inz_c1_{target.key}_{model}_{scheme}"


def save(engine: Engine, result: Result, schema: str | None = None) -> dict[str, int]:
    """Zapisuje przebiegi (model × schemat) i prognozy testowe. Zwraca {nazwa: run_id}."""
    run_ids = {}
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        for (model, scheme), row in result.metrics.iterrows():
            name = run_name(result.target, model, scheme)
            blocks = result.train_info[model] if scheme == "kroczacy" else None
            run_id = conn.execute(
                sa.insert(db.model_run).returning(db.model_run.c.run_id),
                {
                    "model": name,
                    "code_version": code_version(),
                    "params": {
                        **result.params[model],
                        "target": result.target.key,
                        "scheme": scheme,
                        "threshold": result.thresholds[model],
                    },
                    "train_info": {"train_end": str(TRAIN_END), "blocks": blocks},
                    "metrics": {k: (None if pd.isna(v) else float(v)) for k, v in row.items()},
                },
            ).scalar_one()
            part = result.predictions[
                (result.predictions["model"] == model) & (result.predictions["schemat"] == scheme)
            ]
            frame = part[["dtime_utc", "business_date", "p_hat", "mw_hat"]].assign(run_id=run_id)
            db.upsert(conn, db.inz_prediction, frame, batch=10_000)
            run_ids[name] = run_id
    return run_ids
