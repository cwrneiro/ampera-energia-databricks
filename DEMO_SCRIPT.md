# Demo script — Ampera (~25 min)

Flow: medallion → reconciliation → map → curtailment → plant → client view → Genie. Each beat has a **say** line (exec) and a
**show** (technical). The app and Genie are in PT-BR; the talk track is yours to translate.

## Before the demo (T−10 min)

- Workspace still alive and the medallion's last update is green.
- Open the app once: Lakebase suspends after 20 min idle and the first hit shows
  "Acordando o banco de dados…" (~10 s). Opening Visão geral also warms its ~5 s aggregate.
- Tabs ready: pipeline graph (`ampera_medallion`), Catalog Explorer on `ampera_catalog`,
  the app, the Genie space, and `ampera_gold.curtailment_model_monitor` in a SQL editor.

## 1. The problem (1 min)

**Say:** ONS publishes what plants generate; ANEEL SIGA says what each plant is and where it is.
They don't join. Nobody can say "this plant, on this map, generated this much".

## 2. Medallion (4 min) — pipeline graph

**Show:** bronze (raw ONS, SIGA, CCEE PLD, Open-Meteo, INMET as ingested) → silver (cleaned,
reconciled) → gold (the marts the app and Genie read). One schema per layer, a comment on each table.
Open the expectations: `has_plant_id` (fail), `plant_match_check` / `generation_plant_key_check`
(fail on double-counting), monthly balance ±2% (warn).
**Say:** one declarative pipeline, one refresh job; bad data stops it before it reaches the app.

## 3. Reconciliation — the heart (5 min) — app **Reconciliação** + `ampera_silver.plant_match`

**Say:** the join failed on *format* and *grain*, not on missing IDs.
- Format: ONS CEG ends `.01`, SIGA `.1` → normalized, **64.6% of MWh links on CEG**, confidence 1.0.
- Grain: ONS reports complexes (~20%) and state totals (~14%) as one series. Complexes are split into
  member plants: **96.9% measured**, 2.7% capacity-estimated (labeled "estimado").
- Fuzzy names (same UF + fuel, similarity ≥ 0.82, numerals must match) is a small safety net —
  "Prosperidade III" must never match "Prosperidade II" (a real false match we caught).
- `ai_decide` places what the rules can't (2 matches, 5.1 TWh), asked once per plant; the rest goes to the
  review queue on this sheet.
- **Plant-level unmatched: 0.03% of MWh** (target < 5%), kept with a stable surrogate id, never dropped.
**Show:** `match_method` + `confidence` columns; `plant_match_override` — a human fix wins over every
automatic rule (newest row wins), enforced by `plant_match_check` on every run.

## 4. Map (3 min) — app **Mapa**

**Show:** 1,973 located plants (85% of MWh); filter fonte = Eólica, UF = BA — the camera glides there.
**Say:** this map only exists because the reconciliation joined ONS generation to SIGA coordinates.
Click a plant → step 5.

## 5. Curtailment (3 min) — app **Curtailment**

**Say:** **R$ 8.4 bi** of wind and solar output was cut in 24 months (65.8 TWh). Read it as "at least":
the flag is tuned to 80% precision against ONS's own flags.
**Show:** monthly lost energy by fonte, top plants by R$ lost; click Canoa Quebrada → step 6.
**Technical aside:** every refresh a drift check scores the champion against ONS on the last 3 labeled
months (`curtailment_model_monitor`). We forced a retrain once: the challenger won on those months but
flagged less precisely over 24 months, so we rolled back and tightened the promotion rule.

## 6. Plant (2 min) — app **Usina**

**Show:** expected vs actual output with the curtailed hours hatched, and the **IA** paragraph under
"Curtailment (modelo)": a PT-BR explanation written by Claude from the gold numbers; every number in it
is checked against the facts before it is shown. Then daily series, captured PLD, modeled vs measured weather.
**Say:** price and weather are joined per hour and location in gold; served from Lakebase (Postgres,
autoscaling, scale-to-zero) via synced tables — the app never queries the lakehouse.
Back on **Visão geral**: captured vs average PLD by fonte — solar −22.8%, thermal +15.6%.

## 7. Client view (2 min) — same app, signed in as a client

**Say:** a generator client uses the same app and the same Genie space, and sees only its own plants.
**Show:** (needs a user mapped in `client_access`) header "Carteira Ventos do Nordeste Participações",
18 plants on the map, no Reconciliação sheet; Genie "quantas usinas existem?" → 18.
Without a client login: `evidence/09_tests.txt` (the RLS test run as a client service principal).
**Technical aside:** one rule, two enforcement points — a UC row filter for Genie/SQL, and the same
mapping applied by the app on Lakebase, because synced tables refuse row-filtered sources.

## 8. Genie (4 min) — Genie space

Ask, in order (all benchmarked):
1. "Quais as 10 usinas (CEG) que mais geraram no último ano?"
2. "Como evoluiu a geração mensal dos 5 maiores conjuntos eólicos?"
3. "Qual fonte captura o maior PLD? Compare PLD capturado e PLD médio."
4. "Quanto da geração foi reconciliada diretamente pelo CEG?"
5. "Explique o curtailment da usina Canoa Quebrada"
**Say:** same governed gold tables, curated instructions, 39 benchmark questions checked.
Show the generated SQL once for the technical audience.

## Close (1 min)

**Say:** two sources that don't join → one reliable `plant_id` → curtailment valued in R$ per plant, a
model that watches itself, an explanation a client can read, and a client view scoped to its own
plants — all on one platform, refreshed by one job.
