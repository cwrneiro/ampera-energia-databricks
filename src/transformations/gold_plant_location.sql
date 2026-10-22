-- Gold: one row per plant for the map (point map, decision #9) and plant pages. lat/lon from SIGA
-- where the plant links to it. Synced to Lakebase. Spec: specs/03-gold-marts.md (decision #17)
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.plant_location
  COMMENT 'Gold: one row per plant_id — name, UF, lat/lon (SIGA), capacity, fonte, conjunto, total and last-30-day MWh.'
AS WITH last_day AS (SELECT max(dia) AS d FROM ampera_gold.generation_daily),
agg AS (
  SELECT plant_id,
         sum(mwh)                                                      AS mwh_total,
         sum(CASE WHEN dia > (SELECT d FROM last_day) - 30 THEN mwh END) AS mwh_30d,
         sum(mwh_estimado)                                             AS mwh_estimado_total,
         max_by(match_method, mwh)                                     AS match_method,
         max(nom_conjunto)                                             AS nom_conjunto
  FROM ampera_gold.generation_daily
  GROUP BY plant_id
)
SELECT
  d.plant_id,
  CASE WHEN d.plant_id NOT LIKE 'SURR-%' THEN d.plant_id END AS ceg,
  d.nome,
  d.uf,
  d.lat,
  d.lon,
  d.capacity_mw                                              AS capacidade_mw,
  d.fuel_cls                                                 AS fonte,
  d.tipo,
  d.municipio,
  d.conjunto_key,
  a.nom_conjunto,
  a.match_method,
  d.source                                                   AS fonte_cadastro,
  a.mwh_total,
  a.mwh_30d,
  a.mwh_estimado_total
FROM ampera_silver.dim_plant d
JOIN agg a USING (plant_id);
