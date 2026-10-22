# 06 — Databricks App

## Goal

A deployed **Databricks App** (FastAPI + React) that reads **Lakebase** and shows Ampera their
reconciled generation — by CEG and by conjunto — plus an interactive map. UI in PT-BR, styled with
the brand tokens in `specs/08-branding.md`. **Deployed** 2026-10-02 (`ampera-app`).

## In scope

- **Backend:** FastAPI reading the Lakebase tables in schema `ampera_gold_lb` (spec 05):
  `generation_daily`, `plant_location`, `reconciliation_monthly`.
- **Frontend:** React built with the **Impeccable** skill; UI text in PT-BR.
  - **Overview:** generation KPIs + time series, filters for CEG, conjunto, UF, fonte, period.
  - **Reconciliation:** how ONS links to SIGA — methods `ceg`, `fuzzy`, `unmatched`,
    `ons_conjunto`, `ons_aggregate`, and at plant grain `member_measured` / `member_estimated`;
    both grains (`grao` publicado / usina) from `reconciliation_monthly`.
  - **Map (decision #9 → point map):** plants from `plant_location` (1,973 located, 85% of MWh).
  - **Price and weather** (with Genie, each shown at least once): captured PLD vs average by fonte;
    modeled vs measured weather on a plant page.
- Labeling: show "estimado" where `mwh_estimado` > 0; label measured irradiance (ONS, likely panel
  plane) apart from modeled (horizontal); note INMET wind is at 10 m.

## Out of scope

- Custom auth / RBAC / multi-tenant (decision #7) — workspace auth only. Writes to Lakebase.

## Key decisions

- FastAPI + React (decision #5); reads Lakebase, not the lakehouse (decision #12).
- Hourly data stays in the lakehouse (decision #17); the app works at daily grain.

## Acceptance criteria

- ✓ App deploys to `<profile>` and reads Lakebase as its service principal (totals tie).
- ✓ By-CEG and by-conjunto views render with working filters (period, UF, fonte, conjunto, usina).
- ✓ Map page renders plant points (1,973) with a 5° graticule; click → plant sheet. Fits the viewport
  without page scroll above 900px wide; the map fills the sheet with title + legend (top-left), a filter
  menu behind an icon button (top-right) and notes (footer) as overlays; filters frame the map (2026-10-05).
- ✓ Frontend passes Impeccable's finish review (disposition: ship); brand palette applied.
- ✓ Text wordmark in the header and an SVG favicon (`public/favicon.svg`).

## Build decisions (decision #21, confirmed 2026-10-02)

- Pages: **Visão geral** (KPIs, series, CEG/conjunto ranking, PLD capturado vs médio by fonte),
  **Reconciliação**, **Mapa** (click → plant), **Usina** (daily series, modeled vs measured weather,
  captured PLD).
- Map: MapLibre GL + OpenFreeMap `positron` style (free, no key; tiles load in the viewer's browser).
  Filters frame the filtered plants (the camera glides there, 900 ms); the map refits on resize until
  the viewer pans or zooms.
- Cold Lakebase (scale-to-zero): the API drops its dead pooled connections, retries with backoff,
  then answers 503 "waking"; the UI shows "Acordando o banco de dados…" and retries on its own
  (`tests/test_app_api.py` checks the drain-and-503 path).
- Charts: Recharts. Postgres driver: `psycopg[binary]` (v3), OAuth via `databricks-sdk`.
- Frontend: React + Vite under `app/frontend`, built locally; the bundle syncs `dist` (not in git).

## Implementation notes

- API (`app/app.py`): `/api/meta`, `/plants`, `/reconciliation`, `/overview` (one scan,
  GROUPING SETS: series × fonte, by fonte, by plant, by conjunto), `/plant/{id}`. Read-only; 10-min
  in-process cache (warm overview ~1 s, ~6 s on a cold endpoint). Check: `tests/test_app_api.py`
  (overview, series and plant totals tie).
- Design world "carta topográfica" (Impeccable; contract in `.impeccable/surfaces/app-frontend.md`,
  product record in `PRODUCT.md`). Fonte and method palettes passed the dataviz validator.
- Unmatched on Reconciliação = SUCCESS #1 definition: unmatched ÷ (ceg + fuzzy + ai_decide + unmatched) at the
  published grain (0.59%).
- Deploy: `(cd app/frontend && npm ci && npm run build) && databricks bundle deploy && databricks
  bundle run ampera_app`, then grant the app SP `USAGE` on `ampera_gold_lb` and `SELECT` on its tables.
- Brand mark: text wordmark (`main.jsx`), no image logo.
