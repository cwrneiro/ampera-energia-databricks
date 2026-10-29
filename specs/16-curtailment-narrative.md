# 16 — GenAI: curtailment narrative per plant

## Goal

Turn each plant's curtailment numbers (spec 11) into a short PT-BR explanation a client can read:
how much it lost, in R$, when it concentrated, and why the figure is a lower bound. Grounded in the
same gold numbers and logged the way the `ai_decide` verdicts are (spec 12). Decided 2026-10-27
after the FE review ("extend the ai_decide pattern into a narrative layer").

## Design

- **Scope:** every wind/solar plant with R$ lost > 0 (1,598), over the full 24-month window. One
  narrative per plant, not per month.
- **Facts, not data:** `src/narrative_lib.facts` builds a JSON of pre-formatted PT-BR strings from
  `gold.curtailment_daily`: energy and R$ lost, share of expected output, mean PLD of the lost energy,
  model vs ONS curtailed hours, rank among plants of the same fonte and UF, the 3 worst months, and
  the lower-bound note. The LLM never sees a raw number it would have to round.
- **Model:** `ai_query('databricks-claude-sonnet-5-5', prompt || facts_json)`. Default parameters
  (this endpoint rejects `temperature`, and a low `max_tokens` came back empty). The prompt: 2–3
  sentences, ≤ 70 words, copy every number as written, say it is a lower bound, no markdown.
- **Grounding check:** `narrative_lib.grounded` extracts every numeric token in the answer and requires
  each to appear in the facts JSON. A failing narrative is logged with `grounded = false` and never
  served. `python3 tests/test_narrative.py` covers formatting, hash stability and the check (a
  rounded figure or an invented one fails).
- **Logged once:** `gold.curtailment_narrative_log` keeps one row per plant × facts hash × prompt hash
  (`notebooks/narrate_curtailment`). `ai_query` runs only for keys not on file, so a steady-state refresh
  asks nothing; new numbers (a retrained model, new data) or a prompt change re-ask. A call that errors
  is not logged, so it's retried on the next refresh.
- **Served:** `gold.curtailment_narrative` (current facts, grounded only; row-filtered per client,
  spec 17) is in the Genie space (benchmark #39); its copy `ampera_serving.curtailment_narrative` is
  synced to Lakebase, and `/api/plant` returns it for the Usina sheet's curtailment block with an "IA"
  label and the model version.
- **Runs:** task `narrate_curtailment` after `score_curtailment` (and after `rescore_curtailment` when
  a drift retrain promoted a new champion, spec 18), then `sync_curtailment_narrative`.

## Acceptance

- Every served narrative passes `grounded`; the count of logged vs grounded is in `evidence/10`.
- A second refresh with unchanged numbers asks `ai_query` nothing.
- Usina sheet shows the narrative for a curtailed plant and nothing for others; Genie answers
  "Explique o curtailment da usina Canoa Quebrada" from the table.

## Results

- 2026-10-27 probe (2 plants): both grounded. First full run: 1,598 logged, **1,598 grounded**.
- The forced drift run (spec 18) promoted model v3, whose new numbers re-asked all 1,598 plants (3,196
  logged, all grounded); the rollback to v2 matched the already-logged v2 facts and asked nothing.
