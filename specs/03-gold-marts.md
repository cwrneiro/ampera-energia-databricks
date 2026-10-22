# 03 — Gold Marts

## Goal

Query-ready gold tables the app and Genie read: generation by CEG and by conjunto, enriched with
price and weather — Ampera's "geração por CEG e/ou por conjunto".

## Tables (decision #17) — `ampera_catalog.ampera_gold`, SQL materialized views

| Table | Grain | Rows | Served |
|---|---|---|---|
| `fact_generation_hourly` | plant × hour (from `ampera_silver.generation_plant`) | ~35M | lakehouse (Genie) |
| `generation_daily` | plant × day; PK (dia, plant_id) | 1.46M | Lakebase |
| `plant_location` | plant; lat/lon, capacity, totals | 2,292 | Lakebase |
| `reconciliation_monthly` | grao (publicado / usina) × month × method | 283 | Lakebase |

By CEG / UF / fonte / conjunto are GROUP BYs on `generation_daily`. Gold reads **one** silver fact
(plant grain) and never sums it with the as-published one. Estimated MWh stays visible
(`is_estimated`, `mwh_estimado`). Totals tie: 1,404.2 TWh across all four.

## Enrichment

- **Price (decision #19):** CCEE PLD horário joined on (submercado = ONS subsystem, hour) — 100% of
  MWh priced. Hourly `pld_rs_mwh`, `valor_rs`; daily `pld_medio_rs_mwh`, `pld_capturado_rs_mwh`
  (generation-weighted), `valor_rs`. Captured vs average PLD: solar −22.8%, thermal +15.6%.
- **Weather (decision #18):** `*_modelo` columns from Open-Meteo (the plant's 0.25° cell; on every
  located plant-hour); `*_medido` columns from ONS at the plant, else the nearest INMET station
  ≤ 50 km (`fonte_medicao`, `estacao_inmet`, `dist_estacao_km`). Measured share of located MWh:
  ONS 22% · INMET 55% · none 23%.
- **Alignment checks:** all clocks are local Brasília time; Open-Meteo/INMET radiation is a
  preceding-hour mean, shifted one hour. Best correlation at 0 h shift: modeled vs ONS irradiance
  0.93, INMET vs modeled irradiance 0.94 / temperature 0.95.

## Labeling notes for the app

ONS irradiance is likely panel-plane (tracking) while ERA5/INMET are horizontal — show separately.
INMET wind is at 10 m (corr 0.37 with 100 m model wind) — a weak proxy. Solar members show a midday
output dip while irradiance peaks (curtailment) — a demo point.

## Acceptance criteria

- ✓ Generation by CEG and by conjunto (series + totals). ✓ Price- and weather-enriched columns
  non-empty. ✓ One row per `plant_id` in `plant_location` (85% of MWh has coordinates).
- ✓ Open-Meteo history complete: all 24 months × 469 cells in the volume (2026-10-05); modeled
  weather on 92% of 2024–25 plant-days and 93% of 2026 (the rest have no coordinates).
