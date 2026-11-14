# Prognozowanie zapotrzebowania netto na energię elektryczną w Polsce z wykorzystaniem uczenia maszynowego

Dokumentacja projektu P2 (aplikacja analityczna). Stan: 14.11.2026.

Aplikacja prognozuje godzinowe **zapotrzebowanie netto** KSE (zapotrzebowanie − generacja fotowoltaiczna) na dobę naprzód. Prognoza jest wykonywana w dniu D o 12:00 na 24 godziny doby D+1, na podstawie danych PSE, prognoz pogody Open-Meteo i kalendarza. Aplikacja porównuje własne prognozy z prognozą operatora (plan dobowy PSE) i udostępnia analizę profili dobowych oraz krzywej kaczki w dashboardzie.

| Dokument | Zawartość |
|---|---|
| [01_technologie.md](01_technologie.md) | technologie i biblioteki z wersjami, uzasadnienie wyboru |
| [02_architektura.md](02_architektura.md) | komponenty, przepływ danych, moment prognozy i dostępność informacji |
| [03_model_danych.md](03_model_danych.md) | ERD, tabele, widoki |
| [04_wyniki.md](04_wyniki.md) | analiza danych, modele, porównanie z PSE |
| [05_instrukcja.md](05_instrukcja.md) | instalacja, pobieranie danych, trening, prognoza na jutro, dashboard |
| [06_testy.md](06_testy.md) | testy automatyczne i ich zakres |

Szczegóły techniczne każdego etapu: `docs/etapy/P2.1.md`–`P2.6.md`. Wymagania: `context/02_wymagania.md`.

## W skrócie
- **Dane:** 4 raporty API PSE (wykonanie KSE, plan dobowy, redysponowanie OZE, ceny RCE) od 14.06.2024, prognozy pogody dla 8 miast; komplet bez brakujących dób.
- **Baza:** PostgreSQL 16 — tabele kwadransowe, widoki godzinowe, rejestr przebiegów modeli i prognozy historyczne.
- **Model:** LightGBM na 21 cechach dostępnych o 12:00 dnia D; walidacja krocząca od 27.09.2024.
- **Wynik:** MAE 797 MW (MAPE 5,9%) — o 49% mniej niż najlepszy model bazowy; prognoza PSE (publikowana ok. 4 h później) — MAE 531 MW.
- **Aplikacja:** dashboard Streamlit (prognoza na jutro, jakość prognoz, analiza); uruchomienie: `docker compose up -d`.
