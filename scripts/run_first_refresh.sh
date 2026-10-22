#!/usr/bin/env bash
# Second bootstrap step: deploy the current code, run the refresh job once with a model retrain
# (medallion incl. ai_decide -> train + blind eval -> score -> governance; the sync tasks fail until
# the synced tables exist), then create the synced tables. Usage: scripts/run_first_refresh.sh [profile]
set -uo pipefail
P=${1:-<profile>}
cd "$(dirname "$0")/.."
(cd app/frontend && npm run build >/dev/null) && echo "frontend built"
databricks bundle deploy -p "$P"
databricks bundle run ampera_refresh -p "$P" --params train=true
scripts/create_synced_tables.sh "$P"
