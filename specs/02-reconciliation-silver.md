# 02 — Reconciliation & Silver (CORE)

## Goal

Give every ONS generation record one reliable `plant_id` that links to the SIGA registry wherever
possible — Ampera's stated pain — and make the matching method visible.

## Matching ladder (decision #10) — `silver.plant_match`, one row per ONS series (`ons_key`)

1. **Override** — `silver.plant_match_override(ons_id, plant_id, note, updated_at)` wins over
   everything; with several rows per `ons_id` the newest `updated_at` wins. A required input,
   created outside the pipeline:
   `CREATE TABLE ampera_catalog.silver.plant_match_override (ons_id STRING, plant_id STRING, note STRING, updated_at TIMESTAMP)`.
2. **CEG (normalized)** — ONS `ceg` and SIGA `CodCEG` with the last segment normalized
   (`.01` → `.1`); method `ceg`, confidence 1.0.
3. **Fuzzy** — normalized names (upper, accent-stripped, generic words removed, tokens sorted),
   same UF + fuel class; normalized Levenshtein ≥ **0.82**; **numerals must match** ("Prosperidade
   III" ≠ "Prosperidade II" — a real false match). Method `fuzzy`, confidence = similarity.
4. **Labeled grains** — ONS complexes (id `CJU_*` or name "Conj…") → `ons_conjunto`; state-level
   `PQU … MMGD` / `CARGA GLOBAL` totals → `ons_aggregate`. No 1:1 SIGA plant by design.
5. **Unmatched** — stable surrogate `SURR-<hash(name|UF|fuel)>` so generation is never dropped.

`ons_key = coalesce(id_ons, nom_usina)` because Tipo III / MMGD groups have no `id_ons`. ONS has no
installed capacity, so capacity can't tie-break (divergence from the original plan).

## Datasets (silver)

`ons_plant` · `siga_plant` (1 row per normalized CEG; coords, capacity) · `plant_match` ·
`generation` (hourly fact **as ONS publishes it**) · `dim_plant` (built from the plant-grain fact,
spec 09). Matching runs as native Spark expressions (`reco_sql.py`) mirroring the tested reference
`reco_lib.py` — Python UDFs can't import local modules on serverless workers.

## Acceptance criteria

- ✓ 100% of generation rows have a `plant_id` (expect_or_fail).
- ✓ Break-down by method in count and MWh; plant-level unmatched < 5% (SUCCESS #1).
- Runnable check (`tests/test_reconciliation.py`): ✓ CEG normalization, ✓ name normalization, ✓
  fuzzy variant clears the bar, ✓ numbered plants never match.
- In-pipeline check `silver.plant_match_check` (fails the update): one row per `ons_key`, and the
  newest override per `ons_id` is the applied `plant_id` with method `override`. ✓ Verified
  2026-10-09 (update `2c99372c`): two test rows for `BAGUA` → the newer won, 967 rows / 967 series.

## Results (24 months, 1,409 TWh, published grain)

ceg 64.6% · ons_conjunto 20.5% · ons_aggregate 14.3% · unmatched 0.4% · fuzzy 0.2% of MWh.
**Plant-level unmatched = 0.59%** of plant-level MWh. Complexes are split into measured member
plants in spec 09. Takeaway for the demo: the join failed on format (CEG suffix) and grain
(complexes, state totals), not missing IDs; fuzzy is a small safety net.

## Open questions

- SIGA grain: `CodCEG` is per generating unit; `dim_plant` is unit-level. Fine for the demo.
