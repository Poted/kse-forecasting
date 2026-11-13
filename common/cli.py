"""CLI pobierania danych i raportu kompletności.

Przykłady:
    uv run kse-data pse --start 2024-06-14
    uv run kse-data weather --start 2024-06-14
    uv run kse-data report
    uv run kse-data db-init && uv run kse-data load && uv run kse-data db-check
    uv run kse-data erd --out docs/erd.md
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from common import completeness, db, openmeteo, pse, storage
from common.config import load_settings

log = logging.getLogger("kse-data")

# Raporty z danymi na dobę następną (publikowane w dniu D): domyślnie pobieramy też jutro.
PSE_DAY_AHEAD = {"pdgopkd", "rce-pln"}
TIMEOUT = httpx.Timeout(120.0, connect=30.0)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "kse-forecasting"})


def download_pse(data_dir: Path, reports: list[str], start: date | None, end: date | None) -> None:
    today = date.today()
    with _client() as client:
        for report in reports:
            r_start = max(start or pse.REPORTS[report], pse.REPORTS[report])
            r_end = end or (today + timedelta(days=1) if report in PSE_DAY_AHEAD else today)
            for c_start, c_end in storage.month_chunks(r_start, r_end):
                df = pse.fetch_frame(client, report, c_start, c_end)
                n = storage.upsert_days(
                    storage.pse_path(data_dir, report, c_start), df, "business_date", c_start, c_end
                )
                log.info("%s %s–%s: pobrano %d, w pliku %d", report, c_start, c_end, len(df), n)


def download_weather(data_dir: Path, start: date | None, end: date | None) -> None:
    points = openmeteo.load_points()
    w_start = max(start or openmeteo.START_DATE, openmeteo.START_DATE)
    w_end = end or date.today()
    with _client() as client:
        for c_start, c_end in storage.month_chunks(w_start, w_end):
            df = openmeteo.fetch_frame(client, points, c_start, c_end)
            n = storage.upsert_days(
                storage.weather_path(data_dir, c_start), df, "time_utc", c_start, c_end
            )
            log.info("pogoda %s–%s: pobrano %d, w pliku %d", c_start, c_end, len(df), n)


def build_report(data_dir: Path, end: date | None) -> str:
    today = date.today()
    checks = []
    for report, first in pse.REPORTS.items():
        r_end = end or (today + timedelta(days=1) if report in PSE_DAY_AHEAD else today)
        df = storage.read_all(data_dir / "raw" / "pse" / report)
        checks.append(completeness.check_pse(report, df, first, r_end))
    points = [p.name for p in openmeteo.load_points()]
    wdf = storage.read_all(data_dir / "raw" / "openmeteo")
    weather = completeness.check_weather(wdf, points, openmeteo.START_DATE, end or today)
    return completeness.to_markdown(checks, weather, datetime.now(UTC))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kse-data", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=storage.DEFAULT_DATA_DIR)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pse = sub.add_parser("pse", help="pobierz raporty PSE")
    p_pse.add_argument("--report", choices=list(pse.REPORTS), action="append")
    p_w = sub.add_parser("weather", help="pobierz pogodę Open-Meteo (_previous_day2)")
    p_r = sub.add_parser("report", help="raport kompletności (Markdown)")
    p_r.add_argument("--out", type=Path, help="plik wynikowy (domyślnie stdout)")
    sub.add_parser("db-init", help="utwórz tabele i widoki w bazie")
    sub.add_parser("load", help="załaduj data/raw do bazy (upsert)")
    sub.add_parser("db-check", help="zgodność liczby wierszy parquet vs baza")
    p_erd = sub.add_parser("erd", help="diagram ERD (Mermaid) ze schematu")
    p_erd.add_argument("--out", type=Path, help="plik wynikowy (domyślnie stdout)")
    for p in (p_pse, p_w, p_r):
        if p is not p_r:
            p.add_argument(
                "--start", type=_date, help="pierwsza doba (domyślnie od początku danych)"
            )
        p.add_argument(
            "--end", type=_date, help="ostatnia doba (domyślnie dziś / jutro dla planu i RCE)"
        )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # bez wpisu dla każdego zapytania

    if args.cmd == "pse":
        download_pse(args.data_dir, args.report or list(pse.REPORTS), args.start, args.end)
    elif args.cmd == "weather":
        download_weather(args.data_dir, args.start, args.end)
    elif args.cmd == "report":
        _write(build_report(args.data_dir, args.end), args.out)
    elif args.cmd == "erd":
        _write(erd_document(), args.out)
    else:
        engine = db.make_engine(load_settings().database_url)
        if args.cmd == "db-init":
            db.init_schema(engine)
            log.info("Schemat gotowy: %s", ", ".join([*db.metadata.tables, *db.VIEWS]))
        elif args.cmd == "load":
            db.init_schema(engine)
            for r in db.load_all(engine, args.data_dir):
                log.info("%s: %d plików, %d wierszy (upsert)", r.table, r.files, r.rows)
        else:
            checks = db.check_counts(engine, args.data_dir)
            for c in checks:
                status = "OK" if c.ok else "NIEZGODNE"
                print(f"{c.table:20s} parquet={c.parquet_rows:7d} baza={c.db_rows:7d} {status}")
            if not all(c.ok for c in checks):
                raise SystemExit(1)


def _write(text: str, out: Path | None) -> None:
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)


def erd_document() -> str:
    return (
        "# ERD — baza danych\n\n"
        "Wygenerowano ze schematu (`common/db.py`): `uv run kse-data erd --out docs/erd.md`.\n"
        "Tabele `pse_*` nie mają kluczy obcych: łączy je czas"
        " (`dtime_utc`, koniec kwadransu UTC).\n"
        "Widoki godzinowe: "
        + ", ".join(f"`{v}`" for v in db.VIEWS)
        + " (opis: `docs/etapy/P2.3.md`).\n\n"
        "```mermaid\n" + db.erd_mermaid() + "\n```\n"
    )


if __name__ == "__main__":
    main()
