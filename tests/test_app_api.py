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
