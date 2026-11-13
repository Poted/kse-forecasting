# ERD — baza danych

Wygenerowano ze schematu (`common/db.py`): `uv run kse-data erd --out docs/erd.md`.
Tabele `pse_*` nie mają kluczy obcych: łączy je czas (`dtime_utc`, koniec kwadransu UTC).
Widoki godzinowe: `v_wykonanie_h`, `v_plan_h`, `v_rce_h`, `v_pogoda_h` (opis: `docs/etapy/P2.3.md`).

```mermaid
erDiagram
    pse_his_wlk_cal {
        timestamptz dtime_utc PK
        date business_date
        float8 demand
        float8 pv
        float8 wi
        float8 jg
        float8 jgm
        float8 jnwrb
        float8 swm_p
        float8 swm_np
        float8 jgw1
        float8 jgm1
        timestamptz publication_ts_utc
    }
    pse_pdgopkd {
        timestamptz dtime_utc PK
        date business_date
        float8 kse_pow_dem
        float8 gen_fv
        float8 gen_wi
        float8 rez_under
        float8 rez_over_demand
        float8 dom_balance_exchange_par
        float8 dom_balance_exchange_non_par
        float8 gen_jgw_jgm_jgz_jga
        float8 ogr_mwe
        timestamptz publication_ts_utc
    }
    pse_poze_redoze {
        timestamptz dtime_utc PK
        date business_date
        float8 pv_red_balance
        float8 pv_red_network
        float8 wi_red_balance
        float8 wi_red_network
        timestamptz publication_ts_utc
    }
    pse_rce_pln {
        timestamptz dtime_utc PK
        date business_date
        float8 rce_pln
        timestamptz publication_ts_utc
    }
    weather_point {
        int2 point_id PK
        text name
        float8 lat
        float8 lon
    }
    weather_forecast {
        int2 point_id PK,FK
        timestamptz time_utc PK
        float8 shortwave_radiation
        float8 cloud_cover
        float8 temperature_2m
        float8 wind_speed_100m
    }
    weather_point ||--o{ weather_forecast : "point_id"
```
