# Databricks notebook source
# MAGIC %md
# MAGIC # Curtailment model — batch scoring (spec 11)
# MAGIC
# MAGIC Scores every wind/solar plant-hour in `ampera_gold.curtailment_features_hourly` with the UC model
# MAGIC `curtailment_expected_cf@champion`, flags curtailment (`expected CF >= 10%` and `actual < Y x expected`,
# MAGIC `Y` from the model version tags), values the lost energy at the hour's PLD and writes:
# MAGIC - `ampera_gold.curtailment_hourly` — lakehouse, for Genie and analysis
# MAGIC - `ampera_gold.curtailment_daily` — synced to Lakebase for the app
# MAGIC
# MAGIC Runs in the refresh job after the medallion and before the Lakebase syncs.

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=3.1" scikit-learn

# COMMAND ----------

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
FEAT = f"{CAT}.ampera_gold.curtailment_features_hourly"
MODEL = f"{CAT}.ampera_gold.curtailment_expected_cf"

# COMMAND ----------

import os
import sys

import mlflow
from mlflow import MlflowClient
from pyspark.sql import functions as F

sys.path.append(os.path.abspath("../src"))
import curtailment_lib as C  # noqa: E402  flag + valuation rules (tests/test_curtailment.py)

mlflow.set_registry_uri("databricks-uc")
mv = MlflowClient().get_model_version_by_alias(MODEL, "champion")
Y = {"EOL": float(mv.tags["y_eol"]), "SOL": float(mv.tags["y_sol"])}
MIN_CF = float(mv.tags["min_expected_cf"])
print(f"{MODEL} v{mv.version}  Y={Y}  min_expected_cf={MIN_CF}")
expected_cf = mlflow.pyfunc.spark_udf(spark, f"models:/{MODEL}@champion", result_type="double",  # noqa: F821
                                      env_manager="local")

# COMMAND ----------

cols = ["fonte", "plant_id", "uf", "hora", "mes", "vento_100m_ms", "irradiancia_wm2", "temp_c", "lat", "lon",
        "vento_ms_medido_ons", "irradiancia_wm2_medida_ons"]
f = spark.table(FEAT)  # noqa: F821
y = F.when(F.col("fonte") == "EOL", F.lit(Y["EOL"])).otherwise(F.lit(Y["SOL"]))
s = (f.withColumn("cf_esperado", expected_cf(*cols))
      .withColumn("mwh_esperado", F.col("cf_esperado") * F.col("capacity_mw"))
      .withColumn("restrito_modelo", C.flagged(F.col("cf_esperado"), F.col("fator_capacidade"), y, MIN_CF))
      .withColumn("mwh_restrito", F.when(F.col("restrito_modelo"), F.greatest(F.col("mwh_esperado") - F.col("mwh"), F.lit(0.0)))
                                   .otherwise(F.lit(0.0)))  # = C.lost_mwh
      .withColumn("valor_rs_perdido", C.value_rs(F.col("mwh_restrito"), F.col("pld_rs_mwh")))
      .select("ts", "gen_date", "plant_id", "nome", "uf", "submercado", "fonte", "conjunto_key", "capacity_mw",
              "mwh", "mwh_esperado", "restrito_modelo", "restrito_ons", "mwh_estimado_ons", "mwh_restrito",
              "pld_rs_mwh", "valor_rs_perdido", F.lit(int(mv.version)).alias("model_version")))
(s.write.mode("overwrite").option("overwriteSchema", "true")
  .clusterBy("gen_date", "plant_id").saveAsTable(f"{CAT}.ampera_gold.curtailment_hourly"))
spark.sql(f"""COMMENT ON TABLE {CAT}.ampera_gold.curtailment_hourly IS
  'Gold (ML): hourly expected vs actual MWh per wind/solar plant; restrito_modelo = model curtailment flag, restrito_ons = ONS flag; mwh_restrito valued at PLD (valor_rs_perdido). Spec 11.'""")

# COMMAND ----------

h = spark.table(f"{CAT}.ampera_gold.curtailment_hourly")  # noqa: F821
d = (h.groupBy(F.col("gen_date").alias("dia"), "plant_id")
      .agg(F.max("nome").alias("nome"), F.max("uf").alias("uf"), F.max("submercado").alias("submercado"),
           F.max("fonte").alias("fonte"), F.max("conjunto_key").alias("conjunto_key"),
           F.max("capacity_mw").alias("capacidade_mw"),
           F.sum("mwh").alias("mwh"), F.sum("mwh_esperado").alias("mwh_esperado"),
           F.sum(F.col("restrito_modelo").cast("int")).alias("horas_restritas_modelo"),
           F.sum(F.col("restrito_ons").cast("int")).alias("horas_restritas_ons"),
           F.sum("mwh_restrito").alias("mwh_restrito"), F.sum("valor_rs_perdido").alias("valor_rs_perdido")))
(d.write.mode("overwrite").option("overwriteSchema", "true")
  .option("delta.enableChangeDataFeed", "true")
  .clusterBy("dia", "plant_id").saveAsTable(f"{CAT}.ampera_gold.curtailment_daily"))
spark.sql(f"""COMMENT ON TABLE {CAT}.ampera_gold.curtailment_daily IS
  'Gold (ML): daily curtailment per wind/solar plant — expected vs actual MWh, curtailed hours (model and ONS), MWh and R$ lost at PLD. Synced to Lakebase. Spec 11.'""")
spark.sql(f"ALTER TABLE {CAT}.ampera_gold.curtailment_daily ALTER COLUMN dia SET NOT NULL")  # noqa: F821
spark.sql(f"ALTER TABLE {CAT}.ampera_gold.curtailment_daily ALTER COLUMN plant_id SET NOT NULL")  # noqa: F821

# COMMAND ----------

# MAGIC %md ## Results

# COMMAND ----------

def show(sql):
    print(spark.sql(sql).toPandas().to_string(index=False))  # noqa: F821


show(f"""SELECT fonte, count(DISTINCT plant_id) AS usinas, round(sum(mwh)/1e6, 2) AS geracao_twh,
           round(sum(mwh_restrito)/1e3, 1) AS restrito_gwh, round(sum(valor_rs_perdido)/1e6, 1) AS perdido_rs_milhoes,
           round(100*sum(mwh_restrito)/sum(mwh_esperado), 2) AS pct_do_esperado
    FROM {CAT}.ampera_gold.curtailment_daily GROUP BY fonte ORDER BY fonte""")
print("\nModel flag vs ONS flag, all labeled plant-hours (both periods):")
show(f"""SELECT fonte, restrito_ons, restrito_modelo, count(*) AS plant_hours
    FROM {CAT}.ampera_gold.curtailment_hourly WHERE restrito_ons IS NOT NULL
    GROUP BY ALL ORDER BY ALL""")
print("\nCoverage: plant-hours with no ONS curtailment flag (ONS's Oct-Dec 2024 solar files carry none) — the model still scores them:")
show(f"""SELECT fonte, count_if(restrito_ons IS NULL) AS sem_rotulo_ons, count(*) AS total,
           round(sum(CASE WHEN restrito_ons IS NULL THEN mwh_restrito END)/1e3, 1) AS restrito_gwh_sem_rotulo
    FROM {CAT}.ampera_gold.curtailment_hourly GROUP BY fonte ORDER BY fonte""")
print("\nTop 10 plants by R$ lost:")
show(f"""SELECT plant_id, max(nome) AS nome, max(uf) AS uf, max(fonte) AS fonte,
           round(sum(mwh_restrito)/1e3, 1) AS restrito_gwh, round(sum(valor_rs_perdido)/1e6, 2) AS perdido_rs_milhoes
    FROM {CAT}.ampera_gold.curtailment_daily GROUP BY plant_id ORDER BY perdido_rs_milhoes DESC LIMIT 10""")
