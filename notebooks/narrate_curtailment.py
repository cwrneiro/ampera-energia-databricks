# Databricks notebook source
# MAGIC %md
# MAGIC # Curtailment narrative (spec 16)
# MAGIC
# MAGIC Turns each plant's curtailment numbers into a short PT-BR explanation for clients. Runs in the refresh
# MAGIC job right after `score_curtailment`.
# MAGIC - **Grounded:** the LLM sees only a facts JSON built from `ampera_gold.curtailment_daily` (`src/narrative_lib.py`),
# MAGIC   with every number pre-formatted; a narrative that cites any number not in the facts is logged with
# MAGIC   `grounded = false` and never shown.
# MAGIC - **Logged like the ai_decide verdicts:** `ampera_gold.curtailment_narrative_log` keeps one row per plant x facts
# MAGIC   hash x prompt hash. `ai_query` is called only for keys not on file, so a steady-state refresh asks nothing;
# MAGIC   a retrained model (new numbers) or a prompt change re-asks. A call that errors is not logged and is retried
# MAGIC   on the next refresh.
# MAGIC - **Served:** `ampera_gold.curtailment_narrative` (one grounded narrative per plant, for the current facts;
# MAGIC   row-filtered per client, spec 17) is in the Genie space; its unfiltered copy `ampera_serving.curtailment_narrative`
# MAGIC   is synced to Lakebase for the Usina sheet.

# COMMAND ----------

import json
import os
import sys

from pyspark.sql import functions as F
from pyspark.sql import Window as W

sys.path.append(os.path.abspath("../src"))
import narrative_lib as N  # noqa: E402  facts, prompt, grounding check (tests/test_narrative.py)

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
DAILY = f"{CAT}.ampera_gold.curtailment_daily"
LOG, CUR = f"{CAT}.ampera_gold.curtailment_narrative_log", f"{CAT}.ampera_gold.curtailment_narrative"
SERV = f"{CAT}.ampera_serving.curtailment_narrative"
KEY = ["plant_id", "facts_hash", "prompt_hash"]
spark.sql(f"""CREATE TABLE IF NOT EXISTS {LOG} (
    plant_id STRING, facts_hash STRING, prompt_hash STRING, fatos_json STRING, narrativa STRING,
    grounded BOOLEAN, endpoint STRING, model_version INT, gerado_em TIMESTAMP)
  COMMENT 'Gold (GenAI): every curtailment narrative ever generated, one per plant x facts hash x prompt hash (notebooks/narrate_curtailment). Spec 16.'""")  # noqa: F821

# COMMAND ----------

# MAGIC %md ## Facts per plant (only plants with R$ lost)

# COMMAND ----------

d = spark.table(DAILY)  # noqa: F821
plants = (d.groupBy("plant_id")
           .agg(F.max("nome").alias("nome"), F.max("fonte").alias("fonte"), F.max("uf").alias("uf"),
                F.max("submercado").alias("submercado"), F.max("capacidade_mw").alias("capacidade_mw"),
                F.min("dia").alias("de"), F.max("dia").alias("ate"),
                *[F.sum(c).alias(c) for c in ("mwh_restrito", "valor_rs_perdido", "mwh_esperado",
                                              "horas_restritas_modelo", "horas_restritas_ons")])
           .filter("valor_rs_perdido > 0"))
peers = W.partitionBy("fonte", "uf")
plants = (plants.withColumn("rank", F.rank().over(peers.orderBy(F.desc("valor_rs_perdido"))))
                .withColumn("n_pares", F.count("*").over(peers)))
months = (d.groupBy("plant_id", F.trunc("dia", "month").alias("mes"))
           .agg(F.sum("mwh_restrito").alias("mwh_restrito"), F.sum("valor_rs_perdido").alias("valor_rs_perdido"))
           .filter("valor_rs_perdido > 0")
           .withColumn("rn", F.row_number().over(W.partitionBy("plant_id").orderBy(F.desc("valor_rs_perdido"))))
           .filter("rn <= 3"))

top = {}
for m in months.orderBy("plant_id", "rn").collect():
    top.setdefault(m.plant_id, []).append(m.asDict())
rows = []
for p in plants.collect():
    f = N.facts(p.asDict(), top.get(p.plant_id, []), p["rank"], p.n_pares)
    rows.append((p.plant_id, N.facts_hash(f), N.PROMPT_HASH, N.facts_json(f)))
facts = spark.createDataFrame(rows, "plant_id STRING, facts_hash STRING, prompt_hash STRING, fatos_json STRING")  # noqa: F821
new = facts.join(spark.table(LOG).select(*KEY), KEY, "left_anti")  # noqa: F821
n = new.count()
print(f"{len(rows)} plants with R$ lost; {n} without a narrative for their current facts (prompt {N.PROMPT_HASH[:12]})")

# COMMAND ----------

# MAGIC %md ## Ask the LLM for new keys only, check grounding, log

# COMMAND ----------

if n:
    version = spark.table(f"{CAT}.ampera_gold.curtailment_hourly").agg(F.max("model_version")).first()[0]  # noqa: F821
    asked = (new.withColumn("prompt", F.concat(F.lit(N.PROMPT), F.col("fatos_json")))
                .withColumn("r", F.expr(f"ai_query('{N.ENDPOINT}', prompt, failOnError => false)"))
                .select(*KEY, "fatos_json", F.col("r.result").alias("narrativa"), F.col("r.errorMessage").alias("erro"))
                .toPandas())  # ~1.6k short rows; ai_query is billed per call, so collect once
    ok = asked[asked["erro"].isna() & asked["narrativa"].notna()].copy()
    ok["narrativa"] = ok["narrativa"].str.strip()
    ok["grounded"] = [N.grounded(t, json.loads(f)) for t, f in zip(ok["narrativa"], ok["fatos_json"])]
    ok["endpoint"], ok["model_version"] = N.ENDPOINT, int(version)
    log = (spark.createDataFrame(ok[[*KEY, "fatos_json", "narrativa", "grounded", "endpoint", "model_version"]])  # noqa: F821
                .withColumn("model_version", F.col("model_version").cast("int"))
                .withColumn("gerado_em", F.current_timestamp()))
    log.createOrReplaceTempView("narrative_new")
    spark.sql(f"""MERGE INTO {LOG} t USING narrative_new s
                  ON t.plant_id = s.plant_id AND t.facts_hash = s.facts_hash AND t.prompt_hash = s.prompt_hash
                  WHEN NOT MATCHED THEN INSERT *""")  # noqa: F821
    err = asked[asked["erro"].notna() | asked["narrativa"].isna()]
    print(f"logged {len(ok)} narratives ({int(ok['grounded'].sum())} grounded, {int((~ok['grounded']).sum())} not); "
          f"{len(err)} calls failed and will be retried on the next refresh")
    if len(err):
        print(err[["plant_id", "erro"]].head(10).to_string(index=False))
    if (~ok["grounded"]).any():
        bad = ok[~ok["grounded"]].head(5)
        for t, f in zip(bad["narrativa"], bad["fatos_json"]):
            print("\nNOT GROUNDED:", t, "\n  numbers not in the facts:", sorted(N.numbers(t) - N.numbers(f)))

# COMMAND ----------

# MAGIC %md ## Serve: one grounded narrative per plant, for today's facts

# COMMAND ----------

cur = (facts.select(*KEY).join(spark.table(LOG).filter("grounded"), KEY)  # noqa: F821
            .join(plants.select("plant_id", "nome", "uf", "fonte"), "plant_id")
            .select("plant_id", "nome", "uf", "fonte", "narrativa", "fatos_json", "endpoint", "model_version", "gerado_em"))
# Unfiltered serving copy = Lakebase sync source; the gold copy carries the client row filter (spec 17).
(cur.write.mode("overwrite").option("overwriteSchema", "true").option("delta.enableChangeDataFeed", "true")
    .saveAsTable(SERV))
spark.sql(f"COMMENT ON TABLE {SERV} IS 'Serving: unfiltered copy of ampera_gold.curtailment_narrative, synced to Lakebase. Spec 16, 17.'")  # noqa: F821
spark.sql(f"ALTER TABLE {SERV} ALTER COLUMN plant_id SET NOT NULL")  # noqa: F821
spark.sql(f"""CREATE OR REPLACE TABLE {CUR}
  COMMENT 'Gold (GenAI): one PT-BR curtailment explanation per wind/solar plant, written by {N.ENDPOINT} from fatos_json (built from curtailment_daily); only narratives whose every number appears in the facts. Clients see only their plants (row filter). Spec 16, 17.'
  WITH ROW FILTER {CAT}.ampera_gold.client_plant_filter ON (plant_id)
  AS SELECT * FROM {SERV}""")  # noqa: F821
served = spark.table(CUR)  # noqa: F821
print(f"{served.count()} of {len(rows)} plants have a grounded narrative")
for r in served.join(plants.select("plant_id", "valor_rs_perdido"), "plant_id").orderBy(F.desc("valor_rs_perdido")).limit(3).collect():
    print(f"\n{r.nome} ({r.uf}): {r.narrativa}")
