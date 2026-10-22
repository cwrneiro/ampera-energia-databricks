# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog governance (spec 13)
# MAGIC
# MAGIC Declares, idempotently, on every refresh:
# MAGIC 1. **Access** — group `ampera_analysts` reads the gold marts only (no bronze/silver, no writes).
# MAGIC 2. **Tags** — every schema and table carries `layer`, `domain` and its upstream `source`; ML/GenAI
# MAGIC    outputs carry `ai`; plant coordinates carry the governed tag `class.geo_coordinates`.
# MAGIC 3. **Evidence** — prints grants, tags and table lineage (`system.access.table_lineage`).

# COMMAND ----------

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("analysts", "ampera_analysts")  # noqa: F821
CAT, GRP = dbutils.widgets.get("catalog"), dbutils.widgets.get("analysts")  # noqa: F821
S = {k: f"{CAT}.ampera_{k}" for k in ("bronze", "silver", "gold", "gold_lb")}


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
          f"REVOKE ALL PRIVILEGES ON SCHEMA {S['silver']} FROM `{GRP}`"]:
    sql(q)
    print("ok:", q)

# COMMAND ----------

# MAGIC %md ## 2. Tags

# COMMAND ----------

LAYER = {"bronze": "bronze", "silver": "silver", "gold": "gold", "gold_lb": "serving"}
for k, s in S.items():
    sql(f"ALTER SCHEMA {s} SET TAGS ('layer' = '{LAYER[k]}', 'domain' = 'energia', 'project' = 'ampera')")

SOURCE = {  # table -> upstream public source(s)
    "ons_generation": "ONS", "ons_conjunto_member": "ONS", "ons_member_generation_wind": "ONS",
    "ons_member_generation_solar": "ONS", "siga_plants": "ANEEL SIGA", "ccee_pld_horario": "CCEE",
    "open_meteo_weather": "Open-Meteo", "inmet_weather": "INMET",
}
AI = {"plant_match_ai": "genai:ai_decide", "ai_decide_eval": "genai:ai_decide",
      "curtailment_hourly": "ml:curtailment_expected_cf", "curtailment_daily": "ml:curtailment_expected_cf"}
tables = sql(f"""SELECT table_schema, table_name FROM {CAT}.information_schema.tables
                 WHERE table_schema IN ('ampera_bronze', 'ampera_silver', 'ampera_gold')""").collect()
for t in tables:
    fqn, layer = f"{CAT}.{t.table_schema}.{t.table_name}", t.table_schema.removeprefix("ampera_")
    tags = {"layer": layer, "domain": "energia", "source": SOURCE.get(t.table_name, "derived")}
    if t.table_name in AI:
        tags["ai"] = AI[t.table_name]
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

for k in ("bronze", "silver", "gold"):
    print(f"\n-- grants on {S[k]} for {GRP}")
    show(f"SHOW GRANTS `{GRP}` ON SCHEMA {S[k]}")
print("\n-- table tags")
show(f"""SELECT schema_name, table_name, concat_ws(', ', collect_list(concat(tag_name, '=', tag_value))) AS tags
         FROM {CAT}.information_schema.table_tags WHERE schema_name LIKE 'ampera_%'
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
