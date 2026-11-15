# Środowisko pracy i testowania

Stan: 15.11.2026. Decyzja użytkownika z 15.11 (`context/00_fundament.md` sekcja 5): testy na laptopie z Windows, dashboard do przeglądania z telefonu na **Streamlit Community Cloud** z bazą **Neon** (PostgreSQL w chmurze), praca nad kodem z telefonu w sesjach Claude Code.

| Gdzie | Do czego | Jak |
|---|---|---|
| Laptop (Windows) | pełne testy: baza, dashboard, polecenia | Docker Desktop — rozdz. 1 |
| Telefon w domowej sieci Wi-Fi | dashboard z laptopa | `http://<IP-laptopa>:8501` — rozdz. 1.4 |
| Telefon gdziekolwiek (np. na wakacjach) | dashboard pod stałym adresem, bez komputera | Streamlit Cloud + Neon — rozdz. 2–4 |
| Telefon: aplikacja Claude | zmiany w kodzie, kolejne etapy („kontynuuj”) | sesje Claude Code — rozdz. 5 |
| Telefon: aplikacja GitHub | przegląd i scalanie PR, dokumentacja (`docs/P2/`) | rozdz. 5 |

## 1. Laptop (Windows)

### 1.1 Instalacja (jednorazowo)
1. **Docker Desktop** z backendem WSL 2 (https://www.docker.com/products/docker-desktop/). Po instalacji uruchom Docker Desktop.
2. **Git for Windows** (https://git-scm.com/download/win).
3. Opcjonalnie **uv** (tylko do pracy bez kontenera aplikacji; https://docs.astral.sh/uv/).

### 1.2 Pierwsze uruchomienie (PowerShell)
```powershell
git clone https://github.com/Poted/kse-forecasting.git
cd kse-forecasting
Copy-Item .env.example .env        # w .env zmień hasło: POSTGRES_PASSWORD i to samo w DATABASE_URL
docker compose up -d --build       # baza + dashboard
docker compose exec app uv run --no-sync kse-init
```
`kse-init` pobiera dane (pierwszy raz: wszystkie od 14.06.2024), ładuje bazę, wykonuje walidację kroczącą i prognozę na jutro. Pierwsze uruchomienie: ok. 6–8 min. Dashboard: http://localhost:8501.

### 1.3 Kolejne uruchomienia
```powershell
docker compose up -d
docker compose exec app uv run --no-sync kse-init    # odświeżenie danych (ostatnie 10 dób) + prognoza na jutro
```
Po zmianach w kodzie (`git pull`): `docker compose up -d --build`.

### 1.4 Dashboard z laptopa na telefonie (ta sama sieć Wi-Fi)
1. Na laptopie: `ipconfig` → adres IPv4 karty Wi-Fi (np. `192.168.1.23`).
2. Na telefonie: `http://192.168.1.23:8501`.
3. Jeśli strona się nie otwiera: zapora Windows musi dopuszczać połączenia przychodzące do Docker Desktop w sieci prywatnej (przy pierwszym uruchomieniu Windows zwykle o to pyta), a profil sieci Wi-Fi powinien być ustawiony jako „Prywatna”.

## 2. Baza w chmurze: Neon (jednorazowo, z laptopa)
1. Załóż konto na https://neon.tech i utwórz projekt (region w Europie, np. Frankfurt; PostgreSQL 16 lub nowszy).
2. Skopiuj **connection string** projektu. Ma postać:
   `postgresql://<użytkownik>:<hasło>@<host>.neon.tech/<baza>?sslmode=require`
   Aplikacja przyjmuje go bez zmian (sama dobiera sterownik psycopg 3).
3. Sprawdź limit miejsca w planie Neon: lokalna baza z danymi i wszystkimi przebiegami modeli zajmuje 132 MB (15.11.2026).
4. Załaduj dane z laptopa do Neon (kontener aplikacji musi działać — rozdz. 1.2):
   ```powershell
   docker compose exec -e DATABASE_URL="<connection string z Neon>" app uv run --no-sync kse-init
   ```
   Pusta baza → pełne ładowanie wszystkich danych, walidacja krocząca i prognoza na jutro. Czas zależy od łącza (lokalnie 3,5 min; do bazy w chmurze dłużej).

**Hasło do bazy** wpisujesz tylko w poleceniu na laptopie i w ustawieniach Streamlit Cloud (rozdz. 3). Nie wpisuj go do repozytorium ani do rozmowy z Claude.

## 3. Dashboard w chmurze: Streamlit Community Cloud (jednorazowo)
Warunek: kod dashboardu jest na gałęzi `main` (scalony PR z P2.5–P2.7).

1. Zaloguj się na https://share.streamlit.io kontem GitHub i zezwól na dostęp do prywatnych repozytoriów.
2. **Create app** → repozytorium `Poted/kse-forecasting`, gałąź `main`, plik główny `app/dashboard.py`.
3. **Advanced settings:**
   - Python version: **3.12**,
   - Secrets:
     ```toml
     DATABASE_URL = "<connection string z Neon>"
     ```
4. **Deploy.** Zależności: Streamlit Cloud instaluje je z `uv.lock` (te same wersje co lokalnie), a pakiet systemowy `libgomp1` (wymagany przez LightGBM) z `packages.txt`.

Fakty z dokumentacji Streamlit Community Cloud (repozytorium `streamlit/docs`, stan z 13.11.2026):
- aplikacja z prywatnego repozytorium jest prywatna; na koncie dozwolona jest jedna prywatna aplikacja; dostęp dla innych osób — zaproszenie e-mailem (**Share**),
- aplikacja bez ruchu przez 12 h usypia; otwarcie strony i przycisk „Yes, get this app back up!” ją budzi,
- sekrety z poziomu głównego są dostępne także jako zmienne środowiskowe (z tego korzysta aplikacja),
- domyślny Python: 3.12.

## 4. Codzienne korzystanie z telefonu
- Otwórz adres aplikacji `….streamlit.app` (zalogowany tym samym kontem GitHub/Streamlit).
- **Przelicz prognozę na jutro** — pobiera najnowsze dane z PSE i Open-Meteo, uczy model i zapisuje prognozę w Neon (ok. 1 min).
- Każde scalenie zmian do `main` aktualizuje aplikację automatycznie.

## 5. Praca nad kodem z telefonu (np. na wakacjach)
1. **Claude Code** (aplikacja Claude, sesja w repozytorium `Poted/kse-forecasting`): „kontynuuj” — realizacja kolejnych etapów według `CLAUDE.md`; zmiany trafiają do PR.
2. **GitHub** (aplikacja): przegląd PR, dokumentacji (`docs/`, diagramy i wykresy wyświetlają się), scalenie do `main`.
3. Po scaleniu Streamlit Cloud aktualizuje dashboard — sprawdzasz zmiany na telefonie.

Testowanie zmian **przed** scaleniem: konto pozwala na jedną prywatną aplikację, więc druga aplikacja z gałęzi roboczej nie jest możliwa bez upublicznienia. Przed scaleniem zmiany sprawdza Claude Code (testy automatyczne, zrzuty ekranu dashboardu w PR) — Ty oceniasz je po scaleniu na telefonie albo po powrocie na laptopie.

## 6. Rozwiązywanie problemów
| Objaw | Działanie |
|---|---|
| Streamlit Cloud: błąd instalacji | logi w panelu aplikacji („Manage app”); sprawdź, czy `uv.lock` i `packages.txt` są na `main` |
| Streamlit Cloud: `Brak DATABASE_URL` | brak sekretu `DATABASE_URL` w ustawieniach aplikacji |
| Błąd połączenia z bazą Neon | connection string z `?sslmode=require`; projekt Neon aktywny |
| „Brak prognoz historycznych” w dashboardzie | baza Neon niezaładowana — rozdz. 2.4 |
| Pogoda nieodświeżona (HTTP 429) | limit zapytań darmowego API Open-Meteo — spróbuj później; `kse-init` działa dalej na danych z dysku |
