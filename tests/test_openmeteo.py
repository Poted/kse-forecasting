"""Klient Open-Meteo na zapisanej odpowiedzi (bez sieci)."""

import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest

from common import openmeteo
from common.completeness import check_weather

FIX = Path(__file__).parent / "fixtures"
POINTS = [openmeteo.Point("Warszawa", 52.2297, 21.0122), openmeteo.Point("Kraków", 50.0647, 19.945)]


def payload():
    return json.loads((FIX / "openmeteo_day2_2pkt_2025-06-21.json").read_text(encoding="utf-8"))


def test_request_params_use_previous_day2():
    params = openmeteo.request_params(POINTS, date(2025, 6, 21), date(2025, 6, 21))
    assert params["latitude"] == "52.2297,50.0647"
    assert all(v.endswith("_previous_day2") for v in params["hourly"].split(","))
    assert params["timezone"] == "GMT"


def test_fetch_frame_long_format():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json=payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        df = openmeteo.fetch_frame(client, POINTS, date(2025, 6, 21), date(2025, 6, 21))
    assert len(seen) == 1
    assert len(df) == 48
    assert set(df["point"]) == {"Warszawa", "Kraków"}
    assert list(df.columns) == ["time_utc", "point", *openmeteo.VARIABLES]
    assert df["time_utc"].iloc[0] == pd.Timestamp("2025-06-21 00:00", tz="UTC")
    # w nocy brak promieniowania, w dzień dodatnie
    wawa = df[df["point"] == "Warszawa"].set_index("time_utc")
    assert wawa["shortwave_radiation"].max() > 0
    check = check_weather(df, ["Warszawa", "Kraków"], date(2025, 6, 21), date(2025, 6, 21))
    assert check.missing_hours == {"Warszawa": 0, "Kraków": 0}
    assert check.duplicate_rows == 0


def test_point_count_mismatch():
    with pytest.raises(ValueError):
        openmeteo.to_frame(payload(), POINTS[:1])


def test_points_config_matches_decision():
    names = [p.name for p in openmeteo.load_points()]
    assert names == [
        "Warszawa",
        "Kraków",
        "Wrocław",
        "Poznań",
        "Gdańsk",
        "Rzeszów",
        "Białystok",
        "Szczecin",
    ]
