# 12 — GenAI: ai_decide reconciliation

## Goal

Place the ONS plants the rules can't (no CEG link, no confident fuzzy match) with a calibrated
GenAI decision, keep humans in charge of the uncertain ones, and measure how far to trust it.
Decisions #31–#33.

## Design

- **Function:** `ai_decide` (Beta; serverless SQL / SDP), `choice` question with fixed labels
  `A | B | C | nenhum`. Labels must be constant, so the per-plant candidates travel in `state` JSON:
  the ONS record (name, UF, type, informed CEG) + its top-3 SIGA candidates in the same UF by
  normalized-name similarity (name, UF, type, municipality, MW, CEG). Helpers: `reco_ai.py`.
- **Pipeline:** `silver.plant_match_ai` (every ONS plant-grain series whose CEG doesn't link) →
  `silver.plant_match` ladder: override → CEG → fuzzy → **ai_decide** (confidence ≥ `AI_CUTOFF`,
  `reco_lib`) → surrogate. Method `ai_decide`, confidence = ai_decide's.
- **Review queue:** `gold.reconciliation_ai_review` (synced to Lakebase): verdict, the three
  candidates with probabilities, applied or not, MWh at stake. Humans confirm through
  `silver.plant_match_override` (newest row wins).
- **No rationale text** (decision #32): the per-candidate probabilities are the explanation.
- **Blind eval:** `notebooks/eval_ai_decide` replays the question on 200 CEG-matched ONS plants with
  the CEG hidden → accuracy, precision/coverage at the cutoff, calibration table → `evidence/`.

## Acceptance

- Expectation `ai_answered` (no `ai_error`, choice present) on `plant_match_ai`.
- Eval reports accuracy and a calibration table; `AI_CUTOFF` revisited with the user if the
  calibration says 0.9 is mis-set (a first probe returned 0.63 on an easy case).

## Results

_Filled after the first eval run._
