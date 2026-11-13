"""Baza PostgreSQL: schemat, ładowanie z aktualizacją rekordów (upsert), widoki godzinowe.

Tabele kwadransowe odpowiadają raportom PSE (klucz: `dtime_utc` — koniec interwału 15 min).
Pogoda: tabela punktów i tabela prognoz godzinowych (klucz: punkt + `time_utc`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, Engine

from common import openmeteo, storage

metadata = sa.MetaData()


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _mw(*names: str) -> list[sa.Column]:
    return [sa.Column(n, sa.Float) for n in names]


def _quarter_table(name: str, comment: str, *value_columns: sa.Column) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        _ts("dtime_utc", primary_key=True, comment="koniec interwału 15 min, UTC"),
        sa.Column("business_date", sa.Date, nullable=False, index=True, comment="doba handlowa"),
        *value_columns,
        _ts("publication_ts_utc", comment="moment publikacji wersji rekordu (PSE)"),
        comment=comment,
    )


# Kolumny wybrane z raportów (context/01_dane.md). Pominięte: kolumny puste lub częściowo puste
# w `his-wlk-cal` (jga, jgo, jgz1, jgz3, jgz2, jgw2, jgm2 — pułapka 6) i lokalne `dtime`/`period`
# (czas tylko z `dtime_utc` — pułapka 1).
his_wlk_cal = _quarter_table(
    "pse_his_wlk_cal",
    "Wykonanie KSE co 15 min [MW] (raport his-wlk-cal)",
    *_mw("demand", "pv", "wi", "jg", "jgm", "jnwrb", "swm_p", "swm_np", "jgw1", "jgm1"),
)
pdgopkd = _quarter_table(
    "pse_pdgopkd",
    "Plan koordynacyjny dobowy PSE na D+1 [MW] (raport pdgopkd)",
    *_mw(
        "kse_pow_dem",
        "gen_fv",
        "gen_wi",
        "rez_under",
        "rez_over_demand",
        "dom_balance_exchange_par",
        "dom_balance_exchange_non_par",
        "gen_jgw_jgm_jgz_jga",
        "ogr_mwe",
    ),
)
poze_redoze = _quarter_table(
    "pse_poze_redoze",
    "Nierynkowe redysponowanie OZE [MW; ujemne = redukcja; NULL = brak] (raport poze-redoze)",
    *_mw("pv_red_balance", "pv_red_network", "wi_red_balance", "wi_red_network"),
)
rce_pln = _quarter_table(
    "pse_rce_pln",
    "Rynkowa cena energii RCE [zł/MWh] (raport rce-pln); do 09.2025 ceny godzinowe",
    sa.Column("rce_pln", sa.Float),
)

weather_point = sa.Table(
    "weather_point",
    metadata,
    sa.Column("point_id", sa.SmallInteger, primary_key=True),
    sa.Column("name", sa.Text, nullable=False, unique=True),
    sa.Column("lat", sa.Float, nullable=False),
    sa.Column("lon", sa.Float, nullable=False),
    comment="Punkty pogodowe (config/punkty_pogodowe.toml)",
)
weather_forecast = sa.Table(
    "weather_forecast",
    metadata,
    sa.Column(
        "point_id", sa.SmallInteger, sa.ForeignKey("weather_point.point_id"), primary_key=True
    ),
    _ts("time_utc", primary_key=True, comment="znacznik godziny z Open-Meteo, UTC"),
    *[sa.Column(v, sa.Float) for v in openmeteo.VARIABLES],
    comment="Prognoza pogody wydana 48 h przed godziną docelową (Open-Meteo, _previous_day2)",
)

PSE_TABLES: dict[str, sa.Table] = {
    "his-wlk-cal": his_wlk_cal,
    "pdgopkd": pdgopkd,
    "poze-redoze": poze_redoze,
    "rce-pln": rce_pln,
}

# Godzina = interwał [h, h+1) w UTC. Kwadrans o końcu `dtime_utc` należy do godziny
# date_trunc('hour', dtime_utc - 15 min): końce h:15, h:30, h:45, h+1:00 → godzina h.
HOUR = "date_trunc('hour', dtime_utc - interval '15 minutes')"

VIEWS: dict[str, str] = {
    "v_wykonanie_h": f"""
        SELECT {HOUR} AS hour_utc,
               min(business_date) AS business_date,
               avg(demand) AS demand,
               avg(pv) AS pv,
               avg(demand - pv) AS net_demand,
               avg(wi) AS wi,
               count(demand) AS n_quarters
        FROM pse_his_wlk_cal
        GROUP BY 1""",
    "v_plan_h": f"""
        SELECT {HOUR} AS hour_utc,
               min(business_date) AS business_date,
               avg(kse_pow_dem) AS kse_pow_dem,
               avg(gen_fv) AS gen_fv,
               avg(kse_pow_dem - gen_fv) AS net_demand_pse,
               avg(gen_wi) AS gen_wi,
               max(publication_ts_utc) AS publication_ts_utc,
               count(kse_pow_dem) AS n_quarters
        FROM pse_pdgopkd
        GROUP BY 1""",
    "v_rce_h": f"""
        SELECT {HOUR} AS hour_utc,
               min(business_date) AS business_date,
               avg(rce_pln) AS rce_pln,
               min(rce_pln) AS rce_pln_min,
               count(rce_pln) AS n_quarters
        FROM pse_rce_pln
        GROUP BY 1""",
    "v_pogoda_h": """
        SELECT time_utc,
               avg(shortwave_radiation) AS shortwave_radiation,
               avg(cloud_cover) AS cloud_cover,
               avg(temperature_2m) AS temperature_2m,
               avg(wind_speed_100m) AS wind_speed_100m,
               count(*) AS n_points
        FROM weather_forecast
        GROUP BY time_utc""",
}

VIEW_COMMENTS = {
    "v_wykonanie_h": "Wykonanie godzinowe (średnia z kwadransów) i zapotrzebowanie netto",
    "v_plan_h": "Plan PSE godzinowo; net_demand_pse = benchmark P2",
    "v_rce_h": "RCE godzinowo (średnia i minimum z kwadransów)",
    "v_pogoda_h": "Pogoda: średnia z punktów (decyzja 08.11), znacznik godziny jak w Open-Meteo",
}


def make_engine(url: str) -> Engine:
    return sa.create_engine(url, future=True)


def init_schema(engine: Engine, schema: str | None = None) -> None:
    """Tworzy tabele (jeśli nie istnieją) i odtwarza widoki."""
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        metadata.create_all(conn)
        for name, sql in VIEWS.items():
            conn.execute(sa.text(f"CREATE OR REPLACE VIEW {name} AS {sql}"))
            comment = VIEW_COMMENTS[name].replace("'", "''")
            conn.exec_driver_sql(f"COMMENT ON VIEW {name} IS '{comment}'")


def _records(df: pd.DataFrame, columns: Iterable[str]) -> list[dict]:
    sub = df[list(columns)]
    sub = sub.astype(object).where(sub.notna(), None)
    return sub.to_dict("records")


def upsert(conn: Connection, table: sa.Table, df: pd.DataFrame, batch: int = 5000) -> int:
    """INSERT … ON CONFLICT (klucz) DO UPDATE — korekty PSE nadpisują poprzednie wartości."""
    if df.empty:
        return 0
    columns = [c.name for c in table.columns]
    keys = [c.name for c in table.primary_key.columns]
    rows = _records(df, columns)
    for i in range(0, len(rows), batch):
        stmt = pg_insert(table).values(rows[i : i + batch])
        stmt = stmt.on_conflict_do_update(
            index_elements=keys,
            set_={c: stmt.excluded[c] for c in columns if c not in keys},
        )
        conn.execute(stmt)
    return len(rows)


def prepare_pse(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["business_date"] = pd.to_datetime(out["business_date"]).dt.date
    return out.drop_duplicates("dtime_utc", keep="last")


def load_points(conn: Connection, points: list[openmeteo.Point]) -> dict[str, int]:
    rows = pd.DataFrame(
        [
            {"point_id": i, "name": p.name, "lat": p.lat, "lon": p.lon}
            for i, p in enumerate(points, start=1)
        ]
    )
    upsert(conn, weather_point, rows)
    return dict(zip(rows["name"], rows["point_id"], strict=True))


def prepare_weather(df: pd.DataFrame, point_ids: dict[str, int]) -> pd.DataFrame:
    unknown = set(df["point"]) - set(point_ids)
    if unknown:
        raise ValueError(f"Punkty spoza konfiguracji: {sorted(unknown)}")
    out = df.copy()
    out["point_id"] = out["point"].map(point_ids)
    return out.drop_duplicates(["point_id", "time_utc"], keep="last")


@dataclass
class LoadResult:
    table: str
    files: int
    rows: int


def load_all(engine: Engine, data_dir: Path, schema: str | None = None) -> list[LoadResult]:
    """Ładuje wszystkie pliki parquet z `data/raw` do bazy (plik po pliku, upsert)."""
    results = []
    with engine.begin() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        for report, table in PSE_TABLES.items():
            files = sorted((data_dir / "raw" / "pse" / report).glob("*.parquet"))
            n = sum(upsert(conn, table, prepare_pse(pd.read_parquet(f))) for f in files)
            results.append(LoadResult(table.name, len(files), n))
        point_ids = load_points(conn, openmeteo.load_points())
        files = sorted((data_dir / "raw" / "openmeteo").glob("*.parquet"))
        n = sum(
            upsert(conn, weather_forecast, prepare_weather(pd.read_parquet(f), point_ids))
            for f in files
        )
        results.append(LoadResult(weather_forecast.name, len(files), n))
    return results


@dataclass
class CountCheck:
    table: str
    parquet_rows: int
    db_rows: int

    @property
    def ok(self) -> bool:
        return self.parquet_rows == self.db_rows


def check_counts(engine: Engine, data_dir: Path, schema: str | None = None) -> list[CountCheck]:
    """Zgodność liczby wierszy: unikalne klucze w parquet vs wiersze w tabelach bazy."""
    checks = []
    with engine.connect() as conn:
        if schema:
            conn.execute(sa.text(f'SET search_path TO "{schema}"'))

        def count(table: sa.Table) -> int:
            return conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()

        for report, table in PSE_TABLES.items():
            df = storage.read_all(data_dir / "raw" / "pse" / report)
            n = int(df["dtime_utc"].nunique()) if not df.empty else 0
            checks.append(CountCheck(table.name, n, count(table)))
        wdf = storage.read_all(data_dir / "raw" / "openmeteo")
        n = len(wdf.drop_duplicates(["point", "time_utc"])) if not wdf.empty else 0
        checks.append(CountCheck(weather_forecast.name, n, count(weather_forecast)))
    return checks


def erd_mermaid() -> str:
    """Diagram ERD (Mermaid) generowany ze schematu `metadata`."""
    types = {
        sa.DateTime: "timestamptz",
        sa.Date: "date",
        sa.Float: "float8",
        sa.SmallInteger: "int2",
        sa.Text: "text",
    }
    lines = ["erDiagram"]
    for table in metadata.sorted_tables:
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            typ = next((v for k, v in types.items() if isinstance(col.type, k)), str(col.type))
            marks = []
            if col.primary_key:
                marks.append("PK")
            if col.foreign_keys:
                marks.append("FK")
            mark = (" " + ",".join(marks)) if marks else ""
            lines.append(f"        {typ} {col.name}{mark}")
        lines.append("    }")
    for table in metadata.sorted_tables:
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            lines.append(f'    {parent} ||--o{{ {table.name} : "{fk.column.name}"')
    return "\n".join(lines)
