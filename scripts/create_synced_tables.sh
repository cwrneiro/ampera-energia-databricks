#!/usr/bin/env bash
# Create the Lakebase synced tables the app reads (SNAPSHOT) and print their pipeline ids for
# targets/dev.yml (sync_pipeline_*). Spec 05. Row-filtered gold tables sync from their unfiltered
# ampera_serving copy (synced tables refuse a row-filtered source; spec 17). Usage: scripts/create_synced_tables.sh [profile]
set -euo pipefail
P=${1:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
bv() {  # bundle variable from targets/dev.yml; an empty value aborts (never write grants/payloads against "")
  local v; v=$(databricks bundle validate -p "$P" -o json | jq -r ".variables.$1.value // empty")
  [ -n "$v" ] || { echo "bundle validate returned no value for '$1' — fill targets/dev.yml" >&2; exit 1; }
  echo "$v"
}
CAT=$(bv catalog); LB=$(bv lakebase_project)
sync() {  # <table> <primary key as a JSON array> <source schema>
  databricks postgres get-synced-table synced_tables/$CAT.ampera_gold_lb.$1 -p "$P" >/dev/null 2>&1 || \
  databricks postgres create-synced-table $CAT.ampera_gold_lb.$1 -p "$P" --json "{\"spec\": {
    \"source_table_full_name\": \"$CAT.$3.$1\", \"primary_key_columns\": $2,
    \"scheduling_policy\": \"SNAPSHOT\", \"branch\": \"projects/$LB/branches/production\",
    \"postgres_database\": \"databricks_postgres\", \"create_database_objects_if_missing\": true,
    \"new_pipeline_spec\": {\"storage_catalog\": \"$CAT\", \"storage_schema\": \"default\"}}}" >/dev/null
  echo "sync_pipeline_$1: $(databricks postgres get-synced-table synced_tables/$CAT.ampera_gold_lb.$1 -p "$P" -o json | jq -r .status.pipeline_id)"
}
sync generation_daily         '["dia", "plant_id"]'                 ampera_serving
sync plant_location           '["plant_id"]'                        ampera_serving
sync reconciliation_monthly   '["grao", "mes", "match_method"]'     ampera_gold
sync reconciliation_ai_review '["ons_key"]'                         ampera_gold
sync curtailment_daily        '["dia", "plant_id"]'                 ampera_serving
sync curtailment_narrative    '["plant_id"]'                        ampera_serving
sync client_plant_access      '["principal", "plant_id"]'           ampera_serving
