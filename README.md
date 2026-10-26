# Ampera Energia Analytics — reconciled generation & curtailment losses for Brazilian renewables

An end-to-end Databricks prototype for **Energy & Utilities**. It is built for a fictional
Brazilian energy-data firm, Ampera Energia Analytics, and uses **public data only** (ONS, ANEEL
SIGA, CCEE, Open-Meteo, INMET).

**The customer problem.** Ampera sells analytics to Brazilian generators, traders and sector
associations, and has two problems that block every downstream product:

1. **The data doesn't join.** ONS (the grid operator) publishes hourly generation. ANEEL's SIGA is
   the registry of record, with capacity, location and the plant's CEG code. The two only partly
   join. CEG formats differ, ONS mixes plants with wind/solar *complexes* and state totals, and
   some plants have no usable CEG at all. Without one plant ID, generation can't be tied to a plant.
2. **Curtailment is invisible in money terms.** ONS increasingly orders wind and solar plants to
   cut output (*constrained-off*), and in 2025–26 this happened at scale in the Northeast. Owners
   and traders need **how much energy and how many R$ were lost, per plant**, and an estimate they
   can trust.

**What the build delivers.**
- **One plant ID.** Every ONS series resolves to exactly one `plant_id`. Unmatched energy is
  **0.03%** of plant-level MWh; the target was under 5%.
- **A curtailment model.** It estimates each wind/solar plant-hour's unconstrained output, flags
  curtailment, and values the lost energy at the hourly PLD price: **65.8 TWh, R$ 8.4 bi** over
  24 months.
- **Delivery.** Results are served through Lakebase to a PT-BR Databricks App, which includes a
  Genie chat.

## The journey, stage by stage — code and execution evidence

All evidence is plain text committed in [`evidence/`](evidence/). It covers executed notebooks
with their outputs, run logs, query results and API transcripts. Captured on 2026-10-22 from
workspace `<profile>`.

| Stage | What runs | Code | Execution evidence |
|---|---|---|---|
| **Lakeflow — ingest** | Declarative Pipeline `ampera_medallion`. Auto Loader streaming tables ingest 8 public sources (ONS generation, complex members, constrained-off detail; ANEEL SIGA; CCEE PLD; Open-Meteo; INMET). Bronze → silver → gold, with 17 data-quality expectations. Orchestrated by Lakeflow Job `ampera_refresh` | [`src/transformations/`](src/transformations/), [`resources/ampera_medallion.pipeline.yml`](resources/ampera_medallion.pipeline.yml), [`resources/ampera_refresh.job.yml`](resources/ampera_refresh.job.yml) | [`01_pipeline_run.txt`](evidence/01_pipeline_run.txt) (expectations pass/fail per dataset, from `event_log`), [`02_job_runs.txt`](evidence/02_job_runs.txt) (every task's result) |
| **Unity Catalog — govern** | Schemas `ampera_bronze/silver/gold/gold_lb` with a comment on every table. Group `ampera_analysts` reads gold only. Tags (`ampera_layer`, `ampera_source`, `ampera_ai`, governed `class.geo_coordinates` on coordinates). Model registered in UC. Lineage | [`notebooks/governance.py`](notebooks/governance.py) (last job task) | [`notebooks/governance.ipynb`](evidence/notebooks/governance.ipynb) (grants, tags, full lineage bronze → ML → Lakebase from `system.access.table_lineage`), [`03_medallion_tables.txt`](evidence/03_medallion_tables.txt) (every table, row count, comment) |
| **Lakebase — operational serving** | Autoscaling Lakebase Postgres `ampera-demo` (0.5–4 CU, scale-to-zero). 5 synced tables (gold → Postgres) refreshed by the job. The app reads only Lakebase | [`scripts/create_synced_tables.sh`](scripts/create_synced_tables.sh), [`app/app.py`](app/app.py) | [`06_lakebase_serving.txt`](evidence/06_lakebase_serving.txt) (sync state, last sync), [`07_app_api.txt`](evidence/07_app_api.txt) (API answers served from Postgres) |
| **ML — curtailment model** | scikit-learn `HistGradientBoostingRegressor` per technology. It predicts the unconstrained capacity factor from weather (Open-Meteo, plus ONS at-plant measurements where they exist), hour, month and plant history, and is trained only on hours ONS did not flag. Tracked in MLflow, registered in UC as `curtailment_expected_cf@champion`, and batch-scored every refresh | [`notebooks/train_curtailment.py`](notebooks/train_curtailment.py), [`notebooks/score_curtailment.py`](notebooks/score_curtailment.py), [`gold_curtailment_features_hourly.sql`](src/transformations/gold_curtailment_features_hourly.sql) | [`notebooks/train_curtailment.ipynb`](evidence/notebooks/train_curtailment.ipynb) (data, test error vs ONS, Y tuning table, registration), [`notebooks/score_curtailment.ipynb`](evidence/notebooks/score_curtailment.ipynb), [`04_ml_curtailment.txt`](evidence/04_ml_curtailment.txt) |
| **GenAI — `ai_decide` reconciliation** | `ai_decide` (calibrated choice over 3 SIGA candidates or *nenhum*) places ONS plants the rules can't. It is asked once per plant, candidate set and prompt, and the verdict is kept, so refreshes are deterministic and don't re-bill. It auto-applies at confidence ≥ 0.9; anything less goes to a human review queue in the app. A blind evaluation measures how far to trust it | [`reco_ai.py`](src/transformations/reco_ai.py), [`notebooks/adjudicate_ai.py`](notebooks/adjudicate_ai.py), [`silver_ai_verdict.py`](src/transformations/silver_ai_verdict.py), [`silver_plant_match.py`](src/transformations/silver_plant_match.py), [`notebooks/eval_ai_decide.py`](notebooks/eval_ai_decide.py) | [`notebooks/adjudicate_ai.ipynb`](evidence/notebooks/adjudicate_ai.ipynb) (verdicts asked / on file), [`notebooks/eval_ai_decide.ipynb`](evidence/notebooks/eval_ai_decide.ipynb) (accuracy, calibration, confusion), [`05_genai_ai_decide.txt`](evidence/05_genai_ai_decide.txt) (every production verdict) |
| **Genie Agent — natural language** | Genie space over the 5 gold marts. PT-BR instructions, example SQL, join specs and 38 benchmark questions. Deployed by the bundle | [`resources/genie/ampera.geniespace.json`](resources/genie/ampera.geniespace.json) | [`08_genie_conversations.json`](evidence/08_genie_conversations.json) (5 questions → answer text, generated SQL, rows), [`09_tests.txt`](evidence/09_tests.txt) (every curated SQL runs live) |
| **Databricks App — to the business** | FastAPI + React (PT-BR) with 5 sheets: Overview, Reconciliation (incl. the `ai_decide` review queue), Curtailment, Map, Plant (actual vs expected). A slide-out **Genie chat** runs *on behalf of the signed-in user* (UC grants apply per user) and renders interactive Recharts plots | [`app/`](app/), [`resources/ampera_app.app.yml`](resources/ampera_app.app.yml) | [`07_app_api.txt`](evidence/07_app_api.txt), [`08_genie_conversations.json`](evidence/08_genie_conversations.json) (asked through the deployed app's `/api/genie`) |

Everything is one Declarative Automation Bundle ([`databricks.yml`](databricks.yml)). One job run
moves data end to end:
**raw files → bronze → silver (incl. `ai_decide`) → gold → ML scoring → Lakebase → app / Genie.**

## Results (from the evidence files)

- **Reconciliation.** 967 ONS series. CEG matches cover 910 TWh; the rest are complexes resolved
  into member plants, state aggregates, 2 fuzzy matches and **2 `ai_decide` matches carrying 5.1
  TWh**, leaving **0.27 TWh unmatched (0.03%)**. All 24 months of the plant-grain total stay within
  ±2% of the published total. Total: **1,404.19 TWh**, the same in SQL, the app and Genie.
- **`ai_decide`, blind test** (200 CEG-matched plants, CEG registry number hidden): 91% accuracy.
  At the 0.9 cutoff it auto-applies 93 of 200 with **100% precision**, and calibration holds
  (0.8–0.9 bucket: 30/30). The first production run answered *nenhum* for all 33 unresolved plants.
  It became useful once the prompt carried evidence per candidate (name similarity, same CEG
  registry number, same plant type); see [spec 12](specs/12-genai-reconciliation.md).
- **Curtailment model, test months** (Apr–Sep 2026). Capacity-factor MAE is **0.088 wind / 0.013
  solar**, better than ONS's own estimate (0.098 / 0.015). The flag ratio Y is tuned for the best
  recall at precision ≥ 0.8 against ONS's constrained-off flags, so the R$ figure is a conservative
  "at least". Over 24 months: wind **41.6 TWh / R$ 5.7 bi** lost (16.5% of expected), solar
  **24.2 TWh / R$ 2.6 bi** (28.2%).

## Reproduce

Needs the Databricks CLI ≥ 0.294, `jq`, Python 3.11+ (`databricks-sdk`, `psycopg` for the app test),
Node 20+, `curl` and `unzip`; a workspace with Unity Catalog, serverless compute, Lakebase
Autoscaling, Databricks Apps and Genie; and an existing catalog you can create schemas in. Every
script takes the CLI profile as its last argument (default `$DATABRICKS_CONFIG_PROFILE`).

1. `cp targets/dev.yml.example targets/dev.yml` and fill the workspace host, catalog and warehouse.
2. `scripts/bootstrap_workspace.sh <profile>`: Unity Catalog schemas, the raw volume, the empty
   override and ai_decide verdict tables, the Lakebase project and the `ampera_analysts` group.
3. `scripts/land_raw_data.sh <profile>`: ONS, ANEEL SIGA, INMET and an Open-Meteo seed into the volume.
   It ends by printing the one manual step: the CCEE PLD download (CCEE blocks scripted clients).
4. `scripts/run_first_refresh.sh <profile>`: first deploy and medallion run, the refresh job with a
   model retrain, then the Lakebase synced tables. Paste the printed `sync_pipeline_*` ids into
   `targets/dev.yml`.
5. `scripts/deploy_and_refresh.sh false <profile>`: deploy, start the app, grant its service
   principal read on `ampera_gold_lb`, run the refresh job.
6. Full weather history (resumable; about 3 daily runs on the free tier), then refresh:
   ```bash
   databricks experimental aitools tools query -w <warehouse-id> -p <profile> -o json \
     "SELECT round(lat*4)/4 AS lat, round(lon*4)/4 AS lon, count(*) plants FROM <catalog>.ampera_silver.dim_plant
      WHERE lat IS NOT NULL GROUP BY 1,2" > data/raw/open_meteo/cells.json
   python3 scripts/fetch_open_meteo.py
   databricks fs cp -r --overwrite data/raw/open_meteo/raw dbfs:/Volumes/<catalog>/ampera_bronze/raw/open_meteo -p <profile>
   databricks bundle run ampera_refresh -p <profile>
   ```
7. Tests: `python3 tests/test_reconciliation.py`, `python3 tests/test_curtailment.py`,
   `python3 tests/test_genie_space.py`, `DATABRICKS_CONFIG_PROFILE=<profile> python3 tests/test_app_api.py`.

The evidence is regenerated with `python3 scripts/collect_evidence.py` and
`python3 scripts/export_run_notebooks.py <job_run_id>`. Raw data is not committed. Architecture:
[`ARCHITECTURE.md`](ARCHITECTURE.md). Design decisions: [`specs/00-overview.md`](specs/00-overview.md)
(decision log) and `specs/01`–`15`.

## Data sources (all public)

- **ONS** dados abertos: hourly generation per plant (`geracao-usina-2`), complex membership
  (`usina_conjunto`), wind/solar constrained-off detail per plant (`restricao_coff_*_detail`).
- **ANEEL SIGA**: generation registry (CEG, capacity, coordinates).
- **CCEE**: hourly PLD (spot price) per submarket.
- **Open-Meteo** (ERA5 reanalysis; free tier, non-commercial) and **INMET** station archives.

Ampera Energia Analytics is fictional. No customer data is used anywhere in this repository.
