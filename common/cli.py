"""CLI pobierania danych i raportu kompletności.

Przykłady:
    uv run kse-data pse --start 2024-06-14
    uv run kse-data weather --start 2024-06-14
    uv run kse-data report
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from common import completeness, openmeteo, pse, storage

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
    p_w = sub.add_parser("weather", help="pobierz pogodę Open-Meteo (_previous_day1)")
    p_r = sub.add_parser("report", help="raport kompletności (Markdown)")
    p_r.add_argument("--out", type=Path, help="plik wynikowy (domyślnie stdout)")
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

    if args.cmd == "pse":
        download_pse(args.data_dir, args.report or list(pse.REPORTS), args.start, args.end)
    elif args.cmd == "weather":
        download_weather(args.data_dir, args.start, args.end)
    else:
        text = build_report(args.data_dir, args.end)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text)


if __name__ == "__main__":
    main()
