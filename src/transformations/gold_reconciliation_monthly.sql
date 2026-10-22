-- Gold: the reconciliation story by month — how ONS generation links to SIGA, at the published grain
-- (ampera_silver.generation) and at plant grain after splitting complexes (ampera_silver.generation_plant).
-- Synced to Lakebase for the app's reconciliation page. Spec: specs/03-gold-marts.md (decision #17)
CREATE OR REFRESH MATERIALIZED VIEW ampera_gold.reconciliation_monthly
  COMMENT 'Gold: monthly MWh and plant count per match_method, for grao publicado (ONS as published) and usina (plant grain).'
AS SELECT 'publicado' AS grao, CAST(date_trunc('month', gen_date) AS DATE) AS mes, match_method,
          sum(mwh) AS mwh, count(DISTINCT plant_id) AS n_usinas
   FROM ampera_silver.generation
   GROUP BY ALL
UNION ALL
   SELECT 'usina', CAST(date_trunc('month', gen_date) AS DATE), match_method,
          sum(mwh), count(DISTINCT plant_id)
   FROM ampera_silver.generation_plant
   GROUP BY ALL;
