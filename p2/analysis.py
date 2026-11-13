"""Analiza danych P2: profile dobowe i sezonowe, krzywa kaczki, błąd prognozy PSE.

Dane z widoków godzinowych (P2.3). Godzina lokalna = początek godziny w Europe/Warsaw
(ta sama konwencja co tabela w `context/00_fundament.md`).

Uruchomienie (wykresy do `docs/fig/`, tabele do `docs/fig/p2_4_tabele.md`):
    uv run python -m p2.analysis
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from p2 import metrics

SEASONS = {
    12: "zima",
    1: "zima",
    2: "zima",
    3: "wiosna",
    4: "wiosna",
    5: "wiosna",
    6: "lato",
    7: "lato",
    8: "lato",
    9: "jesień",
    10: "jesień",
    11: "jesień",
}
SEASON_ORDER = ["zima", "wiosna", "lato", "jesień"]

HOURLY_SQL = """
SELECT w.hour_utc, w.business_date, w.demand, w.pv, w.net_demand,
       p.kse_pow_dem, p.gen_fv, p.net_demand_pse
FROM v_wykonanie_h w
LEFT JOIN v_plan_h p ON p.hour_utc = w.hour_utc AND p.n_quarters = 4
WHERE w.n_quarters = 4
ORDER BY w.hour_utc
"""


def load_hourly(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(sa.text(HOURLY_SQL), conn)
    return add_calendar(df)


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hour_utc"] = pd.to_datetime(out["hour_utc"], utc=True)
    local = out["hour_utc"].dt.tz_convert("Europe/Warsaw")
    out["hour_local"] = local.dt.hour
    out["business_date"] = pd.to_datetime(out["business_date"]).dt.date
    month = pd.to_datetime(out["business_date"]).dt.month
    out["month"] = pd.to_datetime(out["business_date"]).dt.to_period("M")
    out["season"] = pd.Categorical(month.map(SEASONS), SEASON_ORDER, ordered=True)
    return out


def daily_profile(df: pd.DataFrame, by: str, value: str = "net_demand") -> pd.DataFrame:
    """Średnia wartość wg godziny lokalnej (wiersze) i grupy `by` (kolumny)."""
    return df.pivot_table(
        index="hour_local", columns=by, values=value, aggfunc="mean", observed=True
    )


def june_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """Profil netto w czerwcu dla kolejnych lat (rozwój krzywej kaczki)."""
    june = df[df["month"].dt.month == 6].copy()
    june["year"] = june["month"].dt.year
    return daily_profile(june, "year")


def duck_depth(df: pd.DataFrame, midday=(9, 16), evening=(17, 22)) -> pd.DataFrame:
    """Dla każdej doby: minimum netto w południe, maksimum wieczorem i różnica (głębokość).

    Zwraca średnie miesięczne kolumn `midday_min`, `evening_max`, `depth` [MW].
    """
    mid = df[df["hour_local"].between(*midday)].groupby("business_date")["net_demand"].min()
    eve = df[df["hour_local"].between(*evening)].groupby("business_date")["net_demand"].max()
    daily = pd.DataFrame({"midday_min": mid, "evening_max": eve}).dropna()
    daily["depth"] = daily["evening_max"] - daily["midday_min"]
    daily["month"] = pd.to_datetime(daily.index).to_period("M")
    return daily.groupby("month")[["midday_min", "evening_max", "depth"]].mean()


def monthly_means(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("month")[["demand", "pv", "net_demand"]].mean()


def pse_errors(df: pd.DataFrame) -> pd.DataFrame:
    """Godziny z prognozą PSE i błędami: netto, zapotrzebowanie, PV (prognoza − wykonanie)."""
    out = df.dropna(subset=["net_demand_pse"]).copy()
    out["err_net"] = out["net_demand_pse"] - out["net_demand"]
    out["err_demand"] = out["kse_pow_dem"] - out["demand"]
    out["err_pv"] = out["gen_fv"] - out["pv"]
    return out


def pse_summary(err: pd.DataFrame) -> pd.DataFrame:
    rows = {
        "netto": metrics.summary(err["net_demand"], err["net_demand_pse"]),
        "zapotrzebowanie": metrics.summary(err["demand"], err["kse_pow_dem"]),
    }
    # PV: bez MAPE — w nocy pv = 0, błąd procentowy niezdefiniowany
    rows["PV"] = {
        "MAE": metrics.mae(err["pv"], err["gen_fv"]),
        "RMSE": metrics.rmse(err["pv"], err["gen_fv"]),
        "MAPE": float("nan"),
        "bias": metrics.bias(err["pv"], err["gen_fv"]),
        "n": float(len(err)),
    }
    ext = metrics.daily_extremes_error(err, "net_demand", "net_demand_pse")
    rows["netto — szczyt dobowy"] = {
        "MAE": float(ext["peak_error"].abs().mean()),
        "RMSE": float("nan"),
        "MAPE": float("nan"),
        "bias": float(ext["peak_error"].mean()),
        "n": float(len(ext)),
    }
    rows["netto — minimum południowe"] = {
        "MAE": float(ext["midday_min_error"].abs().mean()),
        "RMSE": float("nan"),
        "MAPE": float("nan"),
        "bias": float(ext["midday_min_error"].mean()),
        "n": float(ext["midday_min_error"].notna().sum()),
    }
    return pd.DataFrame(rows).T


def error_by(err: pd.DataFrame, by: str) -> pd.DataFrame:
    """MAE i bias błędu netto wg godziny lokalnej albo miesiąca."""
    g = err.groupby(by, observed=True)["err_net"]
    return pd.DataFrame({"MAE": g.apply(lambda e: e.abs().mean()), "bias": g.mean()})


def main(out_dir: Path | None = None) -> None:
    from common import db
    from common.config import PROJECT_ROOT, load_settings
    from p2 import plots

    out_dir = out_dir or PROJECT_ROOT / "docs" / "fig"
    df = load_hourly(db.make_engine(load_settings().database_url))
    plots.render_all(df, out_dir)
    print(f"Wykresy i tabele: {out_dir}")


if __name__ == "__main__":
    main()
