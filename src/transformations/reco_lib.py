"""Pure reconciliation helpers (no pyspark import — importable & testable standalone).

Used by the silver pipeline files as UDFs. The whole point of normalize_ceg is that ONS and
SIGA CEG codes do NOT join raw (0% overlap) but ~92.5% after normalizing the trailing unit
segment. See specs/02-reconciliation-silver.md and tests/test_reconciliation.py.
"""
import re
import unicodedata

THRESHOLD = 0.82  # fuzzy accept bar; tune on real unmatched-MWh (spec 02)

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
