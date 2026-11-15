"""Polecenie `kse-init`: doprowadza system do stanu gotowego do pracy (jedno polecenie).

Kroki (każdy pomijany, jeśli niepotrzebny):
1. schemat bazy,
2. dane PSE i pogoda: pierwsze uruchomienie — pełne pobranie; kolejne — ostatnie 10 dób
   (korekty PSE) oraz pogoda do D+2,
3. załadowanie do bazy (upsert; przy odświeżeniu tylko ostatnie miesiące),
4. walidacja krocząca (P2.5), jeśli w bazie nie ma przebiegu `lightgbm`,
5. prognoza na jutro (P2.6).

Działa tak samo lokalnie (`uv run kse-init`), w kontenerze
(`docker compose exec app uv run --no-sync kse-init`) i w sesji chmurowej Claude.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import timedelta
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from common import cli, db, openmeteo, pse, storage
from common.config import load_settings
from common.http import FetchError
from p2 import backtest, forecast

log = logging.getLogger("kse-init")
REFRESH_DAYS = 10


def has_raw_data(data_dir: Path) -> bool:
    """Czy są już pliki dla wszystkich raportów PSE i pogody."""
    dirs = [data_dir / "raw" / "pse" / r for r in pse.REPORTS] + [data_dir / "raw" / "openmeteo"]
    return all(any(d.glob("*.parquet")) for d in dirs)


def has_backtest(engine: Engine) -> bool:
    with engine.connect() as conn:
        n = conn.execute(
            sa.select(sa.func.count())
            .select_from(db.model_run)
            .where(db.model_run.c.model == "lightgbm")
        ).scalar_one()
    return n > 0


def run(engine: Engine, data_dir: Path, skip_download: bool = False) -> dict:
    t0 = time.time()
    db.init_schema(engine)
    today = forecast.today_local()
    full = not has_raw_data(data_dir)
    since = None if full else today - timedelta(days=REFRESH_DAYS)
    summary = {"pobranie": "pominięte" if skip_download else ("pełne" if full else "odświeżenie")}

    if not skip_download:
        log.info("Pobieranie danych: %s", summary["pobranie"])
        cli.download_pse(data_dir, list(pse.REPORTS), since, None)
        w_start = since or openmeteo.START_DATE
        try:
            cli.download_weather(data_dir, w_start, today + timedelta(days=2))
        except FetchError as exc:  # np. HTTP 429 — limit zapytań darmowego API Open-Meteo
            if full:
                raise
            log.warning("Pogoda nieodświeżona (%s) — używam danych z dysku.", exc)
            summary["pogoda"] = "nieodświeżona (błąd API Open-Meteo) — dane z poprzedniego pobrania"
        db.load_all(engine, data_dir, since=since)

    if has_backtest(engine):
        summary["walidacja"] = "jest w bazie"
    else:
        log.info("Walidacja krocząca (ok. 1 min)")
        actual, weather, pse_plan = backtest.load_inputs(engine)
        res = backtest.run_backtest(actual, weather, pse_plan)
        table = backtest.evaluate(res.forecasts)
        backtest.save_runs(engine, res, table)
        summary["walidacja"] = f"MAE LightGBM {table.loc['lightgbm', 'MAE']:.0f} MW"

    res = forecast.run(engine, data_dir, update=False)
    summary["prognoza"] = f"{res.forecast_date} → {res.target_date} (przebieg {res.run_id})"
    summary["ostrzeżenia"] = res.warnings
    summary["czas"] = f"{time.time() - t0:.0f} s"
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kse-init", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=storage.DEFAULT_DATA_DIR)
    parser.add_argument("--skip-download", action="store_true", help="bez pobierania danych")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    engine = db.make_engine(load_settings().database_url)
    summary = run(engine, args.data_dir, args.skip_download)
    print("\nGotowe.")
    for k, v in summary.items():
        if v:
            print(f"  {k}: {v}")
    print("Dashboard: uv run kse-app (lokalnie) albo http://localhost:8501 (docker compose).")


if __name__ == "__main__":
    main()
