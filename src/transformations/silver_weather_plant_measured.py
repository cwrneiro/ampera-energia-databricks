# Silver: weather measured AT the plant by ONS (wind/solar complex members, from the curtailment
# detail), hourly. ONS-flagged invalid readings are dropped. This is the drill-down layer; INMET
# fills in only where a plant has no ONS data (decision #18). Spec: specs/03-gold-marts.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
import reco_sql as S


def _hourly(table, value_col, flag_col, out_col):
    d = spark.read.table(table)  # noqa: F821
    return (d.filter(F.coalesce(F.col(flag_col), F.lit(0)) == 0)
             .select(F.coalesce(S.ceg_norm_col("ceg"), F.concat(F.lit("SURR-M-"), F.trim("id_ons"))).alias("plant_id"),
                     F.date_trunc("hour", "din_instante").alias("ts"),  # 30-min t covers [t, t+30m)
                     F.col(value_col).alias(out_col))
             .groupBy("plant_id", "ts").agg(F.avg(out_col).alias(out_col)))


@dp.materialized_view(
    name="silver.weather_plant_measured",
    comment="Silver: hourly wind speed / irradiance measured at the plant by ONS (complex members), invalid readings dropped.",
    cluster_by=["plant_id"],
)
def weather_plant_measured():
    wind = _hourly("bronze.ons_member_generation_wind",
                   "val_ventoverificado", "flg_dadoventoinvalido", "vento_ms")
    solar = _hourly("bronze.ons_member_generation_solar",
                    "val_irradianciaverificado", "flg_dadoirradianciainvalido", "irradiancia_wm2")
    return (wind.join(solar, ["plant_id", "ts"], "full")
                .withColumn("fonte_medicao", F.lit("ONS")))
