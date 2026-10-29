-- Serving: unfiltered copy of ampera_gold.plant_location — the Lakebase sync source only, because synced tables
-- refuse a row-filtered source. The pipeline reads gold as its owner (not a client), so the copy is
-- complete; the app re-applies the client filter on Lakebase. Nobody else is granted this schema. Spec 17.
CREATE OR REFRESH MATERIALIZED VIEW ampera_serving.plant_location
  COMMENT 'Serving: unfiltered copy of ampera_gold.plant_location. Synced to Lakebase as ampera_gold_lb.plant_location. Spec 17.'
AS SELECT * FROM ampera_gold.plant_location;
