# P2.5 — metryki modeli zapotrzebowania netto

Wygenerowano: `uv run kse-p2 backtest`. Prognoza w dniu D o 12:00 na godziny doby D+1.
Walidacja krocząca, LightGBM douczany co miesiąc. Wartości w MW, MAPE w %. Wspólny
zbiór godzin: wszystkie modele i PSE mają prognozę i jest wykonanie.
\* PSE: plan dobowy publikowany ok. 16:00 dnia D (po momencie prognozy P2) — benchmark.

## całość

| model | MAE | RMSE | MAPE | bias | MAE_szczyt | MAE_min_poludnie | n |
|---|---|---|---|---|---|---|---|
| naive_d1 (D−1) | 2 269 | 2 994 | 16 | -5.47 | 2 181 | 3 193 | 18 649 |
| naive_week (T−7) | 1 555 | 2 353 | 12 | -37 | 911 | 3 059 | 18 649 |
| LightGBM | 797 | 1 149 | 5.87 | 24 | 646 | 1 471 | 18 649 |
| PSE (plan dobowy)* | 531 | 783 | 4.14 | -44 | 324 | 957 | 18 649 |

## 27.09–31.12.2024

| model | MAE | RMSE | MAPE | bias | MAE_szczyt | MAE_min_poludnie | n |
|---|---|---|---|---|---|---|---|
| naive_d1 (D−1) | 2 322 | 3 074 | 14 | -6.86 | 2 256 | 3 693 | 2 305 |
| naive_week (T−7) | 1 454 | 2 313 | 8.92 | -96 | 985 | 3 037 | 2 305 |
| LightGBM | 1 063 | 1 506 | 6.31 | -88 | 1 226 | 1 726 | 2 305 |
| PSE (plan dobowy)* | 399 | 606 | 2.42 | -33 | 262 | 779 | 2 305 |

## 2025

| model | MAE | RMSE | MAPE | bias | MAE_szczyt | MAE_min_poludnie | n |
|---|---|---|---|---|---|---|---|
| naive_d1 (D−1) | 2 243 | 2 996 | 16 | -6.25 | 2 140 | 3 171 | 8 760 |
| naive_week (T−7) | 1 513 | 2 330 | 11 | -20 | 862 | 2 956 | 8 760 |
| LightGBM | 793 | 1 150 | 5.86 | -4.92 | 609 | 1 470 | 8 760 |
| PSE (plan dobowy)* | 530 | 785 | 4.13 | -38 | 309 | 1 022 | 8 760 |

## 2026

| model | MAE | RMSE | MAPE | bias | MAE_szczyt | MAE_min_poludnie | n |
|---|---|---|---|---|---|---|---|
| naive_d1 (D−1) | 2 282 | 2 968 | 17 | -4.15 | 2 206 | 3 067 | 7 584 |
| naive_week (T−7) | 1 634 | 2 390 | 13 | -39 | 945 | 3 185 | 7 584 |
| LightGBM | 721 | 1 014 | 5.75 | 91 | 511 | 1 395 | 7 584 |
| PSE (plan dobowy)* | 572 | 828 | 4.68 | -53 | 361 | 937 | 7 584 |

## Ważność cech LightGBM (gain, model końcowy)

| cecha | udział |
|---|---|
| `net_mean7` | 46.0% |
| `net_lag7` | 13.4% |
| `shortwave_radiation` | 11.2% |
| `pv_est` | 10.7% |
| `dow` | 4.2% |
| `net_lag14` | 2.2% |
| `is_holiday` | 1.7% |
| `rad_day_mean` | 1.7% |
| `is_weekend` | 1.4% |
| `hour_local` | 1.2% |
| `temperature_2m` | 1.2% |
| `doy_sin` | 0.9% |
| `doy_cos` | 0.9% |
| `net_lag2` | 0.7% |
| `cloud_cover` | 0.6% |
| `wind_speed_100m` | 0.4% |
| `demand_lag2` | 0.4% |
| `pv_lag2` | 0.4% |
| `net_daymean_lag2` | 0.3% |
| `month` | 0.3% |
| `net_lag3` | 0.1% |

Godzin w zbiorze testowym: 18649.
