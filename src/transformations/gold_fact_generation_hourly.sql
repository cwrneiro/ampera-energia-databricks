-- Gold: hourly generation per plant (plant grain, from ampera_silver.generation_plant — no double counting).
-- Lakehouse only (Genie, price correlation); not synced to Lakebase. Weather: modeled (Open-Meteo) +
-- measured (ONS at plant, else INMET <= 50 km). Price: CCEE PLD by submarket + hour. Spec: specs/03-gold-marts.md (decision #17)
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.fact_generation_hourly
  COMMENT 'Gold: hourly MWh per plant (complexes split into member plants; is_estimated marks the capacity-weighted estimate).'
  CLUSTER BY (gen_date, plant_id)
AS SELECT
  g.ts,
  g.gen_date,
  g.plant_id,
  CASE WHEN g.plant_id NOT LIKE 'SURR-%' THEN g.plant_id END AS ceg,
  d.nome,
  d.uf,
  g.submercado,
  d.fuel_cls                               AS fonte,
  g.conjunto_key,
  c.nom_conjunto,
  g.match_method,
  g.confidence,
  g.is_estimated,
  g.mwh,
  -- price: CCEE hourly PLD for the plant's submarket (ONS subsystem)
  pr.pld_rs_mwh,
  g.mwh * pr.pld_rs_mwh                    AS valor_rs,
  -- weather, modeled (Open-Meteo ERA5, the plant's 0.25° cell): base layer for every located plant
  w.vento_100m_ms                          AS vento_100m_ms_modelo,
  w.irradiancia_wm2                        AS irradiancia_wm2_modelo,
  w.temp_c                                 AS temp_c_modelo,
  w.precip_mm                              AS precip_mm_modelo,
  -- weather, measured (decision #18): ONS at the plant for complex members; otherwise the nearest
  -- INMET station within 50 km. INMET wind is at 10 m (ONS at the turbine); see fonte_medicao.
  coalesce(m.vento_ms, i.vento_10m_ms)     AS vento_ms_medido,
  coalesce(m.irradiancia_wm2, i.irradiancia_wm2) AS irradiancia_wm2_medida,
  i.temp_c                                 AS temp_c_medida,
  i.precip_mm                              AS precip_mm_medida,
  CASE WHEN m.plant_id IS NOT NULL THEN 'ONS'
       WHEN s.station IS NOT NULL THEN 'INMET' END AS fonte_medicao,
  s.station                                AS estacao_inmet,
  round(s.dist_km, 1)                      AS dist_estacao_km
FROM ampera_silver.generation_plant g
JOIN ampera_silver.dim_plant d USING (plant_id)
LEFT JOIN (SELECT conjunto_key, max(nom_conjunto) AS nom_conjunto
           FROM ampera_silver.conjunto_member GROUP BY conjunto_key) c
  ON g.conjunto_key = c.conjunto_key
LEFT JOIN ampera_silver.price_pld_hourly pr
  ON pr.submercado = g.submercado AND pr.ts = g.ts
LEFT JOIN ampera_silver.weather_cell_hourly w
  ON w.cell_lat = round(d.lat * 4) / 4 AND w.cell_lon = round(d.lon * 4) / 4 AND w.ts = g.ts
LEFT JOIN ampera_silver.weather_plant_measured m
  ON m.plant_id = g.plant_id AND m.ts = g.ts
LEFT JOIN ampera_silver.plant_inmet_station s
  ON s.plant_id = g.plant_id
LEFT JOIN ampera_silver.weather_inmet_hourly i
  ON i.station = s.station AND i.ts = g.ts;
