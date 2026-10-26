# Silver (GenAI): the ai_decide verdicts the matching ladder applies. ai_decide itself runs outside the
# pipeline (notebooks/adjudicate_ai), once per ONS plant x top-3 candidate set x prompt, into the durable
# table ampera_silver.ai_decide_verdict (created empty by scripts/bootstrap_workspace.sh) — so refreshes
# don't re-bill or re-roll the same question. This view keeps only the verdict for each plant's *current*
# key (today's candidates and prompt), re-judged with the shared acceptance rule; for a plant whose
# candidates just changed it is empty until the job's adjudication + re-run. Spec: specs/12-genai-reconciliation.md
from pyspark import pipelines as dp
from reco_ai import VERDICT_KEY, accepted, current_keys
from reco_lib import VERDICT


@dp.temporary_view(name="ai_verdict", comment="ai_decide verdict for each ONS plant's current key (ai_accepted = shared rule).")
def ai_verdict():
    keys = current_keys(spark.read.table("ampera_silver.ons_plant"), spark.read.table("ampera_silver.siga_plant"))  # noqa: F821
    return spark.read.table(VERDICT).join(keys, VERDICT_KEY, "left_semi").withColumn("ai_accepted", accepted())  # noqa: F821
