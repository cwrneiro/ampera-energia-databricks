-- Serving: unfiltered copy of ampera_gold.generation_daily — the Lakebase sync source only, because synced tables
-- refuse a row-filtered source. The pipeline reads gold as its owner (not a client), so the copy is
-- complete; the app re-applies the client filter on Lakebase. Nobody else is granted this schema. Spec 17.
CREATE OR REFRESH MATERIALIZED VIEW ampera_serving.generation_daily
  COMMENT 'Serving: unfiltered copy of ampera_gold.generation_daily. Synced to Lakebase as ampera_gold_lb.generation_daily. Spec 17.'
  CLUSTER BY (dia, plant_id)
AS SELECT * FROM ampera_gold.generation_daily;
