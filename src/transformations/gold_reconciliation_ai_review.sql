-- Gold: the ai_decide review queue for the app's Reconciliação sheet — every ONS plant ai_decide was
-- asked about (its verdict for today's candidates, ai_verdict), its three SIGA candidates with
-- probabilities, the plant's final match_method / plant_id (the app's state comes from these) and how
-- much generation rides on it. Synced to Lakebase.
-- Spec: specs/12-genai-reconciliation.md
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.reconciliation_ai_review
  COMMENT 'Gold (GenAI): ai_decide verdicts per ONS plant (candidates A/B/C, probabilities, applied or queued for review) with the MWh at stake.'
AS SELECT
  a.ons_key,
  a.nom_usina,
  a.uf,
  a.fuel_raw                                  AS tipo,
  a.ai_choice,
  a.ai_confidence,
  a.ai_accepted,
  a.ai_plant_id,
  a.a_id, a.a_nome, a.a_municipio, a.ai_prob_a,
  a.b_id, a.b_nome, a.b_municipio, a.ai_prob_b,
  a.c_id, a.c_nome, a.c_municipio, a.ai_prob_c,
  a.ai_prob_nenhum,
  m.match_method,
  m.plant_id,
  g.mwh_total
FROM ai_verdict a
JOIN ampera_silver.plant_match m USING (ons_key)
LEFT JOIN (SELECT ons_key, sum(mwh) AS mwh_total FROM ampera_silver.generation GROUP BY ons_key) g USING (ons_key);
