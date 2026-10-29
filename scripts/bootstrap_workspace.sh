#!/usr/bin/env bash
# One-time workspace prerequisites for the dev target (README "Reproduce" step 2): Unity Catalog
# schemas, raw volume, the empty override and ai_decide verdict tables (the catalog must already exist),
# the client access table + row filter function (spec 17), the Lakebase project and the analysts and
# clients groups. Idempotent: reruns skip what exists.
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
         "CREATE SCHEMA IF NOT EXISTS $CAT.ampera_serving COMMENT 'Unfiltered copies of the row-filtered gold tables: Lakebase sync sources only (synced tables refuse row-filtered sources). Spec 17.'" \
         "CREATE VOLUME IF NOT EXISTS $CAT.ampera_bronze.raw" \
         "CREATE TABLE IF NOT EXISTS $CAT.ampera_silver.plant_match_override (ons_id STRING, plant_id STRING, note STRING, updated_at TIMESTAMP) COMMENT 'Manual reconciliation fixes; newest updated_at per ons_id wins (spec 02).'" \
         "CREATE TABLE IF NOT EXISTS $CAT.ampera_silver.ai_decide_verdict ($VERDICT_DDL) COMMENT 'Silver (GenAI): durable ai_decide verdicts, one per ONS plant x candidate set x prompt (notebooks/adjudicate_ai). Spec 12.'" \
         "CREATE TABLE IF NOT EXISTS $CAT.ampera_gold.client_plant_access (principal STRING NOT NULL, cliente STRING NOT NULL, plant_id STRING NOT NULL) COMMENT 'Gold (access): which plants each client principal may see; filled by notebooks/client_access. Spec 17.'" \
         "CREATE OR REPLACE FUNCTION $CAT.ampera_gold.client_plant_filter(plant_id STRING) RETURNS BOOLEAN COMMENT 'Row filter (spec 17): a principal listed in client_plant_access sees only its plants; everyone else (Ampera staff, pipelines, syncs) sees all rows.' RETURN NOT EXISTS (SELECT 1 FROM $CAT.ampera_gold.client_plant_access a WHERE a.principal = current_user()) OR EXISTS (SELECT 1 FROM $CAT.ampera_gold.client_plant_access a WHERE a.principal = current_user() AND a.plant_id = client_plant_filter.plant_id)"; do
  databricks experimental aitools tools query -w "$WH" "$q" -p "$P" >/dev/null; echo "ok: ${q%% (*}"
done

echo "== Lakebase project $LB"
databricks postgres get-project projects/$LB -p "$P" >/dev/null 2>&1 \
  || databricks postgres create-project $LB --json '{"spec": {"display_name": "Ampera", "pg_version": 17}}' -p "$P"
databricks postgres update-endpoint projects/$LB/branches/production/endpoints/primary \
  "spec.autoscaling_limit_min_cu,spec.autoscaling_limit_max_cu,spec.suspend_timeout_duration" \
  --json '{"spec": {"autoscaling_limit_min_cu": 0.5, "autoscaling_limit_max_cu": 4, "suspend_timeout_duration": "1200s"}}' \
  -p "$P" >/dev/null; echo "endpoint sized 0.5-4 CU, suspend 20 min"

# Account-level groups (UC can only grant to those), created through the workspace's account SCIM proxy
# and assigned to the workspace; `databricks groups create` may make a workspace-local group instead.
HAVE=$(databricks groups list -p "$P" -o json | jq -r '.[].displayName')
for g in ampera_analysts ampera_clients; do  # analysts: read gold (spec 13); clients: their plants only (spec 17)
  echo "== group $g"
  grep -qx "$g" <<< "$HAVE" && continue
  id=$(databricks api post /api/2.0/account/scim/v2/Groups -p "$P" \
         --json "{\"schemas\": [\"urn:ietf:params:scim:schemas:core:2.0:Group\"], \"displayName\": \"$g\"}" | jq -r .id)
  databricks api put /api/2.0/preview/permissionassignments/principals/$id -p "$P" --json '{"permissions": ["USER"]}' >/dev/null
  echo "created account group $g and assigned it to the workspace"
done
# Clients run Genie and SQL on the warehouse as themselves (on-behalf-of-user): SQL access + CAN_USE.
CG=$(databricks groups list -p "$P" -o json | jq -r '.[] | select(.displayName=="ampera_clients") | .id')
databricks groups patch "$CG" -p "$P" --json '{"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
  "Operations": [{"op": "add", "path": "entitlements", "value": [{"value": "databricks-sql-access"}]}]}' >/dev/null
databricks permissions update warehouses "$WH" -p "$P" \
  --json '{"access_control_list": [{"group_name": "ampera_clients", "permission_level": "CAN_USE"}]}' >/dev/null
echo "ampera_clients: SQL access, can use warehouse $WH"

echo "Next: scripts/land_raw_data.sh $P"
