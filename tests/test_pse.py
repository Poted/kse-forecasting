"""Klient PSE na zapisanych odpowiedziach API (bez sieci)."""

import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest

from common import pse
from common.completeness import check_pse

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def paged_transport(calls):
    p1 = load("pse_his-wlk-cal_2025-10-26_p1.json")
    p2 = load("pse_his-wlk-cal_2025-10-26_p2.json")

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=p2 if "$after" in request.url.params else p1)

    return httpx.MockTransport(handler)


def test_pagination_follows_next_link():
    calls = []
    with httpx.Client(transport=paged_transport(calls)) as client:
        records = pse.fetch_records(client, "his-wlk-cal", date(2025, 10, 26), date(2025, 10, 26))
    assert len(calls) == 2
    assert "business_date" in calls[0] and "2025-10-26" in calls[0]
    assert len(records) == 100  # doba zmiany czasu na zimowy


def test_to_frame_parses_utc_and_sorts():
    calls = []
    with httpx.Client(transport=paged_transport(calls)) as client:
        df = pse.fetch_frame(client, "his-wlk-cal", date(2025, 10, 26), date(2025, 10, 26))
    assert str(df["dtime_utc"].dt.tz) == "UTC"
    assert df["dtime_utc"].is_monotonic_increasing
    assert not df["dtime_utc"].duplicated().any()
    # dtime_utc = koniec interwału: 1. kwadrans doby 26.10.2025 (CEST) kończy się 22:15 UTC 25.10
    assert df["dtime_utc"].iloc[0] == pd.Timestamp("2025-10-25 22:15", tz="UTC")
    check = check_pse("his-wlk-cal", df, date(2025, 10, 26), date(2025, 10, 26))
    assert check.missing_days == [] and check.wrong_count_days == []


def test_dtime_without_seconds_is_parsed():
    payload = load("pse_poze-redoze_2026-06-15.json")
    assert payload["value"][0]["dtime_utc"] == "2026-06-14 22:15"  # format bez sekund
    df = pse.to_frame(payload["value"])
    assert df["dtime_utc"].iloc[0] == pd.Timestamp("2026-06-14 22:15", tz="UTC")


def test_date_filter():
    assert pse.date_filter(date(2024, 6, 14), date(2024, 6, 30)) == (
        "business_date ge '2024-06-14' and business_date le '2024-06-30'"
    )


def test_unknown_report_rejected():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
        with pytest.raises(ValueError):
            pse.fetch_records(client, "nie-ma", date(2024, 6, 14), date(2024, 6, 14))
