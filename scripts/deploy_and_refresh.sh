#!/usr/bin/env bash
# Deploy everything, (re)start the app, grant its service principal read on the Lakebase serving
# schema, then run the refresh job. Usage: scripts/deploy_and_refresh.sh [train=true|false] [profile]
set -uo pipefail
TRAIN=${1:-false}; P=${2:-<profile>}; LB=ampera-demo
cd "$(dirname "$0")/.."
(cd app/frontend && npm run build >/dev/null) && echo "frontend built"
databricks bundle deploy -p "$P" || exit 1
databricks bundle run ampera_app -p "$P"
SP=$(databricks apps get ampera-app -p "$P" -o json | jq -r .service_principal_client_id)
databricks psql --project $LB -p "$P" -- -d databricks_postgres -c \
  "GRANT USAGE ON SCHEMA ampera_gold_lb TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA ampera_gold_lb TO \"$SP\";"
databricks bundle run ampera_refresh -p "$P" --params train=$TRAIN
