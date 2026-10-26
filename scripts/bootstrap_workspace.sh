#!/usr/bin/env bash
# One-time workspace prerequisites for the dev target (README "Reproduce" step 2): Unity Catalog
# schemas, raw volume, the empty override and ai_decide verdict tables (the catalog must already exist),
# the Lakebase project and the analysts group. Idempotent: reruns skip what exists.
# Usage: scripts/bootstrap_workspace.sh [profile]   (default $DATABRICKS_CONFIG_PROFILE, else DEFAULT)
set -euo pipefail
P=${1:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
bv() {  # bundle variable from targets/dev.yml; an empty value aborts (never write grants/payloads against "")
  local v; v=$(databricks bundle validate -p "$P" -o json | jq -r ".variables.$1.value // empty")
  [ -n "$v" ] || { echo "bundle validate returned no value for '$1' — fill targets/dev.yml" >&2; exit 1; }
  echo "$v"
}
LB=$(bv lakebase_project); CAT=$(bv catalog); WH=$(bv warehouse_id)
VERDICT_DDL=$(python3 -c 'import sys; sys.path.insert(0, "src/transformations"); import reco_lib; print(reco_lib.VERDICT_DDL)')

echo "== Unity Catalog objects in $CAT"
for q in "CREATE SCHEMA IF NOT EXISTS $CAT.ampera_bronze" "CREATE SCHEMA IF NOT EXISTS $CAT.ampera_silver" \
         "CREATE SCHEMA IF NOT EXISTS $CAT.ampera_gold" "CREATE SCHEMA IF NOT EXISTS $CAT.ampera_gold_lb" \
         "CREATE VOLUME IF NOT EXISTS $CAT.ampera_bronze.raw" \
         "CREATE TABLE IF NOT EXISTS $CAT.ampera_silver.plant_match_override (ons_id STRING, plant_id STRING, note STRING, updated_at TIMESTAMP) COMMENT 'Manual reconciliation fixes; newest updated_at per ons_id wins (spec 02).'" \
         "CREATE TABLE IF NOT EXISTS $CAT.ampera_silver.ai_decide_verdict ($VERDICT_DDL) COMMENT 'Silver (GenAI): durable ai_decide verdicts, one per ONS plant x candidate set x prompt (notebooks/adjudicate_ai). Spec 12.'"; do
  databricks experimental aitools tools query -w "$WH" "$q" -p "$P" >/dev/null; echo "ok: ${q%% (*}"
done

echo "== Lakebase project $LB"
databricks postgres get-project projects/$LB -p "$P" >/dev/null 2>&1 \
  || databricks postgres create-project $LB --json '{"spec": {"display_name": "Ampera", "pg_version": 17}}' -p "$P"
databricks postgres update-endpoint projects/$LB/branches/production/endpoints/primary \
  "spec.autoscaling_limit_min_cu,spec.autoscaling_limit_max_cu,spec.suspend_timeout_duration" \
  --json '{"spec": {"autoscaling_limit_min_cu": 0.5, "autoscaling_limit_max_cu": 4, "suspend_timeout_duration": "1200s"}}' \
  -p "$P" >/dev/null; echo "endpoint sized 0.5-4 CU, suspend 20 min"

echo "== group ampera_analysts (read-only on gold, spec 13)"
databricks groups list -p "$P" -o json | grep -q '"ampera_analysts"' \
  || databricks groups create --display-name ampera_analysts -p "$P" -o json | grep -o '"id":"[^"]*"'

echo "Next: scripts/land_raw_data.sh $P"
