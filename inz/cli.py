"""CLI pracy inżynierskiej.

uv run kse-inz dataset            # zbiór uczący → tabela inz_dataset, statystyki celów, wykresy
uv run kse-inz dataset --no-save  # bez zapisu do bazy
"""

from __future__ import annotations

import argparse
import logging

from common import db
from common.config import PROJECT_ROOT, load_settings
from inz import dataset, stats

log = logging.getLogger("kse-inz")
FIG_DIR = PROJECT_ROOT / "docs" / "fig"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kse-inz", description="Praca inżynierska")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ds = sub.add_parser("dataset", help="zbuduj zbiór uczący (I1)")
    p_ds.add_argument("--no-save", action="store_true", help="bez zapisu do bazy")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = db.make_engine(load_settings().database_url)
    db.init_schema(engine)
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
    if not args.no_save:
        log.info("Zapisano %d wierszy do inz_dataset", dataset.save(engine, data))
    tables = stats.target_stats(data)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "i1_statystyki.md").write_text(stats.to_markdown(tables), encoding="utf-8")
    stats.make_figures(tables, FIG_DIR)
    for name in ("Podsumowanie", "Cele wg lat", "Braki"):
        print(f"\n{name}\n{tables[name].to_string()}")


if __name__ == "__main__":
    main()
