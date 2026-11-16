"""Statystyki celów zbioru uczącego inż (I1): tabele, plik Markdown, wykresy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from inz import dataset

RED = "y_red_balance"
NET = "y_red_network"
NEG = "y_rce_neg"


def _prepare(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    local = (df["dtime_utc"] - dataset.QUARTER).dt.tz_convert(dataset.TZ)
    df["hour_local"] = local.dt.hour
    day = pd.to_datetime(df["business_date"])
    df["year"] = day.dt.year
    df["ym"] = day.dt.to_period("M")
    for col in (RED, NET, NEG):
        df[col] = df[col].astype("float")
    df["y_red_any"] = ((df[RED] == 1) | (df[NET] == 1)).astype(float).where(df[RED].notna())
    return df


def _counts(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Liczby kwadransów i dób z ograniczeniem / ceną ujemną w grupach `key`."""
    known = df[df[RED].notna()]
    g = known.groupby(key)
    out = pd.DataFrame(
        {
            "doby": g["business_date"].nunique(),
            "kwadranse": g.size(),
            "ogr. bilansowe [kw.]": g[RED].sum(),
            "ogr. sieciowe [kw.]": g[NET].sum(),
            "ogr. dowolne [kw.]": g["y_red_any"].sum(),
            "doby z ogr. bilansowym": known[known[RED] == 1]
            .groupby(key)["business_date"]
            .nunique(),
            "doby z ogr. dowolnym": known[known["y_red_any"] == 1]
            .groupby(key)["business_date"]
            .nunique(),
        }
    )
    price = df[df[NEG].notna()]
    out["RCE < 0 [kw.]"] = price.groupby(key)[NEG].sum()
    out["doby z RCE < 0"] = price[price[NEG] == 1].groupby(key)["business_date"].nunique()
    return out.fillna(0).astype(int)


def _magnitude(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for label, col, flag in (
        ("bilansowe", "pv_red_balance_mw", RED),
        ("sieciowe", "pv_red_network_mw", NET),
    ):
        v = df.loc[df[flag] == 1, col]
        rows[label] = {
            "kwadranse": len(v),
            "średnia": v.mean(),
            "p10": v.quantile(0.10),
            "mediana": v.median(),
            "p90": v.quantile(0.90),
            "maks.": v.max(),
        }
    return pd.DataFrame(rows).T


def _cooccurrence(df: pd.DataFrame) -> pd.DataFrame:
    both = df[df[RED].notna() & df[NEG].notna()]
    groups = {
        "ograniczenie bilansowe": both[RED] == 1,
        "tylko ograniczenie sieciowe": (both[RED] == 0) & (both[NET] == 1),
        "bez ograniczeń": both["y_red_any"] == 0,
    }
    rows = {
        name: {"kwadranse": int(mask.sum()), "P(RCE < 0)": both.loc[mask, NEG].mean()}
        for name, mask in groups.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def _missing(data: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "plan PSE": dataset.PLAN,
        "prognoza P2": dataset.P2,
        "pogoda": dataset.WEATHER,
        "cele ograniczeń": ["y_red_balance", "y_red_network"],
        "cel RCE": ["y_rce_neg"],
    }
    rows = {}
    for name, cols in groups.items():
        miss = data[cols].isna().any(axis=1)
        days = data.loc[miss, "business_date"]
        rows[name] = {
            "kwadranse z brakiem": int(miss.sum()),
            "doby": days.nunique(),
            "od": str(days.min()) if len(days) else "—",
            "do": str(days.max()) if len(days) else "—",
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def target_stats(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = _prepare(data)
    known = df[df[RED].notna()]
    hourly = pd.DataFrame(
        {
            "ogr. bilansowe": known.groupby("hour_local")[RED].mean() * 100,
            "ogr. sieciowe": known.groupby("hour_local")[NET].mean() * 100,
            "RCE < 0": df[df[NEG].notna()].groupby("hour_local")[NEG].mean() * 100,
        }
    )
    summary = pd.DataFrame(
        {
            "wartość": {
                "kwadranse w zbiorze": len(df),
                "doby w zbiorze": df["business_date"].nunique(),
                "pierwsza doba": df["business_date"].min(),
                "ostatnia doba": df["business_date"].max(),
                "ostatnia doba z celami ograniczeń": known["business_date"].max(),
                "kwadranse z celami ograniczeń": len(known),
                "udział kw. z ogr. bilansowym [%]": round(known[RED].mean() * 100, 2),
                "udział kw. z ogr. sieciowym [%]": round(known[NET].mean() * 100, 2),
                "udział kw. z RCE < 0 [%]": round(df[NEG].mean() * 100, 2),
                "anomalie pv = 0 (wyzerowane)": int(df["red_pv0_anomaly"].astype(float).sum()),
            }
        }
    )
    return {
        "Podsumowanie": summary,
        "Cele wg lat": _counts(df, "year"),
        "Cele wg miesięcy": _counts(df, "ym"),
        "Wielkość ograniczeń PV [MW] (kwadranse z ograniczeniem)": _magnitude(df),
        "Ceny ujemne a ograniczenia": _cooccurrence(df),
        "Udział kwadransów wg godziny lokalnej [%]": hourly,
        "Braki": _missing(data),
    }


def _cell(v) -> str:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return "—"
    if isinstance(v, float):
        if v.is_integer():
            return f"{v:,.0f}".replace(",", " ")
        return f"{v:.3f}" if abs(v) < 1 else f"{v:,.1f}".replace(",", " ")
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    return str(v)


def to_markdown(tables: dict[str, pd.DataFrame]) -> str:
    lines = [
        "# I1 — statystyki celów zbioru uczącego inż",
        "",
        "Wygenerowano: `uv run kse-inz dataset`. Kwadranse (15 min), doby handlowe.",
        "Ograniczenia: raport `poze-redoze` po regule czyszczenia (ograniczenie przy `pv = 0`",
        "wyzerowane). Cele ograniczeń tylko dla kwadransów z wykonaniem KSE.",
        "",
    ]
    for title, table in tables.items():
        lines += [f"## {title}", "", "| | " + " | ".join(map(str, table.columns)) + " |"]
        lines.append("|---" * (len(table.columns) + 1) + "|")
        for idx, row in table.iterrows():
            cells = [_cell(v.item() if hasattr(v, "item") else v) for v in row]
            lines.append(f"| {idx} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def make_figures(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    from p2 import plots

    monthly = tables["Cele wg miesięcy"][
        ["ogr. bilansowe [kw.]", "ogr. sieciowe [kw.]", "RCE < 0 [kw.]"]
    ]
    plots.monthly_chart(
        monthly,
        {
            "ogr. bilansowe [kw.]": "ograniczenie bilansowe PV",
            "ogr. sieciowe [kw.]": "ograniczenie sieciowe PV",
            "RCE < 0 [kw.]": "RCE < 0",
        },
        "Liczba kwadransów z ograniczeniem PV i z ceną ujemną wg miesiąca",
        out_dir / "i1_cele_miesiace.png",
        ylabel="kwadranse",
    )
    plots.profile_chart(
        tables["Udział kwadransów wg godziny lokalnej [%]"],
        "Udział kwadransów z ograniczeniem PV i z ceną ujemną wg godziny",
        out_dir / "i1_cele_godziny.png",
        ylabel="% kwadransów",
    )
