# Silver: cleaned ONS hourly generation fact — val_geracao cast to double, each row carrying
# its resolved plant_id. This is what gold aggregates. Spec: specs/02-reconciliation-silver.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="ampera_silver.generation",
    comment="Silver: cleaned ONS hourly generation (MWh) with resolved plant_id + match method.",
    cluster_by=["gen_date", "uf"],
)
@dp.expect_or_fail("has_plant_id", "plant_id IS NOT NULL")
@dp.expect("non_negative_mwh", "mwh >= 0 OR mwh IS NULL")
def generation():
    g = spark.read.table("ampera_bronze.ons_generation")  # noqa: F821
    pm = (spark.read.table("ampera_silver.plant_match")  # noqa: F821
          .select("ons_key", "plant_id", "match_method", "confidence"))
    return (
        g.withColumn("ons_key", F.coalesce(F.expr("nullif(trim(id_ons), '')"), F.col("nom_usina")))
        # val_geracao is STRING up to 2026_04 and DOUBLE from 2026_05; Auto Loader kept the STRING
        # schema and rescued the DOUBLE values into _rescued_data -> read from either.
        .withColumn("mwh", F.coalesce(
            F.expr("try_cast(val_geracao AS double)"),
            F.expr("try_cast(get_json_object(_rescued_data, '$.val_geracao') AS double)")))
        .withColumn("ts", F.col("din_instante").cast("timestamp"))
        .withColumn("gen_date", F.to_date("ts"))
        .withColumnRenamed("id_estado", "uf")
        .join(pm, "ons_key", "left")
        .select("ts", "gen_date", "uf", "id_subsistema", "id_ons", "ons_key",
                F.col("nom_usina").alias("nome_ons"),
                "plant_id", "match_method", "confidence", "mwh")
    )
