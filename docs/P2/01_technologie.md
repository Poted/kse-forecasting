# 1. Technologie

Wersje według `uv.lock` i środowiska uruchomieniowego (16.11.2026).

## Środowisko
| Technologia | Wersja | Zastosowanie |
|---|---|---|
| Python | 3.12 | język całej aplikacji |
| uv | 0.11.32 | zarządzanie środowiskiem i zależnościami; plik `uv.lock` zapewnia te same wersje pakietów lokalnie i w kontenerze |
| PostgreSQL | 16 (obraz `postgres:16`) | baza danych |
| Docker, Docker Compose | — | uruchomienie bazy i aplikacji jednym poleceniem |
| Git, GitHub | — | repozytorium kodu i dokumentacji |
| GitHub Actions | — | codzienna prognoza automatyczna (`.github/workflows/prognoza-dzienna.yml`) |
| Streamlit Community Cloud | — | hosting dashboardu (wdrożenie z gałęzi `main`) |
| Neon | PostgreSQL w chmurze | baza danych wersji w chmurze (plan Free) |

## Biblioteki
| Biblioteka | Wersja | Zastosowanie |
|---|---|---|
| httpx | 0.28.1 | klienci API PSE i Open-Meteo (z ponawianiem zapytań) |
| pandas | 3.1.1 | przetwarzanie szeregów czasowych |
| numpy | 2.5.4 | obliczenia numeryczne |
| pyarrow | 26.0.1 | zapis surowych danych w formacie Parquet |
| SQLAlchemy | 2.1.8 | schemat bazy, zapytania, upsert |
| psycopg | 3.3.8 | sterownik PostgreSQL |
| LightGBM | 4.7.0 | model prognostyczny (gradientowo wzmacniane drzewa decyzyjne) |
| scikit-learn | 1.9.1 | interfejs modelu (`LGBMRegressor`) |
| holidays | 0.108 | kalendarz świąt w Polsce |
| Streamlit | 1.67.0 | dashboard |
| Plotly | 7.1.0 | interaktywne wykresy w dashboardzie |
| matplotlib | 3.11.2 | wykresy statyczne do dokumentacji (`docs/fig/`) |
| pytest | 9.2.0 | testy automatyczne |
| ruff | 0.17.4 | kontrola stylu i jakości kodu |
| Jupyter (ipykernel, nbconvert) | — | notebook analizy (`p2/notebooks/`), tylko uruchamianie |

## Źródła danych
| Źródło | Dane | Licencja / warunki |
|---|---|---|
| API raportów PSE (`api.raporty.pse.pl`) | wykonanie KSE, plan koordynacyjny dobowy, redysponowanie OZE, ceny RCE | źródło podane w aplikacji; warunki korzystania — do potwierdzenia |
| Open-Meteo, Previous Runs API | prognozy pogody wydane 48 h przed godziną docelową | CC BY 4.0 (strona licencji Open-Meteo) |

## Uzasadnienie wyboru
| Wybór | Powód |
|---|---|
| PostgreSQL | relacyjny model danych z kluczami czasowymi, upsert (`INSERT … ON CONFLICT`) dla korekt wstecznych PSE, typ JSONB dla parametrów i metryk modeli |
| Parquet jako warstwa surowa | odtwarzalność: dane z API zapisane bez zmian, baza ładowana z plików; kolumnowy format o małym rozmiarze (PSE: 16 MB za 2,4 roku) |
| LightGBM | szybki trening na CPU (walidacja krocząca: 27 treningów w ok. 1 min), obsługa brakujących wartości, dobre wyniki dla danych tabelarycznych; temat zgłoszony jako „uczenie maszynowe” |
| Streamlit + Plotly | dashboard w Pythonie, bez osobnego frontendu; interaktywne wykresy |
| uv + `uv.lock` | jedno polecenie instalacji, identyczne wersje w każdym środowisku |
| Docker Compose | wymaganie niefunkcjonalne NFR-04: baza i aplikacja jednym poleceniem |
| Streamlit Community Cloud + Neon | dashboard dostępny z telefonu pod stałym adresem, bez własnego serwera; obie usługi w planach bezpłatnych wystarczają (zużycie: pamięć do 296 MB, baza ok. 110 MB) |
| GitHub Actions | harmonogram (cron) bez własnego serwera; Streamlit Cloud nie ma harmonogramu zadań |
