# I3 — metryki modeli celu 1: modele bazowe, LightGBM, MLP, LSTM

Wygenerowano: `uv run kse-inz nn` albo `uv run kse-inz nn-import`. Wiersze modeli
bazowych i LightGBM: ostatnie przebiegi `uv run kse-inz c1`. Cel: ograniczenie bilansowe PV.
Trening: doby ≤ 31.12.2025; test: 2026. Opis kolumn: `docs/fig/i2_metryki.md`.
Sieci: wersja kodu `374c912-dirty`, urządzenie `cpu`.

| model | walidacja | AUC | AP | F1 | precyzja | czułość | próg | MAE | MAE_ogr |
|---|---|---|---|---|---|---|---|---|---|
| baseline: kalendarz | trening ≤ 2025 | 0.938 | 0.722 | 0.735 | 0.656 | 0.836 | 0.214 | 147 | 622 |
| baseline: reguła z planu PSE | trening ≤ 2025 | 0.967 | 0.846 | 0.777 | 0.779 | 0.775 | 0.388 | 140 | 629 |
| LightGBM | trening ≤ 2025 | 0.976 | 0.882 | 0.808 | 0.819 | 0.798 | 0.325 | 132 | 535 |
| LightGBM (regresja dwuetapowa) | trening ≤ 2025 | 0.976 | 0.882 | 0.808 | 0.819 | 0.798 | 0.325 | 118 | 563 |
| MLP | trening ≤ 2025 | 0.979 | 0.901 | 0.817 | 0.861 | 0.776 | 0.292 | 114 | 544 |
| LSTM | trening ≤ 2025 | 0.980 | 0.900 | 0.823 | 0.840 | 0.807 | 0.303 | 125 | 546 |
| baseline: kalendarz | krocząca | 0.938 | 0.722 | 0.735 | 0.656 | 0.836 | 0.214 | 147 | 622 |
| baseline: reguła z planu PSE | krocząca | 0.964 | 0.842 | 0.778 | 0.773 | 0.782 | 0.388 | 145 | 618 |
| LightGBM | krocząca | 0.977 | 0.886 | 0.823 | 0.814 | 0.833 | 0.325 | 121 | 514 |
| LightGBM (regresja dwuetapowa) | krocząca | 0.977 | 0.886 | 0.823 | 0.814 | 0.833 | 0.325 | 117 | 547 |
| MLP | krocząca | 0.978 | 0.889 | 0.834 | 0.806 | 0.864 | 0.292 | 125 | 525 |
| LSTM | krocząca | 0.977 | 0.880 | 0.825 | 0.772 | 0.886 | 0.303 | 126 | 513 |

## Rozrzut wyników sieci: 5 ziaren losowych (trening ≤ 2025)

| model | metryka | średnia | odch. std. | min | maks |
|---|---|---|---|---|---|
| MLP | AUC | 0.978 | 0.004 | 0.971 | 0.980 |
| MLP | AP | 0.893 | 0.014 | 0.869 | 0.905 |
| MLP | F1 | 0.813 | 0.035 | 0.752 | 0.838 |
| MLP | MAE | 119 | 6.2 | 114 | 129 |
| LSTM | AUC | 0.979 | 0.003 | 0.974 | 0.981 |
| LSTM | AP | 0.892 | 0.014 | 0.876 | 0.908 |
| LSTM | F1 | 0.821 | 0.019 | 0.791 | 0.839 |
| LSTM | MAE | 124 | 7.5 | 114 | 133 |
