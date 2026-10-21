# 07 — Genie Agent

## Goal

A **Genie Agent** over the gold marts so Ampera can ask natural-language questions —
especially "geração por CEG" and "por conjunto" — and get correct SQL-backed answers.

## Built (2026-10-02) — decision #22

- **Space:** "Ampera · Geração Elétrica", id (set on deploy), warehouse
  `<warehouse-id>` (`var.warehouse_id`). Bundle resource `resources/ampera_genie.genie_space.yml`;
  body in `resources/genie/ampera.geniespace.json` (catalog name is literal there, not `${var.catalog}`;
  other targets deploy a catalog-substituted copy, SETUP §3).
- **Sources:** all four gold tables, raw (no Metric View): `generation_daily` (default grain),
  `plant_location` (capacity, municipality), `reconciliation_monthly`, `fact_generation_hourly` (hourly
  profiles only). Join specs: both facts → `plant_location` on `plant_id` (many-to-one).
- **PT-BR surfaces:** column descriptions + synonyms (usina, conjunto, geração, fonte, PLD, irradiância…),
  entity matching on names/UF/fonte/submercado/match_method; `confidence`, `dist_estacao_km`,
  `fonte_cadastro` hidden. Answers in PT-BR.
- **Snippets:** measures `geracao_twh`, `pld_capturado_rs_mwh` (= SUM(valor_rs)/SUM(mwh)), `pct_estimado`;
  filters "Usinas com CEG", "Últimos 12 meses" (relative to the last available day).
- **Example SQL** (one per shape): top CEG, conjunto monthly series, UF × fonte, captured vs average PLD
  by fonte (**price**), hourly generation vs irradiance for a solar conjunto (**weather**), share by
  reconciliation method (`grao = 'usina'`).
- **Text instructions** (< 2,000 chars): CEG NULL for SURR- plants, `mwh_estimado` ⊂ `mwh`, never sum
  the two `grao`, group conjuntos by `conjunto_key` (names repeat across keys in `plant_location`), daily
  table unless an hourly profile is asked.
- **Benchmarks:** 32 checked-SQL chat benchmarks (meets the ≥30 bar for optimization runs). First 14 =
  7 questions × 2 phrasings: CEG, top conjuntos, UF,
  solar by month, wind captured PLD, wind vs modeled wind speed (RS, Jul 2026), all-history total.
  The other 18 add submercado, fonte shares, capacity, estimated share, value at PLD, peak month,
  plant counts, semester comparison, captured PLD by submercado, hourly profile, CEG share, weather.

## Out of scope

- A separate chat UI (Genie's native surface; embed later if wanted). Model fine-tuning.
- Running benchmark-driven optimization (the 32 benchmarks make it possible when needed).

## Acceptance criteria

- ✓ "Generation by CEG" (Itaipu 2025 → 46.64 TWh) and "top 5 conjuntos 2025" match checked SQL.
- ✓ Price (solar captured PLD −22.8% vs average) and weather (Arinos hourly irradiance profile) answered
  correctly via the Conversation API; all-history total ties at 1,404.19 TWh.
- ✓ Curated questions/instructions are versioned in the bundle. `python tests/test_genie_space.py`
  checks the payload shape; `GENIE_LIVE=1` also runs every example/benchmark SQL and the total tie.
