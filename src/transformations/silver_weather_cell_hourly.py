# Silver: Open-Meteo hourly weather per 0.25° cell, in local Brasília time (same clock as ONS).
# Radiation is Open-Meteo's mean over the PRECEDING hour, so the value stamped t+1 belongs to ONS
# hour [t, t+1) and is shifted back one hour; wind/temperature are instantaneous at t.
# Spec: specs/03-gold-marts.md (decision #18)
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window


@dp.materialized_view(
    name="silver.weather_cell_hourly",
    comment="Silver: hourly Open-Meteo (ERA5) weather per 0.25° plant cell, local time; radiation aligned to ONS hours.",
    cluster_by=["cell_lat", "cell_lon"],
)
@dp.expect("has_values", "temp_c IS NOT NULL")
def weather_cell_hourly():
    b = spark.read.table("bronze.open_meteo_weather")  # noqa: F821
    h = (b.withColumn("cell_lat", F.regexp_extract("_source_file", r"cell_(-?[0-9.]+)_", 1).cast("double"))
          .withColumn("cell_lon", F.regexp_extract("_source_file", r"_(-?[0-9.]+)\.json$", 1).cast("double"))
          .withColumn("r", F.explode(F.arrays_zip(
              F.col("hourly.time").alias("t"),
              F.col("hourly.temperature_2m").alias("temp_c"),
              F.col("hourly.wind_speed_100m").alias("vento_100m_ms"),
              F.col("hourly.shortwave_radiation").alias("rad_prev_hour"),
              F.col("hourly.precipitation").alias("precip_mm"))))
          .select("cell_lat", "cell_lon",
                  F.to_timestamp("r.t", "yyyy-MM-dd'T'HH:mm").alias("ts"),
                  "r.temp_c", "r.vento_100m_ms", "r.rad_prev_hour", "r.precip_mm")
          .dropDuplicates(["cell_lat", "cell_lon", "ts"]))
    w = Window.partitionBy("cell_lat", "cell_lon").orderBy("ts")
    nxt_is_next_hour = F.lead("ts").over(w) == F.col("ts") + F.expr("INTERVAL 1 HOUR")  # months may be missing
    return (h.withColumn("irradiancia_wm2", F.when(nxt_is_next_hour, F.lead("rad_prev_hour").over(w)))
             .drop("rad_prev_hour"))
