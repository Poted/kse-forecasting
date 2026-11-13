"""Baza: testy jednostkowe (bez bazy) i integracyjne na PostgreSQL w tymczasowym schemacie.

Testy integracyjne wymagają działającej bazy z `DATABASE_URL` (`docker compose up -d`);
bez niej są pomijane.
"""

import json
import uuid
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa

from common import db, openmeteo, pse, storage
from common.config import load_settings

FIX = Path(__file__).parent / "fixtures"


def fixture_json(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def his_wlk_cal_frame() -> pd.DataFrame:
    p1 = fixture_json("pse_his-wlk-cal_2025-10-26_p1.json")
    p2 = fixture_json("pse_his-wlk-cal_2025-10-26_p2.json")
    return pse.to_frame(p1["value"] + p2["value"])


def weather_frame() -> pd.DataFrame:
    points = [p for p in openmeteo.load_points() if p.name in ("Warszawa", "Kraków")]
    return openmeteo.to_frame(fixture_json("openmeteo_2pkt_2025-06-21.json"), points)


# --- bez bazy ---------------------------------------------------------------


def test_erd_contains_tables_and_relation():
    text = db.erd_mermaid()
    for name in db.metadata.tables:
        assert f"    {name} {{" in text
    assert 'weather_point ||--o{ weather_forecast : "point_id"' in text
    assert "timestamptz dtime_utc PK" in text


def test_prepare_pse_converts_date_and_dedups():
    df = his_wlk_cal_frame()
    out = db.prepare_pse(pd.concat([df, df.iloc[[0]]]))
    assert len(out) == 100
    assert out["business_date"].iloc[0] == date(2025, 10, 26)


def test_prepare_weather_rejects_unknown_point():
    df = weather_frame()
    with pytest.raises(ValueError, match="spoza konfiguracji"):
        db.prepare_weather(df, {"Warszawa": 1})


def test_tables_skip_empty_columns():
    cols = set(db.his_wlk_cal.columns.keys())
    assert not cols & {"jga", "jgo", "jgz1", "jgz3", "dtime", "period"}
    assert {"demand", "pv", "dtime_utc", "business_date"} <= cols


# --- z bazą -----------------------------------------------------------------


@pytest.fixture
def engine_schema():
    try:
        engine = db.make_engine(load_settings().database_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:  # brak konfiguracji albo bazy
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


@pytest.fixture
def data_dir(tmp_path):
    df = his_wlk_cal_frame()
    storage.upsert_days(
        storage.pse_path(tmp_path, "his-wlk-cal", date(2025, 10, 1)),
        df,
        "business_date",
        date(2025, 10, 26),
        date(2025, 10, 26),
    )
    storage.upsert_days(
        storage.weather_path(tmp_path, date(2025, 6, 1)),
        weather_frame(),
        "time_utc",
        date(2025, 6, 21),
        date(2025, 6, 21),
    )
    return tmp_path


def query(engine, schema, sql):
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        return pd.read_sql(sa.text(sql), conn)


def test_load_and_row_count_consistency(engine_schema, data_dir):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    db.load_all(engine, data_dir, schema)
    checks = {c.table: c for c in db.check_counts(engine, data_dir, schema)}
    assert checks["pse_his_wlk_cal"].db_rows == 100
    assert checks["weather_forecast"].db_rows == 48
    assert all(c.ok for c in checks.values())


def test_upsert_overwrites_corrections(engine_schema, data_dir):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    db.load_all(engine, data_dir, schema)
    path = storage.pse_path(data_dir, "his-wlk-cal", date(2025, 10, 1))
    df = pd.read_parquet(path)
    df.loc[0, "demand"] = 1.0  # korekta wsteczna
    df.to_parquet(path, index=False)
    db.load_all(engine, data_dir, schema)
    got = query(engine, schema, "SELECT count(*) AS n, min(demand) AS d FROM pse_his_wlk_cal")
    assert got["n"].iloc[0] == 100
    assert got["d"].iloc[0] == 1.0


def test_hourly_view_dst_day_and_net_demand(engine_schema, data_dir):
    engine, schema = engine_schema
    db.init_schema(engine, schema)
    db.load_all(engine, data_dir, schema)
    hours = query(engine, schema, "SELECT * FROM v_wykonanie_h ORDER BY hour_utc")
    assert len(hours) == 25  # doba zmiany czasu na zimowy
    assert (hours["n_quarters"] == 4).all()
    # pierwsza godzina doby: kwadranse o końcach 22:15–23:00 UTC 25.10 → godzina 22:00 UTC
    assert hours["hour_utc"].iloc[0] == pd.Timestamp("2025-10-25 22:00", tz="UTC")
    raw = his_wlk_cal_frame().iloc[:4]
    assert hours["net_demand"].iloc[0] == pytest.approx((raw["demand"] - raw["pv"]).mean())
    weather = query(engine, schema, "SELECT * FROM v_pogoda_h")
    assert len(weather) == 24 and (weather["n_points"] == 2).all()
