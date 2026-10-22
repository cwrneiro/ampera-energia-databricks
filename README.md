# Ampera — Databricks Demo

A full-stack Databricks demonstration for **Ampera Energia Analytics** (a fictional Brazilian energy-data firm):
reconcile power-plant generation from two open Brazilian sources that don't join directly, then
serve it through an app and a Genie Agent.

**The story:** Lakeflow Declarative Pipeline medallion → reliable plant reconciliation (one
`plant_id` per ONS series, CEG or surrogate) → price and weather enrichment → autoscaling Lakebase
via synced tables → Databricks App (FastAPI + React, PT-BR, map) → Genie Agent.

**Start here:** `ARCHITECTURE.md` (what it builds and how it connects) → `SETUP.md` (deploy it in
your workspace; `AGENTS.md` for coding agents, `/setup` in Claude Code).

## Status (2026-10-05)

| Unit | Spec | State |
|---|---|---|
| Bronze ingestion | 01 | ✓ live |
| Reconciliation (silver) | 02 | ✓ live — plant-level unmatched 0.59% of MWh |
| Complexes → member plants | 09 | ✓ live — 96.9% of complex MWh measured, 2.7% estimated |
| Gold marts + price + weather | 03 | ✓ live — price + weather on all 24 months |
| Pipeline + refresh job | 04 | ✓ live |
| Lakebase synced tables | 05 | ✓ live — gold changes reach Lakebase via the refresh job |
| App | 06 | ✓ deployed — `ampera-app`, 4 PT-BR sheets over Lakebase, Impeccable review: ship |
| Genie Agent | 07 | ✓ deployed — "Ampera · Geração Elétrica", 4 gold tables, 32 benchmarks |

`STATE.md` has the live handoff.

## Data sources

- **ONS** — hourly generation per plant ([geracao-usina-2](https://dados.ons.org.br/dataset/geracao-usina-2)),
  complex → plant mapping (`usina_conjunto`), per-plant measured generation and weather for wind/solar
  complexes (`restricao_coff_eolica_detail`, `restricao_coff_fotovoltaica_detail`)
- **ANEEL SIGA** — plant registry ([siga](https://dadosabertos.aneel.gov.br/dataset/siga-sistema-de-informacoes-de-geracao-da-aneel))
- **CCEE** — hourly PLD (`pld_horario`; browser download, CCEE blocks scripts)
- **Weather** — Open-Meteo archive (ERA5, free non-commercial tier) and INMET station archives

## Repo layout

- `databricks.yml`, `resources/` — Asset Bundle: pipeline `ampera_medallion`, job `ampera_refresh`,
  app `ampera_app`, Genie space `ampera_genie` (body in `resources/genie/*.geniespace.json`)
- `app/` — Databricks App: `app.py` (FastAPI, read-only over Lakebase `ampera_gold_lb`), `app.yaml`,
  `frontend/` (React + Vite + Recharts + MapLibre; built `dist/` is gitignored, synced by the bundle)
- `src/transformations/` — one dataset per file (`bronze_*`, `silver_*`, `gold_*`); `reco_lib.py`
  (tested matching reference) and `reco_sql.py` (its Spark-expression mirror)
- `scripts/fetch_open_meteo.py` — resumable, rate-limited weather fetch
- `tests/test_reconciliation.py` — runnable matching check; `tests/test_app_api.py` — app API check
  (totals tie; live part runs when the `PG*` env vars from `app/app.py` are set);
  `tests/test_genie_space.py` — Genie payload shape + curated SQL (`GENIE_LIVE=1`)
- `specs/` — `00-overview.md` (goal, scope, **decision log**), `01`–`09` one spec per unit, `08` branding
- `SUCCESS_CRITERIA.md`, `CLAUDE.md` (working contract), `STATE.md` (handoff), `DEMO_SCRIPT.md` (talk track)
- `PRODUCT.md` (product record) and `DESIGN.md` (as-built design system) for frontend work;
  `.impeccable/` holds the app's direction contract and design sidecar
- `data/` — local raw downloads (gitignored)

## Run it

```bash
P=<profile>
databricks bundle deploy -t dev --profile $P              # pipeline + job
databricks bundle run ampera_refresh -t dev --profile $P   # medallion, then Lakebase syncs
python3 tests/test_reconciliation.py                      # matching logic check
python3 tests/test_app_api.py                             # app API check
GENIE_LIVE=1 python3 tests/test_genie_space.py            # Genie payload + every curated SQL
(cd app/frontend && npm ci && npm run build)              # app frontend → dist/
databricks bundle deploy -t dev --profile $P && databricks bundle run ampera_app -t dev --profile $P
```

App: `ampera-app` in the workspace (workspace login). Map tiles
come from OpenFreeMap (free, no key) and load in the viewer's browser.

**Workspace:** Databricks CLI profile `<profile>`. Catalog `ampera_catalog`
(`ampera_bronze` / `ampera_silver` / `ampera_gold` / `ampera_gold_lb`); Lakebase project `ampera-demo`.

**Repo:** https://github.com/cwrneiro/ampera-energia-databricks.
