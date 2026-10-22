# Silver: distinct ONS plant dimension with normalized match keys. Spec: specs/02-reconciliation-silver.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
import reco_sql as S


@dp.materialized_view(
    name="ampera_silver.ons_plant",
    comment="Silver: one row per ONS plant (id_ons) with normalized name/CEG/fuel match keys.",
)
def ons_plant():
    g = spark.read.table("ampera_bronze.ons_generation")  # noqa: F821
    # Small-plant groups (Tipo III / MMGD) have a name but no id_ons -> key on name as fallback.
    g = g.withColumn("ons_key", F.coalesce(F.expr("nullif(trim(id_ons), '')"), F.col("nom_usina")))
    p = g.groupBy("ons_key").agg(
        F.max("nom_usina").alias("nom_usina"),
        F.max("id_estado").alias("uf"),
        F.max("nom_tipocombustivel").alias("fuel_raw"),
        F.max("nom_tipousina").alias("tipousina"),
        F.max("ceg").alias("ceg_raw"),  # '-' sorts below real codes, so max() prefers a real CEG
    )
    # ONS reports at mixed granularity: plant-level, wind/solar "Conj." complexes, and state-level
    # "PQU <UF> ... MMGD" / "... CARGA GLOBAL" aggregates. Only plant-level rows can 1:1-match SIGA.
    grain = (F.when(F.col("nom_usina").rlike("(?i)^PQU |CARGA GLOBAL"), F.lit("aggregate"))
             # complexes: ONS id CJU_* or a name like "Conj. X" / "Conjunto Eólico X" (21 series,
             # 22.6 TWh, were missed by a "Conj." prefix check)
             .when(F.col("ons_key").startswith("CJU_") | F.col("nom_usina").rlike("(?i)^conj"),
                   F.lit("conjunto"))
             .otherwise(F.lit("plant")))
    return (
        p.withColumn("name_norm", S.name_norm_col("nom_usina"))
        .withColumn("ceg_norm", S.ceg_norm_col("ceg_raw"))
        .withColumn("fuel_cls", S.fuel_cls_col("fuel_raw"))
        .withColumn("ons_grain", grain)
    )
