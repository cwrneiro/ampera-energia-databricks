# Silver (CORE): resolve each ONS plant to one plant_id via the matching ladder.
# override -> CEG(normalized) -> fuzzy(name sim within UF+fuel >= THRESHOLD) -> surrogate hash.
# Spec: specs/02-reconciliation-silver.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import reco_lib as R
import reco_sql as S


@dp.materialized_view(
    name="silver.plant_match",
    comment="Silver: id_ons -> plant_id with match_method (override/ceg/fuzzy/unmatched) + confidence.",
)
@dp.expect_or_fail("has_plant_id", "plant_id IS NOT NULL")
def plant_match():
    ons = spark.read.table("silver.ons_plant")  # noqa: F821
    siga = spark.read.table("silver.siga_plant")  # noqa: F821

    # Manual overrides win over the automatic result; newest row per ons_id wins (duplicates would
    # fan out plant_match and double-count generation). Required input — DDL in specs/02.
    ow = Window.partitionBy("ons_id").orderBy(F.col("updated_at").desc_nulls_last())
    ov = (spark.read.table("silver.plant_match_override")  # noqa: F821
          .withColumn("_rn", F.row_number().over(ow)).filter("_rn = 1")
          .select(F.col("ons_id").alias("ov_id"), F.col("plant_id").alias("ov_plant_id")))

    # Step 1 — CEG (normalized on both sides).
    siga_ceg = siga.select(F.col("plant_id").alias("ceg_plant_id")).distinct()
    ceg = (ons.join(siga_ceg, ons.ceg_norm == siga_ceg.ceg_plant_id, "left")
           .withColumn("ceg_match", F.col("ceg_plant_id").isNotNull()))

    # Step 2 — fuzzy for the non-CEG-matched, within same UF + fuel class.
    unm = ceg.filter(~F.col("ceg_match")).select("ons_key", "name_norm", "uf", "fuel_cls")
    s2 = siga.select(F.col("plant_id").alias("f_plant_id"),
                     F.col("name_norm").alias("s_name"),
                     F.col("uf").alias("s_uf"),
                     F.col("fuel_cls").alias("s_fuel"))
    cand = (unm.join(s2, (unm.uf == s2.s_uf) & (unm.fuel_cls == s2.s_fuel), "left")
            .withColumn("sim", F.when(S.numerals_col(F.col("name_norm")) == S.numerals_col(F.col("s_name")),
                                      S.sim_col(F.col("name_norm"), F.col("s_name"))).otherwise(F.lit(0.0))))
    w = Window.partitionBy("ons_key").orderBy(F.col("sim").desc_nulls_last())
    best = (cand.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1")
            .select("ons_key", F.col("f_plant_id").alias("fuzzy_plant_id"),
                    F.col("sim").alias("fuzzy_sim")))

    m = ceg.join(best, "ons_key", "left")
    m = m.join(ov, m.ons_key == ov.ov_id, "left")

    th = R.THRESHOLD
    surrogate = F.concat(F.lit("SURR-"), F.sha2(
        F.concat_ws("|", F.coalesce("name_norm", F.lit("")),
                    F.coalesce("uf", F.lit("")), F.coalesce("fuel_cls", F.lit(""))), 256).substr(1, 16))

    plant_id = (F.when(F.col("ov_plant_id").isNotNull(), F.col("ov_plant_id"))
                .when(F.col("ceg_match"), F.col("ceg_norm"))
                .when(F.col("fuzzy_sim") >= th, F.col("fuzzy_plant_id"))
                .otherwise(surrogate))
    # Aggregate/conjunto grains have no 1:1 SIGA plant by design -> their own labels, not "unmatched".
    no_auto_match = (F.when(F.col("ons_grain") == "aggregate", F.lit("ons_aggregate"))
                     .when(F.col("ons_grain") == "conjunto", F.lit("ons_conjunto"))
                     .otherwise(F.lit("unmatched")))
    method = (F.when(F.col("ov_plant_id").isNotNull(), F.lit("override"))
              .when(F.col("ceg_match"), F.lit("ceg"))
              .when(F.col("fuzzy_sim") >= th, F.lit("fuzzy"))
              .otherwise(no_auto_match))
    confidence = (F.when(F.col("ov_plant_id").isNotNull(), F.lit(1.0))
                  .when(F.col("ceg_match"), F.lit(1.0))
                  .when(F.col("fuzzy_sim") >= th, F.col("fuzzy_sim"))
                  .otherwise(F.lit(0.0)))

    return (m.withColumn("plant_id", plant_id)
            .withColumn("match_method", method)
            .withColumn("confidence", confidence)
            .select("ons_key", "plant_id", "match_method", "confidence",
                    F.col("ceg_norm").alias("ons_ceg"), "fuzzy_sim"))
