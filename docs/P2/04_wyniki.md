# 4. Wyniki

Dane: doby 14.06.2024–13.11.2026. Wartości w MW, MAPE w %. Błąd = prognoza − wykonanie. Pełne tabele: `docs/fig/p2_4_tabele.md`, `docs/fig/p2_5_metryki.md`.

## 4.1 Jakość danych
Wszystkie raporty PSE i dane pogodowe są kompletne: brak brakujących dób, brak dób z nieprawidłową liczbą kwadransów, brak duplikatów (`docs/kompletnosc_danych.md`). Doby zmiany czasu mają poprawne 92 i 100 kwadransów.

## 4.2 Analiza zapotrzebowania netto
**Profil dobowy wg pory roku** (`docs/fig/p2_4_profil_sezonowy_netto.png`):

| Pora roku | Minimum netto (godzina) | Maksimum netto (godzina) |
|---|---|---|
| zima | 16 129 (3:00) | 22 507 (17:00) |
| wiosna | 9 769 (11:00) | 19 743 (20:00) |
| lato | 9 126 (11:00) | 18 680 (20:00) |
| jesień | 13 539 (11:00) | 20 807 (19:00) |

Zimą minimum przypada w nocy. Od wiosny do jesieni generacja PV przesuwa minimum na godzinę 11:00, a maksimum na wieczór.

**Krzywa kaczki** (`docs/fig/p2_4_krzywa_kaczki_czerwiec.png`, `docs/fig/p2_4_glebokosc_kaczki.png`):

| Czerwiec | Średnia generacja PV | Minimum netto (11:00) | Maksimum netto (20:00) |
|---|---|---|---|
| 2024 (od 14.06) | 3 497 | 10 523 | 18 934 |
| 2025 | 3 579 | 8 990 | 18 077 |
| 2026 | 4 328 | 7 985 | 18 690 |

Minimum południowe w czerwcu obniżyło się o 2,5 GW między 2024 a 2026 r., a maksimum wieczorne pozostało na poziomie 18–19 GW. Średnia dobowa różnica między maksimum wieczornym a minimum południowym latem 2026 r. wynosi 10,3–11,5 GW (latem 2024 r.: 8,6–9,5 GW).

**Prognoza PSE** (plan dobowy, `docs/fig/p2_4_blad_pse_godziny.png`): MAE 522 MW, MAPE 4,1%. Błąd zależy od godziny — od 239 MW o północy do 994 MW o 11:00; w minimum południowym MAE wynosi 945 MW.

## 4.3 Modele
| Model | Opis |
|---|---|
| `naive_d1` | „jak wczoraj”: ta sama godzina ostatniej pełnej doby (D−1) |
| `naive_week` | „jak tydzień temu”: ta sama godzina tego samego dnia tygodnia (D+1 − 7 dni) |
| LightGBM | 21 cech: kalendarz, historia netto (ta sama godzina w poprzednich dobach, średnia z 7 dób), pogoda D+1 (promieniowanie, zachmurzenie, temperatura, wiatr), szacunek generacji PV |
| PSE | plan dobowy (`kse_pow_dem − gen_fv`), publikowany ok. 16:00 dnia D — benchmark z przewagą informacyjną |

**Walidacja krocząca:** prognozy dla dób 27.09.2024–12.11.2026; LightGBM douczany co miesiąc (27 treningów) na wszystkich dobach znanych w chwili prognozy. Pierwszy model uczony na ok. 3 miesiącach danych (decyzja z 08.11: historyczne prognozy od 27.09.2024 dla pracy inżynierskiej).

## 4.4 Wyniki walidacji (18 649 godzin)
| Model | MAE | RMSE | MAPE | MAE w szczycie dobowym | MAE w minimum południowym |
|---|---|---|---|---|---|
| naive_d1 | 2 269 | 2 994 | 16,4 | 2 181 | 3 193 |
| naive_week | 1 555 | 2 353 | 11,8 | 911 | 3 059 |
| **LightGBM** | **797** | **1 149** | **5,87** | 646 | 1 471 |
| PSE (plan dobowy) | 531 | 783 | 4,14 | 324 | 957 |

| Okres | LightGBM (MAE / MAPE) | PSE (MAE / MAPE) |
|---|---|---|
| 27.09–31.12.2024 | 1 063 / 6,31 | 399 / 2,42 |
| 2025 | 793 / 5,86 | 530 / 4,13 |
| 2026 | 721 / 5,75 | 572 / 4,68 |

Wykresy: `docs/fig/p2_5_mae_miesiace.png`, `docs/fig/p2_5_mae_godziny.png`, `docs/fig/p2_5_tydzien_czerwiec.png`.

**Wnioski z wyników:**
- LightGBM zmniejsza MAE o 49% względem najlepszego modelu bazowego.
- Prognoza PSE jest dokładniejsza w 25 z 27 miesięcy; LightGBM jest lepszy w maju i czerwcu 2026 r. PSE publikuje plan ok. 4 godziny później i korzysta z danych operatora.
- Błąd obu prognoz jest największy w godzinach 8–16, czyli w godzinach generacji PV.
- Wyniki pierwszych miesięcy (2024 r.) są słabsze z powodu krótkiej historii uczącej; od 2025 r. MAE LightGBM maleje (793 → 721).
- Najważniejsze cechy (udział w zysku podziałów): średnia netto z 7 dób 46%, netto sprzed tygodnia 13%, promieniowanie 11%, szacunek PV 11%.
- Cecha „szacunek PV” (stosunek PV do prognozowanego promieniowania z ostatnich 7 dób × promieniowanie godziny docelowej) zmniejszyła MAE z 819 do 797 MW i systematyczne przeszacowanie w 2026 r. z +226 do +91 MW — odzwierciedla wzrost mocy zainstalowanej PV.

## 4.5 Aplikacja
Dashboard (`docs/fig/p2_6_widok_*.png`) prezentuje prognozę na jutro z prognozą PSE, jakość prognoz w wybranym okresie i analizę profili. Prognoza na jutro jest liczona z aktualnych danych w ok. 40 s (pobranie, trening, prognoza).

## 4.6 Ograniczenia
- Dane PSE są w wersji po korektach; w chwili prognozy dostępna była wersja pierwotna.
- Moment publikacji przebiegów modeli pogodowych Open-Meteo nie był sprawdzany; margines prognozy wydanej 48 h wcześniej wynosi co najmniej 13 h.
- Hiperparametry LightGBM są stałe (bez strojenia).
- Pogoda to średnia z 8 miast bez wag (możliwe rozszerzenie: wagi wg mocy PV w regionach).
