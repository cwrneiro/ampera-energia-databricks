-- Silver: hourly PLD per ONS subsystem code (N/NE/S/SE) in local Brasília time — the same clock and
-- region key as ampera_silver.generation_plant, so gold joins on (submercado, ts). HORA 0 = 00:00–01:00.
-- Spec: specs/03-gold-marts.md
CREATE OR REFRESH MATERIALIZED VIEW ampera_silver.price_pld_hourly (
  CONSTRAINT known_submercado EXPECT (submercado IN ('N', 'NE', 'S', 'SE')),
  CONSTRAINT plausible_pld    EXPECT (pld_rs_mwh BETWEEN 0 AND 5000)
)
  COMMENT 'Silver: hourly PLD (R$/MWh) per submercado (ONS subsystem code), local time.'
AS SELECT DISTINCT
  CASE trim(SUBMERCADO) WHEN 'NORTE' THEN 'N' WHEN 'NORDESTE' THEN 'NE'
                        WHEN 'SUL' THEN 'S'   WHEN 'SUDESTE' THEN 'SE' END       AS submercado,
  make_timestamp(int(substr(MES_REFERENCIA, 1, 4)), int(substr(MES_REFERENCIA, 5, 2)),
                 int(DIA), int(HORA), 0, 0)                                    AS ts,
  CAST(PLD_HORA AS DOUBLE)                                                     AS pld_rs_mwh
FROM ampera_bronze.ccee_pld_horario;
