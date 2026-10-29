# 17 — UC: client row-level security (app + Genie)

## Goal

A generator client signs in to the same app and the same Genie space and sees **only its own
plants**; Ampera staff see everything. Extends spec 13 (analysts read gold only). Decided
2026-10-27 after the FE review.

## Design

- **Clients and portfolios:** two fictional clients in the committed seed
  `src/seed/client_portfolio.csv` — *Ventos do Nordeste Participações* (18 wind plants whose SIGA owner
  is an "Eólica Umburanas" SPE, BA) and *Sol do Sertão Energia* (22 solar plants owned by "SPE Futura"
  SPEs, BA). Real public plant ids; the ownership by the fictional clients is the demo's assumption.
- **Principals:** which users / service principals act for a client is workspace-specific, so it comes
  from the bundle variable `client_access` (JSON, set in the gitignored `targets/dev.yml`).
  `notebooks/client_access` writes `gold.client_plant_access` (principal × plant).
- **One rule, two enforcement points.** A principal listed in `client_plant_access` sees only its
  plants; anyone else (staff, pipelines, syncs) sees every row.
  - **UC row filter** `gold.client_plant_filter(plant_id)` (created by `scripts/bootstrap_workspace.sh`)
    on the five plant-grain gold tables: `fact_generation_hourly`, `generation_daily`, `plant_location`
    (declared in the pipeline, `WITH ROW FILTER`) and `curtailment_daily`, `curtailment_narrative` (CTAS
    in their notebooks). Genie runs on behalf of the user, so its answers are filtered by UC.
  - **App:** Lakebase synced tables **refuse a row-filtered source** ("cannot have both row/column
    security and online materialized views", verified 2026-10-27), so the synced tables read unfiltered
    copies in a new schema `ampera_serving` (granted to nobody) and the app re-applies the same mapping:
    `scope()` reads `x-forwarded-email`, and every Lakebase read for a client principal adds
    `plant_id IN (SELECT plant_id FROM client_plant_access WHERE principal = %s)`. Inside Apps an
    unidentified request is a 401, never "all plants".
- **Grants:** group `ampera_clients` gets `USE CATALOG`, `USE SCHEMA` on gold and `SELECT` on exactly
  the five filtered tables (no schema-wide SELECT, nothing on bronze/silver/serving), plus
  warehouse `CAN_USE`. Market-wide reconciliation is staff-only: no UC grant, a 403 in the app, and
  the Reconciliação sheet is hidden. The app header shows "Carteira <cliente>".
- **Asserted:** `notebooks/governance` fails the job if client grants drift from those five tables or
  any of them lacks `client_plant_filter`, and if analysts gain anything on `ampera_serving`.

## Acceptance

- `python3 tests/test_app_api.py`: client scope SQL, staff see all, 401 in Apps without a user,
  403 on reconciliation for a client.
- Live (`tests/test_rls_live.py`, a test service principal mapped to *Ventos do Nordeste*): on the
  warehouse it sees exactly its 18 plants in each of the five tables, and is denied on
  `reconciliation_monthly` and `ampera_serving`; Genie as that principal answers about its plants only.
- Totals for staff are unchanged (1,404.19 TWh).
