# Databricks notebook source
# MAGIC %md
# MAGIC # ai_decide reconciliation — blind evaluation (spec 12)
# MAGIC
# MAGIC The pipeline asks `ai_decide` to place ONS plants whose CEG doesn't link to SIGA. To measure how far
# MAGIC to trust it, we replay the same question on plants whose answer we **know**: ONS plants that *do* match
# MAGIC SIGA by CEG. The CEG registry number is hidden (so `mesmo_numero_ceg` is unknown); the model sees names, name
# MAGIC similarity, UF, plant type, municipality and capacity,
# MAGIC with the same top-3 candidate builder as the pipeline (`reco_ai.candidates`). The true plant may be
# MAGIC A, B, C, or absent (then the right answer is `nenhum`).
# MAGIC
# MAGIC Outputs: accuracy, accuracy and coverage at the accept cutoff (`AI_CUTOFF`), and a calibration table.

# COMMAND ----------

import os
import sys

sys.path.append(os.path.abspath("../src/transformations"))
import reco_ai  # noqa: E402
import reco_lib as R  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("n", "200")  # noqa: F821
CAT, N = dbutils.widgets.get("catalog"), int(dbutils.widgets.get("n"))  # noqa: F821
print(f"catalog={CAT}  sample={N}  AI_CUTOFF={R.AI_CUTOFF}")

# COMMAND ----------

ons = spark.table(f"{CAT}.ampera_silver.ons_plant").filter("ons_grain = 'plant'")  # noqa: F821
siga = spark.table(f"{CAT}.ampera_silver.siga_plant")  # noqa: F821
known = (ons.join(siga.select(F.col("plant_id").alias("ceg_norm")), "ceg_norm", "left_semi")
            .withColumn("truth_id", F.col("ceg_norm"))
            .orderBy(F.xxhash64("ons_key")).limit(N)
            # blind: keep only the CEG's type prefix (UTE, EOL...), hide the registry number that gives the answer away
            .withColumn("ceg_raw", F.split("ceg_raw", "[.]")[0]))
c = reco_ai.candidates(known, siga).join(known.select("ons_key", "truth_id"), "ons_key")
truth = (F.when(F.col("a_id") == F.col("truth_id"), "A").when(F.col("b_id") == F.col("truth_id"), "B")
          .when(F.col("c_id") == F.col("truth_id"), "C").otherwise("nenhum"))
# Serverless has no .cache(): persist once so every metric reads the same ai_decide answers.
EVAL = f"{CAT}.ampera_silver.ai_decide_eval"
reco_ai.decide(c.withColumn("truth", truth)).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(EVAL)
spark.sql(f"COMMENT ON TABLE {EVAL} IS 'Silver (GenAI eval): blind ai_decide answers on CEG-matched ONS plants with the CEG hidden. Spec 12.'")  # noqa: F821
res = spark.table(EVAL)  # noqa: F821
print(f"{res.count()} plants scored -> {EVAL}")

# COMMAND ----------

def show(df):
    print(df.toPandas().to_string(index=False))


ok = F.col("ai_choice") == F.col("truth")
print("Truth distribution (where the real plant sits among the candidates):")
show(res.groupBy("truth").count().orderBy("truth"))
print("\nOverall:")
show(res.agg(F.count("*").alias("n"), F.round(F.avg(ok.cast("double")), 3).alias("accuracy"),
             F.count_if(F.col("ai_error").isNotNull()).alias("errors")))
print(f"\nAt the accept cutoff (confidence >= {R.AI_CUTOFF}, choice != nenhum) — what the pipeline would auto-apply:")
acc = res.filter("ai_accepted")
show(acc.agg(F.count("*").alias("auto_applied"),
             F.round(F.count("*") / F.lit(res.filter("truth != 'nenhum'").count()), 3).alias("coverage_of_matchable"),
             F.round(F.avg(ok.cast("double")), 3).alias("precision")))

# COMMAND ----------

# MAGIC %md ## Calibration: does confidence mean what it says?

# COMMAND ----------

b = F.least(F.floor(F.col("ai_confidence") * 10) / 10, F.lit(0.9))
show(res.groupBy(b.alias("confidence_from"))
        .agg(F.count("*").alias("n"), F.round(F.avg("ai_confidence"), 3).alias("mean_confidence"),
             F.round(F.avg(ok.cast("double")), 3).alias("accuracy"))
        .orderBy("confidence_from"))
print("\nConfusion (truth x choice):")
show(res.groupBy("truth").pivot("ai_choice", ["A", "B", "C", "nenhum"]).count().orderBy("truth"))

# COMMAND ----------

# MAGIC %md ## Examples: wrong answers (what the model got confused by)

# COMMAND ----------

show(res.filter(~ok).select("nom_usina", "uf", "truth", "ai_choice", F.round("ai_confidence", 2).alias("conf"),
                            "a_nome", "b_nome", "c_nome").limit(15))

# COMMAND ----------

# MAGIC %md ## Production run: what the pipeline decided (`ampera_silver.plant_match_ai`)

# COMMAND ----------

show(spark.sql(f"""SELECT ai_choice, ai_accepted, count(*) AS ons_plants, round(avg(ai_confidence), 3) AS mean_conf
                   FROM {CAT}.ampera_silver.plant_match_ai GROUP BY ALL ORDER BY ALL"""))
show(spark.sql(f"""SELECT match_method, count(*) AS ons_series FROM {CAT}.ampera_silver.plant_match
                   GROUP BY ALL ORDER BY ons_series DESC"""))
