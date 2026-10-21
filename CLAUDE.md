# CLAUDE.md — Ampera Databricks Demo

**One-liner:** A full-stack Databricks demo for Ampera that reconciles Brazilian
power-plant generation data from ONS + ANEEL SIGA (which don't join directly) and serves it via
a Declarative Pipeline medallion, an autoscaling Lakebase, a FastAPI+React app with a map, and a
Genie Agent.

Read `specs/00-overview.md` for the goal and decision log, and `SUCCESS_CRITERIA.md` for the bar.
Work proceeds **one small spec at a time** (`specs/01..08`).

## First interaction: configured?

If `targets/` has no `*.yml` (only `customer.yml.example`), say one line — "Not configured for your
workspace yet — run `/setup` (or follow SETUP.md)." — and carry on with the request. Never block,
never auto-run setup. Setup rules for every agent: `AGENTS.md`.

## Databricks

- Workspace is the CLI profile **`<profile>`** — always pass `--profile <profile>`.
  Never auto-select another profile.
- Route Databricks work through the Databricks skills: load `databricks-core` first, then the
  matching product skill (databricks-pipelines, databricks-lakebase, databricks-apps,
  databricks-genie-agents, etc.).

## Tone & interaction style

- **Full-stack story, both audiences** (technical POC + exec pitch): every medallion layer must be
  demonstrable AND the app/Genie must look polished.
- **Plan the load-bearing decisions before implementing** them, and get explicit user confirmation
  (catalog/schema names, reconciliation thresholds, deployment targets). Carry the interview's
  verification habit into everyday work — don't let a key decision slide through implicitly.
- **Ask before adding a dependency.** Prefer stdlib / native Databricks / already-present libs.
- Terse status updates. Code first, short explanation after.
- **Language:** the **app UI is PT-BR** (customer-facing). Specs, docs, code, comments, and commit
  messages are **English**.

## Development style

- Lakeflow **Declarative Pipeline** (SDP) for ETL; a clean **bronze → silver → gold** medallion.
- Reconciliation is the heart of the demo — treat it with care: CEG where present, fuzzy surrogate
  key otherwise, with a confidence score and a manual-override table (see `specs/02`).
- Testing: every non-trivial transform (especially reconciliation/matching logic) leaves a runnable
  check — a small expectation/assertion or a `test_*` — the smallest thing that fails if the logic
  breaks. No heavy frameworks unless asked.
- **Spec discipline:** if implementation diverges from a spec, update the spec in the same change.
  New scope = a new small spec file, not a growing old one. Keep each spec ~1 page; split if larger.
- Frontend is built with the **Impeccable** skill, using the brand tokens in `specs/08-branding.md`.

## Session continuity contract

STATE.md is the handoff note a fresh session reads after `/clear`.

- At the start of every session, if STATE.md was not already injected into context, read it before
  doing anything else.
- Before finishing any work chunk, update STATE.md and commit it together with the work.
- STATE.md is a pointer, not a journal: keep it under half a page; history lives in `git log` and
  `specs/`.
- Enforcement: a `Stop` hook blocks ending a turn when tracked changes are newer than STATE.md on
  disk. It does NOT force a commit — commits happen at natural chunk boundaries. If blocked, refresh
  STATE.md (including any open question you're about to ask the user), don't create a WIP commit.

## Commit attribution

- End commit messages with: `Co-authored-by: Isaac <no-reply@databricks.com>`
- End PR descriptions with: `This pull request and its description were written by Isaac.`
