"""CLI pracy inżynierskiej.

uv run kse-inz dataset            # zbiór uczący → tabela inz_dataset, statystyki celów, wykresy
uv run kse-inz c1                 # cel 1: modele bazowe i LightGBM, metryki, zapis przebiegów
uv run kse-inz nn                 # cel 1: sieci MLP i LSTM (wymaga: uv sync --group nn)
uv run kse-inz nn-import KATALOG  # wyniki sieci z plików (np. z Colaba) → baza, tabela metryk
Opcja --no-save: bez zapisu do bazy.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from common import db
from common.config import PROJECT_ROOT, load_settings
from inz import dataset, evaluate, experiment, models, stats

log = logging.getLogger("kse-inz")
FIG_DIR = PROJECT_ROOT / "docs" / "fig"
MODEL_DIR = PROJECT_ROOT / "models"
LABELS = {
    "baseline_kalendarz": "baseline: kalendarz",
    "baseline_plan": "baseline: reguła z planu PSE",
    "lightgbm": "LightGBM",
    "lightgbm_2etapy": "LightGBM (regresja dwuetapowa)",
    "mlp": "MLP",
    "lstm": "LSTM",
    "staly": "trening ≤ 2025",
    "kroczacy": "krocząca",
}
COLUMNS = ["AUC", "AP", "F1", "precyzja", "czułość", "próg", "MAE", "MAE_ogr"]
EXAMPLE_WEEK = ("2026-06-08", "2026-06-14")


def run_dataset(engine, save: bool, export: Path | None = None) -> None:
    inputs = dataset.load_inputs(engine)
    if inputs["p2_forecast"].empty:
        raise SystemExit("Brak historycznych prognoz P2 — najpierw: uv run kse-p2 backtest")
    data = dataset.build_dataset(**inputs)
    log.info(
        "Zbiór: %d kwadransów, doby %s – %s",
        len(data),
        data["business_date"].min(),
        data["business_date"].max(),
    )
    if save:
        log.info("Zapisano %d wierszy do inz_dataset", dataset.save(engine, data))
    if export:
        export.parent.mkdir(parents=True, exist_ok=True)
        data.to_parquet(export, index=False)
        log.info("Zbiór zapisany w pliku %s", export)
    tables = stats.target_stats(data)
    (FIG_DIR / "i1_statystyki.md").write_text(stats.to_markdown(tables), encoding="utf-8")
    stats.make_figures(tables, FIG_DIR)
    for name in ("Podsumowanie", "Cele wg lat", "Braki"):
        print(f"\n{name}\n{tables[name].to_string()}")


def _num(v, col: str) -> str:
    if pd.isna(v):
        return "—"
    if col in ("MAE", "MAE_ogr"):
        return f"{v:.1f}" if v < 100 else f"{v:,.0f}".replace(",", " ")
    if col in ("n", "n_ogr"):
        return f"{int(v):,}".replace(",", " ")
    return f"{v:.3f}"


def _metric_rows(table: pd.DataFrame, columns: list[str]) -> list[str]:
    lines = [
        "| model | walidacja | " + " | ".join(columns) + " |",
        "|---" * (len(columns) + 2) + "|",
    ]
    for (model, scheme), row in table.iterrows():
        cells = " | ".join(_num(row[c], c) for c in columns)
        lines.append(f"| {LABELS[model]} | {LABELS[scheme]} | {cells} |")
    return lines


def c1_markdown(results: list[experiment.Result]) -> str:
    first = results[0]
    days = first.test["business_date"]
    lines = [
        "# I2 — metryki modeli celu 1 (ograniczenia PV na kwadrans D+1)",
        "",
        "Wygenerowano: `uv run kse-inz c1`. Trening: doby ≤ 31.12.2025; test: "
        f"{days.min():%d.%m.%Y}–{days.max():%d.%m.%Y}.",
        "Walidacja krocząca: model dla miesiąca M uczony na dobach do końca miesiąca M−2.",
        "AUC, AP — z prawdopodobieństwa; F1, precyzja, czułość — przy progu wyznaczonym na okresie",
        "treningowym (prognozy krzyżowe). MAE [MW] — wszystkie kwadranse; MAE_ogr — kwadranse",
        "z ograniczeniem.",
        "",
    ]
    for res in results:
        m = res.metrics.iloc[0]
        lines += [
            f"## {res.target.label}",
            "",
            f"Kwadranse testowe: {_num(m['n'], 'n')}, z ograniczeniem: {_num(m['n_ogr'], 'n')} "
            f"({m['n_ogr'] / m['n']:.1%}). MAE prognozy zerowej: {res.zero_mae['MAE']:.1f} MW "
            f"(MAE_ogr {res.zero_mae['MAE_ogr']:.1f} MW).",
            "",
            "### Wszystkie kwadranse",
            "",
            *_metric_rows(res.metrics, COLUMNS),
            "",
            "### Kwadranse z planowaną generacją PV > 0",
            "",
            f"Kwadranse: {_num(res.metrics_day.iloc[0]['n'], 'n')}.",
            "",
            *_metric_rows(res.metrics_day, ["AUC", "AP", "F1", "MAE"]),
            "",
            "### LightGBM wg miesięcy (trening ≤ 2025)",
            "",
        ]
        part = res.predictions[
            (res.predictions["model"] == "lightgbm") & (res.predictions["schemat"] == "staly")
        ].merge(res.test[["dtime_utc", res.target.flag, res.target.mw]], on="dtime_utc")
        monthly = evaluate.by_month(
            part, res.target.flag, res.target.mw, res.thresholds["lightgbm"]
        )
        cols = ["n_ogr", "AUC", "AP", "F1", "MAE", "MAE_ogr"]
        lines += ["| miesiąc | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
        lines += [
            f"| {idx} | " + " | ".join(_num(row[c], c) for c in cols) + " |"
            for idx, row in monthly.iterrows()
        ]
        top = (
            res.fitted["lightgbm"]
            .importance()
            .sort_values("klasyfikator", ascending=False)
            .head(12)
        )
        lines += [
            "",
            "### Ważność cech LightGBM (gain, 12 najważniejszych dla klasyfikatora)",
            "",
            "| cecha | klasyfikator | regresor |",
            "|---|---|---|",
            *[
                f"| `{k}` | {r['klasyfikator']:.1%} | {r['regresor']:.1%} |"
                for k, r in top.iterrows()
            ],
            "",
        ]
    return "\n".join(lines)


def c1_figures(res: experiment.Result, out_dir: Path) -> None:
    from inz import plots as iplots
    from p2 import plots

    key = res.target.key
    static = res.predictions[res.predictions["schemat"] == "staly"]
    wide_p = static.pivot(index="dtime_utc", columns="model", values="p_hat")
    truth = res.test.set_index("dtime_utc")
    names = ["lightgbm", "baseline_plan", "baseline_kalendarz"]
    ap = res.metrics.xs("staly", level="schemat")["AP"]
    iplots.pr_curves(
        truth[res.target.flag].reindex(wide_p.index),
        {f"{LABELS[n]} (AP {ap[n]:.2f})": wide_p[n] for n in names},
        f"Precyzja–czułość, {res.target.label}, test 2026",
        out_dir / f"i2_pr_{key}.png",
    )
    wide_mw = static.pivot(index="dtime_utc", columns="model", values="mw_hat")
    days = pd.to_datetime(truth["business_date"])
    week = truth[(days >= EXAMPLE_WEEK[0]) & (days <= EXAMPLE_WEEK[1])]
    if not week.empty:
        frame = pd.DataFrame(
            {
                "wykonanie": week[res.target.mw],
                "LightGBM": wide_mw["lightgbm"].reindex(week.index),
                "LightGBM dwuetapowy": wide_mw["lightgbm_2etapy"].reindex(week.index),
                "reguła z planu PSE": wide_mw["baseline_plan"].reindex(week.index),
            }
        )
        plots.series_chart(
            frame,
            f"Tydzień 8–14.06.2026: {res.target.label} [MW], wykonanie i prognozy",
            out_dir / f"i2_tydzien_{key}.png",
        )


def run_c1(engine, save: bool) -> None:
    data = dataset.read(engine)
    if data.empty:
        raise SystemExit("Brak zbioru uczącego — najpierw: uv run kse-inz dataset")
    results = []
    for target in models.TARGETS.values():
        res = experiment.run(data, target)
        results.append(res)
        log.info("%s: progi %s", target.label, {k: round(v, 3) for k, v in res.thresholds.items()})
        c1_figures(res, FIG_DIR)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        res.fitted["lightgbm"].clf_.booster_.save_model(
            str(MODEL_DIR / f"inz_c1_{target.key}_clf.txt")
        )
        res.fitted["lightgbm"].reg_.booster_.save_model(
            str(MODEL_DIR / f"inz_c1_{target.key}_reg.txt")
        )
        if save:
            log.info("Zapisane przebiegi: %s", experiment.save(engine, res))
        print(f"\n{target.label}\n{res.metrics[COLUMNS].round(3).to_string()}")
    (FIG_DIR / "i2_metryki.md").write_text(c1_markdown(results), encoding="utf-8")


NN_PREFIX = "i3"
MODEL_ORDER = ["baseline_kalendarz", "baseline_plan", "lightgbm", "lightgbm_2etapy", "mlp", "lstm"]


def seed_spread(data: pd.DataFrame, target, thresholds: dict, n_seeds: int) -> list[dict]:
    """Rozrzut metryk sieci dla kolejnych ziaren losowych (trening ≤ 2025, test 2026)."""
    from inz import nn

    _, train, test = experiment.split(data, target)
    rows = []
    for cls in nn.MODELS:
        for seed in range(models.SEED, models.SEED + n_seeds):
            out = cls(seed=seed).fit(train, target).predict(test)
            m = evaluate.metrics(
                test[target.flag],
                test[target.mw],
                out["p_hat"],
                out["mw_hat"],
                thresholds[cls.name],
            )
            rows.append(
                {"model": cls.name, "seed": seed, **{k: m[k] for k in ("AUC", "AP", "F1", "MAE")}}
            )
            log.info("%s, ziarno %d: AP %.3f, MAE %.1f", cls.name, seed, m["AP"], m["MAE"])
    return rows


def i3_markdown(table: pd.DataFrame, target, payload: dict) -> str:
    order = {name: i for i, name in enumerate(MODEL_ORDER)}
    table = table.loc[
        sorted(table.index, key=lambda k: (experiment.SCHEMES.index(k[1]), order.get(k[0], 99)))
    ]
    lines = [
        "# I3 — metryki modeli celu 1: modele bazowe, LightGBM, MLP, LSTM",
        "",
        "Wygenerowano: `uv run kse-inz nn` albo `uv run kse-inz nn-import`. Wiersze modeli",
        "bazowych i LightGBM: ostatnie przebiegi `uv run kse-inz c1`. Cel: " + target.label + ".",
        "Trening: doby ≤ 31.12.2025; test: 2026. Opis kolumn: `docs/fig/i2_metryki.md`.",
        f"Sieci: wersja kodu `{payload.get('code_version')}`,"
        f" urządzenie `{payload.get('device')}`.",
        "",
        *_metric_rows(table, COLUMNS),
        "",
    ]
    seeds = pd.DataFrame(payload.get("seeds") or [])
    if not seeds.empty:
        lines += [
            f"## Rozrzut wyników sieci: {seeds['seed'].nunique()} ziaren losowych (trening ≤ 2025)",
            "",
            "| model | metryka | średnia | odch. std. | min | maks |",
            "|---|---|---|---|---|---|",
        ]
        for name, group in seeds.groupby("model", sort=False):
            for col in ("AUC", "AP", "F1", "MAE"):
                v = group[col]
                cells = " | ".join(_num(x, col) for x in (v.mean(), v.std(), v.min(), v.max()))
                lines.append(f"| {LABELS[name]} | {col} | {cells} |")
        lines.append("")
    return "\n".join(lines)


def _publish_nn(engine, res: experiment.Result, payload: dict) -> None:
    """Zapis przebiegów sieci w bazie i wspólna tabela metryk (I2 + sieci)."""
    run_ids = experiment.save(engine, res, version=payload.get("code_version"))
    log.info("Zapisane przebiegi: %s", run_ids)
    table = experiment.latest_metrics(engine, res.target)
    (FIG_DIR / "i3_metryki.md").write_text(
        i3_markdown(table, res.target, payload), encoding="utf-8"
    )
    print(table[COLUMNS].round(3).to_string())


def run_nn(args) -> None:
    try:
        import torch
    except ModuleNotFoundError:
        raise SystemExit("Brak PyTorch — zainstaluj: uv sync --group nn") from None

    from inz import nn

    target = models.TARGETS[args.target]
    engine = None
    if args.data:
        data = pd.read_parquet(args.data)
        data["dtime_utc"] = pd.to_datetime(data["dtime_utc"], utc=True)
        data["business_date"] = pd.to_datetime(data["business_date"]).dt.date
    else:
        engine = _engine()
        data = dataset.read(engine)
    if data.empty:
        raise SystemExit("Brak zbioru uczącego — najpierw: uv run kse-inz dataset")
    res = experiment.run(data, target, model_classes=nn.MODELS)
    print(f"\n{target.label}\n{res.metrics[COLUMNS].round(3).to_string()}")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in res.fitted.items():
        path = MODEL_DIR / f"inz_c1_{target.key}_{name}.pt"
        torch.save(model.state(), path)
        log.info("Model %s: %s (epoki: %d)", name, path, model.epochs_)
    extra = {
        "device": str(next(iter(res.fitted.values())).device),
        "torch": torch.__version__,
        "epochs": {name: model.epochs_ for name, model in res.fitted.items()},
        "seeds": seed_spread(data, target, res.thresholds, args.seeds) if args.seeds else [],
    }
    experiment.dump(res, args.out_dir, NN_PREFIX, extra)
    log.info("Pliki wynikowe: %s", args.out_dir)
    if engine is not None and not args.no_save:
        _, payload = experiment.load(args.out_dir, NN_PREFIX, target)
        _publish_nn(engine, res, payload)


def run_nn_import(args) -> None:
    target = models.TARGETS[args.target]
    res, payload = experiment.load(args.dir, NN_PREFIX, target)
    _publish_nn(_engine(), res, payload)


def _engine():
    engine = db.make_engine(load_settings().database_url)
    db.init_schema(engine)
    return engine


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kse-inz", description="Praca inżynierska")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ds = sub.add_parser("dataset", help="zbuduj zbiór uczący (I1)")
    p_ds.add_argument(
        "--export", type=Path, help="zapisz zbiór także do pliku parquet (dla Colaba)"
    )
    p_c1 = sub.add_parser("c1", help="cel 1: modele bazowe i LightGBM (I2)")
    p_nn = sub.add_parser("nn", help="cel 1: sieci MLP i LSTM (I3)")
    p_nn.add_argument("--data", type=Path, help="zbiór z pliku parquet zamiast z bazy")
    p_nn.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "results" / "i3")
    p_nn.add_argument("--seeds", type=int, default=0, help="rozrzut wyników dla N ziaren")
    p_imp = sub.add_parser("nn-import", help="wyniki sieci z plików → baza i tabela metryk")
    p_imp.add_argument(
        "dir", type=Path, help="katalog z plikami i3_*_wynik.json i *_prognozy.parquet"
    )
    for p in (p_nn, p_imp):
        p.add_argument("--target", choices=list(models.TARGETS), default="balance")
    for p in (p_ds, p_c1, p_nn):
        p.add_argument("--no-save", action="store_true", help="bez zapisu do bazy")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    if args.cmd == "dataset":
        run_dataset(_engine(), save=not args.no_save, export=args.export)
    elif args.cmd == "c1":
        run_c1(_engine(), save=not args.no_save)
    elif args.cmd == "nn":
        run_nn(args)
    else:
        run_nn_import(args)


if __name__ == "__main__":
    main()
