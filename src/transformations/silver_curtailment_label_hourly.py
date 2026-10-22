# Silver: ONS's own curtailment record per plant-hour, from the constrained-off detail already in
# bronze. flg_geracaorestrita = 1 when ONS limited the plant's output that half-hour (the label the
# curtailment model is checked against); val_geracaoestimada = ONS's estimate of what the plant could
# have produced (a benchmark for our model). Spec: specs/11-ml-curtailment.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
import reco_sql as S


def _hourly(table, fonte):
    d = spark.read.table(table)  # noqa: F821
    return (d.select(F.coalesce(S.ceg_norm_col("ceg"), F.concat(F.lit("SURR-M-"), F.trim("id_ons"))).alias("plant_id"),
                     F.date_trunc("hour", "din_instante").alias("ts"),  # 30-min t covers [t, t+30m)
                     "flg_geracaorestrita", "val_geracaoestimada")
             .groupBy("plant_id", "ts")
             .agg(F.max("flg_geracaorestrita").cast("boolean").alias("restrito_ons"),
                  F.avg("val_geracaoestimada").alias("mwh_estimado_ons"))
             .withColumn("fonte", F.lit(fonte)))


@dp.materialized_view(
    name="ampera_silver.curtailment_label_hourly",
    comment="Silver: ONS constrained-off flag (restrito_ons) and ONS estimated MWh per wind/solar plant-hour.",
    cluster_by=["plant_id", "ts"],
)
@dp.expect("has_flag", "restrito_ons IS NOT NULL")
def curtailment_label_hourly():
    return (_hourly("ampera_bronze.ons_member_generation_wind", "EOL")
            .unionByName(_hourly("ampera_bronze.ons_member_generation_solar", "SOL")))
