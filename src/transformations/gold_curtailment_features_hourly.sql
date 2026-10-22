-- Gold: model-ready plant-hours for the curtailment model (wind + solar, measured generation only).
-- Target = capacity factor (mwh / SIGA capacity); weather = Open-Meteo (available for every located
-- plant, so the model also scores plants ONS doesn't report curtailment for); label = ONS flag where
-- published. Read by notebooks/train_curtailment + score_curtailment. Spec: specs/11-ml-curtailment.md
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.curtailment_features_hourly (
  CONSTRAINT has_capacity EXPECT (capacity_mw > 0) ON VIOLATION DROP ROW,
  CONSTRAINT has_weather  EXPECT (vento_100m_ms IS NOT NULL OR irradiancia_wm2 IS NOT NULL) ON VIOLATION DROP ROW
)
  COMMENT 'Gold: wind/solar plant-hours with capacity factor, Open-Meteo weather, PLD and the ONS curtailment label (ML features).'
  CLUSTER BY (fonte, gen_date)
AS SELECT
  f.ts,
  f.gen_date,
  f.plant_id,
  f.nome,
  f.uf,
  f.submercado,
  f.fonte,
  f.conjunto_key,
  d.capacity_mw,
  f.mwh,
  f.mwh / d.capacity_mw                         AS fator_capacidade,
  hour(f.ts)                                    AS hora,
  month(f.ts)                                   AS mes,
  f.vento_100m_ms_modelo                        AS vento_100m_ms,
  f.irradiancia_wm2_modelo                      AS irradiancia_wm2,
  f.temp_c_modelo                               AS temp_c,
  d.lat,
  d.lon,
  f.pld_rs_mwh,
  l.restrito_ons,                               -- NULL where ONS publishes no constrained-off detail
  l.mwh_estimado_ons
FROM ampera_gold.fact_generation_hourly f
JOIN ampera_silver.dim_plant d USING (plant_id)
LEFT JOIN ampera_silver.curtailment_label_hourly l
  ON l.plant_id = f.plant_id AND l.ts = f.ts
WHERE f.fonte IN ('EOL', 'SOL') AND NOT f.is_estimated;
