# Databricks notebook source
# MAGIC %md
# MAGIC # Curtailment model — challenger vs champion (spec 18)
# MAGIC
# MAGIC Runs only after the drift check retrained a `challenger` (trained on everything before the monitor
# MAGIC window, its Y tuned on the window). Scores every labeled plant-hour with both versions and promotes
# MAGIC the challenger to `champion` only if, **for every technology**, on the window it keeps flag precision
# MAGIC ≥ 0.8 and has a lower capacity-factor MAE than the champion, **and** over all labeled months it does not
# MAGIC lose flag precision (`curtailment_lib.beats`). Otherwise the champion stays. Both results (window and
# MAGIC all months) and the decision are appended to `ampera_gold.curtailment_model_monitor`; `promoted` is
# MAGIC published so the job re-scores only when the champion changed.

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=3.1" scikit-learn

# COMMAND ----------

import os
import sys
from datetime import date, datetime, timezone

import mlflow
from mlflow import MlflowClient
from pyspark.sql import functions as F

sys.path.append(os.path.abspath("../src"))
import curtailment_lib as C  # noqa: E402  beats (tests/test_curtailment.py)
import curtailment_monitor as M  # noqa: E402

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
dbutils.widgets.text("window_from", "")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
MODEL = f"{CAT}.ampera_gold.curtailment_expected_cf"
MON = f"{CAT}.ampera_gold.curtailment_model_monitor"
mlflow.set_registry_uri("databricks-uc")

feat = spark.table(f"{CAT}.ampera_gold.curtailment_features_hourly")  # noqa: F821
w_from = date.fromisoformat(dbutils.widgets.get("window_from"))  # noqa: F821
w_to = M.window(feat)[1]
labeled = feat.filter(F.col("restrito_ons").isNotNull())
in_win = F.col("gen_date").between(w_from, w_to)

# COMMAND ----------

res, hist, ver = {}, {}, {}
for alias in ("champion", "challenger"):
    scored, ver[alias] = M.score(spark, labeled, MODEL, alias)  # noqa: F821
    res[alias], hist[alias] = M.metrics(scored.filter(in_win)), M.metrics(scored)
    for f in res[alias]:
        res[alias][f]["precision_all"] = hist[alias][f]["precision"]
    print(f"{alias} v{ver[alias]}: window {res[alias]}\n  all labeled months {hist[alias]}")

wins = {f: C.beats(res["challenger"][f], res["champion"][f]) for f in res["champion"]}
promote = all(wins.values()) and ver["challenger"] != ver["champion"]
decision = (f"promoted v{ver['challenger']} over v{ver['champion']}" if promote
            else f"kept v{ver['champion']}: challenger v{ver['challenger']} wins {wins}")
c = MlflowClient()
if promote:
    c.set_registered_model_alias(MODEL, "champion", ver["challenger"])
    c.set_model_version_tag(MODEL, ver["challenger"], "promoted_by", f"drift check, window {w_from}..{w_to}")
c.delete_registered_model_alias(MODEL, "challenger")
print(decision)

now = datetime.now(timezone.utc)
h_from = labeled.agg(F.min("gen_date")).first()[0]
rows = [(now, kind, ver[alias], f, frm, w_to, x["precision"], x["recall"], x["mae_model"], x["mae_ons"],
         x["flagged"], x["labeled_hours"], None, decision)
        for alias in ("champion", "challenger")
        for kind, frm, src in ((alias, w_from, res[alias]), (f"{alias}_history", h_from, hist[alias]))
        for f, x in sorted(src.items())]
spark.createDataFrame(rows, spark.table(MON).schema).write.mode("append").saveAsTable(MON)  # noqa: F821
dbutils.jobs.taskValues.set("promoted", "true" if promote else "false")  # noqa: F821
