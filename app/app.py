"""Ampera app backend: read-only JSON API over Lakebase `ampera_gold_lb` + the built React SPA.

Spec: specs/06-app.md. Local run (from app/):
  DATABRICKS_CONFIG_PROFILE=<profile> LAKEBASE_ENDPOINT=projects/ampera-demo/branches/production/endpoints/primary \
  PGHOST=<endpoint host> PGDATABASE=databricks_postgres PGUSER=<your email> uvicorn app:app --reload
"""
import os
import queue
import time
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import PermissionDenied, Unauthenticated
from fastapi import FastAPI, HTTPException, Request
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
IN_SCOPE = "plant_id IN (SELECT plant_id FROM ampera_gold_lb.client_plant_access WHERE principal = %s)"


def where(de: date | None, ate: date | None, eq: dict, scope: str | None = None) -> tuple[str, list]:
    """WHERE clause + params for generation_daily. `eq` maps FILTER_COLS keys to values (None = off);
    `scope` = a client principal, limited to its plants (spec 17)."""
    parts, params = [], []
    if scope:
        parts.append(IN_SCOPE); params.append(scope)
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


# --- client scope (spec 17) -------------------------------------------------------------------
# Synced tables can't carry Unity Catalog row filters, so the app applies the same mapping as
# ampera_gold.client_plant_filter: a signed-in principal listed in client_plant_access sees only its
# plants; anyone else (Ampera staff) sees all. Genie needs none of this: it runs as the user, so UC
# filters it.

def scope(request: Request) -> str | None:
    """The signed-in principal if it acts for a client, else None (all plants)."""
    who = request.headers.get("x-forwarded-email")
    if not who:
        if os.environ.get("DATABRICKS_APP_NAME"):  # Apps always forwards the user; never guess
            raise HTTPException(401, "Usuário não identificado")
        return None  # local dev
    return who if _cliente(who, _bucket()) else None


@lru_cache(maxsize=256)
def _cliente(who, _b) -> str | None:
    try:
        r = query("SELECT min(cliente) AS cliente FROM ampera_gold_lb.client_plant_access WHERE principal = %s", (who,))
    except psycopg.errors.UndefinedTable:  # access model not synced yet: no client mapping exists
        return None
    return r[0]["cliente"]


def staff_only(request: Request):
    # Market-wide reconciliation is Ampera's internal view; clients aren't granted it in UC either.
    if scope(request):
        raise HTTPException(403, "Disponível apenas para a equipe Ampera")


@app.get("/api/me")
def me(request: Request):
    who = scope(request)
    return {"cliente": _cliente(who, _bucket()) if who else None}


# --- API -------------------------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    return _meta(_bucket())


@lru_cache(maxsize=4)
def _meta(_b):
    return query("SELECT min(dia) AS de, max(dia) AS ate FROM ampera_gold_lb.generation_daily")[0]


@app.get("/api/plants")
def plants(request: Request):
    return _plants(scope(request), _bucket())


@lru_cache(maxsize=64)
def _plants(sc, _b):
    w, params = (f"WHERE {IN_SCOPE}", (sc,)) if sc else ("", ())
    return query(f"""
        SELECT plant_id, ceg, nome, uf, lat, lon, capacidade_mw, fonte, tipo, municipio,
               conjunto_key, nom_conjunto, match_method, mwh_total, mwh_30d, mwh_estimado_total
        FROM ampera_gold_lb.plant_location {w} ORDER BY mwh_total DESC NULLS LAST""", params)


@app.get("/api/reconciliation")
def reconciliation(request: Request):
    staff_only(request)
    return _reconciliation(_bucket())


@lru_cache(maxsize=4)
def _reconciliation(_b):
    return query("""SELECT grao, mes, match_method, mwh, n_usinas
                    FROM ampera_gold_lb.reconciliation_monthly ORDER BY grao, mes, match_method""")


@app.get("/api/overview")
def overview(request: Request, de: date | None = None, ate: date | None = None, uf: str | None = None,
             fonte: str | None = None, usina: str | None = None, conjunto: str | None = None):
    return _overview(de, ate, uf, fonte, usina, conjunto, scope(request), _bucket())


@lru_cache(maxsize=256)
def _overview(de, ate, uf, fonte, usina, conjunto, sc, _b):
    w, params = where(de, ate, {"uf": uf, "fonte": fonte, "usina": usina, "conjunto": conjunto}, sc)
    g = grain(de, ate)
    # One scan of generation_daily, four groupings (series, by fonte, by plant, by conjunto).
    rows = query(f"""
        SELECT CASE GROUPING(p, fonte, plant_id, conjunto_key)
                 WHEN 3 THEN 'serie' WHEN 11 THEN 'fonte' WHEN 13 THEN 'usina' ELSE 'conjunto' END AS g,
               p, fonte, plant_id, conjunto_key, max(nome) AS nome, max(nom_conjunto) AS nom_conjunto,
               max(uf) AS uf, count(DISTINCT plant_id) AS n_usinas,
               sum(mwh) AS mwh, sum(mwh_estimado) AS mwh_estimado, sum(valor_rs) AS valor_rs,
               avg(pld_medio_rs_mwh) AS pld_medio
        FROM (SELECT date_trunc('{g}', dia)::date AS p, * FROM ampera_gold_lb.generation_daily {w}) t
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
def plant(plant_id: str, request: Request):
    return _plant(plant_id, scope(request), _bucket())


@lru_cache(maxsize=128)
def _plant(plant_id, sc, _b):
    w, params = (f" AND {IN_SCOPE}", (plant_id, sc)) if sc else ("", (plant_id,))
    info = query(f"SELECT * FROM ampera_gold_lb.plant_location WHERE plant_id = %s{w}", params)
    if not info:
        raise HTTPException(404, "Usina não encontrada")
    days = query("""
        SELECT dia, mwh, mwh_estimado, match_method, pld_medio_rs_mwh, pld_capturado_rs_mwh, valor_rs,
               vento_100m_ms_modelo, irradiancia_wm2_modelo, temp_c_modelo, precip_mm_modelo,
               vento_ms_medido, irradiancia_wm2_medida, fonte_medicao
        FROM ampera_gold_lb.generation_daily WHERE plant_id = %s ORDER BY dia""", (plant_id,))
    try:
        curt = query("""
            SELECT dia, mwh_esperado, mwh_restrito, valor_rs_perdido, horas_restritas_modelo, horas_restritas_ons
            FROM ampera_gold_lb.curtailment_daily WHERE plant_id = %s ORDER BY dia""", (plant_id,))
    except psycopg.errors.UndefinedTable:  # not synced yet (first refresh): empty panel, not a 500
        curt = []
    try:  # grounded PT-BR explanation from the narrative step (spec 16); none for plants without losses
        narr = query("""SELECT narrativa, endpoint, model_version, gerado_em
                        FROM ampera_gold_lb.curtailment_narrative WHERE plant_id = %s""", (plant_id,))
    except psycopg.errors.UndefinedTable:
        narr = []
    return {"usina": info[0], "dias": days, "curtailment": curt, "narrativa": narr[0] if narr else None}


# --- curtailment (ML, spec 11) ----------------------------------------------------------------

@app.get("/api/curtailment")
def curtailment(request: Request, de: date | None = None, ate: date | None = None, uf: str | None = None,
                fonte: str | None = None):
    return _curtailment(de, ate, uf, fonte, scope(request), _bucket())


@lru_cache(maxsize=64)
def _curtailment(de, ate, uf, fonte, sc, _b):
    w, params = where(de, ate, {"uf": uf, "fonte": fonte}, sc)
    t = "ampera_gold_lb.curtailment_daily"
    serie = query(f"""
        SELECT date_trunc('month', dia)::date AS mes, fonte, sum(mwh) AS mwh, sum(mwh_esperado) AS mwh_esperado,
               sum(mwh_restrito) AS mwh_restrito, sum(valor_rs_perdido) AS valor_rs_perdido
        FROM {t} {w} GROUP BY 1, 2 ORDER BY 1, 2""", params)
    usinas = query(f"""
        SELECT plant_id, max(nome) AS nome, max(uf) AS uf, max(fonte) AS fonte, max(capacidade_mw) AS capacidade_mw,
               sum(mwh) AS mwh, sum(mwh_restrito) AS mwh_restrito, sum(valor_rs_perdido) AS valor_rs_perdido,
               sum(horas_restritas_modelo) AS horas_modelo, sum(horas_restritas_ons) AS horas_ons
        FROM {t} {w} GROUP BY plant_id ORDER BY valor_rs_perdido DESC NULLS LAST LIMIT 25""", params)
    return {"serie": serie, "usinas": usinas}


# --- ai_decide review queue (GenAI, spec 12) ------------------------------------------------

@app.get("/api/reconciliation/ai")
def reconciliation_ai(request: Request):
    staff_only(request)
    return _reconciliation_ai(_bucket())


@lru_cache(maxsize=4)
def _reconciliation_ai(_b):
    return query("SELECT * FROM ampera_gold_lb.reconciliation_ai_review ORDER BY mwh_total DESC NULLS LAST")


# --- Genie chat, on behalf of the signed-in user (spec 14) ------------------------------------

def _genie_client(request: Request) -> WorkspaceClient:
    # Databricks Apps forwards the user's token when user authorization (scope dashboards.genie) is on:
    # Genie then runs as that user, so Unity Catalog grants apply per user. Inside Apps
    # (DATABRICKS_APP_NAME is set by the runtime) a missing token is refused, never the app's service
    # principal. Local dev: the CLI profile.
    tok = request.headers.get("x-forwarded-access-token")
    if tok:
        return WorkspaceClient(host=_ws.config.host, token=tok, auth_type="pat")
    if os.environ.get("DATABRICKS_APP_NAME"):
        raise HTTPException(401, "Autorização do usuário não concedida")
    return _ws


GENIE_WAIT = timedelta(seconds=110)


@app.post("/api/genie")
def genie(body: dict, request: Request):
    q = (body.get("pergunta") or "").strip()
    if not q:
        raise HTTPException(400, "Pergunta vazia")
    w, space = _genie_client(request), os.environ["GENIE_SPACE_ID"]
    try:
        m = (w.genie.create_message_and_wait(space, body["conversa"], q, timeout=GENIE_WAIT) if body.get("conversa")
             else w.genie.start_conversation_and_wait(space, q, timeout=GENIE_WAIT))
        return _answer(w, space, m)
    except PermissionDenied as e:  # UC grants: the user's to see, not a 500
        raise HTTPException(403, str(e)[:400])
    except Unauthenticated as e:
        raise HTTPException(401, str(e)[:400])
    except Exception as e:  # Genie failed or timed out, incl. fetching the query result
        raise HTTPException(502, str(e)[:400] or type(e).__name__)


def _answer(w: WorkspaceClient, space: str, m) -> dict:
    out = {"conversa": m.conversation_id, "mensagem": m.id, "texto": None, "sql": None,
           "descricao": None, "colunas": [], "linhas": [], "sugestoes": []}
    for a in m.attachments or []:
        if a.text and a.text.content:
            out["texto"] = a.text.content
        if a.suggested_questions and a.suggested_questions.questions:
            out["sugestoes"] = a.suggested_questions.questions
        if a.query:
            out["sql"], out["descricao"] = a.query.query, a.query.description
            r = w.genie.get_message_attachment_query_result(space, m.conversation_id, m.id, a.attachment_id)
            sr = r.statement_response
            if sr and sr.manifest and sr.manifest.schema:
                out["colunas"] = [{"nome": c.name, "tipo": c.type_name.value if c.type_name else "STRING"}
                                  for c in sr.manifest.schema.columns]
                out["linhas"] = (sr.result.data_array or [])[:500] if sr.result else []
    if m.error and not out["texto"] and not out["sql"]:
        out["texto"] = f"Genie não conseguiu responder: {m.error.error}"
    return out


_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.exists():  # SPA uses hash routing, so static files + index.html are enough
    app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
