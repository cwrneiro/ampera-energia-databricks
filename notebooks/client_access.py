# Databricks notebook source
# MAGIC %md
# MAGIC # Client access model (spec 17)
# MAGIC
# MAGIC Ampera's generator clients may see **only their own plants**, in the app and in the Genie space.
# MAGIC - Portfolios (which plants each fictional client holds) are the committed seed `src/seed/client_portfolio.csv`
# MAGIC   (real plant ids, picked by SIGA owner name).
# MAGIC - Principals (which users / service principals act for each client) are workspace-specific, so they come
# MAGIC   from the `client_access` job parameter (JSON `{"cliente": ["principal", ...]}`, set in the gitignored
# MAGIC   bundle overlay), never from the repo.
# MAGIC - Writes `ampera_gold.client_plant_access` (principal x plant), the table the UC row filter
# MAGIC   `ampera_gold.client_plant_filter` reads, and its unfiltered twin `ampera_serving.client_plant_access`, synced to
# MAGIC   Lakebase so the app applies the same mapping to its Postgres reads.

# COMMAND ----------

import json
import os

import pandas as pd
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("client_access", "{}")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
ACCESS = json.loads(dbutils.widgets.get("client_access") or "{}")  # noqa: F821

seed = pd.read_csv(os.path.abspath("../src/seed/client_portfolio.csv"), dtype=str)
unknown = set(ACCESS) - set(seed["cliente"])
assert not unknown, f"client_access names clients with no portfolio in the seed: {sorted(unknown)}"
print(seed.groupby(["cliente", "fonte", "uf"]).size().to_string())

# COMMAND ----------

rows = [(p, c, pid) for c, principals in ACCESS.items() for p in principals
        for pid in seed.loc[seed["cliente"] == c, "plant_id"]]
access = spark.createDataFrame(rows, "principal STRING, cliente STRING, plant_id STRING")  # noqa: F821
known = spark.table(f"{CAT}.ampera_serving.plant_location").select("plant_id")  # noqa: F821
missing = access.join(known, "plant_id", "left_anti").select("plant_id").distinct().count()
assert missing == 0, f"{missing} seed plant ids are not in plant_location (seed out of date?)"

access.createOrReplaceTempView("access_new")
spark.sql(f"INSERT OVERWRITE {CAT}.ampera_gold.client_plant_access SELECT principal, cliente, plant_id FROM access_new")  # noqa: F821
(spark.table(f"{CAT}.ampera_gold.client_plant_access")  # noqa: F821
      .write.mode("overwrite").option("overwriteSchema", "true").option("delta.enableChangeDataFeed", "true")
      .saveAsTable(f"{CAT}.ampera_serving.client_plant_access"))
spark.sql(f"""COMMENT ON TABLE {CAT}.ampera_serving.client_plant_access IS
  'Serving: copy of ampera_gold.client_plant_access, synced to Lakebase so the app filters client users the same way as the UC row filter. Spec 17.'""")  # noqa: F821
for c in ("principal", "plant_id"):
    spark.sql(f"ALTER TABLE {CAT}.ampera_serving.client_plant_access ALTER COLUMN {c} SET NOT NULL")  # noqa: F821

# COMMAND ----------

print(spark.table(f"{CAT}.ampera_gold.client_plant_access")  # noqa: F821
      .groupBy("cliente").agg(F.countDistinct("principal").alias("principals"), F.countDistinct("plant_id").alias("plants"))
      .orderBy("cliente").toPandas().to_string(index=False))
