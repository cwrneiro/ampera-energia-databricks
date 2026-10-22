# 15 — Execution evidence and publication

## Goal

Make the build's execution readable as text for an evaluator who can't see images, and publish a
clean public repo. Decisions #40–#41.

## Design

- **Notebooks with outputs:** job runs of `train_curtailment`, `score_curtailment`,
  `eval_ai_decide`, `governance` exported and converted to `.ipynb` with their outputs
  (`scripts/export_run_notebooks.py`) → `evidence/notebooks/`.
- **Captures** (`scripts/collect_evidence.sh` → `evidence/*.txt|json`): pipeline update events and
  expectation results, reconciliation metrics, row counts per layer, Lakebase synced-table status and
  Postgres row counts, app API responses (`curl`), Genie Conversation API answers with their SQL,
  `pytest` output.
- **Index:** README maps each required stage → code → evidence file.
- **Publication:** sanitization grep (no workspace hostnames, ids or emails),
  then public repo `cwrneiro/ampera-energia-databricks` — only after the user's go-ahead.
