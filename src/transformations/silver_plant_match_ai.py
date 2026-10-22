# Silver (GenAI): ai_decide adjudicates ONS plants whose CEG doesn't link to SIGA. Each gets its
# top-3 SIGA candidates in the same UF (by name similarity) as A/B/C; ai_decide returns calibrated
# probabilities over A | B | C | nenhum. plant_match applies the choice when confidence >= AI_CUTOFF.
# Spec: specs/12-genai-reconciliation.md
from pyspark import pipelines as dp
from pyspark.sql import functions as F
from reco_ai import candidates, decide


@dp.materialized_view(
    name="ampera_silver.plant_match_ai",
    comment="Silver (GenAI): ai_decide verdict (A/B/C/nenhum + calibrated probabilities) for ONS plants whose CEG doesn't link to SIGA.",
)
@dp.expect("ai_answered", "ai_error IS NULL AND ai_choice IS NOT NULL")
def plant_match_ai():
    ons = spark.read.table("ampera_silver.ons_plant").filter("ons_grain = 'plant'")  # noqa: F821
    siga = spark.read.table("ampera_silver.siga_plant")  # noqa: F821
    todo = ons.join(siga.select(F.col("plant_id").alias("ceg_norm")), "ceg_norm", "left_anti")
    return decide(candidates(todo, siga))
