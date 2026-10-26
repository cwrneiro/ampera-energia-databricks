#!/usr/bin/env bash
# First refresh (README "Reproduce" step 4, after the raw data is landed): first deploy + medallion run,
# then deploy again and run the refresh job once with a model retrain (medallion -> ai_decide
# adjudication -> train + blind eval -> score -> governance; the sync tasks fail until the synced tables
# exist), then create the synced tables and print their pipeline ids for targets/dev.yml.
# Usage: scripts/run_first_refresh.sh [profile]
set -euo pipefail
P=${1:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
(cd app/frontend && npm run build >/dev/null); echo "frontend built"
# The very first deploy can't create the Genie space (its gold tables don't exist yet); the pipeline is created.
databricks bundle deploy -p "$P" || echo "deploy incomplete — expected before the first medallion run"
databricks bundle run ampera_medallion -p "$P"
databricks bundle deploy -p "$P"
# The sync tasks fail until the synced tables exist (created below); any other failed task stops here.
JOB=$(databricks bundle summary -p "$P" -o json | jq -r .resources.jobs.ampera_refresh.id)
last_run() { databricks jobs list-runs --job-id "$JOB" --limit 1 -p "$P" -o json | jq -r '.[0].run_id // empty'; }
PREV=$(last_run)
if ! databricks bundle run ampera_refresh -p "$P" --params train=true; then
  RUN=$(last_run)
  [ -n "$RUN" ] && [ "$RUN" != "$PREV" ] || { echo "the refresh job didn't start" >&2; exit 1; }
  BAD=$(databricks jobs get-run "$RUN" -p "$P" -o json | jq -r '.tasks[]
    | select((.state.result_state // "") | test("^(SUCCESS|EXCLUDED|SKIPPED)$") | not)
    | select(.task_key | startswith("sync_") | not) | .task_key')
  [ -z "$BAD" ] || { echo "refresh run $RUN failed outside the sync tasks: $BAD" >&2; exit 1; }
  echo "refresh run $RUN: only the sync tasks failed (expected before the synced tables exist)"
fi
scripts/create_synced_tables.sh "$P"
