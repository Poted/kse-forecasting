# CLAUDE.md

Jedno repozytorium dla dwóch prac:
- **P2** — *Prognozowanie zapotrzebowania netto na energię elektryczną w Polsce z wykorzystaniem uczenia maszynowego* (aplikacja analityczna + dokumentacja).
- **Inż** — *System prognozowania ryzyka nadpodaży energii elektrycznej związanej z generacją fotowoltaiczną w KSE z wykorzystaniem uczenia maszynowego* (praca inżynierska).

Kolejność: P2 (etapy P2.1–P2.7) → tag `p2-v1.0` → inż (I1–I6) na `main`.

## Protokół pracy (obowiązkowy, samodzielny)
Claude Code prowadzi realizację samodzielnie według planu etapów w `context/03_plan_wykonania.md`. Użytkownik nie przekazuje poleceń z innych rozmów — wystarczy „kontynuuj”.

Na początku każdej sesji:
1. Ustal punkt startu (sekcja „Gałęzie”). Przeczytaj `docs/STAN.md` i tabelę „Stan” w `context/03_plan_wykonania.md`.
2. Bieżący etap = pierwszy w tabeli „Stan” bez statusu `zrobione`.
3. Jeśli nie ma pliku `context/zadania/<etap>.md` — utwórz go na podstawie `03_plan_wykonania.md` (format jak `P2.1.md`: zakres, „Gotowe, gdy”, decyzje, z których korzysta).
4. Decyzje: jeśli etap wymaga rozstrzygnięcia pytania otwartego (`00_fundament.md` sekcja 6, `03_plan_wykonania.md`), a decyzji nie ma w `00_fundament.md` sekcja 5 — dopisz pytanie w `docs/STAN.md` (sekcja „Decyzje potrzebne”), napisz to użytkownikowi i zatrzymaj się. Jeśli użytkownik rozstrzygnie je w sesji — dopisz decyzję z datą do `00_fundament.md` sekcja 5.
5. Wykonaj etap. Duże etapy dziel na kroki; commit po każdym kroku.
6. Dokumentuj etap w `docs/etapy/<etap>.md`: co powstało, jak działa, decyzje techniczne i ich powody, jak uruchomić, wyniki (liczby, wykresy). Pisz tak, żeby użytkownik mógł to zrozumieć i wykorzystać w dokumentacji P2 i w pracy inżynierskiej. Obowiązkowa sekcja „Jak sprawdzić samodzielnie”: 2–5 poleceń do uruchomienia po `uv sync` i `docker compose up -d` oraz oczekiwany wynik każdego z nich.
7. Sprawdź „Gotowe, gdy”. Jeśli nie da się go spełnić — opisz dlaczego w `docs/STAN.md` i zatrzymaj się.
8. Wpis w `docs/STAN.md` (na górze: data, etap, co zrobione, wyniki, problemy, pytania). Status `zrobione` w pliku zadania i w tabeli „Stan”. Commit + push, PR do `main` (sekcja „Gałęzie”).
9. Przejdź do następnego etapu (krok 2), chyba że użytkownik poprosił tylko o jeden etap.

Wyjątek: tag `p2-v1.0` (koniec P2) — tylko po akceptacji użytkownika.

## Gałęzie
**Od 16.11.2026 (decyzja użytkownika):** `p2` — tylko poprawki P2, na niej tagi `p2-v1.x`; `main` — praca inżynierska. Poprawka P2: commit na `p2`, potem `git merge p2` do `main` (nigdy `main` → `p2`). Nowy tag P2 tylko po akceptacji użytkownika. Pozostałe zasady poniżej dotyczą sytuacji, gdy środowisko nie pozwala pushować na `main`/`p2`.

- Jeśli możesz pushować na `main` — pracuj na `main`.
- Jeśli środowisko pozwala tylko na gałąź sesji (`claude/...`):
  - Start: `git fetch origin`; sprawdź otwarte PR-y do `main` (`gh api repos/Poted/kse-forecasting/pulls`). Jeśli jest niescalony PR z poprzedniej sesji — zacznij od jego gałęzi (scal ją do swojej gałęzi sesji). Inaczej zacznij od `origin/main`.
  - Po każdym etapie: push gałęzi sesji, PR do `main` (jeden PR na sesję, aktualizowany; `gh api -X POST repos/Poted/kse-forecasting/pulls`), spróbuj scalić (`gh api -X PUT repos/Poted/kse-forecasting/pulls/<nr>/merge`). GraphQL (`gh pr ...`) nie działa w sesjach Claude Code — używaj REST (`gh api`).
  - Jeśli scalenie jest niedozwolone — zostaw PR otwarty, zapisz to w `docs/STAN.md` i kontynuuj na tej samej gałęzi. Scala użytkownik albo rozmowa w projekcie.

## Zasady
- Fakty, nie przypuszczenia. Znaczenie pól sprawdzaj w danych lub w https://api.raporty.pse.pl/EndpointsMap.pdf. Czego nie wiesz — wpisz jako pytanie w `docs/STAN.md`.
- Nie rozstrzygaj samodzielnie pytań oznaczonych jako otwarte w `context/`.
- W `context/` zmieniasz tylko: pliki w `zadania/`, tabelę „Stan” w `03_plan_wykonania.md` i decyzje użytkownika w `00_fundament.md` sekcja 5. Reszta to ustalenia użytkownika.
- Tylko zakres zadania. Bez funkcji spoza zakresu (np. logowania użytkowników).
- Logika w plikach `.py`; notebooki tylko do analizy i uruchamiania.
- Testy dla każdego modułu. Bez sekretów i bez danych w repozytorium (`data/`, `models/*.pkl` itp. w `.gitignore`).
- Krótkie podsumowania.

## Materiały
| Plik | Zawartość |
|---|---|
| `context/00_fundament.md` | tematy, zakres obu prac, mechanika prognoz, dostępność informacji w czasie, decyzje |
| `context/01_dane.md` | raporty PSE, pola, pogoda, zweryfikowane fakty, **pułapki** |
| `context/02_wymagania.md` | wymagania funkcjonalne i niefunkcjonalne, przypadki użycia |
| `context/03_plan_wykonania.md` | etapy z warunkami „Gotowe, gdy”, narzędzia, struktura repozytorium |
| `context/04_komunikacja.md` | protokół kierownik ↔ Claude Code ↔ Colab |
| `context/05_literatura.md` | literatura |
| `context/zadania/` | zadania (tworzone z planu etapów) |
| `docs/STAN.md` | raporty z wykonania, decyzje potrzebne |
| `docs/etapy/` | dokumentacja każdego etapu |

## Pułapki — skrót (pełna lista: `context/01_dane.md`)
1. Czas zawsze z `dtime_utc` (koniec interwału 15-min). Doby mają 92 lub 100 kwadransów.
2. Cechy tylko z danych dostępnych w chwili prognozy (tabela w `context/00_fundament.md`, sekcja 3). Wymagany test braku przecieku.
3. RCE godzinowe do 09.2025, kwadransowe od 10.2025.
4. PSE koryguje dane wstecz → upsert.
5. Puste kolumny `his-wlk-cal`: `jgz1`, `jgz3`, `jga`, `jgo` — nie używać.
