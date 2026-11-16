"""Sieci neuronowe celu 1 (I3): MLP i LSTM w PyTorch, interfejs jak modele z `inz/models.py`.

- `MLPModel`  — wejście: cechy jednego kwadransu.
- `LSTMModel` — wejście: sekwencja kwadransów jednej doby (92/96/100, dopełniana do 100
  z maską); dwukierunkowa, bo wszystkie cechy doby D+1 są znane w chwili prognozy.
Obie sieci mają dwa wyjścia na kwadrans: logit ograniczenia i wielkość [MW / skala].
Funkcja straty: entropia krzyżowa + błąd średniokwadratowy. Wczesne zatrzymanie na
dobach walidacyjnych wylosowanych z okresu treningowego (20% dób, stałe ziarno).
Wymaga PyTorch: `uv sync --group nn` (w Colabie jest w środowisku).
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import torch
from torch import nn

from inz.models import FEATURES, SEED, Target, _output

MAX_QUARTERS = 100
VAL_FRACTION = 0.2


class _MLP(nn.Module):
    def __init__(self, n_features: int, hidden: tuple[int, ...], dropout: float):
        super().__init__()
        layers, size = [], n_features
        for h in hidden:
            layers += [nn.Linear(size, h), nn.ReLU(), nn.Dropout(dropout)]
            size = h
        self.body = nn.Sequential(*layers, nn.Linear(size, 2))

    def forward(self, x):
        return self.body(x)


class _LSTM(nn.Module):
    def __init__(self, n_features: int, hidden: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, batch_first=True, bidirectional=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(2 * hidden, 2)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(self.drop(out))


class _NetModel:
    """Wspólna pętla uczenia. Podklasy: budowa sieci i tensory (kwadranse albo doby)."""

    name: str
    config: dict

    def __init__(self, **overrides):
        self.cfg = {**self.config, **overrides}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    @property
    def params(self) -> dict:
        return {"nn": self.cfg, "features": FEATURES, "val_fraction": VAL_FRACTION}

    # --- do nadpisania
    def _build(self) -> nn.Module:
        raise NotImplementedError

    def _tensors(self, frame: pd.DataFrame, target: Target | None):
        """Zwraca (X, Y, maska, pozycje wierszy `frame` w tensorze)."""
        raise NotImplementedError

    # --- wspólne
    def _features(self, frame: pd.DataFrame) -> np.ndarray:
        x = (frame[FEATURES].to_numpy(dtype=np.float64) - self.mean_) / self.std_
        return np.nan_to_num(x, nan=0.0).astype(np.float32)

    def _targets(self, frame: pd.DataFrame, target: Target | None) -> np.ndarray:
        if target is None:
            return np.zeros((len(frame), 2), dtype=np.float32)
        y = frame[target.flag].to_numpy(dtype=np.float32)
        mw = frame[target.mw].to_numpy(dtype=np.float32) / self.mw_scale_
        return np.stack([y, mw], axis=1)

    def _loss(self, out, y, mask):
        bce = nn.functional.binary_cross_entropy_with_logits(
            out[..., 0], y[..., 0], reduction="none"
        )
        mse = (out[..., 1] - y[..., 1]) ** 2
        return ((bce + mse) * mask).sum() / mask.sum()

    def fit(self, train: pd.DataFrame, target: Target):
        cfg = self.cfg
        torch.manual_seed(cfg["seed"])
        x = train[FEATURES].to_numpy(dtype=np.float64)
        self.mean_ = np.nanmean(x, axis=0)
        std = np.nanstd(x, axis=0)
        self.std_ = np.where(std > 0, std, 1.0)
        pos = train.loc[train[target.flag] == 1, target.mw]
        self.mw_scale_ = float(pos.std()) if len(pos) > 1 and pos.std() > 0 else 1.0

        days = np.sort(train["business_date"].unique())
        rng = np.random.default_rng(cfg["seed"])
        val_days = set(rng.choice(days, size=max(1, int(len(days) * VAL_FRACTION)), replace=False))
        is_val = train["business_date"].isin(val_days)
        xt, yt, mt, _ = self._tensors(train[~is_val], target)
        xv, yv, mv, _ = (
            t.to(self.device) if torch.is_tensor(t) else t
            for t in self._tensors(train[is_val], target)
        )

        self.net_ = self._build().to(self.device)
        opt = torch.optim.Adam(
            self.net_.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"]
        )
        gen = torch.Generator().manual_seed(cfg["seed"])
        best, best_state, wait = np.inf, None, 0
        self.history_ = []
        for _ in range(cfg["max_epochs"]):
            self.net_.train()
            order = torch.randperm(len(xt), generator=gen)
            for i in range(0, len(order), cfg["batch"]):
                idx = order[i : i + cfg["batch"]]
                xb, yb, mb = (t[idx].to(self.device) for t in (xt, yt, mt))
                opt.zero_grad()
                loss = self._loss(self.net_(xb), yb, mb)
                loss.backward()
                opt.step()
            self.net_.eval()
            with torch.no_grad():
                val = float(self._loss(self.net_(xv), yv, mv))
            self.history_.append(val)
            if val < best - 1e-5:
                best, best_state, wait = val, copy.deepcopy(self.net_.state_dict()), 0
            else:
                wait += 1
                if wait >= cfg["patience"]:
                    break
        self.net_.load_state_dict(best_state)
        self.epochs_ = len(self.history_)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        x, _, _, pos = self._tensors(frame, None)
        self.net_.eval()
        with torch.no_grad():
            out = self.net_(x.to(self.device)).cpu().numpy()
        out = out.reshape(-1, 2)[pos]
        p = 1 / (1 + np.exp(-out[:, 0].astype(np.float64)))
        return _output(frame, p, out[:, 1].astype(np.float64) * self.mw_scale_)

    def state(self) -> dict:
        """Stan do zapisu w pliku (`torch.save`): wagi, skalowanie, konfiguracja, cechy."""
        return {
            "name": self.name,
            "config": self.cfg,
            "features": FEATURES,
            "mean": self.mean_,
            "std": self.std_,
            "mw_scale": self.mw_scale_,
            "state_dict": {k: v.cpu() for k, v in self.net_.state_dict().items()},
        }

    @classmethod
    def from_state(cls, state: dict):
        if state["features"] != FEATURES:
            raise ValueError("Model zapisany dla innej listy cech")
        model = cls(**state["config"])
        model.mean_, model.std_, model.mw_scale_ = state["mean"], state["std"], state["mw_scale"]
        model.net_ = model._build().to(model.device)
        model.net_.load_state_dict(state["state_dict"])
        return model


class MLPModel(_NetModel):
    name = "mlp"
    config = {
        "hidden": (128, 64),
        "dropout": 0.1,
        "lr": 1e-3,
        "weight_decay": 1e-5,
        "batch": 512,
        "max_epochs": 200,
        "patience": 15,
        "seed": SEED,
    }

    def _build(self) -> nn.Module:
        return _MLP(len(FEATURES), tuple(self.cfg["hidden"]), self.cfg["dropout"])

    def _tensors(self, frame, target):
        x = torch.from_numpy(self._features(frame))
        y = torch.from_numpy(self._targets(frame, target))
        return x, y, torch.ones(len(frame)), np.arange(len(frame))


class LSTMModel(_NetModel):
    name = "lstm"
    config = {
        "hidden": 64,
        "dropout": 0.1,
        "lr": 2e-3,
        "weight_decay": 1e-5,
        "batch": 32,
        "max_epochs": 300,
        "patience": 25,
        "seed": SEED,
    }

    def _build(self) -> nn.Module:
        return _LSTM(len(FEATURES), self.cfg["hidden"], self.cfg["dropout"])

    def _tensors(self, frame, target):
        """Doba = jedna sekwencja (kolejność wg `dtime_utc`), dopełniona zerami do 100."""
        order = np.lexsort((frame["dtime_utc"].to_numpy(), frame["business_date"].to_numpy()))
        day_codes, _ = pd.factorize(frame["business_date"].to_numpy()[order], sort=False)
        step = pd.Series(day_codes).groupby(day_codes).cumcount().to_numpy()
        if step.max() >= MAX_QUARTERS:
            raise ValueError("Doba ma więcej niż 100 kwadransów")
        n_days = int(day_codes.max()) + 1
        feats, targs = self._features(frame)[order], self._targets(frame, target)[order]
        x = np.zeros((n_days, MAX_QUARTERS, feats.shape[1]), dtype=np.float32)
        y = np.zeros((n_days, MAX_QUARTERS, 2), dtype=np.float32)
        mask = np.zeros((n_days, MAX_QUARTERS), dtype=np.float32)
        x[day_codes, step], y[day_codes, step], mask[day_codes, step] = feats, targs, 1.0
        pos = np.empty(len(frame), dtype=np.int64)
        pos[order] = day_codes * MAX_QUARTERS + step  # pozycja wiersza `frame` w tensorze
        return torch.from_numpy(x), torch.from_numpy(y), torch.from_numpy(mask), pos


MODELS = (MLPModel, LSTMModel)
