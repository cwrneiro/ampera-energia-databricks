# 01 — Ingestion & Bronze

## Goal

Land raw data from every source into `ampera_catalog.ampera_bronze`, as ingested (minimal
transformation), with `_source`, `_ingested_at`, `_source_file` metadata. Batch only (decision #7);
24-month window (decision #14).

## Sources → bronze tables (all built and green)

| Bronze table | Source | How it lands | Rows |
|---|---|---|---|
| `ons_generation` | ONS `geracao-usina-2` monthly parquet | HTTP → volume → Auto Loader | 12.1M |
| `siga_plants` | ANEEL SIGA snapshot CSV | HTTP → volume → Auto Loader (all STRING) | 25,045 |
| `ons_conjunto_member` | ONS `usina_conjunto` (spec 09) | HTTP → volume | 2,143 |
| `ons_member_generation_wind` / `_solar` | ONS `restricao_coff_{eolica,fotovoltaica}_detail` (spec 09) | HTTP → volume | 36.4M / 16.7M |
| `ccee_pld_horario` | CCEE PLD horário yearly CSV | **browser download** → volume (decision #19) | 96,576 |
| `open_meteo_weather` | Open-Meteo archive (ERA5), JSON per cell × month | `scripts/fetch_open_meteo.py` → volume | 469 cells × month |
| `inmet_weather` | INMET yearly station archives (CSV) | HTTP (browser user-agent) → volume, explicit 20-col schema | ~14M lines |

Raw files live in `/Volumes/ampera_catalog/ampera_bronze/raw/<source>/` (and locally in `data/`,
gitignored). Resource URLs come from each portal's CKAN `package_show` API (ONS, ANEEL).

## Confirmed columns & quirks

- **ONS generation:** `din_instante` (hourly, local Brasília time), `id_subsistema` (N/NE/S/SE),
  `id_estado` (UF), `cod_modalidadeoperacao`, `nom_tipousina`, `nom_tipocombustivel` (fuel),
  `nom_usina`, `id_ons`, `ceg`, `val_geracao`. `val_geracao` is a dot-decimal STRING up to 2026-04
  and a DOUBLE from 2026-05 (Auto Loader rescues those into `_rescued_data`; silver reads either).
  Missing CEG is the literal `'-'` (49.7% of plants). From 2026-05 names are uppercased.
- **SIGA:** `;`-delimited, utf-8-sig, comma decimals. Name `NomEmpreendimento`, CEG `CodCEG`, UF
  `SigUFPrincipal`, type `SigTipoGeracao`, capacity `MdaPotenciaFiscalizadaKw`, lat/long
  `NumCoordNEmpreendimento` / `NumCoordEEmpreendimento` (100% populated → point map).
- **CEG:** never joins raw (ONS `.01` vs SIGA `.1`); normalizing the last segment → 92.5%.
- **Solar member detail:** a flag column is BOOLEAN in the 2024 files and INT later → two append
  flows (schema hints didn't help). **INMET:** each file starts with an 8-line metadata header, so
  schema inference must be bypassed; times are UTC; radiation in kJ/m².

## Acceptance criteria

- ✓ Bronze tables exist for generation, registry, prices and weather with ingestion metadata, and
  row counts match the source files.
- ✓ Confirmed column lists recorded above (CEG in ONS: yes, partly; lat/long in SIGA: yes).

## Operational notes

- PLD refresh is manual: drop new `pld_horario_<year>.csv` files into `.../raw/ccee_pld/`.
- Open-Meteo history fills in over ~3 daily runs of the fetch script (free-tier limit); upload
  each completed month directory to `.../raw/open_meteo/`. INMET's 2026 archive ends 31-Aug-2026.
