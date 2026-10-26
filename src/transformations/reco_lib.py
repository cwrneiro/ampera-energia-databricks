"""Pure reconciliation helpers (no pyspark import — importable & testable standalone).

Used by the silver pipeline files as UDFs. The whole point of normalize_ceg is that ONS and
SIGA CEG codes do NOT join raw (0% overlap) but ~92.5% after normalizing the trailing unit
segment. See specs/02-reconciliation-silver.md and tests/test_reconciliation.py.
"""
import hashlib
import re
import unicodedata

THRESHOLD = 0.82  # fuzzy accept bar; tune on real unmatched-MWh (spec 02)
AI_CUTOFF = 0.9  # ai_decide accept bar (confidence); calibrated by notebooks/eval_ai_decide (spec 12)
AI_CHOICES = ("A", "B", "C")  # ai_decide labels that name a candidate; "nenhum" never does

# Durable ai_decide verdicts (plain Delta, outside the pipeline): one row per ONS plant x candidate set x
# prompt, written by notebooks/adjudicate_ai, read by the pipeline. A required input like
# plant_match_override: scripts/bootstrap_workspace.sh creates it empty (a pipeline can't test whether a
# table exists). TRUNCATE it to force a full re-adjudication. Spec 12.
VERDICT = "ampera_silver.ai_decide_verdict"
VERDICT_DDL = ", ".join(
    ["ons_key STRING", "nom_usina STRING", "uf STRING", "fuel_raw STRING", "ceg_raw STRING"]
    + [f"{p}_{c}" for p in "abc" for c in ("id STRING", "nome STRING", "uf STRING", "tipo STRING", "municipio STRING",
                                           "capacidade_mw DOUBLE", "sim DOUBLE")]
    + ["cand_hash STRING", "prompt_hash STRING", "ai_choice STRING", "ai_confidence DOUBLE", "ai_prob_a DOUBLE",
       "ai_prob_b DOUBLE", "ai_prob_c DOUBLE", "ai_prob_nenhum DOUBLE", "ai_error STRING", "ai_plant_id STRING",
       "ai_accepted BOOLEAN", "decided_at TIMESTAMP"])

# Portuguese accent map (uppercase) — mirrored by reco_sql for the Spark `translate` expression.
ACCENTED = "ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ"
PLAIN = "AAAAAEEEEIIIIOOOOOUUUUCN"

# Generic tokens that carry no identifying signal for plant-name matching.
_GENERIC = {
    "USINA", "USINAS", "UHE", "PCH", "CGH", "UFV", "UTE", "UTN", "EOL", "EOLICA", "EOLICAS",
    "EOLICO", "EOLICOS", "PARQUE", "PARQUES", "COMPLEXO", "CONJUNTO", "CENTRAL",
    "HIDRELETRICA", "HIDROELETRICA", "HIDRICA", "HIDRAULICA",
    "TERMELETRICA", "FOTOVOLTAICA", "FOTOVOLTAICO", "SOLAR", "ENERGIA", "ENERGIAS", "GERADORA",
    "SA", "S", "LTDA", "EPP", "DO", "DA", "DE", "DOS", "DAS", "E",
}

_FUEL = {
    "HIDRAULICA": "HID", "UHE": "HID", "PCH": "HID", "CGH": "HID",
    "FOTOVOLTAICA": "SOL", "UFV": "SOL",
    "EOLICA": "EOL", "EOL": "EOL",
    "NUCLEAR": "NUC", "UTN": "NUC",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(name):
    """Uppercase, strip accents/punctuation, drop generic words, sort tokens (order-independent)."""
    if not name:
        return ""
    s = re.sub(r"[^A-Z0-9 ]", " ", strip_accents(str(name)).upper())
    toks = [t for t in s.split() if t and t not in _GENERIC]
    return " ".join(sorted(toks))


def normalize_ceg(ceg):
    """Normalize the trailing unit segment (ONS '.01' vs SIGA '.1'). Missing CEG ('-'/'') -> None."""
    if not ceg:
        return None
    c = str(ceg).strip()
    if c in ("", "-"):
        return None
    parts = c.split(".")
    if parts and parts[-1].isdigit():
        parts[-1] = str(int(parts[-1]))
    return ".".join(parts)


def fuel_class(v):
    """Map ONS fuel descriptor or SIGA SigTipoGeracao to a coarse class."""
    if not v:
        return "OTHER"
    k = strip_accents(str(v)).upper().strip()
    if k in _FUEL:
        return _FUEL[k]
    if k == "UTE" or any(x in k for x in ("GAS", "OLEO", "CARVAO", "BIOMASSA", "BAGACO",
                                          "DIESEL", "TERMICA", "TERM")):
        return "THERM"
    return "OTHER"


NUMERAL_RE = r"^([0-9]+|[IVX]+)$"  # arabic or roman numeral token; mirrored by reco_sql.numerals_col


def numerals(name_norm):
    """Numeral tokens of a normalized name, e.g. 'II PROSPERIDADE' -> ['II']."""
    return sorted(t for t in (name_norm or "").split() if re.match(NUMERAL_RE, t))


def numerals_match(a, b):
    """Plants that differ only by a numeral (Prosperidade II vs III) are different plants."""
    return numerals(a) == numerals(b)


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def name_sim(a, b):
    """Normalized Levenshtein similarity in [0,1]. Mirrors reco_sql.sim_col (F.levenshtein)."""
    if not a or not b:
        return 0.0
    m = max(len(a), len(b))
    return 1.0 - _levenshtein(a, b) / m if m else 0.0


def ai_accept(choice, confidence, plant_id):
    """ai_decide verdict is applied: it names a real candidate (plant_id = the chosen slot's SIGA id) at or
    above AI_CUTOFF. Mirrors reco_sql.ai_accept_col."""
    return choice in AI_CHOICES and plant_id is not None and confidence is not None and confidence >= AI_CUTOFF


def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


def cand_hash(ids):
    """Hash of the A/B/C candidate ids in order (missing -> ''). Mirrors reco_sql.cand_hash_col."""
    return sha256("|".join(i or "" for i in ids))


def verdict_key(ons_key, ids, prompt):
    """A stored ai_decide verdict is reused only for the same plant, candidates and prompt (spec 12)."""
    return ons_key, cand_hash(ids), sha256(prompt)
