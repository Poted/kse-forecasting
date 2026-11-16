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

**Pierwsze uruchomienie — dane i modele** (jednorazowo, ok. 6–8 min):
```bash
docker compose exec app uv run --no-sync kse-init
```
`kse-init` pobiera dane, ładuje bazę, wykonuje walidację kroczącą i prognozę na jutro; kolejne uruchomienia odświeżają ostatnie 10 dób. Alternatywnie w dashboardzie: przy pustej bazie przycisk „Załaduj dane”.

**Wersja w chmurze** (Streamlit Community Cloud + Neon, codzienna prognoza w GitHub Actions): kroki wdrożenia w `docs/srodowisko.md`.

## 5.3 Uruchomienie lokalne (bez kontenera aplikacji)
```bash
uv sync
cp .env.example .env
docker compose up -d db
uv run kse-init                 # dane, baza, walidacja, prognoza na jutro
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
| `kse-init [--skip-download]` | przygotowanie systemu jednym poleceniem: dane, ładowanie, walidacja (gdy brak), prognoza na jutro |
| `kse-app` | dashboard |
| `python -m p2.analysis` | wykresy i tabele analizy (`docs/fig/p2_4_*`) |

## 5.5 Obsługa dashboardu
**Prognoza na jutro.** Przycisk „Przelicz prognozę na jutro” pobiera najnowsze dane, uczy model i zapisuje prognozę (ok. 1 min). Widok pokazuje dobę prognozy, średnią, minimum i maksimum, wykres godzinowy z prognozą PSE (po jej publikacji ok. 16:00) i — gdy doba minie — wykonanie. Ostrzeżenia pojawiają się, gdy wykonanie za poprzednią dobę jest niekompletne albo brakuje danych pogodowych. Tabela godzinowa jest w rozwijanej sekcji.

**Historia prognoz.** Dla każdej doby: ostatnia prognoza wykonana dzień wcześniej porównana z wykonaniem i z planem PSE — liczba porównanych dób, średni MAE, wykres dziennego MAE, podsumowanie wg wersji kodu, tabela dzienna. Doba pojawia się po publikacji pełnego wykonania (ok. 00:00–02:00 następnego dnia).

**Jakość prognoz.** Wybór okresu (doby docelowe) przeliczająca tabelę metryk (MAE, RMSE, MAPE, bias, błąd w szczycie i w minimum południowym) dla modeli bazowych, LightGBM i PSE. Suwak wybiera tydzień do porównania prognozy z wykonaniem. Wykresy MAE wg godziny i wg miesiąca.

**Analiza.** Profil dobowy netto wg pory roku, krzywa kaczki (czerwiec w kolejnych latach), dobowe minimum południowe i maksimum wieczorne, średnie miesięczne.

Wykresy: najechanie albo dotknięcie pokazuje wartości, kliknięcie w legendę ukrywa serię; przybliżanie jest wyłączone (na telefonie blokowało przewijanie). Panel boczny zawiera źródła danych i licencje.

## 5.6 Codzienna praca
W wersji w chmurze prognoza na jutro liczy się automatycznie codziennie o 10:17 UTC (GitHub Actions); lokalnie — przycisk albo `kse-p2 forecast`, w dniu D około 12:00. Dane PSE za dobę D−1 są publikowane ok. 00:00–02:00 dnia D. Model korzysta tylko z informacji dostępnych o 12:00 dnia D, więc godzina uruchomienia nie wpływa na wynik.

## 5.7 Rozwiązywanie problemów
| Objaw | Przyczyna / działanie |
|---|---|
| `Brak DATABASE_URL` | brak pliku `.env` — skopiuj `.env.example` |
| `connection refused` (port 5432) | baza nie działa — `docker compose up -d db` |
| Dashboard: „Brak prognozy” | uruchom przycisk przeliczenia albo `kse-p2 forecast` |
| Dashboard: „Brak prognoz historycznych” | uruchom `kse-p2 backtest` |
| Ostrzeżenie o niekompletnym wykonaniu za D−1 | PSE nie opublikował jeszcze pełnej doby — przelicz później |
| Dashboard: „Baza danych jest pusta” | nowa baza (np. w chmurze) — przycisk „Załaduj dane” albo `kse-init` |
| Streamlit Cloud: błąd po aktualizacji kodu | Manage app → Reboot app |
