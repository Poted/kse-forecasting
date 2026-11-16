"""Wykresy inż (matplotlib, PNG do dokumentacji) — styl i paleta z `p2.plots`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_curve

from p2 import plots
from p2.plots import plt


def pr_curves(y, scores: dict[str, pd.Series], title: str, path: Path) -> None:
    """Krzywe precyzja–czułość; etykiety z AP w legendzie."""
    fig, ax = plt.subplots(figsize=(7, 5))
    for color, (label, p) in zip(plots.SERIES, scores.items(), strict=False):
        precision, recall, _ = precision_recall_curve(y, p)
        ax.plot(recall, precision, color=color, label=label)
    ax.axhline(float(pd.Series(y).mean()), color=plots.TEXT_2, linewidth=1, linestyle=":")
    ax.set_title(title, pad=44)
    ax.set_xlabel("czułość")
    ax.set_ylabel("precyzja")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2, borderaxespad=0.2)
    fig.savefig(path)
    plt.close(fig)
