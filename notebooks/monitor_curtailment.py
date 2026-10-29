# Databricks notebook source
# MAGIC %md
# MAGIC # Curtailment model — drift check (spec 18)
# MAGIC
# MAGIC Runs every refresh right after `score_curtailment`. On the trailing 3 months that carry ONS
# MAGIC constrained-off flags it checks the two promises behind the R$ headline, per technology, for the
# MAGIC `champion` that produced `ampera_gold.curtailment_hourly`:
# MAGIC - flag **precision ≥ 0.8** against ONS's own flags (the "at least" framing), and
# MAGIC - capacity-factor **MAE no worse than ONS's own estimate** on the hours ONS did not flag.
# MAGIC
# MAGIC Either broken → `drift = true`: the job retrains a `challenger` on everything before the window and
# MAGIC `promote_curtailment` promotes it only if it beats the champion on that window. Every check is appended
# MAGIC to `ampera_gold.curtailment_model_monitor`. The job parameter `force_drift=true` exercises the retrain and
# MAGIC promotion path when the data shows no drift (it is static in this demo).

# COMMAND ----------

import os
import sys
from datetime import datetime, timezone

from pyspark.sql import functions as F

sys.path.append(os.path.abspath("../src"))
import curtailment_lib as C  # noqa: E402  drift_reasons (tests/test_curtailment.py)
import curtailment_monitor as M  # noqa: E402

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("force_drift", "false")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
FORCE = dbutils.widgets.get("force_drift").lower() == "true"  # noqa: F821
MON = f"{CAT}.ampera_gold.curtailment_model_monitor"
spark.sql(f"""CREATE TABLE IF NOT EXISTS {MON} (
    checked_at TIMESTAMP, kind STRING, model_version INT, fonte STRING, window_from DATE, window_to DATE,
    precision DOUBLE, recall DOUBLE, mae_model DOUBLE, mae_ons DOUBLE, flagged BIGINT, labeled_hours BIGINT,
    drift BOOLEAN, decision STRING)
  COMMENT 'Gold (ML ops): every drift check (kind=check) and challenger comparison (kind=challenger / champion) of curtailment_expected_cf on the trailing labeled months. Spec 18.'""")  # noqa: F821

# COMMAND ----------

h = spark.table(f"{CAT}.ampera_gold.curtailment_hourly")  # noqa: F821
w_from, w_to = M.window(h)
version = h.agg(F.max("model_version")).first()[0]
m = M.metrics(h.filter(F.col("gen_date").between(w_from, w_to)))
now = datetime.now(timezone.utc)
rows, drift = [], FORCE
for fonte, x in sorted(m.items()):
    why = C.drift_reasons(x)
    drift = drift or bool(why)
    rows.append((now, "check", version, fonte, w_from, w_to, x["precision"], x["recall"], x["mae_model"], x["mae_ons"],
                 x["flagged"], x["labeled_hours"], bool(why), "; ".join(why) or "ok"))
    print(f"{fonte} v{version} {w_from}..{w_to}: precision {x['precision']} recall {x['recall']} "
          f"MAE {x['mae_model']} vs ONS {x['mae_ons']} -> {'; '.join(why) or 'ok'}")
if FORCE:
    print("force_drift=true: retraining a challenger regardless")
spark.createDataFrame(rows, spark.table(MON).schema).write.mode("append").saveAsTable(MON)  # noqa: F821
dbutils.jobs.taskValues.set("drift", "true" if drift else "false")  # noqa: F821
dbutils.jobs.taskValues.set("window_from", str(w_from))  # noqa: F821
print(f"drift = {drift}")
