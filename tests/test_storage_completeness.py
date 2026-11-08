from datetime import date

import pandas as pd

from common import storage
from common.completeness import check_pse, expected_quarters, to_markdown


def test_expected_quarters_dst():
    assert expected_quarters(date(2025, 3, 30)) == 92
    assert expected_quarters(date(2025, 10, 26)) == 100
    assert expected_quarters(date(2025, 6, 15)) == 96


def test_month_chunks():
    chunks = list(storage.month_chunks(date(2024, 6, 14), date(2024, 8, 3)))
    assert chunks == [
        (date(2024, 6, 14), date(2024, 6, 30)),
        (date(2024, 7, 1), date(2024, 7, 31)),
        (date(2024, 8, 1), date(2024, 8, 3)),
    ]
    assert list(storage.month_chunks(date(2024, 6, 2), date(2024, 6, 1))) == []


def day_frame(day: str, value: float, n: int = 96) -> pd.DataFrame:
    end = pd.Timestamp(day, tz="Europe/Warsaw").tz_convert("UTC")
    t = pd.date_range(end + pd.Timedelta(minutes=15), periods=n, freq="15min")
    return pd.DataFrame({"business_date": day, "dtime_utc": t, "demand": value})


def test_upsert_replaces_only_fetched_days(tmp_path):
    path = tmp_path / "x.parquet"
    storage.upsert_days(
        path,
        pd.concat([day_frame("2026-06-01", 1.0), day_frame("2026-06-02", 1.0)]),
        "business_date",
        date(2026, 6, 1),
        date(2026, 6, 2),
    )
    n = storage.upsert_days(
        path, day_frame("2026-06-02", 2.0), "business_date", date(2026, 6, 2), date(2026, 6, 2)
    )
    df = pd.read_parquet(path)
    assert n == 192
    assert df.groupby("business_date")["demand"].first().to_dict() == {
        "2026-06-01": 1.0,
        "2026-06-02": 2.0,
    }
    assert df["dtime_utc"].is_monotonic_increasing


def test_check_pse_detects_gaps_and_duplicates():
    df = pd.concat([day_frame("2026-06-01", 1.0), day_frame("2026-06-03", 1.0, n=95)])
    df = pd.concat([df, df.iloc[[0]]])
    df.loc[df.index[1], "demand"] = None
    c = check_pse("his-wlk-cal", df, date(2026, 6, 1), date(2026, 6, 3))
    assert c.missing_days == [date(2026, 6, 2)]
    assert c.wrong_count_days == [(date(2026, 6, 1), 97, 96), (date(2026, 6, 3), 95, 96)]
    assert c.duplicate_dtime == 1
    assert c.null_share["demand"] > 0
    text = to_markdown([c], None, pd.Timestamp("2026-11-08 12:00"))
    assert "2026-06-02" in text and "`his-wlk-cal`" in text
