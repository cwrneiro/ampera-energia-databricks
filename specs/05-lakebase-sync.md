# 05 — Lakebase & synced tables

## Goal

Serve the app from an **autoscaling Lakebase** Postgres database fed from gold via **synced
tables**, so the app gets low-latency reads without querying the lakehouse.

## Setup (decision #20)

- Project `ampera-demo`: Postgres 17, branch `production`, database `databricks_postgres`,
  endpoint `primary` autoscaling 0.5–4 CU, scale-to-zero after 1,200 s (20 min; was 300 s — raised
  2026-10-05 so a live demo rarely hits a cold compute). The app shows "Acordando o banco de dados…"
  and retries on its own when it does (spec 06).
- Synced tables in the standard-catalog schema `ampera_catalog.ampera_gold_lb` → Postgres schema
  `ampera_gold_lb` (no Lakebase UC catalog needed). Pipeline metadata in `ampera_catalog.default`.

| Synced table | Source | Primary key | Rows |
|---|---|---|---|
| `ampera_gold_lb.generation_daily` | `ampera_serving.generation_daily` | (dia, plant_id) | 1,458,248 |
| `ampera_gold_lb.plant_location` | `ampera_serving.plant_location` | (plant_id) | 2,292 |
| `ampera_gold_lb.reconciliation_monthly` | `ampera_gold.reconciliation_monthly` | (grao, mes, match_method) | 283 |
| `ampera_gold_lb.reconciliation_ai_review` | `ampera_gold.reconciliation_ai_review` | (ons_key) | — |
| `ampera_gold_lb.curtailment_daily` | `ampera_serving.curtailment_daily` | (dia, plant_id) | — |
| `ampera_gold_lb.curtailment_narrative` | `ampera_serving.curtailment_narrative` | (plant_id) | — |
| `ampera_gold_lb.client_plant_access` | `ampera_serving.client_plant_access` | (principal, plant_id) | — |

- Plant-grain tables sync from their unfiltered `ampera_serving` copy: synced tables refuse a source
  with a UC row filter, and the gold originals carry the client filter (spec 17). Row counts above
  are from the 2026-10-05 sync; later tables are counted in `evidence/06`.

- **SNAPSHOT** mode (gold is fully recomputed each run; no Change Data Feed needed). Refreshed by
  the job `ampera_refresh` (spec 04). Synced tables are created by CLI
  (`databricks postgres create-synced-table`) — DAB support isn't available yet.

## Acceptance criteria

- ✓ Lakebase project with autoscaling exists on `<profile>`.
- ✓ Synced tables ONLINE; rows and TWh match gold exactly; PK indexes present; a one-plant month
  query runs in 3.6 ms.
- ✓ A gold change reaches Lakebase: after the 2026-10-05 Open-Meteo backfill + refresh job, 2024–25
  modeled weather in `ampera_gold_lb.generation_daily` went from 0 to 92% of rows; totals still 1,404.19 TWh.
  The app SP kept USAGE/SELECT through the SNAPSHOT re-sync (no re-grant needed).
- ✓ The app reads Lakebase as its service principal (deployed 2026-10-02; totals tie to gold).

## Operating notes

- Synced tables are read-only in Postgres (SELECT, CREATE INDEX, DROP only).
- The app's service principal needs `USAGE` on schema `ampera_gold_lb` and `SELECT` on its tables
  (grant after the app is deployed and the syncs are ONLINE).
