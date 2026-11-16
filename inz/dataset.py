"""Zbiór uczący inż (I1): cechy z kontrolą momentu dostępności i cele na kwadrans doby T = D+1.

Jeden wiersz = jeden kwadrans (`dtime_utc`, koniec interwału 15 min); doba T ma 92, 96 lub 100
kwadransów. Momenty prognozy (`context/00_fundament.md` sekcja 3):
- cel 2 (ceny ujemne): dzień D, 12:00 czasu lokalnego — cechy `FEATURES_C2`,
- cel 1 (ograniczenia PV): dzień D po publikacji planu PSE na T (ok. 16:00) — cechy `FEATURES_C1`.

Grupy cech i ich dostępność:
- kalendarz — znany z góry,
- prognoza P2 netto (godzinowa, wykonana o 12:00 dnia D) — tylko prognozy z
  `forecast_moment_utc` ≤ 12:00 dnia D,
- pogoda Open-Meteo `_previous_day2` — tylko wartości wydane najpóźniej o 12:00 dnia D,
- plan dobowy PSE na T — tylko wersja opublikowana przed początkiem doby T; niedostępny
  o 12:00 dnia D, więc poza `FEATURES_C2`.
Wykonanie KSE, ograniczenia OZE i ceny doby T nie są argumentami funkcji budujących cechy.

Cele (`build_targets`): ograniczenie PV bilansowe i sieciowe [MW ≥ 0, flaga 0/1], `rce_pln < 0`.
Test braku przecieku: `tests/test_inz_dataset.py`.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from common import db
from p2 import features as p2f

TZ = p2f.TZ
FIRST_TARGET = date(2024, 9, 27)  # początek danych poze-redoze
QUARTER = pd.Timedelta(minutes=15)
P2_MODEL = "lightgbm"

CALENDAR = ["quarter_local", "dow", "month", "doy_sin", "doy_cos", "is_holiday", "is_weekend"]
PLAN = list(db.INZ_PLAN_COLUMNS)
P2 = ["p2_net_demand_hat"]
WEATHER = list(p2f.WEATHER_VARS)

FEATURES_C2 = [*CALENDAR, *P2, *WEATHER]  # 12:00 dnia D
FEATURES_C1 = [*CALENDAR, *PLAN, *P2, *WEATHER]  # po publikacji planu PSE
TARGETS = ["pv_red_balance_mw", "pv_red_network_mw", "y_red_balance", "y_red_network", "y_rce_neg"]
FLAGS = ["y_red_balance", "y_red_network", "red_pv0_anomaly", "y_rce_neg"]


def quarters(t: date) -> pd.DataFrame:
    """Kwadranse doby handlowej T: `dtime_utc` (koniec interwału) i numer kwadransu doby."""
    ends = pd.date_range(
        p2f.day_start_utc(t) + QUARTER, p2f.day_start_utc(t + timedelta(days=1)), freq="15min"
    )
    local = (ends - QUARTER).tz_convert(TZ)
    return pd.DataFrame({"dtime_utc": ends, "quarter_local": local.hour * 4 + local.minute // 15})


def hour_of(dtime_utc: pd.Series) -> pd.Series:
    """Początek godziny UTC, do której należy kwadrans (jak w widokach godzinowych bazy)."""
    return (dtime_utc - QUARTER).dt.floor("h")


def available_plan(plan: pd.DataFrame, t: date) -> pd.DataFrame:
    """Plan PSE na dobę T w wersji opublikowanej przed jej początkiem."""
    rows = plan[plan["business_date"] == t]
    return rows[rows["publication_ts_utc"] < p2f.day_start_utc(t)]


def available_p2(p2_forecast: pd.DataFrame, d: date) -> pd.DataFrame:
    """Prognozy P2 na dobę D+1 wykonane najpóźniej o 12:00 dnia D."""
    rows = p2_forecast[p2_forecast["target_date"] == d + timedelta(days=1)]
    return rows[rows["forecast_moment_utc"] <= p2f.forecast_moment_utc(d)]


def build_day(
    d: date, plan: pd.DataFrame, p2_forecast: pd.DataFrame, weather: pd.DataFrame
) -> pd.DataFrame:
    """Cechy dla wszystkich kwadransów doby T = D+1, z informacji dostępnych w dniu D.

    `plan`: `dtime_utc`, `business_date`, `publication_ts_utc`, kolumny planu (kwadranse).
    `p2_forecast`: `hour_utc`, `target_date`, `forecast_moment_utc`, `net_demand_hat`.
    `weather`: `time_utc` i zmienne pogodowe (średnia z punktów, godzinowo).
    """
    t = d + timedelta(days=1)
    rows = quarters(t)
    rows.insert(1, "business_date", t)
    hours = hour_of(rows["dtime_utc"])

    ts = pd.Timestamp(t)
    rows["dow"] = ts.day_of_week
    rows["month"] = ts.month
    rows["doy_sin"] = np.sin(2 * np.pi * ts.day_of_year / 365.25)
    rows["doy_cos"] = np.cos(2 * np.pi * ts.day_of_year / 365.25)
    rows["is_holiday"] = int(t in p2f.PL_HOLIDAYS)
    rows["is_weekend"] = int(ts.day_of_week >= 5)

    p = available_plan(plan, t).set_index("dtime_utc")
    for col in PLAN:
        rows[col] = p[col].reindex(rows["dtime_utc"]).to_numpy()
    rows["plan_publication_ts_utc"] = (
        p["publication_ts_utc"].reindex(rows["dtime_utc"]).reset_index(drop=True)
    )

    fc = available_p2(p2_forecast, d).set_index("hour_utc")["net_demand_hat"]
    rows["p2_net_demand_hat"] = fc.reindex(hours).to_numpy()

    hour_list = pd.Series(hours.unique())
    wx = p2f._weather_for_hours(p2f.available_weather(weather, d), hour_list)
    wx.index = hour_list
    for v in WEATHER:
        rows[v] = wx[v].reindex(hours).to_numpy()
    return rows


def build_features(
    plan: pd.DataFrame,
    p2_forecast: pd.DataFrame,
    weather: pd.DataFrame,
    first_target: date,
    last_target: date,
) -> pd.DataFrame:
    days = pd.date_range(first_target, last_target, freq="D").date
    frames = [build_day(t - timedelta(days=1), plan, p2_forecast, weather) for t in days]
    return pd.concat(frames, ignore_index=True)


def build_targets(redoze: pd.DataFrame, rce: pd.DataFrame, actual: pd.DataFrame) -> pd.DataFrame:
    """Cele na kwadrans.

    `redoze`: `dtime_utc`, `pv_red_balance`, `pv_red_network` [MW; ujemne = redukcja; NULL = brak],
    `publication_ts_utc`. `rce`: `dtime_utc`, `rce_pln`. `actual`: `dtime_utc`, `pv` (wykonanie).

    - Ograniczenie [MW] = −wartość raportu (≥ 0); NULL w raporcie = 0.
    - Cele ograniczeń są określone tylko dla kwadransów z wykonaniem (`pv` nie NULL): raport
      `poze-redoze` ma wiersze także dla dób przyszłych (puste), więc sam wiersz nie oznacza,
      że doba już się odbyła.
    - Reguła czyszczenia (pułapka 5): ograniczenie przy wykonanej generacji `pv == 0` jest
      zerowane; kwadrans oznaczony `red_pv0_anomaly = 1`.
    """
    out = redoze[["dtime_utc"]].copy()
    bal = (-redoze["pv_red_balance"].astype(float)).clip(lower=0).fillna(0.0)
    net = (-redoze["pv_red_network"].astype(float)).clip(lower=0).fillna(0.0)
    pv = actual.set_index("dtime_utc")["pv"].astype(float).reindex(out["dtime_utc"]).to_numpy()
    known = ~np.isnan(pv)
    anomaly = known & (pv == 0) & ((bal.to_numpy() > 0) | (net.to_numpy() > 0))
    out["pv_red_balance_mw"] = np.where(known, np.where(anomaly, 0.0, bal), np.nan)
    out["pv_red_network_mw"] = np.where(known, np.where(anomaly, 0.0, net), np.nan)
    out["y_red_balance"] = _flag(out["pv_red_balance_mw"] > 0, known)
    out["y_red_network"] = _flag(out["pv_red_network_mw"] > 0, known)
    out["red_pv0_anomaly"] = _flag(pd.Series(anomaly, index=out.index), known)
    out["red_publication_ts_utc"] = redoze["publication_ts_utc"].to_numpy()

    price = rce[["dtime_utc", "rce_pln"]].copy()
    price["rce_pln"] = price["rce_pln"].astype(float)
    price["y_rce_neg"] = _flag(price["rce_pln"] < 0, price["rce_pln"].notna().to_numpy())
    return out.merge(price, on="dtime_utc", how="outer")


def _flag(condition: pd.Series, known: np.ndarray) -> pd.Series:
    return condition.astype("Int64").where(known)


def build_dataset(
    plan: pd.DataFrame,
    p2_forecast: pd.DataFrame,
    weather: pd.DataFrame,
    redoze: pd.DataFrame,
    rce: pd.DataFrame,
    actual: pd.DataFrame,
    first_target: date = FIRST_TARGET,
    last_target: date | None = None,
) -> pd.DataFrame:
    """Cechy + cele dla dób [first_target, last_target] (domyślnie do ostatniej doby planu)."""
    last_target = last_target or plan["business_date"].max()
    feats = build_features(plan, p2_forecast, weather, first_target, last_target)
    data = feats.merge(build_targets(redoze, rce, actual), on="dtime_utc", how="left")
    for col in FLAGS:
        data[col] = data[col].astype("Int64")
    return data


# --- baza -------------------------------------------------------------------

_SQL = {
    "plan": "SELECT dtime_utc, business_date, publication_ts_utc, "
    + ", ".join(PLAN)
    + " FROM pse_pdgopkd ORDER BY dtime_utc",
    "p2_forecast": "SELECT hour_utc, target_date, forecast_moment_utc, net_demand_hat "
    f"FROM v_p2_forecast_latest WHERE model = '{P2_MODEL}'",
    "weather": "SELECT time_utc, " + ", ".join(WEATHER) + " FROM v_pogoda_h ORDER BY time_utc",
    "redoze": "SELECT dtime_utc, pv_red_balance, pv_red_network, publication_ts_utc "
    "FROM pse_poze_redoze ORDER BY dtime_utc",
    "rce": "SELECT dtime_utc, rce_pln FROM pse_rce_pln ORDER BY dtime_utc",
    "actual": "SELECT dtime_utc, pv FROM pse_his_wlk_cal ORDER BY dtime_utc",
}
_TIME_COLUMNS = ("dtime_utc", "hour_utc", "time_utc", "publication_ts_utc", "forecast_moment_utc")
_DATE_COLUMNS = ("business_date", "target_date")


def load_inputs(engine: Engine, schema: str | None = None) -> dict[str, pd.DataFrame]:
    """Tabele wejściowe z bazy; klucze = nazwy argumentów `build_dataset`."""
    frames = {}
    with engine.connect() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        for name, sql in _SQL.items():
            df = pd.read_sql(sa.text(sql), conn)
            for col in _TIME_COLUMNS:
                if col in df:
                    df[col] = pd.to_datetime(df[col], utc=True)
            for col in _DATE_COLUMNS:
                if col in df:
                    df[col] = pd.to_datetime(df[col]).dt.date
            frames[name] = df
    return frames


def save(engine: Engine, data: pd.DataFrame, schema: str | None = None) -> int:
    """Zastępuje zawartość tabeli `inz_dataset` (zbiór jest w całości odtwarzalny z danych)."""
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        conn.execute(sa.delete(db.inz_dataset))
        # limit PostgreSQL: 65 535 parametrów na zapytanie (wiersze × kolumny)
        batch = 65_535 // len(db.inz_dataset.columns)
        return db.upsert(conn, db.inz_dataset, data, batch=batch)


def read(engine: Engine, schema: str | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        df = pd.read_sql(sa.text("SELECT * FROM inz_dataset ORDER BY dtime_utc"), conn)
    for col in ("dtime_utc", "plan_publication_ts_utc", "red_publication_ts_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["business_date"] = pd.to_datetime(df["business_date"]).dt.date
    return df
