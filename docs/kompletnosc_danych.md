# Raport kompletności danych surowych

Wygenerowano: 2026-11-08 16:13 UTC (`uv run kse-data report`).

## PSE

| Raport | Zakres dób | Wiersze | Doby z danymi | Brakujące doby | Doby z inną liczbą kwadransów | Duplikaty `dtime_utc` | `dtime_utc` poza siatką 15 min |
|---|---|---|---|---|---|---|---|
| `his-wlk-cal` | 2024-06-14 – 2026-11-08 | 84292 | 878/878 | 0 | 0 | 0 | 0 |
| `pdgopkd` | 2024-06-14 – 2026-11-09 | 84388 | 879/879 | 0 | 0 | 0 | 0 |
| `poze-redoze` | 2024-09-27 – 2026-11-08 | 74212 | 773/773 | 0 | 0 | 0 | 0 |
| `rce-pln` | 2024-06-14 – 2026-11-09 | 84388 | 879/879 | 0 | 0 | 0 | 0 |

### `his-wlk-cal`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `jga` 100.0% (84292), `jgo` 100.0% (84292), `jgz1` 100.0% (84292), `jgz3` 100.0% (84292), `jgz2` 77.0% (64926), `jgw2` 62.8% (52930), `jgm2` 57.9% (48802), `jg` 0.0% (30), `pv` 0.0% (30), `wi` 0.0% (30), `jgm` 0.0% (30), `jgm1` 0.0% (30), `jgw1` 0.0% (30), `jnwrb` 0.0% (30), `swm_p` 0.0% (30), `demand` 0.0% (30), `swm_np` 0.0% (30)

### `pdgopkd`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `gen_jga` 100.0% (84388), `gen_jgo` 100.0% (84388), `capacity_jga` 100.0% (84388), `capacity_jgo` 100.0% (84388), `gen_jgz_zak_1` 100.0% (84388), `capacity_jgz_zak_1` 100.0% (84388), `gen_jgm_zak_2` 92.0% (77664), `capacity_jgm_zak_2` 92.0% (77664), `gen_jgz_zak_3` 87.4% (73728), `capacity_jgz_zak_3` 87.4% (73728), `gen_jgz_zak_2` 76.9% (64896), `capacity_jgz_zak_2` 76.9% (64896), `gen_jgw_zak_2` 57.8% (48772), `capacity_jgw_zak_2` 57.8% (48772), `tot_jgm_char_pow` 8.6% (7296)

### `poze-redoze`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych (kolumny z brakami): `pv_red_network` 95.3% (70700), `wi_red_network` 93.5% (69403), `wi_red_balance` 91.6% (68006), `pv_red_balance` 87.0% (64580)

### `rce-pln`

- Brakujące doby: —
- Doby z inną liczbą kwadransów: —
- Udział wartości pustych: brak pustych wartości

## Open-Meteo (`_previous_day1`)

Zakres: 2024-06-14 – 2026-11-08 (doby UTC), wiersze: 168576, duplikaty (punkt, godzina): 0.

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
