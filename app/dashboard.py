"""Dashboard P2 (Streamlit): prognoza na jutro, jakość prognoz, analiza.

Uruchomienie: `uv run kse-app` (albo `docker compose up -d` — usługa `app`).
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

# Hosting (np. Streamlit Community Cloud) uruchamia `streamlit run app/dashboard.py`; pakiety
# projektu (`app`, `common`, `p2`) muszą być importowalne także bez instalacji projektu.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app import bootstrap, charts, data
from common import db, storage
from common.config import load_settings
from p2 import analysis, backtest, forecast

st.set_page_config(page_title="KSE — zapotrzebowanie netto", layout="wide")

# Bez paska narzędzi Plotly: na ekranach dotykowych jest stale widoczny i zasłania tytuły.
PLOT_CONFIG = {"displayModeBar": False}


@st.cache_resource
def engine():
    eng = db.make_engine(load_settings().database_url)
    db.init_schema(eng)  # tabele i widoki (nowa baza w chmurze jest pusta)
    return eng


def view_empty_database() -> None:
    """Pusta baza (np. nowa baza Neon): jednorazowe załadowanie danych z poziomu dashboardu."""
    st.subheader("Baza danych jest pusta")
    st.write(
        "Jednorazowo trzeba pobrać dane PSE i pogodę od 14.06.2024, załadować je do bazy, "
        "wykonać walidację modeli i prognozę na jutro. Trwa to ok. 10 minut — "
        "nie zamykaj strony do końca."
    )
    if st.button("Załaduj dane", type="primary"):
        with st.spinner("Pobieranie i ładowanie danych, walidacja modeli…"):
            summary = bootstrap.run(engine(), storage.DEFAULT_DATA_DIR)
        st.cache_data.clear()
        st.success(f"Gotowe: {summary.get('prognoza')} · {summary.get('walidacja')}")
        st.rerun()


@st.cache_data(ttl=600)
def cached_hourly() -> pd.DataFrame:
    return data.hourly_analysis(engine())


@st.cache_data(ttl=600)
def cached_quality(start, end) -> pd.DataFrame:
    return data.quality_frame(engine(), start, end)


@st.cache_data(ttl=60)
def cached_latest() -> pd.DataFrame:
    return forecast.latest_operational(engine())


def fmt(v: float) -> str:
    return "—" if pd.isna(v) else f"{v:,.0f}".replace(",", " ")


def view_tomorrow() -> None:
    st.subheader("Prognoza zapotrzebowania netto na jutro")
    st.caption(
        "Prognoza wykonywana w dniu D na 24 godziny doby D+1 z danych dostępnych o 12:00 dnia D "
        "(wykonanie do D−1, prognoza pogody wydana 48 h wcześniej, kalendarz). "
        "Plan PSE publikowany ok. 16:00 dnia D — pokazany do porównania."
    )
    if st.button(
        "Przelicz prognozę na jutro",
        type="primary",
        help="Pobiera najnowsze dane PSE i pogodę, uczy model i zapisuje prognozę",
    ):
        with st.spinner("Pobieranie danych i trening modelu (ok. 1 min)…"):
            res = forecast.run(engine(), update=True)
        st.cache_data.clear()
        st.success(
            f"Zapisano prognozę z {res.forecast_date} na {res.target_date} (przebieg {res.run_id})."
        )
        for w in res.warnings:
            st.warning(w)

    latest = cached_latest()
    if latest.empty:
        st.info("Brak prognozy. Użyj przycisku powyżej albo `uv run kse-p2 forecast`.")
        return
    run = data.run_info(engine(), int(latest["run_id"].iloc[0])) or {}
    target, made = latest["target_date"].iloc[0], latest["forecast_date"].iloc[0]
    cols = st.columns(4)
    cols[0].metric("Doba prognozy", str(target))
    cols[1].metric("Średnia prognoza netto", f"{fmt(latest['net_demand_hat'].mean())} MW")
    cols[2].metric("Minimum (godz.)", f"{fmt(latest['net_demand_hat'].min())} MW")
    cols[3].metric("Maksimum (godz.)", f"{fmt(latest['net_demand_hat'].max())} MW")
    created = (
        pd.Timestamp(run.get("created_at")).tz_convert("Europe/Warsaw")
        if run.get("created_at") is not None
        else None
    )
    st.caption(
        f"Wykonana w dniu {made}"
        + (f", przeliczona {created:%Y-%m-%d %H:%M}" if created is not None else "")
        + f"; przebieg {run.get('run_id')}, kod {run.get('code_version') or '—'}."
    )
    for w in (run.get("train_info") or {}).get("warnings", []):
        st.warning(w)
    st.plotly_chart(
        charts.forecast_chart(latest, f"Doba {target}: prognoza netto"),
        width="stretch",
        config=PLOT_CONFIG,
    )
    table = pd.DataFrame(
        {
            "godzina": latest["hour_utc"].dt.tz_convert("Europe/Warsaw").dt.strftime("%H:%M"),
            "LightGBM [MW]": latest["net_demand_hat"].round(0),
            "PSE [MW]": latest["net_demand_pse"].round(0),
            "wykonanie [MW]": latest["net_demand"].round(0),
        }
    )
    with st.expander("Tabela godzinowa"):
        st.dataframe(table, hide_index=True, width="stretch")


def view_quality() -> None:
    st.subheader("Jakość prognoz: prognoza vs wykonanie")
    rng = data.quality_range(engine())
    if rng is None:
        st.info("Brak prognoz historycznych. Uruchom `uv run kse-p2 backtest`.")
        return
    lo, hi = rng
    chosen = st.date_input(
        "Okres (doby docelowe)",
        value=(max(lo, hi - timedelta(days=90)), hi),
        min_value=lo,
        max_value=hi,
    )
    if not isinstance(chosen, tuple) or len(chosen) != 2:
        st.info("Wybierz początek i koniec okresu.")
        return
    start, end = chosen
    fc = cached_quality(start, end)
    if fc.empty:
        st.info("Brak danych w wybranym okresie.")
        return
    table = backtest.evaluate(fc)
    table.index = [charts.MODEL_LABEL.get(i, i) for i in table.index]
    show = table[["MAE", "RMSE", "MAPE", "bias", "MAE_szczyt", "MAE_min_poludnie"]].rename(
        columns={
            "MAE_szczyt": "MAE w szczycie",
            "MAE_min_poludnie": "MAE w min. południowym",
            "MAPE": "MAPE [%]",
        }
    )
    st.dataframe(show.round(1), width="stretch")
    st.caption(
        f"Godzin: {len(fc)}. Wartości w MW. Prognozy modeli z walidacji kroczącej "
        "(P2.5); PSE publikuje plan ok. 4 h po momencie prognozy P2."
    )

    days = sorted(fc["target_date"].unique())
    week_end = st.select_slider("Tydzień kończący się dobą", options=days, value=days[-1])
    week = fc[
        (fc["target_date"] > week_end - timedelta(days=7)) & (fc["target_date"] <= week_end)
    ].set_index("hour_utc")
    series = week[["y", "lightgbm", "net_demand_pse"]].rename(columns=charts.MODEL_LABEL)
    series.index = series.index.tz_convert("Europe/Warsaw").tz_localize(None)
    st.plotly_chart(
        charts.lines(series, "Prognoza vs wykonanie"), width="stretch", config=PLOT_CONFIG
    )

    c1, c2 = st.columns(2)
    c1.plotly_chart(
        charts.by_group_mae(
            backtest.mae_by(fc, "hour_local"), "MAE wg godziny", "godzina (czas lokalny)"
        ),
        width="stretch",
        config=PLOT_CONFIG,
    )
    by_month = backtest.mae_by(fc, "month")
    by_month.index = by_month.index.astype(str)
    c2.plotly_chart(
        charts.by_group_mae(by_month, "MAE wg miesiąca", "miesiąc"),
        width="stretch",
        config=PLOT_CONFIG,
    )


def view_analysis() -> None:
    st.subheader("Analiza zapotrzebowania netto")
    df = cached_hourly()
    st.caption(
        f"Dane: doby {df['business_date'].min()} – {df['business_date'].max()}, pełne "
        "godziny. Netto = zapotrzebowanie − generacja PV. Godzina lokalna = początek godziny."
    )
    c1, c2 = st.columns(2)
    season = analysis.daily_profile(df, "season")
    season.columns = [str(c) for c in season.columns]
    c1.plotly_chart(
        charts.lines(season, "Profil dobowy netto wg pory roku", "godzina", charts.SEASON_COLORS),
        width="stretch",
        config=PLOT_CONFIG,
    )
    june = analysis.june_profiles(df)
    june.columns = [str(c) for c in june.columns]
    c2.plotly_chart(
        charts.lines(june, "Krzywa kaczki: netto w czerwcu, kolejne lata", "godzina"),
        width="stretch",
        config=PLOT_CONFIG,
    )
    duck = analysis.duck_depth(df)[["evening_max", "midday_min"]]
    duck.index = duck.index.astype(str)
    duck.columns = ["maks. wieczorem (17–22)", "min. w południe (9–16)"]
    st.plotly_chart(
        charts.lines(
            duck,
            "Dobowe minimum południowe i maksimum wieczorne netto (średnie miesięczne)",
            "miesiąc",
            markers=True,
        ),
        width="stretch",
        config=PLOT_CONFIG,
    )
    monthly = analysis.monthly_means(df)
    monthly.index = monthly.index.astype(str)
    monthly.columns = ["zapotrzebowanie", "generacja PV", "netto"]
    st.plotly_chart(
        charts.lines(monthly, "Średnie miesięczne", "miesiąc", markers=True),
        width="stretch",
        config=PLOT_CONFIG,
    )


def sources() -> None:
    with st.sidebar:
        st.markdown("### Źródła danych")
        st.markdown(
            "- **PSE S.A.** — raporty API [api.raporty.pse.pl](https://api.raporty.pse.pl): "
            "wykonanie KSE (`his-wlk-cal`), plan koordynacyjny dobowy (`pdgopkd`).\n"
            "- **Open-Meteo** — [open-meteo.com](https://open-meteo.com), Previous Runs API; "
            "dane na licencji [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).\n"
            "- Święta: pakiet `holidays`."
        )
        st.caption("Dane PSE w wersji z dnia pobrania (PSE koryguje dane wstecz).")


sources()
if bootstrap.db_is_empty(engine()):
    view_empty_database()
    st.stop()
tab1, tab2, tab3 = st.tabs(["Prognoza na jutro", "Jakość prognoz", "Analiza"])
with tab1:
    view_tomorrow()
with tab2:
    view_quality()
with tab3:
    view_analysis()
