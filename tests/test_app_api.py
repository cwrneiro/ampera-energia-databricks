"""Runnable check for the app API (spec 06): `python tests/test_app_api.py`.

Offline: filter/grain helpers. Live (when PGHOST is set, see app/app.py docstring): the overview's
four groupings must tie to the same total as plant_location — the app never double counts.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "DEFAULT")
import app as A  # noqa: E402


def test_where():
    assert A.where(None, None, {"uf": None}) == ("", [])
    w, p = A.where(date(2026, 1, 1), None, {"uf": "BA", "fonte": None, "usina": "X"})
    assert w == "WHERE dia >= %s AND uf = %s AND plant_id = %s" and p == [date(2026, 1, 1), "BA", "X"]


def test_grain():
    assert A.grain(date(2026, 7, 1), date(2026, 9, 30)) == "day"
    assert A.grain(date(2026, 1, 1), date(2026, 9, 30)) == "month"
    assert A.grain(None, date(2026, 9, 30)) == "month"


def test_cold_compute_drains_pool_then_503():
    # Scale-to-zero: every pooled connection is dead and the compute refuses connects for a while.
    class Dead:
        closed = False
        def execute(self, *_):
            raise A.psycopg.OperationalError("server closed the connection")
        def close(self):
            self.closed = True
    pooled = [Dead(), Dead(), Dead()]
    for c in pooled:
        A._idle.put(c)
    connects = []
    real_connect, real_sleep = A._connect, A.time.sleep
    A._connect = lambda: connects.append(1) or Dead()
    A.time.sleep = lambda s: None
    try:
        A.query("SELECT 1")
        raise AssertionError("expected 503")
    except A.HTTPException as e:
        assert e.status_code == 503 and e.detail == "waking"
    finally:
        A._connect, A.time.sleep = real_connect, real_sleep
    assert all(c.closed for c in pooled) and A._idle.empty()
    assert len(connects) == 4  # first try used a pooled conn; the 4 retries each opened a fresh one


class Req:  # the only part of a FastAPI Request the Genie handler reads
    def __init__(self, token=None):
        self.headers = {"x-forwarded-access-token": token} if token else {}


def _status(fn):
    try:
        fn()
    except A.HTTPException as e:
        return e.status_code, e.detail
    raise AssertionError("expected an HTTPException")


def test_genie_runs_as_the_signed_in_user():
    # Spec 14: inside Databricks Apps Genie only ever runs with the user's forwarded token, so UC
    # grants apply per user; locally (no DATABRICKS_APP_NAME) the developer's CLI profile is used.
    os.environ.pop("DATABRICKS_APP_NAME", None)
    w = A._genie_client(Req("user-token"))
    assert w is not A._ws and w.config.token == "user-token"
    assert A._genie_client(Req()) is A._ws
    os.environ["DATABRICKS_APP_NAME"] = "ampera-app"
    try:
        assert _status(lambda: A._genie_client(Req())) == (401, "Autorização do usuário não concedida")
        assert A._genie_client(Req("user-token")).config.token == "user-token"
    finally:
        del os.environ["DATABRICKS_APP_NAME"]


def test_genie_errors_are_typed():
    # A UC permission error is the user's to see (403), not a 500; a failure fetching the query
    # result comes back as a readable 502 too.
    from types import SimpleNamespace as NS
    from databricks.sdk.errors import PermissionDenied, Unauthenticated

    def raises(e):
        def f(*_, **__):
            raise e
        return f
    msg = NS(conversation_id="c", id="m", error=None,
             attachments=[NS(text=None, suggested_questions=None, attachment_id="a", query=NS(query="SELECT 1", description=None))])
    cases = [
        (NS(start_conversation_and_wait=raises(PermissionDenied("no SELECT on table"))), 403),
        (NS(start_conversation_and_wait=raises(Unauthenticated("token expired"))), 401),
        (NS(start_conversation_and_wait=lambda *_, **__: msg,
            get_message_attachment_query_result=raises(RuntimeError("statement failed"))), 502),
    ]
    real, os.environ["GENIE_SPACE_ID"] = A._genie_client, "space"
    try:
        for genie, code in cases:
            A._genie_client = lambda _r, g=genie: NS(genie=g)
            st, detail = _status(lambda: A.genie({"pergunta": "oi"}, Req("t")))
            assert st == code and detail, (st, detail, code)
    finally:
        A._genie_client = real


def test_plant_loads_before_curtailment_is_synced():
    # Spec 14: the curtailment synced table appears only after the first scored refresh; the Usina
    # sheet must still load, with an empty curtailment panel, instead of a 500.
    def fake(sql, params=()):
        if "curtailment_daily" in sql:
            raise A.psycopg.errors.UndefinedTable('relation "ampera_gold_lb.curtailment_daily" does not exist')
        return [{"plant_id": "X.1"}] if "plant_location" in sql else [{"dia": "2026-01-01", "mwh": 1.0}]
    real, A.query = A.query, fake
    try:
        r = A._plant.__wrapped__("X.1", 0)
    finally:
        A.query = real
    assert r["curtailment"] == [] and r["usina"] == {"plant_id": "X.1"} and len(r["dias"]) == 1


def test_totals_tie_live():
    if not os.environ.get("PGHOST"):
        print("skip live check (PGHOST unset)")
        return
    o = A.overview()
    total = o["kpis"]["mwh"]
    plants = sum(r["mwh_total"] or 0 for r in A.plants())
    serie = sum(r["mwh"] or 0 for r in o["serie"])
    assert abs(total - plants) / total < 1e-9 and abs(total - serie) / total < 1e-9, (total, plants, serie)
    assert o["kpis"]["n_usinas"] == len(A.plants())


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
