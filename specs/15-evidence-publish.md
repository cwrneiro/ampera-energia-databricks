# 15 — Execution evidence and publication

## Goal

Make the build's execution readable as text for an evaluator who can't see images, and publish a
clean public repo. Decisions #40–#41.

## Design

- **Notebooks with outputs:** job runs of `adjudicate_ai`, `train_curtailment`, `score_curtailment`,
  `eval_ai_decide`, `governance` exported and converted to `.ipynb` with their outputs
  (`scripts/export_run_notebooks.py <job_run_id>`) → `evidence/notebooks/`. `train_curtailment` and
  `eval_ai_decide` run only with `train=true`, so their notebooks stay from run 2 (2026-10-22); the
  others come from the latest `train=false` run.
- **Captures** (`scripts/collect_evidence.py` → `evidence/*.txt|json`): job runs and their task graph,
  pipeline expectation results, reconciliation metrics, row counts per layer, the durable ai_decide
  verdict store, Lakebase synced-table status and Postgres row counts, app API responses, Genie
  Conversation API answers with their SQL, test output.
- **Index:** README maps each required stage → code → evidence file.
- **Publication:** sanitization grep (no workspace hostnames, ids or emails),
  then public repo `cwrneiro/ampera-energia-databricks` — only after the user's go-ahead.
