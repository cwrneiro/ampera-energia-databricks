-- Bronze: raw ANEEL SIGA plant registry snapshot.
-- CSV quirks (preserved as-is for silver to clean): ';' delimiter, comma decimals,
-- lat/long in NumCoordN/E Empreendimento. All columns read as STRING (inferColumnTypes=false)
-- so comma-decimals and codes survive untouched. Spec: specs/01-ingestion-bronze.md
CREATE OR REFRESH STREAMING TABLE siga_plants
  COMMENT 'Bronze: raw ANEEL SIGA plant registry (all columns STRING) + ingestion metadata.'
AS SELECT
  *,
  'ANEEL SIGA'         AS _source,
  current_timestamp()  AS _ingested_at,
  _metadata.file_path  AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/bronze/raw/siga',
  format => 'csv',
  sep => ';',
  header => true,
  inferColumnTypes => false,
  encoding => 'UTF-8'
);
