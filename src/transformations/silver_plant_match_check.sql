-- Silver check: plant_match has one row per ONS series, and the newest manual override per ons_id
-- is the one applied. Any row here fails the update so it can't reach gold/Lakebase.
-- Spec: specs/02-reconciliation-silver.md
CREATE OR REFRESH MATERIALIZED VIEW ampera_silver.plant_match_check (
  CONSTRAINT one_row_per_series EXPECT (n_rows = 1) ON VIOLATION FAIL UPDATE,
  CONSTRAINT override_wins EXPECT (ov_plant_id IS NULL OR (plant_id = ov_plant_id AND match_method = 'override')) ON VIOLATION FAIL UPDATE
)
  COMMENT 'Silver check: duplicated series or unapplied override in plant_match — must stay empty.'
AS WITH ov AS (
  SELECT ons_id, plant_id AS ov_plant_id
  FROM ampera_silver.plant_match_override
  QUALIFY row_number() OVER (PARTITION BY ons_id ORDER BY updated_at DESC NULLS LAST) = 1
), m AS (
  SELECT ons_key, max(plant_id) AS plant_id, max(match_method) AS match_method, count(*) AS n_rows
  FROM ampera_silver.plant_match
  GROUP BY ons_key
)
SELECT m.*, ov.ov_plant_id
FROM m LEFT JOIN ov ON m.ons_key = ov.ons_id
WHERE m.n_rows > 1
   OR (ov.ov_plant_id IS NOT NULL AND NOT (m.plant_id <=> ov.ov_plant_id AND m.match_method = 'override'));
