# kse-forecasting

Prognozowanie w Krajowym Systemie Elektroenergetycznym na podstawie danych PSE:
- **P2:** prognoza zapotrzebowania netto (zapotrzebowanie − generacja PV) na dobę naprzód,
- **Praca inżynierska:** prognoza ryzyka nadpodaży energii z PV (ograniczenia generacji PV przez PSE, ujemne ceny RCE).

Kontekst projektu: `context/`. Stan prac: `docs/STAN.md`. **Dokumentacja P2: `docs/P2/`.** Środowisko pracy (laptop, telefon, chmura): `docs/srodowisko.md`.

## Uruchomienie

Wymagania: [uv](https://docs.astral.sh/uv/) (sam pobierze Python 3.12), Docker z Compose (albo lokalny PostgreSQL 16).

### Instalacja
```bash
uv sync
```

### Baza danych
1. Ustawienia: `cp .env.example .env` i zmień hasło (`POSTGRES_PASSWORD` oraz to samo w `DATABASE_URL`).
2. Start bazy PostgreSQL 16 (dane w wolumenie `pgdata`) i dashboardu (http://localhost:8501):
   ```bash
   docker compose up -d
   ```
   Tylko baza: `docker compose up -d db`. Zatrzymanie: `docker compose down` (dane zostają;
   `docker compose down -v` usuwa wolumen).

**Bez Dockera:** zainstaluj PostgreSQL 16 lokalnie, utwórz użytkownika i bazę zgodnie z `.env`
(np. `createuser -P kse` i `createdb -O kse kse`) i ustaw `DATABASE_URL`
na `postgresql+psycopg://kse:<hasło>@localhost:5432/kse`.

Aplikacja odczytuje `DATABASE_URL` z `.env` (`common/config.py`); zmienna środowiskowa ma pierwszeństwo.

### Pobieranie danych
```bash
uv run kse-data pse        # raporty PSE → data/raw/pse/
uv run kse-data weather    # Open-Meteo → data/raw/openmeteo/
uv run kse-data report --out docs/kompletnosc_danych.md
```
Szczegóły: `docs/etapy/P2.2.md`.

### Ładowanie do bazy
```bash
uv run kse-data load       # schemat + upsert z data/raw/
uv run kse-data db-check   # zgodność liczby wierszy parquet vs baza
```
Schemat i widoki godzinowe: `docs/etapy/P2.3.md`, ERD: `docs/erd.md`.

### Modele (P2)
```bash
uv run kse-p2 backtest     # walidacja krocząca, metryki, prognozy historyczne do bazy
```
Szczegóły: `docs/etapy/P2.5.md`.

### Prognoza na jutro i dashboard (P2)
```bash
uv run kse-p2 forecast     # pobranie najnowszych danych, trening, prognoza netto na jutro
uv run kse-inz dataset     # inż: zbiór uczący (tabela inz_dataset), statystyki celów
uv run kse-inz c1          # inż: cel 1 (ograniczenia PV) — modele bazowe i LightGBM, metryki
uv run kse-app             # dashboard Streamlit: http://localhost:8501
```
Szczegóły: `docs/etapy/P2.6.md`.

### Testy i lint
```bash
uv run pytest
uv run ruff check .
```

## Struktura
| Katalog | Zawartość |
|---|---|
| `common/` | klienci API, baza, czas/kalendarz, walidacja, cechy wspólne |
| `p2/` | model zapotrzebowania netto |
| `inz/` | modele nadpodaży, notebooki Colab |
| `app/` | dashboard Streamlit |
| `tests/` | testy |
| `config/` | konfiguracja |
| `models/` | zapisane modele (poza gitem) |
| `docs/` | dokumentacja, `STAN.md` |

Źródła danych: [API raportów PSE](https://api.raporty.pse.pl), [Open-Meteo](https://open-meteo.com).
