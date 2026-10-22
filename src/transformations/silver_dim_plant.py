# Silver: unified plant dimension — one row per plant_id in the plant-grain fact. SIGA attributes
# (name, capacity, coords) where the plant links to SIGA, else ONS names. Spec: specs/02, specs/09
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="ampera_silver.dim_plant",
    comment="Silver: one row per plant_id (SIGA registry attrs where linked, else ONS-sourced).",
)
def dim_plant():
    gp = spark.read.table("ampera_silver.generation_plant")  # noqa: F821
    siga = spark.read.table("ampera_silver.siga_plant")  # noqa: F821

    ids = gp.groupBy("plant_id").agg(F.max("nome").alias("nome_ons"), F.max("uf").alias("uf_ons"),
                                     F.max("fuel_cls").alias("fuel_ons"),
                                     F.max("conjunto_key").alias("conjunto_key"))
    return (ids.join(siga, "plant_id", "left")
            .select("plant_id",
                    F.coalesce("nome", "nome_ons").alias("nome"),
                    F.coalesce("uf", "uf_ons").alias("uf"),
                    "tipo",
                    F.coalesce("fuel_cls", "fuel_ons").alias("fuel_cls"),
                    "capacity_mw", "lat", "lon", "municipio", "fase", "conjunto_key",
                    F.when(F.col("nome").isNotNull(), "siga").otherwise("ons").alias("source")))
