# 04 · Komunikacja między środowiskami

Źródło prawdy: repozytorium `Poted/kse-forecasting` (prywatne), folder `context/`.

## Role
| Kto | Gdzie | Co robi |
|---|---|---|
| Użytkownik | wszędzie | decyzje, pisanie tekstu pracy, uruchamianie Claude Code („kontynuuj”) i Colaba |
| Claude Code | sesja w repozytorium | samodzielnie realizuje etapy z `03_plan_wykonania.md` (protokół w `CLAUDE.md`); dokumentuje każdy etap w `docs/etapy/`; raportuje w `docs/STAN.md`; zatrzymuje się tylko przy brakującej decyzji |
| Rozmowa w projekcie claude.ai „Inżynierka” | claude.ai (dostęp do repozytorium) | zarządzanie projektem: przegląd kodu, dokumentacji i wyników, decyzje, część teoretyczna i praktyczna pracy, dokumentacja P2. Nie przekazuje poleceń do Claude Code |
| Colab | notebook z repozytorium | trening sieci (etap I3) |

## Cykl pracy
1. Użytkownik w Claude Code: `kontynuuj`. Claude Code realizuje kolejne etapy, aż skończy albo trafi na brakującą decyzję.
2. Decyzje potrzebne → `docs/STAN.md`. Użytkownik rozstrzyga je w Claude Code albo w rozmowie w projekcie; decyzja trafia do `00_fundament.md` sekcja 5.
3. Przegląd: w rozmowie w projekcie użytkownik prosi o „sprawdź stan” — rozmowa pobiera repozytorium, czyta `docs/STAN.md` i `docs/etapy/`, omawia kod i wyniki.

## Colab (etap I3)
- Notebook w `inz/notebooks/`; logika w plikach `.py` z repozytorium.
- Komórka startowa: klonowanie repozytorium tokenem z Colab Secrets (`GITHUB_TOKEN`: fine-grained, tylko `kse-forecasting`, `Contents: read`), instalacja pakietu, zamontowanie Dysku.
- Dane: Colab pobiera je z API tym samym poleceniem CLI co aplikacja i zapisuje na Dysk (`kse-forecasting/data/`).
- Wyniki: metryki i modele na Dysk (`kse-forecasting/results/`, `kse-forecasting/models/`). Colab nie robi pushu. Do repozytorium przenosi je Claude Code (małe pliki metryk → `results/`).

## Projects (claude.ai)
- Integracja GitHub w wiedzy projektu: wybrać `context/`, `docs/`. Synchronizacja ręczna (przycisk „Sync”).
- Po podpięciu repozytorium dokumenty z folderu `claude/` w projekcie można usunąć — inaczej będą dwie wersje.
