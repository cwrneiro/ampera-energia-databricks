"""Live check of client row-level security (spec 17): `python tests/test_rls_live.py`.

Runs SQL on the warehouse twice: as a test service principal mapped to a client (OAuth M2M from
AMPERA_CLIENT_SP_ID / AMPERA_CLIENT_SP_SECRET, kept in the gitignored .env) and as staff (the CLI
profile in DATABRICKS_CONFIG_PROFILE). The client must see exactly its seed portfolio in each of the five
row-filtered gold tables and be denied everything else; staff must see every plant. With GENIE_SPACE_ID
set it also asks Genie, as the client, how many plants it sees. Needs WAREHOUSE_ID and, off the demo
catalog, CATALOG. Skips without the client credentials.
"""
import csv
import os

SEED = os.path.join(os.path.dirname(__file__), "..", "src", "seed", "client_portfolio.csv")
CLIENT = os.environ.get("AMPERA_CLIENT", "Ventos do Nordeste Participações")
TABLES = ["fact_generation_hourly", "generation_daily", "plant_location", "curtailment_daily", "curtailment_narrative"]
DENIED = ["ampera_gold.reconciliation_monthly", "ampera_serving.generation_daily", "ampera_silver.dim_plant",
          "ampera_gold.client_plant_access"]


def portfolio():
    return {r["plant_id"] for r in csv.DictReader(open(SEED, encoding="utf-8")) if r["cliente"] == CLIENT}


def clients():
    from databricks.sdk import WorkspaceClient
    staff = WorkspaceClient()
    client = WorkspaceClient(host=staff.config.host, client_id=os.environ["AMPERA_CLIENT_SP_ID"],
                             client_secret=os.environ["AMPERA_CLIENT_SP_SECRET"], auth_type="oauth-m2m")
    return staff, client


def run(w, sql):
    """Rows as lists, or the error message."""
    r = w.statement_execution.execute_statement(sql, warehouse_id=os.environ["WAREHOUSE_ID"], wait_timeout="50s")
    if r.status.error:
        return r.status.error.message
    return (r.result.data_array or []) if r.result else []


def test_client_sees_only_its_plants():
    if not os.environ.get("AMPERA_CLIENT_SP_ID"):
        print("skip live RLS check (AMPERA_CLIENT_SP_ID unset; see .env)")
        return
    cat, mine = os.environ.get("CATALOG", "ampera_catalog"), portfolio()
    staff, client = clients()
    for t in TABLES:
        got = run(client, f"SELECT DISTINCT plant_id FROM {cat}.ampera_gold.{t}")
        assert isinstance(got, list), f"client denied on {t}: {got}"
        seen = {r[0] for r in got}
        assert seen and seen <= mine, f"{t}: client sees plants outside its portfolio: {sorted(seen - mine)[:5]}"
        everyone = int(run(staff, f"SELECT count(DISTINCT plant_id) FROM {cat}.ampera_gold.{t}")[0][0])
        assert everyone > len(seen), f"{t}: staff should see all plants ({everyone})"
        print(f"ok {t}: client {len(seen)} of {len(mine)} portfolio plants; staff {everyone}")
    for t in DENIED:
        got = run(client, f"SELECT 1 FROM {cat}.{t} LIMIT 1")
        assert isinstance(got, str) and ("PERMISSION" in got.upper() or "INSUFFICIENT" in got.upper()), (t, got)
        print(f"ok denied {t}")
    if os.environ.get("GENIE_SPACE_ID"):
        m = client.genie.start_conversation_and_wait(os.environ["GENIE_SPACE_ID"],
                                                     "Quantas usinas distintas existem em plant_location?")
        q = next((a for a in m.attachments or [] if a.query), None)
        assert q, f"Genie gave no query: {m.attachments}"
        res = client.genie.get_message_attachment_query_result(os.environ["GENIE_SPACE_ID"], m.conversation_id, m.id,
                                                               q.attachment_id).statement_response
        print(f"ok Genie as client: {q.query.query!r} -> {res.result.data_array}")
        assert int(res.result.data_array[0][0]) <= len(mine)


if __name__ == "__main__":
    test_client_sees_only_its_plants()
    print("ok")
