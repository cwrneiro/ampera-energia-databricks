# Databricks notebook source
# MAGIC %md
# MAGIC # ai_decide adjudication (spec 12)
# MAGIC
# MAGIC Runs in the refresh job right after the medallion. For every ONS plant whose CEG doesn't link to SIGA
# MAGIC it builds the top-3 SIGA candidates (`reco_ai.candidates`, shared with the blind eval) and the verdict
# MAGIC key: `ons_key` + hash of the A/B/C candidate ids + hash of the ai_decide prompt. `ai_decide` is asked
# MAGIC **only for keys with no stored verdict**; the answers are MERGEd into the durable Delta table
# MAGIC `ampera_silver.ai_decide_verdict`. So a steady-state refresh asks nothing (deterministic totals, no
# MAGIC re-billing), a new plant or a changed candidate set is asked once, and a prompt change re-asks all.
# MAGIC
# MAGIC Publishes `new_verdicts` as a task value: when it is > 0 the job re-runs the pipeline once so the new
# MAGIC verdicts reach `plant_match` and gold in the same refresh. Force a full re-adjudication with
# MAGIC `TRUNCATE TABLE <catalog>.ampera_silver.ai_decide_verdict`.

# COMMAND ----------

import os
import sys

sys.path.append(os.path.abspath("../src/transformations"))
import reco_ai  # noqa: E402
import reco_lib as R  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
V, NEW = f"{CAT}.{R.VERDICT}", f"{CAT}.{R.VERDICT}_new"
KEY = reco_ai.VERDICT_KEY
spark.sql(f"""CREATE TABLE IF NOT EXISTS {V} ({R.VERDICT_DDL})
  COMMENT 'Silver (GenAI): durable ai_decide verdicts, one per ONS plant x candidate set x prompt (notebooks/adjudicate_ai). Spec 12.'""")  # noqa: F821

# COMMAND ----------

ons = spark.table(f"{CAT}.ampera_silver.ons_plant")  # noqa: F821
siga = spark.table(f"{CAT}.ampera_silver.siga_plant")  # noqa: F821
cands = reco_ai.with_verdict_key(reco_ai.candidates(reco_ai.unlinked_plants(ons, siga), siga))
new = cands.join(spark.table(V).select(*KEY), KEY, "left_anti")  # noqa: F821
n = new.count()
print(f"{cands.count()} ONS plants need ai_decide; {n} without a stored verdict (prompt {reco_ai.PROMPT_HASH[:12]})")

# COMMAND ----------

if n:
    # Persist the answers once in a staging table (ai_decide is nondeterministic and billed per call); the
    # MERGE and the check read it. Good answers are kept; a failed one never reaches the verdict table, so
    # the next run re-asks only that plant — and this task fails so it doesn't land as "unmatched" silently.
    (reco_ai.decide(new).withColumn("decided_at", F.current_timestamp())
     .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(NEW))
    spark.sql(f"COMMENT ON TABLE {NEW} IS 'Silver (GenAI): staging for the latest adjudication run (answers checked, then MERGEd into ai_decide_verdict). Spec 12.'")  # noqa: F821
    spark.sql(f"""MERGE INTO {V} t USING (SELECT * FROM {NEW} WHERE ai_error IS NULL AND ai_choice IS NOT NULL) s
                  ON t.ons_key = s.ons_key AND t.cand_hash = s.cand_hash AND t.prompt_hash = s.prompt_hash
                  WHEN NOT MATCHED THEN INSERT *""")  # noqa: F821
    bad = spark.table(NEW).filter("ai_error IS NOT NULL OR ai_choice IS NULL")  # noqa: F821
    nbad = bad.count()
    print(f"merged {n - nbad} new verdicts into {V}")
    if nbad:
        print(bad.select("ons_key", "nom_usina", "ai_choice", "ai_error").toPandas().to_string(index=False))
    assert nbad == 0, f"ai_decide returned no answer or an error for {nbad} of {n} new plants (see {NEW})"
dbutils.jobs.taskValues.set("new_verdicts", n)  # noqa: F821

# COMMAND ----------

# MAGIC %md ## Verdicts for today's candidates (what the pipeline applies)

# COMMAND ----------

print(spark.table(V).join(cands.select(*KEY), KEY, "left_semi").withColumn("ai_accepted", reco_ai.accepted())  # noqa: F821
      .groupBy("ai_choice", "ai_accepted")
      .agg(F.count("*").alias("ons_plants"), F.round(F.avg("ai_confidence"), 3).alias("mean_conf"),
           F.max("decided_at").alias("last_decided"))
      .orderBy("ai_choice", "ai_accepted").toPandas().to_string(index=False))
