#!/usr/bin/env bash
# One-time workspace bootstrap for the dev target (SETUP.md §2–§6 for this repo's defaults):
# Lakebase project, the analysts group, first bundle deploy and the first medallion run.
# Usage: scripts/bootstrap_workspace.sh [profile]   (default <profile>). Idempotent-ish: reruns skip what exists.
set -uo pipefail
P=${1:-<profile>}
LB=ampera-demo
cd "$(dirname "$0")/.."

echo "== Lakebase project $LB"
databricks postgres get-project projects/$LB -p "$P" >/dev/null 2>&1 \
  || databricks postgres create-project $LB --json '{"spec": {"display_name": "Ampera", "pg_version": 17}}' -p "$P"
databricks postgres update-endpoint projects/$LB/branches/production/endpoints/primary \
  "spec.autoscaling_limit_min_cu,spec.autoscaling_limit_max_cu,spec.suspend_timeout_duration" \
  --json '{"spec": {"autoscaling_limit_min_cu": 0.5, "autoscaling_limit_max_cu": 4, "suspend_timeout_duration": "1200s"}}' \
  -p "$P" >/dev/null && echo "endpoint sized 0.5-4 CU, suspend 20 min"

echo "== group ampera_analysts (read-only on gold, spec 13)"
databricks groups list -p "$P" -o json | grep -q '"ampera_analysts"' \
  || databricks groups create --display-name ampera_analysts -p "$P" -o json | grep -o '"id":"[^"]*"'

echo "== bundle deploy (the first one may fail on the Genie space / job: gold and sync tables don't exist yet)"
databricks bundle deploy -p "$P" || echo "deploy incomplete — expected before the first run"

echo "== medallion run"
databricks bundle run ampera_medallion -p "$P"
