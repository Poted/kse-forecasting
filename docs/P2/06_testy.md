# 6. Testy

Testy automatyczne: `uv run pytest` (63 testy, 16.11.2026: wszystkie przechodzą). Kontrola stylu: `uv run ruff check .` (bez błędów). Testy klientów API działają na zapisanych odpowiedziach (`tests/fixtures/`), bez dostępu do sieci. Testy bazy danych tworzą tymczasowy schemat i usuwają go po teście; bez działającej bazy są pomijane.

| Plik | Testy | Zakres |
|---|---|---|
| `test_smoke.py` | 13 | importy pakietów, konfiguracja (`.env`, zmienne środowiskowe, brak `DATABASE_URL`), adres bazy w formacie Neon |
| `test_http.py` | 3 | ponawianie zapytań (5xx, 429, błędy sieci), brak ponawiania przy 4xx |
| `test_pse.py` | 5 | paginacja `nextLink`, doba zmiany czasu (100 kwadransów), parsowanie czasu UTC w dwóch formatach |
| `test_openmeteo.py` | 4 | parametry zapytania (`_previous_day2`), format odpowiedzi dla wielu punktów, konfiguracja punktów |
| `test_storage_completeness.py` | 4 | liczba kwadransów doby (92/96/100), podział na miesiące, zastępowanie dób przy ponownym zapisie, wykrywanie braków i duplikatów |
| `test_db.py` | 8 | zgodność liczby wierszy, nadpisanie korekty bez duplikatu, widok godzinowy dla doby 25-godzinnej, zapis przebiegów i widok najnowszych prognoz |
| `test_p2_analysis.py` | 7 | metryki (MAE, RMSE, MAPE, bias, szczyt, minimum południowe; RMSE ≥ MAE), profile, głębokość krzywej kaczki, wykresy |
| `test_p2_features.py` | 10 | **brak przecieku informacji**, kontrola czułości, godziny doby przy zmianie czasu, moment prognozy, konwencja czasu pogody, opóźnienia, walidacja krocząca uczy się tylko na znanych dobach |
| `test_app.py` | 9 | stałe kolory serii, wykresy bez przybliżania, wykres prognozy, prognoza na jutro (w tym ostrzeżenie o niekompletnych danych), zapis prognozy, podsumowania historii prognoz (dzienne, wg wersji kodu), `kse-init` (wykrycie danych), sprawdzanie połączeń z bazą, uruchomienie dashboardu (4 zakładki, przeładowanie modułów) |

## Test braku przecieku informacji
Wymaganie NFR-02. `test_no_leakage` buduje cechy prognozy z dnia D, a następnie mnoży ×10 wszystkie dane niedostępne o 12:00 dnia D — wykonanie od początku doby D i prognozy pogody wydane po 12:00 dnia D. Cechy muszą pozostać identyczne. Test kontrolny (`test_available_data_is_used`) sprawdza, że zmiana danych dostępnych (wykonanie z D−1, pogoda wydana wcześniej) zmienia cechy — test przecieku nie przechodzi więc „pusto”. Osobny test sprawdza, że wśród cech nie ma pól planu PSE.

## Testy danych i weryfikacje ręczne
- Raport kompletności danych (`kse-data report`) i zgodność liczby wierszy (`kse-data db-check`).
- Średnie godzinowe netto z widoku bazy porównane z niezależną analizą wstępną (`docs/etapy/P2.3.md`) — zgodne.
- Powtarzalność: ponowne uruchomienie walidacji daje identyczne metryki (stałe ziarno, tryb deterministyczny LightGBM).
- Dashboard sprawdzony w przeglądarce (zrzuty `docs/fig/p2_6_widok_*.png`), także w kontenerze i na telefonie (emulacja iPhone 13 oraz wersja w chmurze).
- Scenariusz chmurowy odtworzony lokalnie: pusta baza + adres w formacie Neon → `kse-init` → dashboard bez błędów.
- Codzienna prognoza w GitHub Actions: pierwsze uruchomienie 15.11.2026 — sukces (53 s).
