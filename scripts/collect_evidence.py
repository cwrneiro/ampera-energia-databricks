"""Capture text-readable execution evidence into evidence/ (spec 15). Read-only: queries, API GETs,
Genie questions through the deployed app, test runs.

Usage: python3 scripts/collect_evidence.py [profile]      (warehouse/app/space ids discovered from the workspace)
"""
import datetime as dt
import json
import os
import subprocess
import sys

P = sys.argv[1] if len(sys.argv) > 1 else "<profile>"
CAT, WH, LB = "ampera_catalog", "<warehouse-id>", "ampera-demo"
ROOT = os.path.join(os.path.dirname(__file__), "..")
EV = os.path.join(ROOT, "evidence")


def cli(*args, js=True):
    r = subprocess.run(["databricks", *args, "-p", P] + (["-o", "json"] if js else []), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:500])
    return json.loads(r.stdout) if js else r.stdout


def sql(q):
    return cli("experimental", "aitools", "tools", "query", "-w", WH, q)


def table(rows):
    if not rows:
        return "(no rows)\n"
    cols = list(rows[0])
    w = {c: max(len(c), *(len(str(r.get(c))) for r in rows)) for c in cols}
    line = lambda r: "  ".join(str(r.get(c, "")).rjust(w[c]) for c in cols)  # noqa: E731
    return "\n".join([line({c: c for c in cols}), *map(line, rows)]) + "\n"


def write(name, title, body):
    with open(os.path.join(EV, name), "w") as f:
        f.write(f"# {title}\n# captured {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M UTC} from workspace profile {P}\n\n{body}")
    print("wrote evidence/" + name)


def section(q, label=None):
    return f"-- {label or ''}\n{q.strip()}\n\n{table(sql(q))}\n"


def pipeline_and_job():
    pid = next(p["pipeline_id"] for p in cli("pipelines", "list-pipelines") if p["name"] == "ampera_medallion")
    upd = cli("pipelines", "list-updates", pid)["updates"][0]
    body = f"pipeline ampera_medallion {pid}\nlatest update {upd['update_id']} state={upd['state']} cause={upd.get('cause')}\n\n"
    body += section(f"""SELECT origin.flow_name AS dataset, e.name AS expectation,
             sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
      FROM (SELECT origin, explode(from_json(details:flow_progress.data_quality.expectations,
                   'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
            FROM event_log('{pid}') WHERE event_type = 'flow_progress' AND origin.update_id = '{upd['update_id']}'
              AND details:flow_progress.data_quality.expectations IS NOT NULL)
      GROUP BY ALL ORDER BY dataset, expectation""", "data-quality expectations, latest update (event_log)")
    body += section(f"""SELECT origin.flow_name AS dataset, max(details:flow_progress.metrics.num_output_rows)::bigint AS output_rows,
             max_by(details:flow_progress.status::string, timestamp) AS final_status
      FROM event_log('{pid}') WHERE event_type = 'flow_progress' AND origin.update_id = '{upd['update_id']}'
      GROUP BY ALL ORDER BY dataset""", "flows of the latest update")
    write("01_pipeline_run.txt", "Lakeflow Declarative Pipeline — latest update, flows and expectations", body)

    job = next(j for j in cli("jobs", "list") if j["settings"]["name"] == "ampera_refresh")
    runs = cli("jobs", "list-runs", "--job-id", str(job["job_id"]), "--limit", "5")
    body = ""
    for r in runs:
        run = cli("jobs", "get-run", str(r["run_id"]))
        body += (f"run {run['run_id']}  {run['state'].get('result_state')}  params={run.get('job_parameters')}  "
                 f"start={dt.datetime.fromtimestamp(run['start_time'] / 1000, dt.timezone.utc):%Y-%m-%d %H:%M} UTC\n")
        for t in sorted(run["tasks"], key=lambda t: t.get("start_time") or 0):
            dur = ((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 60000
            body += f"   {t['task_key']:<30} {str(t['state'].get('result_state')):<10} {dur:6.1f} min\n"
        body += "\n"
    write("02_job_runs.txt", "Lakeflow Job ampera_refresh — recent runs and task results", body)


def medallion():
    tabs = sql(f"""SELECT table_schema, table_name, table_type, comment FROM {CAT}.information_schema.tables
                   WHERE table_schema LIKE 'ampera_%' AND table_name NOT LIKE '\\_\\_%'
                     AND table_name NOT LIKE 'event\\_log\\_%' ORDER BY 1, 2""")  # skip pipeline internals
    rows = []
    for t in tabs:
        n = sql(f"SELECT count(*) AS n FROM {CAT}.{t['table_schema']}.{t['table_name']}")[0]["n"]
        rows.append({"schema": t["table_schema"], "table": t["table_name"], "type": t["table_type"], "rows": n,
                     "comment": (t["comment"] or "")[:90]})
    body = table(rows) + "\n"
    body += section(f"""SELECT match_method, count(*) AS ons_series, round(sum(g.mwh) / 1e6, 2) AS twh
      FROM {CAT}.ampera_silver.plant_match m
      LEFT JOIN (SELECT ons_key, sum(mwh) AS mwh FROM {CAT}.ampera_silver.generation GROUP BY 1) g USING (ons_key)
      GROUP BY 1 ORDER BY twh DESC""", "reconciliation: every ONS series -> one plant_id (SUCCESS #1)")
    body += section(f"""SELECT round(100 * sum(CASE WHEN match_method = 'unmatched' THEN mwh END)
                   / sum(CASE WHEN match_method IN ('ceg', 'fuzzy', 'ai_decide', 'unmatched') THEN mwh END), 2) AS unmatched_pct_of_plant_level_mwh
      FROM {CAT}.ampera_gold.reconciliation_monthly WHERE grao = 'publicado'""", "target < 5%")
    body += section(f"SELECT round(sum(mwh) / 1e6, 2) AS total_twh, count(DISTINCT plant_id) AS plants, min(dia) AS de, max(dia) AS ate FROM {CAT}.ampera_gold.generation_daily",
                    "gold total (ties to the app)")
    body += section(f"""SELECT fonte, round(sum(mwh) / 1e6, 2) AS twh, round(sum(valor_rs) / 1e9, 2) AS valor_rs_bi,
             round(try_divide(sum(valor_rs), sum(mwh)), 2) AS pld_capturado FROM {CAT}.ampera_gold.generation_daily GROUP BY 1 ORDER BY 2 DESC""",
                    "generation by fonte with CCEE PLD enrichment")
    write("03_medallion_tables.txt", "Unity Catalog medallion — tables, row counts and reconciliation results", body)


def ml_genai():
    body = json.dumps({k: v for k, v in cli("registered-models", "get", f"{CAT}.ampera_gold.curtailment_expected_cf").items()
                       if k in ("full_name", "comment", "aliases", "created_at", "updated_at")}, indent=1) + "\n\n"
    for v in cli("model-versions", "list", f"{CAT}.ampera_gold.curtailment_expected_cf"):
        body += f"version {v['version']}  status={v.get('status')}  run_id={v.get('run_id')}  created={v.get('created_at')}\n"
    body += "\n" + section(f"""SELECT fonte, count(DISTINCT plant_id) AS plants, round(sum(mwh) / 1e6, 2) AS gen_twh,
             round(sum(mwh_restrito) / 1e3, 1) AS curtailed_gwh, round(sum(valor_rs_perdido) / 1e6, 1) AS lost_rs_millions,
             round(100 * sum(mwh_restrito) / sum(mwh_esperado), 2) AS pct_of_expected, max(model_version) AS model_version
      FROM {CAT}.ampera_gold.curtailment_hourly GROUP BY 1 ORDER BY 1""", "batch scoring output")
    body += section(f"""SELECT fonte, count_if(restrito_modelo AND restrito_ons) AS tp, count_if(restrito_modelo AND NOT restrito_ons) AS fp,
             count_if(NOT restrito_modelo AND restrito_ons) AS fn,
             round(count_if(restrito_modelo AND restrito_ons) / count_if(restrito_modelo AND restrito_ons IS NOT NULL), 3) AS precision_vs_ons,
             round(count_if(restrito_modelo AND restrito_ons) / count_if(restrito_ons), 3) AS recall_vs_ons
      FROM {CAT}.ampera_gold.curtailment_hourly GROUP BY 1 ORDER BY 1""", "model flag vs ONS constrained-off flag, all 24 months")
    body += section(f"""SELECT dia, round(mwh, 1) AS mwh, round(mwh_esperado, 1) AS mwh_expected, horas_restritas_modelo AS h_model,
             horas_restritas_ons AS h_ons, round(mwh_restrito, 1) AS mwh_lost, round(valor_rs_perdido) AS rs_lost
      FROM {CAT}.ampera_gold.curtailment_daily WHERE plant_id = (SELECT plant_id FROM {CAT}.ampera_gold.curtailment_daily
           GROUP BY 1 ORDER BY sum(valor_rs_perdido) DESC LIMIT 1) AND dia BETWEEN '2026-08-01' AND '2026-08-14' ORDER BY dia""",
                    "real model output: the top plant by R$ lost, two weeks")
    write("04_ml_curtailment.txt", "ML — curtailment model in UC, scoring output and agreement with ONS", body)

    body = section(f"""SELECT nom_usina, uf, tipo, ai_choice, ai_confidence, ai_accepted, a_nome, ai_prob_a, b_nome, ai_prob_b,
             c_nome, ai_prob_c, ai_prob_nenhum, match_method, plant_id
      FROM {CAT}.ampera_gold.reconciliation_ai_review ORDER BY ai_accepted DESC, ai_confidence DESC""",
                   "every ai_decide verdict in production (applied at confidence >= 0.9, else review queue)")
    body += section(f"""SELECT truth, ai_choice, count(*) AS n FROM {CAT}.ampera_silver.ai_decide_eval GROUP BY ALL ORDER BY ALL""",
                    "blind eval (CEG registry number hidden), confusion")
    write("05_genai_ai_decide.txt", "GenAI — ai_decide reconciliation verdicts and blind evaluation", body)


def lakebase_and_app():
    body = ""
    for t in ("generation_daily", "plant_location", "reconciliation_monthly", "reconciliation_ai_review", "curtailment_daily"):
        s = cli("postgres", "get-synced-table", f"synced_tables/{CAT}.ampera_gold_lb.{t}")
        st = s.get("status", {})
        body += f"{t:<26} source=ampera_gold.{t}  pipeline={st.get('pipeline_id')}  " \
                f"state={st.get('detailed_state')}  last_sync={json.dumps(st.get('last_sync', {}).get('delta_table_sync_info', {}))[:120]}\n"
    proj = cli("postgres", "get-project", f"projects/{LB}")
    body += f"\nLakebase project {LB}: pg_version={proj['status'].get('pg_version')}  default endpoint settings={proj['status'].get('default_endpoint_settings')}\n"
    write("06_lakebase_serving.txt", "Lakebase — synced tables (gold -> Postgres) and project", body)

    app = cli("apps", "get", "ampera-app")
    tok = cli("auth", "token")["access_token"]
    base = app["url"]

    def call(path, data=None):  # curl: python.org builds on macOS ship without CA certificates
        args = ["curl", "-sf", "-m", "180", "-H", f"Authorization: Bearer {tok}", "-H", "Content-Type: application/json"]
        r = subprocess.run(args + (["-d", json.dumps(data)] if data else []) + [base + "/api/" + path],
                           capture_output=True, text=True, check=True)
        return json.loads(r.stdout)
    body = f"app ampera-app  status={app['app_status']['state']}  compute={app['compute_status']['state']}  " \
           f"user_api_scopes={app.get('effective_user_api_scopes')}\nresources={json.dumps(app.get('resources'), ensure_ascii=False)}\n\n"
    ov = call("overview")
    body += f"GET /api/meta -> {json.dumps(call('meta'))}\n\nGET /api/overview -> kpis {json.dumps(ov['kpis'])}\n" \
            f"   fontes {json.dumps(ov['fontes'], ensure_ascii=False)[:900]}\n   top plants {json.dumps(ov['ranking_usinas'][:3], ensure_ascii=False)[:700]}\n\n"
    cu = call("curtailment", None)
    body += f"GET /api/curtailment -> {len(cu['serie'])} month×fonte rows; top plants:\n{json.dumps(cu['usinas'][:5], ensure_ascii=False, indent=1)}\n\n"
    ai = call("reconciliation/ai")
    body += f"GET /api/reconciliation/ai -> {len(ai)} verdicts, {sum(r['ai_accepted'] for r in ai)} applied\n\n"
    write("07_app_api.txt", "Databricks App — deployed app, API responses read from Lakebase", body)

    qs = ["Quanto as eólicas perderam por curtailment em 2026, em GWh e R$ milhões?",
          "Quais os 5 conjuntos que mais geraram em 2025?",
          "Geração solar por mês em 2025, em GWh",
          "Qual o PLD capturado por fonte em 2025?",
          "Quantas usinas foram reconciliadas pela IA (ai_decide)?"]
    out = []
    for q in qs:
        try:
            out.append({"pergunta": q, **call("genie", {"pergunta": q})})
        except Exception as e:  # keep the transcript honest
            out.append({"pergunta": q, "erro": str(e)})
    with open(os.path.join(EV, "08_genie_conversations.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote evidence/08_genie_conversations.json")


def tests():
    env = {**os.environ, "DATABRICKS_CONFIG_PROFILE": P, "DATABRICKS_WAREHOUSE_ID": WH, "GENIE_LIVE": "1"}
    body = ""
    for t in ("tests/test_reconciliation.py", "tests/test_genie_space.py"):
        r = subprocess.run([sys.executable, t], cwd=ROOT, capture_output=True, text=True, env=env)
        body += f"$ python3 {t}\n{r.stdout}{r.stderr}exit={r.returncode}\n\n"
    write("09_tests.txt", "Runnable checks — reconciliation logic and Genie benchmark SQL (live)", body)


if __name__ == "__main__":
    os.makedirs(EV, exist_ok=True)
    for step in (pipeline_and_job, medallion, ml_genai, lakebase_and_app, tests):
        try:
            step()
        except Exception as e:
            print(f"{step.__name__} FAILED: {e}")
