# SETUP — deploy Ampera in your Databricks workspace

A numbered procedure that takes an empty Databricks workspace to the running medallion, Lakebase,
app and Genie space. **Three ways to run it, same result:**

1. **By hand** — follow the steps below in a terminal.
2. **Any coding agent** (Cursor, Copilot, Windsurf, Aider, …) — ask it to "walk me through
   SETUP.md"; `AGENTS.md` tells it the rules.
3. **Claude Code** — run `/setup`: an interactive interview over these same steps.

Everything is **additive**: you create a new bundle target `targets/<target>.yml` next to any
existing target, and no existing configuration changes. The one possible exception is §6.4: a
single line in `app/app.yaml`, which you only edit if you choose a non-default Lakebase project id. `ARCHITECTURE.md` explains what each step
creates and how the pieces connect.

**Prerequisites:** Databricks CLI ≥ 0.294, `jq`, Python 3.11+, Node 20+ (frontend build), `curl`,
`unzip`. Workspace with Unity Catalog, serverless compute (pipelines + SQL), Lakebase Autoscaling,
Databricks Apps and Genie enabled. You need `CREATE CATALOG` (or an existing catalog you own).

Set these once per shell (examples):

```bash
export P=<profile>            # CLI profile:   databricks auth profiles
export T=<target>             # bundle target, e.g. prod
export CAT=<catalog>          # UC catalog, e.g. ampera_catalog
export LB=<lakebase-project>  # Lakebase project id; default ampera-demo (no app.yaml edit)
```

## 1. Collect values → create your target file

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile $P   # if new
cp targets/customer.yml.example targets/$T.yml
sed -i.bak "s/^  customer:/  $T:/" targets/$T.yml && rm targets/$T.yml.bak
```

Fill every `<…>` in `targets/$T.yml`. Each field has a discovery command next to it. Leave the
three `sync_pipeline_*` values as they are until §6. Checks:

| Value | Verify |
|---|---|
| host / profile | `databricks current-user me --profile $P` |
| warehouse_id | `databricks warehouses get <id> --profile $P` |
| users group | `databricks groups list --profile $P -o json \| jq -r '.[].displayName'` |

## 2. Unity Catalog objects

Run in a SQL editor, or with `databricks experimental aitools tools query "<sql>" --profile $P`.
Replace `<catalog>`:

```sql
CREATE CATALOG IF NOT EXISTS <catalog>;
CREATE SCHEMA IF NOT EXISTS <catalog>.bronze;
CREATE SCHEMA IF NOT EXISTS <catalog>.silver;
CREATE SCHEMA IF NOT EXISTS <catalog>.gold;
CREATE SCHEMA IF NOT EXISTS <catalog>.gold_lb;     -- synced tables land here
CREATE VOLUME IF NOT EXISTS <catalog>.bronze.raw;  -- raw source files
-- Manual reconciliation fixes (spec 02); the pipeline requires it, empty is fine.
CREATE TABLE IF NOT EXISTS <catalog>.silver.plant_match_override
  (ons_id STRING, plant_id STRING, note STRING, updated_at TIMESTAMP);
```

## 3. Genie payload for your catalog

The Genie JSON spells out the catalog name everywhere. Make a copy for your target:

```bash
sed "s/ampera_catalog\./$CAT./g" resources/genie/ampera.geniespace.json \
  > targets/$T.geniespace.json
```

Then set `file_path: $T.geniespace.json` in `targets/$T.yml`, using the actual target name. Rerun
this step whenever the source JSON changes.

## 4. Lakebase project

```bash
databricks postgres create-project $LB --json '{"spec": {"display_name": "Ampera", "pg_version": 17}}' --profile $P
databricks postgres update-endpoint projects/$LB/branches/production/endpoints/primary \
  "spec.autoscaling_limit_min_cu,spec.autoscaling_limit_max_cu,spec.suspend_timeout_duration" \
  --json '{"spec": {"autoscaling_limit_min_cu": 0.5, "autoscaling_limit_max_cu": 4, "suspend_timeout_duration": "1200s"}}' \
  --profile $P
```

These are the demo's sizes: 0.5–4 CU, suspend after 20 min idle. Increase `suspend_timeout_duration`
or disable suspension if the app must never pause on its first request.

## 5. Land the raw data in the volume

Window: 24 months, **2024-10 … 2026-09** (decision #14). To move it, change `MONTHS` below and
`FIRST`/`LAST` in `scripts/fetch_open_meteo.py`. Every source must have at least one file before
the first pipeline run: a streaming table can't infer a schema from an empty folder.

```bash
V=dbfs:/Volumes/$CAT/bronze/raw
S3=https://ons-aws-prod-opendata.s3.amazonaws.com/dataset
MONTHS="print(' '.join(f'{y}_{m:02d}' for y in range(2024, 2027) for m in range(1, 13) if (2024, 10) <= (y, m) <= (2026, 9)))"
mkdir -p data/raw/land && cd data/raw/land

# ONS hourly generation, per-member wind/solar detail (monthly parquet), complex membership
for ym in $(python3 -c "$MONTHS"); do
  curl -fsSO $S3/geracao_usina_2_ho/GERACAO_USINA-2_$ym.parquet
  curl -fsSO $S3/restricao_coff_eolica_detail_tm/RESTRICAO_COFF_EOLICA_DETAIL_$ym.parquet
  curl -fsSO $S3/restricao_coff_fotovoltaica_detail_tm/RESTRICAO_COFF_FOTOVOLTAICA_DETAIL_$ym.parquet
done
curl -fsSO $S3/usina_conjunto/RELACIONAMENTO_USINA_CONJUNTO.parquet
for f in GERACAO_USINA-2_*;                  do databricks fs cp $f $V/ons/              --profile $P; done
for f in RESTRICAO_COFF_EOLICA_DETAIL_*;     do databricks fs cp $f $V/ons_member_wind/  --profile $P; done
for f in RESTRICAO_COFF_FOTOVOLTAICA_DETAIL_*; do databricks fs cp $f $V/ons_member_solar/ --profile $P; done
databricks fs cp RELACIONAMENTO_USINA_CONJUNTO.parquet $V/ons_conjunto_member/ --profile $P

# ANEEL SIGA registry (URL from the CKAN API, so it survives resource-id changes)
curl -fsSL -o siga-empreendimentos-geracao.csv "$(curl -fsS 'https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=siga-sistema-de-informacoes-de-geracao-da-aneel' \
  | jq -r '.result.resources[].url | select(endswith("/siga-empreendimentos-geracao.csv"))')"
databricks fs cp siga-empreendimentos-geracao.csv $V/siga/ --profile $P

# INMET station archives (yearly zip; needs a browser user agent)
for y in 2024 2025 2026; do
  curl -fsSL -A 'Mozilla/5.0' -o inmet_$y.zip https://portal.inmet.gov.br/uploads/dadoshistoricos/$y.zip
  mkdir -p inmet/$y && unzip -jqo inmet_$y.zip -d inmet/$y
done
databricks fs cp -r inmet $V/inmet --profile $P
```

- **CCEE PLD (manual):** CCEE blocks scripted clients, so don't automate it. In a browser, download
  "PLD horário" for each year from the CCEE open-data portal (`pld_horario_<year>.csv`), then
  `databricks fs cp pld_horario_<year>.csv $V/ccee_pld/ --profile $P`.
- **Open-Meteo (bootstrap):** the full cell list comes from `silver.dim_plant`, which only exists
  after the first run. Start with one cell, which is enough for schema inference:
  ```bash
  cd ../../.. && mkdir -p data/raw/open_meteo
  echo '[{"lat": "-25.5", "lon": "-54.5", "plants": "1"}]' > data/raw/open_meteo/cells.json
  python3 scripts/fetch_open_meteo.py --budget 200
  databricks fs cp -r data/raw/open_meteo/raw $V/open_meteo --profile $P
  ```
  ⚠️ The free Open-Meteo API is for **non-commercial use only**. For production, use a paid
  Open-Meteo plan or ERA5 from Copernicus (decision #18).

## 6. Deploy, run, sync, serve

1. **Deploy the bundle and run the medallion.**
   ```bash
   databricks bundle validate -t $T --profile $P
   databricks bundle deploy -t $T --profile $P
   databricks bundle run ampera_medallion -t $T --profile $P
   ```
   ⚠️ The first deploy runs before the gold tables and the sync pipelines exist. If it fails on the
   Genie space or the refresh job, the pipeline is still created. Run the medallion, finish
   steps 2–3, and deploy again.
2. **Create the three synced tables** (SNAPSHOT, read by the app):
   ```bash
   sync() {  # <table> <primary key as a JSON array>
     databricks postgres create-synced-table $CAT.gold_lb.$1 --profile $P --json "{\"spec\": {
       \"source_table_full_name\": \"$CAT.gold.$1\", \"primary_key_columns\": $2,
       \"scheduling_policy\": \"SNAPSHOT\", \"branch\": \"projects/$LB/branches/production\",
       \"postgres_database\": \"databricks_postgres\", \"create_database_objects_if_missing\": true,
       \"new_pipeline_spec\": {\"storage_catalog\": \"$CAT\", \"storage_schema\": \"default\"}}}"
     databricks postgres get-synced-table synced_tables/$CAT.gold_lb.$1 --profile $P -o json | jq -r "\"$1: \" + .status.pipeline_id"
   }
   sync generation_daily       '["dia", "plant_id"]'
   sync plant_location         '["plant_id"]'
   sync reconciliation_monthly '["grao", "mes", "match_method"]'
   ```
3. **Paste the three pipeline ids** into `sync_pipeline_*` in `targets/$T.yml`.
4. **Point the app at your Lakebase endpoint.** Skip this if your project id is `ampera-demo`.
   Otherwise, in `app/app.yaml`, set `LAKEBASE_ENDPOINT` to
   `projects/<lakebase-project>/branches/production/endpoints/primary`. App runtime env can't read
   bundle variables, so this one line is a file edit.
5. **Build the frontend, deploy everything, start the app.**
   ```bash
   (cd app/frontend && npm ci && npm run build)
   databricks bundle deploy -t $T --profile $P
   databricks bundle run ampera_app -t $T --profile $P
   ```
6. **Grant the app read access in Postgres.** The role is the app's service principal client id:
   ```bash
   SP=$(databricks apps get ampera-app --profile $P -o json | jq -r .service_principal_client_id)
   databricks psql --project $LB --profile $P -- -d databricks_postgres -c \
     "GRANT USAGE ON SCHEMA gold_lb TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA gold_lb TO \"$SP\";"
   ```
7. **Grant Genie users read access in UC** (SQL), and give the group `CAN_USE` on the warehouse:
   ```sql
   GRANT USE CATALOG ON CATALOG <catalog> TO `<users-group>`;
   GRANT USE SCHEMA, SELECT ON SCHEMA <catalog>.gold TO `<users-group>`;
   ```

## 7. Full weather history (after the first green run)

```bash
databricks experimental aitools tools query "SELECT round(lat*4)/4 AS lat, round(lon*4)/4 AS lon, count(*) plants
  FROM $CAT.silver.dim_plant WHERE lat IS NOT NULL GROUP BY 1,2" --profile $P --output json > data/raw/open_meteo/cells.json
python3 scripts/fetch_open_meteo.py          # resumable; ~3 daily runs on the free tier
databricks fs cp -r data/raw/open_meteo/raw $V/open_meteo --overwrite --profile $P
databricks bundle run ampera_refresh -t $T --profile $P   # medallion, then the Lakebase syncs
```

## 8. Validate & go live

```bash
python3 tests/test_reconciliation.py                                   # matching logic (offline)
python3 tests/test_genie_space.py                                      # Genie payload shape (offline)
DATABRICKS_CONFIG_PROFILE=$P CATALOG=$CAT GENIE_LIVE=1 python3 tests/test_genie_space.py   # every curated SQL
```

The live Genie check also compares the all-history total with the demo's 1,404.19 TWh. That only
holds for the demo window and data vintage, so expect a different number if either changed.

Go-live checklist:

- [ ] Pipeline update green. The reconciliation expectations (`has_plant_id`, `plant_match_check`,
      `generation_plant_key_check`) pass.
- [ ] App opens for a member of the users group. "Visão geral" totals match
      `SELECT sum(mwh) FROM <catalog>.gold.generation_daily`.
- [ ] Genie answers a "geração por CEG" question.
- [ ] Refresh cadence decided. ONS/SIGA/INMET landing is manual today. Automate it (a job running
      §5) before setting `pause_status: UNPAUSED`. CCEE stays a manual drop.
- [ ] Open-Meteo licensing resolved for commercial use (§5).
- [ ] Owners named:

| Component | Owner | Notes |
|---|---|---|
| Medallion pipeline + refresh job | | failure e-mails in `targets/<target>.yml` |
| Reconciliation overrides (`silver.plant_match_override`) | | domain owner; newest row per `ons_id` wins |
| Lakebase project | | scale-to-zero and sizes in §4 |
| App + Genie space | | permissions in `targets/<target>.yml` |
| Raw data landing (§5, CCEE manual) | | |
