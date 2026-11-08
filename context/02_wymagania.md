# 02 · Wymagania i przypadki użycia (wersja robocza)

Status: propozycja do akceptacji. Zakres: P2 = wymagania oznaczone P2 i WSP; inżynierka = cały system.
Oznaczenia: WSP — wspólne, P2 — tylko P2, INZ — tylko inżynierka.

## Ustalenia
- Brak logowania użytkowników (decyzja użytkownika, 1.11.2026).
- P2 nie ma wymagań co do bazy danych poza dokumentacją. Wymaganie prowadzącego (cytat przekazany przez użytkownika): to ma być działająca aplikacja i ma coś analizować.
- Widoki dashboardu P2 (wstępnie przyjęte, 1.11.2026): (1) prognoza na jutro z prognozą PSE; (2) jakość prognoz: prognoza vs wykonanie, błędy wg godzin i miesięcy; (3) analiza: profile dobowe w sezonach, spadek zapotrzebowania netto w południe (krzywa kaczki).
- Prognoza P2 wykonywana w dniu D o 12:00 na 24 godziny doby D+1 (decyzja użytkownika, 2.11.2026).

## Aktorzy
- **Analityk** — przegląda prognozy i analizy w dashboardzie.
- **Administrator** — uruchamia pobieranie danych, trening i prognozy.
- **Systemy zewnętrzne** — API PSE, API pogody.

## Wymagania funkcjonalne
| ID | Wymaganie | Zakres |
|---|---|---|
| FR-01 | Pobieranie raportów PSE (`his-wlk-cal`, `pdgopkd`, `poze-redoze`, `rce-pln`) dla zadanego zakresu dat | WSP |
| FR-02 | Pobieranie danych pogodowych (archiwalne prognozy) dla wybranych punktów w Polsce | WSP |
| FR-03 | Normalizacja czasu do UTC i kontrola kompletności (raport brakujących kwadransów) | WSP |
| FR-04 | Zapis do bazy z aktualizacją rekordów (PSE koryguje dane wstecz) | WSP |
| FR-05 | Budowa cech z kontrolą momentu dostępności danych (brak przecieku informacji) | WSP |
| FR-06 | Rejestr przebiegów modeli: parametry, metryki, data | WSP |
| FR-07 | Agregacja godzinowa i zmienna docelowa: zapotrzebowanie netto (`demand − pv`) | P2 |
| FR-08 | Trening i ewaluacja modeli zapotrzebowania netto (baseline’y, LightGBM) z walidacją kroczącą | P2 |
| FR-09 | Zapis historycznych prognoz z walidacji kroczącej (używane jako cecha w INZ) | P2 |
| FR-10 | Prognoza zapotrzebowania netto na dobę D+1 (moment prognozy: 12:00 dnia D) na żądanie | P2 |
| FR-11 | Porównanie prognoz z prognozą PSE z planu dobowego | P2 |
| FR-12 | Dashboard: trzy widoki opisane w Ustaleniach | P2 |
| FR-13 | Trening i ewaluacja modeli ograniczeń PV: klasyfikacja i regresja (baseline’y, LightGBM, MLP, LSTM) | INZ |
| FR-14 | Trening i ewaluacja modelu ryzyka ujemnych cen | INZ |
| FR-15 | Prognoza ryzyka nadpodaży na każdy kwadrans D+1 (prawdopodobieństwo, MW) | INZ |
| FR-16 | Dashboard: ryzyko nadpodaży na jutro, analiza historycznych epizodów, porównanie modeli | INZ |

## Wymagania niefunkcjonalne
| ID | Wymaganie | Zakres |
|---|---|---|
| NFR-01 | Odtwarzalność: stałe ziarno losowe, kod w repozytorium, pobieranie danych z API jednym poleceniem | WSP |
| NFR-02 | Poprawność czasowa: UTC, automatyczne testy braku przecieku informacji | WSP |
| NFR-03 | Odporność na błędy API: ponawianie zapytań, logowanie | WSP |
| NFR-04 | Uruchomienie lokalne jednym poleceniem (Docker Compose: baza + aplikacja) | WSP |
| NFR-05 | Testy jednostkowe i testy danych | WSP |
| NFR-06 | Trening sieci w Colab, modele zapisywane jako pliki i wczytywane przez aplikację | INZ |
| NFR-07 | Źródła danych i ich licencje podane w aplikacji | WSP |

## Przypadki użycia
| ID | Przypadek użycia | Aktor | Wymagania | Zakres |
|---|---|---|---|---|
| UC-01 | Aktualizacja danych | Administrator | FR-01–FR-04 | WSP |
| UC-02 | Przegląd jakości danych | Administrator, Analityk | FR-03 | WSP |
| UC-03 | Trening i ocena modelu | Administrator | FR-06, FR-08, FR-13, FR-14 | P2 / INZ |
| UC-04 | Wygenerowanie prognozy na jutro | Administrator | FR-10, FR-15 | P2 / INZ |
| UC-05 | Przegląd prognozy zapotrzebowania netto | Analityk | FR-12 | P2 |
| UC-06 | Ocena prognoz i porównanie z PSE | Analityk | FR-11, FR-12 | P2 |
| UC-07 | Przegląd ryzyka nadpodaży na jutro | Analityk | FR-15, FR-16 | INZ |
| UC-08 | Analiza historycznych epizodów nadpodaży | Analityk | FR-16 | INZ |
| UC-09 | Porównanie modeli | Analityk | FR-06, FR-16 | INZ |

## Pytania otwarte
1. Prognoza na jutro: uruchamiana ręcznie czy automatycznie — do decyzji po omówieniu obu projektów.
