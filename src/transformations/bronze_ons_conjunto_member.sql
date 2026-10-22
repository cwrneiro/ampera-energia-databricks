-- Bronze: raw ONS complex -> member plant mapping (dataset usina_conjunto), with member CEG and
-- validity dates. Spec: specs/09-conjunto-members.md
CREATE OR REFRESH STREAMING TABLE ons_conjunto_member
  COMMENT 'Bronze: raw ONS complex-to-member-plant mapping (usina_conjunto) + ingestion metadata.'
AS SELECT
  *,
  'ONS usina_conjunto'  AS _source,
  current_timestamp()   AS _ingested_at,
  _metadata.file_path   AS _source_file
FROM STREAM read_files('/Volumes/${catalog}/ampera_bronze/raw/ons_conjunto_member', format => 'parquet');
