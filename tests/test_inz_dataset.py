"""Zbiór uczący inż: budowa cech, cele i test braku przecieku (dane syntetyczne)."""

import uuid
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import sqlalchemy as sa

from common import db
from common.config import load_settings
from inz import dataset, stats
from p2 import features as p2f

START = date(2025, 6, 10)
END = date(2025, 6, 20)
Q = dataset.QUARTER


def day_quarters(first: date, last: date) -> pd.DataFrame:
    frames = []
    for d in pd.date_range(first, last, freq="D").date:
        q = dataset.quarters(d)
        q["business_date"] = d
        frames.append(q)
    return pd.concat(frames, ignore_index=True)


def synthetic_plan(first=START, last=END) -> pd.DataFrame:
    df = day_quarters(first, last).drop(columns="quarter_local")
    rng = np.random.default_rng(1)
    for col in dataset.PLAN:
        df[col] = rng.uniform(100, 20000, len(df))
    # publikacja ok. 16:00 czasu lokalnego w dniu poprzedzającym dobę planu
    df["publication_ts_utc"] = [
        p2f.day_start_utc(d) - pd.Timedelta(hours=8) for d in df["business_date"]
    ]
    return df


def synthetic_p2(first=START, last=END) -> pd.DataFrame:
    frames = []
    for t in pd.date_range(first, last, freq="D").date:
        h = p2f.target_hours(t)
        frames.append(
            pd.DataFrame(
                {
                    "hour_utc": h["hour_utc"],
                    "target_date": t,
                    "forecast_moment_utc": p2f.forecast_moment_utc(t - timedelta(days=1)),
                    "net_demand_hat": 10000.0 + 100 * h["hour_local"],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def synthetic_weather(first=START, last=END) -> pd.DataFrame:
    t = pd.date_range(
        pd.Timestamp(first - timedelta(days=1), tz="UTC"),
        pd.Timestamp(last + timedelta(days=2), tz="UTC"),
        freq="h",
    )
    rng = np.random.default_rng(2)
    return pd.DataFrame({"time_utc": t} | {v: rng.uniform(1, 100, len(t)) for v in dataset.WEATHER})


def synthetic_targets(first=START, last=END):
    q = day_quarters(first, last)
    noon = q["quarter_local"].between(44, 51)
    redoze = pd.DataFrame(
        {
            "dtime_utc": q["dtime_utc"],
            "pv_red_balance": np.where(noon, -500.0, np.nan),
            "pv_red_network": np.where(q["quarter_local"] == 48, -5.0, np.nan),
            "publication_ts_utc": q["dtime_utc"] + pd.Timedelta(days=20),
        }
    )
    rce = pd.DataFrame({"dtime_utc": q["dtime_utc"], "rce_pln": np.where(noon, -10.0, 300.0)})
    actual = pd.DataFrame({"dtime_utc": q["dtime_utc"], "pv": np.where(noon, 8000.0, 100.0)})
    return redoze, rce, actual


D = date(2025, 6, 14)  # doba wykonania prognozy; T = 15.06
T = D + timedelta(days=1)


def features_of(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[["dtime_utc", *dataset.FEATURES_C1]].reset_index(drop=True)


# --- struktura --------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "n"), [(date(2025, 6, 15), 96), (date(2025, 3, 30), 92), (date(2025, 10, 26), 100)]
)
def test_quarters_of_business_day(day, n):
    q = dataset.quarters(day)
    assert len(q) == n
    assert q["dtime_utc"].iloc[0] == p2f.day_start_utc(day) + Q  # koniec pierwszego kwadransu
    assert q["dtime_utc"].iloc[-1] == p2f.day_start_utc(day + timedelta(days=1))
    assert q["quarter_local"].iloc[0] == 0 and q["quarter_local"].iloc[-1] == 95


def test_build_day_maps_sources_to_quarters():
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    rows = dataset.build_day(D, plan, fc, weather)
    assert len(rows) == 96 and (rows["business_date"] == T).all()
    assert not rows[dataset.FEATURES_C1].isna().any().any()
    # plan: wartości tego samego kwadransu
    expected = plan.set_index("dtime_utc").loc[rows["dtime_utc"], "gen_fv"].to_numpy()
    assert np.array_equal(rows["gen_fv"].to_numpy(), expected)
    # prognoza P2 i pogoda: wartość godziny, do której należy kwadrans (4 jednakowe kwadranse)
    assert (
        rows.groupby(dataset.hour_of(rows["dtime_utc"]))["p2_net_demand_hat"].nunique() == 1
    ).all()
    assert rows["p2_net_demand_hat"].iloc[0] == 10000.0  # godzina lokalna 0
    assert rows["p2_net_demand_hat"].iloc[-1] == 10000.0 + 100 * 23
    w = weather.set_index("time_utc")
    h0 = p2f.day_start_utc(T)
    assert rows["shortwave_radiation"].iloc[0] == w.loc[h0 + pd.Timedelta(hours=1)].iloc[0]
    assert rows["temperature_2m"].iloc[0] == pytest.approx(
        (w.loc[h0, "temperature_2m"] + w.loc[h0 + pd.Timedelta(hours=1), "temperature_2m"]) / 2
    )
    assert rows["dow"].iloc[0] == 6 and rows["is_weekend"].iloc[0] == 1  # 15.06.2025 niedziela


# --- dostępność informacji ---------------------------------------------------


def test_feature_lists_respect_forecast_moments():
    # cel 2 (12:00 dnia D): bez planu PSE na D+1 (publikacja ok. 16:00 dnia D)
    assert not set(dataset.FEATURES_C2) & set(dataset.PLAN)
    assert set(dataset.FEATURES_C2) < set(dataset.FEATURES_C1)
    # cechy nie zawierają celów, cen ani wykonania
    forbidden = {*dataset.TARGETS, "rce_pln", "red_pv0_anomaly", "pv", "demand", "wi"}
    forbidden |= {"pv_red_balance", "pv_red_network", "wi_red_balance", "wi_red_network"}
    assert not forbidden & set(dataset.FEATURES_C1)


@pytest.mark.parametrize("d", [D, date(2025, 6, 17)])
def test_no_leakage(d):
    """Dane niedostępne w dniu D (prognoza P2 i pogoda po 12:00, późniejsza wersja planu)
    nie wpływają na cechy doby D+1."""
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    base = features_of(dataset.build_day(d, plan, fc, weather))
    t = d + timedelta(days=1)

    # prognoza P2 na T wykonana po 12:00 dnia D (np. ponowne przeliczenie) — inne wartości
    late = fc[fc["target_date"] == t].assign(
        forecast_moment_utc=p2f.forecast_moment_utc(d) + pd.Timedelta(hours=1),
        net_demand_hat=lambda x: x["net_demand_hat"] * 10,
    )
    fc2 = pd.concat([fc[fc["target_date"] != t], late, fc[fc["target_date"] == t]])
    # pogoda wydana po 12:00 dnia D i wszystko, co dotyczy innych dób
    weather2 = weather.copy()
    issued_late = weather2["time_utc"] - p2f.WEATHER_LEAD > p2f.forecast_moment_utc(d)
    weather2.loc[issued_late, dataset.WEATHER] *= 10
    # plany innych dób
    plan2 = plan.copy()
    plan2.loc[plan2["business_date"] != t, dataset.PLAN] *= 10

    got = features_of(
        dataset.build_day(
            d, plan2, fc2.drop_duplicates(["hour_utc", "forecast_moment_utc"]), weather2
        )
    )
    pd.testing.assert_frame_equal(got, base)


def test_late_p2_forecast_and_late_plan_are_not_used():
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    fc_late = fc.assign(forecast_moment_utc=fc["forecast_moment_utc"] + pd.Timedelta(minutes=1))
    rows = dataset.build_day(D, plan, fc_late, weather)
    assert rows["p2_net_demand_hat"].isna().all()
    # plan opublikowany po rozpoczęciu doby (korekta) nie jest cechą
    plan_late = plan.assign(publication_ts_utc=p2f.day_start_utc(T) + pd.Timedelta(hours=1))
    rows = dataset.build_day(D, plan_late, fc, weather)
    assert rows[dataset.PLAN].isna().all().all()
    assert rows["plan_publication_ts_utc"].isna().all()


def test_available_data_is_used():
    """Kontrola czułości: zmiana danych dostępnych zmienia cechy."""
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    base = dataset.build_day(D, plan, fc, weather)
    plan2 = plan.copy()
    plan2.loc[plan2["business_date"] == T, "gen_fv"] += 1
    assert (dataset.build_day(D, plan2, fc, weather)["gen_fv"] != base["gen_fv"]).all()
    fc2 = fc.assign(net_demand_hat=fc["net_demand_hat"] + 1)
    got = dataset.build_day(D, plan, fc2, weather)
    assert (got["p2_net_demand_hat"] != base["p2_net_demand_hat"]).all()
    weather2 = weather.assign(cloud_cover=weather["cloud_cover"] + 1)
    assert (dataset.build_day(D, plan, fc, weather2)["cloud_cover"] != base["cloud_cover"]).all()


def test_features_do_not_depend_on_targets():
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    redoze, rce, actual = synthetic_targets()
    a = dataset.build_dataset(plan, fc, weather, redoze, rce, actual, START, END)
    b = dataset.build_dataset(
        plan,
        fc,
        weather,
        redoze.assign(pv_red_balance=-1.0, pv_red_network=-1.0),
        rce.assign(rce_pln=-999.0),
        actual.assign(pv=1.0),
        START,
        END,
    )
    pd.testing.assert_frame_equal(features_of(a), features_of(b))
    assert not a["y_red_balance"].equals(b["y_red_balance"])


# --- cele -------------------------------------------------------------------


def test_targets_definition():
    redoze, rce, actual = synthetic_targets(T, T)
    y = dataset.build_targets(redoze, rce, actual).set_index("dtime_utc")
    q = dataset.quarters(T).set_index("dtime_utc")["quarter_local"]
    noon = q.between(44, 51)
    assert (y.loc[noon, "pv_red_balance_mw"] == 500.0).all()  # znak odwrócony: MW ≥ 0
    assert (y.loc[~noon, "pv_red_balance_mw"] == 0.0).all()  # NULL w raporcie = brak ograniczenia
    assert y["y_red_balance"].sum() == 8 and y["y_red_network"].sum() == 1
    assert y.loc[q == 48, "pv_red_network_mw"].iloc[0] == 5.0
    assert y["y_rce_neg"].sum() == 8 and (y["red_pv0_anomaly"] == 0).all()


def test_targets_unknown_without_actuals_and_pv0_rule():
    redoze, rce, actual = synthetic_targets(T, T)
    q = dataset.quarters(T)["quarter_local"]
    # brak wykonania dla ostatnich kwadransów (doba w toku / przyszła) → cel nieokreślony
    actual_part = actual[q.to_numpy() < 80]
    # ograniczenie zgłoszone przy pv = 0 → wyzerowane i oznaczone
    actual_part = actual_part.assign(pv=np.where(q[q < 80] == 48, 0.0, actual_part["pv"]))
    y = dataset.build_targets(redoze, rce, actual_part)
    assert y["y_red_balance"].isna().sum() == 16 and y["pv_red_balance_mw"].isna().sum() == 16
    anomaly = y[q.to_numpy() == 48].iloc[0]
    assert anomaly["red_pv0_anomaly"] == 1
    assert anomaly["y_red_balance"] == 0 and anomaly["y_red_network"] == 0
    assert anomaly["pv_red_balance_mw"] == 0.0 and anomaly["pv_red_network_mw"] == 0.0
    assert y["y_red_balance"].sum() == 7
    assert y["y_rce_neg"].notna().all()  # cena nie zależy od wykonania


def test_target_stats_tables():
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    data = dataset.build_dataset(plan, fc, weather, *synthetic_targets(), START, END)
    tables = stats.target_stats(data)
    years = tables["Cele wg lat"]
    assert years.loc[2025, "doby"] == 11 and years.loc[2025, "ogr. bilansowe [kw.]"] == 88
    assert years.loc[2025, "doby z ogr. bilansowym"] == 11
    co = tables["Ceny ujemne a ograniczenia"]
    assert co.loc["ograniczenie bilansowe", "P(RCE < 0)"] == 1.0
    assert co.loc["bez ograniczeń", "P(RCE < 0)"] == 0.0
    assert tables["Braki"]["kwadranse z brakiem"].sum() == 0
    text = stats.to_markdown(tables)
    assert "## Cele wg lat" in text and "| 2025 | 11 |" in text


# --- z bazą -----------------------------------------------------------------


@pytest.fixture
def engine_schema():
    try:
        engine = db.make_engine(load_settings().database_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Brak bazy PostgreSQL: {exc}")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield engine, schema
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_save_replaces_table_and_roundtrip(engine_schema):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    plan, fc, weather = synthetic_plan(), synthetic_p2(), synthetic_weather()
    redoze, rce, actual = synthetic_targets()
    full = dataset.build_dataset(plan, fc, weather, redoze, rce, actual, START, END)
    assert dataset.save(engine, full, schema) == 11 * 96
    # doba bez wykonania: cele NULL w bazie
    short = dataset.build_dataset(
        plan, fc, weather, redoze, rce, actual[actual["dtime_utc"] <= p2f.day_start_utc(T)], T, T
    )
    assert dataset.save(engine, short, schema) == 96
    got = dataset.read(engine, schema)
    assert len(got) == 96 and (got["business_date"] == T).all()
    assert got["y_red_balance"].isna().all() and got["pv_red_balance_mw"].isna().all()
    assert got["y_rce_neg"].sum() == 8
    assert np.allclose(got["gen_fv"], short["gen_fv"])
    assert (got["dtime_utc"] == short["dtime_utc"]).all()
