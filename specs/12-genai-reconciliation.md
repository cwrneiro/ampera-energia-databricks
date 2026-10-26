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
- **Durable verdicts (outside the pipeline):** ai_decide is nondeterministic and billed per call, so
  it is asked once per **verdict key** = `ons_key` + hash of the A/B/C candidate ids + hash of the
  prompt (`reco_lib.verdict_key`, mirrored by `reco_ai.with_verdict_key`). Job task `adjudicate_ai`
  (`notebooks/adjudicate_ai`, after the medallion) builds the candidates for every ONS plant-grain
  series whose CEG doesn't link, calls ai_decide only for keys not on file, asserts every new answer
  has a choice and no error, and MERGEs them into the plain Delta table
  `silver.ai_decide_verdict` (answers are staged once in `silver.ai_decide_verdict_new` so the check and
  the MERGE read the same calls; good answers are kept even when another failed, and the task fails). It publishes `new_verdicts`; when > 0 a condition task runs
  `medallion_rerun` (same pipeline) so a new plant is applied in the same refresh. At steady state
  ai_decide is asked nothing and the re-run is skipped: totals are identical across refreshes.
  A changed candidate set re-asks that plant; a changed prompt re-asks all.
  **Force a full re-adjudication:** `TRUNCATE TABLE <catalog>.ampera_silver.ai_decide_verdict`, then
  run the job.
- **Pipeline:** temporary view `ai_verdict` = the stored verdict for each plant's **current** key
  (today's candidates and prompt; a candidate set that changes and changes back reuses its own stored
  answer, never another set's). `silver.ai_decide_verdict` is a required input like the override table: `scripts/bootstrap_workspace.sh`
  creates it empty (a pipeline can't test whether a table exists), so a fresh workspace bootstraps.
  Re-judged with the shared rule `reco_lib.ai_accept` (the chosen slot holds a real candidate and
  confidence ≥ `AI_CUTOFF`; `nenhum` or missing confidence never) → `silver.plant_match` ladder: override → CEG → fuzzy → **ai_decide** (accepted
  verdict) → surrogate. Method `ai_decide`, confidence = ai_decide's.
- **Review queue:** `gold.reconciliation_ai_review` (synced to Lakebase): current verdict, the three
  candidates with probabilities, the plant's final `match_method` / `plant_id`, MWh at stake. The app
  derives the state from `match_method` (spec 14). Humans confirm through
  `silver.plant_match_override` (newest row wins).
- **No rationale text** (decision #32): the per-candidate probabilities are the explanation.
- **Blind eval:** `notebooks/eval_ai_decide` replays the question on 200 CEG-matched ONS plants with
  the CEG hidden → accuracy, precision/coverage at the cutoff, calibration table → `evidence/`.

## Acceptance

- `adjudicate_ai` asserts every new verdict has a choice and no `ai_error` (a failed answer never
  reaches the verdict table, so it is re-asked next run).
- Pipeline check `silver.plant_match_ai_check` (fails the update): every `ai_decide` row in
  `plant_match` has an accepted verdict, uses the verdict's plant, and has a CEG that doesn't link to SIGA.
- `tests/test_reconciliation.py`: `ai_accept` truth table; verdict key stable / changes with
  candidates or prompt.
- Eval reports accuracy and a calibration table; `AI_CUTOFF` revisited with the user if the
  calibration says 0.9 is mis-set (a first probe returned 0.63 on an easy case).

## Results

- First pipeline run (2026-10-22): 33 ONS plant series reach ai_decide (5.4 TWh, mostly retired
  thermal plants). With rules only in the prompt it answered `nenhum` for all 33 (confidence ~0.65),
  even for plants re-registered under the same CEG registry number with a new fuel code or unit
  suffix (Prosperidade II, CGVE Innova, Do Atlântico). Passing the evidence per candidate instead
  (`similaridade_nome`, `mesmo_numero_ceg`, `mesmo_tipo`) moved those three to 0.95–0.97 and left the
  rest ≤ 0.52: the 0.9 cutoff separates them. Blind eval: see `evidence/`.
