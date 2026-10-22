# AGENTS.md — instructions for any coding agent

This repo deploys the Ampera reconciliation demo (ONS + ANEEL SIGA → medallion → Lakebase →
app + Genie) as one Databricks Asset Bundle. Read `ARCHITECTURE.md` for what it builds and
`SETUP.md` to stand it up.

## First interaction: is this configured?

If `targets/` holds no `*.yml` file (only `customer.yml.example`), this checkout isn't configured
for the user's workspace yet. Say **one line** — "Not configured for your workspace yet — I can walk
you through SETUP.md." — then do what the user asked. Don't block on it, and don't run setup
unprompted.

## Setting up: walk the user through `SETUP.md`

`SETUP.md` is the source of truth. Go section by section:

- **Discover, then ask.** List what exists (`databricks auth profiles`, `catalogs list`,
  `warehouses list`, `postgres list-projects`, `groups list`) and offer those values. Don't make
  the user type what a command can find.
- **Validate cheap things.** Run the verify command for each value and report ✅ found / ⚠️ missing /
  ⏭️ skipped. A missing value is a warning, not a blocker. Never report a check you didn't run.
- **Additive only.** Write `targets/<target>.yml` and `targets/<target>.geniespace.json`. Never
  edit other targets or the variable defaults in `databricks.yml`. The one sanctioned edit is
  `LAKEBASE_ENDPOINT` in `app/app.yaml`, and only for a non-default Lakebase project (SETUP §6.4).
- **Confirm before anything outward-facing.** Show the filled target file before you write it.
  Ask again before each `bundle deploy`, `bundle run`, Lakebase create, synced-table create, GRANT
  or upload.
- **Never pick a CLI profile yourself.** Always pass `--profile`.

## Non-negotiable conventions

- **Reconciliation invariants:** every ONS series gets exactly one `plant_id`. Overrides in
  `ampera_silver.plant_match_override` win, and the newest `updated_at` per `ons_id` wins. Never sum
  `ampera_silver.generation` (as published) with `ampera_silver.generation_plant` (plant grain). Keep
  `src/transformations/reco_lib.py` (tested reference) and `reco_sql.py` (the Spark expressions
  the pipeline runs) in sync. Serverless pipelines can't use Python UDFs that import local modules.
- **Catalog:** transforms use `schema.table` names. They resolve against the pipeline catalog
  `${var.catalog}`, and volume paths use `${catalog}`. Never hard-code a catalog name.
- **Genie JSON** (`resources/genie/*.geniespace.json`): keep id-keyed arrays sorted by id and
  `column_configs` sorted by name. `python3 tests/test_genie_space.py` checks this.
- **CCEE** blocks non-browser clients. Never script around it; PLD files are a manual download.
- **Language:** app UI text is PT-BR. Code, comments, docs and commit messages are English.
- **Checks:** every non-trivial transform change leaves a runnable check. Run `python3
  tests/test_reconciliation.py` after any matching change.
- **Never bypass git hooks** (`--no-verify`). If a hook blocks, fix the cause.
