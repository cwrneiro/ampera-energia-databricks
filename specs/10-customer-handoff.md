# 10 — Customer handoff

## Goal

Anyone, with or without a coding agent, can deploy and run the project in their own workspace,
and the demo `dev` target stays as it is.

## Decisions (confirmed 2026-10-09)

| # | Decision | Choice |
|---|---|---|
| 23 | Portability | Tool-independent `SETUP.md` (canonical) + `targets/customer.yml.example` (field list) + `AGENTS.md`; Claude Code `/setup` skill is a convenience layer over SETUP.md |
| 24 | Output | Additive bundle target `targets/<target>.yml` (+ catalog-substituted Genie JSON); no deploy by the interview without confirmation |
| 25 | Validation | Cheap checks against the target workspace (✅/⚠️/⏭️), missing = warning |
| 26 | Catalog | Parameterized: transforms use `schema.table` (pipeline catalog = `var.catalog`), bronze volume paths `${catalog}` (pipeline `configuration`); Lakebase project = `var.lakebase_project` |

## Known limits

- `app/app.yaml` `LAKEBASE_ENDPOINT` is a literal (app runtime env can't read bundle variables) —
  the one file edit in SETUP §6.4.
- Raw landing (ONS/SIGA/INMET) is a documented command sequence, not a job; CCEE stays manual.
- The fresh-workspace path (SETUP §1–8 end to end) has not been run on an empty workspace.

## Acceptance criteria

- `databricks bundle validate` passes for `dev` and for a filled copy of the example target.
- After the catalog change, the demo pipeline runs green with unchanged totals (1,404.19 TWh).
