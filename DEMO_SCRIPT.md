# Demo script — Ampera (~20 min)

Flow: medallion → reconciliation → map → plant → Genie. Each beat has a **say** line (exec) and a
**show** (technical). The app and Genie are in PT-BR; the talk track is yours to translate.

## Before the demo (T−10 min)

- Workspace still alive and the medallion's last update is green.
- Open the app once: Lakebase suspends after 20 min idle and the first hit shows
  "Acordando o banco de dados…" (~10 s). Opening Visão geral also warms its ~5 s aggregate.
- Tabs ready: pipeline graph (`ampera_medallion`), Catalog Explorer on `ampera_catalog`,
  the app, the Genie space.

## 1. The problem (1 min)

**Say:** ONS publishes what plants generate; ANEEL SIGA says what each plant is and where it is.
They don't join. Nobody can say "this plant, on this map, generated this much".

## 2. Medallion (4 min) — pipeline graph

**Show:** bronze (raw ONS, SIGA, CCEE PLD, Open-Meteo, INMET as ingested) → silver (cleaned,
reconciled) → gold (the marts the app and Genie read). One schema per layer, a comment on each table.
Open the expectations: `has_plant_id` (fail), `plant_match_check` / `generation_plant_key_check`
(fail on double-counting), monthly balance ±2% (warn).
**Say:** one declarative pipeline, one refresh job; bad data stops it before it reaches the app.

## 3. Reconciliation — the heart (5 min) — app **Reconciliação** + `silver.plant_match`

**Say:** the join failed on *format* and *grain*, not on missing IDs.
- Format: ONS CEG ends `.01`, SIGA `.1` → normalized, **64.6% of MWh links on CEG**, confidence 1.0.
- Grain: ONS reports complexes (~20%) and state totals (~14%) as one series. Complexes are split into
  member plants: **96.9% measured**, 2.7% capacity-estimated (labeled "estimado").
- Fuzzy names (same UF + fuel, similarity ≥ 0.82, numerals must match) is a small safety net —
  "Prosperidade III" must never match "Prosperidade II" (a real false match we caught).
- **Plant-level unmatched: 0.59% of MWh** (target < 5%), kept with a stable surrogate id, never dropped.
**Show:** `match_method` + `confidence` columns; `plant_match_override` — a human fix wins over every
automatic rule (newest row wins), enforced by `plant_match_check` on every run.

## 4. Map (3 min) — app **Mapa**

**Show:** 1,973 located plants (85% of MWh); filter fonte = Eólica, UF = BA — the camera glides there.
**Say:** this map only exists because the reconciliation joined ONS generation to SIGA coordinates.
Click a plant → step 5.

## 5. Plant (2 min) — app **Usina**

**Show:** daily series, captured PLD, modeled (Open-Meteo) vs measured (ONS/INMET) weather.
**Say:** price and weather are joined per hour and location in gold; served from Lakebase (Postgres,
autoscaling, scale-to-zero) via synced tables — the app never queries the lakehouse.
Back on **Visão geral**: captured vs average PLD by fonte — solar −22.8%, thermal +15.6%.

## 6. Genie (4 min) — Genie space

Ask, in order (all benchmarked):
1. "Quais as 10 usinas (CEG) que mais geraram no último ano?"
2. "Como evoluiu a geração mensal dos 5 maiores conjuntos eólicos?"
3. "Qual fonte captura o maior PLD? Compare PLD capturado e PLD médio."
4. "Quanto da geração foi reconciliada diretamente pelo CEG?"
**Say:** same governed gold tables, curated instructions, 32 benchmark questions checked.
Show the generated SQL once for the technical audience.

## Close (1 min)

**Say:** two sources that don't join → one reliable `plant_id` with a visible method and confidence →
an app and a natural-language agent on top, all on one platform, refreshed by one job.
