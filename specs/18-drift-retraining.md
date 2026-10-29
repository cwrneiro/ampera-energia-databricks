# 18 — ML: drift-triggered retraining

## Goal

Keep the curtailment model (spec 11) honest over time: when its held-out error against ONS's own
flags degrades, retrain, and promote the new version only if it is actually better. Decided
2026-10-27 after the FE review.

## Design

- **Check, every refresh** (`notebooks/monitor_curtailment`, after `score_curtailment`): on the trailing
  3 months that carry ONS constrained-off flags, per technology, for the champion that produced
  `gold.curtailment_hourly`. The two promises behind the headline (`curtailment_lib.drift_reasons`):
  - flag **precision ≥ 0.8** vs ONS (the "at least" framing), and
  - capacity-factor **MAE no worse than ONS's own estimate** on hours ONS did not flag.
  Either broken → `drift = true` (task value). Job parameter `force_drift=true` takes the same path
  without drift, because the demo's data is static and real drift won't occur.
- **Retrain:** `retrain_challenger` re-runs `notebooks/train_curtailment` with `split` = window start
  (train on everything before it, Y tuned on the window) and `alias = challenger`.
- **Promote** (`notebooks/promote_curtailment`): scores every labeled hour with champion and challenger
  (`src/curtailment_monitor.score`, same rules as scoring) and promotes only if, for every technology,
  the challenger (a) keeps precision ≥ 0.8 on the window, (b) has a strictly lower MAE than the
  champion on the window, and (c) does not lose flag precision over **all** labeled months
  (`curtailment_lib.beats`). The `challenger` alias is removed either way. Guard (c) was added after
  the first forced run (see Results).
- **Re-score:** only after a promotion, `rescore_curtailment` re-runs scoring, so the new champion's
  numbers reach gold, the Lakebase sync and the narrative (spec 16) in the same refresh.
- **Log:** every check (`kind = check`) and comparison (`kind = champion / challenger`, with the
  decision) is appended to `gold.curtailment_model_monitor`.
- `python3 tests/test_curtailment.py` covers `drift_reasons` and `beats`.

## Acceptance

- A normal refresh: check rows logged, `drift = false`, retrain/promote/re-score skipped.
- A `force_drift=true` refresh: challenger registered, comparison logged with the decision, champion
  changed only if the challenger won; evidence in `evidence/04`.

## Caveat

The monitor window sits inside the champion's own test months (Apr–Sep 2026), so the first checks
measure it on months whose Y it was tuned on: a sanity floor, not an independent test. With new
monthly ONS data the window moves past the training data and becomes a true held-out check.

## Results

- 2026-10-27, routine refresh: champion v2 on Jul–Sep 2026 — wind precision 0.861, MAE 0.0944 vs ONS
  0.1045; solar 0.852, 0.0119 vs 0.0134 → no drift; retrain / promote / re-score skipped.
- 2026-10-27, `force_drift=true`: challenger v3 (trained to 2026-06, Y tuned on Jul–Sep: wind 0.75, solar
  1.0) beat v2 on the window (wind MAE 0.0922 vs 0.0944, precision 0.820; solar 0.0111 vs 0.0119, 0.858)
  and was **promoted** under rules (a)+(b); the job re-scored (69.9 TWh / R$ 9.19 bi) and regenerated
  1,598 grounded narratives. But its wind Y, tuned on 3 months, flagged less precisely over all 24
  months (0.712 vs v2's 0.763), which weakens the "at least" reading of R$. **Rolled back to v2**
  (decision 2026-10-27, logged as `kind = rollback`) and added guard (c); under it v3 would be kept.
  Headline back to 65.8 TWh / R$ 8.4 bi; v2's narratives were already logged, so the rollback asked
  `ai_query` nothing.
