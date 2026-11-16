# 03 · Plan wykonania

Plan etapów obu prac. Claude Code realizuje go samodzielnie (protokół w `CLAUDE.md`). Rozmowa w projekcie claude.ai czyta najpierw: `00_fundament.md`, ten dokument, `04_komunikacja.md`, `01_dane.md`, potem `docs/STAN.md`.

## Zasady prowadzenia
- Wyłącznie fakty. Propozycje oznaczone jako propozycje. Decyzje podejmuje użytkownik; zapis w `00_fundament.md` (sekcja Decyzje).
- Kolejność: P2 → tag `p2-v1.0` (po akceptacji użytkownika) → inż. Etap jest zakończony dopiero po spełnieniu warunku „Gotowe, gdy”.
- Każdy etap = plik w `context/zadania/` (tworzy go Claude Code z tej tabeli) + dokumentacja w `docs/etapy/`.
- Po każdym etapie: aktualizacja tabeli „Stan” poniżej.
- Bez dodatków spoza zakresu.

## Narzędzia
| Narzędzie | Do czego | Etapy |
|---|---|---|
| Claude Code | cały kod: pobieranie danych, baza, cechy, LightGBM, dashboard, testy, dokumentacja techniczna (README, ERD, diagramy) | wszystkie |
| Google Colab | trening i strojenie sieci MLP/LSTM (GPU) | tylko I3 |
| Rozmowa w projekcie claude.ai „Inżynierka” | zarządzanie projektem, przegląd kodu i wyników, decyzje, tekst pracy i dokumentacji P2 | równolegle |
| GitHub `Poted/kse-forecasting` | kod, `context/`, zadania, raporty, dokumentacja etapów, tagi | wszystkie |
| Dysk Google | dane i modele dla Colaba | I3 |

Uzasadnienie Colaba tylko w I3: zbiór ma ok. 83,5 tys. kwadransów (870 dni × 96). LightGBM trenuje się na CPU. Sieci również można trenować na CPU; GPU przyspiesza strojenie (ocena, nie pomiar).

Komunikacja: `04_komunikacja.md`.

## Repozytorium
- `Poted/kse-forecasting` (prywatne), gałąź `main`. Koniec P2 = tag `p2-v1.0` (zamrożona wersja do oddania). Inż kontynuowana na `main`. Jeśli P2 musi być oddane jako osobne repozytorium: kopia z tagu `p2-v1.0`.
- Układ:
  - `context/` — dokumenty projektu i zadania (źródło prawdy)
  - `common/` — klienci API (PSE, Open-Meteo), baza, czas/kalendarz, walidacja, cechy wspólne
  - `p2/` — model zapotrzebowania netto
  - `inz/` — modele nadpodaży, notebooki Colab
  - `app/` — dashboard (widoki P2 i inż)
  - `tests/`, `docs/` (w tym `STAN.md`), `models/`, `config/`; `data/` poza gitem

## Etapy P2
| Etap | Zakres | Gotowe, gdy |
|---|---|---|
| P2.1 Środowisko | struktura repo, `pyproject`, Docker Compose (PostgreSQL), ruff, pytest, README | baza startuje jednym poleceniem; `pytest` przechodzi |
| P2.2 Dane | klient PSE: 4 raporty, paginacja, ponawianie; klient Open-Meteo (`_previous_day1`); zapis surowy (parquet); CLI pobierania; raport kompletności | dane od 14.06.2024 do dziś pobrane; raport braków; testy klientów na zapisanych odpowiedziach |
| P2.3 Baza | schemat, ładowanie z aktualizacją rekordów, widoki godzinowe, ERD | dane w bazie; ERD w `docs/`; test zgodności liczby wierszy |
| P2.4 Analiza | profile dobowe i sezonowe, krzywa kaczki, błąd prognozy PSE | notebook + wykresy w `docs/fig/` |
| P2.5 Modele | cechy z kontrolą momentu dostępności; baseline’y; LightGBM; walidacja krocząca; porównanie z PSE; zapis historycznych prognoz | tabela metryk wszystkich modeli i PSE; test braku przecieku; historyczne prognozy w bazie |
| P2.6 Aplikacja | Streamlit, 3 widoki; polecenie „prognoza na jutro” | dashboard startuje jednym poleceniem; prognoza na jutro liczy się z aktualnych danych |
| P2.7 Dokumentacja | technologie, architektura, ERD, wyniki, instrukcja | dokumentacja w `docs/P2/`; tag `p2-v1.0` |

**Koniec P2 = P2.7 gotowe.**

## Etapy inż
| Etap | Zakres | Gotowe, gdy |
|---|---|---|
| I1 Zbiór uczący | kwadranse: plan PSE na D+1, historyczne prognozy P2, pogoda, kalendarz; cele: ograniczenie bilansowe/sieciowe PV, MW, RCE < 0 | tabela w bazie; testy dostępności informacji; statystyki celów |
| I2 Cel 1: LightGBM | baseline’y + LightGBM: klasyfikacja i regresja; trening ≤ 2025, test 2026 | metryki AUC, AP, F1, MAE vs baseline’y |
| I3 Sieci (Colab) | MLP i LSTM (sekwencja 96 kwadransów doby) | metryki w tej samej tabeli; notebook w repo; model zapisany |
| I4 Cel 2: ceny ujemne | model o 12:00 dnia D; baseline’y | metryki vs baseline’y; przy słabym wyniku — analiza związku cen z ograniczeniami |
| I5 System | widoki: ryzyko na jutro, epizody historyczne, porównanie modeli; testy; podręcznik | dashboard kompletny; testy przechodzą; podręcznik w `docs/` |
| I6 Opcja | symulacja magazynu energii | tylko jeśli starczy czasu |

**Tekst pracy:** część teoretyczna może powstawać od początku, równolegle z P2. Część praktyczna — po I5, na podstawie dokumentacji i wyników.

## Historyczne prognozy P2 (rozstrzygnięte 8.11.2026)
Inż uczy się na danych o ograniczeniach od 27.09.2024. Wybrany wariant: P2 generuje historyczne prognozy od 27.09.2024, model uczony na dostępnej historii od 14.06.2024 (walidacja krocząca, model douczany na rosnącym oknie). Odrzucone: starsze dane z raportów historycznych PSE (inny format, niesprawdzone); prognoza PSE zamiast P2.

## Stan
| Etap | Status | Wymaga decyzji |
|---|---|---|
| P2.1 | zrobione (8.11.2026) | — |
| P2.2 | zrobione (8.11.2026) | — (punkty pogodowe: decyzja 8.11) |
| P2.3 | zrobione (13.11.2026) | — |
| P2.4 | zrobione (13.11.2026) | — |
| P2.5 | zrobione (13.11.2026) | — (historyczne prognozy od 27.09.2024: decyzja 8.11; pogoda _previous_day2: decyzja 13.11) |
| P2.6 | zrobione (13.11.2026) | — (prognoza na jutro ręcznie: decyzja 8.11) |
| P2.7 | zrobione (16.11.2026); tag `p2-v1.0` na gałęzi `p2` | — (tag zaakceptowany 16.11) |
| I1 | zrobione (16.11.2026) | — |
| I2 | zrobione (16.11.2026) | — |
| I3–I6 | nierozpoczęte | — |
| Tekst inż | nierozpoczęty (prowadzony w rozmowie w projekcie) | — |
