-- Bronze: raw Open-Meteo (ERA5) hourly weather, one JSON file per 0.25° plant cell × month, as
-- returned by the API (scripts/fetch_open_meteo.py). The requested cell is in the file name.
-- Spec: specs/03-gold-marts.md (decision #18)
CREATE OR REFRESH STREAMING TABLE open_meteo_weather
  COMMENT 'Bronze: raw Open-Meteo ERA5 hourly weather per plant grid cell and month (API JSON as returned).'
AS SELECT
  *,
  'Open-Meteo archive (ERA5)'  AS _source,
  current_timestamp()          AS _ingested_at,
  _metadata.file_path          AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/bronze/raw/open_meteo',
  format => 'json',
  multiLine => true,
  recursiveFileLookup => true
);
