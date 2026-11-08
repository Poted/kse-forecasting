# 04 · Komunikacja między środowiskami

Źródło prawdy: repozytorium `Poted/kse-forecasting` (prywatne), folder `context/`.

## Role
| Kto | Gdzie | Co robi |
|---|---|---|
| Użytkownik | wszędzie | decyzje, akceptacja planów, pisanie tekstu pracy (z pomocą kierownika), uruchamianie Claude Code i Colaba |
| Kierownik | rozmowa w projekcie claude.ai „Inżynierka” (dostęp do repozytorium) | planuje; pisze zadania w `context/zadania/`; aktualizuje `context/`; czyta `docs/STAN.md`; omawia etapy z użytkownikiem |
| Claude Code | sesja Claude Code w repozytorium | wykonuje zadania wg protokołu z `CLAUDE.md`; raportuje w `docs/STAN.md` |
| Colab | notebook z repozytorium | trening sieci (etap I3) |

## Cykl pracy
1. Kierownik zapisuje zadanie `context/zadania/<etap>.md` (status `do zrobienia`) i robi push.
2. Użytkownik w Claude Code wpisuje: `kontynuuj`.
3. Claude Code: pull → zadanie → wykonanie → `docs/STAN.md` → status `zrobione` → push.
4. Użytkownik w rozmowie z kierownikiem: „sprawdź stan”. Kierownik robi pull, czyta `docs/STAN.md`, weryfikuje wynik, omawia go z użytkownikiem i przygotowuje kolejne zadanie.

Pytania Claude Code do kierownika trafiają do `docs/STAN.md` (sekcja „Pytania do kierownika”). Odpowiedzi kierownik wpisuje w kolejnym zadaniu albo w `context/`.

## Colab (etap I3)
- Notebook w `inz/notebooks/`; logika w plikach `.py` z repozytorium.
- Komórka startowa: klonowanie repozytorium tokenem z Colab Secrets (`GITHUB_TOKEN`: fine-grained, tylko `kse-forecasting`, `Contents: read`), instalacja pakietu, zamontowanie Dysku.
- Dane: Colab pobiera je z API tym samym poleceniem CLI co aplikacja i zapisuje na Dysk (`kse-forecasting/data/`).
- Wyniki: metryki i modele na Dysk (`kse-forecasting/results/`, `kse-forecasting/models/`). Colab nie robi pushu. Do repozytorium przenosi je Claude Code w kolejnym zadaniu (małe pliki metryk → `results/`; modele → według zadania).

## Projects (claude.ai)
- Integracja GitHub w wiedzy projektu: wybrać `context/` i `docs/STAN.md`. Synchronizacja ręczna (przycisk „Sync”).
- Po podpięciu repozytorium dokumenty z folderu `claude/` w projekcie można usunąć — inaczej będą dwie wersje.
