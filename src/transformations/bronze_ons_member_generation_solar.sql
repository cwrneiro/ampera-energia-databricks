-- Bronze: raw ONS per-member-plant generation for solar complexes (restricao_coff_fotovoltaica_detail),
-- 30-min, val_geracaoverificada = measured MW. Spec: specs/09-conjunto-members.md
-- Two append flows: the 2024 files store flg_dadoirradianciainvalido as BOOLEAN (and lack
-- id_ons_conjuntousina), later files as INT. Auto Loader can't merge those schemas in one read
-- (schemaHints didn't help), so each file set is read on its own and the old flag is cast to INT.
CREATE OR REFRESH STREAMING TABLE ons_member_generation_solar
  COMMENT 'Bronze: raw ONS measured 30-min generation per solar complex member (coff detail) + ingestion metadata.';

CREATE FLOW ons_member_generation_solar_2025_on
AS INSERT INTO ons_member_generation_solar BY NAME
SELECT
  *,
  'ONS restricao_coff_fotovoltaica_detail'  AS _source,
  current_timestamp()                       AS _ingested_at,
  _metadata.file_path                       AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/bronze/raw/ons_member_solar',
  format => 'parquet',
  pathGlobFilter => '*_202[5-9]_*.parquet'
);

CREATE FLOW ons_member_generation_solar_2024
AS INSERT INTO ons_member_generation_solar BY NAME
SELECT
  * EXCEPT (flg_dadoirradianciainvalido),
  CAST(flg_dadoirradianciainvalido AS INT)  AS flg_dadoirradianciainvalido,
  'ONS restricao_coff_fotovoltaica_detail'  AS _source,
  current_timestamp()                       AS _ingested_at,
  _metadata.file_path                       AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/bronze/raw/ons_member_solar',
  format => 'parquet',
  pathGlobFilter => '*_2024_*.parquet'
);
