# ai_decide reconciliation helpers (no pipeline decorators): used by silver_plant_match_ai and by the
# blind eval notebook (notebooks/eval_ai_decide). Spec: specs/12-genai-reconciliation.md
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import reco_lib as R
import reco_sql as S

# ai_decide's model follows evidence better than rules: the state spells out, per candidate, the facts a
# reconciler would check (name similarity, same CEG registry number, same plant type). First pass with
# only rules in the prompt answered "nenhum" for every plant, even exact re-registrations (spec 12).
QUESTIONS = """{"match": {"type": "choice",
  "instructions": "Match a Brazilian power plant from the ONS operator (state.ons) to the ANEEL SIGA registry. Candidates A, B and C come with evidence: similaridade_nome (1.0 = same normalized name), mesmo_numero_ceg (the registry number inside the CEG code is the same, strong evidence of the same plant) and mesmo_tipo (same plant type: UTE thermal, EOL wind, UFV solar, UHE/PCH/CGH hydro; a different type means a different plant). Different numerals in the name (I vs II) mean different plants. Pick the candidate that is the same plant, or nenhum.",
  "criteria": {"A": "Candidate A is the same plant as state.ons", "B": "Candidate B is the same plant as state.ons",
               "C": "Candidate C is the same plant as state.ons", "nenhum": "None of the candidates is the same plant as state.ons"}}}"""
CEG_NUM = r"([0-9]{6}-[0-9])"  # CEG = TYPE.FUEL.UF.NNNNNN-D.SS; NNNNNN-D survives re-registration


def _cand(prefix):
    num = F.regexp_extract(F.col(f"{prefix}_id"), CEG_NUM, 1)
    return F.struct(F.col(f"{prefix}_nome").alias("nome"), F.col(f"{prefix}_tipo").alias("tipo"),
                    F.col(f"{prefix}_municipio").alias("municipio"), F.col(f"{prefix}_capacidade_mw").alias("capacidade_mw"),
                    F.round(f"{prefix}_sim", 2).alias("similaridade_nome"),
                    (num == F.col("_ons_num")).alias("mesmo_numero_ceg"),
                    (F.col(f"{prefix}_tipo") == F.col("_ons_tipo")).alias("mesmo_tipo"))


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
    df = (df.withColumn("_ons_num", F.nullif(F.regexp_extract("ceg_raw", CEG_NUM, 1), F.lit("")))
            .withColumn("_ons_tipo", F.upper(F.split("ceg_raw", "[.]")[0])))
    state = F.to_json(F.struct(
        F.struct(F.col("nom_usina").alias("nome"), F.col("uf"), F.col("fuel_raw").alias("combustivel"),
                 F.col("_ons_tipo").alias("tipo")).alias("ons"),
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
          .drop("_r", "_ons_num", "_ons_tipo"))
    return r

