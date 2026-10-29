# Ampera Energia Analytics — Curtailment losses in R$, per plant, on one trusted plant ID

*Business deck for two named buyers, each read against the metric they are paid on. Every number
below is taken from a committed, text-readable run in [`evidence/`](../evidence/). Industry: Energy &
Utilities, Brazilian renewables.*

| Buyer | Measured on | What this build moves |
|---|---|---|
| **Diretor Comercial** (Head of Commercial, executive sponsor) | New data-product revenue (ARR) and client renewal rate | A per-plant "R$ lost to curtailment" product that survives client diligence |
| **Head of Data & Analytics** (domain owner) | Time-to-launch of a new data product and the analyst ticket backlog | Plant matching drops from weeks of spreadsheet work to one refresh run; self-service questions leave the ticket queue |

---

## 1. The outcome, up front

**R$ 8.4 bi of wind and solar output was cut in 24 months. We can now say which plant lost how much,
in R$, from data you already own.**

| What the business gets | Result | Source |
|---|---|---|
| One plant ID across ONS and ANEEL SIGA | **99.97% of plant-level energy resolved** (0.03% unmatched; target < 5%) | `evidence/03_medallion_tables.txt` |
| Curtailment valued per plant | **65.8 TWh lost, R$ 8.4 bi** at hourly PLD, 24 months, 1,598 plants | `evidence/04_ml_curtailment.txt` |
| An estimate better than the grid operator's own | Capacity-factor error **0.088 vs 0.098 (wind), 0.013 vs 0.015 (solar)**, on 6 held-out months (Apr–Sep 2026) | `evidence/notebooks/train_curtailment.ipynb` |
| Answers in plain Portuguese | Genie + in-app chat on the same governed numbers | `evidence/08_genie_conversations.json` |

*Why it matters now: ONS has been ordering wind and solar plants to cut output at scale in the
Northeast in 2025–26. Owners and traders currently see it as a vague "lost generation", not as money.*

---

## 2. The problem (illustrative voice of each stakeholder)

- **Diretor Comercial** (ARR, renewals): "My clients ask what curtailment cost them. I answer with a
  range and a caveat. I can't put a price on that, and it won't get a renewal signed."
- **Head of Data & Analytics** (time-to-launch, ticket backlog): "ONS and SIGA don't join. CEG formats
  differ, ONS mixes plants with wind/solar complexes and state totals, and some plants have no CEG.
  Every new product starts with weeks of manual matching, and every client question becomes a ticket."

Two blockers, one root cause: **no single, trusted plant ID**.

### Challenges, and what answers each

| Challenge today | Databricks answer | Measured result |
|---|---|---|
| Analysts jump between 5 platforms (ONS, ANEEL SIGA, CCEE, Open-Meteo, INMET) and stitch them by hand | Lakeflow Declarative Pipeline, one medallion | 8 datasets, ~79 M raw rows in one governed pipeline |
| No trusted plant ID: ONS and SIGA don't join | CEG normalization, complex splitting, fuzzy match, `ai_decide` | 99.97% of plant-level energy resolved |
| Manual matching: weeks per new product | Matching is a pipeline with confidence scores and an override table | One refresh run |
| Curtailment invisible in R$ | ML estimate of unconstrained output, valued at hourly PLD | 65.8 TWh, R$ 8.4 bi (lower bound) |
| No estimate of what a plant would have produced | Per-technology model in MLflow + UC | Beats ONS's own estimate on held-out months |
| No self-service: every question is an analyst ticket | Genie Agent + in-app chat, PT-BR | Generated SQL shown, UC grants per person |
| Inconsistent numbers depending on who ran the query | Unity Catalog, one governed source | 1,404.19 TWh identical in SQL, app and Genie |
| Slow time-to-insight, team stuck on plumbing | Scheduled refresh job, quality gates | Failed expectations stop the refresh |

---

## 3. Impact and value

| KPI | Before | After (measured on 24 months) |
|---|---|---|
| Plant-level generation with a unique plant ID | Partial; manual matching | **99.97%**; totals tie to the published ONS total within ±2% every month (1,404.19 TWh, identical in SQL, app and Genie) |
| Curtailment per plant | Not available in R$ | **Wind 41.6 TWh / R$ 5.7 bi (16.5% of expected output); solar 24.2 TWh / R$ 2.6 bi (28.2%)** |
| Trust in the AI step | n/a | **91% accuracy, 100% precision for auto-applied matches** (blind test, CEG hidden); the rest go to a human queue |
| Time to a new answer | Analyst + SQL | Natural-language question in Portuguese, generated SQL shown |

**Read the R$ figure as "at least".** The flag threshold is tuned for 80% precision against ONS's own
constrained-off flags; recall is 41% (wind) and 81% (solar), so real losses are larger than reported.
We chose to under-claim rather than risk a number a client can challenge.

**What each stakeholder gets**
- **Diretor Comercial → ARR and renewals:** a new sellable product, "R$ lost per plant", for generators,
  traders and associations (1,598 plants valued, R$ 8.4 bi lower bound). Lineage runs end to end
  (bronze → model → app), which is what a client asks for in diligence before renewing.
- **Head of Data & Analytics → time-to-launch and ticket backlog:** matching becomes a pipeline, not a
  spreadsheet (CEG first, fuzzy name second, AI third, a confidence score on every row, an override
  table that always wins). A new product starts from one refresh run instead of weeks of matching, and
  questions in Portuguese go to Genie instead of the analyst queue.

---

## 4. How it works — one Databricks platform, six stages

```
Public files ──▶ Lakeflow Declarative Pipeline ──▶ Unity Catalog ──▶ ML + GenAI ──▶ Lakebase ──▶ App + Genie
 ONS, SIGA,       bronze → silver → gold,           grants, tags,     curtailment   synced       FastAPI+React
 CCEE, weather    17 quality expectations           lineage, UC model model, ai_decide tables       (PT-BR), Genie chat
```

| Stage | Databricks capability | What it does here |
|---|---|---|
| Ingest | Lakeflow Declarative Pipelines, Auto Loader | 5 platforms, 8 datasets, ~79 M raw rows, bronze → silver → gold |
| Govern | Unity Catalog | Layer schemas, table comments, tags, `ampera_analysts` reads gold only, model in UC, lineage; **row filter: a generator client sees only its own plants** |
| Intelligence (ML) | MLflow + UC model registry | Per-technology gradient-boosting model of unconstrained output; scored every refresh; **drift check retrains a challenger, promoted only if it beats the champion** |
| Intelligence (GenAI) | `ai_decide`, `ai_query` | Places the plants the rules cannot; **writes a grounded PT-BR loss explanation per plant**; both stored once, so refreshes are deterministic |
| Serve | Lakebase (autoscaling Postgres) | 7 synced tables; the app never queries the lakehouse; scale-to-zero |
| Ask | Genie Agent | PT-BR instructions, 39 benchmark questions, curated SQL; clients get answers about their plants only |
| Surface | Databricks Apps | 5 sheets + map + chat that runs as the signed-in user, so UC grants apply per person; client users see only their portfolio |

---

## 5. The reconciliation, step by step

1. **CEG match** — normalize `.01` vs `.1`; links the bulk of energy (910 TWh).
2. **Complex splitting** — ONS wind/solar complexes become member plants (measured, not guessed).
3. **Fuzzy name** — same state and fuel; numerals must match ("Prosperidade III" never becomes "II").
4. **`ai_decide`** — a calibrated choice among 3 candidates or *none* for what remains.
5. **Human review** — anything under 0.9 confidence lands in an in-app queue; overrides always win.

Honest finding: the first AI pass answered *none* for all 33 unresolved plants. Adding per-candidate
evidence to the prompt (name similarity, same registry number, same type) fixed it; the change and
the before/after are in `specs/12-genai-reconciliation.md`.

---

## 6. How it was built: tools, workflow, trade-offs

**AI tools**
- Isaac (Claude Code) + tmux, with Databricks skills (core, pipelines, Lakebase, apps, Genie, and others).
- Impeccable design skill for the frontend, using brand tokens.
- Review passes (code review plus Isaac Review) and parallel read-only agents that audited git history for secrets before publishing.

**Workflow**
- Interview first, then 14 small one-page specs, each with explicit success criteria; one spec at a time.
- Decision log: every load-bearing choice (catalog, thresholds, stack) confirmed before implementation.
- Evidence over claims: every number traces to a committed run capture or executed notebook; each non-trivial transform has a runnable check.
- A handoff note kept current, so each fresh session resumed from the same state.

**Trade-offs**
| Decision | Cost | Why |
|---|---|---|
| Curtailment flag tuned for 80% precision | Recall 41% (wind), 81% (solar); R$ 8.4 bi is a lower bound | A number a client can't challenge |
| `ai_decide` auto-applies only at confidence ≥ 0.9 | More plants go to the human queue | 100% precision in the blind test |
| AI verdicts stored once per plant and prompt | Less freshness | Repeatable numbers on every refresh |
| Rules before AI (CEG, complexes, fuzzy, then AI) | More pipeline stages | The AI only touches what the rules can't place |
| Lakebase serves the app | A sync step | Low latency, scale-to-zero |
| Row filter in UC, same mapping in the app | Unfiltered serving copies of 4 tables (synced tables refuse a row-filtered source) | One client rule for Genie, SQL and the app, tested as a real client principal |
| Narratives must cite only numbers from the facts | A narrative that rounds or invents a figure is dropped, not shown | No AI-written number reaches a client that the data doesn't back |
| Promote a retrained model only if it beats the champion | A degraded champion keeps serving until a challenger wins | The headline never moves to a worse model |
| Public data only | Open-Meteo free tier is non-commercial; CCEE PLD refresh is manual | Production would use ERA5 via Copernicus |
| Scope cuts | No streaming ingest, 24-month window | Depth on reconciliation and curtailment |

---

## 7. Proof it ran

Everything is committed as plain text, not screenshots:

- `evidence/01_pipeline_run.txt` — expectations passed/failed per dataset, from the pipeline event log
- `evidence/02_job_runs.txt` — every task of the refresh job
- `evidence/03_medallion_tables.txt` — every table, row count and comment
- `evidence/04_ml_curtailment.txt`, `evidence/notebooks/train_curtailment.ipynb` — model, error vs ONS, threshold tuning
- `evidence/05_genai_ai_decide.txt`, `evidence/notebooks/eval_ai_decide.ipynb` — every AI verdict, blind evaluation
- `evidence/06_lakebase_serving.txt`, `evidence/07_app_api.txt` — sync state, API answers from Postgres
- `evidence/08_genie_conversations.json` — Genie answers with generated SQL and rows
- `evidence/09_tests.txt` — runnable checks, all passing, incl. client row-level security run as a client principal
- `evidence/10_genai_narrative.txt` — every curtailment narrative logged, how many passed the grounding check, examples with their facts

---

## 8. Risks we are upfront about

| Risk | Mitigation |
|---|---|
| Curtailment is a model estimate | Reported as a conservative lower bound; error measured against ONS on held-out months (Apr–Sep 2026) |
| AI mismatches | Only ≥ 0.9 confidence auto-applies (100% precision in the blind test); the rest is reviewed by a person |
| Public-data licensing | Open-Meteo free tier is non-commercial; production swaps in ERA5 via Copernicus |
| PLD download is manual | CCEE blocks scripted clients; documented one-step refresh |

---

## 9. Next steps

1. **30 days** — Ampera supplies its commercial PLD feed and validates 20 plants against client-reported losses.
2. **60 days** — Open the client view to the pilot client (already built: the same app and Genie, row-filtered to
   its plants, with a grounded loss explanation per plant); add a monthly per-plant statement on the same gold tables.
3. **90 days** — Extend the window beyond 24 months; add price forecasting on the same governed base.

**Ask:** the Diretor Comercial nominates one generator client to pilot the per-plant curtailment
statement (the first renewal conversation it supports); the Head of Data & Analytics owns the 20-plant
validation.

*Ampera Energia Analytics is fictional. Public data only (ONS, ANEEL SIGA, CCEE, Open-Meteo, INMET).*
