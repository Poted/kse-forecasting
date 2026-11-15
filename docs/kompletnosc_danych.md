# Raport kompletności danych surowych

Wygenerowano: 2026-11-13 12:00 UTC (`uv run kse-data report`).

## PSE

| Raport | Zakres dób | Wiersze | Doby z danymi | Brakujące doby | Doby z inną liczbą kwadransów | Duplikaty `dtime_utc` | `dtime_utc` poza siatką 15 min |
|---|---|---|---|---|---|---|---|
| `his-wlk-cal` | 2024-06-14 – 2026-11-13 | 84772 | 883/883 | 0 | 0 | 0 | 0 |
| `pdgopkd` | 2024-06-14 – 2026-11-14 | 84772 | 883/884 | 1 | 0 | 0 | 0 |
| `poze-redoze` | 2024-09-27 – 2026-11-13 | 74692 | 778/778 | 0 | 0 | 0 | 0 |
| `rce-pln` | 2024-06-14 – 2026-11-14 | 84772 | 883/884 | 1 | 0 | 0 | 0 |

### `his-wlk-cal`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `jga` 100.0% (84772), `jgo` 100.0% (84772), `jgz1` 100.0% (84772), `jgz3` 100.0% (84772), `jgz2` 76.6% (64944), `jgw2` 62.5% (52948), `jgm2` 57.6% (48820), `jg` 0.1% (48), `pv` 0.1% (48), `wi` 0.1% (48), `jgm` 0.1% (48), `jgm1` 0.1% (48), `jgw1` 0.1% (48), `jnwrb` 0.1% (48), `swm_p` 0.1% (48), `demand` 0.1% (48), `swm_np` 0.1% (48)

### `pdgopkd`

- Brakujące doby: 2026-11-14
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `gen_jga` 100.0% (84772), `gen_jgo` 100.0% (84772), `capacity_jga` 100.0% (84772), `capacity_jgo` 100.0% (84772), `gen_jgz_zak_1` 100.0% (84772), `capacity_jgz_zak_1` 100.0% (84772), `gen_jgm_zak_2` 91.6% (77664), `capacity_jgm_zak_2` 91.6% (77664), `gen_jgz_zak_3` 87.0% (73728), `capacity_jgz_zak_3` 87.0% (73728), `gen_jgz_zak_2` 76.6% (64896), `capacity_jgz_zak_2` 76.6% (64896), `gen_jgw_zak_2` 57.5% (48772), `capacity_jgw_zak_2` 57.5% (48772), `tot_jgm_char_pow` 8.6% (7296)

### `poze-redoze`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `pv_red_network` 95.3% (71180), `wi_red_network` 93.6% (69883), `wi_red_balance` 91.7% (68486), `pv_red_balance` 87.1% (65060)

### `rce-pln`

- Brakujące doby: 2026-11-14
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych: brak pustych wartości

## Open-Meteo (`_previous_day2`)

Zakres: 2024-06-13 – 2026-11-13 (doby UTC), wiersze: 169728, duplikaty (punkt, godzina): 0.

| Punkt | Brakujące godziny | puste `cloud_cover` | puste `shortwave_radiation` | puste `temperature_2m` | puste `wind_speed_100m` |
|---|---|---|---|---|---|
| Warszawa | 0 | 0 | 0 | 0 | 0 |
| Kraków | 0 | 0 | 0 | 0 | 0 |
| Wrocław | 0 | 0 | 0 | 0 | 0 |
| Poznań | 0 | 0 | 0 | 0 | 0 |
| Gdańsk | 0 | 0 | 0 | 0 | 0 |
| Rzeszów | 0 | 0 | 0 | 0 | 0 |
| Białystok | 0 | 0 | 0 | 0 | 0 |
| Szczecin | 0 | 0 | 0 | 0 | 0 |
