"""Ampera app backend: read-only JSON API over Lakebase `gold_lb` + the built React SPA.

Spec: specs/06-app.md. Local run (from app/):
  DATABRICKS_CONFIG_PROFILE=<profile> LAKEBASE_ENDPOINT=projects/ampera-demo/branches/production/endpoints/primary \
  PGHOST=<endpoint host> PGDATABASE=databricks_postgres PGUSER=<your email> uvicorn app:app --reload
"""
import os
import queue
import time
from contextlib import contextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

app = FastAPI(title="Ampera")
app.add_middleware(GZipMiddleware, minimum_size=1000)

_ws = WorkspaceClient()
_token = {"value": None, "at": 0.0}
_idle: "queue.SimpleQueue[psycopg.Connection]" = queue.SimpleQueue()


def _password() -> str:
    # OAuth tokens live 1 h and are only checked at connect time; refresh at 45 min.
    if time.time() - _token["at"] > 45 * 60:
        _token["value"] = _ws.postgres.generate_database_credential(
            endpoint=os.environ["LAKEBASE_ENDPOINT"]).token
        _token["at"] = time.time()
    return _token["value"]


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["PGHOST"], port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "databricks_postgres"), user=os.environ["PGUSER"],
        password=_password(), sslmode="require", autocommit=True, row_factory=dict_row)


@contextmanager
def _conn():
    # ponytail: unbounded idle-connection queue, swap for psycopg_pool if concurrency grows
    try:
        c = _idle.get_nowait()
    except queue.Empty:
        c = _connect()
    try:
        yield c
    except Exception:
        c.close()
        raise
    _idle.put(c)


def _drop_idle():
    while True:
        try:
            _idle.get_nowait().close()
        except queue.Empty:
            return


def query(sql: str, params=()) -> list[dict]:
    # Scale-to-zero kills every pooled connection at once, and a waking compute can refuse a few
    # connects: drop the whole pool, back off, retry. Still waking -> 503 so the UI says so and retries.
    for wait in (0, 0.5, 1, 2, 4):
        time.sleep(wait)
        try:
            with _conn() as c:
                return c.execute(sql, params).fetchall()
        except psycopg.OperationalError:
            _drop_idle()
    raise HTTPException(503, "waking", headers={"Retry-After": "3"})


def _bucket() -> int:
    # Cache key component: cached answers expire every 10 min, so a Lakebase sync shows up soon after.
    return int(time.time() // 600)


# --- filters ---------------------------------------------------------------------------------

FILTER_COLS = {"uf": "uf", "fonte": "fonte", "usina": "plant_id", "conjunto": "conjunto_key"}


def where(de: date | None, ate: date | None, eq: dict) -> tuple[str, list]:
    """WHERE clause + params for generation_daily. `eq` maps FILTER_COLS keys to values (None = off)."""
    parts, params = [], []
    if de:
        parts.append("dia >= %s"); params.append(de)
    if ate:
        parts.append("dia <= %s"); params.append(ate)
    for k, v in eq.items():
        if v:
            parts.append(f"{FILTER_COLS[k]} = %s"); params.append(v)
    return ("WHERE " + " AND ".join(parts)) if parts else "", params


def grain(de: date | None, ate: date | None) -> str:
    """Daily series for short windows (<= ~3 months), monthly otherwise."""
    return "day" if de and ate and (ate - de).days <= 92 else "month"


# --- API -------------------------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    return _meta(_bucket())


@lru_cache(maxsize=4)
def _meta(_b):
    return query("SELECT min(dia) AS de, max(dia) AS ate FROM gold_lb.generation_daily")[0]


@app.get("/api/plants")
def plants():
    return _plants(_bucket())


@lru_cache(maxsize=4)
def _plants(_b):
    return query("""
        SELECT plant_id, ceg, nome, uf, lat, lon, capacidade_mw, fonte, tipo, municipio,
               conjunto_key, nom_conjunto, match_method, mwh_total, mwh_30d, mwh_estimado_total
        FROM gold_lb.plant_location ORDER BY mwh_total DESC NULLS LAST""")


@app.get("/api/reconciliation")
def reconciliation():
    return _reconciliation(_bucket())


@lru_cache(maxsize=4)
def _reconciliation(_b):
    return query("""SELECT grao, mes, match_method, mwh, n_usinas
                    FROM gold_lb.reconciliation_monthly ORDER BY grao, mes, match_method""")


@app.get("/api/overview")
def overview(de: date | None = None, ate: date | None = None, uf: str | None = None,
             fonte: str | None = None, usina: str | None = None, conjunto: str | None = None):
    return _overview(de, ate, uf, fonte, usina, conjunto, _bucket())


@lru_cache(maxsize=256)
def _overview(de, ate, uf, fonte, usina, conjunto, _b):
    w, params = where(de, ate, {"uf": uf, "fonte": fonte, "usina": usina, "conjunto": conjunto})
    g = grain(de, ate)
    # One scan of generation_daily, four groupings (series, by fonte, by plant, by conjunto).
    rows = query(f"""
        SELECT CASE GROUPING(p, fonte, plant_id, conjunto_key)
                 WHEN 3 THEN 'serie' WHEN 11 THEN 'fonte' WHEN 13 THEN 'usina' ELSE 'conjunto' END AS g,
               p, fonte, plant_id, conjunto_key, max(nome) AS nome, max(nom_conjunto) AS nom_conjunto,
               max(uf) AS uf, count(DISTINCT plant_id) AS n_usinas,
               sum(mwh) AS mwh, sum(mwh_estimado) AS mwh_estimado, sum(valor_rs) AS valor_rs,
               avg(pld_medio_rs_mwh) AS pld_medio
        FROM (SELECT date_trunc('{g}', dia)::date AS p, * FROM gold_lb.generation_daily {w}) t
        GROUP BY GROUPING SETS ((p, fonte), (fonte), (plant_id), (conjunto_key))""", params)
    by = {k: [r for r in rows if r["g"] == k] for k in ("serie", "fonte", "usina", "conjunto")}
    for r in by["fonte"]:
        r["pld_capturado"] = r["valor_rs"] / r["mwh"] if r["mwh"] else None
    tot = lambda col: sum(r[col] or 0 for r in by["fonte"])  # noqa: E731
    top = lambda rs: sorted(rs, key=lambda r: -(r["mwh"] or 0))[:15]  # noqa: E731
    return {
        "grao": g,
        "kpis": {"mwh": tot("mwh"), "mwh_estimado": tot("mwh_estimado"), "valor_rs": tot("valor_rs"),
                 "pld_capturado": tot("valor_rs") / tot("mwh") if tot("mwh") else None,
                 "n_usinas": len(by["usina"])},
        "serie": [{k: r[k] for k in ("p", "fonte", "mwh", "mwh_estimado")} for r in by["serie"]],
        "fontes": [{k: r[k] for k in ("fonte", "mwh", "pld_medio", "pld_capturado", "n_usinas")}
                   for r in by["fonte"]],
        "ranking_usinas": [{k: r[k] for k in ("plant_id", "nome", "uf", "mwh", "mwh_estimado")}
                           for r in top(by["usina"])],
        "ranking_conjuntos": [{k: r[k] for k in ("conjunto_key", "nom_conjunto", "uf", "n_usinas", "mwh",
                                                 "mwh_estimado")}
                              for r in top(r for r in by["conjunto"] if r["conjunto_key"])],
    }


@app.get("/api/plant/{plant_id}")
def plant(plant_id: str):
    return _plant(plant_id, _bucket())


@lru_cache(maxsize=128)
def _plant(plant_id, _b):
    info = query("SELECT * FROM gold_lb.plant_location WHERE plant_id = %s", (plant_id,))
    if not info:
        raise HTTPException(404, "Usina não encontrada")
    days = query("""
        SELECT dia, mwh, mwh_estimado, match_method, pld_medio_rs_mwh, pld_capturado_rs_mwh, valor_rs,
               vento_100m_ms_modelo, irradiancia_wm2_modelo, temp_c_modelo, precip_mm_modelo,
               vento_ms_medido, irradiancia_wm2_medida, fonte_medicao
        FROM gold_lb.generation_daily WHERE plant_id = %s ORDER BY dia""", (plant_id,))
    return {"usina": info[0], "dias": days}


_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.exists():  # SPA uses hash routing, so static files + index.html are enough
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
