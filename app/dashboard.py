"""Dashboard (Streamlit): widoki P2 (zapotrzebowanie netto) i inż (ryzyko nadpodaży PV).

Uruchomienie: `uv run kse-app` (albo `docker compose up -d` — usługa `app`).
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

# Hosting (np. Streamlit Community Cloud) uruchamia `streamlit run app/dashboard.py`; pakiety
# projektu (`app`, `common`, `p2`) muszą być importowalne także bez instalacji projektu.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Streamlit przeładowuje po zmianie tylko moduły z katalogu skryptu (`app/`) albo z PYTHONPATH.
# Bez tego po aktualizacji kodu w chmurze `p2/` i `common/` zostawały w pamięci w starej wersji.
_paths = [x for x in os.environ.get("PYTHONPATH", "").split(os.pathsep) if x]
if str(ROOT) not in _paths:
    os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT), *_paths])

import pandas as pd
import streamlit as st

from app import bootstrap, charts, data, data_inz
from common import db, storage
from common.config import load_settings
from inz import forecast as inz_forecast
from p2 import analysis, backtest, forecast

st.set_page_config(page_title="KSE — zapotrzebowanie netto i ryzyko nadpodaży", layout="wide")

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


@st.cache_data(ttl=600)
def cached_operational_eval() -> pd.DataFrame:
    return forecast.operational_eval(engine())


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


def view_history() -> None:
    st.subheader("Historia prognoz: prognoza na jutro vs wykonanie")
    st.caption(
        "Każda doba: ostatnia prognoza wykonana dzień wcześniej (przeliczenie automatyczne "
        "albo przycisk) porównana z wykonaniem PSE i z planem PSE. Doba pojawia się, gdy PSE "
        "opublikuje pełne wykonanie (ok. 00:00–02:00 następnego dnia)."
    )
    df = cached_operational_eval()
    daily = forecast.daily_summary(df)
    if daily.empty:
        st.info(
            "Brak dób z pełnym wykonaniem. Pierwsza porównana doba pojawi się dzień po prognozie."
        )
        return
    cols = st.columns(3)
    cols[0].metric("Porównanych dób", len(daily))
    cols[1].metric("MAE LightGBM", f"{fmt(daily['MAE_lightgbm'].mean())} MW")
    cols[2].metric("MAE PSE", f"{fmt(daily['MAE_pse'].mean())} MW")

    frame = daily.set_index("target_date")[["MAE_lightgbm", "MAE_pse"]]
    frame.index = frame.index.astype(str)
    frame.columns = ["LightGBM", "PSE (plan dobowy)"]
    st.plotly_chart(
        charts.lines(frame, "Dzienny MAE prognozy netto", "doba", markers=True),
        width="stretch",
        config=PLOT_CONFIG,
    )

    st.markdown("**Wg wersji kodu** — postęp narzędzia")
    versions = forecast.version_summary(daily)
    versions["code_version"] = versions["code_version"].astype(object).fillna("—")
    st.dataframe(
        versions.rename(
            columns={
                "code_version": "wersja kodu",
                "first_day": "od doby",
                "days": "dób",
                "MAE_lightgbm": "MAE LightGBM",
                "MAE_pse": "MAE PSE",
            }
        ).round(1),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Tabela dzienna"):
        st.dataframe(
            daily.rename(
                columns={
                    "target_date": "doba",
                    "code_version": "wersja kodu",
                    "hours": "godzin",
                    "MAE_lightgbm": "MAE LightGBM",
                    "MAE_pse": "MAE PSE",
                    "bias_lightgbm": "bias LightGBM",
                }
            )
            .sort_values("doba", ascending=False)
            .round(1),
            hide_index=True,
            width="stretch",
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


# --- widoki inż: ryzyko nadpodaży ---------------------------------------------

MODEL_NAMES = {
    "baseline_kalendarz": "baseline: kalendarz",
    "baseline_plan": "baseline: reguła z planu PSE",
    "baseline_jak_dzis": "baseline: jak dziś",
    "lightgbm": "LightGBM",
    "lightgbm_2etapy": "LightGBM (regresja dwuetapowa)",
    "mlp": "MLP",
    "lstm": "LSTM",
}
SCHEME_NAMES = {"staly": "trening ≤ 2025", "kroczacy": "krocząca"}
INZ_SETUP = "Uruchom `uv run kse-inz init` (zbiór uczący, eksperymenty, prognoza)."


@st.cache_data(ttl=60)
def cached_risk(goal: str) -> pd.DataFrame:
    return inz_forecast.latest(engine(), goal)


@st.cache_data(ttl=600)
def cached_quarters(start, end) -> pd.DataFrame:
    return data_inz.quarters(engine(), start, end)


@st.cache_data(ttl=600)
def cached_comparison() -> dict:
    return data_inz.comparison(engine())


def _hhmm(dtime_utc: pd.Series) -> pd.Series:
    return data_inz.local_time(dtime_utc).dt.strftime("%H:%M")


def view_risk() -> None:
    st.subheader("Ryzyko nadpodaży energii z PV na jutro")
    st.caption(
        "Dla każdego kwadransu doby D+1: prawdopodobieństwo i wielkość nierynkowego ograniczenia "
        "(redysponowania bilansowego) generacji PV — liczone po publikacji planu PSE (ok. 16:00 "
        "dnia D) — oraz prawdopodobieństwo ujemnej ceny RCE — liczone z danych dostępnych "
        "o 12:00 dnia D."
    )
    if st.button(
        "Przelicz prognozę ryzyka",
        type="primary",
        help="Pobiera najnowsze dane, uczy modele i zapisuje brakujące prognozy na jutro. "
        "Wymaga prognozy P2 na jutro (zakładka „Prognoza na jutro”).",
    ):
        with st.spinner("Pobieranie danych i trening modeli (ok. 1 min)…"):
            res = inz_forecast.run(engine(), update=True)
        st.cache_data.clear()
        done = ", ".join(res.run_ids) or "bez nowych prognoz"
        st.success(f"Prognoza z {res.forecast_date} na {res.target_date}: {done}.")
        for w in res.warnings:
            st.warning(w)

    c1, c2 = cached_risk("c1"), cached_risk("c2")
    if c1.empty and c2.empty:
        st.info("Brak prognozy. Użyj przycisku powyżej albo `uv run kse-inz forecast`.")
        return

    def target_of(df):
        return None if df.empty else df["business_date"].iloc[0]

    days = {d for d in (target_of(c1), target_of(c2)) if d is not None}
    day = max(days)
    if len(days) > 1:
        st.warning(
            f"Prognozy dotyczą różnych dób (ograniczenia: {target_of(c1)}, ceny: {target_of(c2)}) "
            f"— plan PSE na {day} nie był jeszcze opublikowany. Pokazana doba: {day}."
        )
    c1 = c1[c1["business_date"] == day] if not c1.empty else c1
    c2 = c2[c2["business_date"] == day] if not c2.empty else c2

    cols = st.columns(4)
    cols[0].metric("Doba prognozy", str(day))
    threshold = None
    if not c1.empty:
        threshold = (c1["params"].iloc[0] or {}).get("threshold")
        cols[1].metric("Maks. prawdopodobieństwo ograniczenia PV", f"{c1['p_hat'].max():.0%}")
        energy = c1["mw_hat"].sum() * 0.25
        cols[2].metric(
            "Prognozowane ograniczenie",
            f"{fmt(energy)} MWh",
            help=f"maksimum {fmt(c1['mw_hat'].max())} MW",
        )
    if not c2.empty:
        cols[3].metric("Maks. prawdopodobieństwo ceny ujemnej", f"{c2['p_hat'].max():.0%}")

    if not c1.empty and threshold is not None:
        periods = data_inz.risk_periods(c1, threshold)
        if periods:
            text = ", ".join(f"{a}–{b}" for a, b in periods)
            st.error(f"Okresy zagrożenia nadpodażą (prawdopodobieństwo ≥ {threshold:.0%}): {text}")
        else:
            st.success(f"Brak okresów zagrożenia (prawdopodobieństwo wszędzie < {threshold:.0%}).")

    base = c1 if not c1.empty else c2
    prob = pd.DataFrame(index=_hhmm(base["dtime_utc"]))
    if not c1.empty:
        prob["ograniczenie PV"] = (c1["p_hat"] * 100).to_numpy()
    if not c2.empty:
        prob["ujemna cena RCE"] = (c2["p_hat"] * 100).to_numpy()
    st.plotly_chart(
        charts.lines(prob, f"Doba {day}: prawdopodobieństwo", "czas lokalny", unit="%"),
        width="stretch",
        config=PLOT_CONFIG,
    )
    if not c1.empty:
        mw = pd.DataFrame({"prognoza": c1["mw_hat"].to_numpy()}, index=_hhmm(c1["dtime_utc"]))
        st.plotly_chart(
            charts.lines(mw, f"Doba {day}: prognozowane ograniczenie PV", "czas lokalny"),
            width="stretch",
            config=PLOT_CONFIG,
        )
    for name, df in (("ograniczenia PV", c1), ("ceny ujemne", c2)):
        if df.empty:
            continue
        info = df["train_info"].iloc[0] or {}
        created = pd.Timestamp(df["created_at"].iloc[0]).tz_convert("Europe/Warsaw")
        st.caption(
            f"Model — {name}: przeliczono {created:%Y-%m-%d %H:%M}, przebieg "
            f"{int(df['run_id'].iloc[0])}, trening do {info.get('train_to')}, "
            f"kod {df['code_version'].iloc[0] or '—'}."
        )
        for w in info.get("warnings", []):
            st.warning(w)
    with st.expander("Tabela kwadransowa"):
        table = pd.DataFrame({"kwadrans": _hhmm(base["dtime_utc"]).to_numpy()})
        if not c1.empty:
            table["P(ograniczenie PV) [%]"] = (c1["p_hat"] * 100).round(1).to_numpy()
            table["ograniczenie PV [MW]"] = c1["mw_hat"].round(0).to_numpy()
        if not c2.empty:
            table["P(RCE < 0) [%]"] = (c2["p_hat"] * 100).round(1).to_numpy()
        st.dataframe(table, hide_index=True, width="stretch")


def view_episodes() -> None:
    st.subheader("Historyczne epizody nadpodaży")
    rng = data_inz.dataset_range(engine())
    if rng is None:
        st.info("Brak zbioru danych o ograniczeniach. " + INZ_SETUP)
        return
    lo, hi = rng
    chosen = st.date_input(
        "Okres",
        value=(max(lo, hi - timedelta(days=365)), hi),
        min_value=lo,
        max_value=hi,
        key="episodes_range",
    )
    if not isinstance(chosen, tuple) or len(chosen) != 2:
        st.info("Wybierz początek i koniec okresu.")
        return
    frame = cached_quarters(*chosen)
    table = data_inz.episodes(frame)
    if table.empty:
        st.info("W wybranym okresie nie było ograniczeń bilansowych PV.")
        return
    cols = st.columns(4)
    cols[0].metric("Doby z ograniczeniem", len(table))
    cols[1].metric("Ograniczona energia", f"{fmt(table['energia_mwh'].sum() / 1000)} GWh")
    cols[2].metric("Największe ograniczenie", f"{fmt(table['maks_mw'].max())} MW")
    cols[3].metric("Kwadranse z ceną < 0", fmt(frame["y_rce_neg"].sum()))
    st.caption(
        "Ograniczenie = nierynkowe redysponowanie bilansowe PV (raport PSE `poze-redoze`). "
        "Prognoza: operacyjna, a dla dób wcześniejszych — z walidacji kroczącej (od 01.2026)."
    )
    show = table.rename(
        columns={
            "business_date": "doba",
            "energia_mwh": "energia [MWh]",
            "maks_mw": "maks. [MW]",
            "kwadranse": "kwadranse",
            "kwadranse_rce_ujemne": "kw. z RCE < 0",
            "rce_min": "RCE min [zł/MWh]",
            "prognoza_mwh": "prognoza [MWh]",
            "prognoza_maks_p": "prognoza: maks. P",
        }
    )
    st.dataframe(show.round(2).head(50), hide_index=True, width="stretch")

    day = st.selectbox("Doba (kolejność: od największego epizodu)", list(table["business_date"]))
    one = frame[frame["business_date"] == day]
    x = _hhmm(one["dtime_utc"])
    mw = pd.DataFrame(
        {
            "wykonanie": one["pv_red_balance_mw"].to_numpy(),
            "prognoza": one["mw_c1"].to_numpy(),
            "plan PSE: generacja PV": one["gen_fv"].to_numpy(),
        },
        index=x,
    ).dropna(axis=1, how="all")
    c1, c2 = st.columns(2)
    c1.plotly_chart(
        charts.lines(mw, f"{day}: ograniczenie PV i planowana generacja PV", "czas lokalny"),
        width="stretch",
        config=PLOT_CONFIG,
    )
    price = pd.DataFrame({"RCE": one["rce_pln"].to_numpy()}, index=x)
    c2.plotly_chart(
        charts.lines(price, f"{day}: cena RCE", "czas lokalny", unit="zł/MWh"),
        width="stretch",
        config=PLOT_CONFIG,
    )
    prob = pd.DataFrame(
        {
            "ograniczenie PV": (one["p_c1"] * 100).to_numpy(),
            "ujemna cena RCE": (one["p_c2"] * 100).to_numpy(),
        },
        index=x,
    ).dropna(axis=1, how="all")
    if not prob.empty:
        st.plotly_chart(
            charts.lines(prob, f"{day}: prognozowane prawdopodobieństwo", "czas lokalny", unit="%"),
            width="stretch",
            config=PLOT_CONFIG,
        )


def view_models() -> None:
    st.subheader("Porównanie modeli")
    tables = cached_comparison()
    if tables["c1"].empty and tables["c2"].empty:
        st.info("Brak przebiegów eksperymentów. " + INZ_SETUP)
        return
    st.caption(
        "Trening: doby do 31.12.2025; test: 2026. „Krocząca” — model douczany co miesiąc. "
        "AUC, AP — z prawdopodobieństwa; F1 — przy progu wyznaczonym na okresie treningowym; "
        "MAE [MW] — wszystkie kwadranse, MAE_ogr — kwadranse z ograniczeniem."
    )
    specs = (
        ("c1", "Cel 1: ograniczenie bilansowe PV", ["AUC", "AP", "F1", "MAE", "MAE_ogr"]),
        ("c2", "Cel 2: ujemna cena RCE (prognoza o 12:00 dnia D)", ["AUC", "AP", "F1"]),
    )
    for key, title, columns in specs:
        table = tables[key]
        if table.empty:
            continue
        st.markdown(f"**{title}**")
        frame = table.reset_index()
        frame["schemat"] = pd.Categorical(frame["schemat"], list(SCHEME_NAMES), ordered=True)
        frame = frame.sort_values(["schemat", "AP"], ascending=[True, False])
        show = pd.DataFrame(
            {
                "model": frame["model"].map(lambda m: MODEL_NAMES.get(m, m)),
                "walidacja": frame["schemat"].map(SCHEME_NAMES),
                **{
                    c: frame[c].astype(float).round(3 if c in ("AUC", "AP", "F1") else 0)
                    for c in columns
                },
            }
        )
        st.dataframe(show, hide_index=True, width="stretch")
        static = frame[frame["schemat"] == "staly"].set_index("model")
        ap = pd.DataFrame(
            {"AP": static["AP"].astype(float).to_numpy()},
            index=[MODEL_NAMES.get(m, m) for m in static.index],
        )
        st.bar_chart(ap, horizontal=True, height=60 + 40 * len(ap))


def sources() -> None:
    with st.sidebar:
        st.markdown("### Źródła danych")
        st.markdown(
            "- **PSE S.A.** — raporty API [api.raporty.pse.pl](https://api.raporty.pse.pl): "
            "wykonanie KSE (`his-wlk-cal`), plan koordynacyjny dobowy (`pdgopkd`), "
            "redysponowanie OZE (`poze-redoze`), ceny RCE (`rce-pln`).\n"
            "- **Open-Meteo** — [open-meteo.com](https://open-meteo.com), Previous Runs API; "
            "dane na licencji [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).\n"
            "- Święta: pakiet `holidays`."
        )
        st.caption("Dane PSE w wersji z dnia pobrania (PSE koryguje dane wstecz).")


sources()
if bootstrap.db_is_empty(engine()):
    view_empty_database()
    st.stop()
TABS = {
    "Prognoza na jutro": view_tomorrow,
    "Historia prognoz": view_history,
    "Jakość prognoz": view_quality,
    "Analiza": view_analysis,
    "Ryzyko nadpodaży": view_risk,
    "Epizody nadpodaży": view_episodes,
    "Porównanie modeli": view_models,
}
for tab, view in zip(st.tabs(list(TABS)), TABS.values(), strict=True):
    with tab:
        view()
