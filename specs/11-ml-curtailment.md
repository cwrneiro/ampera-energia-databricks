# 11 — ML: curtailment detection

## Goal

Quantify energy (MWh) and money (R$ at PLD) that Brazilian wind and solar plants lose to
curtailment (ONS "constrained-off"), per plant and month — Ampera's core product line — including
plants for which ONS publishes no curtailment flag. Decisions #29–#30 (00-overview).

## Design

- **Labels (no new source):** the ONS constrained-off *detail* files already in bronze
  (`ons_member_generation_{wind,solar}`) carry `flg_geracaorestrita` (ONS limited the plant) and
  `val_geracaoestimada` (ONS's own estimate). → `silver.curtailment_label_hourly` (plant-hour).
- **Features:** `gold.curtailment_features_hourly` (pipeline): EOL/SOL measured plant-hours, target
  capacity factor = MWh / SIGA capacity, Open-Meteo wind 100 m / irradiance, temperature, hour,
  month, UF, lat/lon, PLD, ONS label (NULL where not published).
- **Model:** one scikit-learn `HistGradientBoostingRegressor` per technology on the *unconstrained*
  capacity factor, plus each plant's mean training CF as a feature. Trained only on hours ONS did
  not flag; time split 2024-10…2026-03 train / 2026-04…2026-09 test. One MLflow pyfunc
  `ampera_gold.curtailment_expected_cf` in UC, alias `champion`.
- **Flag:** curtailed hour = expected CF ≥ 10% **and** actual < Y × expected. Y tuned per technology
  by F1 against ONS flags on the test months and stored as model-version tags (`y_eol`, `y_sol`) —
  frozen with the version, read by scoring.
- **Valuation:** MWh lost = expected − actual on flagged hours; R$ lost = MWh lost × hourly PLD.
- **Runs:** `notebooks/train_curtailment` (job param `train=true`) and `score_curtailment` (every
  refresh) in `ampera_refresh`, between the medallion and the Lakebase syncs (serverless SDP can't
  run Python UDFs). Scoring writes `gold.curtailment_hourly` (lakehouse/Genie) and
  `gold.curtailment_daily` (synced to Lakebase).

## Acceptance

- Test-month regression MAE reported next to ONS's own estimate's MAE (`evidence/`).
- Precision / recall / F1 of the flag vs ONS, per technology, reported; Y recorded on the version.
- `curtailment_daily` in Lakebase; app Curtailment sheet + Usina expected-vs-actual; Genie answers
  "quanto a usina X perdeu por curtailment".

## Results

_Filled after the first training run._
