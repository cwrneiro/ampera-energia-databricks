#!/usr/bin/env bash
# Create the Lakebase synced tables the app reads (SNAPSHOT) and print their pipeline ids for
# databricks.yml (sync_pipeline_*). SETUP.md §6.2. Usage: scripts/create_synced_tables.sh [profile]
set -uo pipefail
P=${1:-<profile>}; CAT=ampera_catalog; LB=ampera-demo
sync() {  # <table> <primary key as a JSON array>
  databricks postgres get-synced-table synced_tables/$CAT.ampera_gold_lb.$1 -p "$P" >/dev/null 2>&1 || \
  databricks postgres create-synced-table $CAT.ampera_gold_lb.$1 -p "$P" --json "{\"spec\": {
    \"source_table_full_name\": \"$CAT.ampera_gold.$1\", \"primary_key_columns\": $2,
    \"scheduling_policy\": \"SNAPSHOT\", \"branch\": \"projects/$LB/branches/production\",
    \"postgres_database\": \"databricks_postgres\", \"create_database_objects_if_missing\": true,
    \"new_pipeline_spec\": {\"storage_catalog\": \"$CAT\", \"storage_schema\": \"default\"}}}" >/dev/null
  echo "sync_pipeline_$1: $(databricks postgres get-synced-table synced_tables/$CAT.ampera_gold_lb.$1 -p "$P" -o json | jq -r .status.pipeline_id)"
}
sync generation_daily         '["dia", "plant_id"]'
sync plant_location           '["plant_id"]'
sync reconciliation_monthly   '["grao", "mes", "match_method"]'
sync reconciliation_ai_review '["ons_key"]'
sync curtailment_daily        '["dia", "plant_id"]'
