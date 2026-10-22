# 13 — Unity Catalog governance

## Goal

Show the data is governed, not just stored: who can read what, what each asset is, and where it
came from. Decision #34.

## Design (`notebooks/governance`, last task of `ampera_refresh`, idempotent)

- **Catalog layout:** `ampera_catalog` (an existing catalog; the bundle never runs CREATE CATALOG —
  decision #28) with schemas `ampera_bronze / ampera_silver / ampera_gold / ampera_gold_lb`.
- **Access:** group `ampera_analysts` gets `USE CATALOG` + `USE SCHEMA, SELECT` on `ampera_gold`
  only; bronze/silver revoked. The app's Genie chat runs on behalf of the user, so these grants
  decide what each person can ask about.
- **Tags:** schema and table tags `ampera_layer`, `ampera_domain=energia`, `ampera_source` (ONS, ANEEL
  SIGA, CCEE, Open-Meteo, INMET, derived), `ampera_ai` on ML/GenAI outputs — namespaced because
  `layer`/`domain`/`source`/`project` may already be governed tag policies in a metastore; governed tag `class.geo_coordinates` on
  plant lat/lon (skipped with a message if the tag policy refuses).
- **Model:** `ampera_gold.curtailment_expected_cf` registered in UC (alias `champion`).
- **Lineage:** printed from `system.access.table_lineage` (bronze → silver → gold → ML → serving).

## Acceptance

- The governance task's output (grants, tags, lineage) is committed under `evidence/`.
