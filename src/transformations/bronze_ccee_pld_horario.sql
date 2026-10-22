-- Bronze: raw CCEE PLD horário (hourly spot price, R$/MWh, per submarket), yearly CSVs downloaded
-- from dadosabertos.ccee.org.br by browser — CCEE blocks automated clients, so refresh is a manual
-- drop into the volume. All columns STRING (the 2024 file quotes its fields, later files don't).
-- Spec: specs/03-gold-marts.md
CREATE OR REFRESH STREAMING TABLE ccee_pld_horario
  COMMENT 'Bronze: raw CCEE hourly PLD (R$/MWh) per submarket, as downloaded + ingestion metadata.'
AS SELECT
  *,
  'CCEE pld_horario'   AS _source,
  current_timestamp()  AS _ingested_at,
  _metadata.file_path  AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/ampera_bronze/raw/ccee_pld',
  format => 'csv',
  sep => ';',
  header => true,
  inferColumnTypes => false
);
