"""Klient API raportów PSE (https://api.raporty.pse.pl).

Dokumentacja pól: https://api.raporty.pse.pl/EndpointsMap.pdf
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pandas as pd

from common.http import get_json

BASE_URL = "https://api.raporty.pse.pl/api"
PAGE_SIZE = 20000

# Raporty używane w projekcie i pierwsza doba, od której mają dane (context/01_dane.md).
REPORTS: dict[str, date] = {
    "his-wlk-cal": date(2024, 6, 14),
    "pdgopkd": date(2024, 6, 14),
    "poze-redoze": date(2024, 9, 27),
    "rce-pln": date(2024, 6, 14),
}

TIME_COLUMNS = ("dtime_utc", "publication_ts_utc")


def date_filter(start: date, end: date) -> str:
    return f"business_date ge '{start.isoformat()}' and business_date le '{end.isoformat()}'"


def fetch_records(
    client: httpx.Client, report: str, start: date, end: date, **retry_kw: Any
) -> list[dict[str, Any]]:
    """Wszystkie rekordy raportu dla dób [start, end]; paginacja przez `nextLink`."""
    if report not in REPORTS:
        raise ValueError(f"Nieznany raport: {report}")
    url: str | None = f"{BASE_URL}/{report}"
    params: dict[str, Any] | None = {"$filter": date_filter(start, end), "$first": PAGE_SIZE}
    records: list[dict[str, Any]] = []
    while url:
        payload = get_json(client, url, params, **retry_kw)
        records.extend(payload.get("value", []))
        url = payload.get("nextLink")
        params = None  # nextLink zawiera już wszystkie parametry
    return records


def to_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Rekordy → DataFrame. Kolumny czasu UTC parsowane do `datetime64[UTC]`.

    `dtime_utc` występuje w dwóch formatach (z sekundami i bez, np. w `poze-redoze`),
    dlatego parsowanie z `format="mixed"`. Pozostałe kolumny bez zmian (zapis surowy).
    """
    df = pd.DataFrame.from_records(records)
    for col in TIME_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="mixed", utc=True)
    if "dtime_utc" in df.columns:
        df = df.sort_values("dtime_utc", kind="stable").reset_index(drop=True)
    return df


def fetch_frame(
    client: httpx.Client, report: str, start: date, end: date, **retry_kw: Any
) -> pd.DataFrame:
    return to_frame(fetch_records(client, report, start, end, **retry_kw))
