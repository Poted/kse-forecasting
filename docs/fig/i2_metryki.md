# I2 — metryki modeli celu 1 (ograniczenia PV na kwadrans D+1)

Wygenerowano: `uv run kse-inz c1`. Trening: doby ≤ 31.12.2025; test: 01.01.2026–15.11.2026.
Walidacja krocząca: model dla miesiąca M uczony na dobach do końca miesiąca M−2.
AUC, AP — z prawdopodobieństwa; F1, precyzja, czułość — przy progu wyznaczonym na okresie
treningowym (prognozy krzyżowe). MAE [MW] — wszystkie kwadranse; MAE_ogr — kwadranse
z ograniczeniem.

## ograniczenie bilansowe PV

Kwadranse testowe: 30 624, z ograniczeniem: 5 374 (17.5%). MAE prognozy zerowej: 164.8 MW (MAE_ogr 939.2 MW).

### Wszystkie kwadranse

| model | walidacja | AUC | AP | F1 | precyzja | czułość | próg | MAE | MAE_ogr |
|---|---|---|---|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.938 | 0.722 | 0.735 | 0.656 | 0.836 | 0.214 | 147 | 622 |
| baseline: kalendarz | krocząca | 0.938 | 0.722 | 0.735 | 0.656 | 0.836 | 0.214 | 147 | 622 |
| baseline: reguła z planu PSE | trening ≤ 2025 | 0.967 | 0.846 | 0.777 | 0.779 | 0.775 | 0.388 | 140 | 629 |
| baseline: reguła z planu PSE | krocząca | 0.964 | 0.842 | 0.778 | 0.773 | 0.782 | 0.388 | 145 | 618 |
| LightGBM | trening ≤ 2025 | 0.976 | 0.882 | 0.808 | 0.819 | 0.798 | 0.325 | 132 | 535 |
| LightGBM | krocząca | 0.977 | 0.886 | 0.823 | 0.814 | 0.833 | 0.325 | 121 | 514 |
| LightGBM (regresja dwuetapowa) | trening ≤ 2025 | 0.976 | 0.882 | 0.808 | 0.819 | 0.798 | 0.325 | 118 | 563 |
| LightGBM (regresja dwuetapowa) | krocząca | 0.977 | 0.886 | 0.823 | 0.814 | 0.833 | 0.325 | 117 | 547 |

### Kwadranse z planowaną generacją PV > 0

Kwadranse: 17 912.

| model | walidacja | AUC | AP | F1 | MAE |
|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.888 | 0.725 | 0.735 | 251 |
| baseline: kalendarz | krocząca | 0.888 | 0.725 | 0.735 | 251 |
| baseline: reguła z planu PSE | trening ≤ 2025 | 0.934 | 0.847 | 0.777 | 239 |
| baseline: reguła z planu PSE | krocząca | 0.930 | 0.843 | 0.778 | 247 |
| LightGBM | trening ≤ 2025 | 0.952 | 0.882 | 0.808 | 214 |
| LightGBM | krocząca | 0.954 | 0.886 | 0.823 | 203 |
| LightGBM (regresja dwuetapowa) | trening ≤ 2025 | 0.952 | 0.882 | 0.808 | 202 |
| LightGBM (regresja dwuetapowa) | krocząca | 0.954 | 0.886 | 0.823 | 201 |

### LightGBM wg miesięcy (trening ≤ 2025)

| miesiąc | n_ogr | AUC | AP | F1 | MAE | MAE_ogr |
|---|---|---|---|---|---|---|
| 2026-01 | 23 | 0.951 | 0.108 | 0.000 | 3.1 | 301 |
| 2026-02 | 101 | 0.990 | 0.735 | 0.562 | 33.1 | 747 |
| 2026-03 | 601 | 0.976 | 0.904 | 0.824 | 136 | 553 |
| 2026-04 | 845 | 0.977 | 0.935 | 0.874 | 208 | 577 |
| 2026-05 | 755 | 0.972 | 0.913 | 0.842 | 184 | 513 |
| 2026-06 | 848 | 0.971 | 0.927 | 0.766 | 220 | 670 |
| 2026-07 | 859 | 0.971 | 0.909 | 0.811 | 156 | 444 |
| 2026-08 | 636 | 0.967 | 0.850 | 0.821 | 177 | 552 |
| 2026-09 | 487 | 0.978 | 0.878 | 0.807 | 131 | 427 |
| 2026-10 | 199 | 0.975 | 0.681 | 0.681 | 95.0 | 367 |
| 2026-11 | 20 | 0.972 | 0.196 | 0.000 | 86.6 | 177 |

### Ważność cech LightGBM (gain, 12 najważniejszych dla klasyfikatora)

| cecha | klasyfikator | regresor |
|---|---|---|
| `pv_share` | 40.1% | 32.0% |
| `shortwave_radiation` | 11.4% | 2.1% |
| `rez_under` | 7.5% | 4.3% |
| `gen_fv` | 6.2% | 1.3% |
| `res_load` | 4.3% | 12.8% |
| `doy_cos` | 3.3% | 5.5% |
| `doy_sin` | 2.4% | 6.6% |
| `ogr_mwe` | 2.4% | 2.5% |
| `temperature_2m` | 2.1% | 1.8% |
| `gen_fv_day_max` | 1.9% | 1.5% |
| `wind_speed_100m` | 1.8% | 1.3% |
| `p2_net_demand_hat` | 1.6% | 9.5% |

## ograniczenie sieciowe PV

Kwadranse testowe: 30 624, z ograniczeniem: 306 (1.0%). MAE prognozy zerowej: 0.3 MW (MAE_ogr 31.1 MW).

### Wszystkie kwadranse

| model | walidacja | AUC | AP | F1 | precyzja | czułość | próg | MAE | MAE_ogr |
|---|---|---|---|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.620 | 0.013 | 0.029 | 0.015 | 0.471 | 0.071 | 2.1 | 28.4 |
| baseline: kalendarz | krocząca | 0.620 | 0.013 | 0.029 | 0.015 | 0.471 | 0.071 | 2.1 | 28.4 |
| baseline: reguła z planu PSE | trening ≤ 2025 | 0.736 | 0.019 | 0.034 | 0.017 | 1.000 | 0.033 | 2.0 | 27.6 |
| baseline: reguła z planu PSE | krocząca | 0.671 | 0.015 | 0.034 | 0.017 | 1.000 | 0.033 | 1.7 | 28.5 |
| LightGBM | trening ≤ 2025 | 0.819 | 0.027 | 0.055 | 0.029 | 0.830 | 0.001 | 3.2 | 27.7 |
| LightGBM | krocząca | 0.811 | 0.025 | 0.058 | 0.030 | 0.810 | 0.001 | 2.7 | 30.2 |
| LightGBM (regresja dwuetapowa) | trening ≤ 2025 | 0.819 | 0.027 | 0.055 | 0.029 | 0.830 | 0.001 | 1.5 | 29.5 |
| LightGBM (regresja dwuetapowa) | krocząca | 0.811 | 0.025 | 0.058 | 0.030 | 0.810 | 0.001 | 1.3 | 30.5 |

### Kwadranse z planowaną generacją PV > 0

Kwadranse: 17 912.

| model | walidacja | AUC | AP | F1 | MAE |
|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.454 | 0.015 | 0.030 | 3.6 |
| baseline: kalendarz | krocząca | 0.454 | 0.015 | 0.030 | 3.6 |
| baseline: reguła z planu PSE | trening ≤ 2025 | 0.545 | 0.019 | 0.034 | 3.4 |
| baseline: reguła z planu PSE | krocząca | 0.434 | 0.015 | 0.034 | 2.8 |
| LightGBM | trening ≤ 2025 | 0.689 | 0.027 | 0.056 | 5.4 |
| LightGBM | krocząca | 0.675 | 0.025 | 0.058 | 4.4 |
| LightGBM (regresja dwuetapowa) | trening ≤ 2025 | 0.689 | 0.027 | 0.056 | 2.5 |
| LightGBM (regresja dwuetapowa) | krocząca | 0.675 | 0.025 | 0.058 | 2.2 |

### LightGBM wg miesięcy (trening ≤ 2025)

| miesiąc | n_ogr | AUC | AP | F1 | MAE | MAE_ogr |
|---|---|---|---|---|---|---|
| 2026-01 | 0 | — | — | 0.000 | 1.0 | — |
| 2026-02 | 20 | 0.745 | 0.014 | 0.032 | 5.0 | 15.0 |
| 2026-03 | 0 | — | — | 0.000 | 1.7 | — |
| 2026-04 | 36 | 0.768 | 0.025 | 0.073 | 3.3 | 6.3 |
| 2026-05 | 0 | — | — | 0.000 | 3.5 | — |
| 2026-06 | 49 | 0.789 | 0.046 | 0.083 | 5.5 | 25.0 |
| 2026-07 | 48 | 0.936 | 0.197 | 0.076 | 5.5 | 81.5 |
| 2026-08 | 133 | 0.794 | 0.113 | 0.183 | 4.8 | 18.2 |
| 2026-09 | 20 | 0.824 | 0.019 | 0.037 | 2.4 | 20.1 |
| 2026-10 | 0 | — | — | 0.000 | 1.2 | — |
| 2026-11 | 0 | — | — | 0.000 | 0.3 | — |

### Ważność cech LightGBM (gain, 12 najważniejszych dla klasyfikatora)

| cecha | klasyfikator | regresor |
|---|---|---|
| `doy_sin` | 23.8% | 5.8% |
| `doy_cos` | 13.9% | 6.0% |
| `pv_share` | 12.8% | 1.3% |
| `month` | 8.7% | 7.1% |
| `gen_fv` | 6.3% | 2.5% |
| `shortwave_radiation` | 5.4% | 8.4% |
| `ogr_mwe` | 3.7% | 4.3% |
| `gen_fv_day_max` | 3.3% | 3.6% |
| `dow` | 3.0% | 2.1% |
| `res_load_day_min` | 2.4% | 1.6% |
| `wind_speed_100m` | 1.9% | 6.7% |
| `temperature_2m` | 1.9% | 11.1% |
