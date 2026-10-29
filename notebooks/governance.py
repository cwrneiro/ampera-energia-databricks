# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog governance (spec 13)
# MAGIC
# MAGIC Declares, idempotently, on every refresh:
# MAGIC 1. **Access** — group `ampera_analysts` reads the gold marts only (no bronze/silver/serving, no writes);
# MAGIC    group `ampera_clients` reads only the five plant-grain gold tables, each row-filtered to the client's
# MAGIC    own plants (spec 17). Both are asserted after applying, so the task fails if the access model drifts.
# MAGIC 2. **Tags** — every schema and table carries `ampera_layer`, `ampera_domain` and its upstream
# MAGIC    `ampera_source`; ML/GenAI outputs carry `ampera_ai`; plant coordinates carry the governed tag
# MAGIC    `class.geo_coordinates`. Keys are namespaced (`ampera_*`) so they never collide with governed tag policies such as `layer`, `domain`, `source`
# MAGIC    and `project`, which may already exist in a metastore with their own allowed values.
# MAGIC 3. **Evidence** — prints grants, tags and table lineage (`system.access.table_lineage`).

# COMMAND ----------

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("analysts", "ampera_analysts")  # noqa: F821
dbutils.widgets.text("clients", "ampera_clients")  # noqa: F821
CAT, GRP, CLI = dbutils.widgets.get("catalog"), dbutils.widgets.get("analysts"), dbutils.widgets.get("clients")  # noqa: F821
S = {k: f"{CAT}.ampera_{k}" for k in ("bronze", "silver", "gold", "gold_lb", "serving")}
CLIENT_TABLES = ["fact_generation_hourly", "generation_daily", "plant_location", "curtailment_daily", "curtailment_narrative"]
FILTER = f"{CAT}.ampera_gold.client_plant_filter"


def sql(q):
    return spark.sql(q)  # noqa: F821


def show(q):
    print(sql(q).toPandas().to_string(index=False))


def kind(fqn):
    t = sql(f"SELECT table_type FROM {CAT}.information_schema.tables WHERE "
            f"table_schema = '{fqn.split('.')[1]}' AND table_name = '{fqn.split('.')[2]}'").first()
    return {"MATERIALIZED_VIEW": "MATERIALIZED VIEW", "STREAMING_TABLE": "STREAMING TABLE"}.get(t and t[0], "TABLE")

# COMMAND ----------

# MAGIC %md ## 1. Access: analysts read gold only

# COMMAND ----------

for q in [f"GRANT USE CATALOG ON CATALOG {CAT} TO `{GRP}`",
          f"GRANT USE SCHEMA, SELECT ON SCHEMA {S['gold']} TO `{GRP}`",
          f"REVOKE ALL PRIVILEGES ON SCHEMA {S['bronze']} FROM `{GRP}`",
          f"REVOKE ALL PRIVILEGES ON SCHEMA {S['silver']} FROM `{GRP}`",
          f"REVOKE ALL PRIVILEGES ON SCHEMA {S['serving']} FROM `{GRP}`"]:
    sql(q)
    print("ok:", q)

# The access model is asserted, not just applied: the job fails if it drifts (spec 13).
def schema_privs(schema, grp=GRP):
    return {r.ActionType for r in sql(f"SHOW GRANTS `{grp}` ON SCHEMA {schema}").collect()
            if r.Principal == grp and r.ObjectType == "SCHEMA"}


gold = schema_privs(S["gold"])
assert {"USE SCHEMA", "SELECT"} <= gold and "MODIFY" not in gold, f"{GRP} on {S['gold']}: {gold}"
for k in ("bronze", "silver", "serving"):
    assert not schema_privs(S[k]), f"{GRP} must have nothing on {S[k]}: {schema_privs(S[k])}"
leaks = sql(f"""SELECT table_schema, table_name, privilege_type FROM {CAT}.information_schema.table_privileges
                WHERE grantee = '{GRP}' AND table_schema IN ('ampera_bronze', 'ampera_silver', 'ampera_serving')""").collect()
assert not leaks, f"{GRP} has table grants in bronze/silver/serving: {leaks[:5]}"
print(f"asserted: {GRP} reads {S['gold']} ({sorted(gold)}), nothing on bronze/silver/serving")

# COMMAND ----------

# MAGIC %md ## 1b. Access: clients read their own plants only (spec 17)

# COMMAND ----------

for q in ([f"GRANT USE CATALOG ON CATALOG {CAT} TO `{CLI}`", f"GRANT USE SCHEMA ON SCHEMA {S['gold']} TO `{CLI}`"]
          + [f"GRANT SELECT ON TABLE {S['gold']}.{t} TO `{CLI}`" for t in CLIENT_TABLES]
          + [f"REVOKE ALL PRIVILEGES ON SCHEMA {S[k]} FROM `{CLI}`" for k in ("bronze", "silver", "serving")]):
    sql(q)
    print("ok:", q)

cgold = schema_privs(S["gold"], CLI)
assert cgold == {"USE SCHEMA"}, f"{CLI} on {S['gold']} must be USE SCHEMA only (no schema-wide SELECT): {cgold}"
for k in ("bronze", "silver", "serving"):
    assert not schema_privs(S[k], CLI), f"{CLI} must have nothing on {S[k]}"
tgrants = {(r.table_schema, r.table_name, r.privilege_type) for r in sql(
    f"SELECT table_schema, table_name, privilege_type FROM {CAT}.information_schema.table_privileges WHERE grantee = '{CLI}'").collect()}
assert tgrants == {("ampera_gold", t, "SELECT") for t in CLIENT_TABLES}, f"{CLI} table grants drifted: {sorted(tgrants)}"
filters = {r.table_name: r.filter_name for r in sql(
    f"""SELECT table_name, filter_name FROM {CAT}.information_schema.row_filters
        WHERE table_schema = 'ampera_gold'""").collect()}
for t in CLIENT_TABLES:  # every table a client can read carries the client filter
    assert filters.get(t, "").endswith("client_plant_filter"), f"{S['gold']}.{t} has no client row filter: {filters.get(t)}"
print(f"asserted: {CLI} reads only {CLIENT_TABLES}, each with row filter {FILTER}")

# COMMAND ----------

# MAGIC %md ## 2. Tags

# COMMAND ----------

LAYER = {"bronze": "bronze", "silver": "silver", "gold": "gold", "gold_lb": "serving", "serving": "serving"}
for k, s in S.items():
    sql(f"ALTER SCHEMA {s} SET TAGS ('ampera_layer' = '{LAYER[k]}', 'ampera_domain' = 'energia')")

SOURCE = {  # table -> upstream public source(s)
    "ons_generation": "ONS", "ons_conjunto_member": "ONS", "ons_member_generation_wind": "ONS",
    "ons_member_generation_solar": "ONS", "siga_plants": "ANEEL SIGA", "ccee_pld_horario": "CCEE",
    "open_meteo_weather": "Open-Meteo", "inmet_weather": "INMET",
}
AI = {"ai_decide_verdict": "genai:ai_decide", "ai_decide_verdict_new": "genai:ai_decide", "ai_decide_eval": "genai:ai_decide",
      "curtailment_hourly": "ml:curtailment_expected_cf", "curtailment_daily": "ml:curtailment_expected_cf",
      "curtailment_narrative": "genai:ai_query", "curtailment_narrative_log": "genai:ai_query",
      "curtailment_model_monitor": "ml:curtailment_expected_cf"}
tables = sql(f"""SELECT table_schema, table_name FROM {CAT}.information_schema.tables
                 WHERE table_schema IN ('ampera_bronze', 'ampera_silver', 'ampera_gold', 'ampera_serving')
                   AND table_name NOT LIKE '\\_\\_%' AND table_name NOT LIKE 'event\\_log\\_%'""").collect()  # skip pipeline internals
for t in tables:
    fqn, layer = f"{CAT}.{t.table_schema}.{t.table_name}", t.table_schema.removeprefix("ampera_")
    tags = {"ampera_layer": layer, "ampera_domain": "energia", "ampera_source": SOURCE.get(t.table_name, "derived")}
    if t.table_name in AI:
        tags["ampera_ai"] = AI[t.table_name]
    body = ", ".join(f"'{k}' = '{v}'" for k, v in tags.items())
    try:
        sql(f"ALTER {kind(fqn)} {fqn} SET TAGS ({body})")
    except Exception as e:  # report, don't fail the refresh
        print(f"skip tags on {fqn}: {str(e).splitlines()[0][:160]}")
print(f"tagged {len(tables)} tables")

for t in ["plant_location", "curtailment_features_hourly"]:
    fqn = f"{S['gold']}.{t}"
    for col in ("lat", "lon"):
        try:
            sql(f"ALTER {kind(fqn)} {fqn} ALTER COLUMN {col} SET TAGS ('class.geo_coordinates')")
        except Exception as e:  # governed tag needs ASSIGN on the tag policy; report, don't fail the job
            print(f"skip governed tag on {fqn}.{col}: {str(e).splitlines()[0][:160]}")

# COMMAND ----------

# MAGIC %md ## 3. Evidence: grants, tags, lineage

# COMMAND ----------

for k in ("bronze", "silver", "gold", "serving"):
    print(f"\n-- grants on {S[k]} for {GRP}")
    show(f"SHOW GRANTS `{GRP}` ON SCHEMA {S[k]}")
print(f"\n-- table grants for {CLI}")
show(f"SELECT table_schema, table_name, privilege_type FROM {CAT}.information_schema.table_privileges WHERE grantee = '{CLI}' ORDER BY ALL")
print("\n-- row filters")
show(f"SELECT table_schema, table_name, filter_name, target_columns FROM {CAT}.information_schema.row_filters WHERE table_schema LIKE 'ampera_%' ORDER BY ALL")
print("\n-- client access model (principals masked)")
show(f"""SELECT cliente, count(DISTINCT principal) AS principals, count(DISTINCT plant_id) AS plants
         FROM {S['gold']}.client_plant_access GROUP BY ALL ORDER BY ALL""")
print("\n-- table tags")
show(f"""SELECT schema_name, table_name, concat_ws(', ', collect_list(concat(tag_name, '=', tag_value))) AS tags
         FROM {CAT}.information_schema.table_tags WHERE schema_name LIKE 'ampera_%' AND tag_name LIKE 'ampera_%'
         GROUP BY ALL ORDER BY ALL""")
print("\n-- column tags")
show(f"""SELECT schema_name, table_name, column_name, tag_name FROM {CAT}.information_schema.column_tags
         WHERE schema_name LIKE 'ampera_%' ORDER BY ALL""")
print("\n-- lineage (system.access.table_lineage): source -> target across the medallion, ML and GenAI")
try:
    show(f"""SELECT DISTINCT replace(source_table_full_name, '{CAT}.', '') AS source,
                replace(target_table_full_name, '{CAT}.', '') AS target, entity_type
         FROM system.access.table_lineage
         WHERE target_table_full_name LIKE '{CAT}.ampera_%' AND source_table_full_name IS NOT NULL
           AND event_date >= current_date() - INTERVAL 30 DAYS
         ORDER BY target, source""")
except Exception as e:
    print(f"lineage unavailable: {str(e).splitlines()[0][:200]}")
