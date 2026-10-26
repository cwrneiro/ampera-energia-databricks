# Databricks notebook source
# MAGIC %md
# MAGIC # Curtailment model — training (spec 11)
# MAGIC
# MAGIC **Problem.** Brazilian wind and solar plants are increasingly *curtailed* (ONS orders them to cut
# MAGIC output for grid/energy reasons). Ampera wants to know how much energy — and how many R$ at PLD —
# MAGIC is lost, per plant, including plants ONS doesn't publish curtailment for.
# MAGIC
# MAGIC **Approach.** Learn each technology's *unconstrained* capacity factor from weather, then flag hours
# MAGIC where actual output falls far below that expectation.
# MAGIC - Data: `ampera_gold.curtailment_features_hourly` (pipeline output; Open-Meteo weather, SIGA capacity, ONS label).
# MAGIC - Train only on hours ONS did **not** flag as constrained (`restrito_ons = false`), first 18 months.
# MAGIC - Test on the last 6 months: regression error vs ONS's own estimate, then tune the flag ratio `Y`
# MAGIC   against ONS's constrained-off flags: best recall with precision >= 0.8, so the R$ figure is a
# MAGIC   conservative "at least". `Y` is stored with the model version.
# MAGIC - One `HistGradientBoostingRegressor` per technology (EOL, SOL), wrapped in one MLflow pyfunc and
# MAGIC   registered in Unity Catalog with alias `champion`.

# COMMAND ----------

# MAGIC %pip install -q "mlflow>=3.1" scikit-learn

# COMMAND ----------

dbutils.widgets.text("catalog", "ampera_catalog")  # noqa: F821
CAT = dbutils.widgets.get("catalog")  # noqa: F821
FEAT = f"{CAT}.ampera_gold.curtailment_features_hourly"
MODEL = f"{CAT}.ampera_gold.curtailment_expected_cf"
SPLIT = "2026-04-01"        # train < SPLIT <= test (18 / 6 months)
SAMPLE_ROWS = 1_500_000     # per technology, training sample cap (driver memory)
print(FEAT, MODEL)

# COMMAND ----------

import os
import sys

import mlflow
import sklearn
import numpy as np
import pandas as pd
from pyspark.sql import functions as F
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, precision_recall_fscore_support

sys.path.append(os.path.abspath("../src"))
import curtailment_lib as C  # noqa: E402  flag rule, Y selection (tests/test_curtailment.py)

MIN_EXPECTED_CF, PRECISION_FLOOR = C.MIN_EXPECTED_CF, C.PRECISION_FLOOR
mlflow.set_registry_uri("databricks-uc")
UFS = sorted(r.uf for r in spark.table(FEAT).select("uf").distinct().collect())  # noqa: F821
WEATHER = {"EOL": "vento_100m_ms", "SOL": "irradiancia_wm2"}                       # Open-Meteo, every plant
MEASURED = {"EOL": "vento_ms_medido_ons", "SOL": "irradiancia_wm2_medida_ons"}      # ONS at the plant, NaN elsewhere


def features(pdf, fonte, plant_cf, ufs):
    """Model inputs for one technology. plant_cf = per-plant mean unconstrained CF (train set)."""
    fb = np.nanmedian(list(plant_cf.values())) if plant_cf else 0.3
    return pd.DataFrame({
        "weather": pdf[WEATHER[fonte]].astype(float),
        "weather_measured": pdf[MEASURED[fonte]].astype(float),
        "hora": pdf["hora"].astype(int), "mes": pdf["mes"].astype(int),
        "temp_c": pdf["temp_c"].astype(float),
        "lat": pdf["lat"].astype(float), "lon": pdf["lon"].astype(float),
        "uf": pd.Categorical(pdf["uf"], categories=ufs).codes,
        "plant_cf": pdf["plant_id"].map(plant_cf).fillna(fb).astype(float),
    })

# COMMAND ----------

# MAGIC %md ## Data: labeled plant-hours

# COMMAND ----------

df = spark.table(FEAT).filter("restrito_ons IS NOT NULL")  # noqa: F821
print(df.groupBy("fonte", (F.col("gen_date") >= SPLIT).alias("is_test"), "restrito_ons")
      .agg(F.count("*").alias("plant_hours"), F.countDistinct("plant_id").alias("plants"),
           F.round(F.sum("mwh") / 1e6, 2).alias("twh")).orderBy("fonte", "is_test", "restrito_ons")
      .toPandas().to_string(index=False))

# COMMAND ----------

models, plant_cfs, report = {}, {}, []
for fonte in ["EOL", "SOL"]:
    base = df.filter(F.col("fonte") == fonte)
    tr = base.filter((F.col("gen_date") < SPLIT) & ~F.col("restrito_ons"))
    n = tr.count()
    tr_pd = tr.sample(fraction=min(1.0, SAMPLE_ROWS / max(n, 1)), seed=7).toPandas()
    plant_cf = tr_pd.groupby("plant_id")["fator_capacidade"].mean().clip(0, 1.2).to_dict()
    X, y = features(tr_pd, fonte, plant_cf, UFS), tr_pd["fator_capacidade"].clip(0, 1.2)
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
                                      categorical_features=[X.columns.get_loc("uf")], random_state=7)
    m.fit(X, y)
    models[fonte], plant_cfs[fonte] = m, plant_cf
    print(f"{fonte}: trained on {len(tr_pd):,} of {n:,} unconstrained train plant-hours, {len(plant_cf)} plants")

# COMMAND ----------

# MAGIC %md ## Test (last 6 months): regression error vs ONS's own estimate

# COMMAND ----------

test = {}
for fonte in ["EOL", "SOL"]:
    te_all = df.filter((F.col("fonte") == fonte) & (F.col("gen_date") >= SPLIT))
    nt = te_all.count()
    te = te_all.sample(fraction=min(1.0, SAMPLE_ROWS / max(nt, 1)), seed=11).toPandas()  # driver memory cap
    te["restrito_ons"] = te["restrito_ons"].astype(bool)
    te["cf_esperado"] = np.clip(models[fonte].predict(features(te, fonte, plant_cfs[fonte], UFS)), 0, 1.2)
    te["cf_ons"] = te["mwh_estimado_ons"] / te["capacity_mw"]
    test[fonte] = te
    un = te[~te["restrito_ons"]]
    ons = un.dropna(subset=["cf_ons"])
    report.append({"fonte": fonte, "test_plant_hours": nt, "test_sample": len(te), "unconstrained": len(un),
                   "mae_cf_model": round(mean_absolute_error(un["fator_capacidade"].clip(0, 1.2), un["cf_esperado"]), 4),
                   "mae_cf_ons_estimate": round(mean_absolute_error(ons["fator_capacidade"].clip(0, 1.2), ons["cf_ons"].clip(0, 1.2)), 4),
                   "mean_cf_actual": round(un["fator_capacidade"].mean(), 4)})
print(pd.DataFrame(report).to_string(index=False))

# COMMAND ----------

# MAGIC %md ## Tune the flag ratio Y against ONS constrained-off flags
# MAGIC Flag an hour when `expected CF >= 10%` and `actual < Y x expected`. Pick the Y with the best recall
# MAGIC whose precision is >= 0.8 (ONS flags ~40% of hours, so F1 alone rewards flagging every shortfall).

# COMMAND ----------

grid = np.round(np.arange(0.30, 1.0001, 0.05), 2)
rows = []
for fonte, te in test.items():
    judge = te[te["cf_esperado"] >= MIN_EXPECTED_CF]
    for Y in grid:
        pred = C.flagged(judge["cf_esperado"], judge["fator_capacidade"], Y)
        p, r, f1, _ = precision_recall_fscore_support(judge["restrito_ons"], pred, average="binary", zero_division=0)
        rows.append({"fonte": fonte, "Y": Y, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)})
tune = pd.DataFrame(rows)

best = pd.DataFrame([C.choose_y(t.to_dict("records")) for _, t in tune.groupby("fonte")]).set_index("fonte")
print(tune.pivot(index="Y", columns="fonte", values=["precision", "recall", "f1"]).to_string())
print("\nchosen:\n", best.to_string())
Y_BY_FONTE = best["Y"].to_dict()

# COMMAND ----------

# MAGIC %md ## Register in Unity Catalog

# COMMAND ----------


class ExpectedCF(mlflow.pyfunc.PythonModel):
    """Expected unconstrained capacity factor for wind (EOL) and solar (SOL) plant-hours."""

    def __init__(self, models, plant_cfs, ufs):
        self.models, self.plant_cfs, self.ufs = models, plant_cfs, ufs

    def predict(self, context, model_input):
        df = model_input
        out = pd.Series(np.nan, index=df.index)
        for fonte, m in self.models.items():
            idx = df["fonte"] == fonte
            if idx.any():
                out[idx] = np.clip(m.predict(features(df[idx], fonte, self.plant_cfs[fonte], self.ufs)), 0, 1.2)
        return out


cols = ["fonte", "plant_id", "uf", "hora", "mes", "vento_100m_ms", "irradiancia_wm2", "temp_c", "lat", "lon",
        "vento_ms_medido_ons", "irradiancia_wm2_medida_ons"]
example = pd.concat([test["EOL"][cols].head(3), test["SOL"][cols].head(3)], ignore_index=True)
model = ExpectedCF(models, plant_cfs, UFS)
with mlflow.start_run(run_name="curtailment_expected_cf") as run:
    mlflow.log_params({"split": SPLIT, "min_expected_cf": MIN_EXPECTED_CF, "sample_rows": SAMPLE_ROWS,
                       "precision_floor": PRECISION_FLOOR,
                       "y_eol": Y_BY_FONTE["EOL"], "y_sol": Y_BY_FONTE["SOL"]})
    for r in report:
        mlflow.log_metrics({f"{r['fonte']}_mae_cf_model": r["mae_cf_model"],
                            f"{r['fonte']}_mae_cf_ons_estimate": r["mae_cf_ons_estimate"]})
    for fonte, b in best.iterrows():
        mlflow.log_metrics({f"{fonte}_precision": b["precision"], f"{fonte}_recall": b["recall"], f"{fonte}_f1": b["f1"]})
    info = mlflow.pyfunc.log_model(name="model", python_model=model, input_example=example,
                                   registered_model_name=MODEL,
                                   pip_requirements=[f"scikit-learn=={sklearn.__version__}", "pandas", "numpy"])

from mlflow import MlflowClient  # noqa: E402

c = MlflowClient()
v = info.registered_model_version
for k, val in {"y_eol": Y_BY_FONTE["EOL"], "y_sol": Y_BY_FONTE["SOL"], "min_expected_cf": MIN_EXPECTED_CF}.items():
    c.set_model_version_tag(MODEL, v, k, str(val))
c.set_registered_model_alias(MODEL, "champion", v)
c.update_registered_model(MODEL, description="Expected unconstrained capacity factor (wind/solar) from Open-Meteo weather; "
                          "flags curtailment where actual < Y x expected. Spec 11. Trained by notebooks/train_curtailment.")
print(f"registered {MODEL} v{v} as champion; run {run.info.run_id}; Y={Y_BY_FONTE}")
