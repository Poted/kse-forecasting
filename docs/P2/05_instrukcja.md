# 5. Instrukcja

## 5.1 Wymagania
- Docker z Docker Compose (baza i aplikacja), albo PostgreSQL 16 zainstalowany lokalnie.
- Do pracy bez kontenera aplikacji: [uv](https://docs.astral.sh/uv/) (instaluje Python 3.12).
- Dostęp do internetu: `api.raporty.pse.pl`, `previous-runs-api.open-meteo.com`.

## 5.2 Instalacja i uruchomienie (Docker)
```bash
git clone https://github.com/Poted/kse-forecasting.git
cd kse-forecasting
cp .env.example .env            # ustaw hasło: POSTGRES_PASSWORD i to samo w DATABASE_URL
docker compose up -d --build    # baza (db) + dashboard (app)
```
Dashboard: http://localhost:8501. Zatrzymanie: `docker compose down` (dane w bazie zostają).

**Pierwsze uruchomienie — dane i modele** (jednorazowo, ok. 5 min):
```bash
docker compose exec app uv run --no-sync kse-data pse        # raporty PSE od 14.06.2024
docker compose exec app uv run --no-sync kse-data weather    # pogoda od 13.06.2024
docker compose exec app uv run --no-sync kse-data load       # ładowanie do bazy
docker compose exec app uv run --no-sync kse-p2 backtest     # walidacja, prognozy historyczne
docker compose exec app uv run --no-sync kse-p2 forecast     # prognoza na jutro
```

## 5.3 Uruchomienie lokalne (bez kontenera aplikacji)
```bash
uv sync
cp .env.example .env
docker compose up -d db
uv run kse-data pse && uv run kse-data weather && uv run kse-data load
uv run kse-p2 backtest
uv run kse-p2 forecast
uv run kse-app                  # http://localhost:8501
```

## 5.4 Polecenia
| Polecenie | Działanie |
|---|---|
| `kse-data pse [--start RRRR-MM-DD] [--end …] [--report …]` | pobranie raportów PSE do `data/raw/pse/` |
| `kse-data weather [--start …] [--end …]` | pobranie pogody do `data/raw/openmeteo/` |
| `kse-data report [--out plik.md]` | raport kompletności danych |
| `kse-data load` | utworzenie schematu i załadowanie danych do bazy (upsert) |
| `kse-data db-check` | zgodność liczby wierszy pliki ↔ baza |
| `kse-data erd [--out plik.md]` | diagram ERD ze schematu |
| `kse-p2 backtest [--no-save]` | walidacja krocząca, metryki (`docs/fig/p2_5_metryki.md`), wykresy, zapis prognoz |
| `kse-p2 forecast [--no-update]` | prognoza netto na jutro (z odświeżeniem danych albo bez) |
| `kse-app` | dashboard |
| `python -m p2.analysis` | wykresy i tabele analizy (`docs/fig/p2_4_*`) |

## 5.5 Obsługa dashboardu
**Prognoza na jutro.** Przycisk „Przelicz prognozę na jutro” pobiera najnowsze dane, uczy model i zapisuje prognozę (ok. 1 min). Widok pokazuje dobę prognozy, średnią, minimum i maksimum, wykres godzinowy z prognozą PSE (po jej publikacji ok. 16:00) i — gdy doba minie — wykonanie. Ostrzeżenia pojawiają się, gdy wykonanie za poprzednią dobę jest niekompletne albo brakuje danych pogodowych. Tabela godzinowa jest w rozwijanej sekcji.

**Jakość prognoz.** Wybór okresu (doby docelowe) przeliczająca tabelę metryk (MAE, RMSE, MAPE, bias, błąd w szczycie i w minimum południowym) dla modeli bazowych, LightGBM i PSE. Suwak wybiera tydzień do porównania prognozy z wykonaniem. Wykresy MAE wg godziny i wg miesiąca.

**Analiza.** Profil dobowy netto wg pory roku, krzywa kaczki (czerwiec w kolejnych latach), dobowe minimum południowe i maksimum wieczorne, średnie miesięczne.

Wykresy są interaktywne: najechanie pokazuje wartości, kliknięcie w legendę ukrywa serię. Panel boczny zawiera źródła danych i licencje.

## 5.6 Codzienna praca
Prognoza na jutro jest uruchamiana ręcznie (przycisk albo `kse-p2 forecast`) — zgodnie z założeniem w dniu D około 12:00. Dane PSE za dobę D−1 są publikowane ok. 00:00–02:00 dnia D.

## 5.7 Rozwiązywanie problemów
| Objaw | Przyczyna / działanie |
|---|---|
| `Brak DATABASE_URL` | brak pliku `.env` — skopiuj `.env.example` |
| `connection refused` (port 5432) | baza nie działa — `docker compose up -d db` |
| Dashboard: „Brak prognozy” | uruchom przycisk przeliczenia albo `kse-p2 forecast` |
| Dashboard: „Brak prognoz historycznych” | uruchom `kse-p2 backtest` |
| Ostrzeżenie o niekompletnym wykonaniu za D−1 | PSE nie opublikował jeszcze pełnej doby — przelicz później |
