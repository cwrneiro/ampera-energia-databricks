# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Ampera data/engineering team** — want to see that ONS generation and ANEEL SIGA plants
  finally join, at plant (CEG) and conjunto grain, and trust the numbers.
- **Ampera decision-makers** — want the picture fast: how much generated, where, at what price.
- Scene: first presented live by a Databricks FE on a shared/projected screen, then left with the
  team to explore on their own. Both must work.

## Product Purpose

Shows Brazilian power-plant generation (last 24 months, 2024-10 … 2026-09) reconciled across ONS
and ANEEL SIGA — two sources that don't join directly — by CEG and by conjunto, with captured price
(CCEE PLD) and weather, on a map. Success: the reconciliation is believable and the generation
story is legible in seconds.

## Positioning

One trusted plant ID across ONS and SIGA: CEG where present, fuzzy match with confidence otherwise,
ONS complex members resolved; every MWh accounted for (unmatched share is shown, not hidden).

## Operating Context

Read-only data app (Databricks App, workspace auth) over Lakebase; daily grain. UI in PT-BR.

## Capabilities and Constraints

- Pages: Visão geral, Reconciliação (incl. the `ai_decide` review queue), Curtailment (energy lost to
  constraints, modeled), Mapa, Usina (plant detail with actual vs expected). A slide-out Genie chat
  ("Pergunte ao Genie") answers in PT-BR on every page, on behalf of the signed-in user.
- Terms: CEG, conjunto, UF, fonte (EOL, SOL, HID, THERM, NUC, OTHER), submercado, PLD (R$/MWh),
  "estimado" (capacity-weighted member estimate), grão publicado vs usina.
- Measured irradiance (ONS, likely panel plane) is shown apart from modeled (horizontal);
  INMET wind is at 10 m. Estimated MWh is always labeled.

## Brand Commitments

- Ampera only — no Databricks mark in the UI.
- Palette/typography in `specs/08-branding.md` (purple `#541790`, blue `#0089f7`, orange `#fe5200`,
  Nunito, light mode).
- Brand mark: the text wordmark "Ampera **Energia**" (`main.jsx`) and an SVG bolt favicon.

## Evidence on Hand

Real data only: Lakebase `ampera_gold_lb` (generation_daily, plant_location, reconciliation_monthly).
No testimonials, customer quotes, or claims beyond what the data shows.

## Product Principles

1. Every number traces to the data; totals tie across views.
2. Show the reconciliation's uncertainty (estimado, unmatched), don't hide it.
3. Legible at projector distance, explorable up close.
