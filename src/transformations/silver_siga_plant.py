# Silver: cleaned ANEEL SIGA registry, one row per CEG, coords + capacity parsed.
# Spec: specs/02-reconciliation-silver.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import reco_sql as S


def _dec(col):  # SIGA numbers use comma decimals, stored as STRING in bronze
    return F.regexp_replace(F.col(col), ",", ".").cast("double")


@dp.materialized_view(
    name="silver.siga_plant",
    comment="Silver: cleaned SIGA plant registry, one row per normalized CEG, with lat/long + MW.",
)
def siga_plant():
    s = spark.read.table("bronze.siga_plants")  # noqa: F821
    df = (
        s.withColumn("plant_id", S.ceg_norm_col("CodCEG"))
        .withColumn("name_norm", S.name_norm_col("NomEmpreendimento"))
        .withColumn("fuel_cls", S.fuel_cls_col("SigTipoGeracao"))
        .withColumn("capacity_mw", _dec("MdaPotenciaFiscalizadaKw") / 1000)
        .withColumn("lat", _dec("NumCoordNEmpreendimento"))
        .withColumn("lon", _dec("NumCoordEEmpreendimento"))
        .withColumnRenamed("NomEmpreendimento", "nome")
        .withColumnRenamed("SigUFPrincipal", "uf")
        .withColumnRenamed("SigTipoGeracao", "tipo")
        .withColumnRenamed("DscMuninicpios", "municipio")
        .withColumnRenamed("DscFaseUsina", "fase")
        .filter(F.col("plant_id").isNotNull())
    )
    # 25045 rows ~ 25042 CEGs: dedup to one row per plant_id, keep the largest capacity.
    w = Window.partitionBy("plant_id").orderBy(F.col("capacity_mw").desc_nulls_last())
    return (
        df.withColumn("_rn", F.row_number().over(w))
        .filter("_rn = 1")
        .select("plant_id", "nome", "name_norm", "uf", "tipo", "fuel_cls",
                "capacity_mw", "lat", "lon", "municipio", "fase")
    )
