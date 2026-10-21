# 04 — Declarative Pipeline & refresh job

## Goal

One **Lakeflow Declarative Pipeline (SDP)** builds bronze → silver → gold on `<profile>`,
with data-quality expectations on the reconciliation output, and one job keeps Lakebase current.

## What exists (Databricks Asset Bundle `ampera`, target `dev`)

- **Pipeline `ampera_medallion`** (`resources/ampera_medallion.pipeline.yml`):
  serverless, triggered, SQL + Python files in `src/transformations/` (one dataset per file:
  `bronze_*`, `silver_*`, `gold_*`). Publishes to `bronze` by default; silver/gold use
  `schema.table` names resolved against the pipeline catalog (`var.catalog`), and bronze volume
  paths use `${catalog}` from the pipeline `configuration` (spec 10).
- **Job `ampera_refresh`** (`resources/ampera_refresh.job.yml`): medallion pipeline,
  then the three Lakebase synced-table pipelines (ids are bundle variables in `databricks.yml`).
  Daily 06:00 BRT, **paused**; unpause when the demo needs fresh data.

## Expectations (approach: fail on correctness, warn on quality)

| Rule | Dataset | Action |
|---|---|---|
| `plant_id` not null | plant_match, generation, generation_plant | fail |
| one row per (plant_id, ons_key, hour) | generation_plant_key_check | fail |
| monthly plant total within ±2% of published; no NULL month | generation_balance | warn |
| MWh ≥ 0 | generation, generation_plant | warn |
| PLD in range, known submarket | price_pld_hourly | warn |
| modeled weather present | weather_cell_hourly | warn |

Not implemented from the original list: a `confidence ∈ [0,1]` rule (true by construction) and an
orphan `plant_id` check (impossible by construction: `dim_plant` is built from the fact).

## Acceptance criteria

- ✓ Runs green end to end; all medallion tables populated.
- ✓ Violations are visible (warns in the event log; fails stop the update).
- ✓ `databricks bundle deploy -t dev --profile <profile>` creates/updates pipeline + job.

## Operating notes

- Deploy, then `databricks pipelines stop <id>` before `start-update`: a failed update's automatic
  retries otherwise race the new deploy.
- Materialized views recompute fully each run; no full refresh is needed for bronze unless its
  read schema changes.
