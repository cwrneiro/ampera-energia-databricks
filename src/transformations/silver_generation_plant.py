# Silver: hourly generation at PLANT grain, no double counting. Complex (conjunto) rows are
# replaced by their members: measured per-member generation where ONS publishes it, else a
# capacity-weighted split labeled as estimated. Spec: specs/09-conjunto-members.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import reco_sql as S

COLS = ["ts", "gen_date", "uf", "submercado", "ons_key", "conjunto_key", "plant_id", "nome", "fuel_cls",
        "match_method", "confidence", "is_estimated", "mwh"]


def _in_range(date_col, frm, to):
    return ((date_col >= F.coalesce(frm, F.lit("1900-01-01").cast("date")))
            & (date_col <= F.coalesce(to, F.lit("9999-12-31").cast("date"))))


def _members(table, fuel):
    d = spark.read.table(table)  # noqa: F821
    return (d.select(F.trim("id_ons").alias("member_id"),
                     F.trim("id_ons_conjuntousina").alias("cx_detail"),
                     F.col("id_estado").alias("uf"),
                     F.col("id_subsistema").alias("submercado"),
                     F.trim("nom_usina").alias("nome"),
                     S.ceg_norm_col("ceg").alias("ceg_norm"),
                     # 30-min instant t covers [t, t+30m); avg of an hour's two MW values = MWh
                     F.date_trunc("hour", "din_instante").alias("ts"),
                     "val_geracaoverificada")
            .withColumn("fuel_cls", F.lit(fuel)))


@dp.materialized_view(
    name="ampera_silver.generation_plant",
    comment="Silver: hourly MWh per plant_id; complexes split into members (measured, or estimated).",
    cluster_by=["gen_date", "uf"],
)
@dp.expect_or_fail("has_plant_id", "plant_id IS NOT NULL")
@dp.expect("non_negative_mwh", "mwh >= 0 OR mwh IS NULL")
def generation_plant():
    gen = (spark.read.table("ampera_silver.generation")  # noqa: F821
           .withColumnRenamed("id_subsistema", "submercado")
           .join(spark.read.table("ampera_silver.ons_plant")  # noqa: F821
                 .select("ons_key", "fuel_cls"), "ons_key", "left"))
    cm = spark.read.table("ampera_silver.conjunto_member")  # noqa: F821
    ckeys = cm.select(F.col("conjunto_key").alias("ons_key")).distinct()

    base = gen.join(ckeys, "ons_key", "left_anti")
    cx = gen.join(ckeys, "ons_key", "left_semi")

    # --- measured members (hourly) ------------------------------------------------------------
    mem = (_members("ampera_bronze.ons_member_generation_wind", "EOL")
           .unionByName(_members("ampera_bronze.ons_member_generation_solar", "SOL"))
           .groupBy("member_id", "cx_detail", "uf", "submercado", "nome", "ceg_norm", "fuel_cls", "ts")
           .agg(F.avg("val_geracaoverificada").alias("mwh")))
    # Early solar files (2024_10..12) lack id_ons_conjuntousina -> look the complex up in the mapping.
    mp = cm.select(F.col("member_id").alias("m_id"), F.col("conjunto_key").alias("m_cx"),
                   "valid_from", "valid_to")
    need = mem.filter(F.col("cx_detail").isNull())
    w = Window.partitionBy("member_id", "ts").orderBy(F.col("valid_from").desc_nulls_last())
    fixed = (need.join(F.broadcast(mp), (need.member_id == mp.m_id)
                       & _in_range(F.to_date(need.ts), mp.valid_from, mp.valid_to))
             .withColumn("_rn", F.row_number().over(w)).filter("_rn = 1")
             .withColumn("cx_detail", F.col("m_cx"))
             .select(*mem.columns))
    mem = mem.filter(F.col("cx_detail").isNotNull()).unionByName(fixed)

    cx_hours = cx.select("ons_key", "ts").distinct()
    measured = (mem.withColumnRenamed("cx_detail", "conjunto_key")
                .join(cx_hours.withColumnRenamed("ons_key", "conjunto_key"), ["conjunto_key", "ts"], "left_semi")
                .withColumn("gen_date", F.to_date("ts"))
                .withColumn("ons_key", F.col("member_id"))
                .withColumn("plant_id", F.coalesce("ceg_norm", F.concat(F.lit("SURR-M-"), "member_id")))
                .withColumn("match_method", F.lit("member_measured"))
                .withColumn("confidence", F.lit(1.0))
                .withColumn("is_estimated", F.lit(False))
                .select(*COLS))

    # --- estimated members: complex-hours with no measured member ----------------------------
    measured_hours = measured.select(F.col("conjunto_key").alias("ons_key"), "ts").distinct()
    cx_un = cx.join(measured_hours, ["ons_key", "ts"], "left_anti")
    act = (cm.filter("capacity_mw > 0")
           .dropDuplicates(["conjunto_key", "member_id", "valid_from"])
           .select(F.col("conjunto_key").alias("a_cx"), F.col("plant_id").alias("a_plant_id"),
                   F.col("nome").alias("a_nome"), F.col("capacity_mw"),
                   F.col("valid_from"), F.col("valid_to")))
    wc = Window.partitionBy("ons_key", "ts")
    est = (cx_un.join(F.broadcast(act), (cx_un.ons_key == act.a_cx)
                      & _in_range(cx_un.gen_date, act.valid_from, act.valid_to))
           .withColumn("mwh", F.col("mwh") * F.col("capacity_mw") / F.sum("capacity_mw").over(wc))
           .withColumn("conjunto_key", F.col("ons_key"))
           .withColumn("plant_id", F.col("a_plant_id"))
           .withColumn("nome", F.col("a_nome"))
           .withColumn("match_method", F.lit("member_estimated"))
           .withColumn("confidence", F.lit(0.0))
           .withColumn("is_estimated", F.lit(True))
           .select(*COLS))

    # Complex-hours with neither measured nor estimable members stay at complex level.
    est_hours = est.select(F.col("conjunto_key").alias("ons_key"), "ts").distinct()
    cx_left = (cx_un.join(est_hours, ["ons_key", "ts"], "left_anti")
               .withColumn("conjunto_key", F.col("ons_key"))
               .withColumn("nome", F.col("nome_ons"))
               .withColumn("is_estimated", F.lit(False))
               .select(*COLS))

    # ONS also publishes some complex members as standalone series (24 plants, ~1.9 TWh over 24 months,
    # also inside the complex total). Keep the standalone series; drop the member copy so each
    # plant-hour is counted once. Spec: specs/09-conjunto-members.md
    standalone = base.select("plant_id", "ts").distinct()
    measured = measured.join(standalone, ["plant_id", "ts"], "left_anti")
    est = est.join(standalone, ["plant_id", "ts"], "left_anti")

    base = (base.withColumn("conjunto_key", F.lit(None).cast("string"))
            .withColumn("nome", F.col("nome_ons"))
            .withColumn("is_estimated", F.lit(False))
            .select(*COLS))
    return base.unionByName(measured).unionByName(est).unionByName(cx_left)
