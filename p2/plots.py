"""Wykresy P2.4 (matplotlib, PNG do dokumentacji).

Paleta: kategoryczna, stała kolejność (niebieski, pomarańczowy, morski, żółty), sprawdzona
walidatorem palety (separacja dla daltonizmu). Dwa ostatnie kolory mają kontrast < 3:1
względem tła, dlatego linie mają etykiety bezpośrednie, a wartości są też w tabelach.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from p2 import analysis  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "legend.frameon": False,
        "font.size": 10,
        "lines.linewidth": 2,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    }
)


def _thousands(ax) -> None:
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " "))
    )


def _end_labels(ax, x, ends: list[tuple[str, float]]) -> None:
    """Etykiety na końcach linii, rozsunięte w pionie, żeby się nie nakładały."""
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.045
    placed: list[float] = []
    for label, y in sorted(ends, key=lambda t: t[1]):
        if placed and y - placed[-1] < gap:
            y = placed[-1] + gap
        placed.append(y)
        ax.annotate(
            label,
            (x, y),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            color=TEXT_2,
            annotation_clip=False,
        )


def _legend(ax, n: int) -> None:
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=n, borderaxespad=0.2)


def _profile_chart(
    profile: pd.DataFrame, title: str, path: Path, ylabel="MW", zero_line: bool = False
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ends = []
    for color, col in zip(SERIES, profile.columns, strict=False):
        s = profile[col]
        ax.plot(s.index, s.values, color=color, label=str(col))
        ends.append((str(col), float(s.values[-1])))
    if zero_line:
        ax.axhline(0, color=TEXT_2, linewidth=1)
    _end_labels(ax, profile.index[-1], ends)
    ax.set_title(title, pad=28)
    ax.set_xlabel("godzina (czas lokalny, początek godziny)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(0, 25.5)
    _thousands(ax)
    _legend(ax, len(profile.columns))
    fig.savefig(path)
    plt.close(fig)


def _monthly_chart(
    frame: pd.DataFrame,
    labels: dict[str, str],
    title: str,
    path: Path,
    ylabel="MW",
    zero_line: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = frame.index.to_timestamp()
    for color, (col, label) in zip(SERIES, labels.items(), strict=False):
        ax.plot(x, frame[col], color=color, label=label, marker="o", markersize=4)
    if zero_line:
        ax.axhline(0, color=TEXT_2, linewidth=1)
    ax.set_title(title, pad=28)
    ax.set_ylabel(ylabel)
    _thousands(ax)
    _legend(ax, len(labels))
    fig.savefig(path)
    plt.close(fig)


def _fmt(v: float) -> str:
    return "—" if pd.isna(v) else f"{v:,.0f}".replace(",", " ")


def _md_table(frame: pd.DataFrame, index_name: str, pct: tuple[str, ...] = ()) -> str:
    cols = list(frame.columns)
    lines = [
        f"| {index_name} | " + " | ".join(map(str, cols)) + " |",
        "|---" * (len(cols) + 1) + "|",
    ]
    for idx, row in frame.iterrows():
        cells = [f"{row[c]:.2f}" if c in pct and pd.notna(row[c]) else _fmt(row[c]) for c in cols]
        lines.append(f"| {idx} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_all(df: pd.DataFrame, out_dir: Path) -> dict[str, pd.DataFrame]:
    """Tworzy wszystkie wykresy P2.4 i plik z tabelami. Zwraca tabele (do notebooka)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}

    season = analysis.daily_profile(df, "season")
    tables["profil_sezon"] = season
    _profile_chart(
        season,
        "Zapotrzebowanie netto — średni profil dobowy wg pory roku",
        out_dir / "p2_4_profil_sezonowy_netto.png",
    )

    june = analysis.june_profiles(df)
    tables["kaczka_czerwiec"] = june
    _profile_chart(
        june,
        "Krzywa kaczki: zapotrzebowanie netto w czerwcu, kolejne lata",
        out_dir / "p2_4_krzywa_kaczki_czerwiec.png",
    )

    last_june = df[df["month"] == pd.Period(f"{june.columns.max()}-06", "M")]
    comp = analysis.daily_profile(last_june.assign(k="x"), "k", "demand").rename(
        columns={"x": "zapotrzebowanie"}
    )
    comp["generacja PV"] = analysis.daily_profile(last_june.assign(k="x"), "k", "pv")["x"]
    comp["netto"] = analysis.daily_profile(last_june.assign(k="x"), "k", "net_demand")["x"]
    tables["skladowe_czerwiec"] = comp
    _profile_chart(
        comp,
        f"Czerwiec {june.columns.max()}: zapotrzebowanie, PV i netto",
        out_dir / "p2_4_skladowe_czerwiec.png",
    )

    monthly = analysis.monthly_means(df)
    tables["miesiace"] = monthly
    _monthly_chart(
        monthly,
        {"demand": "zapotrzebowanie", "net_demand": "netto", "pv": "generacja PV"},
        "Średnie miesięczne: zapotrzebowanie, netto, PV",
        out_dir / "p2_4_srednie_miesieczne.png",
    )

    duck = analysis.duck_depth(df)
    tables["glebokosc_kaczki"] = duck
    _monthly_chart(
        duck,
        {"evening_max": "maks. wieczorem (17–22)", "midday_min": "min. w południe (9–16)"},
        "Krzywa kaczki: dobowe minimum południowe i maksimum wieczorne netto",
        out_dir / "p2_4_glebokosc_kaczki.png",
    )

    err = analysis.pse_errors(df)
    summary = analysis.pse_summary(err)
    tables["pse_metryki"] = summary
    by_hour = analysis.error_by(err, "hour_local")
    by_month = analysis.error_by(err, "month")
    tables["pse_godziny"] = by_hour
    tables["pse_miesiace"] = by_month

    _profile_chart(
        by_hour,
        "Błąd prognozy PSE netto wg godziny (prognoza − wykonanie)",
        out_dir / "p2_4_blad_pse_godziny.png",
        zero_line=True,
    )
    _monthly_chart(
        by_month,
        {"MAE": "MAE", "bias": "bias"},
        "Błąd prognozy PSE netto wg miesiąca (prognoza − wykonanie)",
        out_dir / "p2_4_blad_pse_miesiace.png",
        zero_line=True,
    )

    period = f"{df['business_date'].min()} – {df['business_date'].max()}"
    text = [
        "# P2.4 — tabele",
        "",
        f"Wygenerowano: `uv run python -m p2.analysis`. Dane: doby {period}, tylko pełne godziny.",
        "Wartości w MW (MAPE w %). Błąd = prognoza − wykonanie.",
        "",
        "## Średni profil dobowy netto wg pory roku",
        _md_table(season.round(0), "godzina"),
        "",
        "## Netto w czerwcu, kolejne lata",
        _md_table(june.round(0), "godzina"),
        "",
        "## Głębokość krzywej kaczki (średnie miesięczne)",
        _md_table(duck, "miesiąc"),
        "",
        "## Prognoza PSE z planu dobowego — metryki",
        _md_table(summary, "wielkość", pct=("MAPE",)),
        "",
        "## Błąd PSE netto wg godziny",
        _md_table(by_hour, "godzina"),
        "",
        "## Błąd PSE netto wg miesiąca",
        _md_table(by_month, "miesiąc"),
        "",
    ]
    (out_dir / "p2_4_tabele.md").write_text("\n".join(text), encoding="utf-8")
    return tables
