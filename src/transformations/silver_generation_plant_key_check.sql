-- Silver check: every (plant_id, ons_key, hour) appears once in silver.generation_plant. Any row
-- here is a double-counted series-hour (e.g. a plant ONS reports both standalone and inside its
-- complex); the expectation fails the update so it can't reach gold/Lakebase. One plant with
-- several ONS series (Itaipu 50/60 Hz, Belo Monte + Pimental) is legitimate and summed per plant.
-- Spec: specs/09-conjunto-members.md
CREATE OR REFRESH MATERIALIZED VIEW silver.generation_plant_key_check (
  CONSTRAINT one_row_per_plant_hour EXPECT (n_rows = 1) ON VIOLATION FAIL UPDATE
)
  COMMENT 'Silver check: duplicated (plant_id, ons_key, ts) in generation_plant — must stay empty.'
AS SELECT plant_id, ons_key, ts, count(*) AS n_rows
FROM silver.generation_plant
GROUP BY plant_id, ons_key, ts
HAVING count(*) > 1;
