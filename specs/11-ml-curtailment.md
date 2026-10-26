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
  month, UF, lat/lon, PLD, ONS label (NULL where not published), plus ONS's at-plant measured wind /
  irradiance where it exists (NULL elsewhere; added after the first run, see Results).
- **Model:** one scikit-learn `HistGradientBoostingRegressor` per technology on the *unconstrained*
  capacity factor, plus each plant's mean training CF as a feature. Trained only on hours ONS did
  not flag; time split 2024-10…2026-03 train / 2026-04…2026-09 test. One MLflow pyfunc
  `ampera_gold.curtailment_expected_cf` in UC, alias `champion`.
- **Flag:** curtailed hour = expected CF ≥ 10% **and** actual < Y × expected. Y tuned per technology
  on the test months against ONS flags: **best recall with precision ≥ 0.8** (decision 2026-10-22; F1
  rewarded flagging every shortfall because ONS flags ~40% of hours). Stored as model-version tags
  (`y_eol`, `y_sol`) — frozen with the version, read by scoring.
- **Valuation:** MWh lost = expected − actual on flagged hours; R$ lost = MWh lost × hourly PLD.
- **One definition:** the flag, lost energy (never negative), valuation and the Y rule (best recall
  at precision ≥ 0.8, else max precision) live in `src/curtailment_lib.py`, imported by the train
  (pandas) and score (Spark) notebooks (the flag and valuation run as-is on Spark Columns; lost energy
  is mirrored there with `F.when`/`F.greatest`); `python3 tests/test_curtailment.py` checks a worked example
  (cf_exp 0.5, cf 0.2, Y 0.65, 10 MW, PLD 100 → flagged, 3.0 MWh, R$ 300).
- **Runs:** `notebooks/train_curtailment` (job param `train=true`) and `score_curtailment` (every
  refresh) in `ampera_refresh`, between the medallion and the Lakebase syncs (serverless SDP can't
  run Python UDFs). Scoring writes `gold.curtailment_hourly` (lakehouse/Genie) and
  `gold.curtailment_daily` (synced to Lakebase).

## Acceptance

- Test-month regression MAE reported next to ONS's own estimate's MAE (`evidence/`).
- Precision / recall / F1 of the flag vs ONS, per technology, reported; Y recorded on the version.
- `curtailment_daily` in Lakebase; app Curtailment sheet + Usina expected-vs-actual; Genie answers
  "quanto a usina X perdeu por curtailment".
- Coverage note: ONS's Oct–Dec 2024 solar detail files carry no restriction flag (0.9 M plant-hours);
  the model scores those hours anyway — that's where it adds coverage, not "plants ONS ignores".

## Results

- **Run 1** (2026-10-22, Open-Meteo weather only): test MAE of capacity factor 0.145 wind / 0.022 solar
  vs 0.098 / 0.015 for ONS's own estimate (which uses measured wind and power curves). F1-tuned Y
  hit the grid edge (0.9), flagging 37% of the wind hours ONS didn't flag: 56 TWh / R$ 9.4 bi lost
  for wind, inflated. → added ONS measured weather as a feature and the precision-floor rule.
- **Run 2:** see `evidence/`.
