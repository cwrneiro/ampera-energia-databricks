-- Gold: daily generation per plant — the app's default grain, synced to Lakebase. By CEG / UF /
-- fonte / conjunto are GROUP BYs on this table. Spec: specs/03-gold-marts.md (decision #17)
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.generation_daily
  COMMENT 'Gold: daily MWh per plant with CEG, UF, submercado, fonte, conjunto; mwh_estimado = estimated part.'
  CLUSTER BY (dia, plant_id)
AS SELECT
  gen_date                                         AS dia,
  plant_id,                                        -- (dia, plant_id) is the Lakebase primary key
  max(ceg)                                         AS ceg,
  max(nome)                                        AS nome,
  max(uf)                                          AS uf,
  max(submercado)                                  AS submercado,
  max(fonte)                                       AS fonte,
  max(conjunto_key)                                AS conjunto_key,
  max(nom_conjunto)                                AS nom_conjunto,
  max_by(match_method, mwh)                        AS match_method,   -- dominant method that day
  sum(mwh)                                         AS mwh,
  sum(CASE WHEN is_estimated THEN mwh ELSE 0 END)  AS mwh_estimado,
  avg(pld_rs_mwh)                                  AS pld_medio_rs_mwh,          -- simple daily mean
  try_divide(sum(valor_rs), sum(mwh))              AS pld_capturado_rs_mwh,      -- generation-weighted
  sum(valor_rs)                                    AS valor_rs,
  avg(vento_100m_ms_modelo)                        AS vento_100m_ms_modelo,
  avg(irradiancia_wm2_modelo)                      AS irradiancia_wm2_modelo,
  avg(temp_c_modelo)                               AS temp_c_modelo,
  sum(precip_mm_modelo)                            AS precip_mm_modelo,
  avg(vento_ms_medido)                             AS vento_ms_medido,
  avg(irradiancia_wm2_medida)                      AS irradiancia_wm2_medida,
  max(fonte_medicao)                               AS fonte_medicao
FROM ampera_gold.fact_generation_hourly
GROUP BY gen_date, plant_id;
