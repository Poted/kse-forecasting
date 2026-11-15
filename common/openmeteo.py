"""Klient Open-Meteo: poprzednie przebiegi modeli (Previous Runs API).

Wg dokumentacji (https://open-meteo.com/en/docs/previous-runs-api) zmienna z przyrostkiem
`_previous_dayN` to wartość prognozowana N × 24 h przed godziną docelową. Używamy
`_previous_day2` (decyzja 13.11, `context/00_fundament.md` sekcja 5): dla każdej godziny
doby D+1 prognoza wydana najpóźniej o 23:00 dnia D−1, czyli dostępna o 12:00 dnia D.
`_previous_day1` dla godzin D+1 po ok. 12:00 byłaby wydana po momencie prognozy (przeciek).

Konwencja czasu (dokumentacja Open-Meteo): `shortwave_radiation` — średnia z godziny
poprzedzającej znacznik; `temperature_2m`, `cloud_cover`, `wind_speed_100m` — wartości chwilowe.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from common.config import PROJECT_ROOT
from common.http import get_json

BASE_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
START_DATE = date(2024, 6, 13)  # doba handlowa 14.06.2024 zaczyna się 13.06 22:00 UTC
VARIABLES = ("shortwave_radiation", "cloud_cover", "temperature_2m", "wind_speed_100m")
LEAD_DAYS = 2
SUFFIX = f"_previous_day{LEAD_DAYS}"
POINTS_FILE = PROJECT_ROOT / "config" / "punkty_pogodowe.toml"


@dataclass(frozen=True)
class Point:
    name: str
    lat: float
    lon: float


def load_points(path: Path = POINTS_FILE) -> list[Point]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [Point(p["nazwa"], float(p["lat"]), float(p["lon"])) for p in data["punkt"]]


def request_params(points: list[Point], start: date, end: date) -> dict[str, Any]:
    return {
        "latitude": ",".join(f"{p.lat}" for p in points),
        "longitude": ",".join(f"{p.lon}" for p in points),
        "hourly": ",".join(v + SUFFIX for v in VARIABLES),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "GMT",
    }


def to_frame(payload: Any, points: list[Point]) -> pd.DataFrame:
    """Odpowiedź (obiekt dla 1 punktu, lista dla wielu) → tabela długa.

    Kolumny: `time_utc` (znacznik godziny z API, UTC), `point`, zmienne bez przyrostka.
    """
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(points):
        raise ValueError(f"Oczekiwano {len(points)} punktów, otrzymano {len(items)}")
    frames = []
    for point, item in zip(points, items, strict=True):
        hourly = item["hourly"]
        df = pd.DataFrame({"time_utc": pd.to_datetime(hourly["time"], utc=True)})
        df["point"] = point.name
        for var in VARIABLES:
            df[var] = pd.to_numeric(pd.Series(hourly.get(var + SUFFIX)), errors="coerce")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def fetch_frame(
    client: httpx.Client, points: list[Point], start: date, end: date, **retry_kw: Any
) -> pd.DataFrame:
    payload = get_json(client, BASE_URL, request_params(points, start, end), **retry_kw)
    return to_frame(payload, points)
