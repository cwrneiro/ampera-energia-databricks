# Silver: ONS complex -> member plant bridge, with validity dates and SIGA capacity (used to pick
# active members and weight the estimate). Spec: specs/09-conjunto-members.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
import reco_sql as S


def _date(col):
    return F.to_date(F.expr(f"nullif(trim({col}), '')"))


@dp.materialized_view(
    name="ampera_silver.conjunto_member",
    comment="Silver: complex (conjunto_key) -> member plant_id with validity dates and SIGA capacity.",
)
def conjunto_member():
    m = spark.read.table("ampera_bronze.ons_conjunto_member")  # noqa: F821
    siga = (spark.read.table("ampera_silver.siga_plant")  # noqa: F821
            .select("plant_id", "capacity_mw"))
    return (
        m.select(F.trim("id_ons_conjunto").alias("conjunto_key"),
                 F.trim("id_ons_usina").alias("member_id"),
                 F.trim("nom_conjunto").alias("nom_conjunto"),
                 F.trim("nom_usina").alias("nome"),
                 F.trim("estad_id").alias("uf"),
                 S.ceg_norm_col("ceg").alias("ceg_norm"),
                 _date("dat_iniciorelacionamento").alias("valid_from"),
                 _date("dat_fimrelacionamento").alias("valid_to"))
        .join(siga, F.col("ceg_norm") == siga.plant_id, "left")
        .withColumn("in_siga", F.col("plant_id").isNotNull())
        .withColumn("plant_id", F.coalesce("plant_id", "ceg_norm", F.concat(F.lit("SURR-M-"), "member_id")))
    )
