# ERD — baza danych

Wygenerowano ze schematu (`common/db.py`): `uv run kse-data erd --out docs/erd.md`.
Tabele `pse_*` nie mają kluczy obcych: łączy je czas (`dtime_utc`, koniec kwadransu UTC).
Widoki godzinowe: `v_wykonanie_h`, `v_plan_h`, `v_rce_h`, `v_pogoda_h`, `v_p2_forecast_latest`, `v_p2_operational_eval` (opis: `docs/etapy/P2.3.md`).

```mermaid
erDiagram
    inz_dataset {
        timestamptz dtime_utc PK
        date business_date
        int2 quarter_local
        int2 dow
        int2 month
        float8 doy_sin
        float8 doy_cos
        int2 is_holiday
        int2 is_weekend
        float8 kse_pow_dem
        float8 gen_fv
        float8 gen_wi
        float8 rez_under
        float8 rez_over_demand
        float8 dom_balance_exchange_par
        float8 dom_balance_exchange_non_par
        float8 gen_jgw_jgm_jgz_jga
        float8 ogr_mwe
        timestamptz plan_publication_ts_utc
        float8 p2_net_demand_hat
        float8 shortwave_radiation
        float8 cloud_cover
        float8 temperature_2m
        float8 wind_speed_100m
        float8 pv_red_balance_mw
        float8 pv_red_network_mw
        int2 y_red_balance
        int2 y_red_network
        int2 red_pv0_anomaly
        timestamptz red_publication_ts_utc
        float8 rce_pln
        int2 y_rce_neg
    }
    model_run {
        int4 run_id PK
        text model
        timestamptz created_at
        text code_version
        jsonb params
        jsonb train_info
        jsonb metrics
    }
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
    inz_prediction {
        int4 run_id PK,FK
        timestamptz dtime_utc PK
        date business_date
        float8 p_hat
        float8 mw_hat
    }
    p2_forecast {
        int4 run_id PK,FK
        timestamptz hour_utc PK
        date target_date
        date forecast_date
        timestamptz forecast_moment_utc
        float8 net_demand_hat
    }
    weather_forecast {
        int2 point_id PK,FK
        timestamptz time_utc PK
        float8 shortwave_radiation
        float8 cloud_cover
        float8 temperature_2m
        float8 wind_speed_100m
    }
    model_run ||--o{ inz_prediction : "run_id"
    model_run ||--o{ p2_forecast : "run_id"
    weather_point ||--o{ weather_forecast : "point_id"
```
