# ai_decide reconciliation helpers (no pipeline decorators): used by silver_plant_match_ai and by the
# blind eval notebook (notebooks/eval_ai_decide). Spec: specs/12-genai-reconciliation.md
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import reco_lib as R
import reco_sql as S

QUESTIONS = """{"match": {"type": "choice",
  "instructions": "The ONS record and candidates A, B, C (ANEEL SIGA registry) describe Brazilian power plants. Which candidate is the same physical plant as the ONS record? Names may differ in accents, abbreviations, prefixes (UHE, EOL, UFV, UTE) and word order, but numerals (e.g. I vs II, 2 vs 3) identify different plants. Answer nenhum if none is clearly the same plant.",
  "criteria": {"A": "Candidate A is the same plant", "B": "Candidate B is the same plant",
               "C": "Candidate C is the same plant", "nenhum": "None of the candidates is the same plant"}}}"""


def _cand(prefix):
    return F.struct(F.col(f"{prefix}_nome").alias("nome"), F.col(f"{prefix}_uf").alias("uf"),
                    F.col(f"{prefix}_tipo").alias("tipo"), F.col(f"{prefix}_municipio").alias("municipio"),
                    F.col(f"{prefix}_capacidade_mw").alias("capacidade_mw"), F.col(f"{prefix}_id").alias("ceg"))


def candidates(ons, siga, k=3):
    """ONS plants (columns ons_key, nom_usina, uf, fuel_raw, ceg_raw, name_norm) -> one row with
    their top-k SIGA candidates in the same UF as columns a_*, b_*, c_*. Shared with the blind eval."""
    s = siga.select(F.col("plant_id").alias("s_id"), F.col("nome").alias("s_nome"),
                    F.col("name_norm").alias("s_norm"), F.col("uf").alias("s_uf"), F.col("tipo").alias("s_tipo"),
                    F.col("municipio").alias("s_municipio"), F.round("capacity_mw", 1).alias("s_capacidade_mw"))
    w = Window.partitionBy("ons_key").orderBy(F.col("sim").desc(), "s_id")
    top = (ons.join(s, ons.uf == s.s_uf)
           .withColumn("sim", S.sim_col(F.col("name_norm"), F.col("s_norm")))
           .withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") <= k))
    cols = ["s_id", "s_nome", "s_uf", "s_tipo", "s_municipio", "s_capacidade_mw", "sim"]
    piv = top.groupBy("ons_key", "nom_usina", "uf", "fuel_raw", "ceg_raw").pivot("_rn", [1, 2, 3]).agg(
        *[F.first(c).alias(c[2:] if c.startswith("s_") else c) for c in cols])
    for i, p in ((1, "a"), (2, "b"), (3, "c")):
        for c in ["id", "nome", "uf", "tipo", "municipio", "capacidade_mw", "sim"]:
            piv = piv.withColumnRenamed(f"{i}_{c}", f"{p}_{c}")
    return piv


def decide(df):
    """Adds ai_choice / ai_confidence / ai_prob_* / ai_plant_id / ai_accepted via ai_decide."""
    state = F.to_json(F.struct(
        F.struct(F.col("nom_usina").alias("nome"), F.col("uf"), F.col("fuel_raw").alias("tipo"),
                 F.col("ceg_raw").alias("ceg_informado")).alias("ons"),
        _cand("a").alias("A"), _cand("b").alias("B"), _cand("c").alias("C")))
    r = df.withColumn("_r", F.call_function("ai_decide", state, F.lit(QUESTIONS),
                                            F.create_map(F.lit("version"), F.lit("1.0"))))

    def g(path, t="string"):
        return F.expr(f"variant_get(_r, '$.response.answers.match.{path}', '{t}')")
    r = (r.withColumn("ai_choice", g("choice"))
          .withColumn("ai_confidence", g("confidence", "double"))
          .withColumn("ai_prob_a", g("probabilities.A", "double"))
          .withColumn("ai_prob_b", g("probabilities.B", "double"))
          .withColumn("ai_prob_c", g("probabilities.C", "double"))
          .withColumn("ai_prob_nenhum", g("probabilities.nenhum", "double"))
          .withColumn("ai_error", F.expr("variant_get(_r, '$.error_message', 'string')"))
          .withColumn("ai_plant_id", F.when(F.col("ai_choice") == "A", F.col("a_id"))
                                      .when(F.col("ai_choice") == "B", F.col("b_id"))
                                      .when(F.col("ai_choice") == "C", F.col("c_id")))
          .withColumn("ai_accepted", F.coalesce(F.col("ai_plant_id").isNotNull()
                                                & (F.col("ai_confidence") >= R.AI_CUTOFF), F.lit(False)))
          .drop("_r"))
    return r

