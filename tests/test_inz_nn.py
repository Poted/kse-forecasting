"""Sieci MLP i LSTM (I3) — dane syntetyczne. Pomijane bez PyTorch (`uv sync --group nn`)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from inz import evaluate, experiment, models, nn  # noqa: E402
from tests.test_inz_models import TARGET, synthetic_dataset  # noqa: E402

FAST = {"max_epochs": 12, "patience": 12}


@pytest.fixture(scope="module")
def frames():
    # 26.10.2025 (100 kwadransów) w treningu, 29.03.2026 (92 kwadranse) w teście
    df = experiment.prepare(synthetic_dataset(date(2025, 8, 1), date(2026, 3, 31)), TARGET)
    return df[df["business_date"] <= date(2025, 12, 31)], df[
        df["business_date"] > date(2025, 12, 31)
    ]


@pytest.mark.parametrize("cls", nn.MODELS)
def test_network_learns_and_output_is_valid(frames, cls):
    train, test = frames
    model = cls(**FAST).fit(train, TARGET)
    out = model.predict(test)
    assert len(out) == len(test) and out.index.equals(test.index)
    assert out["p_hat"].between(0, 1).all() and (out["mw_hat"] >= 0).all()
    m = evaluate.metrics(test[TARGET.flag], test[TARGET.mw], out["p_hat"], out["mw_hat"], 0.5)
    assert m["AUC"] > 0.95
    assert m["MAE"] < test[TARGET.mw].mean()  # lepiej niż prognoza zerowa
    assert 1 <= model.epochs_ <= FAST["max_epochs"]


@pytest.mark.parametrize("cls", nn.MODELS)
def test_prediction_follows_row_order(frames, cls):
    """Prognoza przypisana do właściwego wiersza niezależnie od kolejności wierszy."""
    train, test = frames
    model = cls(**FAST).fit(train, TARGET)
    base = model.predict(test)
    shuffled = test.sample(frac=1, random_state=1)
    out = model.predict(shuffled)
    assert np.allclose(out.loc[test.index, "p_hat"], base["p_hat"], atol=1e-5)
    assert np.allclose(out.loc[test.index, "mw_hat"], base["mw_hat"], atol=1e-2)


def test_lstm_sequences_handle_dst_days(frames):
    train, test = frames
    model = nn.LSTMModel(**FAST).fit(train.tail(96 * 30), TARGET)
    x, y, mask, pos = model._tensors(train, TARGET)
    counts = train.groupby("business_date").size()
    assert x.shape == (len(counts), nn.MAX_QUARTERS, len(models.FEATURES))
    assert sorted(mask.sum(dim=1).int().tolist()) == sorted(counts.tolist())
    assert counts.max() == 100 and test.groupby("business_date").size().min() == 92
    assert len(np.unique(pos)) == len(train)
    # cele trafiają na właściwe pozycje sekwencji
    assert np.allclose(y.reshape(-1, 2)[pos][:, 0], train[TARGET.flag].to_numpy())


@pytest.mark.parametrize("cls", nn.MODELS)
def test_same_seed_gives_same_model_on_cpu(frames, cls):
    train, test = frames
    part = train.tail(96 * 40)
    a = cls(max_epochs=3, patience=3).fit(part, TARGET).predict(test)
    b = cls(max_epochs=3, patience=3).fit(part, TARGET).predict(test)
    c = cls(max_epochs=3, patience=3, seed=7).fit(part, TARGET).predict(test)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(a["p_hat"], c["p_hat"])


@pytest.mark.parametrize("cls", nn.MODELS)
def test_state_roundtrip(frames, cls, tmp_path):
    train, test = frames
    model = cls(max_epochs=2, patience=2).fit(train.tail(96 * 30), TARGET)
    path = tmp_path / "model.pt"
    torch.save(model.state(), path)
    restored = cls.from_state(torch.load(path, weights_only=False))
    pd.testing.assert_frame_equal(restored.predict(test), model.predict(test))


def test_missing_features_do_not_break_prediction(frames):
    train, test = frames
    model = nn.MLPModel(max_epochs=2, patience=2).fit(train.tail(96 * 30), TARGET)
    out = model.predict(test.assign(p2_net_demand_hat=np.nan))
    assert out.notna().all().all()


def test_experiment_dump_and_load_roundtrip(frames, tmp_path, monkeypatch):
    monkeypatch.setitem(nn.MLPModel.config, "max_epochs", 2)
    monkeypatch.setattr(experiment, "CV_FOLDS", 2)
    data = synthetic_dataset(date(2025, 8, 1), date(2026, 2, 28))
    res = experiment.run(data, TARGET, model_classes=(nn.MLPModel,))
    assert list(res.metrics.index) == [("mlp", "staly"), ("mlp", "kroczacy")]
    assert res.params["mlp"]["nn"]["hidden"] == (128, 64)
    experiment.dump(res, tmp_path, "i3", {"device": "cpu"})
    loaded, payload = experiment.load(tmp_path, "i3", TARGET)
    assert payload["device"] == "cpu" and loaded.thresholds == res.thresholds
    pd.testing.assert_frame_equal(
        loaded.metrics.astype(float), res.metrics.astype(float), check_names=False
    )
    assert len(loaded.predictions) == len(res.predictions)
    assert loaded.predictions["business_date"].iloc[0] == date(2026, 1, 1)
