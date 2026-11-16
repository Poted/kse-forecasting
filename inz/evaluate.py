"""Metryki celu 1: klasyfikacja (AUC, AP, F1) i regresja (MAE [MW])."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Próg maksymalizujący F1 (wyznaczany na danych walidacyjnych, nie testowych)."""
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-12, None)
    return float(thresholds[int(np.argmax(f1[:-1]))])


def metrics(y, mw, p_hat, mw_hat, threshold: float) -> dict[str, float]:
    y = np.asarray(y, dtype=int)
    mw, p_hat, mw_hat = (np.asarray(v, dtype=float) for v in (mw, p_hat, mw_hat))
    pred = (p_hat >= threshold).astype(int)
    both = len(np.unique(y)) == 2
    precision = precision_score(y, pred, zero_division=0)
    recall = recall_score(y, pred, zero_division=0)
    pos = y == 1
    return {
        "AUC": roc_auc_score(y, p_hat) if both else np.nan,
        "AP": average_precision_score(y, p_hat) if both else np.nan,
        "F1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "precyzja": precision,
        "czułość": recall,
        "próg": threshold,
        "MAE": float(np.abs(mw_hat - mw).mean()),
        "MAE_ogr": float(np.abs(mw_hat - mw)[pos].mean()) if pos.any() else np.nan,
        "n": len(y),
        "n_ogr": int(pos.sum()),
    }


def by_month(frame: pd.DataFrame, flag: str, mw: str, threshold: float) -> pd.DataFrame:
    key = pd.to_datetime(frame["business_date"]).dt.to_period("M")
    rows = {
        m: metrics(g[flag], g[mw], g["p_hat"], g["mw_hat"], threshold)
        for m, g in frame.groupby(key)
    }
    return pd.DataFrame(rows).T
