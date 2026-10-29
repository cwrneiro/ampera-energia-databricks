"""Curtailment narrative rules (spec 16). Pure: imported by notebooks/narrate_curtailment, tested by
tests/test_narrative.py.

Each plant with R$ lost gets a short PT-BR explanation written by an LLM from a facts JSON built here
from gold. The facts carry every number pre-formatted, the prompt says to copy them as written, and
`grounded` rejects a narrative that cites any number not in the facts — so what the app shows can't
invent a figure. Narratives are stored keyed by plant + facts hash + prompt hash (like the ai_decide
verdicts): a refresh with unchanged numbers asks nothing; a new model version or prompt re-asks.
"""
import hashlib
import json
import re

ENDPOINT = "databricks-claude-sonnet-5-5"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE = {"EOL": "eólica", "SOL": "solar"}
PLURAL = {"EOL": "eólicas", "SOL": "solares"}

PROMPT = """Você escreve para clientes de uma empresa de análise do setor elétrico brasileiro.
Explique em português do Brasil, em 2 ou 3 frases (no máximo 70 palavras), quanto a usina abaixo perdeu
por curtailment (restrição de geração ordenada pelo ONS) e quando isso se concentrou.
Regras:
- Use apenas os fatos do JSON. Copie cada número exatamente como está escrito no JSON; não calcule,
  não arredonde e não invente números, datas ou causas.
- Diga que o valor é um limite inferior.
- Texto corrido, sem títulos, listas, aspas ou markdown.
Fatos: """

PROMPT_HASH = hashlib.sha256(f"{ENDPOINT}\n{PROMPT}".encode()).hexdigest()


def num(x, dec=1):
    """PT-BR number: 1234.56 -> '1.234,6'."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def mes(d):
    """date -> 'ago/2025'."""
    return f"{MESES[d.month - 1]}/{d.year}"


def energia(mwh):
    return f"{num(mwh / 1e3)} GWh" if mwh >= 1e3 else f"{num(mwh, 0)} MWh"


def reais(rs):
    return f"R$ {num(rs / 1e6, 2)} milhões" if rs >= 1e6 else f"R$ {num(rs / 1e3, 0)} mil"


def facts(p, meses_top, rank, n_pares):
    """Facts JSON (dict of strings) for one plant.

    p: plant totals {nome, fonte, uf, submercado, capacidade_mw, de, ate, mwh_restrito, valor_rs_perdido,
       mwh_esperado, horas_restritas_modelo, horas_restritas_ons (None = ONS publishes no flag)}.
    meses_top: up to 3 {mes (date), mwh_restrito, valor_rs_perdido}, worst first.
    rank / n_pares: position by R$ lost among plants of the same fonte and UF.
    """
    fonte = FONTE.get(p["fonte"], p["fonte"])
    return {
        "usina": p["nome"], "fonte": fonte, "uf": p["uf"], "submercado": p["submercado"],
        "capacidade": f"{num(p['capacidade_mw'])} MW" if p["capacidade_mw"] else "n/d",
        "periodo": f"{mes(p['de'])} a {mes(p['ate'])}",
        "energia_perdida": energia(p["mwh_restrito"]),
        "valor_perdido": reais(p["valor_rs_perdido"]),
        "parcela_do_esperado": f"{num(100 * p['mwh_restrito'] / p['mwh_esperado'])}%" if p["mwh_esperado"] else "n/d",
        "pld_medio_da_energia_perdida": f"R$ {num(p['valor_rs_perdido'] / p['mwh_restrito'], 0)}/MWh",
        "horas_restritas_modelo": num(p["horas_restritas_modelo"], 0),
        "horas_restritas_ons": "sem registro do ONS" if p["horas_restritas_ons"] is None else num(p["horas_restritas_ons"], 0),
        "ranking": f"{rank}ª de {n_pares} usinas {PLURAL.get(p['fonte'], fonte)} em {p['uf']} por R$ perdido",
        "piores_meses": [{"mes": mes(m["mes"]), "energia_perdida": energia(m["mwh_restrito"]),
                          "valor_perdido": reais(m["valor_rs_perdido"])} for m in meses_top],
        "limite_inferior": "o modelo marca uma hora como restrita com 80% de precisão frente às marcações do ONS, "
                           "então a perda real é maior",
    }


def facts_json(f):
    """Canonical JSON: the prompt input and the hash input."""
    return json.dumps(f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def facts_hash(f):
    return hashlib.sha256(facts_json(f).encode()).hexdigest()


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def numbers(text):
    """Numeric tokens, trailing separators dropped ('5,3' and '2025' from 'R$ 5,3 milhões em 2025.')."""
    return {m.group(0) for m in _NUM.finditer(text)}


def grounded(text, f):
    """True when every number in the narrative appears verbatim in the facts."""
    return bool(text and text.strip()) and numbers(text) <= numbers(facts_json(f))
