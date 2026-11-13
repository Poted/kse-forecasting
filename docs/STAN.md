# STAN

Raporty z wykonania zadań. Najnowszy wpis na górze.

## Decyzje potrzebne
- (brak blokujących)

---

## 2026-11-13 · P2.5 Modele — zrobione
**Zrobione:** cechy z kontrolą dostępności (`p2/features.py`), modele bazowe `naive_d1`, `naive_week`, LightGBM, walidacja krocząca z miesięcznym douczaniem (`p2/backtest.py`), CLI `uv run kse-p2 backtest`, tabele `model_run` i `p2_forecast`, widok `v_p2_forecast_latest`, test braku przecieku. Dokumentacja: `docs/etapy/P2.5.md`, metryki: `docs/fig/p2_5_metryki.md`.

**Decyzja w sesji (13.11, zapisana w `00_fundament.md` sekcja 5):** pogoda `_previous_day2` zamiast `_previous_day1` — wg dokumentacji Open-Meteo `_previous_day1` to wartość prognozowana 24 h przed godziną docelową, czyli dla godzin D+1 po ok. 12:00 wydana po momencie prognozy. Pogoda pobrana ponownie od 13.06.2024. Uwaga: `01_dane.md` (sekcja Pogoda) nadal wskazuje `_previous_day1` — do aktualizacji przez użytkownika/rozmowę w projekcie.

**Wyniki** (18 649 godzin, doby 27.09.2024–12.11.2026, wspólny zbiór): MAE [MW] — `naive_d1` 2 269, `naive_week` 1 555, **LightGBM 797** (MAPE 5,87%), PSE 531 (MAPE 4,14%). LightGBM 2025: 793, 2026: 721. PSE lepszy w 25 z 27 miesięcy (LightGBM lepszy w V i VI 2026). Cecha `pv_est` (szacunek PV z ostatnich 7 dób) obniżyła MAE z 819 do 797 i bias 2026 z +226 do +91 MW. Historyczne prognozy w bazie (przebiegi 7–9). `pytest` 50 passed, `ruff` bez błędów.

**Problemy:** `open-meteo.com` poza listą dozwolonych hostów — dokumentację przeczytano ze źródeł strony w publicznym repozytorium `open-meteo/open-meteo-website` (stan z 10.11.2026).

**Pytania do kierownika (nieblokujące):**
- `01_dane.md`: zaktualizować opis pogody (`_previous_day2`, konwencja czasu `shortwave_radiation`)? Claude Code nie zmienia tego pliku.

## 2026-11-13 · P2.4 Analiza — zrobione
**Zrobione:** `p2/analysis.py`, `p2/metrics.py`, `p2/plots.py`; notebook `p2/notebooks/P2.4_analiza.ipynb`; 7 wykresów i tabele w `docs/fig/`. Dokumentacja: `docs/etapy/P2.4.md`. Nowe zależności: `matplotlib`; dev: `ipykernel`, `nbconvert`, `nbformat`.

**Wyniki:** minimum netto w czerwcu (11:00): 2024 — 10 523 MW, 2025 — 8 990, 2026 — 7 985; maksimum wieczorne ok. 18–19 GW. Prognoza PSE netto (godziny): MAE 522 MW, RMSE 771, MAPE 4,10%; w minimum południowym MAE 945 MW, w szczycie 325 MW; MAE wg godziny od 239 (0:00) do 994 MW (11:00). `pytest` 39 passed, `ruff` bez błędów.

**Problemy:** brak. PR: https://github.com/Poted/kse-forecasting/pull/2 (zaktualizowany o P2.4; otwarty).

## 2026-11-13 · P2.3 Baza — zrobione
**Zrobione:** schemat PostgreSQL (`common/db.py`): 4 tabele kwadransowe PSE (klucz `dtime_utc`), `weather_point` + `weather_forecast`; ładowanie parquet z upsertem; widoki godzinowe `v_wykonanie_h` (z `net_demand`), `v_plan_h` (benchmark `net_demand_pse`), `v_rce_h`, `v_pogoda_h` (średnia z punktów); polecenia `kse-data load | db-check | erd`; ERD `docs/erd.md`. Dokumentacja: `docs/etapy/P2.3.md`. Do `docs/etapy/P2.2.md` dodana sekcja „Jak sprawdzić samodzielnie”.

**Wyniki:** dane odświeżone do 13.11 i załadowane; zgodność liczby wierszy parquet = baza dla 5 tabel (84 772 / 84 772 / 74 692 / 84 772 / 169 536). Średnie godzinowe netto z widoku zgodne z tabelą w `00_fundament.md`. `pytest` 33 passed (testy bazy na tymczasowym schemacie), `ruff` bez błędów.

**Problemy:** demon Dockera w nowym kontenerze sesji ponownie uruchamiany ręcznie (`dockerd`). PR do `main`: https://github.com/Poted/kse-forecasting/pull/2 — otwarty; scalenie z sesji zablokowane przez uprawnienia Claude Code (jak PR #1), scala użytkownik.

**Uwagi do P2.5 (nieblokujące, szczegóły w `docs/etapy/P2.3.md`):** konwencja znacznika czasu zmiennych Open-Meteo (chwilowe vs uśrednione za godzinę) do sprawdzenia przed dopasowaniem pogody do godzin.

## 2026-11-13 · przegląd (rozmowa w projekcie)
- PR #1 (P2.2) scalony do `main` 8.11; testy 26 passed, ruff bez błędów.
- Odpowiedź na pytanie o wykonanie z dnia D: obowiązuje obecne ustalenie — w P2.5 cechy z wykonania tylko do końca D−1. Powód: opóźnienie publikacji danych śróddziennych (ok. 40 min, jeden pomiar 8.11) nie jest sprawdzalne historycznie (API trzyma ostatni `publication_ts`). Wykonanie z dnia D — możliwy eksperyment później, nie w P2.5.
- `CLAUDE.md`: dokumentacja etapu ma sekcję „Jak sprawdzić samodzielnie”.
- Ciągłość pracy nie wymaga scalania PR: nowa sesja zaczyna od gałęzi niescalonego PR (sekcja „Gałęzie”). Scalenie do `main` — najpóźniej przed tagiem `p2-v1.0`.
- Następne: P2.3.

## 2026-11-08 · P2.2 Dane — zrobione
**Zrobione:** klienci PSE (4 raporty, paginacja `nextLink`, ponawianie) i Open-Meteo (`_previous_day1`, 8 punktów); zapis parquet w plikach miesięcznych z zastępowaniem dób; CLI `uv run kse-data pse|weather|report`; raport kompletności; testy na zapisanych odpowiedziach API. Dokumentacja: `docs/etapy/P2.2.md`.

**Wyniki:** dane pobrane 14.06.2024–08.11.2026 (plan i RCE do 09.11): `his-wlk-cal` 84 292 wiersze, `pdgopkd` 84 388, `poze-redoze` 74 212 (od 27.09.2024), `rce-pln` 84 388, pogoda 168 576. Brakujące doby: 0, doby z błędną liczbą kwadransów: 0, duplikaty: 0, braki pogody: 0. Raport: `docs/kompletnosc_danych.md`. `pytest`: 26 passed, `ruff`: bez błędów.

**Problemy:** sieć środowiska blokowała API PSE i Open-Meteo — dodane hosty `api.raporty.pse.pl`, `previous-runs-api.open-meteo.com`, `historical-forecast-api.open-meteo.com` do środowiska „KSE” (za zgodą użytkownika).
- PR do `main`: https://github.com/Poted/kse-forecasting/pull/1 — scalenie z sesji zablokowane przez ustawienia uprawnień Claude Code (scalanie bez przeglądu). PR zostaje otwarty; scala użytkownik.

**Pytania do kierownika (nieblokujące):**
- `his-wlk-cal` zwraca też bieżącą dobę D z wykonaniem do bieżącego kwadransu (np. 08.11 o 16:07 UTC — dane do 15:45 UTC). Tabela w `00_fundament.md` sekcja 3 podaje tylko wykonanie za D−1. Czy w P2.5 cechy mają korzystać wyłącznie z D−1 (zgodnie z obecnym ustaleniem), czy rozważyć wykonanie z dnia D do ok. 11:45? Moment publikacji danych śróddziennych historycznie nie jest sprawdzony (API trzyma ostatni `publication_ts`).

## 2026-11-08 · decyzje dla P2.2, P2.5, P2.6 (rozmowa w projekcie)
- Zapisane w `context/00_fundament.md` sekcja 5: punkty pogodowe, historyczne prognozy od 27.09.2024, prognoza na jutro ręcznie.
- `CLAUDE.md`: operacje na PR przez REST (`gh api`), bo GraphQL nie działa w sesjach.
- Następne: P2.2.

## 2026-11-08 · scalenie P2.1 + gałęzie sesji (rozmowa w projekcie)
- Gałąź `claude/stoic-volta-sr0s01` (P2.1) scalona do `main`.
- Odpowiedź na pytanie o gałęzie: praca na gałęzi sesji, po każdym etapie PR do `main` i próba scalenia — zasady w `CLAUDE.md` (sekcja „Gałęzie”).
- Następne: P2.2.

## 2026-11-08 · P2.1 Środowisko — zrobione
**Zrobione:**
- Struktura: pakiety `common`, `p2`, `inz`, `app` (z `__init__.py`), `tests/`, `models/.gitkeep`, `config/.gitkeep`.
- `pyproject.toml` (Python 3.12, `uv`, `uv.lock`, `.python-version`), zależności wg zadania; dev: pytest, ruff; konfiguracja ruff (reguły E, F, W, I, B, UP; linia 100).
- `docker-compose.yml`: PostgreSQL 16, wolumen `pgdata`, healthcheck, dane logowania z `.env`; `.env.example`.
- `common/config.py`: `load_settings()` — `DATABASE_URL` ze zmiennej środowiskowej lub `.env`; brak → czytelny błąd.
- `tests/test_smoke.py`: importy pakietów, testy konfiguracji.
- README: sekcja „Uruchomienie” (w tym wariant bez Dockera).

**Wyniki:**
- `uv run pytest`: 10 passed. `uv run ruff check .`: bez błędów.
- `docker compose up -d --wait`: kontener `postgres:16` healthy (PostgreSQL 16.15); połączenie z Pythona przez `DATABASE_URL` (SQLAlchemy + psycopg) działa.

**Problemy:**
- W środowisku Claude Code demon Dockera nie był uruchomiony — uruchomiony ręcznie (`dockerd`), potem bez problemów.
- Push na gałąź sesji `claude/stoic-volta-sr0s01`, nie na `main` — środowisko sesji zezwala tylko na tę gałąź.

**Pytania do kierownika:**
- Czy zadania mają być pushowane na `main`, czy na gałęzie sesji z PR do `main`? → odpowiedź wyżej.

## 2026-11-08 · protokół samodzielny
- Claude Code realizuje etapy z `context/03_plan_wykonania.md` samodzielnie; dokumentacja etapów w `docs/etapy/`.

## 2026-11-08 · inicjalizacja
- Repozytorium założone: `CLAUDE.md`, `context/`, pierwsze zadanie `context/zadania/P2.1.md`.
