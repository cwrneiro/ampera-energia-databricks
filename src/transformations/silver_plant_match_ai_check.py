# Silver check: the matching ladder's ai_decide rung is enforced, not just written. Every plant_match row
# placed by ai_decide must come from an accepted verdict, use that verdict's plant, and have an ONS CEG
# that doesn't link to SIGA (CEG and fuzzy come first). Any violation fails the update.
# Spec: specs/12-genai-reconciliation.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="ampera_silver.plant_match_ai_check",
    comment="Silver check: ai_decide matches vs their verdict and CEG link — every row must pass the expectations.",
)
@dp.expect_or_fail("from_accepted_verdict", "verdict_accepted")
@dp.expect_or_fail("uses_verdict_plant", "plant_id <=> ai_plant_id")
@dp.expect_or_fail("ceg_not_linked", "NOT ceg_links")
def plant_match_ai_check():
    m = spark.read.table("ampera_silver.plant_match").filter("match_method = 'ai_decide'")  # noqa: F821
    v = spark.read.table("ai_verdict").select("ons_key", "ai_plant_id", F.col("ai_accepted").alias("verdict_accepted"))  # noqa: F821
    siga = (spark.read.table("ampera_silver.siga_plant")  # noqa: F821
            .select(F.col("plant_id").alias("ons_ceg")).distinct().withColumn("ceg_links", F.lit(True)))
    return (m.join(v, "ons_key", "left").join(siga, "ons_ceg", "left")
            .select("ons_key", "ons_ceg", "plant_id", "ai_plant_id",
                    F.coalesce("verdict_accepted", F.lit(False)).alias("verdict_accepted"),
                    F.coalesce("ceg_links", F.lit(False)).alias("ceg_links")))
