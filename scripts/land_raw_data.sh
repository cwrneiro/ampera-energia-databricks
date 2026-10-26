#!/usr/bin/env bash
# Land the raw public data in the volume (README "Reproduce" step 3; spec 01). Window: 24 months,
# 2024-10 … 2026-09 (decision #14) — to move it, change MONTHS below and FIRST/LAST in
# scripts/fetch_open_meteo.py. Every source needs at least one file before the first pipeline run (a
# streaming table can't infer a schema from an empty folder). Downloads several GB into data/raw/land.
# Usage: scripts/land_raw_data.sh [profile]
set -euo pipefail
P=${1:-${DATABRICKS_CONFIG_PROFILE:-DEFAULT}}
cd "$(dirname "$0")/.."
bv() {  # bundle variable from targets/dev.yml; an empty value aborts
  local v; v=$(databricks bundle validate -p "$P" -o json | jq -r ".variables.$1.value // empty")
  [ -n "$v" ] || { echo "bundle validate returned no value for '$1' — fill targets/dev.yml" >&2; exit 1; }
  echo "$v"
}
CAT=$(bv catalog)
V=dbfs:/Volumes/$CAT/ampera_bronze/raw
S3=https://ons-aws-prod-opendata.s3.amazonaws.com/dataset
MONTHS=$(python3 -c "print(' '.join(f'{y}_{m:02d}' for y in range(2024, 2027) for m in range(1, 13) if (2024, 10) <= (y, m) <= (2026, 9)))")
mkdir -p data/raw/land && cd data/raw/land

echo "== ONS hourly generation, per-member wind/solar detail (monthly parquet), complex membership"
for ym in $MONTHS; do
  curl -fsSO $S3/geracao_usina_2_ho/GERACAO_USINA-2_$ym.parquet
  curl -fsSO $S3/restricao_coff_eolica_detail_tm/RESTRICAO_COFF_EOLICA_DETAIL_$ym.parquet
  curl -fsSO $S3/restricao_coff_fotovoltaica_detail_tm/RESTRICAO_COFF_FOTOVOLTAICA_DETAIL_$ym.parquet
done
curl -fsSO $S3/usina_conjunto/RELACIONAMENTO_USINA_CONJUNTO.parquet
for f in GERACAO_USINA-2_*;                    do databricks fs cp --overwrite $f $V/ons/              -p "$P"; done
for f in RESTRICAO_COFF_EOLICA_DETAIL_*;       do databricks fs cp --overwrite $f $V/ons_member_wind/  -p "$P"; done
for f in RESTRICAO_COFF_FOTOVOLTAICA_DETAIL_*; do databricks fs cp --overwrite $f $V/ons_member_solar/ -p "$P"; done
databricks fs cp --overwrite RELACIONAMENTO_USINA_CONJUNTO.parquet $V/ons_conjunto_member/ -p "$P"

echo "== ANEEL SIGA registry (URL from the CKAN API, so it survives resource-id changes)"
curl -fsSL -o siga-empreendimentos-geracao.csv "$(curl -fsS 'https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=siga-sistema-de-informacoes-de-geracao-da-aneel' \
  | jq -r '.result.resources[].url | select(endswith("/siga-empreendimentos-geracao.csv"))')"
databricks fs cp --overwrite siga-empreendimentos-geracao.csv $V/siga/ -p "$P"

echo "== INMET station archives (yearly zip; needs a browser user agent)"
for y in 2024 2025 2026; do
  curl -fsSL -A 'Mozilla/5.0' -o inmet_$y.zip https://portal.inmet.gov.br/uploads/dadoshistoricos/$y.zip
  mkdir -p inmet/$y && unzip -jqo inmet_$y.zip -d inmet/$y
done
databricks fs cp -r --overwrite inmet $V/inmet -p "$P"

echo "== Open-Meteo seed: one cell is enough for schema inference (full history = README step 6)"
cd ../../..
mkdir -p data/raw/open_meteo
[ -f data/raw/open_meteo/cells.json ] || echo '[{"lat": "-25.5", "lon": "-54.5", "plants": "1"}]' > data/raw/open_meteo/cells.json
python3 scripts/fetch_open_meteo.py --budget 200
databricks fs cp -r --overwrite data/raw/open_meteo/raw $V/open_meteo -p "$P"

cat <<EOF

== Manual step: CCEE PLD (CCEE blocks scripted clients — don't automate it)
In a browser, download "PLD horário" for 2024, 2025 and 2026 from the CCEE open-data portal
(pld_horario_<year>.csv), then for each file:
  databricks fs cp pld_horario_<year>.csv $V/ccee_pld/ -p $P
The free Open-Meteo API is for non-commercial use only (decision #18).
Next: scripts/run_first_refresh.sh $P
EOF
