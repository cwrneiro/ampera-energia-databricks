# 14 — App: curtailment, ai_decide queue, Genie chat

## Goal

Surface the ML and GenAI results to the business in the existing PT-BR app, and let users ask
Genie from any page. Decisions #36–#37.

## Design

- **Curtailment sheet** (`#/curtailment`): monthly curtailed energy and R$ lost by fonte; top-25
  plants by R$ lost (click → Usina); model vs ONS hours side by side. Reads
  `ampera_gold_lb.curtailment_daily` via `/api/curtailment`. Filters on the sheet: period, UF and
  fonte (Eólica / Solar / Todas only); a fonte picked on another sheet that the model doesn't cover
  (e.g. HID) reads as Todas here, so what is applied is what is on screen.
- **Usina sheet:** for EOL/SOL plants, daily actual vs expected (model) with curtailed energy. Before
  the curtailment synced table exists, `/api/plant` returns an empty curtailment list (no 500).
- **Reconciliação sheet:** `ai_decide` block — applied matches and the review queue with each
  candidate's probability (`/api/reconciliation/ai`, `ampera_gold_lb.reconciliation_ai_review`).
  The state is the plant's final `match_method`, not ai_decide's confidence: `ai_decide` → Aplicada,
  `override` → Resolvida · manual, `fuzzy` → Resolvida · fuzzy, else Revisar. The review count and the
  "em jogo" MWh cover Revisar rows only; resolved rows highlight the plant the pipeline used.
- **Genie chat:** slide-out panel on every page (`POST /api/genie`). On-behalf-of-user
  (`user_api_scopes: [dashboards.genie]`, `x-forwarded-access-token`), so UC grants apply per user.
  Inside Databricks Apps (`DATABRICKS_APP_NAME` set) a missing user token is a 401 "Autorização do
  usuário não concedida" — never a fallback to the app's service principal; locally the CLI profile is
  used. SDK errors map by type: permission denied → 403, unauthenticated → 401, anything else
  (including fetching the query result) → 502 with Genie's message.
  Each answer shows Genie's text, a collapsible SQL block, and the result as a Recharts chart picked
  by column types (date → line, category + number → bar, two numbers → scatter, else table) with
  a chart/table toggle. Follow-ups stay in the same Genie conversation; "Nova conversa" drops any
  reply still in flight. Chart series use synthetic keys (`s0`, `s1`, …) with the label as the name,
  so names with dots plot. The closed drawer is `inert` (no Tab stops, hidden from assistive tech).

## Acceptance

- `python3 tests/test_app_api.py`: Genie runs as the forwarded user (401 in Apps without a token,
  CLI profile locally), typed errors (403 / 401 / 502), Usina loads without the curtailment table.
- `/api/curtailment` totals equal `SUM(mwh_restrito)` in `gold.curtailment_daily` for the filter.
- A chat question returns SQL + rows and renders a chart; the API transcript is in `evidence/`.
