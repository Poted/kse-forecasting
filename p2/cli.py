"""CLI modeli P2.

uv run kse-p2 backtest            # walidacja krocząca, zapis do bazy, metryki, wykresy
uv run kse-p2 backtest --no-save  # bez zapisu do bazy
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from common import db
from common.config import PROJECT_ROOT, load_settings
from p2 import backtest, features

log = logging.getLogger("kse-p2")
FIG_DIR = PROJECT_ROOT / "docs" / "fig"
MODEL_PATH = PROJECT_ROOT / "models" / "p2_lightgbm.txt"
LABELS = {
    "naive_d1": "naive_d1 (D−1)",
    "naive_week": "naive_week (T−7)",
    "lightgbm": "LightGBM",
    "PSE (plan dobowy)": "PSE (plan dobowy)*",
}


def _fmt(v) -> str:
    if pd.isna(v):
        return "—"
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 10 else f"{v:.2f}"


def metrics_markdown(periods: dict[str, pd.DataFrame], importance: pd.Series, n_rows: int) -> str:
    cols = ["MAE", "RMSE", "MAPE", "bias", "MAE_szczyt", "MAE_min_poludnie", "n"]
    lines = [
        "# P2.5 — metryki modeli zapotrzebowania netto",
        "",
        "Wygenerowano: `uv run kse-p2 backtest`. Prognoza w dniu D o 12:00 na godziny doby D+1.",
        "Walidacja krocząca, LightGBM douczany co miesiąc. Wartości w MW, MAPE w %. Wspólny",
        "zbiór godzin: wszystkie modele i PSE mają prognozę i jest wykonanie.",
        "\\* PSE: plan dobowy publikowany ok. 16:00 dnia D (po momencie prognozy P2) — benchmark.",
        "",
    ]
    for name, table in periods.items():
        lines += [
            f"## {name}",
            "",
            "| model | " + " | ".join(cols) + " |",
            "|---" * (len(cols) + 1) + "|",
        ]
        for idx, row in table.iterrows():
            lines.append(
                f"| {LABELS.get(idx, idx)} | " + " | ".join(_fmt(row[c]) for c in cols) + " |"
            )
        lines.append("")
    lines += [
        "## Ważność cech LightGBM (gain, model końcowy)",
        "",
        "| cecha | udział |",
        "|---|---|",
    ]
    share = importance / importance.sum()
    lines += [f"| `{k}` | {v:.1%} |" for k, v in share.items()]
    lines += ["", f"Godzin w zbiorze testowym: {n_rows}.", ""]
    return "\n".join(lines)


def make_figures(fc: pd.DataFrame, out_dir: Path) -> None:
    from p2 import plots

    by_month = backtest.mae_by(fc, "month")[["lightgbm", "PSE", "naive_d1", "naive_week"]]
    by_month.columns = ["LightGBM", "PSE (plan dobowy)", "naive D−1", "naive T−7"]
    plots.monthly_chart(
        by_month,
        {c: c for c in by_month.columns},
        "MAE prognozy netto wg miesiąca: modele P2 i PSE",
        out_dir / "p2_5_mae_miesiace.png",
    )
    by_hour = backtest.mae_by(fc, "hour_local")[["lightgbm", "PSE", "naive_d1", "naive_week"]]
    by_hour.columns = ["LightGBM", "PSE", "naive D−1", "naive T−7"]
    plots.profile_chart(by_hour, "MAE prognozy netto wg godziny", out_dir / "p2_5_mae_godziny.png")
    week = fc[
        (fc["target_date"] >= pd.Timestamp("2026-06-08").date())
        & (fc["target_date"] <= pd.Timestamp("2026-06-14").date())
    ]
    if not week.empty:
        frame = week.set_index("hour_utc")[["y", "lightgbm", "net_demand_pse"]]
        frame.columns = ["wykonanie", "LightGBM", "PSE"]
        plots.series_chart(
            frame,
            "Tydzień 8–14.06.2026: wykonanie i prognozy netto",
            out_dir / "p2_5_tydzien_czerwiec.png",
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kse-p2", description="Modele P2")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_bt = sub.add_parser("backtest", help="walidacja krocząca i porównanie z PSE")
    p_bt.add_argument("--no-save", action="store_true", help="bez zapisu prognoz do bazy")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = db.make_engine(load_settings().database_url)
    db.init_schema(engine)
    actual, weather, pse = backtest.load_inputs(engine)
    res = backtest.run_backtest(actual, weather, pse)
    fc = res.forecasts
    log.info(
        "Prognozy: %d godzin, doby %s – %s",
        len(fc),
        fc["target_date"].min(),
        fc["target_date"].max(),
    )

    periods = backtest.evaluate_periods(fc)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "p2_5_metryki.md").write_text(
        metrics_markdown(periods, res.importance, len(fc)), encoding="utf-8"
    )
    make_figures(fc, FIG_DIR)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.final_model.booster_.save_model(str(MODEL_PATH))
    log.info("Model końcowy: %s (cechy: %d)", MODEL_PATH, len(features.FEATURES))
    if not args.no_save:
        run_ids = backtest.save_runs(engine, res, periods["całość"])
        log.info("Zapisane przebiegi: %s", run_ids)
    print(periods["całość"].round(2).to_string())


if __name__ == "__main__":
    main()
