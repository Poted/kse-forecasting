# I4 — metryki modeli celu 2 (ujemna cena RCE na kwadrans D+1)

Wygenerowano: `uv run kse-inz c2`. Prognoza o 12:00 dnia D. Trening: doby ≤ 2025; test: 01.01.2026–15.11.2026.
Walidacja krocząca: model dla miesiąca M uczony na dobach do 2 dób przed początkiem
miesiąca (ceny są znane następnego dnia). Próg F1 wyznaczony na okresie treningowym.

Kwadranse testowe: 30 624, z ceną ujemną: 1 339 (4.4%).

## Wszystkie kwadranse

| model | walidacja | AUC | AP | F1 | precyzja | czułość | próg |
|---|---|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.882 | 0.259 | 0.347 | 0.228 | 0.727 | 0.098 |
| baseline: kalendarz | krocząca | 0.882 | 0.259 | 0.347 | 0.228 | 0.727 | 0.098 |
| baseline: jak dziś (doba D) | trening ≤ 2025 | 0.687 | 0.188 | 0.402 | 0.402 | 0.402 | 1.000 |
| baseline: jak dziś (doba D) | krocząca | 0.687 | 0.188 | 0.402 | 0.402 | 0.402 | 1.000 |
| LightGBM | trening ≤ 2025 | 0.976 | 0.725 | 0.579 | 0.431 | 0.881 | 0.007 |
| LightGBM | krocząca | 0.973 | 0.719 | 0.554 | 0.398 | 0.915 | 0.007 |

F1 LightGBM (trening ≤ 2025) przy progu dobranym na teście: 0.652 — tylko
diagnostyka kalibracji progu, nie wynik modelu.

## Kwadranse z planowaną generacją PV > 0

Kwadranse: 17 912.

| model | walidacja | AUC | AP | F1 |
|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.837 | 0.266 | 0.349 |
| baseline: kalendarz | krocząca | 0.837 | 0.266 | 0.349 |
| baseline: jak dziś (doba D) | trening ≤ 2025 | 0.682 | 0.212 | 0.410 |
| baseline: jak dziś (doba D) | krocząca | 0.682 | 0.212 | 0.410 |
| LightGBM | trening ≤ 2025 | 0.962 | 0.734 | 0.588 |
| LightGBM | krocząca | 0.960 | 0.727 | 0.560 |

## LightGBM wg miesięcy (trening ≤ 2025)

| miesiąc | kw. z ceną < 0 | AUC | AP | F1 |
|---|---|---|---|---|
| 2026-01 | 41 | 0.942 | 0.368 | 0.406 |
| 2026-02 | 12 | 1.000 | 0.979 | 0.857 |
| 2026-03 | 142 | 0.966 | 0.620 | 0.526 |
| 2026-04 | 390 | 0.968 | 0.835 | 0.692 |
| 2026-05 | 248 | 0.991 | 0.905 | 0.689 |
| 2026-06 | 127 | 0.971 | 0.680 | 0.448 |
| 2026-07 | 152 | 0.953 | 0.677 | 0.509 |
| 2026-08 | 123 | 0.971 | 0.640 | 0.492 |
| 2026-09 | 87 | 0.989 | 0.775 | 0.642 |
| 2026-10 | 17 | 0.934 | 0.084 | 0.095 |
| 2026-11 | 0 | — | — | 0.000 |

## Ważność cech LightGBM (gain)

| cecha | udział |
|---|---|
| `p2_net_demand_hat` | 26.2% |
| `rce_lag1` | 21.9% |
| `wind_day_mean` | 7.7% |
| `wind_speed_100m` | 7.0% |
| `shortwave_radiation` | 5.5% |
| `doy_sin` | 5.3% |
| `rce_lag7` | 3.7% |
| `quarter_local` | 3.2% |
| `rce_day_min_lag1` | 2.5% |
| `p2_day_min` | 2.5% |
| `rad_day_max` | 2.2% |
| `cloud_cover` | 2.1% |
| `temperature_2m` | 2.0% |
| `month` | 2.0% |
| `dow` | 1.8% |
| `doy_cos` | 1.7% |
| `rce_day_min_lag7` | 1.3% |
| `is_holiday` | 0.5% |
| `rce_neg_share_lag7` | 0.3% |
| `is_weekend` | 0.3% |
| `rce_neg_share_lag1` | 0.3% |
