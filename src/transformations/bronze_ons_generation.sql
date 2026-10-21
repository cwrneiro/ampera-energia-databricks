-- Bronze: raw ONS hourly generation per plant (dataset geracao-usina-2).
-- As-ingested, types preserved (val_geracao stays STRING; cast happens in silver).
-- Auto Loader picks up new monthly files landed in the volume. Spec: specs/01-ingestion-bronze.md
CREATE OR REFRESH STREAMING TABLE ons_generation
  COMMENT 'Bronze: raw ONS hourly generation (geracao-usina-2), as-ingested + ingestion metadata.'
AS SELECT
  *,
  'ONS geracao-usina-2'  AS _source,
  current_timestamp()    AS _ingested_at,
  _metadata.file_path    AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/bronze/raw/ons',
  format => 'parquet'
);
