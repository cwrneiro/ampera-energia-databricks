-- Bronze: raw ONS per-member-plant generation for wind complexes (restricao_coff_eolica_detail),
-- 30-min, val_geracaoverificada = measured MW. Spec: specs/09-conjunto-members.md
CREATE OR REFRESH STREAMING TABLE ons_member_generation_wind
  COMMENT 'Bronze: raw ONS measured 30-min generation per wind complex member (coff detail) + ingestion metadata.'
AS SELECT
  *,
  'ONS restricao_coff_eolica_detail'  AS _source,
  current_timestamp()               AS _ingested_at,
  _metadata.file_path               AS _source_file
FROM STREAM read_files('/Volumes/${catalog}/ampera_bronze/raw/ons_member_wind', format => 'parquet');
