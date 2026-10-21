# SUCCESS_CRITERIA — Ampera Demo v1

A great v1 is verifiable by inspection or by running something. Vague ("works well") is not allowed.

## Functional

1. **Reconciliation (core).** Every plant generation record from ONS resolves to exactly one unique
   `plant_id`, whether or not it has a CEG. A query can show: total ONS plants, how many matched by
   CEG, how many by fuzzy surrogate key, and how many unmatched (target: unmatched < 5% of
   **plant-level** generation MWh; decision #15). ONS complexes (`Conj.` / `Conjunto …`) and
   state-level totals (`PQU`/`CARGA GLOBAL`) have no 1:1 SIGA plant, so they are reported as
   separate categories, not as unmatched.
   Each fuzzy match carries a confidence score.
2. **Generation by CEG and by conjunto.** A user can retrieve total/time-series generation grouped
   by CEG and grouped by conjunto (group), as Ampera's brief requires — in SQL, in the app, and
   via Genie.
3. **Medallion is navigable.** Bronze holds raw ONS (generation + complex members), SIGA, CCEE PLD
   and weather (Open-Meteo, INMET) as ingested; silver holds
   cleaned + reconciled entities; gold holds the query-ready marts the app and Genie read. Each
   layer is a distinct schema and each table has a one-line comment.
4. **Pipeline runs green.** The Lakeflow Declarative Pipeline executes bronze→silver→gold end to end
   on `<profile>` with data-quality expectations defined on the reconciliation output; a
   failed expectation is visible, not silent.
5. **Lakebase.** An autoscaling Lakebase Postgres instance holds the app's serving tables, fed from
   gold via a **Synced Table**. The app reads Lakebase, not the lakehouse directly.
6. **App.** A deployed Databricks App (FastAPI + React, UI in PT-BR) shows generation by CEG/conjunto
   with filters, and an interactive point map of plants (SIGA has lat/long — decision #9). App
   styling uses the Ampera brand tokens.
7. **Genie Agent.** A Genie Agent answers natural-language questions over the gold marts, including
   "generation by CEG", "by conjunto", and at least one price- or weather-enriched question, with
   curated instructions/example SQL so the common questions answer correctly.
8. **Enrichment present.** Gold joins price (CCEE PLD, decision #19) by hour + submarket and
   weather by location + hour (Open-Meteo for every located plant; measured ONS/INMET where
   available — decision #18). Both joins required. Across the app and Genie combined, each enrichment —
   price and weather — is demonstrated at least once (not necessarily in the same surface).

## Quality

9. Non-trivial transforms (reconciliation/matching above all) have a runnable check that fails if the
   logic breaks.
10. No secrets or raw data files committed (enforced by `.gitignore`).
11. App frontend meets Impeccable's bar (visual hierarchy, accessible contrast, responsive).

## Process

12. Each spec file is ~1 page, self-contained, and traces to the decision log in `00-overview.md`.
13. Every feature traces to a spec; divergence updates the spec in the same change.
14. STATE.md is never staler than the work on disk (Stop hook enforces).
