# 14 — App: curtailment, ai_decide queue, Genie chat

## Goal

Surface the ML and GenAI results to the business in the existing PT-BR app, and let users ask
Genie from any page. Decisions #36–#37.

## Design

- **Curtailment sheet** (`#/curtailment`): monthly curtailed energy and R$ lost by fonte; top-25
  plants by R$ lost (click → Usina); model vs ONS hours side by side. Reads
  `ampera_gold_lb.curtailment_daily` via `/api/curtailment`.
- **Usina sheet:** for EOL/SOL plants, daily actual vs expected (model) with curtailed energy.
- **Reconciliação sheet:** `ai_decide` block — applied matches and the review queue with each
  candidate's probability (`/api/reconciliation/ai`, `ampera_gold_lb.reconciliation_ai_review`).
- **Genie chat:** slide-out panel on every page (`POST /api/genie`). On-behalf-of-user
  (`user_api_scopes: [dashboards.genie]`, `x-forwarded-access-token`), so UC grants apply per user.
  Each answer shows Genie's text, a collapsible SQL block, and the result as a Recharts chart picked
  by column types (date → line, category + number → bar, two numbers → scatter, else table) with
  a chart/table toggle. Follow-ups stay in the same Genie conversation.

## Acceptance

- `/api/curtailment` totals equal `SUM(mwh_restrito)` in `gold.curtailment_daily` for the filter.
- A chat question returns SQL + rows and renders a chart; the API transcript is in `evidence/`.
