# 09 — Complex (conjunto) members

## Goal

ONS reports wind/solar complexes (`Conj. …` / `Conjunto …`, ~20% of MWh) as one series. Break them down into their
member plants, each with a CEG that links to SIGA, using ONS's own measured per-plant data. Where no
per-plant data exists, use an estimate that is clearly labeled as one. Decision #16.

## In scope

- **Bronze** (from the raw volume, as-ingested):
  - `ons_conjunto_member` ← `usina_conjunto` (`RELACIONAMENTO_USINA_CONJUNTO.parquet`): 304
    complexes → 2,143 members, with member CEG and validity dates.
  - `ons_member_generation_wind` / `_solar` ← `restricao_coff_{eolica,fotovoltaica}_detail`
    (monthly parquet, same 24-month window): `val_geracaoverificada` = measured MW per member, 30-min.
- **Silver**:
  - `conjunto_member`: complex key → member `id_ons`, normalized CEG, `plant_id`, validity dates.
  - `generation_plant`: hourly generation at **plant grain, with no double counting**. It contains
    the non-complex rows of `generation`, plus measured member rows (half-hour MW averaged to
    hourly MWh), plus estimated member rows for complex-hours that have no member detail.
  - `generation_balance`: monthly published total vs plant-grain total (the check).
- `dim_plant` gains complex member plants. `generation` stays as published, so "by conjunto" still
  works.

## Key decisions

- `match_method` for member rows: `member_measured` (confidence 1.0) or `member_estimated`
  (`is_estimated = true`, shown in the app as "estimado").
- Estimate: complex-hour total split across members active on that date (mapping validity dates),
  weighted by SIGA capacity. Complex-hours with no measured members get the estimate; if no member
  has a capacity, the row stays at complex level (`ons_conjunto`).
- Measured accuracy of the capacity split (Aug-2026, vs measured): monthly WAPE wind 9.5% /
  solar 7.4%, hourly 16.3% / 11.6%. That's why it is used only as a fallback.

## Acceptance criteria

- `generation_plant` monthly total within **±2%** of the published total (expectation on
  `generation_balance`; violations visible in the pipeline UI).
- `member_estimated` ≤ ~3% of complex MWh (actual 2.7%); `member_measured` ≥ 95% (actual 96.9%).
- 0 null `plant_id`; member CEGs link to SIGA for ≥ 98% of member MWh.

## Results (24 months, `silver.generation_plant`, 1,404.2 TWh)

- Monthly balance vs published: ratio **0.9917–0.9997** (within ±2%, all 24 months).
- Complex MWh: **member_measured 96.9%** · **member_estimated 2.7%** · left at complex level 0.41%.
- **Double count found & removed:** ONS publishes 24 wind plants both standalone and inside their
  complex (12 complexes, 1.9 TWh). The member copy is dropped where a standalone series exists;
  `silver.generation_plant_key_check` fails the update if any (plant_id, ons_key, hour) repeats.
  Plants with several ONS series (Itaipu 50/60 Hz, Belo Monte + Pimental, Henry Borden ext/sub…)
  are legitimate and summed per plant.
- Member MWh linked to SIGA: 99.0%. 0 null `plant_id`. `dim_plant` 2,292 rows.
- Ingest notes: solar detail bronze uses two append flows (flag column BOOLEAN in 2024 files, INT later).

## Open questions

- The ±2% balance check could not see the 0.13% double count (it hid inside the members' ~0.8%
  shortfall); the key check is what guards it now.
