# CLAUDE.md

Jedno repozytorium dla dwóch prac:
- **P2** — *Prognozowanie zapotrzebowania netto na energię elektryczną w Polsce z wykorzystaniem uczenia maszynowego* (aplikacja analityczna + dokumentacja).
- **Inż** — *System prognozowania ryzyka nadpodaży energii elektrycznej związanej z generacją fotowoltaiczną w KSE z wykorzystaniem uczenia maszynowego* (praca inżynierska).

Kolejność: P2 (etapy P2.1–P2.7) → tag `p2-v1.0` → inż (I1–I6) na `main`.

## Protokół pracy (obowiązkowy)
Zadania przygotowuje kierownik projektu (osobna rozmowa Claude). Komunikacja wyłącznie przez repozytorium.

Na początku każdej sesji:
1. `git pull`.
2. Przeczytaj `docs/STAN.md` i znajdź pierwszy plik w `context/zadania/` ze statusem `do zrobienia`.
3. Przeczytaj materiały wskazane w zadaniu (zawsze: `context/01_dane.md` przy pracy z danymi).
4. Wykonaj zadanie. Jeśli zadanie ma pole „Akceptacja planu: tak” — najpierw przedstaw plan użytkownikowi i poczekaj.
5. Sprawdź warunek „Gotowe, gdy”. Jeśli nie da się go spełnić — opisz dlaczego w `docs/STAN.md` i zatrzymaj się.
6. Zaktualizuj `docs/STAN.md` (sekcja na górze: data, zadanie, co zrobione, wyniki, problemy, pytania do kierownika).
7. W pliku zadania zmień status na `zrobione` (albo `zablokowane`).
8. Commit + push na `main`.

Gdy nie ma zadania `do zrobienia` — napisz to użytkownikowi i nic nie zmieniaj.

## Zasady
- Fakty, nie przypuszczenia. Znaczenie pól sprawdzaj w danych lub w https://api.raporty.pse.pl/EndpointsMap.pdf. Czego nie wiesz — wpisz jako pytanie w `docs/STAN.md`.
- Nie rozstrzygaj samodzielnie pytań oznaczonych jako otwarte w `context/`.
- Nie zmieniaj plików w `context/` poza statusem zadania.
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
| `context/zadania/` | zadania do wykonania |
| `docs/STAN.md` | raporty z wykonania |

## Pułapki — skrót (pełna lista: `context/01_dane.md`)
1. Czas zawsze z `dtime_utc` (koniec interwału 15-min). Doby mają 92 lub 100 kwadransów.
2. Cechy tylko z danych dostępnych w chwili prognozy (tabela w `context/00_fundament.md`, sekcja 3). Wymagany test braku przecieku.
3. RCE godzinowe do 09.2025, kwadransowe od 10.2025.
4. PSE koryguje dane wstecz → upsert.
5. Puste kolumny `his-wlk-cal`: `jgz1`, `jgz3`, `jga`, `jgo` — nie używać.
