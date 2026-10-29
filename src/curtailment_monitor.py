"""Spark side of the drift check (spec 18), shared by notebooks/monitor_curtailment and
notebooks/promote_curtailment. The decisions themselves (drift_reasons, beats) are pure and live in
curtailment_lib, tested by tests/test_curtailment.py.

The monitor window is the trailing MONITOR_MONTHS months that carry ONS constrained-off flags. Metrics
match train_curtailment: flag precision / recall against ONS on labeled hours, and capacity-factor MAE
on the hours ONS did not flag, next to the MAE of ONS's own estimate.
"""
from pyspark.sql import functions as F

import curtailment_lib as C

FEATURES = ["fonte", "plant_id", "uf", "hora", "mes", "vento_100m_ms", "irradiancia_wm2", "temp_c", "lat", "lon",
            "vento_ms_medido_ons", "irradiancia_wm2_medida_ons"]


def window(df):
    """(first day, last day) of the trailing labeled months in df (needs gen_date, restrito_ons)."""
    last = df.filter("restrito_ons IS NOT NULL").agg(F.max("gen_date")).first()[0]
    first = df.select(F.add_months(F.trunc(F.lit(last), "month"), 1 - C.MONITOR_MONTHS)).first()[0]
    return first, last


def metrics(scored):
    """{fonte: {precision, recall, mae_model, mae_ons, flagged, labeled_hours}} on labeled plant-hours.

    scored needs: fonte, mwh, mwh_esperado, capacity_mw, restrito_ons, restrito_modelo, mwh_estimado_ons.
    """
    cf = lambda c: F.least(F.greatest(F.col(c) / F.col("capacity_mw"), F.lit(0.0)), F.lit(1.2))  # noqa: E731
    free = ~F.col("restrito_ons")
    rows = (scored.filter("restrito_ons IS NOT NULL AND capacity_mw > 0").groupBy("fonte").agg(
        F.count("*").alias("labeled_hours"),
        F.count_if(F.col("restrito_modelo")).alias("flagged"),
        F.try_divide(F.count_if(F.col("restrito_modelo") & F.col("restrito_ons")),
                     F.count_if(F.col("restrito_modelo"))).alias("precision"),
        F.try_divide(F.count_if(F.col("restrito_modelo") & F.col("restrito_ons")),
                     F.count_if(F.col("restrito_ons"))).alias("recall"),
        F.avg(F.when(free, F.abs(cf("mwh") - cf("mwh_esperado")))).alias("mae_model"),
        F.avg(F.when(free & F.col("mwh_estimado_ons").isNotNull(),
                     F.abs(cf("mwh") - cf("mwh_estimado_ons")))).alias("mae_ons")).collect())
    rnd = lambda x: None if x is None else round(float(x), 4)  # noqa: E731
    return {r.fonte: {"precision": rnd(r.precision), "recall": rnd(r.recall), "mae_model": rnd(r.mae_model),
                      "mae_ons": rnd(r.mae_ons), "flagged": r.flagged, "labeled_hours": r.labeled_hours}
            for r in rows}


def score(spark, df, model, alias):
    """df scored by model@alias with that version's frozen Y (as score_curtailment does), plus its version."""
    import mlflow  # only promote_curtailment scores (it pip-installs mlflow); the monitor needs no mlflow
    mv = mlflow.MlflowClient().get_model_version_by_alias(model, alias)
    y = F.when(F.col("fonte") == "EOL", F.lit(float(mv.tags["y_eol"]))).otherwise(F.lit(float(mv.tags["y_sol"])))
    udf = mlflow.pyfunc.spark_udf(spark, f"models:/{model}@{alias}", result_type="double", env_manager="local")
    s = (df.withColumn("cf_esperado", udf(*FEATURES))
           .withColumn("mwh_esperado", F.col("cf_esperado") * F.col("capacity_mw"))
           .withColumn("restrito_modelo", C.flagged(F.col("cf_esperado"), F.col("fator_capacidade"), y,
                                                    float(mv.tags["min_expected_cf"]))))
    return s, int(mv.version)
