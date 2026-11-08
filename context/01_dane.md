# 01 · Dane

Stan weryfikacji: 2026-11-08, na danych pobranych z API (nie na opisach).

## Źródła
API PSE: `https://api.raporty.pse.pl/api/<raport>?$filter=business_date ge 'YYYY-MM-DD' and business_date le 'YYYY-MM-DD'&$first=20000` (paginacja przez `nextLink`). Dokumentacja pól: https://api.raporty.pse.pl/EndpointsMap.pdf

| Raport | Zawartość | Zakres | Kompletność | Użycie |
|---|---|---|---|---|
| `his-wlk-cal` | wykonanie KSE co 15 min: `demand`, `pv`, `wi`, `jg`, `jgm`, `jnwrb`, `swm_p`, `swm_np` [MW] | od 14.06.2024 | 870 dni, 0 braków | P2: cel; inż: analiza, cechy |
| `pdgopkd` | plan koordynacyjny dobowy (prognozy PSE na D+1): `gen_fv`, `gen_wi`, `kse_pow_dem`, `rez_under`, `rez_over_demand`, `dom_balance_exchange_par`, `gen_jgw_jgm_jgz_jga`, `ogr_mwe` | od 14.06.2024 | 870 dni, 0 braków | inż: główne cechy; P2: benchmark |
| `poze-redoze` | nierynkowe redysponowanie OZE co 15 min: `pv_red_balance`, `pv_red_network`, `wi_red_balance`, `wi_red_network` [MW; ujemne = redukcja; null = brak] | od 27.09.2024 | 765 dni, 0 braków | inż: cel 1 |
| `rce-pln` | rynkowa cena energii `rce_pln` [zł/MWh] | od 14.06.2024 | 870 dni, 0 braków | inż: cel 2 |

Kompletność sprawdzona dla 14.06.2024–31.10.2026. Starsze dane PSE (przed 14.06.2024) są w raportach historycznych na stronie PSE, w innym formacie. Niesprawdzone.

### Pogoda — Open-Meteo
- **Archiwum prognoz** (`historical-forecast-api.open-meteo.com`): sprawdzone dla Warszawy 14.06–31.12.2024 — 4824 godziny, 0 braków (`shortwave_radiation`, `cloud_cover`, `temperature_2m`, `wind_speed_100m`). Dalszych okresów nie pobrano — połączenie ze środowiska kierownika było przerywane (problem środowiska, nie API).
- **Poprzednie przebiegi modeli** (`previous-runs-api.open-meteo.com`, zmienne z przyrostkiem `_previous_day1` = prognoza sprzed doby): zwraca dane dla 14.06.2024. Kompletność całego okresu — do sprawdzenia przy pobieraniu (P2.2).
- Dla prognozy D+1 właściwe są zmienne `_previous_day1` (prognoza wydana dobę wcześniej). Archiwum prognoz składa szereg z najświeższych przebiegów, więc jest bliższe pogodzie rzeczywistej niż prognozie na dobę naprzód.
- Zapas: ERA5 (Copernicus), IMGW — niesprawdzone.

## Zweryfikowane fakty
- Bilans: `demand = jg + jgm + jnwrb + swm_p + swm_np` (średni błąd 9 MW). `pv` i `wi` są częścią `jnwrb`.
- Momenty publikacji: wykonanie KSE za D−1 ok. 00:00–02:00 dnia D (lipiec–październik 2026; starsze rekordy mają późniejsze znaczniki publikacji — korekty); RCE na D+1 ok. 14:00 dnia D; plan PSE na D+1 ok. 16:00 dnia D (każdego dnia, min. 3,5 h przed dobą); ograniczenia OZE z medianą ok. 3 tygodnie po dobie.
- Jakość prognoz PSE w planie dobowym: PV MAE 325 MW (r = 0,986), wiatr 407 MW, zapotrzebowanie 383 MW.
- Ograniczenia PV: 444 z 765 dni; 12 480 kwadransów (2024: 172, 2025: 6765, 2026: 5543); typowo 50–1157 MW, maks. 4160 MW.
- P(cena < 0 | ograniczenie PV) = 0,21; bez ograniczeń 0,006.
- Rozmiar danych PSE (CSV, 14.06.2024–31.10.2026): ok. 59 MB.

## Pułapki (obowiązkowe w implementacji)
1. **Czas:** pracować na `dtime_utc` (koniec interwału 15-min). Lokalne `dtime` ma etykiety typu `02a:15` przy zmianie czasu; doby mają 92 lub 100 kwadransów.
2. **RCE:** do 09.2025 ceny godzinowe (4 jednakowe kwadranse), od 10.2025 kwadransowe.
3. **Moment informacji:** tylko dane dostępne w chwili prognozy (tabela w `00_fundament.md`, sekcja 3).
4. **Korekty danych:** PSE koryguje dane wstecz. W chwili prognozy dostępna była wersja pierwotna, w API jest wersja ostateczna — ograniczenie do opisania w pracy.
5. **Anomalie:** 102 kwadranse z ograniczeniem PV przy `pv == 0`, 2 w nocy — reguła czyszczenia.
6. **Pola puste:** w `his-wlk-cal` kolumny `jgz1`, `jgz3`, `jga`, `jgo` w 100% null; `jgw2`, `jgm2`, `jgz2` częściowo — nie używać.
7. **Pobieranie:** odtwarzalne z API (polecenie CLI). Duże zakresy w kawałkach, z ponawianiem.

## Źródła odrzucone
| Źródło | Powód |
|---|---|
| Ausgrid Solar Home (300 domów, 2010–13) | dane australijskie i stare; zdjęte ze strony Ausgrid |
| GoiEner (Hiszpania) | wersja przetworzona zawiera tylko zużycie |
| SimBench + pandapower | obliczenia rozpływowe poza kierunkiem |
| Dane AMI/CSIRE, Tauron dostepnemoce.pl | niepubliczne / tylko mapy statyczne |
