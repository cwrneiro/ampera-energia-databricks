# Silver check: monthly published ONS total vs plant-grain total. If the complex -> member split
# drops or double-counts generation, plant_mwh drifts from published_mwh and the expectation flags
# it in the pipeline UI. Spec: specs/09-conjunto-members.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F


def _sum_if(method):
    return F.sum(F.when(F.col("match_method") == method, F.col("mwh")).otherwise(0.0))


@dp.materialized_view(
    name="silver.generation_balance",
    comment="Silver check: monthly published vs plant-grain MWh, and measured/estimated member MWh.",
)
@dp.expect("balance_within_2pct", "abs(plant_mwh / published_mwh - 1) <= 0.02")
@dp.expect("published_mwh_present", "published_mwh > 0")  # a NULL ratio would slip past the check above
def generation_balance():
    month = F.date_trunc("month", "gen_date").cast("date").alias("month")
    pub = (spark.read.table("silver.generation")  # noqa: F821
           .groupBy(month).agg(F.sum("mwh").alias("published_mwh")))
    pl = (spark.read.table("silver.generation_plant")  # noqa: F821
          .groupBy(month).agg(F.sum("mwh").alias("plant_mwh"),
                              _sum_if("member_measured").alias("member_measured_mwh"),
                              _sum_if("member_estimated").alias("member_estimated_mwh"),
                              _sum_if("ons_conjunto").alias("complex_level_mwh")))
    return pub.join(pl, "month").withColumn("ratio", F.col("plant_mwh") / F.col("published_mwh"))
