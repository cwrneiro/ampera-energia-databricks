# Silver: INMET station hourly weather (local Brasília time) + the plant -> nearest-station map used
# only for plants with NO ONS at-plant data (decision #18). Spec: specs/03-gold-marts.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window

MAX_KM = 50  # decision #18: use a station only if it is within 50 km of the plant


def _num(c):  # comma decimals; -9999 = missing
    v = F.regexp_replace(F.trim(F.col(c)), ",", ".").cast("double")
    return F.when(v <= -9999, None).otherwise(v)


def _stations():
    b = spark.read.table("bronze.inmet_weather")  # noqa: F821
    keys = ["CODIGO (WMO):", "LATITUDE:", "LONGITUDE:", "ESTACAO:", "UF:"]
    meta = (b.filter(F.col("_c0").isin(*keys))
             .groupBy("_source_file").pivot("_c0", keys).agg(F.first("_c1")))
    return meta.select("_source_file",
                       F.trim(F.col("`CODIGO (WMO):`")).alias("station"),
                       F.trim(F.col("`ESTACAO:`")).alias("station_name"),
                       F.trim(F.col("`UF:`")).alias("station_uf"),
                       _num("`LATITUDE:`").alias("st_lat"),
                       _num("`LONGITUDE:`").alias("st_lon"))


@dp.materialized_view(
    name="silver.weather_inmet_hourly",
    comment="Silver: INMET hourly weather per station, local time; radiation kJ/m² -> W/m², aligned to ONS hours.",
    cluster_by=["station"],
)
def weather_inmet_hourly():
    b = spark.read.table("bronze.inmet_weather")  # noqa: F821
    rows = (b.filter(F.col("_c0").rlike(r"^\d{4}/\d{2}/\d{2}$"))
             .select("_source_file",
                     # Hora UTC "HHMM UTC" -> local = UTC-3 (Brasília, no DST since 2019)
                     (F.to_timestamp(F.concat_ws(" ", "_c0", F.substring("_c1", 1, 4)), "yyyy/MM/dd HHmm")
                      - F.expr("INTERVAL 3 HOURS")).alias("ts"),
                     _num("_c2").alias("precip_mm"),
                     (_num("_c6") / 3.6).alias("rad_prev_hour"),  # kJ/m² over the hour -> mean W/m²
                     _num("_c7").alias("temp_c"),
                     _num("_c18").alias("vento_10m_ms")))
    st = _stations()
    h = rows.join(st, "_source_file").drop("_source_file").dropDuplicates(["station", "ts"])
    # Like Open-Meteo, radiation stamped t+1 is the mean over [t, t+1) -> shift to ONS hour t.
    w = Window.partitionBy("station").orderBy("ts")
    nxt_is_next_hour = F.lead("ts").over(w) == F.col("ts") + F.expr("INTERVAL 1 HOUR")  # stations have gaps
    r = F.lead("rad_prev_hour").over(w)
    # Missing stays NULL (greatest() would turn NULL into 0); small negatives at night -> 0; values
    # above 1,400 W/m² (beyond top-of-atmosphere ~1,361) are sensor errors -> NULL.
    clean = F.when(r.isNull() | (r > 1400), None).otherwise(F.greatest(r, F.lit(0.0)))
    return (h.withColumn("irradiancia_wm2", F.when(nxt_is_next_hour, clean))
             .drop("rad_prev_hour"))


@dp.materialized_view(
    name="silver.plant_inmet_station",
    comment="Silver: nearest INMET station (<= 50 km) for located plants that have no ONS at-plant weather.",
)
def plant_inmet_station():
    # ponytail: nearest station only — hours where it has gaps stay NULL; add a next-nearest fallback
    # if gaps matter on the plant page.
    dim = spark.read.table("silver.dim_plant").filter("lat IS NOT NULL")  # noqa: F821
    ons = spark.read.table("silver.weather_plant_measured").select("plant_id").distinct()  # noqa: F821
    st = _stations().drop("_source_file").dropDuplicates(["station"])
    p = dim.join(ons, "plant_id", "left_anti").select("plant_id", "lat", "lon")
    rad = F.lit(3.141592653589793 / 180)
    dist = 2 * 6371 * F.asin(F.sqrt(
        F.pow(F.sin((F.col("st_lat") - F.col("lat")) * rad / 2), 2)
        + F.cos(F.col("lat") * rad) * F.cos(F.col("st_lat") * rad)
        * F.pow(F.sin((F.col("st_lon") - F.col("lon")) * rad / 2), 2)))
    w = Window.partitionBy("plant_id").orderBy("dist_km")
    return (p.crossJoin(F.broadcast(st)).withColumn("dist_km", dist)
             .filter(F.col("dist_km") <= MAX_KM)
             .withColumn("_rn", F.row_number().over(w)).filter("_rn = 1")
             .select("plant_id", "station", "station_name", "station_uf", "dist_km"))
