"""Zapis surowych danych w parquet, w plikach miesięcznych.

Układ: `<data_dir>/raw/pse/<raport>/<RRRR-MM>.parquet`,
`<data_dir>/raw/openmeteo/<RRRR-MM>.parquet`.
Zapis zastępuje w pliku wiersze z dób objętych nowym pobraniem (PSE koryguje dane wstecz),
pozostałe doby zostają.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from common.config import PROJECT_ROOT

DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def month_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Dzieli [start, end] na przedziały w obrębie miesięcy kalendarzowych."""
    if end < start:
        return
    cur = start
    while cur <= end:
        next_month = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        chunk_end = min(end, next_month - timedelta(days=1))
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def pse_path(data_dir: Path, report: str, month: date) -> Path:
    return data_dir / "raw" / "pse" / report / f"{month:%Y-%m}.parquet"


def weather_path(data_dir: Path, month: date) -> Path:
    return data_dir / "raw" / "openmeteo" / f"{month:%Y-%m}.parquet"


def _days(df: pd.DataFrame, day_column: str) -> pd.Series:
    col = df[day_column]
    if pd.api.types.is_datetime64_any_dtype(col):
        return col.dt.date
    return pd.to_datetime(col).dt.date


def upsert_days(path: Path, new: pd.DataFrame, day_column: str, start: date, end: date) -> int:
    """Zastępuje w pliku wiersze z dób [start, end] wierszami `new`. Zwraca liczbę wierszy pliku.

    `day_column`: kolumna określająca dobę (`business_date` dla PSE; `time_utc` dla pogody).
    """
    frames = []
    if path.exists():
        old = pd.read_parquet(path)
        days = _days(old, day_column)
        frames.append(old[(days < start) | (days > end)])
    frames.append(new)
    frames = [f for f in frames if not f.empty]
    if not frames:
        return 0
    out = pd.concat(frames, ignore_index=True)
    sort_col = "dtime_utc" if "dtime_utc" in out.columns else day_column
    extra = ["point"] if "point" in out.columns else []
    out = out.sort_values([sort_col, *extra], kind="stable").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(path)
    return len(out)


def read_all(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
