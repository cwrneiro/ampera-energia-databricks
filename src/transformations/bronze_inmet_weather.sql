-- Bronze: raw INMET automatic-station hourly CSVs (yearly archives, one file per station), read
-- line by line as text columns _c0.._c19: each file has an 8-line metadata header (station, lat,
-- lon...), a column header, then 20-column hourly rows in UTC with comma decimals. Silver parses both.
-- Spec: specs/03-gold-marts.md (decision #18)
CREATE OR REFRESH STREAMING TABLE inmet_weather
  COMMENT 'Bronze: raw INMET station hourly CSV lines (metadata + data, all STRING) + ingestion metadata.'
AS SELECT
  *,
  'INMET dados históricos'  AS _source,
  current_timestamp()       AS _ingested_at,
  _metadata.file_path       AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/ampera_bronze/raw/inmet',
  format => 'csv',
  sep => ';',
  header => false,
  -- explicit schema: inference samples the 2-column metadata lines at the top of each file
  schema => '_c0 STRING, _c1 STRING, _c2 STRING, _c3 STRING, _c4 STRING, _c5 STRING, _c6 STRING, _c7 STRING, _c8 STRING, _c9 STRING, _c10 STRING, _c11 STRING, _c12 STRING, _c13 STRING, _c14 STRING, _c15 STRING, _c16 STRING, _c17 STRING, _c18 STRING, _c19 STRING',
  encoding => 'ISO-8859-1',
  recursiveFileLookup => true
);
