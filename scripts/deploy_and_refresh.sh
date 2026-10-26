#!/usr/bin/env bash
# Deploy everything, (re)start the app, grant its service principal read on the Lakebase serving
# schema, then run the refresh job. Usage: scripts/deploy_and_refresh.sh [train=true|false] [profile]
set -euo pipefail
TRAIN=${1:-false}; P=${2:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
[ -f targets/dev.geniespace.json ] || cp resources/genie/ampera.geniespace.json targets/dev.geniespace.json  # validate needs it
bv() {  # bundle variable from targets/dev.yml; an empty value aborts (never write grants/payloads against "")
  local v; v=$(databricks bundle validate -p "$P" -o json | jq -r ".variables.$1.value // empty")
  [ -n "$v" ] || { echo "bundle validate returned no value for '$1' — fill targets/dev.yml" >&2; exit 1; }
  echo "$v"
}
LB=$(bv lakebase_project); CAT=$(bv catalog)
# Genie space body names its tables; the dev overlay points at a copy with this target's catalog (spec 07)
sed "s/ampera_catalog\./$CAT./g" resources/genie/ampera.geniespace.json > targets/dev.geniespace.json
(cd app/frontend && npm run build >/dev/null); echo "frontend built"
databricks bundle deploy -p "$P"
databricks bundle run ampera_app -p "$P"
SP=$(databricks apps get ampera-app -p "$P" -o json | jq -r '.service_principal_client_id // empty')
[ -n "$SP" ] || { echo "app ampera-app has no service principal yet" >&2; exit 1; }
databricks psql --project $LB -p "$P" -- -d databricks_postgres -c \
  "GRANT USAGE ON SCHEMA ampera_gold_lb TO \"$SP\"; GRANT SELECT ON ALL TABLES IN SCHEMA ampera_gold_lb TO \"$SP\";"
databricks bundle run ampera_refresh -p "$P" --params train=$TRAIN
