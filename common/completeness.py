"""Raport kompletności surowych danych (PSE i Open-Meteo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

WARSAW = ZoneInfo("Europe/Warsaw")


def expected_quarters(day: date) -> int:
    """Liczba kwadransów doby handlowej w czasie lokalnym: 92, 96 albo 100 (zmiana czasu)."""
    start = datetime(day.year, day.month, day.day, tzinfo=WARSAW)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=WARSAW)
    return int((end.timestamp() - start.timestamp()) // 900)


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


@dataclass
class PseCheck:
    report: str
    start: date
    end: date
    rows: int
    days_present: int
    missing_days: list[date] = field(default_factory=list)
    wrong_count_days: list[tuple[date, int, int]] = field(default_factory=list)
    duplicate_dtime: int = 0
    off_grid_dtime: int = 0
    null_share: dict[str, float] = field(default_factory=dict)


def check_pse(report: str, df: pd.DataFrame, start: date, end: date) -> PseCheck:
    """Sprawdza raport PSE dla dób [start, end]."""
    if df.empty:
        return PseCheck(report, start, end, 0, 0, missing_days=date_range(start, end))
    days = pd.to_datetime(df["business_date"]).dt.date
    df = df[(days >= start) & (days <= end)]
    days = pd.to_datetime(df["business_date"]).dt.date
    counts = days.value_counts()
    res = PseCheck(report, start, end, rows=len(df), days_present=int(counts.size))
    for d in date_range(start, end):
        n = int(counts.get(d, 0))
        if n == 0:
            res.missing_days.append(d)
        elif n != (exp := expected_quarters(d)):
            res.wrong_count_days.append((d, n, exp))
    res.duplicate_dtime = int(df["dtime_utc"].duplicated().sum())
    t = df["dtime_utc"]
    res.off_grid_dtime = int(((t.dt.minute % 15 != 0) | (t.dt.second != 0)).sum())
    res.null_share = {c: float(df[c].isna().mean()) for c in df.columns if df[c].isna().any()}
    return res


@dataclass
class WeatherCheck:
    start: date
    end: date
    rows: int
    points: list[str]
    missing_hours: dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    null_counts: dict[str, dict[str, int]] = field(default_factory=dict)


def check_weather(df: pd.DataFrame, points: list[str], start: date, end: date) -> WeatherCheck:
    """Sprawdza pogodę: 24 godziny UTC na dobę dla każdego punktu, braki wartości."""
    expected = pd.date_range(
        pd.Timestamp(start, tz="UTC"),
        pd.Timestamp(end, tz="UTC") + pd.Timedelta(hours=23),
        freq="h",
    )
    if df.empty:
        return WeatherCheck(start, end, 0, points, {p: len(expected) for p in points})
    df = df[(df["time_utc"] >= expected[0]) & (df["time_utc"] <= expected[-1])]
    res = WeatherCheck(start, end, rows=len(df), points=points)
    res.duplicate_rows = int(df.duplicated(["point", "time_utc"]).sum())
    variables = [c for c in df.columns if c not in ("time_utc", "point")]
    for p in points:
        sub = df[df["point"] == p]
        res.missing_hours[p] = int(len(expected.difference(pd.DatetimeIndex(sub["time_utc"]))))
        res.null_counts[p] = {v: int(sub[v].isna().sum()) for v in variables}
    return res


def _fmt_days(days: list[date], limit: int = 20) -> str:
    if not days:
        return "—"
    shown = ", ".join(d.isoformat() for d in days[:limit])
    return shown + (f" … (+{len(days) - limit})" if len(days) > limit else "")


def to_markdown(pse: list[PseCheck], weather: WeatherCheck | None, generated: datetime) -> str:
    lines = [
        "# Raport kompletności danych surowych",
        "",
        f"Wygenerowano: {generated:%Y-%m-%d %H:%M} UTC (`uv run kse-data report`).",
        "",
        "## PSE",
        "",
        "| Raport | Zakres dób | Wiersze | Doby z danymi | Brakujące doby | "
        "Doby z inną liczbą kwadransów | Duplikaty `dtime_utc` | `dtime_utc` poza siatką 15 min |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in pse:
        total = (c.end - c.start).days + 1
        lines.append(
            f"| `{c.report}` | {c.start} – {c.end} | {c.rows} | {c.days_present}/{total} | "
            f"{len(c.missing_days)} | {len(c.wrong_count_days)} | {c.duplicate_dtime} | "
            f"{c.off_grid_dtime} |"
        )
    for c in pse:
        lines += ["", f"### `{c.report}`", ""]
        lines.append(f"- Brakujące doby: {_fmt_days(c.missing_days)}")
        if c.wrong_count_days:
            items = ", ".join(f"{d} ({n} zamiast {e})" for d, n, e in c.wrong_count_days[:20])
            lines.append(f"- Doby z inną liczbą kwadransów: {items}")
        else:
            lines.append("- Doby z inną liczbą kwadransów: —")
        if c.null_share:
            shares = ", ".join(
                f"`{k}` {v:.1%}" for k, v in sorted(c.null_share.items(), key=lambda kv: -kv[1])
            )
            lines.append(f"- Udział wartości pustych (kolumny z brakami): {shares}")
        else:
            lines.append("- Udział wartości pustych: brak pustych wartości")
    if weather is not None:
        lines += [
            "",
            "## Open-Meteo (`_previous_day1`)",
            "",
            f"Zakres: {weather.start} – {weather.end} (doby UTC), wiersze: {weather.rows}, "
            f"duplikaty (punkt, godzina): {weather.duplicate_rows}.",
            "",
        ]
        variables = sorted({v for d in weather.null_counts.values() for v in d})
        lines.append(
            "| Punkt | Brakujące godziny | " + " | ".join(f"puste `{v}`" for v in variables) + " |"
        )
        lines.append("|---|---|" + "---|" * len(variables))
        for p in weather.points:
            nulls = weather.null_counts.get(p, {})
            cells = " | ".join(str(nulls.get(v, "—")) for v in variables)
            lines.append(f"| {p} | {weather.missing_hours.get(p, 0)} | {cells} |")
    return "\n".join(lines) + "\n"
