"""Cel 2 (I4): cechy z cen RCE z kontrolą dostępności, model „jak dziś”, eksperyment."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from inz import c2, dataset, experiment, models
from p2 import features as p2f
from tests.test_inz_models import synthetic_dataset

FIRST, LAST = date(2025, 8, 1), date(2026, 2, 28)
T = date(2025, 9, 10)


def synthetic_rce(data: pd.DataFrame, extra_days: int = 0) -> pd.DataFrame:
    """Cena ujemna, gdy zapotrzebowanie − PV − wiatr < 8 GW. Publikacja 10 h przed dobą."""
    res = data["kse_pow_dem"] - data["gen_fv"] - data["gen_wi"]
    rce = pd.DataFrame(
        {
            "dtime_utc": data["dtime_utc"],
            "business_date": data["business_date"],
            "rce_pln": np.where(res < 8000, -50.0, 300.0) + data["quarter_local"] * 0.01,
        }
    )
    rce["publication_ts_utc"] = [
        p2f.day_start_utc(d) - pd.Timedelta(hours=10) for d in rce["business_date"]
    ]
    return rce


@pytest.fixture(scope="module")
def frames():
    data = synthetic_dataset(FIRST, LAST)
    rce = synthetic_rce(data)
    data = data.merge(rce[["dtime_utc", "rce_pln"]], on="dtime_utc")
    data["y_rce_neg"] = (data["rce_pln"] < 0).astype("Int64")
    return data, rce


def test_feature_list_has_no_plan_targets_or_current_price():
    forbidden = {*dataset.PLAN, *dataset.TARGETS, "rce_pln", "res_load", "pv_share"}
    assert not forbidden & set(c2.FEATURES)
    assert set(dataset.FEATURES_C2) < set(c2.FEATURES)


def test_lag_features_values(frames):
    data, rce = frames
    out = c2.add_features(data, rce)
    day = out[out["business_date"] == T].set_index("quarter_local")
    prev = rce[rce["business_date"] == T - timedelta(days=1)]["rce_pln"].to_numpy()
    week = rce[rce["business_date"] == T - timedelta(days=7)]["rce_pln"].to_numpy()
    assert np.allclose(day["rce_lag1"], prev) and np.allclose(day["rce_lag7"], week)
    assert day["rce_neg_share_lag1"].iloc[0] == pytest.approx((prev < 0).mean())
    assert day["rce_day_min_lag7"].iloc[0] == week.min()
    src = data[data["business_date"] == T]
    assert day["p2_day_min"].iloc[0] == src["p2_net_demand_hat"].min()
    assert day["rad_day_max"].iloc[0] == src["shortwave_radiation"].max()
    assert day["wind_day_mean"].iloc[0] == pytest.approx(src["wind_speed_100m"].mean())
    # pierwsza doba zbioru: brak historii cen → NaN
    assert out.loc[out["business_date"] == FIRST, "rce_lag1"].isna().all()


def test_no_leakage_from_target_day_and_later(frames):
    """Ceny doby T i późniejszych nie wpływają na cechy doby T."""
    data, rce = frames
    base = c2.add_features(data, rce)
    changed = rce.copy()
    changed.loc[changed["business_date"] >= T, "rce_pln"] = -999.0
    out = c2.add_features(data, changed)
    cols = ["dtime_utc", *c2.FEATURES]
    upto = base["business_date"] <= T
    pd.testing.assert_frame_equal(out.loc[upto, cols], base.loc[upto, cols])
    assert (out.loc[out["business_date"] == T + timedelta(days=1), "rce_lag1"] < -900).all()


def test_price_version_published_after_forecast_moment_is_not_used(frames):
    data, rce = frames
    d = T - timedelta(days=1)  # doba D; prognoza o 12:00 dnia D
    late = rce.copy()
    late.loc[late["business_date"] == d, "publication_ts_utc"] = p2f.forecast_moment_utc(
        d
    ) + pd.Timedelta(minutes=5)
    out = c2.add_features(data, late)
    day = out[out["business_date"] == T]
    assert day[["rce_lag1", "rce_neg_share_lag1", "rce_day_min_lag1"]].isna().all().all()
    assert day["rce_lag7"].notna().all()
    # ta sama doba jako T−7 dla późniejszej prognozy jest już dostępna
    later = out[out["business_date"] == d + timedelta(days=7)]
    assert later["rce_lag7"].notna().all()


def test_dst_day_and_days_without_p2_forecast():
    data = synthetic_dataset(date(2025, 10, 20), date(2025, 10, 28))
    rce = synthetic_rce(data)
    data.loc[data["business_date"] == date(2025, 10, 28), "p2_net_demand_hat"] = np.nan
    out = c2.add_features(data, rce)
    assert out["business_date"].max() == date(2025, 10, 27)  # doba bez prognozy P2 pominięta
    dst = out[out["business_date"] == date(2025, 10, 26)]
    assert len(dst) == 100 and dst["rce_lag1"].notna().all()
    after = out[out["business_date"] == date(2025, 10, 27)]
    assert len(after) == 96 and after["rce_lag1"].notna().all()


def test_persistence_baseline():
    frame = pd.DataFrame({"rce_lag1": [-10.0, 0.0, 250.0, np.nan]})
    out = c2.PersistenceBaseline().fit(frame, c2.TARGET).predict(frame)
    assert out["p_hat"].tolist() == [1.0, 0.0, 0.0, 0.0] and (out["mw_hat"] == 0).all()


def test_walk_cutoff_for_daily_labels():
    assert experiment.walk_cutoff(date(2026, 3, 1), "day") == date(2026, 2, 27)
    assert experiment.walk_cutoff(date(2026, 3, 1)) == date(2026, 1, 31)


def test_experiment_for_classification_only_target(frames, monkeypatch):
    monkeypatch.setitem(models.LGBM_PARAMS, "n_estimators", 20)
    monkeypatch.setitem(models.LGBM_PARAMS, "learning_rate", 0.2)
    monkeypatch.setitem(models.LGBM_PARAMS, "n_jobs", 1)
    data, rce = frames
    res = experiment.run(c2.add_features(data, rce), c2.TARGET, model_classes=c2.MODELS)
    names = [m.name for m in c2.MODELS]
    assert list(res.metrics.index) == [(m, s) for m in names for s in experiment.SCHEMES]
    assert res.fitted["lightgbm"].reg_ is None
    assert res.params["lightgbm"]["features"] == c2.FEATURES
    assert (res.predictions["mw_hat"] == 0).all()
    blocks = res.train_info["lightgbm"]
    assert [b["train_to"] for b in blocks] == ["2025-12-30", "2026-01-30"]
    m = res.metrics
    assert m.loc[("lightgbm", "staly"), "AP"] > m.loc[("baseline_jak_dzis", "staly"), "AP"]
    assert experiment.run_name(c2.TARGET, "lightgbm", "staly") == "inz_c2_rce_neg_lightgbm_staly"
