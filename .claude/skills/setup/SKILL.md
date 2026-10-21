---
name: setup
description: Interactive setup interview that configures and deploys this repo in the user's Databricks workspace by walking SETUP.md. Trigger: /setup, "set this up in my workspace", "configure for our environment".
---

# /setup — interview over SETUP.md

This is a **convenience layer over `SETUP.md`**, which is the canonical procedure. Follow its
sections in order and run its commands. Don't invent steps. If the two ever disagree, `SETUP.md`
wins: fix this skill to match.

## Resume first

Progress lives in `handoff/setup-state.json` (gitignored), shaped like
`{"target": "...", "profile": "...", "done": ["1", "2", ...], "values": {...}}`. If the file exists,
summarize what's collected and done, then ask (AskUserQuestion) whether to resume or start over.
Update the file after every section.

## Interview rules

- **One section per turn.** Use AskUserQuestion, and offer **discovered** values as the options:
  - profile ← `databricks auth profiles` (never auto-select; the user picks)
  - catalog ← `databricks catalogs list --profile <p>`, plus "create new"
  - warehouse ← `databricks warehouses list --profile <p>`
  - Lakebase project ← `databricks postgres list-projects --profile <p>`, plus "create new"
  - users group ← `databricks groups list --profile <p>`
  - target name, refresh cadence, failure e-mail: free text through "Other"
- **Validate cheap checks** and report ✅ found / ⚠️ missing / ⏭️ skipped. Missing is a warning. Never
  claim a check you didn't run.
- **Additive artifacts only:** `targets/<target>.yml` (from `targets/customer.yml.example`),
  `targets/<target>.geniespace.json` (SETUP §3) and `handoff/RUNBOOK-<target>.md`: the SETUP §8
  owner table, filled in, plus the chosen values. The only edit to an existing file is
  `LAKEBASE_ENDPOINT` in `app/app.yaml`, and only for a non-default Lakebase project (SETUP §6.4).
  It needs its own confirmation.
- **Confirm the full payload** (show the filled `targets/<target>.yml`) before writing it.
- **Confirm again before every outward-facing step:** UC DDL (§2), Lakebase create (§4), uploads
  (§5), `bundle deploy` / `bundle run` (§6), synced tables (§6.2), GRANTs (§6.6–7). One
  confirmation covers one step.
- §5 CCEE and the Open-Meteo license note need the user's own action. Explain them and wait.
- Finish with §8: run the offline checks, tick the go-live checklist with the user, and write the
  runbook.
