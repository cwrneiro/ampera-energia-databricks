#!/usr/bin/env bash
# Deploy everything, (re)start the app, grant its service principal read on the Lakebase serving
# schema, then run the refresh job. Usage: scripts/deploy_and_refresh.sh [train=true|false] [profile]
set -uo pipefail
TRAIN=${1:-false}; P=${2:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
[ -f targets/dev.geniespace.json ] || cp resources/genie/ampera.geniespace.json targets/dev.geniespace.json  # validate needs it
bv() { databricks bundle validate -p "$P" -o json | jq -r ".variables.$1.value"; }  # values come from targets/<target>.yml
LB=$(bv lakebase_project)
# Genie space body names its tables; the dev overlay points at a copy with this target's catalog (SETUP §3)
sed "s/ampera_catalog\./$(bv catalog)./g" resources/genie/ampera.geniespace.json > targets/dev.geniespace.json
(cd app/frontend && npm run build >/dev/null) && echo "frontend built"
databricks bundle deploy -p "$P" || exit 1
databricks bundle run ampera_app -p "$P"
SP=$(databricks apps get ampera-app -p "$P" -o json | jq -r .service_principal_client_id)
databricks psql --project $LB -p "$P" -- -d databricks_postgres -c \
  "GRANT USAGE ON SCHEMA ampera_gold_lb TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA ampera_gold_lb TO \"$SP\";"
databricks bundle run ampera_refresh -p "$P" --params train=$TRAIN
