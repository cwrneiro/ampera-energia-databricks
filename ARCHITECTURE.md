# ARCHITECTURE — what this project builds, what it uses, how it connects

## 1. What it does

ONS publishes hourly generation per plant. ANEEL SIGA is the registry of what each plant is and
where it sits. The two don't join directly: CEG codes are formatted differently, about half of ONS
series have no CEG, and ONS mixes single plants with wind/solar complexes and state totals. This
project reconciles them in a Lakeflow Declarative Pipeline and adds CCEE hourly prices (PLD) and
weather. The results are served through Lakebase Postgres to a PT-BR web app with a map, and
through a Genie space for natural-language questions.

**Core invariant:** every ONS generation row resolves to exactly one `plant_id`, in this order:
manual override → normalized CEG → fuzzy name (same UF and fuel, numerals must match) →
complex/aggregate label → stable surrogate `SURR-…`. Each row records its `match_method` and
`confidence`. Generation is never dropped and never double counted, and pipeline expectations
enforce both (§4.4).

## 2. Resource inventory

`<catalog>` = bundle variable `catalog`, set in the gitignored overlay `targets/dev.yml`
(template: `targets/dev.yml.example`).

### Created by the bundle (`databricks bundle deploy`)

| Resource | Bundle key / file | Notes |
|---|---|---|
| Pipeline `ampera_medallion` | `resources/ampera_medallion.pipeline.yml` | Serverless, triggered; catalog `var.catalog`, default schema `ampera_bronze`; code = `src/transformations/**` |
| Job `ampera_refresh` | `resources/ampera_refresh.job.yml` | medallion → `adjudicate_ai` (ai_decide, re-runs the medallion only when it wrote new verdicts) → ML scoring → the synced-table pipelines (`var.sync_pipeline_*`) → governance; daily 06:00 BRT, paused by default |
| App `ampera-app` | `resources/ampera_app.app.yml`, `app/` | FastAPI + built React SPA; `postgres` resource on `projects/${var.lakebase_project}/branches/production`, `CAN_CONNECT_AND_CREATE`; gets its own service principal |
| Genie space "Ampera · Geração Elétrica" | `resources/ampera_genie.genie_space.yml` + JSON body | Runs on `var.warehouse_id`; 4 gold tables, instructions, examples, 32 benchmarks |

### Created by scripts (CLI / SQL, outside the bundle; README "Reproduce")

| Resource | Script | Points at it |
|---|---|---|
| Schemas `ampera_bronze` `ampera_silver` `ampera_gold` `ampera_gold_lb` (in an existing catalog) | `scripts/bootstrap_workspace.sh` | `var.catalog` |
| Volume `<catalog>.ampera_bronze.raw` (one folder per source) | `bootstrap_workspace.sh`; files: `scripts/land_raw_data.sh` | `${catalog}` in the bronze SQL |
| Table `<catalog>.ampera_silver.plant_match_override` | `bootstrap_workspace.sh` | read by `silver_plant_match.py` |
| Lakebase project (PG 17; endpoint `primary`, 0.5–4 CU, suspends after 20 min) | `bootstrap_workspace.sh` | `var.lakebase_project`, `LAKEBASE_ENDPOINT` in `app/app.yaml` |
| Table `<catalog>.ampera_silver.ai_decide_verdict` (durable ai_decide verdicts) | `bootstrap_workspace.sh` (empty); rows: job task `adjudicate_ai` | read by the pipeline view `ai_verdict` (spec 12) |
| 5 synced tables `<catalog>.ampera_gold_lb.*` (SNAPSHOT) and their pipelines | `scripts/create_synced_tables.sh` (from `run_first_refresh.sh`) | `var.sync_pipeline_*`; metadata in `<catalog>.default` |
| Postgres grants for the app service principal | `scripts/deploy_and_refresh.sh` | — |

### Depended on (must already exist)

| Dependency | Config | Used by |
|---|---|---|
| Workspace with UC, serverless, Lakebase Autoscaling, Apps, Genie | `workspace.host` in `targets/<target>.yml` | everything |
| SQL warehouse | `var.warehouse_id` | Genie |
| Users group | `permissions` in `targets/<target>.yml` | app `CAN_USE`, Genie `CAN_RUN`, UC `SELECT` on gold |
| Public sources: ONS open data (S3), ANEEL CKAN, INMET portal, Open-Meteo archive API | `scripts/land_raw_data.sh` / `scripts/fetch_open_meteo.py` | raw landing |
| CCEE PLD CSVs (browser download) | printed by `scripts/land_raw_data.sh` | `ampera_bronze.ccee_pld_horario` |
| OpenFreeMap tiles | `app/frontend` (no key) | loaded by the viewer's browser |

### Data objects (all created by the pipeline)

| Layer | Tables | Role |
|---|---|---|
| **bronze** (streaming tables, Auto Loader) | `ons_generation`, `ons_conjunto_member`, `ons_member_generation_wind` / `_solar`, `siga_plants`, `ccee_pld_horario`, `open_meteo_weather`, `inmet_weather` | Raw files as ingested, plus `_source`, `_ingested_at`, `_source_file` |
| **silver** — reconciliation | `ons_plant`, `siga_plant`, `plant_match`, `conjunto_member` | One row per ONS series → `plant_id`, `match_method`, `confidence` |
| **silver** — facts | `generation` (as ONS publishes), `generation_plant` (plant grain: complexes split into measured / estimated members), `dim_plant` | **Never sum `generation` with `generation_plant`** |
| **silver** — enrichment | `price_pld_hourly`, `weather_cell_hourly` (Open-Meteo), `weather_plant_measured` (ONS), `weather_inmet_hourly`, `plant_inmet_station` (≤ 50 km) | Joined by hour + submarket / location |
| **silver** — checks | `plant_match_check`, `generation_plant_key_check`, `generation_balance` | Expectations (§4.4) |
| **gold** (materialized views) | `fact_generation_hourly` (plant × hour), `generation_daily` (plant × day), `plant_location` (plant), `reconciliation_monthly` (grain × month × method) | Read by Genie; the last three are synced to Lakebase |
| **gold_lb** (synced, Postgres schema `ampera_gold_lb`) | `generation_daily`, `plant_location`, `reconciliation_monthly` | Read by the app |

## 3. How it connects

```
 ONS S3 · ANEEL CKAN · INMET ──(1)──▶ Volume <catalog>.ampera_bronze.raw/<source>/
 CCEE (browser) · Open-Meteo API ─┘                │
                                                   (2) Auto Loader
                                                   ▼
            ┌──────────────── Pipeline ampera_medallion ────────────────┐
            │ bronze ──(3)──▶ silver (reconcile, enrich, check) ──(4)──▶ gold │
            └────────────────────────────────────────────────────────────────┘
                 ▲ (5) plant_match_override                │ (6) SNAPSHOT sync
                                                           ▼
   Job ampera_refresh (7) ──▶ medallion, then 3 sync pipelines ──▶ Lakebase gold_lb
                                                           │ (8) Postgres + OAuth token
   Browser ◀──(10)── App ampera-app (FastAPI + SPA) ◀┘
      └──(11) OpenFreeMap tiles
   User ──(12)──▶ Genie space ──(13) SQL on warehouse──▶ ampera_gold.*
```

1. **Landing.** `scripts/land_raw_data.sh` (ONS, SIGA, INMET), a browser download (CCEE) and
   `scripts/fetch_open_meteo.py` (Open-Meteo) put files under `/Volumes/<catalog>/ampera_bronze/raw/`.
2. **Ingest.** Each bronze streaming table reads its folder with `read_files`, which picks up only
   new files. The path comes from the pipeline `configuration.catalog`.
3. **Silver.** Reconciliation follows the ladder in §1 (`reco_sql.py`, the Spark-expression mirror
   of the tested `reco_lib.py`). Complexes are split into members using ONS measured data, with a
   capacity-weighted estimate as the fallback. Price and weather are joined in.
4. **Gold.** Materialized views read the plant-grain fact plus enrichment. They recompute fully on
   each run.
5. **Overrides.** People insert rows into `ampera_silver.plant_match_override`. The next run applies them,
   and the newest `updated_at` per `ons_id` wins.
6. **Sync.** Three SNAPSHOT synced tables copy gold into Lakebase Postgres schema `ampera_gold_lb`.
7. **Orchestration.** The job runs the medallion, then the three sync pipelines.
8. **App → Lakebase.** The `postgres` app resource injects `PGHOST`, `PGUSER` and `PGDATABASE`.
   The app mints a 1-hour OAuth database token as its service principal
   (`generate_database_credential` on `LAKEBASE_ENDPOINT`) and reads with `SELECT` grants on
   `ampera_gold_lb`. It never queries the lakehouse.
9. **Cold start.** After 20 min idle the Lakebase compute suspends. The API drops dead
   connections, retries, then returns 503 "waking", and the UI retries on its own.
10. **Users → app.** Workspace SSO. Access is the app `CAN_USE` permission.
11. **Map tiles.** Fetched by the viewer's browser from OpenFreeMap; nothing goes through the app.
12. **Users → Genie.** Access is `CAN_RUN` on the space.
13. **Genie → data.** SQL runs on the warehouse **as the asking user**, so users need UC
    `USE CATALOG`, `USE SCHEMA` and `SELECT` on `<catalog>.ampera_gold`, plus `CAN_USE` on the warehouse.

**Identities:** the pipeline and job run as the deploying user (add `run_as` in the target for a
service principal). The app runs as its own service principal. Genie runs as the end user.

## 4. How to use it

1. **Configure and deploy:** the numbered scripts in README "Reproduce".
2. **Refresh:** land new raw files (`scripts/land_raw_data.sh`), then
   `databricks bundle run ampera_refresh`. Or unpause the job's schedule once
   landing is automated.
3. **Fix a match:** insert into `ampera_silver.plant_match_override`
   `(ons_id, plant_id, note, updated_at = current_timestamp())`, then refresh.
4. **Observe:** pipeline expectations, warn vs fail:

| Rule | Dataset | On violation |
|---|---|---|
| `plant_id` not null | `plant_match`, `generation`, `generation_plant` | fail |
| one row per (plant_id, ons_key, hour) | `generation_plant_key_check` | fail |
| newest override applied; one row per series | `plant_match_check` | fail |
| ai_decide rows: accepted verdict, same plant, CEG doesn't link | `plant_match_ai_check` | fail |
| monthly plant total within ±2% of published | `generation_balance` | warn |
| MWh ≥ 0, PLD in range, modeled weather present | `generation*`, `price_pld_hourly`, `weather_cell_hourly` | warn |

   Reconciliation quality over time: `ampera_gold.reconciliation_monthly`, also the app's
   "Reconciliação" page. Plant-level unmatched should stay well under 5% of MWh.
5. **Checks:** `python3 tests/test_reconciliation.py` (matching logic),
   `tests/test_genie_space.py` (Genie payload; `GENIE_LIVE=1` runs every curated SQL),
   `tests/test_app_api.py` (API helpers; with `PG*` env set, checks that totals tie).

## 5. Go-live and maintenance essentials

- **External dependencies:** ONS, ANEEL and INMET portals (formats change; spec 01 lists the quirks
  handled). CCEE is a manual download. **Open-Meteo's free tier is non-commercial**: use a paid plan
  or ERA5 from Copernicus in production.
- **Grants:** UC catalog/schema/`SELECT` for Genie users; Postgres `USAGE` and `SELECT` on `ampera_gold_lb`
  for the app service principal. Rerun the Postgres grant if you drop and recreate a synced table.
- **Cadence:** the job is paused by default. Unpause it only after raw landing is automated.
- **Caveats:** synced tables are read-only in Postgres. Before a manual `start-update`, stop the
  pipeline (failed-update retries can race a deploy). Python UDFs that import local modules don't
  run on serverless; keep matching logic in `reco_sql.py`.
- **Deeper docs:** `specs/00-overview.md` (decision log), `specs/01`–`15` (one per component),
  `SUCCESS_CRITERIA.md`, `DESIGN.md` / `PRODUCT.md` / `.impeccable/` (frontend design system).
