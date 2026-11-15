# 00 · Fundament: P2 i praca inżynierska

Stan ustaleń: 2026-11-08. Punkt wyjścia dla każdej nowej rozmowy o obu pracach.
Źródło prawdy: repozytorium `Poted/kse-forecasting`, folder `context/`.
Dokumenty: `01_dane.md` (dane), `02_wymagania.md` (wymagania, przypadki użycia), `03_plan_wykonania.md` (etapy, narzędzia, repozytorium), `04_komunikacja.md` (kierownik ↔ Claude Code ↔ Colab), `05_literatura.md` (literatura), `zadania/` (zadania dla Claude Code).

## Zasada pracy (obowiązuje w każdej rozmowie)
- Wyłącznie fakty: podane przez użytkownika albo sprawdzone w danych lub źródłach. Niczego nie dopowiadamy ani nie zgadujemy.
- Czego nie wiadomo — zapisujemy jako pytanie otwarte. Propozycje oznaczamy jako propozycje.
- Krótko i do rzeczy. Bez dodatków, o które użytkownik nie prosił.
- Formalności uczelniane (zgłaszanie tematów, kontakt z prowadzącymi) prowadzi użytkownik — nie są częścią tych prac.
- Tekst pracy pisze użytkownik z pomocą kierownika (research, struktura, sprawdzanie). Kod powstaje w Claude Code. Użytkownik ma rozumieć każdy etap.

## Kontekst (od użytkownika)
- Kierunek: informatyka i analiza danych. Obie prace indywidualne.
- Ostatni semestr; wszystko do oddania w styczniu 2027. P2: termin 24.01.2027.
- Zamiar użytkownika: oddać pracę inżynierską przed grudniem 2026.
- Kod może być współdzielony między P2 a pracą inżynierską.
- Użytkownik ma płatny Google Colab; implementacja w Claude Code.

---

## 1. P2 — Profesjonalna aplikacja z elementami analizy danych

**Prowadzący:** Gajda
**Temat (zgłoszony):** Prognozowanie zapotrzebowania netto na energię elektryczną w Polsce z wykorzystaniem uczenia maszynowego
**Opis (zgłoszony):** Aplikacja prognozująca godzinowe zapotrzebowanie na energię z sieci na dobę do przodu, z uwzględnieniem produkcji z fotowoltaiki i danych pogodowych.
**Wymaganie prowadzącego (cytat przekazany przez użytkownika):** to ma być działająca aplikacja i ma coś analizować. Dokumentacja: technologie, diagramy, np. model bazy danych. Brak innych wymagań co do bazy.

### Pojęcia
- **Zapotrzebowanie KSE (`demand`)** — łączna moc pobierana przez odbiorców w Polsce w kwadransie [MW]. W danych: średnio 18 163 MW, zakres 10 464–27 734 MW.
- **Generacja PV (`pv`)** — moc z fotowoltaiki w kwadransie [MW]; wg opisu PSE obejmuje szacunek produkcji prosumentów (metoda niepodana). Maks. w danych 14 565 MW.
- **Zapotrzebowanie netto = `demand − pv`** — część zapotrzebowania pokrywana przez pozostałe źródła (konwencjonalne, wiatr, import). To prognozujemy w P2.

Średnie godzinowe z danych PSE [MW]:

| Godzina | XII 2025: demand | pv | **netto** | VI 2026: demand | pv | **netto** |
|---|---|---|---|---|---|---|
| 4:00 | 15 610 | 0 | **15 610** | 13 710 | 220 | **13 480** |
| 8:00 | 20 670 | 490 | **20 190** | 18 280 | 7 240 | **11 040** |
| 13:00 | 21 840 | 1 820 | **20 020** | 18 970 | 10 250 | **8 720** |
| 20:00 | 20 840 | 0 | **20 840** | 19 230 | 540 | **18 690** |

Latem netto spada w południe i rośnie wieczorem (krzywa kaczki); zimą zjawiska prawie nie ma.

### Mechanika prognozy (ustalone)
- **Moment i horyzont:** prognoza wykonywana w dniu D o 12:00 (czas lokalny) na 24 godziny doby D+1.
- **Cechy:** kalendarz (godzina, dzień tygodnia, miesiąc, święto); historia netto (D−1 i D−7 o tej samej godzinie, średnie z ostatnich dni); prognoza pogody na D+1 (nasłonecznienie, zachmurzenie, temperatura).
- **Zakaz przecieku informacji:** tylko dane dostępne o 12:00 dnia D (tabela w sekcji 3).
- **Modele bazowe:** „jak wczoraj” (D−1), „jak tydzień temu” (D−7). Model: LightGBM.
- **Benchmark:** prognoza PSE z planu dobowego (`kse_pow_dem − gen_fv`). Publikowana ok. 16:00 dnia D, czyli po naszej prognozie — służy tylko do porównania.
- **Ocena:** walidacja krocząca; MAE, RMSE, MAPE; błąd w szczycie i w minimum południowym.
- **Pogoda w danych historycznych:** archiwalne prognozy (Open-Meteo) — szczegóły w `01_dane.md`.

### Dashboard P2 (wstępnie przyjęte)
1. Prognoza na jutro z prognozą PSE.
2. Jakość prognoz: prognoza vs wykonanie, błędy wg godzin i miesięcy.
3. Analiza: profile dobowe w sezonach, krzywa kaczki.

---

## 2. Praca inżynierska (inż)

**Promotor:** Mirosław Gajer
**Tytuł:** System prognozowania ryzyka nadpodaży energii elektrycznej związanej z generacją fotowoltaiczną w Krajowym Systemie Elektroenergetycznym z wykorzystaniem uczenia maszynowego
**Opis:**
> Celem pracy jest opracowanie systemu prognozującego z wyprzedzeniem jednej doby okresy nadpodaży energii elektrycznej w Krajowym Systemie Elektroenergetycznym, wynikające z wysokiej generacji źródeł fotowoltaicznych. System będzie prognozował wystąpienie i skalę nierynkowego redysponowania (ograniczania) generacji fotowoltaicznej przez operatora systemu przesyłowego oraz ryzyko wystąpienia ujemnych cen energii elektrycznej. Modele zostaną zbudowane na podstawie oficjalnych danych publikowanych przez Polskie Sieci Elektroenergetyczne, w tym planów koordynacyjnych, danych o pracy systemu i cenach energii, uzupełnionych danymi meteorologicznymi. W pracy zostaną porównane metody uczenia maszynowego, w tym gradientowo wzmacniane drzewa decyzyjne i sieci neuronowe, z modelami bazowymi. Wyniki zostaną udostępnione w interaktywnym interfejsie prezentującym prognozy i okresy zagrożenia nadpodażą.

**Wymagania formalne (z notatek użytkownika):** ok. 40 stron; teoria 10–15 s.; część praktyczna ok. 30 s. (specyfikacja wymagań, opis systemu, przypadki użycia, diagramy klas, testowanie, krótki podręcznik użytkownika); zakończenie: osiągnięcia i kierunki rozwoju.

### Zakres
- **Pytanie:** czy jutro wystąpi nadpodaż energii z PV, w których kwadransach i jak duża?
- **Cel 1 (rdzeń):** ograniczenia PV przez PSE na każdy kwadrans D+1 — klasyfikacja (jest/nie ma) i regresja (MW). Prognoza po 16:00 dnia D (po publikacji planu PSE na D+1).
- **Cel 2:** ryzyko ujemnych cen RCE na D+1. Prognoza o 12:00 dnia D (RCE na D+1 publikowane ok. 14:00 dnia D).
- **Opcja:** symulacja magazynu energii — poza opisem tematu, tylko jeśli starczy czasu.
- **Cechy:** plan dobowy PSE na D+1 (prognozy PV, wiatru, zapotrzebowania, rezerw, wymiany), historyczne prognozy z P2, kalendarz, pogoda.
- **Modele:** baseline’y (kalendarz, reguły z planu PSE) → LightGBM → MLP i LSTM (Colab). Własne modele od zera, bez fine-tuningu.
- **Walidacja:** trening do 31.12.2025, test na 2026 + walidacja krocząca. Metryki: AUC, AP, F1, MAE [MW].
- **System:** rozszerzenie aplikacji z P2 o widoki: ryzyko nadpodaży na jutro, historyczne epizody, porównanie modeli; testy; podręcznik.

Wyniki sprawdzenia danych (1.11.2026): ograniczenia PV w 444 z 765 dni, 12 480 kwadransów, typowo 50–1157 MW, maks. 4160 MW; ok. 2750 kwadransów z ujemną ceną (2025–10.2026). Szybki test: ograniczenia bilansowe w kwadransach przewidywalne (AUC 0,97; AP 0,87 vs 0,70 dla baseline’u kalendarzowego); flaga dzienna nie bije prostego baseline’u — dlatego celem są godziny i skala.

### Część teoretyczna (10–15 s.) — propozycja
| Podrozdział | Zawartość |
|---|---|
| KSE i bilansowanie | struktura KSE, rola OSP, plany koordynacyjne, źródła dyspozycyjne i must-run, rezerwy |
| Fotowoltaika w Polsce | wzrost mocy, prosumenci, zapotrzebowanie netto, krzywa kaczki |
| Nadpodaż i redysponowanie | przyczyny, podstawy prawne (UE 2019/943 art. 13, Prawo energetyczne), redysponowanie bilansowe vs sieciowe, rekompensaty, skala w Polsce |
| Rynek energii i ceny ujemne | rynek dnia następnego, RCE, mechanizm cen ujemnych, net-billing |
| Metody prognozowania | gradient boosting, MLP, LSTM, klasyfikacja i regresja, metryki, walidacja w czasie, przeciek informacji |
| Istniejące rozwiązania | prognozy PSE, luka badawcza |

### Część praktyczna (ok. 30 s.) — propozycja
| Rozdział | Zawartość |
|---|---|
| Analiza danych | źródła, jakość, moment publikacji, zjawisko w liczbach |
| Specyfikacja wymagań | z `02_wymagania.md` |
| Przypadki użycia | aktorzy, diagram |
| Projekt systemu | architektura, diagram klas, model danych |
| Modele i eksperymenty | baseline’y, LightGBM, MLP, LSTM; cele 1 i 2; wyniki |
| Testowanie | testy jednostkowe, testy danych, walidacja modeli |
| Podręcznik użytkownika | uruchomienie, obsługa dashboardu |
| Zakończenie | osiągnięcia, ograniczenia, kierunki rozwoju |

---

## 3. Dostępność informacji w czasie (sprawdzone w danych)
| Informacja | Dotyczy doby | Dostępna (czas lokalny) |
|---|---|---|
| Wykonanie KSE (`his-wlk-cal`) | D−1 | ok. 00:00–02:00 dnia D; później bywa korygowane |
| Ceny RCE (`rce-pln`) | D+1 | ok. 14:00 dnia D (mediana 10,2 h przed początkiem doby) |
| Plan dobowy PSE (`pdgopkd`) | D+1 | ok. 16:00 dnia D (mediana 8,1 h przed początkiem doby) |
| Ograniczenia OZE (`poze-redoze`) | — | mediana ok. 3 tygodnie po dobie → nie jako cecha |
| Prognozy pogody (Open-Meteo, poprzednie przebiegi modeli) | D+1 | w chwili prognozy |

| Prognoza | Moment | Wejście |
|---|---|---|
| P2: zapotrzebowanie netto D+1 | 12:00 D | wykonanie do D−1, pogoda, kalendarz |
| Inż, cel 2: ceny ujemne D+1 | 12:00 D | jak P2 + prognoza P2 |
| Inż, cel 1: ograniczenia PV D+1 | po 16:00 D | plan PSE na D+1, prognoza P2, pogoda, kalendarz |

## 4. Jak P2 łączy się z inż
- Jedno repozytorium (`Poted/kse-forecasting`); P2 buduje fundament (dane, baza, walidacja, dashboard), inż dokłada nowe cele, modele i widoki. Szczegóły: `03_plan_wykonania.md`.
- Historyczne prognozy z P2 są cechą modeli inż.
- P2 odpowiada „ile energii trzeba dostarczyć”, inż „czy i kiedy będzie jej za dużo”.

## 5. Decyzje
| Data | Decyzja |
|---|---|
| 01.11 | Odrzucone: przepływy zwrotne w sieci nN (obliczenia rozpływowe poza kierunkiem, brak polskich danych sieci nN) |
| 01.11 | Odrzucone dane: Ausgrid (Australia 2010–13, nieutrzymywane przez źródło), GoiEner (brak generacji w wersji przetworzonej) |
| 01.11 | Temat inż: nadpodaż PV w KSE na danych PSE; „uczenie maszynowe” zamiast „głębokie sieci” w tytule |
| 01.11 | Brak logowania użytkowników |
| 02.11 | Prognoza P2 o 12:00 dnia D na dobę D+1 |
| 08.11 | Kolejność: P2, potem inż; jedno repozytorium `Poted/kse-forecasting` (prywatne), gałąź `main`, koniec P2 = tag `p2-v1.0` |
| 08.11 | Komunikacja przez repozytorium; Claude Code realizuje etapy samodzielnie (`CLAUDE.md`) |
| 08.11 | Punkty pogodowe (P2.2): Warszawa, Kraków, Wrocław, Poznań, Gdańsk, Rzeszów, Białystok, Szczecin; wartości uśrednione dla kraju. Wagi wg mocy PV w regionach — możliwe rozszerzenie później |
| 08.11 | Historyczne prognozy P2 (P2.5): od 27.09.2024, model uczony na dostępnej historii od 14.06.2024 (wariant 1). Słabsze pierwsze miesiące raportowane w metrykach |
| 08.11 | Prognoza na jutro (P2.6): uruchamiana ręcznie — przycisk w dashboardzie i polecenie CLI; bez harmonogramu |
| 13.11 | Pogoda w P2 (P2.5): zmienne Open-Meteo `_previous_day2` (prognoza wydana 48 h przed godziną docelową) zamiast `_previous_day1`. Powód: wg dokumentacji Open-Meteo `_previous_day1` to wartość prognozowana 24 h przed godziną docelową — dla godzin D+1 po ok. 12:00 wydana po momencie prognozy (przeciek). `_previous_day2` jest dostępna o 12:00 dnia D dla wszystkich godzin D+1 |
| 15.11 | Środowisko testów: laptop z Windows (Docker Desktop); dashboard do przeglądania z telefonu na Streamlit Community Cloud z bazą Neon (PostgreSQL w chmurze); praca nad kodem z telefonu w sesjach Claude Code. Odrzucone: dashboard w sesjach Claude (zużycie tokenów, limit 2 h), Netlify (nie uruchamia aplikacji Streamlit) |

## 6. Pytania otwarte
- Dokładna data oddania pracy inżynierskiej; zasady uczelni dot. AI; wymagany szablon pracy.

## 7. Linki
- [API PSE — mapa raportów i pól (PDF)](https://api.raporty.pse.pl/EndpointsMap.pdf) · [Portal raportów PSE](https://raporty.pse.pl) · [PSE — raporty historyczne](https://www.pse.pl/raporty-historyczne)
- [PSE — opis wielkości planu koordynacyjnego](https://www.pse.pl/dane-systemowe/plany-pracy-kse/plan-koordynacyjny-5-letni/wielkosci-podstawowe/opis) · [PSE — publikacja danych o redysponowaniu OZE](https://www.pse.pl/-/zmiana-sposobu-publikacji-danych-o-nierynkowym-redysponowaniu-oze)
- Przykładowa doba (15.06.2026): [his-wlk-cal](https://api.raporty.pse.pl/api/his-wlk-cal?$filter=business_date%20eq%20%272026-06-15%27) · [pdgopkd](https://api.raporty.pse.pl/api/pdgopkd?$filter=business_date%20eq%20%272026-06-15%27) · [poze-redoze](https://api.raporty.pse.pl/api/poze-redoze?$filter=business_date%20eq%20%272026-06-15%27) · [rce-pln](https://api.raporty.pse.pl/api/rce-pln?$filter=business_date%20eq%20%272026-06-15%27)
- [Open-Meteo — archiwum prognoz](https://open-meteo.com/en/docs/historical-forecast-api) · [Open-Meteo — poprzednie przebiegi modeli](https://open-meteo.com/en/docs/previous-runs-api)
