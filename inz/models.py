"""Modele celu 1 (ograniczenia PV na kwadrans D+1): modele bazowe i LightGBM.

Każdy model: `fit(train, target)` → `predict(frame)` zwraca `p_hat` (prawdopodobieństwo
ograniczenia) i `mw_hat` (wielkość ograniczenia [MW ≥ 0]). Cechy: `inz.dataset.FEATURES_C1`
plus cechy pochodne z planu PSE (`add_derived`) — wszystkie dostępne po publikacji planu na D+1.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from inz import dataset

SEED = 42


@dataclass(frozen=True)
class Target:
    key: str
    label: str
    flag: str
    mw: str


TARGETS = {
    "balance": Target("balance", "ograniczenie bilansowe PV", "y_red_balance", "pv_red_balance_mw"),
    "network": Target("network", "ograniczenie sieciowe PV", "y_red_network", "pv_red_network_mw"),
}

# Cechy pochodne: tylko z planu PSE na dobę T i prognozy P2 (te same momenty dostępności).
DERIVED = [
    "res_load",  # zapotrzebowanie − PV − wiatr (plan)
    "res_load_exch",  # jw. + saldo wymiany równoległej
    "pv_share",  # udział PV w zapotrzebowaniu (plan)
    "p2_minus_plan",  # prognoza P2 netto − netto wg planu PSE
    "res_load_day_min",  # minimum res_load w dobie
    "gen_fv_day_max",  # maksimum planowanej generacji PV w dobie
]
FEATURES = [*dataset.FEATURES_C1, *DERIVED]


def add_derived(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    df["res_load"] = df["kse_pow_dem"] - df["gen_fv"] - df["gen_wi"]
    df["res_load_exch"] = df["res_load"] + df["dom_balance_exchange_par"]
    df["pv_share"] = df["gen_fv"] / df["kse_pow_dem"]
    df["p2_minus_plan"] = df["p2_net_demand_hat"] - (df["kse_pow_dem"] - df["gen_fv"])
    day = df.groupby("business_date")
    df["res_load_day_min"] = day["res_load"].transform("min")
    df["gen_fv_day_max"] = day["gen_fv"].transform("max")
    return df


def _output(frame: pd.DataFrame, p, mw) -> pd.DataFrame:
    return pd.DataFrame(
        {"p_hat": np.clip(p, 0, 1), "mw_hat": np.clip(mw, 0, None)}, index=frame.index
    )


class CalendarBaseline:
    """Częstość i średnia wielkość ograniczenia w treningu wg (miesiąc, kwadrans doby)."""

    name = "baseline_kalendarz"
    params = {"keys": ["month", "quarter_local"]}

    def fit(self, train: pd.DataFrame, target: Target) -> CalendarBaseline:
        cols = [target.flag, target.mw]
        t = train.astype({target.flag: float})
        self.table_ = t.groupby(["month", "quarter_local"])[cols].mean()
        self.by_quarter_ = t.groupby("quarter_local")[cols].mean()
        self.target_ = target
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        keys = pd.MultiIndex.from_frame(frame[["month", "quarter_local"]])
        got = self.table_.reindex(keys)
        fallback = self.by_quarter_.reindex(frame["quarter_local"])  # miesiąc spoza treningu
        got = got.where(got.notna().to_numpy(), fallback.to_numpy())
        return _output(frame, got[self.target_.flag].to_numpy(), got[self.target_.mw].to_numpy())


class PlanRuleBaseline:
    """Reguła z planu PSE: im niższe `res_load` (zapotrzebowanie − PV − wiatr), tym większe
    ryzyko. Zależność monotoniczna dopasowana w treningu (regresja izotoniczna); przy
    planowanej generacji PV równej 0 wynik = 0."""

    name = "baseline_plan"
    params = {"variable": "res_load", "fit": "isotonic", "rule": "gen_fv > 0"}

    def fit(self, train: pd.DataFrame, target: Target) -> PlanRuleBaseline:
        day = train[train["gen_fv"] > 0]
        self.p_ = IsotonicRegression(increasing=False, out_of_bounds="clip").fit(
            day["res_load"], day[target.flag].astype(float)
        )
        self.mw_ = IsotonicRegression(increasing=False, out_of_bounds="clip").fit(
            day["res_load"], day[target.mw]
        )
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        sun = (frame["gen_fv"] > 0).to_numpy()
        x = frame["res_load"].to_numpy()
        return _output(
            frame, np.where(sun, self.p_.predict(x), 0), np.where(sun, self.mw_.predict(x), 0)
        )


LGBM_PARAMS = {
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


class LightGBMModel:
    """Klasyfikator (ograniczenie jest/nie ma) i regresor (MW, wszystkie kwadranse)."""

    name = "lightgbm"
    params = {"lgbm": LGBM_PARAMS, "features": FEATURES}

    def fit(self, train: pd.DataFrame, target: Target) -> LightGBMModel:
        x = train[FEATURES]
        self.clf_ = lgb.LGBMClassifier(objective="binary", **LGBM_PARAMS).fit(
            x, train[target.flag].astype(int)
        )
        self.reg_ = lgb.LGBMRegressor(objective="regression", **LGBM_PARAMS).fit(
            x, train[target.mw]
        )
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        x = frame[FEATURES]
        return _output(frame, self.clf_.predict_proba(x)[:, 1], self.reg_.predict(x))

    def importance(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "klasyfikator": self.clf_.booster_.feature_importance("gain"),
                "regresor": self.reg_.booster_.feature_importance("gain"),
            },
            index=FEATURES,
        ).pipe(lambda d: d / d.sum())


class LightGBMTwoStage(LightGBMModel):
    """Wariant dwuetapowy regresji: P(ograniczenie) × wielkość warunkowa (regresor uczony
    tylko na kwadransach z ograniczeniem). Klasyfikator jak w `LightGBMModel`."""

    name = "lightgbm_2etapy"
    params = {"lgbm": LGBM_PARAMS, "features": FEATURES, "regression": "p_hat × E[MW | ogr.]"}

    def fit(self, train: pd.DataFrame, target: Target) -> LightGBMTwoStage:
        self.clf_ = lgb.LGBMClassifier(objective="binary", **LGBM_PARAMS).fit(
            train[FEATURES], train[target.flag].astype(int)
        )
        pos = train[train[target.flag] == 1]
        self.reg_ = lgb.LGBMRegressor(objective="regression", **LGBM_PARAMS).fit(
            pos[FEATURES], pos[target.mw]
        )
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        x = frame[FEATURES]
        p = self.clf_.predict_proba(x)[:, 1]
        return _output(frame, p, p * np.clip(self.reg_.predict(x), 0, None))


MODELS = (CalendarBaseline, PlanRuleBaseline, LightGBMModel, LightGBMTwoStage)
