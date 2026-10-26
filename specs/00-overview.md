# 00 — Overview

## Real goal

Ampera Energia Analytics (fictional) is a Brazilian energy-sector AI/data firm (curtailment monitoring, price forecasting,
tariff optimization) serving utilities, traders, and sector associations. Their production data
comes mostly from open APIs. Their stated pain: **ONS generation data and ANEEL SIGA registry data
don't join directly** — some plants have no CEG code — so correlating generation to a plant is
unreliable. This demo shows Databricks solving that reconciliation end to end and presenting the
result through an app and a Genie Agent.

**Second pain (2026-10-21):** curtailment — wind and solar output cut by ONS — is invisible in
R$ terms. The build adds an ML model that estimates unconstrained output and values the lost
energy at PLD, a GenAI (`ai_decide`) step for the plants the matching rules can't place, UC
governance, and a Genie chat in the app (specs 11–15).

**Done & successful (one sentence):** On `<profile>`, a Declarative Pipeline builds a clean
medallion that assigns every ONS generation record a reliable unique plant ID (CEG or surrogate),
served through an autoscaling Lakebase to a branded PT-BR app (with a map) and a Genie Agent that
answers "generation by CEG / by conjunto".

**Audience:** Ampera data/engineering team (technical credibility) + decision-makers
(polished app + Genie). Built by a Databricks FE. Both audiences must land.

## Scope

**In:** ONS hourly generation (+ ONS complex-member data) and the SIGA registry; enrichment with
CCEE PLD prices and weather (Open-Meteo, ONS at-plant, INMET); medallion via Lakeflow Declarative
Pipeline; reconciliation to a unique plant ID; Lakebase + synced tables; FastAPI+React app with a
map; Genie Agent. All SIGA generation types. **Out (v1):** streaming ingest; app auth/RBAC/
multi-tenant; price/generation forecasting; history beyond the 24-month window.

## Decision log (all confirmed by the user on 2026-10-01)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Goal / audience | Full-stack story for technical + exec audiences |
| 2 | Workspace | CLI profile `<profile>` |
| 3 | Language | App UI PT-BR; specs/docs/code/commits English |
| 4 | Session continuity | Enforced — CLAUDE.md contract + Stop hook |
| 5 | App stack | FastAPI + React (Impeccable), interactive map |
| 6 | Data scope | All SIGA generation types |
| 7 | Out of scope | Streaming ingest; app auth/RBAC/multi-tenant |
| 8 | Enrichment | Price **and** weather (sources revised by #18, #19) |
| 9 | Map | Point map if SIGA has lat/long, else UF choropleth → **point map** (SIGA coords 100%) |
| 10 | Reconciliation ID | Normalized CEG, else fuzzy name match (UF + fuel, numerals must match) with confidence, else surrogate; manual-override table. Capacity tie-break dropped (ONS has no capacity) — spec 02 |
| 11 | ETL engine | Lakeflow Declarative Pipeline, bronze → silver → gold |
| 12 | Serving | Autoscaling Lakebase fed from gold via synced tables |
| 13 | Catalog | `ampera_catalog` with schemas `ampera_bronze` / `ampera_silver` / `ampera_gold` |
| 14 | Window | Last 24 months of ONS (2024-10 … 2026-09) |
| 15 | Unmatched metric | SUCCESS #1 over plant-level MWh; complexes + state totals are separate categories |
| 16 | Complex members | ONS measured per-member generation; capacity-weighted "estimado" only where no member data — spec 09 |
| 17 | Gold tables | `fact_generation_hourly` (lakehouse only) + `generation_daily`, `plant_location`, `reconciliation_monthly` (Lakebase) — spec 03 |
| 18 | Weather | Open-Meteo (ERA5) base layer for every plant; drill-down: ONS at-plant measurement, else INMET station ≤ 50 km. Open-Meteo free API is non-commercial (accepted for the demo; production = ERA5 via Copernicus) — spec 03 |
| 19 | Price | CCEE PLD horário, browser-downloaded (CCEE blocks automated clients); manual refresh — spec 03 |
| 20 | Lakebase | Project `ampera-demo` (PG 17, autoscale 0.5–4 CU, scale-to-zero after 20 min); SNAPSHOT synced tables in `ampera_catalog.ampera_gold_lb` (Postgres schema `ampera_gold_lb`); refresh job after the pipeline — spec 05 |
| 21 | App shape | 4 pages (Visão geral, Reconciliação, Mapa, Usina); MapLibre GL + OpenFreeMap `positron` tiles; Recharts; `psycopg[binary]`; React/Vite built locally, `dist` shipped by the bundle (2026-10-02) — spec 06 |
| 22 | Genie Agent | Raw gold tables (all 4, no Metric View) + SQL snippets; PT-BR surfaces; ~12 checked chat benchmarks; managed as a bundle `genie_spaces` resource (2026-10-02) — spec 07 |
| 23–26 | Handoff | ~~SETUP.md + AGENTS.md + `/setup`; additive `targets/<target>.yml`; cheap validation (2026-10-09) — spec 10~~ **Removed 2026-10-26**: customer deployment is out of scope; reproduce = numbered scripts in README, one `targets/dev.yml.example` overlay. The parameterized catalog stays. |
| 27 | Purpose | End-to-end demo for fictional **Ampera Energia Analytics** (public data only) |
| 28 | Workspace | `<profile>`; schemas `ampera_*` inside `ampera_catalog` (existing catalog; the bundle never runs CREATE CATALOG) |
| 29 | ML problem | Curtailment detection: expected unconstrained CF from weather; labels = ONS constrained-off flags already in bronze — spec 11 |
| 30 | ML model | HistGBR per technology, train on unflagged hours, 18/6-month split, MLflow + UC `champion`; flag expected ≥ 10% cap & actual < Y×expected, Y tuned by F1 and stored on the version — spec 11 |
| 31 | GenAI | `ai_decide` choice A/B/C/nenhum per unresolved ONS plant; auto-apply at confidence ≥ 0.9 (to revisit after calibration), else review queue — spec 12 |
| 32 | GenAI rationale | None — per-candidate probabilities shown instead — spec 12 |
| 33 | GenAI eval | Blind replay on CEG-matched plants with the CEG hidden; accuracy + calibration — spec 12 |
| 34 | Governance | Group `ampera_analysts` reads gold only; tags layer/domain/source/ai; model in UC; lineage evidence — spec 13 |
| 36 | App | Curtailment sheet, Usina expected-vs-actual, ai_decide queue on Reconciliação — spec 14 |
| 37 | Genie chat | Slide-out panel on every page, on-behalf-of-user, SQL shown, Recharts chart by column-type heuristic — spec 14 |
| 40 | Evidence | Executed notebooks (`.ipynb` with outputs) + text captures from one script; README index — spec 15 |
| 41 | Publish | New public repo `cwrneiro/ampera-energia-databricks`, single sanitized root commit, after the user's go-ahead — spec 15 |

## What the data showed (2026-10-01; details in specs 01, 02, 09)

- The ONS↔SIGA join failed mainly on **format** (CEG suffix `.01` vs `.1`: 0% → 92.5% after
  normalizing) and **grain** (ONS mixes plants, wind/solar complexes and state totals) — not on
  missing IDs. ONS's own complex-member data resolves the complexes; fuzzy matching is a small
  safety net (~0.2% of MWh).
- ONS data quirks found and handled: a STRING→DOUBLE type change from 2026-05, 24 plants published
  both standalone and inside their complex (double count), and complexes named both "Conj." and
  "Conjunto …".

## Open questions

- None open.
